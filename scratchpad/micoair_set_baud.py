"""Does the module accept a baud ABOVE the dropdown's 921600 maximum?

The dropdown is client-side HTML; /save may take any integer.  Worth testing because a
higher baud is the CHEAPEST route from the measured 55 kB/s to the wire limit: the FC's
top ladder rungs collapse only because a 1124 B frame needs 12.31 ms to clock out against
a ~12.47 ms tick.  At 2 Mbps that same frame takes 5.6 ms and the rung fits comfortably.

Safe to try: the config page is served over WiFi, entirely independent of the UART, so a
baud the FC cannot match breaks only the serial link and never our way back in.

Reads the CURRENT form first and replays every field unchanged except baud -- posting a
partial form would silently reset channel, SSID or port.

usage: micoair_set_baud.py <baud> [ip]      e.g. micoair_set_baud.py 2000000
"""
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BAUD = sys.argv[1] if len(sys.argv) > 1 else "2000000"
HOST = sys.argv[2] if len(sys.argv) > 2 else "192.168.4.1"
BASE = "http://%s" % HOST


def fetch(timeout=6.0):
    with urllib.request.urlopen(BASE + "/", timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def parse_form(html):
    """Recover the form's current state: text/number inputs, selected options, checkboxes."""
    form = {}
    for m in re.finditer(r"<input\b([^>]*)>", html, re.I):
        attrs = m.group(1)
        name = re.search(r"name='([^']+)'", attrs)
        if not name:
            continue
        typ = (re.search(r"type='([^']+)'", attrs) or [None, "text"])[1]
        if typ == "submit":
            continue
        val = re.search(r"value='([^']*)'", attrs)
        if typ == "checkbox":
            # An unchecked box is simply absent from a real browser POST.
            if "checked" in attrs:
                form[name.group(1)] = val.group(1) if val else "1"
        else:
            form[name.group(1)] = val.group(1) if val else ""
    for m in re.finditer(r"<select\b[^>]*name='([^']+)'[^>]*>(.*?)</select>", html,
                         re.I | re.S):
        name, body = m.group(1), m.group(2)
        sel = re.search(r"<option\s+value='([^']*)'[^>]*\bselected\b", body, re.I)
        if sel:
            form[name] = sel.group(1)
        else:
            first = re.search(r"<option\s+value='([^']*)'", body, re.I)
            if first:
                form[name] = first.group(1)
    return form


print("reading current config from %s ..." % BASE)
try:
    before = parse_form(fetch())
except Exception as e:
    print("cannot reach the config page: %s" % e)
    print("Are you still joined to the module's wifi?")
    sys.exit(1)

print("current form state:")
for k in sorted(before):
    print("   %-8s = %s" % (k, before[k]))

old = before.get("baud", "?")
print("\nbaud %s -> %s" % (old, BAUD))
if old == BAUD:
    print("already set; nothing to do.")
    sys.exit(0)

payload = dict(before)
payload["baud"] = BAUD
data = urllib.parse.urlencode(payload).encode()

print("POSTing /save (the module reboots on save) ...")
try:
    req = urllib.request.Request(BASE + "/save", data=data,
                                 headers={"Content-Type":
                                          "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=8.0) as r:
        body = r.read().decode("utf-8", "replace")
    print("  HTTP %d, %d B response" % (r.status, len(body)))
    snippet = re.sub(r"<[^>]+>", " ", body)
    snippet = " ".join(snippet.split())[:300]
    if snippet:
        print("  says: %s" % snippet)
except urllib.error.HTTPError as e:
    print("  HTTP %d -- the firmware REJECTED the value" % e.code)
    sys.exit(2)
except Exception as e:
    # A save that reboots mid-response looks like a connection error; not fatal.
    print("  no clean response (%s) -- expected if it rebooted immediately" % e)

print("\nwaiting for reboot, then re-reading ...")
after = None
for attempt in range(20):
    time.sleep(2.0)
    try:
        after = parse_form(fetch(timeout=4.0))
        break
    except Exception:
        print("   still down (%d/20)" % (attempt + 1))

if after is None:
    print("\nModule did not come back within 40 s.")
    print("Rejoin its wifi (it reboots the radio too) and re-run to check.")
    sys.exit(3)

got = after.get("baud", "?")
print("\nbaud now reads: %s" % got)
changed = [k for k in set(before) | set(after)
           if before.get(k) != after.get(k)]
if changed:
    print("fields that changed: %s" % ", ".join(sorted(changed)))

print("\n--- verdict ---")
if got == BAUD:
    print(">>> ACCEPTED %s. The dropdown was NOT the module's limit." % BAUD)
    print("    Next: set the FC's USART3->BRR to match, then re-run the ladder.")
    print("    At 42 MHz APB1, BRR = round(42e6 / baud) = %d (0x%X) -> %.0f actual"
          % (round(42e6 / float(BAUD)), round(42e6 / float(BAUD)),
             42e6 / round(42e6 / float(BAUD))))
elif got == old:
    print(">>> REJECTED -- it kept %s. The firmware validates the value." % old)
    print("    921600 really is this module's ceiling; 91304 B/s is the hard wall.")
else:
    print(">>> It stored something else entirely: %s. Treat with suspicion." % got)
