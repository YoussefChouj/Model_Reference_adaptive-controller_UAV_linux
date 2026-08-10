"""Measure the MicoAir WiFi Link's real capacity against the FC's 6 -> 90 kB/s ladder.

The firmware steps frame size through {18,30,50,80,120,170,220,280} floats every tick
(~7 s per rung), stamping the rung into float[1], so ONE flash yields the whole curve.

Two artifacts can masquerade as radio loss at these rates, and both are handled here:

  * FC EMISSION CADENCE.  Send_Task runs at 80.2 Hz (12.47 ms).  Before the TX ring
    (firmware 2026-08-09) a transfer that straddled the tick was skipped outright and
    the cadence HALVED -- 48.3 Hz at 884 B, with the radio losing nothing.  The ring
    removed that, but actual Hz is still derived from arrival timestamps rather than
    assumed, so any future cadence collapse is reported as such instead of as loss.
  * FC RING OVERFLOW.  float[3] carries UA3TxDrops.  A seq gap with drops ALSO rising
    is the FC refusing a frame it had no room to queue, i.e. the 91304 B/s UART wire
    binding -- structurally different from the radio losing a frame in the air.
  * UDP REORDERING.  Unlike a serial stream, datagrams can arrive out of order.  A
    negative seq delta is counted as reorder, not as loss.

Loss comes from consecutive float[0] deltas WITHIN one contiguous rung.  Never max-min,
never pooled across rungs -- both traps have already produced false 85-96 % readings on
runs independently measured at 0.000 %.

usage: micoair_ladder.py [seconds] [module_ip] [port]
"""
import bisect
import socket
import struct
import sys
import threading
import time
from pathlib import Path


def _flag(name, default):
    """Pull --name VALUE out of argv so positionals stay positional."""
    if name in sys.argv:
        i = sys.argv.index(name)
        v = sys.argv[i + 1]
        del sys.argv[i:i + 2]
        return float(v)
    return default


# Full-duplex load.  Uplink MUST share this script's socket: a separate process would
# send from an ephemeral port, and if the module replies to whoever it last heard from,
# the downlink would be diverted away from the capture and look like total loss.
UPLINK_BPS = _flag("--uplink-bps", 0.0)
UPLINK_SIZE = int(_flag("--uplink-size", 128))

SECONDS = float(sys.argv[1]) if len(sys.argv) > 1 else 130.0
HOST = sys.argv[2] if len(sys.argv) > 2 else "192.168.4.1"
PORT = int(sys.argv[3]) if len(sys.argv) > 3 else 14550

TAIL = b"\x00\x00\x80\x7f"
TICK_HZ = 80.2
UART_WIRE = 913043 / 10.0          # 8N1 at the FC's actual BRR-derived baud
LADDER = [18, 30, 50, 80, 120, 170, 220, 280]
BLE_REF = 6737.0                   # the module this one replaces
TARGET = 44000.0                   # full MRAC state, ~110 floats @ 100 Hz

OUT = Path(__file__).with_name("micoair_ladder.txt")
lines = []


def log(s=""):
    print(s)
    lines.append(s)


class Reader(threading.Thread):
    """Drains the socket as fast as possible; parsing happens after the capture."""

    def __init__(self, sock):
        super().__init__(daemon=True)
        self.sock = sock
        self.buf = bytearray()
        self.offs = []             # cumulative byte offset of each datagram's end
        self.marks = []            # arrival time of each datagram
        self.count = 0
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
                self.offs.append(len(self.buf))
                self.marks.append(time.perf_counter())
                self.count += 1


sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8 * 1024 * 1024)
sock.settimeout(0.2)
try:
    sock.bind(("0.0.0.0", PORT))
except OSError as e:
    log("could not bind UDP %d: %s" % (PORT, e))
    log("Something else is using it, or you are not on the module's network.")
    sys.exit(1)

rcvbuf = sock.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF)
log("listening on UDP %d | module %s | %.0f s | rcvbuf %d B" % (PORT, HOST, SECONDS, rcvbuf))
log("UART wire limit %.0f B/s; ladder tops out at 90145 B/s = %.1f%% of it\n"
    % (UART_WIRE, 100.0 * 90145 / UART_WIRE))

