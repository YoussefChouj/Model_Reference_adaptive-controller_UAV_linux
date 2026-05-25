from __future__ import annotations

import argparse
import socket
import struct
import time
from dataclasses import dataclass
from typing import List, Optional

try:
    import serial  # type: ignore
    from serial.tools import list_ports  # type: ignore
except ImportError:  # pragma: no cover
    serial = None
    list_ports = None

from ground_station.comm.serial_bridge import load_config

SYNC_0 = 0xAA
SYNC_1 = 0xBB
CMD_0 = 0xCC
CMD_1 = 0xDD


@dataclass
class FrameStats:
    bytes_read: int = 0
    aa_count: int = 0
    aabb_count: int = 0
    frame_a_ok: int = 0
    frame_b_ok: int = 0
    crc_fail: int = 0
    len_fail: int = 0
    unknown_type: int = 0
    last_arm: Optional[int] = None
    last_flymode: Optional[int] = None
    last_sbus_lost: Optional[int] = None
    first_bytes: bytes = b""


def xor_crc8(data: bytes) -> int:
    crc = 0
    for b in data:
        crc ^= b
    return crc & 0xFF


def pack_cmd_frame(cmd_id: int, index: int, value: float) -> bytes:
    payload = bytes([CMD_0, CMD_1, cmd_id & 0xFF, index & 0xFF]) + struct.pack("<f", float(value))
    crc = xor_crc8(payload[2:])
    return payload + bytes([crc])


def probe_udp_bridge(host: str, port: int, timeout_s: float = 0.5) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout_s)
    try:
        sock.sendto(b"ping", (host, port))
        data, _addr = sock.recvfrom(1024)
        return data == b"pong"
    except Exception:
        return False
    finally:
        sock.close()


def decode_stream(buf: bytearray, stats: FrameStats) -> None:
    i = 0
    while True:
        if len(buf) - i < 7:
            break
        if buf[i] != SYNC_0 or buf[i + 1] != SYNC_1:
            i += 1
            continue

        frame_type = buf[i + 2]
        len_hi = buf[i + 3]
        len_lo = buf[i + 4]
        max_num_basis = buf[i + 5]
        payload_len = (len_hi << 8) | len_lo

        if payload_len <= 0 or payload_len > 4096:
            stats.len_fail += 1
            i += 1
            continue

        expected_total = 6 + payload_len + 1
        if len(buf) - i < expected_total:
            break

        frame = bytes(buf[i : i + expected_total])
        i += expected_total

        payload = frame[6 : 6 + payload_len]
        recv_crc = frame[-1]
        calc_crc = xor_crc8(bytes([frame_type, len_hi, len_lo, max_num_basis]) + payload)
        if recv_crc != calc_crc:
            stats.crc_fail += 1
            continue

        if frame_type == 0x01:
            if payload_len != 38:
                stats.len_fail += 1
                continue
            stats.frame_a_ok += 1
            try:
                unpacked = struct.unpack("<8fBBBBBB", payload)
                stats.last_arm = int(unpacked[8])
                stats.last_flymode = int(unpacked[9])
                stats.last_sbus_lost = int(unpacked[10])
            except Exception:
                pass
        elif frame_type == 0x02:
            expected = (4 * (max_num_basis + 2) + 36) * 4 + 22
            if payload_len != expected:
                stats.len_fail += 1
                continue
            stats.frame_b_ok += 1
        else:
            stats.unknown_type += 1

    if i > 0:
        del buf[:i]


def run_serial_probe(
    port: str,
    baud: int,
    seconds: float,
    send_safe_command: bool = False,
) -> FrameStats:
    stats = FrameStats()
    if serial is None:
        raise RuntimeError("pyserial is not installed. Install with: pip install pyserial")

    ser = serial.Serial(port=port, baudrate=baud, timeout=0.1)  # type: ignore[attr-defined]
    try:
        if send_safe_command:
            # Safe test command: clear GS_KeySDKflag (CMD 0x0E, idx 0, val 0.0)
            ser.write(pack_cmd_frame(0x0E, 0, 0.0))

        end_t = time.monotonic() + float(seconds)
        buf = bytearray()
        while time.monotonic() < end_t:
            chunk = ser.read(4096)
            if not chunk:
                continue
            stats.bytes_read += len(chunk)
            stats.aa_count += chunk.count(0xAA)
            stats.aabb_count += sum(
                1 for i in range(max(0, len(chunk) - 1)) if chunk[i] == 0xAA and chunk[i + 1] == 0xBB
            )
            if len(stats.first_bytes) < 64:
                need = 64 - len(stats.first_bytes)
                stats.first_bytes += chunk[:need]
            buf.extend(chunk)
            decode_stream(buf, stats)
        decode_stream(buf, stats)
    finally:
        ser.close()

    return stats


