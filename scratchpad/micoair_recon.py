"""Recon the MicoAir-WiFi-Link while the PC is joined to its AP (no internet).

Everything goes to a report file, so it can be run offline and read back later once
the PC is on a network that can reach Claude again.

Answers three questions:
  1. What does the config page at 192.168.4.1 expose?  (baud, mode, ports)
  2. Which TCP ports are open?  That is where telemetry will actually come from.
  3. Is anything already streaming on the usual MAVLink/telemetry UDP ports?

Pure stdlib -- no requests, no venv needed.

usage: micoair_recon.py [host]
"""
import socket
import sys
import urllib.error
import urllib.request
from pathlib import Path

HOST = sys.argv[1] if len(sys.argv) > 1 else "192.168.4.1"
OUT = Path(__file__).with_name("micoair_recon.txt")

# Ports worth trying: web config, telnet-style bridges, the ESP-AT/transparent
# defaults, and the ArduPilot/MAVLink conventions this class of module targets.
TCP_PORTS = [23, 80, 81, 88, 443, 502, 1234, 2000, 3333, 4444, 5760, 5761,
             6000, 8000, 8080, 8266, 8888, 9000, 14550, 14555, 23333]
UDP_PORTS = [14550, 14551, 14555, 5760, 8888, 9000]

PAGES = ["/", "/index.html", "/config", "/setting", "/settings", "/param",
         "/api/config", "/api/status", "/status", "/info", "/get_config",
         "/wifi", "/serial", "/uart"]

lines = []


def log(s=""):
    print(s)
    lines.append(s)


log("=" * 72)
log("MicoAir-WiFi-Link recon -- host %s" % HOST)
log("=" * 72)

# ---------------------------------------------------------------- reachability
log("\n--- reachability ---")
try:
    s = socket.create_connection((HOST, 80), timeout=3)
    s.close()
    log("TCP 80 open -- web config is up")
except Exception as e:
    log("TCP 80 NOT reachable (%s)" % e)
    log("Are you actually joined to MicoAir_WiFi_Link_FD3D? Check your IP is 192.168.4.x")

# ------------------------------------------------------------------ web config
log("\n--- HTTP pages ---")
for path in PAGES:
    url = "http://%s%s" % (HOST, path)
    try:
        with urllib.request.urlopen(url, timeout=4) as r:
            body = r.read()
        ctype = r.headers.get("Content-Type", "?")
        log("\n[%3d] %-16s %-28s %d B" % (r.status, path, ctype, len(body)))
        try:
            text = body.decode("utf-8", "replace")
        except Exception:
            text = repr(body[:400])
        # The whole point is the settings, so dump small pages verbatim.
        log("-" * 60)
        log(text if len(text) <= 6000 else text[:6000] + "\n...[truncated]...")
        log("-" * 60)
    except urllib.error.HTTPError as e:
        log("[%3d] %-16s (HTTP error)" % (e.code, path))
    except Exception:
        pass          # 404-by-refusal and timeouts are just noise here

# -------------------------------------------------------------------- TCP scan
log("\n--- open TCP ports ---")
open_tcp = []
for p in TCP_PORTS:
    try:
        s = socket.create_connection((HOST, p), timeout=0.6)
    except Exception:
        continue
    open_tcp.append(p)
    banner = b""
    try:
        s.settimeout(1.5)
        banner = s.recv(256)          # a live telemetry port will spew immediately
    except Exception:
        pass
    finally:
        s.close()
    if banner:
        log("  %-6d OPEN  -- %d B unsolicited: %s" % (p, len(banner), banner[:64].hex(" ")))
    else:
        log("  %-6d OPEN  -- silent (needs the FC connected to produce data)" % p)
if not open_tcp:
    log("  none")

# -------------------------------------------------------------------- UDP peek
log("\n--- UDP listen (2 s each; only sees traffic if the module pushes) ---")
for p in UDP_PORTS:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(2.0)
        s.bind(("0.0.0.0", p))
        # Nudge the module: many bridges only stream after they hear from you.
        try:
            s.sendto(b"\n", (HOST, p))
        except Exception:
            pass
        data, addr = s.recvfrom(2048)
        log("  %-6d GOT %d B from %s: %s" % (p, len(data), addr, data[:48].hex(" ")))
    except socket.timeout:
        log("  %-6d silent" % p)
    except Exception as e:
        log("  %-6d could not bind (%s)" % (p, e))
    finally:
        try:
            s.close()
        except Exception:
            pass

log("\n" + "=" * 72)
log("SUMMARY")
log("  open TCP ports: %s" % (open_tcp or "none"))
log("  -> the telemetry socket is almost certainly one of these")
log("  Next: find the UART BAUD setting in the page dumps above.")
log("        It must reach 921600 or this module cannot beat the BLE one.")
log("=" * 72)

OUT.write_text("\n".join(lines), encoding="utf-8")
print("\n\nreport written to %s" % OUT)