rd = Reader(sock)
rd.start()
# Nudge the module so it learns our address — it routes UDP downlink to
# whichever peer sent most recently. One byte is enough; harmless on the FC.
for _ in range(3):
    try:
        sock.sendto(b"\n", (HOST, PORT))
    except OSError:
        pass
    time.sleep(0.1)

up = {"bytes": 0, "n": 0}
up_stop = threading.Event()


def uplink_load():
    """Push PC -> module -> FC USART3 RX on the SAME socket as the downlink."""
    payload = bytes(((i * 7 + 0x31) & 0x7F) or 0x31 for i in range(UPLINK_SIZE))
    period = UPLINK_SIZE / UPLINK_BPS
    nxt = time.perf_counter()
    while not up_stop.is_set():
        now = time.perf_counter()
        if now >= nxt:
            try:
                sock.sendto(payload, (HOST, PORT))
                up["bytes"] += UPLINK_SIZE
                up["n"] += 1
            except OSError:
                pass
            nxt += period
            if nxt < now - 0.05:
                nxt = now
        else:
            time.sleep(0)


if UPLINK_BPS > 0:
    log("FULL DUPLEX: uplink %d B x %.1f/s = %.0f B/s running during the capture\n"
        % (UPLINK_SIZE, UPLINK_BPS / UPLINK_SIZE, UPLINK_BPS))
    threading.Thread(target=uplink_load, daemon=True).start()

t0 = time.perf_counter()
try:
    while time.perf_counter() - t0 < SECONDS:
        time.sleep(0.25)
finally:
    dt = time.perf_counter() - t0
    up_stop.set()
    rd.stop.set()
    rd.join(timeout=2.0)
    sock.close()

if UPLINK_BPS > 0:
    log("uplink sent %d datagrams, %d B -> %.0f B/s actual"
        % (up["n"], up["bytes"], up["bytes"] / dt if dt else 0))

buf = bytes(rd.buf)
offs, marks = rd.offs, rd.marks
log("captured %d B in %.1f s -> %.0f B/s aggregate, in %d datagrams (avg %.0f B)"
    % (len(buf), dt, len(buf) / dt if dt else 0, rd.count,
       len(buf) / rd.count if rd.count else 0))

if not buf:
    log("\nNOTHING ARRIVED. Check in this order:")
    log("  1. Is the PC joined to MicoAir_WiFi_Link_FD3D? (ipconfig -> 192.168.4.x)")
    log("  2. Did the baud save as 921600 and the module reboot?")
    log("  3. Is module RXD on FC TXD (PC10) and module TXD on FC RXD (PC11)?")
    log("     If in doubt, SWAP them -- that is the classic first failure.")
    log("  4. Is the FC powered and running the flashed ladder?")
    OUT.write_text("\n".join(lines), encoding="utf-8")
    sys.exit(1)


def t_at(off):
    i = bisect.bisect_left(offs, off)
    return marks[min(i, len(marks) - 1)]


# ---- parse JustFloat frames -------------------------------------------------
valid = set(LADDER)
frames = []
pos = buf.find(TAIL)
pos = 0 if pos < 0 else pos + 4        # drop the leading partial frame
while True:
    i = buf.find(TAIL, pos)
    if i < 0:
        break
    payload = buf[pos:i]
    pos = i + 4
    if len(payload) < 16:
        continue
    # float[3] = UA3TxDrops, the FC's TX-ring overflow count (firmware 2026-08-09).
    # It separates FC-side loss from air loss: a gap in seq with drops ALSO rising
    # is the ring refusing a frame because the UART could not drain it in time,
    # which is us hitting the wire -- not the radio dropping anything.
    seq, lf, _div, drops = struct.unpack("<ffff", payload[:16])
    if lf != int(lf) or int(lf) not in valid:
        continue                       # not a labelled frame: merged or torn
    nf = int(lf)
    frames.append((nf, seq, len(payload) + 4, len(payload) == nf * 4, t_at(i),
                   drops))

log("recovered %d labelled frames\n" % len(frames))
if not frames:
    log("Bytes arrived but no frame parsed -- baud mismatch corrupts every frame.")
    log("Confirm the module's Baud Rate really saved as 921600.")
    OUT.write_text("\n".join(lines), encoding="utf-8")
    sys.exit(1)

