"""Send a 0xCC 0xDD command frame over the MicoAir WiFi Link and verify the FC
parsed it.

How it works:
1. Open UDP socket to 192.168.4.1:14550 -- the module's downlink to FC USART3.
2. Read `UA3RxFrameCnt` from livewatch BEFORE -- it tells us how many IDLEs
   the FC has seen so far.
3. Send a 0xCC 0xDD frame: CMD 0x10 idx 0 value 0.0 (XOR-CRC8 = 0x10).
   CMD 0x10 is "reset world-frame optical flow origin" -- it zeros earth_x/y
   and the loc-PID feedback. We can read locxPID.FB / locyPID.FB from livewatch
   to confirm the command executed. CRITICAL: don't issue this on a flying
   drone -- it would jump position setpoints to zero in flight.
4. Wait ~1 s for the module to relay and the FC to process.
5. Read UA3RxFrameCnt again. If it went up by >=1, the radio's downlink reached
   the FC's USART3 DMA.
6. Read Ctrler.locxPID.FB / locyPID.FB. If they sit near 0, the command
   executed. NOTE: if the drone is moving, the OF sensor will be integrating
   back to non-zero immediately, so a near-zero reading after reset is only
   meaningful on a stationary drone.

Frame: [0xCC] [0xDD] [CMD_ID u8] [INDEX u8] [VALUE float32 LE] [CRC8]
CRC8 is XOR over [CMD_ID, INDEX, VALUE b0..b3].
CMD 0x10, idx 0, value 0.0 (LE = 00 00 00 00):
  XOR = 0x10 ^ 0x00 ^ 0x00 ^ 0x00 ^ 0x00 ^ 0x00 = 0x10
Frame: CC DD 10 00 00 00 00 00 10

Usage from repo root:
    .venv\\Scripts\\python.exe scratchpad\\test_usart3_dispatch.py

Assumes the FC is powered and disarmed, USART3 wired to the MicoAir module, and
livewatch has been verified (`python -m ground_station.livewatch verify`).
"""
import socket
import struct
import sys
import time
from pathlib import Path

from ground_station.livewatch import LiveReader
from ground_station.livewatch.verify import (
    VerifyResult, compare, flash_segments, plan_samples)


ELF = Path("OBJ/JX_FLY.axf")
MODULE_IP = "192.168.4.1"
UDP_PORT = 14550


def elf_verifies() -> bool:
    """Returns True if the ELF on disk matches the firmware on the FC."""
    segments = flash_segments(ELF)
    samples = plan_samples(segments, n=5)
    with LiveReader(str(ELF)) as lr:
        return compare(samples, lambda a, n: lr._target.read_memory_block8(a, n)).ok


def read_via(names):
    """Resolve and sample names through livewatch. Returns dict or None."""
    try:
        with LiveReader(str(ELF)) as lr:
            plan = lr.plan(names)
            return lr.sample(plan)
    except Exception as exc:
        print("livewatch read %s failed: %s" % (names, exc))
        return None


def main():
    print("[1/4] verifying ELF matches running firmware...")
    if not elf_verifies():
        print("ELF STALE: rebuild or reflash before testing")
        return 1
    print("      ELF OK")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8 * 1024 * 1024)
    sock.settimeout(0.2)

    # Nudge the module so it learns our address before counting
    for _ in range(3):
        sock.sendto(b"\n", (MODULE_IP, UDP_PORT))
        time.sleep(0.1)

    print("[2/4] reading UA3RxFrameCnt + loc-PID BEFORE...")
    pre = read_via(["UA3RxFrameCnt", "UA3RxLastLen",
                    "Ctrler.locxPID.FB", "Ctrler.locyPID.FB"])
    if pre is None:
        return 1
    pre_count = int(pre["UA3RxFrameCnt"])
    pre_x = float(pre["Ctrler.locxPID.FB"])
    pre_y = float(pre["Ctrler.locyPID.FB"])
    print("      UA3RxFrameCnt=%d  UA3RxLastLen=%d  locxPID.FB=%.3f  locyPID.FB=%.3f"
          % (pre_count, int(pre["UA3RxLastLen"]), pre_x, pre_y))

    # 0xCC 0xDD CMD=0x10 idx=0 value=0.0 -> CRC = XOR(0x10, 0x00, 0x00, 0x00, 0x00, 0x00) = 0x10
    cmd_id = 0x10
    idx = 0x00
    value = 0.0
    val_bytes = struct.pack("<f", value)
    crc = cmd_id ^ idx ^ val_bytes[0] ^ val_bytes[1] ^ val_bytes[2] ^ val_bytes[3]
    frame = bytes([0xCC, 0xDD, cmd_id, idx,
                   val_bytes[0], val_bytes[1], val_bytes[2], val_bytes[3], crc])
    print("[3/4] sending: %s (CRC=0x%02X)" % (frame.hex(), crc))
    # send twice -- the parser walks offsets, and one dropped datagram should
    # not be mistaken for a failed test
    for _ in range(2):
        sock.sendto(frame, (MODULE_IP, UDP_PORT))
        time.sleep(0.25)

    # wait for FC to process and IDLE to fire
    time.sleep(1.5)

    print("[4/4] reading UA3RxFrameCnt + loc-PID AFTER...")
    post = read_via(["UA3RxFrameCnt", "UA3RxLastLen",
                     "Ctrler.locxPID.FB", "Ctrler.locyPID.FB"])
    if post is None:
        return 1
    post_count = int(post["UA3RxFrameCnt"])
    post_x = float(post["Ctrler.locxPID.FB"])
    post_y = float(post["Ctrler.locyPID.FB"])
    print("      UA3RxFrameCnt=%d  UA3RxLastLen=%d  locxPID.FB=%.3f  locyPID.FB=%.3f"
          % (post_count, int(post["UA3RxLastLen"]), post_x, post_y))

    print("")
    print("frame-count delta: %+d" % (post_count - pre_count))
    if post_count <= pre_count:
        print("FAIL: UA3RxFrameCnt did NOT advance -- radio downlink did not deliver")
        return 1
    print("PASS: radio downlink reached the FC (frame count advanced)")

    if abs(post_x) < 0.10 and abs(post_y) < 0.10:
        print("PASS: loc-PID feedback reset to ~0 -- command executed via USART3")
        return 0
    print("WARN: command reached the FC but loc-PID did not reset -- was the "
          "drone moving? Re-run on a stationary bench.")
    return 2


if __name__ == "__main__":
    sys.exit(main())