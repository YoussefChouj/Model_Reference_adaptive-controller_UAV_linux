"""
MAVLink-shaped PARAM_SET / PARAM_GET over the 0xCC 0xDD command protocol.

Wire format (agent-05):
  [0xCC][0xDD][CMD][LEN][payload][CRC8]

  CMD 0x21 PARAM_SET:  LEN=36, payload = name(32B, NUL-padded) + value(4B float LE)
  CMD 0x22 PARAM_GET:  LEN=32, payload = name(32B, NUL-padded)

  Reply payload: name(32B) + value(4B LE) + status(1B: 0=ok, 1=not_found)

  CRC8 is XOR over every byte before the CRC itself (indices 0 through LEN+3).

This module is standalone for portability; it can also be imported and used
with a bare serial port (no SerialBridge required).

CLI usage:
  python -m ground_station.mavlink_param set e_deadzone 0.05
  python -m ground_station.mavlink_param get e_deadzone
"""

from __future__ import annotations

import struct
import time
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ground_station.comm.serial_bridge import SerialBridge

# Protocol constants
_SYNC_0 = 0xCC
_SYNC_1 = 0xDD
CMD_PARAM_SET = 0x21
CMD_PARAM_GET = 0x22
PARAM_NAME_LEN = 32
PARAM_REPLY_STATUS_OK = 0
PARAM_REPLY_STATUS_NOT_FOUND = 1


def _xor_crc8(data: bytes) -> int:
    """XOR checksum — matches BSP/usart5.c ParseGsCommandFrames."""
    crc = 0
    for b in data:
        crc ^= b & 0xFF
    return crc & 0xFF


def _pack_name(name: str) -> bytes:
    """Encode a param name as a 32-byte NUL-padded field."""
    encoded = name.encode("utf-8")[:PARAM_NAME_LEN]
    return encoded.ljust(PARAM_NAME_LEN, b"\x00")


def _build_param_frame(cmd: int, name: str, value: Optional[float] = None) -> bytes:
    """Build a PARAM_SET or PARAM_GET frame bytes."""
    name_bytes = _pack_name(name)

    if cmd == CMD_PARAM_SET:
        payload = name_bytes + struct.pack("<f", value)
    else:
        payload = name_bytes

    frame = bytes([_SYNC_0, _SYNC_1, cmd, len(payload)]) + payload
    crc = _xor_crc8(frame)
    return frame + bytes([crc])


def _unpack_param_reply(frame: bytes) -> tuple[str, float, int]:
    """Parse a PARAM_SET / PARAM_GET reply frame.

    Returns (name, value, status).
    status: 0=ok, 1=not_found.

    Raises ValueError if the frame does not look like a param reply.
    """
    if len(frame) < 5 + PARAM_NAME_LEN:
        raise ValueError(f"Reply too short ({len(frame)} bytes)")

    sync0, sync1, cmd, reply_len = frame[0], frame[1], frame[2], frame[3]

    if sync0 != _SYNC_0 or sync1 != _SYNC_1:
        raise ValueError(f"Not a 0xCC 0xDD frame: {frame[:4].hex()}")
    if cmd not in (CMD_PARAM_SET, CMD_PARAM_GET):
        raise ValueError(f"Not a param reply CMD: 0x{cmd:02X}")

    name_bytes = frame[4 : 4 + PARAM_NAME_LEN]
    name = name_bytes.rstrip(b"\x00").decode("utf-8", errors="replace")

    value_bytes = frame[4 + PARAM_NAME_LEN : 4 + PARAM_NAME_LEN + 4]
    value, = struct.unpack("<f", value_bytes)

    status = frame[4 + PARAM_NAME_LEN + 4]
    return name, value, status


def set_param(
    ser,  # Serial-like with a write() method
    name: str,
    value: float,
    timeout_s: float = 1.0,
) -> tuple[bool, str]:
    """Send a PARAM_SET frame and wait for the reply.

    Returns (success, message).
    success=True means the firmware returned PARAM_STATUS_OK.
    """
    frame = _build_param_frame(CMD_PARAM_SET, name, value)
    ser.write(frame)

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        n = ser.in_waiting
        if n == 0:
            time.sleep(0.01)
            continue

        raw = ser.read(n)
        # Scan for the 0xCC 0xDD sync in the received bytes.
        idx = raw.find(bytes([_SYNC_0, _SYNC_1]))
        if idx < 0:
            continue

        candidate = raw[idx:]
        try:
            reply_name, reply_value, status = _unpack_param_reply(candidate)
        except ValueError:
            continue

        if reply_name != name:
            continue

        if status == PARAM_REPLY_STATUS_OK:
            return True, f"set {name}={value}"
        else:
            return False, f"{name} not in firmware param registry"

    return False, "timeout waiting for PARAM_SET reply"