# ---- group into contiguous runs of one rung ---------------------------------
runs = []
cur = [frames[0]]
for f in frames[1:]:
    if f[0] != cur[0][0]:
        runs.append(cur)
        cur = []
    cur.append(f)
runs.append(cur)

stats = {}
for run in runs:
    if len(run) < 4:
        continue                       # too short to trust: rung-boundary crumbs
    span = run[-1][4] - run[0][4]
    if span <= 0.5:
        continue
    nf = run[0][0]
    s = stats.setdefault(nf, {"clean": 0, "trunc": 0, "bytes": 0, "lost": 0,
                              "trans": 0, "reorder": 0, "span": 0.0, "n": 0,
                              "drops": 0})
    # Rise of the FC's ring-overflow counter across this contiguous run.
    s["drops"] += max(0, int(round(run[-1][5] - run[0][5])))
    for _, _, ln, intact, _, _ in run:
        s["clean" if intact else "trunc"] += 1
        if intact:
            s["bytes"] += ln
    for a, b in zip(run, run[1:]):
        d = b[1] - a[1]
        if d >= 1:
            s["trans"] += 1
            s["lost"] += int(d) - 1
        elif d < 0:
            s["reorder"] += 1          # UDP can do this; a serial stream cannot
    s["span"] += span
    s["n"] += len(run) - 1

log("%-7s %-8s %-8s %-11s %-11s %-7s %-8s %-7s %-7s %s"
    % ("floats", "frame B", "act Hz", "offered", "delivered", "wire%", "LOSS %",
       "intact%", "FCdrop", "note"))
log("-" * 112)

best = None
for nf in LADDER:
    frame_b = nf * 4 + 4
    s = stats.get(nf)
    if not s or s["span"] <= 0:
        log("%-7d %-8d %s" % (nf, frame_b, "-- nothing survived --"))
        continue
    emitted = s["n"] + s["lost"]
    hz = emitted / s["span"]
    offered = frame_b * hz
    deliv = s["bytes"] / s["span"]
    denom = s["lost"] + s["trans"]
    loss = 100.0 * s["lost"] / denom if denom else 0.0
    tot = s["clean"] + s["trunc"]
    intact = 100.0 * s["clean"] / tot if tot else 0.0
    note = ""
    if hz < TICK_HZ * 0.75:
        note = "CADENCE %.1f Hz << 80.2: FC emitting slowly, not radio loss" % hz
    if s["drops"]:
        # The FC refused frames its own ring had no room for. That is the UART
        # wire binding, and it accounts for its share of the LOSS column.
        note = ((note + " | " if note else "")
                + "%d FC ring drops = AT THE WIRE" % s["drops"])
    if s["reorder"]:
        note = (note + " | " if note else "") + "%d reorders" % s["reorder"]
    log("%-7d %-8d %-8.1f %-11.0f %-11.0f %-7.1f %-8.2f %-7.1f %-7d %s"
        % (nf, frame_b, hz, offered, deliv, 100.0 * offered / UART_WIRE,
           loss, intact, s["drops"], note))
    if loss < 1.0 and intact > 99.0 and not note.startswith("CADENCE"):
        best = (nf, frame_b, deliv, hz)

log("\n" + "=" * 72)
log("VERDICT")
if best:
    log("  Highest CLEAN rung: %d floats = %d B at %.1f Hz -> %.0f B/s delivered"
        % (best[0], best[1], best[3], best[2]))
    log("  vs BLE module (6737 B/s): %.1fx" % (best[2] / BLE_REF))
    if best[2] >= TARGET:
        log("  >>> CLEARS the %.0f B/s full-MRAC-state target." % TARGET)
        log("      %d floats at %.0f Hz in ONE frame -- no round-robin needed."
            % (best[0], best[3]))
    else:
        log("  >>> Below the %.0f B/s target (%.0f%% of it)."
            % (TARGET, 100.0 * best[2] / TARGET))
        log("      Round-robin across frames is still required.")
else:
    log("  No rung ran clean. If even 18 floats (6095 B/s) fails, suspect the")
    log("  wiring or the baud rather than capacity -- that rate is trivial.")
log("=" * 72)

OUT.write_text("\n".join(lines), encoding="utf-8")
print("\nreport written to %s" % OUT)
