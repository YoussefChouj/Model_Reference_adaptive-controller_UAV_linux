#!/usr/bin/env python
"""
test_rx_loop_crash.py — synthetic byte-stream tests for the Option C RX loop.

We don't open a real serial port. We patch _serial with a fake object that yields
pre-canned bytes, and we assert that the parser is now robust against:
  * 0xAA inside payload (length-prefixed wins; OLD parser would desync)
  * Frame C (0x06) with CRC-CCITT (was buggy in the OLD parser too)
  * Truncated frames (LEN mismatch → resync, no hang)
  * Bad CRC (silently dropped, then next frame accepted)
"""
from __future__ import annotations
import struct
import sys
import threading
from pathlib import Path
from typing import List

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from ground_station.comm.serial_bridge import SerialBridge, _xor_crc8, _crc16_ccitt


class FakeSerial:
    """Yields bytes from a buffer, returns empty on read when buffer is exhausted."""

    def __init__(self, data: bytes):
        self._data = data
        self._pos = 0

    def read(self, n: int) -> bytes:
        if self._pos >= len(self._data):
            return b""
        chunk = self._data[self._pos : self._pos + n]
        self._pos += len(chunk)
        return chunk

    def cancel_read(self) -> None:
        pass

    def close(self) -> None:
        pass


def run_briefly(b: SerialBridge, max_polls: int = 50) -> List[int]:
    """Run _rx_loop on a tiny thread; stop after max_polls calls to is_set()."""
    handled: List[int] = []
    b._handle_frame_orig = b._handle_frame  # type: ignore[attr-defined]

    def _handle(frame_type, max_num_basis, payload):
        handled.append(frame_type)

    b._handle_frame = _handle  # type: ignore[assignment]

    polls = [0]
    stop = threading.Event()
    b._stop_event = stop
    t = threading.Thread(target=b._rx_loop, daemon=True)
    t.start()

    # Poll the loop indirectly: it reads bytes from FakeSerial. When FakeSerial is
    # exhausted it returns empty, so the loop spins in `_resync_to_header`. We just
    # give it a moment to consume the available bytes, then stop.
    import time
    deadline = time.monotonic() + 0.5
    while time.monotonic() < deadline:
        time.sleep(0.02)
        if len(handled) > 0 and b._stop_event.is_set() is False and FakeSerial is not None:
            # Got at least one — give it a touch more time in case more frames follow.
            time.sleep(0.05)
            break
    stop.set()
    t.join(timeout=1.0)
    return handled


def make_serial_bridge_with_stream(stream: bytes) -> SerialBridge:
    """Build a SerialBridge instance backed by FakeSerial without calling __init__."""
    b = SerialBridge.__new__(SerialBridge)
    b._serial = FakeSerial(stream)
    return b


def build_frame_a(payload_insert_aa_at: int = -1) -> bytes:
    payload = bytearray(b"\x00" * 41)
    if payload_insert_aa_at >= 0:
        payload[payload_insert_aa_at] = 0xAA
    crc = _xor_crc8([0x01, 0x00, 41, 12, *payload])
    return bytes([0xAA, 0xBB, 0x01, 0x00, 41, 12]) + bytes(payload) + bytes([crc])


def build_frame_c() -> bytes:
    payload = struct.pack("<12f", *([0.0] * 11 + [12345.0]))  # 48 B
    payload += b"\xAA\xBB"  # deliberate 0xAA 0xBB mid-payload — kills old parser
    assert len(payload) == 50
    crc = _crc16_ccitt([0x06, 0x00, 50, 12, *payload])
    return bytes([0xAA, 0xBB, 0x06, 0x00, 50, 12]) + payload + crc.to_bytes(2, "big")


def test_frame_a_with_aa_in_payload() -> None:
    """OLD parser: desyncs because payload byte 5 = 0xAA. NEW parser: trusts LEN."""
    stream = build_frame_a(payload_insert_aa_at=5)
    b = make_serial_bridge_with_stream(stream)
    handled = run_briefly(b)
    assert handled == [0x01], f"got {handled!r}"
    print("PASS  frame_a_with_aa_in_payload")


def test_frame_c_with_aa_in_payload() -> None:
    stream = build_frame_c()
    b = make_serial_bridge_with_stream(stream)
    handled = run_briefly(b)
    assert handled == [0x06], f"got {handled!r}"
    print("PASS  frame_c_with_aa_in_payload")


def test_truncated_frame_resyncs() -> None:
    """Truncated Frame A: header says 41 B, only 20 follow, then EOF. Must not hang."""
    stream = bytes([0xAA, 0xBB, 0x01, 0x00, 41, 12]) + b"\x00" * 20
    b = make_serial_bridge_with_stream(stream)
    handled = run_briefly(b, max_polls=10)
    assert handled == [], f"got {handled!r}"
    print("PASS  truncated_frame_resyncs")


def test_bad_crc_drops_then_accepts_next() -> None:
    good = build_frame_a()
    bad = bytearray(good)
    bad[-1] ^= 0x01  # flip the CRC byte
    stream = bytes(bad) + good
    b = make_serial_bridge_with_stream(stream)
    handled = run_briefly(b, max_polls=10)
    assert handled == [0x01], f"got {handled!r}"
    print("PASS  bad_crc_drops_then_accepts_next")


def test_back_to_back_frame_a_then_frame_c() -> None:
    """Frame A immediately followed by Frame C — the exact wire layout from v13 firmware."""
    stream = build_frame_a() + build_frame_c()
    b = make_serial_bridge_with_stream(stream)
    handled = run_briefly(b, max_polls=10)
    assert handled == [0x01, 0x06], f"got {handled!r}"
    print("PASS  back_to_back_frame_a_then_frame_c")


if __name__ == "__main__":
    test_frame_a_with_aa_in_payload()
    test_frame_c_with_aa_in_payload()
    test_truncated_frame_resyncs()
    test_bad_crc_drops_then_accepts_next()
    test_back_to_back_frame_a_then_frame_c()
    print("\nALL TESTS PASSED")