"""Serial loopback test: jumper the adapter's TX<->RX, then run.

  python -m ground_station.scripts.loopback_test --port COM6

If bytes echo back, the PC + USB cable + serial adapter are healthy and the
fault (zero telemetry) is on the drone/radio side. If nothing echoes, the
adapter, cable, driver, or port is the problem.
"""
from __future__ import annotations

import argparse
import time

import serial  # type: ignore

PROBE = b"UAV-LOOPBACK-0123456789"


def main() -> None:
    ap = argparse.ArgumentParser(description="Serial TX<->RX loopback test.")
    ap.add_argument("--port", default="COM6")
    ap.add_argument("--baud", type=int, default=115200)
    args = ap.parse_args()

    print(f"Opening {args.port} @ {args.baud} ... (jumper TX<->RX on the adapter)")
    ser = serial.Serial(port=args.port, baudrate=args.baud, timeout=0.5)
    try:
        ser.reset_input_buffer()
        ser.write(PROBE)
        ser.flush()
        time.sleep(0.2)
        got = ser.read(len(PROBE) + 8)
    finally:
        ser.close()

    print(f"sent {len(PROBE)} bytes, received {len(got)}: {got!r}")
    if got == PROBE:
        print("PASS: loopback OK -> PC/cable/adapter healthy; fault is drone-side.")
    elif got:
        print("PARTIAL: some bytes returned but not an exact match -> flaky cable/baud.")
    else:
        print("FAIL: no echo -> adapter/cable/driver/port problem (not the drone).")


if __name__ == "__main__":
    main()
