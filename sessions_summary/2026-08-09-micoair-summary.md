---
session: 2026-08-09-micoair-summary
status: active
updated: 2026-08-09
superseded_by: null
supersedes: 2026-07-31-ticket10-radio.md
---

# Session 2026-08-09 — MicoAir WiFi Link bring-up + USART3 TX ring rework

**Goal:** bring up MicoAir-WiFi-Link radio module on USART3 and lift telemetry capacity above the BLE bottleneck measured 2026-07-31.
**Outcome:** **90363 B/s at 0.00 % loss = 98.8 % of the 91304 B/s UART wire.** TX ring rework delivered **+64 %** vs pre-rework best, cadence collapse gone. The "keep frames under ~700 B" rule is **DEAD** (described the guard, not the link). Round-robin is **OBSOLETE** — full MRAC state (~110 floats = 444 B) fits in one frame at 80 Hz with 2.5× headroom.

CLAUDE.md Session State keeps the headline + active constraints + open decisions. Everything below is detail.

## TX ring rework — measured after flash

Ladder `{18,30,50,80,120,170,220,280}` floats, divider 1, flashed: `rebuild_and_flash --yes`, `Code=81908 RO=1516 RW=2412 ZI=118316`, 0 errors, 75 pre-existing warnings, attempt 1, arm gate DisArmed (129 unanimous Frame A + 9 unanimous SWD reads), `OBJ/JX_FLY.axf` matches the running image.

| floats | frame B | act Hz | offered B/s | delivered B/s | wire % | loss |
|---|---|---|---|---|---|---|
| 18/30/50/80/120 | 76…484 | ~80.3 | 6100…38872 | 6111…38944 | 6.7…42.6 | 0.00 % |
| 170 | 684 | 80.2 | 54886 | 54985 | 60.1 | 0.00 % |
| 220 | 884 | **80.4** | 71035 | **71171** | 77.8 | 0.00 % |
| **280** | **1124** | **80.3** | **90201** | **90363** | **98.8** | **0.00 %** |

Versus pre-rework: 220 rung 42672 → 71171 (**+67 %**), 280 rung 54379 → 90363 (**+66 %**), best 55116 → 90363 (**+64 %**). Cadence collapse to 48.3 Hz was the skip-if-busy DMA guard, exactly as diagnosed.

## What changed in firmware

Files: `BSP/usart3.h`, `BSP/usart3.c`, `TASK/send_data.c`, `TASK/stm32f4xx_it.c`.

- **4096 B TX ring** in `usart3.c`. `Usart3_Stream_TxSend()` copies and returns; `Usart3_Tx_DmaIsr()` advances the tail and arms the next chunk immediately, so the line stays saturated instead of one frame per `Send_Task` tick. `DMA1_Stream3_IRQHandler` now just calls into the driver so the tail pointer stays private.
- `usart3_send()`'s `if(DMA_GetCurrDataCounter(DMA1_Stream3)) return;` guard **deleted**; it now queues. `str_USART` is a staging buffer the DMA never reads.
- **A frame is queued whole or not at all** — a partial write would look like corruption to the host, which is worse than loss.
- `Usart3_Stream_Busy()` **changed meaning** to *backpressure* (ring over half full). Old sense is useless under continuous streaming.
- New livewatch symbols `UA3TxFrames` / `UA3TxDrops` / `UA3TxPeak`. The ladder stamps `UA3TxDrops` into **`float[3]`** so FC-side overflow is separable from air loss with no probe. `scratchpad/micoair_ladder.py` decodes and reports it as an `FCdrop` column.

## Ring sizing is not arbitrary — 2048 would have overflowed

Measured `UA3TxPeak = 3968` of 4096 (within 127 B of full) with `UA3TxDrops = 0` across ~337 s. ~3.5 frames of backlog really do build at the 98.8 % rung: `Send_Task` is preempted by the 1 kHz IMU and 200 Hz control loops, and its `vTaskDelayUntil` catch-up transiently offers 1124 B per 10 ms = 112 kB/s against a 91 kB/s wire. Absorbing that is the ring's entire job. The real operating point (444 B, 39 % of wire) never comes close. **~10.3 kB of ZI left.**

## Known limitation, accepted deliberately — no TX-error recovery

Only `DMA_IT_TC` is enabled on DMA1_Stream3. If a transfer ever raised TE/FE, the completion IRQ would never fire, `s_tx_active` would stay 1 and **USART3 would go permanently silent**. Not handled because direct-mode mem→periph transfer out of SRAM has no realistic error path, and the old code had the identical exposure. **If USART3 ever goes mute with the FC otherwise healthy, read `UA3TxFrames` (still climbing = producer fine) and `UA3TxPeak` (pinned near 4096 = ring not draining) — that pair identifies this instantly.** Fix would be enabling TEIE and re-arming from the error path.

