"""Measure the MicoAir WiFi Link's real throughput with NO flight controller.

Short the module's TXD to its RXD with one jumper.  Then every byte we push over
UDP goes out the UART, straight back in, and returns over UDP:

    PC --UDP--> module --UART TX--> [jumper] --UART RX--> module --UDP--> PC

That exercises the whole bridge in BOTH directions at once, so it is a pessimistic
test: the real telemetry case is one-way downlink only.  Whatever survives here,
the drone will beat.

Loss is counted from CONSECUTIVE sequence deltas within the run -- never max-min,
which has burned this project twice (once reporting 96 % against a true 0.14 %).

Self-synchronising block, because UDP datagram boundaries are destroyed by the
UART byte stream in the middle and re-chunked arbitrarily on the way back:

    A5 5A A5 5A | seq uint32 LE | ramp

usage: micoair_loopback.py [module_ip] [port] [seconds-per-rate] [rate,rate,...]
"""
import socket
import struct
import sys
import threading
import time

HOST = sys.argv[1] if len(sys.argv) > 1 else "192.168.4.1"
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 14550
HOLD = float(sys.argv[3]) if len(sys.argv) > 3 else 6.0
RATES = ([int(x) for x in sys.argv[4].split(",")] if len(sys.argv) > 4
         else [5000, 10000, 20000, 30000, 44000, 60000, 80000, 90000])

MAGIC = b"\xA5\x5A\xA5\x5A"
BLOCK = 256                      # one UDP datagram; well under the 1500 B MTU
RAMP = bytes((i & 0xFF) for i in range(BLOCK - 8))
UART_WIRE = 921600 / 10.0        # 8N1 -> 92160 B/s in EACH direction

# The requirement this whole exercise exists to satisfy.
TARGET = 44000


def block(seq):
    return MAGIC + struct.pack("<I", seq & 0xFFFFFFFF) + RAMP


class Reader(threading.Thread):
    def __init__(self, sock):
        super().__init__(daemon=True)
        self.sock = sock
        self.buf = bytearray()
        self.datagrams = 0
        self.stop = threading.Event()

    def run(self):
        while not self.stop.is_set():
            try:
                d, _ = self.sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break
            if d:
                self.buf += d
                self.datagrams += 1


def analyse(raw):
    """Return (blocks_ok, corrupt, lost, transitions)."""
    ok = corrupt = lost = trans = 0
    prev = None
    pos = 0
    while True:
        i = raw.find(MAGIC, pos)
        if i < 0 or i + BLOCK > len(raw):
            break
        seq = struct.unpack("<I", raw[i + 4:i + 8])[0]
        if raw[i + 8:i + BLOCK] == RAMP:
            ok += 1
            if prev is not None:
                d = (seq - prev) & 0xFFFFFFFF
                if 1 <= d < 1000000:
                    trans += 1
                    lost += d - 1
            prev = seq
        else:
            corrupt += 1
        pos = i + BLOCK
    return ok, corrupt, lost, trans


sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
sock.settimeout(0.2)
try:
    sock.bind(("0.0.0.0", PORT))
except OSError as e:
    print("could not bind UDP %d: %s" % (PORT, e))
    sys.exit(1)

print("loopback via %s:%d | %d B blocks | UART wire limit %.0f B/s per direction"
      % (HOST, PORT, BLOCK, UART_WIRE))
print("jumper TXD<->RXD on the module must be fitted, or nothing comes back.\n")
print("%-11s %-11s %-11s %-8s %-9s %-8s %s"
      % ("target B/s", "offered", "returned", "wire %", "LOSS %", "corrupt", "note"))
print("-" * 84)

seq = 0
best = None
try:
    for rate in RATES:
        rd = Reader(sock)
        rd.start()
        # Wake the bridge so it learns our address before we start timing.
        sock.sendto(block(seq), (HOST, PORT))
        seq += 1
        time.sleep(0.3)
        rd.buf.clear()

        period = BLOCK / float(rate)
        t0 = time.perf_counter()
        nxt = t0
        sent = 0
        while True:
            now = time.perf_counter()
            if now - t0 >= HOLD:
                break
            if now >= nxt:
                sock.sendto(block(seq), (HOST, PORT))
                seq += 1
                sent += BLOCK
                nxt += period
                if nxt < now - 0.05:        # fell behind; stop trying to catch up
                    nxt = now
            else:
                time.sleep(0)
        el = time.perf_counter() - t0
        time.sleep(1.0)                     # let the loop drain
        rd.stop.set()
        rd.join(timeout=1.5)

        ok, corrupt, lost, trans = analyse(bytes(rd.buf))
        offered = sent / el
        returned = ok * BLOCK / el
        loss = 100.0 * lost / (lost + trans) if (lost + trans) else 0.0
        note = ""
        if offered < rate * 0.9:
            note = "PC could not offer the target"
        elif returned < 1.0:
            note = "nothing returned -- is the TXD<->RXD jumper fitted?"
        print("%-11d %-11.0f %-11.0f %-8.1f %-9.2f %-8d %s"
              % (rate, offered, returned, 100.0 * offered / UART_WIRE,
                 loss, corrupt, note))
        if loss < 1.0 and corrupt == 0 and returned > rate * 0.9 and not note:
            best = (rate, returned, loss)
finally:
    sock.close()

print("\n--- verdict ---")
if best:
    print("Highest CLEAN rate: %d B/s offered -> %.0f B/s returned, %.2f%% loss"
          % (best[0], best[1], best[2]))
    print("BLE module for comparison: 6737 B/s  -> this is %.1fx"
          % (best[1] / 6737.0))
    if best[1] >= TARGET:
        print(">>> CLEARS the %d B/s full-MRAC-state target." % TARGET)
        print("    And this is loopback (both directions); one-way will do better.")
    else:
        print(">>> Below the %d B/s target. But loopback loads the bridge twice --" % TARGET)
        print("    retest one-way with the FC before concluding anything.")
else:
    print("No rate ran clean. Check: jumper fitted? baud saved as 921600 and rebooted?")
    print("If every row returned 0 B, the module is not bridging UDP->UART at all.")
