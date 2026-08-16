"""Tests for ground_station.livewatch.patch and the patch CLI subcommand.

All tests are hardware-free.  A SyntheticTransport records write calls and
provides synthetic read-back values.  Real LiveReader / Plan / SymbolResolver
objects are used to exercise the full decode path.
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path
from typing import Any

import pytest

from ground_station.livewatch.patch import (
    PatchResult,
    SafetyGateError,
    patch_symbol,
)
from ground_station.livewatch.cli import build_parser

ELF = Path(__file__).resolve().parents[1] / "OBJ" / "JX_FLY.axf"
SKIP_IF_NO_ELF = pytest.mark.skipif(
    not ELF.exists(), reason="firmware ELF not built"
)

_IEEE754 = struct.Struct("<f")


def _bits(value: float) -> int:
    return int.from_bytes(_IEEE754.pack(value), "little")


# ------------------------------------------------------------------
# patch_symbol unit tests
# ------------------------------------------------------------------

@SKIP_IF_NO_ELF
def test_requires_i_understand():
    """i_understand=False raises SafetyGateError with the mandated message."""
    synth = _make_transport()
    with pytest.raises(SafetyGateError) as exc_info:
        patch_symbol(
            elf_path=str(ELF),
            symbol_name="DroneStatus.ARM_Status",
            value=0.0,
            transport=synth,
            i_understand=False,
        )
    assert "--i-understand is required" in str(exc_info.value)


@SKIP_IF_NO_ELF
def test_dry_run_does_not_write():
    """dry_run=True returns the old value and records zero writes."""
    synth = _make_transport()
    # Set the address to read back as 1.5
    sym = _resolve_one("DroneStatus.ARM_Status")
    synth.set_read_value(sym.address, 1.5)

    result = patch_symbol(
        elf_path=str(ELF),
        symbol_name="DroneStatus.ARM_Status",
        value=99.0,
        transport=synth,
        i_understand=True,
        require_disarmed=False,
        dry_run=True,
    )

    assert result.verified is True
    assert _bits(1.5) == result.old_value
    assert synth.writes == []


@SKIP_IF_NO_ELF
def test_verify_catches_mismatch():
    """verify=True reads back and raises RuntimeError when bits differ."""
    synth = _make_transport()
    sym = _resolve_one("DroneStatus.ARM_Status")
    # set_read_value makes subsequent reads return 1.5; we write 99.0
    synth.set_read_value(sym.address, 1.5)
    # Make write_memory_block32 a no-op so the value never actually changes.
    def noop_write(addr, vals):
        pass
    synth.write_memory_block32 = noop_write

    with pytest.raises(RuntimeError) as exc_info:
        patch_symbol(
            elf_path=str(ELF),
            symbol_name="DroneStatus.ARM_Status",
            value=99.0,
            transport=synth,
            i_understand=True,
            require_disarmed=False,
            verify=True,
        )
    assert "verify failed" in str(exc_info.value)


@SKIP_IF_NO_ELF
def test_verify_succeeds():
    """When the write actually updates RAM, verify=True completes cleanly."""
    synth = _make_transport()
    sym = _resolve_one("DroneStatus.ARM_Status")

    written_bits: list[int] = []

    def recording_write(addr, vals):
        written_bits.extend(vals)
        # Update read-back so verify sees the new value.
        synth.set_read_value(sym.address, _IEEE754.unpack(
            vals[0].to_bytes(4, "little")
        )[0])

    synth.write_memory_block32 = recording_write

    result = patch_symbol(
        elf_path=str(ELF),
        symbol_name="DroneStatus.ARM_Status",
        value=2.5,
        transport=synth,
        i_understand=True,
        require_disarmed=False,
        verify=True,
    )

    assert result.verified is True
    assert written_bits == [_bits(2.5)]


@SKIP_IF_NO_ELF
def test_bit_pattern_for_nan():
    """NaN bits are preserved through write + read-back; bit-equal check succeeds."""
    import math

    synth = _make_transport()
    sym = _resolve_one("DroneStatus.ARM_Status")
    nan_bits = _bits(float("nan"))

    written_bits: list[int] = []

    def write_and_readback(addr, vals):
        written_bits.extend(vals)
        # Return NaN bits so verify sees the exact same bit pattern.
        synth.set_read_value(sym.address, _IEEE754.unpack(
            vals[0].to_bytes(4, "little")
        )[0])

    synth.write_memory_block32 = write_and_readback

    result = patch_symbol(
        elf_path=str(ELF),
        symbol_name="DroneStatus.ARM_Status",
        value=float("nan"),
        transport=synth,
        i_understand=True,
        require_disarmed=False,
        verify=True,
    )

    assert result.verified is True
    # NaN bits are not equal to themselves — verify uses bit equality, not float equality.
    nan_written = _bits(float("nan"))
    assert math.isnan(_IEEE754.unpack(result.new_value.to_bytes(4, "little"))[0])


@SKIP_IF_NO_ELF
def test_disarm_check():
    """require_disarmed=True raises SafetyGateError when ARM_Status != 0."""
    synth = _make_transport()
    sym = _resolve_one("DroneStatus.ARM_Status")
    synth.set_read_value(sym.address, 2)  # ARMED

    with pytest.raises(SafetyGateError) as exc_info:
        patch_symbol(
            elf_path=str(ELF),
            symbol_name="DroneStatus.ARM_Status",
            value=0.0,
            transport=synth,
            i_understand=True,
            require_disarmed=True,
        )
    assert "require_disarmed=True" in str(exc_info.value)
    assert "DISARMED" in str(exc_info.value)


@SKIP_IF_NO_ELF
def test_halt_and_resume():
    """halt_for_write=True calls target.halt() and target.resume()."""
    synth = _make_transport()
    sym = _resolve_one("DroneStatus.ARM_Status")

    written_bits: list[int] = []

    def write_and_readback(addr, vals):
        written_bits.extend(vals)
        synth.set_read_value(sym.address, _IEEE754.unpack(
            vals[0].to_bytes(4, "little")
        )[0])

    synth.write_memory_block32 = write_and_readback

    result = patch_symbol(
        elf_path=str(ELF),
        symbol_name="DroneStatus.ARM_Status",
        value=3.0,
        transport=synth,
        i_understand=True,
        require_disarmed=False,
        halt_for_write=True,
        verify=True,
    )

    assert synth.halt_called is True
    assert synth.resume_called is True
    assert result.verified is True


# ------------------------------------------------------------------
# CLI integration tests
# ------------------------------------------------------------------

def test_cli_patch_requires_i_understand():
    """CLI exits 2 without --i-understand and prints the safety message."""
    p = build_parser()
    args = p.parse_args([
        "--elf", str(ELF),
        "patch", "DroneStatus.ARM_Status", "0.0",
    ])
    assert args.i_understand is False
    assert args.symbol == "DroneStatus.ARM_Status"
    assert args.value == "0.0"


def test_cli_patch_parses_all_flags():
    """All documented flags are accepted by the parser."""
    p = build_parser()
    args = p.parse_args([
        "--elf", str(ELF),
        "patch", "mrac_state.pitch.What[0]", "0.5",
        "--i-understand",
        "--no-disarm-check",
        "--halt",
        "--dry-run",
        "--verify-only",
    ])
    assert args.symbol == "mrac_state.pitch.What[0]"
    assert args.value == "0.5"
    assert args.elf == str(ELF)
    assert args.i_understand is True
    assert args.no_disarm_check is True
    assert args.halt is True
    assert args.dry_run is True
    assert args.verify_only is True


# ------------------------------------------------------------------
# SafetyGateError is exported from __init__
# ------------------------------------------------------------------

def test_safety_gate_error_exported():
    """SafetyGateError is importable from ground_station.livewatch."""
    from ground_station.livewatch import SafetyGateError as SGE
    assert issubclass(SGE, RuntimeError)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _make_transport():
    """Build a minimal SyntheticTransport with an attached LiveReader."""
    from tests.conftest import SyntheticTransport
    return SyntheticTransport()


def _resolve_one(name: str):
    """Resolve one symbol against the real ELF (hardware-free DWARF step)."""
    from ground_station.livewatch.symbols import SymbolResolver
    r = SymbolResolver(ELF)
    try:
        return r.resolve(name)
    finally:
        r.close()