## Concurrency contract, do not break it

Single-producer / single-consumer. Only task context advances `s_tx_head`, only the IRQ advances `s_tx_tail`. `tx_arm()` is reachable from both, hence the two ~10-instruction `__disable_irq()` windows in `Usart3_Stream_TxSend()`. The frame copy sits OUTSIDE them on purpose: the ISR can only advance tail, which only ever *increases* free space, so the space check stays valid.

## 0x21 subscribe stream over USART3 — proven end-to-end

`stream_log.py --transport usart3` ran the default 3-slot frame (`log_frames.md`) over the radio: **403/201/100 rows at 20.1/10.0/5.0 Hz, 0 drops, 0 malformed** (`logs/usart3_verify2.slotN.csv`). MRAC Theta weights and IMU angles decoded to plausible values with gapless seq.

### What changed

- **Budget pct 90 → 95 — FLASHED + PROVEN IN THE RUNNING IMAGE** (`API/subscribe.h`; host parity in `ground_station/livewatch/stream.py`; ceilings recomputed in `tests/test_stream.py`: 215 float32 @ divider 1 @ 921600). 95 % of the honest 92160 cap = 87552 B/s budgeted at nominal 100 Hz; the real 80.4 Hz cadence puts ≤ ~70 kB/s on the wire.
  - Flash: `rebuild_and_flash --yes`, `Code=81908 RO=1516 RW=2412 ZI=118316`, 0 errors, 75 warnings, arm gate DisArmed (130 unanimous Frame A), attempt 2 (attempt 1 exit 2 "part may be erased" — the retry path it exists for). .axf matches.
  - Guard proven live: 205 float32 @ divider 1 = 83200 B/s budgeted — REJECTED by the old pct-90 cap (82944), accepted now; delivered 402 rows @ 80.4 Hz, 0 drops, 0 malformed (`logs/usart3_guard.csv`). Post-flash regression clean too (`logs/usart3_postflash.*`).
- `stream_log.py` **UDP data path**: `--data-port` defaults to `udp:14550` for usart3; `_UdpDataPort` mimics `serial.Serial`; `--usart3-baud` flag added; stale 115200/COM3 defaults replaced with 921600/UDP. `log_frames.md` budget table updated.

## Two gotchas, hit for real

### GOTCHA 1 — module's downlink follows the last uplink source

After the module loses its peer entry (e.g. reboot across a session gap) it drops the downlink SILENTLY: a bind-only socket receives nothing even though ping 192.168.4.1 works fine. Diagnosed via the ring counters: `UA3TxDrops = 0` with `UA3TxFrames` climbing = ring draining = wire alive ⇒ fault was module-side, not FC-side. Fix: `_UdpDataPort` sends a 1-byte nudge from its own socket on open; downlink resumed instantly (82.8 kB/s within one sniff). The nudge byte lands in the FC's USART3 RX, which has no parser and merely counts it — proven harmless by the 6512-datagram uplink test. Reinforces the existing rule: uplink MUST share the capture socket.

### GOTCHA 2 — UART5 subscribe staging is single-buffered

Back-to-back 0x21 frames collide and silently never happen. Hit for real: `run_groups`' tear-down fired three stops unspaced; slots 1+2 stayed active. Fingerprint: `UA3TxFrames` climbing at exactly 15 Hz = 10+5 Hz, the two surviving slots. Stops are now spaced 250 ms apart.

## Setup

- USB-C is POWER ONLY (enumerates nothing). PC side is **UDP 14550, not a COM port**.
- Web config `http://192.168.4.1`, AP `MicoAir_WiFi_Link_FD3D` / `12345678`, running **5 GHz ch36**, baud saved 921600 (matches `BSP/usart3.h`, no firmware change needed). BLE 透传 unchecked.
- Module header `GND VCC RXD TXD` vs FC `GND RXD TXD VCC` — order differs and TX crosses to RX, so no 1:1 cable works. Wired with female-female 杜邦线.

## RX path proven — full duplex is free

No firmware change needed. USART3 IRQ counts IDLE-terminated frames into `UA3RxFrameCnt` (`BSP/usart3.c:19`, `TASK/stm32f4xx_it.c:139`), read over livewatch.

- Quiet: 500 datagrams → counter **6 → 506, exactly 1:1, zero loss**.
- During full 130 s duplex ladder: 6508 sent → **506 → 7012 = 6506 registered, 99.97 %**.
- Re-confirmed after ring rework, at 98.8 % wire utilisation: uplink **6507 of 6512 = 99.92 %**, top rung **90371 B/s duplex vs 90363 quiet (+0.01 %)**, every rung 0.00 % loss, `UA3TxPeak` unchanged at 3968 → RX adds no TX backlog whatsoever.

Commanding over the radio costs telemetry **NOTHING**. The only blocker is the deliberate decision to leave USART3 command dispatch unwired — a decision, not a link limitation.

