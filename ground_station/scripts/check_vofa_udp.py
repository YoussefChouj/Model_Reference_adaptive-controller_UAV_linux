from __future__ import annotations

import argparse
import socket
import time
from typing import List


def count_packets(port: int, seconds: float, host: str) -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind((host, int(port)))
        sock.settimeout(0.2)
        cnt = 0
        end_t = time.time() + float(seconds)
        while time.time() < end_t:
            try:
                sock.recvfrom(65535)
                cnt += 1
            except Exception:
                pass
        return cnt
    finally:
        sock.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="Count UDP packets on VOFA ports.")
    ap.add_argument("--host", default="127.0.0.1", help="Bind host")
    ap.add_argument("--seconds", type=float, default=5.0, help="Capture duration")
    ap.add_argument(
        "--ports",
        nargs="+",
        type=int,
        default=[1347, 1348],
        help="UDP ports to test",
    )
    args = ap.parse_args()

    for port in args.ports:
        try:
            count = count_packets(int(port), float(args.seconds), str(args.host))
            print(f"port{port} packets={count}")
        except OSError as ex:
            print(f"port{port} error={ex}")


if __name__ == "__main__":
    main()
