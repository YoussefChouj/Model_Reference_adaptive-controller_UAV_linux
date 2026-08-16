"""Tests for ground_station.ulog_reader."""
from __future__ import annotations

import struct
import tempfile
from pathlib import Path

import numpy as np
import pytest

from ground_station.ulog_reader import (
    ULogReader,
    load_ulog,
    _ulog_to_dwarf,
    ResolvedField,
    UnresolvedField,
)


# ---------------------------------------------------------------------------
# Synthetic ulog helpers
# ---------------------------------------------------------------------------

def _make_synthetic_ulog(path: Path) -> None:
    """Write a minimal synthetic .ulg with two topics using the pyulog API.

    Builds a valid binary ulog by manually assembling the format sections
    rather than fighting the pyulog internal parsing machinery.
    """
    from pyulog.core import ULog

    # Pre-compute flat field lists (name, type_str)
    att_fields = [
        ("timestamp", "uint64_t"),
        ("q[0]",      "float"),
        ("q[1]",      "float"),
        ("q[2]",      "float"),
        ("q[3]",      "float"),
        ("roll",      "float"),
        ("pitch",     "float"),
        ("yaw",       "float"),
    ]
    loc_fields = [
        ("timestamp", "uint64_t"),
        ("x",  "float"),
        ("y",  "float"),
        ("z",  "float"),
        ("vx", "float"),
        ("vy", "float"),
        ("vz", "float"),
    ]

    def _flat_dtype(fields):
        """Build a numpy dtype for flat (non-nested) fields."""
        dtype_list = []
        for fname, ftype in fields:
            np_t = ULog._UNPACK_TYPES[ftype][2]
            dtype_list.append((fname, np_t))
        return np.dtype(dtype_list).newbyteorder("<")

    att_dtype = _flat_dtype(att_fields)
    loc_dtype = _flat_dtype(loc_fields)

    # Build numpy row arrays
    ts_us = np.arange(500_000, 2_050_000, 250_000, dtype=np.uint64)
    n = len(ts_us)

    att_rows = np.zeros(n, dtype=att_dtype)
    att_rows["timestamp"] = ts_us
    att_rows["q[0]"] = np.ones(n, dtype=np.float32)
    att_rows["q[1]"] = np.zeros(n, dtype=np.float32)
    att_rows["q[2]"] = np.zeros(n, dtype=np.float32)
    att_rows["q[3]"] = np.zeros(n, dtype=np.float32)
    att_rows["roll"]  = np.linspace(0.1, 0.7,  n, dtype=np.float32)
    att_rows["pitch"] = np.linspace(-0.2, 0.2, n, dtype=np.float32)
    att_rows["yaw"]   = np.linspace(0.0, 1.0,  n, dtype=np.float32)

    loc_rows = np.zeros(n, dtype=loc_dtype)
    loc_rows["timestamp"] = ts_us
    loc_rows["x"]  = np.linspace(0.0, 1.0, n, dtype=np.float32)
    loc_rows["y"]  = np.linspace(0.0, 0.5, n, dtype=np.float32)
    loc_rows["z"]  = np.linspace(-0.5, -1.0, n, dtype=np.float32)
    loc_rows["vx"] = np.full(n, 0.5, dtype=np.float32)
    loc_rows["vy"] = np.full(n, 0.2, dtype=np.float32)
    loc_rows["vz"] = np.full(n, -0.3, dtype=np.float32)

    # Assemble binary ulog
    with open(path, "wb") as fh:
        # -- file header (exactly 16 bytes) --------------------------------------
        # Bytes 0-6: magic "ULog\x01\x125" (matches ULog.HEADER_BYTES)
        # Byte 7: version (= 1)
        # Bytes 8-15: start_timestamp (uint64, microseconds)
        header = bytearray(16)
        header[:len(ULog.HEADER_BYTES)] = ULog.HEADER_BYTES
        header[7] = 1  # version
        struct.pack_into("<Q", header, 8, 1_000_000)
        fh.write(bytes(header))

        def _write_section(msg_type, data):
            fh.write(struct.pack("<HB", len(data), msg_type))
            fh.write(data)

        # -- flags (3*8 zero bytes for compat/incompat/offsets) -----------------
        flags = bytes(8 + 8 + 24)                  # compat(8) + incompat(8) + offsets(24)
        _write_section(ULog.MSG_TYPE_FLAG_BITS, flags)

        # -- message format sections -------------------------------------------
        def _write_format(name, fields):
            # "name:type field;type field;..." — no trailing null; parse_string stops at \0
            fmt_str = name + ":" + ";".join(
                f"{ftype} {fname}" for fname, ftype in fields
            )
            _write_section(ULog.MSG_TYPE_FORMAT, fmt_str.encode("utf-8") + b"\x00")

        _write_format("vehicle_attitude",        att_fields)
        _write_format("vehicle_local_position", loc_fields)

        # -- subscription: ADD_LOGGED_MSG for each topic ----------------------
        def _write_subscription(topic_name, fields, msg_id):
            # multi_id (uint8) + msg_id (uint16) + format_name (raw, no null)
            fmt_bytes = topic_name.encode("utf-8")
            data = struct.pack("<BH", 0, msg_id) + fmt_bytes
            _write_section(ULog.MSG_TYPE_ADD_LOGGED_MSG, data)

        _write_subscription("vehicle_attitude",        att_fields, 1)
        _write_subscription("vehicle_local_position", loc_fields, 2)

        # -- data section: DATA messages for each sample ----------------------
        def _write_sample(msg_id, row, fields):
            data = struct.pack("<H", msg_id)        # 2-byte msg_id
            for fname, ftype in fields:
                fmt_char = ULog._UNPACK_TYPES[ftype][0]
                val = row[fname]
                if fmt_char == 'c':                 # char -> single byte
                    data += struct.pack("<c", bytes(str(val), "utf-8"))
                else:
                    data += struct.pack("<" + fmt_char, val)
            _write_section(ULog.MSG_TYPE_DATA, data)

        for i in range(n):
            _write_sample(1, att_rows[i], att_fields)
            _write_sample(2, loc_rows[i], loc_fields)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def synthetic_ulg(tmp_path) -> Path:
    path = tmp_path / "synth.ulg"
    _make_synthetic_ulog(path)
    return path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_load_ulog_returns_topics(synthetic_ulg):
    reader = load_ulog(synthetic_ulg)
    topics = reader.topics
    assert "vehicle_attitude" in topics
    assert "vehicle_local_position" in topics