**Uplink must share the capture's socket** (`micoair_ladder.py --uplink-bps N`): a separate process sends from an ephemeral port and the module may redirect the downlink to it.

## Baud > 921600 rejected — tested, do not retry

POSTed 1000000 / 1500000 / 2000000 straight to `/save`, bypassing the client-side `<select>`. All three **silently rejected**: answers `HTTP 200 "Saved Successfully! Device is rebooting..."`, reboots, still reads 921600. Harness `<scratchpad>/micoair_set_baud.py` (re-reads the live form and replays every field unchanged except baud — a partial POST resets channel/SSID/port). **91304 B/s is a HARD WALL**, and the link now sits at **98.8 % of it**. The firmware lever that was the only remaining option has been taken; nothing further is reachable without different hardware.

## Probe gotcha, hit again

`UA3RxFrameCnt` read `3233, 3233, 506, 3233` — a counter apparently DECREASING. Two identical corrupt reads, so "it agreed twice" is NOT a vote. **`xTickCount` is the ground truth for a target reset**: 3041111 → 3042544, monotonic, ~51 min uptime → no reboot → 3233 was corrupt, 506 real (= 6 + exactly 500 sent). Also 2 of 4 reads died outright with pyOCD `TransferError`. **Never diagnose a brownout from a counter alone.**

## Internet + module simultaneously — solved

Phone USB-tether gives `Ethernet 3 = 10.197.45.44` while Wi-Fi holds `192.168.4.2` on the module's AP. Both reachable at once. Module stays **AP mode on 5 GHz ch36** (no router dependency, identical at desk and field, off the RC's band) — STA mode was deliberately NOT adopted.

## Caveat — desk conditions only

Props off, stationary, ~1 m. **Re-run the ladder in flight before trusting the thesis dataset to it.**

## Rate-matching arithmetic

At the measured 90.4 kB/s = **22600 floats/s** → **~280 floats @ 80 Hz**, or ~2260 @ 10 Hz, or any mix. The `0x21` path already supports 4 independent rates. User's caveat accepted: with dense trajectories and a raised `gamma` some weights are genuinely fast, so do NOT assume 10 Hz suffices globally — per-variable rate choice is the point. Full MRAC state is ~110 floats, so the link now carries it **2.5× over** at full 80 Hz.

## Uncommitted (also from this session)

- TX ring rework: `BSP/usart3.h`, `BSP/usart3.c`, `TASK/send_data.c`, `TASK/stm32f4xx_it.c`, plus untracked `scratchpad/`. **524 tests green.**
- 0x21-over-USART3 migration: `API/subscribe.h` (pct 90→95), `API/subscribe.c` (comment-only), `ground_station/livewatch/stream.py` (parity + 921600 defaults), `stream_log.py` (UDP path, nudge, spaced stops, `--usart3-baud`), `tests/test_stream.py` (budget ceilings), `log_frames.md` (budget table).
- NOT part of this rework: the arm-gate hardening in `ground_station/flashtool/rebuild_and_flash.py` + its tests (voted SWD reads, `elf_matches_target`), and the pre-existing `SKILL.md` / `dashboard.py` / `docs/bench_characterization.md` / vofa-runtime edits. Commit in separate groups.

## Next action items (also in CLAUDE.md Session State)

1. ~~Flash the pct-95 build~~ DONE 2026-08-09.
2. **Re-measure the ladder IN FLIGHT** before trusting the thesis dataset. Watch `UA3TxDrops` / `UA3TxPeak` (ring runs at 97 % occupancy on top rung, flight adds CPU contention). Real 444 B operating point has 2.5× headroom. While up, re-verify the stream aloft: `stream_log.py --transport usart3` is the thesis logging path now.
3. OPEN DECISION: wire USART3 command dispatch or not — proven bidirectional at 99.9 % with downlink pinned to the wire. Constraint is purely deliberate.
4. com0com bridge, if the everyday-logging convenience is still wanted (see CLAUDE.md "PAUSED" note).
5. Flip `USART3_THROUGHPUT_TEST` to 0 in `TASK/send_data.c` once the in-flight re-measure is done — production image should emit the 16 B attitude frame, not the test ladder, when no stream is subscribed.

## PAUSED — com0com + UDP bridge

com0com IS installed and `setupg.exe` shows **"use Ports class" ticked on both halves**, but the operator could not rename the pair to COM20/COM21 — both halves read `portname=COM#`, which means Windows auto-assigns the next free numbers. **So the ports very likely already exist under real COMxx names; enumerate them before trying to rename anything.** Then run `scratchpad/micoair_vcom_bridge.py <the B-side port>` and open the A-side in the tools. **Do NOT measure capacity through the bridge** — it adds a Python hop and a driver buffer; measure raw UDP, use the bridge for everyday logging.