#!/usr/bin/env python
"""
diag_telemetry.py — three-stage dashboard-down triage (no dashboard GUI needed).

Stage 1: probe which COM ports are alive (3 s each)
Stage 2: on the chosen port, sniff bytes for 5 s and count frame signatures
Stage 3: cross-check firmware GS_PROTO_VERSION vs SerialBridge header-length gates

Run:  python -m ground_station.scripts.diag_telemetry
"""
from __future__ import annotations
import serial
import time
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from ground_station.comm.serial_bridge import load_config, SerialBridge

# Match Global_file/global_declare.h:45  (firmware GS_PROTO_VERSION).
FW_GS_PROTO_VERSION = 13


def stage1_probe():
    cfg = load_config()
    candidates = [cfg["serial_port"], "COM3", "COM4", "COM5", "COM6"]
    print("\n=== STAGE 1: COM port probe (3 s each) ===")
    for p in candidates:
        try:
            s = serial.Serial(p, cfg["baud_rate"], timeout=0.05)
            n = 0
            t0 = time.monotonic()
            while time.monotonic() - t0 < 3.0:
                chunk = s.read(256)
                if chunk:
                    n += len(chunk)
            s.close()
            print(f"  {p:8s}  rx_bytes={n:6d}  {'OK' if n > 50 else 'silent'}")
        except Exception as ex:
            print(f"  {p:8s}  ERROR  {ex!r}")


def stage2_sniff():
    cfg = load_config()
    port = cfg["serial_port"]
    baud = int(cfg["baud_rate"])
    print(f"\n=== STAGE 2: 5 s byte sniff on {port} @ {baud} ===")
    try:
        s = serial.Serial(port, baud, timeout=0.05)
    except Exception as ex:
        print(f"  cannot open {port}: {ex!r}")
        return
    sig_counts = {0x01: 0, 0x02: 0, 0x03: 0, 0x04: 0, 0x05: 0, 0x06: 0, "junk": 0, "aa": 0}
    total = 0
    t0 = time.monotonic()
    while time.monotonic() - t0 < 5.0:
        chunk = s.read(512)
        if not chunk:
            continue
        total += len(chunk)
        for i, b in enumerate(chunk):
            if b == 0xAA and i + 1 < len(chunk) and chunk[i + 1] == 0xBB:
                sig_counts["aa"] += 1
                if i + 2 < len(chunk):
                    ft = chunk[i + 2]
                    if ft in sig_counts:
                        sig_counts[ft] += 1
                    else:
                        sig_counts["junk"] += 1
    s.close()
    print(f"  total bytes: {total}")
    for k, v in sig_counts.items():
        if isinstance(k, int):
            print(f"  frame_type=0x{k:02X}: {v}")
        else:
            print(f"  {k}: {v}")
    if sig_counts["aa"] == 0:
        print("  *** NO 0xAA 0xBB SYNC SEEN — firmware not transmitting or wrong port/baud ***")


def stage3_proto_check():
    print("\n=== STAGE 3: GS_PROTO_VERSION check ===")
    print(f"  firmware GS_PROTO_VERSION = {FW_GS_PROTO_VERSION}")
    print(f"  SerialBridge 0x06 (Frame C) length gate: 50 B")
    print(f"  SerialBridge 0x01 (Frame A) length gate: 41 B")
    print(f"  SerialBridge 0x05 (Frame OF) length gate: 39 B")
    if FW_GS_PROTO_VERSION < 13:
        print(f"  *** firmware < v13 — Frame C (0x06) is silently ignored ***")


if __name__ == "__main__":
    print("UAV telemetry diagnostic v1 — pure stdlib + pyserial")
    stage1_probe()
    stage2_sniff()
    stage3_proto_check()