def print_port_list() -> None:
    print("=== Serial Ports ===")
    if list_ports is None:
        print("pyserial not installed, cannot enumerate COM ports.")
        return
    ports = list(list_ports.comports())
    if not ports:
        print("No serial ports detected.")
        return
    for p in ports:
        print(f"- {p.device}: {p.description}")


def main() -> None:
    cfg = load_config()

    ap = argparse.ArgumentParser(
        description="Diagnose telemetry link between STM32 UART4 and ground station GUI."
    )
    ap.add_argument("--port", default=str(cfg.get("serial_port", "COM6")), help="Serial port (e.g. COM6)")
    ap.add_argument("--baud", type=int, default=int(cfg.get("baud_rate", 115200)), help="Baud rate")
    ap.add_argument("--seconds", type=float, default=5.0, help="Probe duration")
    ap.add_argument("--cmd-host", default=str(cfg.get("cmd_host", "127.0.0.1")), help="UDP bridge host")
    ap.add_argument("--cmd-port", type=int, default=int(cfg.get("cmd_udp_port", 1349)), help="UDP bridge port")
    ap.add_argument(
        "--send-safe-command",
        action="store_true",
        help="Send a safe command frame (CMD 0x0E idx 0 val 0.0) to verify TX path",
    )
    args = ap.parse_args()

    print_port_list()
    print("\n=== UDP Bridge Probe ===")
    udp_ok = probe_udp_bridge(args.cmd_host, int(args.cmd_port))
    print(f"cmd bridge {args.cmd_host}:{args.cmd_port}: {'UP (pong)' if udp_ok else 'DOWN (no reply)'}")

    print("\n=== Serial Telemetry Probe ===")
    print(f"Opening {args.port} @ {args.baud} for {args.seconds:.1f}s...")
    try:
        st = run_serial_probe(
            port=args.port,
            baud=int(args.baud),
            seconds=float(args.seconds),
            send_safe_command=bool(args.send_safe_command),
        )
    except PermissionError as ex:
        print(f"ERROR: {ex}")
        print("Hint: COM port is busy. Close dashboard/serial_bridge/Keil serial monitor and retry.")
        return
    except Exception as ex:
        print(f"ERROR: {ex}")
        return

    print(f"bytes_read={st.bytes_read}")
    print(f"sync_markers: aa={st.aa_count} aabb={st.aabb_count}")
    print(f"frame_a_ok={st.frame_a_ok} frame_b_ok={st.frame_b_ok}")
    print(f"crc_fail={st.crc_fail} len_fail={st.len_fail} unknown_type={st.unknown_type}")
    if st.first_bytes:
        preview = " ".join(f"{b:02X}" for b in st.first_bytes)
        print(f"first_bytes[64]: {preview}")

    if st.last_arm is not None:
        print(
            f"last_status: arm={st.last_arm} flymode={st.last_flymode} sbus_lost={st.last_sbus_lost}"
        )

    print("\n=== Interpretation ===")
    if st.bytes_read == 0:
        print("- No bytes received: likely wrong COM port, wiring issue, or firmware not running UART4 telemetry.")
    elif (st.frame_a_ok + st.frame_b_ok) == 0 and st.bytes_read > 0:
        print("- Bytes exist but no valid frames: possible baud mismatch or non-UAV traffic on this COM port.")
    else:
        print("- Telemetry frames are valid. GUI should show live values if connected to this same COM port.")

    if udp_ok:
        print("- UDP bridge is active; if GUI also opens serial directly, avoid double-opening the same COM port.")


if __name__ == "__main__":
    main()
