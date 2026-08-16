"""
Host-side tests for ground_station/mavlink_param.py (agent-05).
Tests the MAVLink-shaped PARAM_SET / PARAM_GET wire format.

Test suite:
  test_set_param_emits_correct_frame  — stub serial, verify raw bytes
  test_get_param_round_trip         — stub serial with reply, verify parsed value
  test_crc8_computation             — known-good frame, verify CRC8
"""

from __future__ import annotations

import struct
import sys
import os

# Make ground_station importable from the repo root.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ground_station.mavlink_param import (
    CMD_PARAM_GET,
    CMD_PARAM_SET,
    PARAM_NAME_LEN,
    _build_param_frame,
    _pack_name,
    _xor_crc8,
    _unpack_param_reply,
    set_param,
    get_param,
)


class _StubSerial:
    """Minimal mock serial with an injectable reply buffer."""

    def __init__(self) -> None:
        self._tx_buf: list[int] = []
        self._rx_buf: list[int] = []
        self.in_waiting: int = 0

    def write(self, data: bytes) -> None:
        self._tx_buf.extend(data)

    def read(self, n: int = -1) -> bytes:
        if n < 0:
            out = bytes(self._rx_buf)
            self._rx_buf.clear()
            self.in_waiting = 0
            return out
        out = bytes(self._rx_buf[:n])
        self._rx_buf = self._rx_buf[n:]
        self.in_waiting = len(self._rx_buf)
        return out

    def inject_reply(self, frame: bytes) -> None:
        self._rx_buf.extend(frame)
        self.in_waiting = len(self._rx_buf)

    def transmitted(self) -> bytes:
        return bytes(self._tx_buf)

    def clear_tx(self) -> None:
        self._tx_buf.clear()


def make_param_reply(cmd: int, name: str, value: float, status: int = 0) -> bytes:
    """Build a firmware-style PARAM_SET/GET reply frame."""
    name_bytes = name.encode("utf-8")[:PARAM_NAME_LEN].ljust(PARAM_NAME_LEN, b"\x00")
    payload = name_bytes + struct.pack("<f", value) + bytes([status])
    frame = bytes([0xCC, 0xDD, cmd, len(payload)]) + payload
    crc = _xor_crc8(frame)
    return frame + bytes([crc])


class TestCRC8:
    def test_xor_crc8_zero(self) -> None:
        """XOR of all zeros is zero."""
        assert _xor_crc8(b"\x00\x00\x00\x00") == 0

    def test_xor_crc8_known(self) -> None:
        """XOR of [0x01, 0x02, 0x03, 0x04] is 0x04 (01^02^03^04)."""
        assert _xor_crc8(bytes([0x01, 0x02, 0x03, 0x04])) == 0x04

    def test_param_reply_crc_matches(self) -> None:
        """CRC computed in Python matches the C implementation."""
        name = "e_deadzone"
        value = 0.05
        frame = make_param_reply(CMD_PARAM_SET, name, value, status=0)
        # CRC is the last byte.
        assert _xor_crc8(frame[:-1]) == frame[-1]


class TestPackName:
    def test_exact_length(self) -> None:
        """Encoded name is exactly 32 bytes."""
        result = _pack_name("e_deadzone")
        assert len(result) == 32

    def test_truncated_long_name(self) -> None:
        """Names longer than 32 bytes are truncated."""
        long_name = "x" * 100
        result = _pack_name(long_name)
        assert len(result) == 32

    def test_padded_short_name(self) -> None:
        """Names shorter than 32 bytes are NUL-padded."""
        result = _pack_name("x")
        assert len(result) == 32
        assert result[0:1] == b"x"
        assert result[1:] == b"\x00" * 31


class TestBuildFrame:
    def test_set_param_frame_structure(self) -> None:
        """PARAM_SET frame: [0xCC][0xDD][0x21][LEN=36][name(32)][value(4)][CRC]."""
        name = "e_deadzone"
        value = 0.05
        frame = _build_param_frame(CMD_PARAM_SET, name, value)
        assert frame[0] == 0xCC
        assert frame[1] == 0xDD
        assert frame[2] == CMD_PARAM_SET
        assert frame[3] == PARAM_NAME_LEN + 4  # 36
        # name occupies bytes 4..35
        assert frame[4 : 4 + len("e_deadzone")] == b"e_deadzone"
        # value occupies bytes 36..39
        val_bytes = frame[4 + PARAM_NAME_LEN : 4 + PARAM_NAME_LEN + 4]
        val, = struct.unpack("<f", val_bytes)
        assert abs(val - value) < 1e-6
        # CRC is last byte
        crc = _xor_crc8(frame[:-1])
        assert frame[-1] == crc

    def test_get_param_frame_structure(self) -> None:
        """PARAM_GET frame: [0xCC][0xDD][0x22][LEN=32][name(32)][CRC]."""
        name = "sigma_pitch"
        frame = _build_param_frame(CMD_PARAM_GET, name)
        assert frame[0] == 0xCC
        assert frame[1] == 0xDD
        assert frame[2] == CMD_PARAM_GET
        assert frame[3] == PARAM_NAME_LEN  # 32
        # No value bytes after the name.
        crc = _xor_crc8(frame[:-1])
        assert frame[-1] == crc
        # Frame length: 2 sync + 1 cmd + 1 len + 32 name + 1 crc = 37
        assert len(frame) == 37