def get_param(
    ser,  # Serial-like with a write() and in_waiting methods
    name: str,
    timeout_s: float = 1.0,
) -> tuple[bool, float]:
    """Send a PARAM_GET frame and wait for the reply.

    Returns (success, value).
    success=False means the firmware returned PARAM_STATUS_NOT_FOUND.
    """
    frame = _build_param_frame(CMD_PARAM_GET, name)
    ser.write(frame)

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        n = ser.in_waiting
        if n == 0:
            time.sleep(0.01)
            continue

        raw = ser.read(n)
        idx = raw.find(bytes([_SYNC_0, _SYNC_1]))
        if idx < 0:
            continue

        candidate = raw[idx:]
        try:
            reply_name, value, status = _unpack_param_reply(candidate)
        except ValueError:
            continue

        if reply_name != name:
            continue

        if status == PARAM_REPLY_STATUS_OK:
            return True, value
        else:
            return False, 0.0

    return False, 0.0


# ----------------------------------------------------------------------
# SerialBridge integration
# ----------------------------------------------------------------------


def _stub_serial() -> object:
    """Return a minimal mock serial with the interface set_param/get_param need."""

    class _Stub:
        def __init__(self) -> None:
            self._buf: list[int] = []
            self.in_waiting: int = 0

        def write(self, data: bytes) -> None:
            self._buf.extend(data)

        def read(self, n: int = -1) -> bytes:
            if n < 0:
                out = bytes(self._buf)
                self._buf.clear()
                self.in_waiting = 0
                return out
            out = bytes(self._buf[:n])
            self._buf = self._buf[n:]
            self.in_waiting = len(self._buf)
            return out

        def inject_reply(self, frame: bytes) -> None:
            self._buf.extend(frame)
            self.in_waiting = len(self._buf)

    return _Stub()


def add_param_methods(bridge: "SerialBridge") -> None:
    """Monkey-patch set_param and get_param onto a SerialBridge instance.

    Called once at import time; idempotent.
    """
    if hasattr(bridge, "_param_methods_added"):
        return
    bridge._param_methods_added = True  # type: ignore[attr]

    # Use the same serial port the bridge manages.
    _ser = bridge._serial  # type: ignore[attr]

    def sb_set_param(name: str, value: float, timeout_s: float = 1.0) -> tuple[bool, str]:
        if _ser is None:
            return False, "serial not open"
        return set_param(_ser, name, value, timeout_s)

    def sb_get_param(name: str, timeout_s: float = 1.0) -> tuple[bool, float]:
        if _ser is None:
            return False, 0.0
        return get_param(_ser, name, timeout_s)

    bridge.set_param = sb_set_param  # type: ignore[attr]
    bridge.get_param = sb_get_param  # type: ignore[attr]


# ----------------------------------------------------------------------
# CLI entry point
# ----------------------------------------------------------------------


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="MAVLink-shaped param read/write over USART3")
    parser.add_argument(
        "--port",
        default=None,
        help="Serial port (e.g. COM6). If omitted, tries to auto-resolve via SerialBridge.",
    )
    sub = parser.add_subparsers(dest="cmd")

    set_p = sub.add_parser("set", help="set <name> <value>")
    set_p.add_argument("name")
    set_p.add_argument("value", type=float)

    get_p = sub.add_parser("get", help="get <name>")
    get_p.add_argument("name")

    args = parser.parse_args()

    # Import here to avoid circular dependency.
    from ground_station.comm.serial_bridge import SerialBridge

    if args.port:
        bridge = SerialBridge(serial_port=args.port)
    else:
        bridge = SerialBridge()

    # Block until the serial port is open and the bridge has started.
    bridge.start()
    import time
    time.sleep(0.5)

    try:
        if args.cmd == "set":
            ok, msg = bridge.set_param(args.name, float(args.value))
            print(msg)
            sys.exit(0 if ok else 1)
        elif args.cmd == "get":
            ok, value = bridge.get_param(args.name)
            if ok:
                print(value)
                sys.exit(0)
            else:
                print("not found", file=sys.stderr)
                sys.exit(1)
        else:
            parser.print_help()
            sys.exit(1)
    finally:
        bridge.stop()
