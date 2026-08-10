# MicoAir WiFi — post-bringup follow-ups

> **Context**: The MicoAir WiFi link was brought up 2026-08-09. TX ring rework delivered
> 90363 B/s at 0.00% loss (98.8% of wire). Full MRAC state fits in one frame at 80 Hz.
> See `sessions_summary/2026-08-09-micoair-summary.md` for the full session record.
>
> **Firmware is FLASHED and running on the drone.** The pct-95 build is live.
>
> **STATUS: ⏸️ SKIPPED as an agent task 2026-08-10** — the only safe agent-side edit
> (item 2, flip `USART3_THROUGHPUT_TEST`) is **already satisfied**: `TASK/send_data.c:472`
> already reads `#define USART3_THROUGHPUT_TEST   0` (production image 2026-08-09). The
> source needs no change. Items 1, 3, 4, 5 are human-operator or decision-gated. Per the
> hard safety constraints, no flashing/bench interaction is routed through an agent.

## Remaining items

### 1. In-flight re-measurement (HUMAN OPERATOR — not an agent task)

**This requires a live drone in flight. Do NOT attempt from an agent session.**

- Run the frame-size ladder in flight: `scratchpad/micoair_ladder.py --transport usart3`
- Watch `UA3TxDrops` and `UA3TxPeak` (ring runs at 97% occupancy on the top rung; flight adds CPU contention)
- The real operating point is 444 B at 39% of wire — 2.5× headroom, but flight adds vibration + CPU load
- While up, re-verify the stream: `stream_log.py --transport usart3` is the thesis logging path

**Acceptance**: `UA3TxDrops = 0` in flight at the 444 B operating point. If non-zero, the ring is undersized for flight conditions.

### 2. Flip `USART3_THROUGHPUT_TEST` to 0 (simple firmware change)

File: `TASK/send_data.c`
- Change `#define USART3_THROUGHPUT_TEST 1` → `0`
- Production image should emit the 16 B attitude frame, not the test ladder, when no stream is subscribed
- Rebuild + flash: `python -m ground_station.flashtool.rebuild_and_flash --yes`
- Verify: the standard 16 B frame appears on the UDP stream (not the ladder)

**Acceptance**: `stream_log.py --transport usart3` shows the 16 B attitude frame, not the ladder, when no subscription is active.

### 3. OPEN DECISION: wire USART3 command dispatch

The MicoAir link is proven bidirectional at 99.9% with downlink pinned to the wire.
The only blocker is the deliberate decision to leave USART3 command dispatch unwired.

**Decision needed from operator**: Should the ground station send CMD frames over USART3 (the MicoAir link)?
- Pro: single cable, 99.9% reliable bidirectional, no BLE dongle needed
- Con: USART3 RX has no parser today (just counts bytes); needs a dispatch path

**If approved**: wire `USART3_IRQHandler` to parse CMD frames and dispatch them. The existing `BSP/usart3.c` RX path already counts IDLE-terminated frames into `UA3RxFrameCnt` — the framing is proven. The dispatch is the missing piece.

### 4. PAUSED: com0com + UDP bridge for everyday logging

com0com IS installed. The ports likely already exist under auto-assigned COMxx names.
- Enumerate: `powershell "Get-CimInstance Win32_SerialPort | Select-Object DeviceID, Name"`
- Once the pair is found, run `scratchpad/micoair_vcom_bridge.py <the B-side port>` (NOT YET WRITTEN)
- Open the A-side in Vofa+ / other tools
- **Do NOT measure capacity through the bridge** — it adds a Python hop + driver buffer; measure raw UDP

### 5. Known limitation — no TX-error recovery

Only `DMA_IT_TC` is enabled on DMA1_Stream3. If a transfer ever raises TE/FE, USART3 goes permanently silent.
- **Monitor**: if USART3 goes mute with FC otherwise healthy, read `UA3TxFrames` (still climbing = producer fine) and `UA3TxPeak` (pinned near 4096 = ring not draining)
- **Fix** (if it ever happens): enable TEIE and re-arm from the error path

## Files potentially touched

- `TASK/send_data.c` — flip `USART3_THROUGHPUT_TEST` to 0
- `BSP/usart3.c` — if wiring command dispatch (item 3)
- `scratchpad/micoair_vcom_bridge.py` — new file (item 4)

## Safety constraints

- Item 1 is HUMAN OPERATOR ONLY. Never run from an agent session.
- Item 2 (rebuild + flash) requires the drone disarmed + props off. The flashtool arm gate must pass.
- Item 3 requires operator decision before any code is written.