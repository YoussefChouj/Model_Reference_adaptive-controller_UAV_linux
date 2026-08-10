"""Push uplink traffic PC -> WiFi -> module -> FC USART3 RX.

Proves the inbound half of the link without touching firmware: the FC's USART3 IRQ
already counts IDLE-terminated frames into UA3RxFrameCnt
(BSP/usart3.c:19, TASK/stm32f4xx_it.c:139), so the counter moving IS the proof that
bytes crossed.  No command dispatch is involved or needed -- USART3 command dispatch
stays deliberately unwired.

Each datagram is sent as one burst with an idle gap after it, so the FC's IDLE-line
detection should register roughly one frame per datagram.  Coalescing is expected at
high rates (the module concatenates), so the counter is a LOWER bound on delivery.

Also usable as background load for the full-duplex test: run this while the downlink
ladder capture is going and compare the downlink numbers against the quiet baseline.

usage: micoair_uplink.py [seconds] [bytes_per_datagram] [datagrams_per_s] [ip] [port]
"""
import socket
import sys
import time

SECONDS = float(sys.argv[1]) if len(sys.argv) > 1 else 10.0
SIZE = int(sys.argv[2]) if len(sys.argv) > 2 else 64
RATE = float(sys.argv[3]) if len(sys.argv) > 3 else 50.0
HOST = sys.argv[4] if len(sys.argv) > 4 else "192.168.4.1"
PORT = int(sys.argv[5]) if len(sys.argv) > 5 else 14550

# Distinctive, non-zero, and NOT the JustFloat tail -- so if these bytes ever showed up
# in a downlink capture we would know the bridge was looping traffic back.
PAYLOAD = bytes(((i * 7 + 0x31) & 0x7F) or 0x31 for i in range(SIZE))

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(0.5)

period = 1.0 / RATE
print("uplink -> %s:%d | %d B x %.0f/s = %.0f B/s offered | %.0f s"
      % (HOST, PORT, SIZE, RATE, SIZE * RATE, SECONDS))

sent = n = 0
t0 = time.perf_counter()
nxt = t0
try:
    while True:
        now = time.perf_counter()
        if now - t0 >= SECONDS:
            break
        if now >= nxt:
            try:
                sock.sendto(PAYLOAD, (HOST, PORT))
                sent += SIZE
                n += 1
            except OSError as e:
                print("send failed: %s" % e)
                break
            nxt += period
            if nxt < now - 0.05:
                nxt = now
        else:
            time.sleep(0)
except KeyboardInterrupt:
    pass
finally:
    el = time.perf_counter() - t0
    sock.close()

print("sent %d datagrams, %d B in %.1f s -> %.0f B/s actual" % (n, sent, el, sent / el))
print("now re-read UA3RxFrameCnt; it should have advanced by up to %d" % n)
