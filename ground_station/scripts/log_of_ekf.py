"""
Headless high-rate logger for the 0x05 OF/EKF frame -> wide CSV.

Why this exists: the dashboard can select the 0x05 frame and record, but it merges
telemetry down to 20 Hz and needs GUI clicks. This streams every frame the link
delivers and runs unattended, which is what the EKF-vs-OF-bias comparison needs.

Sends ONLY CMD 0x0F idx 12 (telemetry frame selection) and restores it on exit.
It never touches arm state, motor test, or any control path.

Link budget (measured, not assumed): UART5 is 115200 8N1. The EKF-telemetry variant
of frame 0x05 is 73 B payload = 80 B on the wire = 6.9 ms, so it CANNOT sustain
200 Hz -- Send_Task busy-waits on the DMA and settles near 145-150 Hz. Frames are
not dropped by that mechanism (the task blocks instead), so a counter gap here means
a genuine RX/serial loss. Both are reported.

Usage:
    python -m ground_station.scripts.log_of_ekf --secs 60 --csv out.csv
"""
from __future__ import annotations

import argparse
import csv
import struct
import sys
import time
from pathlib import Path

try:
    import serial  # type: ignore
except ImportError:  # pragma: no cover
    print("pyserial not installed", file=sys.stderr)
    raise

SYNC_0, SYNC_1 = 0xAA, 0xBB
CMD_0, CMD_1 = 0xCC, 0xDD
FRAME_OF = 0x05

# Field layout of payload 0x05. Mirrors serial_bridge._decode_of_frame so the two
# cannot drift apart silently; see docs/tracking_baseline_and_drift.md.
HEAD_FIELDS = [
    "sample_counter", "of2_dx_fix", "of2_dy_fix", "of2_dx", "of2_dy",
    "acc_x_mg", "acc_y_mg", "lin_acc_x_mg", "lin_acc_y_mg",
    "yaw_c", "pit_c", "rol_c", "bias_x_c", "bias_y_c", "alt_cm",
]
V14_FIELDS = ["acc_bias_x_mg", "acc_bias_y_mg", "acc_bias_z_mg",
              "gyro_bias_x_1e4radps", "gyro_bias_y_1e4radps", "gyro_bias_z_1e4radps",
              "cal_health"]
EKF_FIELDS = ["ekf_vx_mmps", "ekf_vy_mmps", "ekf_vz_mmps",
              "ekf_p0_1e3", "ekf_p1_1e3", "ekf_p2_1e3", "ekf_nis_1e3",
              "ekf_k0_1e3", "ekf_k1_1e3", "ekf_k2_1e3"]
COLUMNS = (["t_host_s"] + HEAD_FIELDS + ["earth_x", "earth_y", "of_quality"]
           + V14_FIELDS + EKF_FIELDS)


def xor_crc8(data) -> int:
    crc = 0
    for b in data:
        crc ^= b
    return crc & 0xFF


def build_cmd(cmd_id: int, index: int, value: float) -> bytes:
    body = bytes([CMD_0, CMD_1, cmd_id & 0xFF, index & 0xFF]) + struct.pack("<f", float(value))
    return body + bytes([xor_crc8(body[2:])])


def decode_of(payload: bytes) -> dict | None:
    if len(payload) not in (39, 53, 73):
        return None
    vals = struct.unpack_from("<H13hH", payload, 0)
    row = dict(zip(HEAD_FIELDS, vals))
    row["earth_x"], row["earth_y"] = struct.unpack_from("<2f", payload, 30)
    row["of_quality"] = payload[38]
    if len(payload) >= 53:
        row.update(zip(V14_FIELDS, struct.unpack_from("<6hH", payload, 39)))
    if len(payload) >= 73:
        row.update(zip(EKF_FIELDS, struct.unpack_from("<10h", payload, 53)))
    return row


def read_exact(ser, n: int) -> bytes | None:
    buf = b""
    while len(buf) < n:
        chunk = ser.read(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", default=None, help="COM port (default: config serial_port / AUTO)")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--secs", type=float, default=60.0)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--keep-frame-on", action="store_true",
                    help="do not restore A/B telemetry on exit")
    args = ap.parse_args()

    port = args.port
    if port is None:
        from ground_station.comm.serial_bridge import load_config, resolve_serial_port
        cfg = load_config()
        port = cfg["serial_port"]
        if str(port).strip().upper() == "AUTO":
            port = resolve_serial_port()
    print(f"[log_of_ekf] port={port} baud={args.baud} secs={args.secs}")

    out = Path(args.csv)
    out.parent.mkdir(parents=True, exist_ok=True)

    ser = serial.Serial(port, args.baud, timeout=0.2)
    n_of = n_other = n_crc = 0
    gaps = 0
    last_counter = None
    t0 = time.monotonic()
    try:
        ser.reset_input_buffer()
        ser.write(build_cmd(0x0F, 12, 1.0))   # of_frame_on = 1
        ser.flush()
        print("[log_of_ekf] of_frame_on=1 sent; capturing...")

        with out.open("w", newline="", encoding="utf-8") as fp:
            w = csv.DictWriter(fp, fieldnames=COLUMNS, extrasaction="ignore")
            w.writeheader()
            sync = False
            while time.monotonic() - t0 < args.secs:
                b = ser.read(1)
                if not b:
                    continue
                byte = b[0]
                if not sync:
                    sync = byte == SYNC_0
                    continue
                if byte != SYNC_1:
                    sync = byte == SYNC_0
                    continue
                sync = False
                header = read_exact(ser, 4)
                if header is None:
                    continue
                ftype, len_hi, len_lo, basis = header
                length = (len_hi << 8) | len_lo
                if length > 400:
                    continue
                payload = read_exact(ser, length)
                if payload is None:
                    continue
                crc_b = ser.read(1)
                if not crc_b:
                    continue
                if xor_crc8([ftype, len_hi, len_lo, basis, *payload]) != crc_b[0]:
                    n_crc += 1
                    continue
                if ftype != FRAME_OF:
                    n_other += 1
                    continue
                row = decode_of(payload)
                if row is None:
                    continue
                c = row["sample_counter"]
                if last_counter is not None:
                    step = (c - last_counter) & 0xFFFF
                    if step != 1:
                        gaps += 1
                last_counter = c
                row["t_host_s"] = round(time.monotonic() - t0, 6)
                w.writerow(row)
                n_of += 1
    except KeyboardInterrupt:
        print("\n[log_of_ekf] interrupted")
    finally:
        if not args.keep_frame_on:
            try:
                ser.write(build_cmd(0x0F, 12, 0.0))  # restore A/B
                ser.flush()
                time.sleep(0.1)
                print("[log_of_ekf] of_frame_on=0 restored")
            except Exception as exc:
                print(f"[log_of_ekf] WARNING could not restore A/B: {exc}")
        ser.close()

    dur = time.monotonic() - t0
    rate = n_of / dur if dur > 0 else 0.0
    print(f"[log_of_ekf] wrote {out}")
    print(f"  frames_0x05={n_of}  other={n_other}  crc_err={n_crc}  counter_gaps={gaps}")
    print(f"  duration={dur:.2f}s  effective_rate={rate:.1f} Hz")
    if n_of == 0:
        print("  NOTE: no 0x05 frames. Is the comm module (not the SWD probe) on UART5?")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
