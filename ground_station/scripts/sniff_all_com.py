#!/usr/bin/env python
"""
sniff_all_com.py — open every COM port, read 3 s each, print byte counts + first byte.
Finds which COM port has the wireless radio's live telemetry stream.
"""
import sys
import time
import serial

PORTS = ["COM3", "COM4", "COM5", "COM6", "COM7"]
BAUD = 115200

for p in PORTS:
    try:
        s = serial.Serial(p, BAUD, timeout=0.05)
    except Exception as ex:
        msg = str(ex).splitlines()[0]
        print(f"{p:6s}  SKIP   {msg}")
        continue
    n = 0
    first_bytes = bytearray()
    t0 = time.monotonic()
    while time.monotonic() - t0 < 3.0:
        chunk = s.read(512)
        if chunk:
            n += len(chunk)
            if len(first_bytes) < 16 and len(chunk) > 0:
                first_bytes.extend(chunk[: 16 - len(first_bytes)])
    s.close()
    fb = " ".join(f"{b:02X}" for b in first_bytes[:16])
    verdict = "LIVE" if n > 100 else ("quiet" if n > 0 else "silent")
    print(f"{p:6s}  rx={n:6d} B  {verdict:8s}  first={fb}")