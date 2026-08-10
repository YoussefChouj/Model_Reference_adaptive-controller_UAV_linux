"""Confirm the post-flip USART3 firmware is emitting the 16 B attitude triple.

Reads UDP 14550 from the MicoAir WiFi Link for ~5 s and decodes every JustFloat
frame. After the throughput-flag flip, every FC tick should land on the wire as
3 little-endian float32 (rol, pit, yaw in radians) + the JustFloat tail
``\\x00\\x00\\x80\\x7f``. Expected cadence: ~80 Hz.

Run from repo root:  .venv\\Scripts\\python.exe scratchpad\\verify_attitude_frame.py
"""
import socket
import struct
import sys
import time

TAIL = b"\x00\x00\x80\x7f"
PORT = 14550
SECS = 5.0


def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8 * 1024 * 1024)
    sock.settimeout(0.2)
    try:
        sock.bind(("0.0.0.0", PORT))
    except OSError as exc:
        print("cannot bind UDP %d: %s" % (PORT, exc))
        print("is another capture script running?")
        return 1

    # Nudge the module so it learns our address before counting
    for _ in range(3):
        try:
            sock.sendto(b"\n", ("192.168.4.1", PORT))
        except OSError:
            pass
        time.sleep(0.1)

    buf = bytearray()
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < SECS:
        try:
            d, _ = sock.recvfrom(65535)
        except socket.timeout:
            continue
        if d:
            buf.extend(d)
    elapsed = time.perf_counter() - t0
    sock.close()

    print("captured %d B in %.1f s -> %.0f B/s"
          % (len(buf), elapsed, len(buf) / elapsed if elapsed else 0))

    if not buf:
        print("nothing arrived; on the module's wifi? FC powered?")
        return 1

    # walk JustFloat frames
    frames = []
    pos = buf.find(TAIL)
    pos = 0 if pos < 0 else pos + 4   # drop leading partial
    while True:
        i = buf.find(TAIL, pos)
        if i < 0:
            break
        payload = bytes(buf[pos:i])
        pos = i + 4
        frames.append(payload)

    print("parsed %d JustFloat frames" % len(frames))

    sizes = {}
    for f in frames:
        sizes[len(f)] = sizes.get(len(f), 0) + 1
    print("frame sizes:", dict(sorted(sizes.items())))

    att = [f for f in frames if len(f) == 12]
    ladder_sizes = {72, 124, 204, 324, 484, 684, 884, 1124}
    ladder = [f for f in frames if len(f) in ladder_sizes]
    print("attitude (12 B, 3 floats): %d" % len(att))
    print("throughput ladder sizes: %d" % len(ladder))

    if not att:
        print("\nNO 12 B ATTITUDE FRAMES -- ladder may still be running or no link.")
        return 1

    print("\nfirst 10 attitude frames (rad):")
    for f in att[:10]:
        r, p, y = struct.unpack("<fff", f)
        print("  rol=%+.3f pit=%+.3f yaw=%+.3f" % (r, p, y))

    hz = len(att) / elapsed if elapsed else 0
    print("\nattitude cadence: %.1f Hz (target 80.2 Hz)" % hz)
    if hz < 70 or hz > 90:
        print("WARN: cadence out of expected band")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())