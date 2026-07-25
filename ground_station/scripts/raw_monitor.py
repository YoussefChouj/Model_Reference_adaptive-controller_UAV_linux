"""Raw serial text monitor — prints everything on the port as text so debug
messages (HARDFAULT / STACKOVF / PRE-SCHED / SEND-RAN) are visible. Binary
telemetry frames show as '.' dots.

  python -m ground_station.scripts.raw_monitor --port COM6 --seconds 20

Start it, THEN reset/power-cycle the drone so the whole boot is captured.
"""
from __future__ import annotations

import argparse
import time

import serial  # type: ignore


def main() -> None:
    ap = argparse.ArgumentParser(description="Raw serial text monitor.")
    ap.add_argument("--port", default="COM6")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--seconds", type=float, default=20.0)
    args = ap.parse_args()

    print(f"Monitoring {args.port} @ {args.baud} for {args.seconds:.0f}s — reset the drone NOW...")
    ser = serial.Serial(port=args.port, baudrate=args.baud, timeout=0.2)
    buf = bytearray()
    try:
        end = time.monotonic() + args.seconds
        while time.monotonic() < end:
            chunk = ser.read(4096)
            if chunk:
                buf.extend(chunk)
    finally:
        ser.close()

    text = "".join(
        chr(b) if (32 <= b < 127 or b in (10, 13)) else "." for b in buf
    )
    print("---- stream ----")
    print(text)
    print("---- end ----")
    print(f"[{len(buf)} bytes total]")
    for marker in ("HARDFAULT", "STACKOVF", "PRE-SCHED", "SEND-RAN"):
        if marker in text:
            # print the line(s) containing the marker
            for line in text.splitlines():
                if marker in line:
                    print(f"  FOUND: {line.strip()}")


if __name__ == "__main__":
    main()
