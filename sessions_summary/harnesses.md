---
session: harnesses
status: active
updated: 2026-08-09
superseded_by: null
supersedes: null
---

# MicoAir WiFi Link harness inventory

**These scripts live in `scratchpad/` and are UNTRACKED** (gitignored on purpose — session scratch). Anything cited from earlier sessions that is not here **no longer exists**; the session scratchpad gets cleaned. Do not go looking for retired names like `goodput.py`, `air_loopback.py`, `packet_vs_byte.py`, `baud_hunt.py`, `set_brr.py`.

## Current scripts

| Script | What it does | When to run |
|---|---|---|
| `micoair_ladder.py` | **THE measurement.** Binds UDP 14550, derives ACTUAL Hz from arrival timestamps so a cadence collapse is reported as such instead of scored as loss; loss from consecutive `float[0]` deltas WITHIN one contiguous rung; reads `float[3]` = `UA3TxDrops` into an `FCdrop` column so FC ring overflow is separable from air loss without a probe; counts UDP reorders separately. `--uplink-bps N` adds full-duplex load on the SAME socket. | Always. **A full sweep needs ≥130 s** — 8 rungs × 7 s each; a 20 s run only covers ~3 rungs and prints "nothing survived" for the rest. |
| `micoair_set_baud.py` | Re-reads the live form, replays every field unchanged except baud, POSTs `/save`, waits out the reboot, reports what actually stuck. | Only when probing baud headroom. **Baud > 921600 is REJECTED** — do not retry. |
| `micoair_uplink.py` | Standalone uplink. | Pair with a `livewatch read UA3RxFrameCnt` when measuring RX in isolation. Prefer the ladder's `--uplink-bps` for duplex. |
| `micoair_recon.py` | Config-page dump + TCP/UDP port scan, writes a report file. | When something about the module's behaviour surprises you. |
| `micoair_loopback.py` | TXD ↔ RXD jumper test, needs no FC. | Never (wires arrived — test is for hardware fault isolation only). |

> **No com0com needed.** All tools speak native UDP. `scratchpad/micoair_vcom_bridge.py` was deleted 2026-08-10.

## Usage example

```
.venv/Scripts/python.exe scratchpad/micoair_ladder.py 130
```

Default binds UDP 14550 against the module's AP (`192.168.4.1:14550`). Override target with positional args; full duplex with `--uplink-bps N`.

## What this script is NOT

It is not a flight harness. Re-run the ladder in flight (`stream_log.py --transport usart3` is the thesis logging path) before trusting any thesis dataset to it.