def test_at_returns_snapshot(synthetic_ulg):
    reader = load_ulog(synthetic_ulg)
    snap = reader.at(t_seconds=1.0)
    # Should have both topics
    assert "vehicle_attitude" in snap
    assert "vehicle_local_position" in snap
    att = snap["vehicle_attitude"]
    assert "q[0]" in att   # ulog field names use brackets, not bare "q"
    assert "roll" in att


def test_between_filters_by_time(synthetic_ulg):
    reader = load_ulog(synthetic_ulg)
    sliced = reader.between(t0=0.5, t1=1.5)
    for name, df in sliced.items():
        assert df.index.min() >= 0.5
        assert df.index.max() < 1.5


def test_no_elf_path_works(synthetic_ulg):
    reader = ULogReader(synthetic_ulg, elf_path=None)
    assert reader.topics == ["vehicle_attitude", "vehicle_local_position"]
    df = reader.topic("vehicle_attitude")
    assert "roll" in df.columns
    # No resolved_ columns when no elf
    assert all(not c.startswith("resolved_") for c in df.columns)


def test_dwarf_resolution_no_elf(synthetic_ulg):
    reader = ULogReader(synthetic_ulg, elf_path=None)
    results = reader.fields_resolved()
    assert all(isinstance(r, UnresolvedField) for r in results)


def test_corrupt_ulog_raises_friendly(tmp_path):
    bad = tmp_path / "corrupt.ulg"
    bad.write_bytes(b"not a ulog file at all")
    with pytest.raises(ValueError, match="not a valid ulog"):
        load_ulog(bad)


def test_ulog_to_dwarf():
    # Split-based: all underscores in the base become dots.
    # s_ekf_x_3 -> s.ekf.x[3] (every underscore becomes a dot)
    # The DWARF resolver then tries this against DWARF names; if the base
    # name has underscores (like s_ekf), the full DWARF path needs to match.
    assert _ulog_to_dwarf("s_ekf_x_3") == "s.ekf.x[3]"
    assert _ulog_to_dwarf("q_0")       == "q[0]"
    assert _ulog_to_dwarf("s_ekf_x")  is None  # no trailing index
    assert _ulog_to_dwarf("timestamp") is None
    assert _ulog_to_dwarf("roll")      is None


def test_resolved_twins_without_elf(synthetic_ulg):
    """Resolved columns must not appear when elf_path is None."""
    reader = ULogReader(synthetic_ulg, elf_path=None)
    df = reader.topic("vehicle_attitude")
    assert not any(c.startswith("resolved_") for c in df.columns)


def test_between_with_topic_filter(synthetic_ulg):
    reader = load_ulog(synthetic_ulg)
    sliced = reader.between(0.6, 1.4)
    assert "vehicle_attitude" in sliced
    assert "vehicle_local_position" in sliced
    # All returned frames should respect the window
    for df in sliced.values():
        assert df.index.min() >= 0.6
        assert df.index.max() < 1.4


# ---------------------------------------------------------------------------
# DWARF resolution tests — require OBJ/JX_FLY.axf
# ---------------------------------------------------------------------------

def test_dwarf_resolution_ambiguous(synthetic_ulg, tmp_path, monkeypatch):
    """No-match ELF path -> all fields unresolved, no crash."""
    # Use a path that definitely has no DWARF info
    fake_elf = tmp_path / "empty.o"
    fake_elf.write_bytes(b"\x7fELF")      # minimal ELF header, no DWARF

    reader = ULogReader(synthetic_ulg, elf_path=fake_elf)
    results = reader.fields_resolved()
    assert all(isinstance(r, UnresolvedField) for r in results)


@pytest.fixture
def real_elf_path() -> Path | None:
    """Path to firmware ELF if it exists in the standard location."""
    candidates = [
        Path("OBJ/JX_FLY.axf"),
        Path("../OBJ/JX_FLY.axf"),
    ]
    for p in candidates:
        if p.exists():
            return p.resolve()
    return None


def test_dwarf_resolution_with_real_elf(synthetic_ulg, real_elf_path):
    if real_elf_path is None:
        pytest.skip("OBJ/JX_FLY.axf not found")

    reader = ULogReader(synthetic_ulg, elf_path=real_elf_path)
    df = reader.topic("vehicle_attitude")
    # Should have both raw and resolved_ columns
    assert "roll" in df.columns
    resolved_cols = [c for c in df.columns if c.startswith("resolved_")]
    assert len(resolved_cols) > 0, "Expected at least one resolved_ column"
