#!/usr/bin/env python
"""
sniff_raw.py — Listen on COM6 for ANY bytes at a wide range of bauds.
If the wireless debugger is set to a non-default baud, we should see at
least noise (random-looking bytes) at the wrong baud and proper frames
at the right one. 12 s total runtime.
"""
import sys, time, serial

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM6"
BAUDS = [9600, 19200, 38400, 57600, 115200, 230400, 460800]

for baud in BAUDS:
    try:
        s = serial.Serial(PORT, baud, timeout=0.1)
    except Exception as ex:
        print(f"  {baud:7d}  SKIP   {str(ex).splitlines()[0]}")
        continue
    s.reset_input_buffer()
    n = 0
    aa_bb = 0
    first = bytearray()
    t0 = time.monotonic()
    while time.monotonic() - t0 < 3.0:
        chunk = s.read(512)
        if chunk:
            n += len(chunk)
            if len(first) < 64:
                first.extend(chunk[: 64 - len(first)])
            # count 0xAA 0xBB occurrences as a quick sync check
            for i in range(len(chunk) - 1):
                if chunk[i] == 0xAA and chunk[i + 1] == 0xBB:
                    aa_bb += 1
    s.close()
    fb = " ".join(f"{b:02X}" for b in first[:32])
    if n > 1000:
        verdict = "** LIVE **"
    elif n > 0:
        verdict = "noisy"
    else:
        verdict = "silent"
    print(f"  {baud:7d}  rx={n:7d} B  0xAA0xBB={aa_bb:4d}  {verdict:12s}  first=[{fb}]")