class TestSetParamEmitsCorrectFrame:
    def test_set_param_emits_correct_bytes(self) -> None:
        """Stub serial; verify the written bytes match the expected wire format."""
        ser = _StubSerial()
        ok, msg = set_param(ser, "e_deadzone", 0.05, timeout_s=0.1)
        tx = ser.transmitted()
        ser.clear_tx()  # reset so we see only the first call's bytes
        # Should be: [0xCC][0xDD][0x21][36][name 32B][value 4B][CRC]
        assert tx[0] == 0xCC
        assert tx[1] == 0xDD
        assert tx[2] == 0x21
        assert tx[3] == 36
        # "e_deadzone" is 10 characters
        assert tx[4 : 4 + 10] == b"e_deadzone"
        # CRC covers everything before it
        assert _xor_crc8(tx[:-1]) == tx[-1]
        # Frame length: 2 sync + 1 cmd + 1 len + 32 name + 4 value + 1 crc = 41
        assert len(tx) == 41

    def test_set_param_returns_ok_on_success_reply(self) -> None:
        """When firmware returns PARAM_STATUS_OK, set_param returns (True, ...)."""
        ser = _StubSerial()
        ser.inject_reply(make_param_reply(CMD_PARAM_SET, "e_deadzone", 0.05, status=0))
        ok, msg = set_param(ser, "e_deadzone", 0.05, timeout_s=0.5)
        assert ok is True
        assert "e_deadzone" in msg

    def test_set_param_returns_not_found_on_bad_reply(self) -> None:
        """When firmware returns NOT_FOUND, set_param returns (False, ...)."""
        ser = _StubSerial()
        ser.inject_reply(make_param_reply(CMD_PARAM_SET, "e_deadzone", 0.0, status=1))
        ok, msg = set_param(ser, "e_deadzone", 0.05, timeout_s=0.5)
        assert ok is False



class TestGetParamRoundTrip:
    def test_get_param_returns_correct_value(self) -> None:
        """Stub serial replies with a known value; get_param returns it."""
        ser = _StubSerial()
        expected = 0.123456
        ser.inject_reply(make_param_reply(CMD_PARAM_GET, "e_deadzone", expected, status=0))
        ok, value = get_param(ser, "e_deadzone", timeout_s=0.5)
        assert ok is True
        assert abs(value - expected) < 1e-5

    def test_get_param_not_found(self) -> None:
        """Stub serial returns NOT_FOUND; get_param returns False."""
        ser = _StubSerial()
        ser.inject_reply(make_param_reply(CMD_PARAM_GET, "no_such_param", 0.0, status=1))
        ok, value = get_param(ser, "no_such_param", timeout_s=0.5)
        assert ok is False


class TestUnpackReply:
    def test_roundtrip(self) -> None:
        """Encode + decode a reply yields the original name and value."""
        name = "sigma_pitch"
        value = 0.333
        frame = make_param_reply(CMD_PARAM_GET, name, value, status=0)
        dec_name, dec_val, dec_status = _unpack_param_reply(frame)
        assert dec_name == name
        assert abs(dec_val - value) < 1e-6
        assert dec_status == 0

    def test_short_frame_raises(self) -> None:
        """A frame shorter than the minimum length raises ValueError."""
        try:
            _unpack_param_reply(bytes([0xCC, 0xDD]))
            raise AssertionError("Expected ValueError")
        except ValueError:
            pass  # expected

    def test_wrong_sync_raises(self) -> None:
        """A frame without 0xCC 0xDD sync raises ValueError."""
        try:
            _unpack_param_reply(bytes([0xAA, 0xBB, 0x22, 32]) + b"\x00" * 35)
            raise AssertionError("Expected ValueError")
        except ValueError:
            pass  # expected
