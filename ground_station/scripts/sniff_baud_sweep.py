#!/usr/bin/env python
"""
sniff_baud_sweep.py — open COM6 at every common baud for 4 s each, dump byte counts.
The wireless debugger usually runs at 115200, 57600, or 38400. If the FC's airborne
radio is bound to the ground debugger at a mismatched baud, telemetry bytes would
just look like noise (still nonzero) at the wrong baud.
"""
import sys
import time
import serial

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM6"
BAUDS = [9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600, 1000000]

print(f"sniffing {PORT} @ {len(BAUDS)} baud rates (4 s each)")
for baud in BAUDS:
    try:
        s = serial.Serial(PORT, baud, timeout=0.05)
    except Exception as ex:
        print(f"  {baud:7d}  SKIP   {str(ex).splitlines()[0]}")
        continue
    n = 0
    first = bytearray()
    t0 = time.monotonic()
    while time.monotonic() - t0 < 4.0:
        chunk = s.read(1024)
        if chunk:
            n += len(chunk)
            if len(first) < 16:
                first.extend(chunk[: 16 - len(first)])
    s.close()
    fb = " ".join(f"{b:02X}" for b in first[:16])
    verdict = "LIVE" if n > 1000 else ("quiet" if n > 0 else "silent")
    print(f"  {baud:7d}  rx={n:7d} B  {verdict:8s}  first=[{fb}]")