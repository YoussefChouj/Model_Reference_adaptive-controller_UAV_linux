---
session: 2026-07-31-ticket10-radio
status: closed
updated: 2026-08-09
superseded_by: 2026-08-09-micoair-summary.md
supersedes: null
---

# Session 2026-07-31 — Ticket-10 radio capacity (CLOSED)

**Goal:** measure the new BLE radio module's real air capacity and pinpoint the knee.
**Outcome:** MAX CLEAN SUSTAINED GOODPUT = **4170 B/s** at 12 floats / 52 B frames / 80.2 Hz, 0.00 % loss. Per-frame SIZE limited, not byte-rate. **Superseded 2026-08-09** — see `2026-08-09-micoair-summary.md` (TX ring rework + 921600 baud lifted the limit to **90363 B/s = 98.8 % of the 91304 B/s UART wire**).

## What was actually measured

Two auto-stepping frame-size ladders, flashed once each, ran from the firmware itself stepping the rung (rung stamped into `float[1]`).

### Coarse ladder `{8,16,24,32,48,64,96,128,160,192,224}` floats, 2.9 → 72 kB/s offered

| floats | frame B | offered B/s | delivered B/s | loss |
|---|---|---|---|---|
| 8 | 36 | 2887 | 2887 | 0.00 % |
| 16 | 68 | 5454 | 4227 | 17.87 % |
| 24 | 100 | 8020 | 2059 | 59.24 % |
| 32 | 132 | 10586 | 235 | 80.57 % |
| ≥64 | ≥260 | ≥20852 | nothing survives | |

### Fine ladder `{8,10,12,14,16,18,20,24}`

| floats | frame B | offered B/s | delivered B/s | loss | intact |
|---|---|---|---|---|---|
| 8 | 36 | 2887 | 2887 | 0.00 % | 100 % |
| 10 | 44 | 3529 | 3529 | 0.00 % | 100 % |
| **12** | **52** | **4170** | **4170** | **0.00 %** | **100 %** |
| 14 | 60 | 4812 | 4375 | 7.85 % | 98.6 % |
| 16 | 68 | 5454 | 4434 | 14.71 % | 95.3 % |
| 18 | 76 | 6095 | 4353 | 21.09 % | 90.4 % |
| 20 | 84 | 6737 | 3029 | 42.38 % | 77.9 % |
| 24 | 100 | 8020 | 2903 | 47.07 % | 68.2 % |

### Iso-byte-rate ladder (same 4170 B/s offered, only packaging differs)

| floats | div | Hz | frame B | offered B/s | delivered B/s | air loss | intact |
|---|---|---|---|---|---|---|---|
| **12** | 1 | 80.2 | **52** | 4170 | **4114** | **0.81 %** | 99.5 % |
| 25 | 2 | 40.1 | 104 | 4170 | 3721 | 9.09 % | 98.1 % |
| 51 | 4 | 20.05 | 208 | 4170 | 2875 | 25.86 % | 92.8 % |
| 103 | 8 | 10.03 | 416 | 4170 | 2841 | 22.96 % | 87.9 % |
| 207 | 16 | 5.01 | 832 | 4170 | 2367 | 34.29 % | 84.0 % |

Doubled-rate (8341 B/s): 51/2 → 73.99 % loss, 103/4 → 88.31 %, 207/8 → 88.78 %.

**An 832 B frame at 5 Hz loses 34 % while a 52 B frame at 80 Hz loses 0.81 % at identical bytes/sec.** Slowing down does NOT rescue a large frame. Mechanism: frames bigger than one BLE connection event get fragmented, and one lost fragment kills the whole frame. **Neither byte-rate nor packet-rate limited — packet SIZE limited.**

## Ruled-out levers (do not retry)

- **Lowering UART baud to 460800** — UART only 4.5 % utilised at 4170 B/s. Knee is a byte rate at the radio, FC baud was constant across every rung.
- **Lowering TX power 4 → −6 dBm** — power buys link MARGIN, not throughput. Already 0.00 % loss at desk range. 4 dBm is module max, keep it.

## Why this was a regression

Old 24RF best: **7718 B/s @ 0.08 % loss, 96 B frames** (memory `project_24rf_downlink_capacity`; 5413 B/s often quoted was its *suboptimal* 112 B config that skipped ticks). New BLE module best: **4170 B/s @ 0.00 %**. New radio carries **46 % less**. Real constraint is the module's BLE connection parameters (connection interval, packets per connection event, DLE, PHY) — not reachable from our side. Windows tool exposes only baud / TX power / pairing.

## Diagnostic sequence that got here (do not re-derive)

1. Dongle **USB replug** was required after the config tool was killed with COM7 open. Before: 0 bytes. After: bytes immediately.
2. `fc_baud_sweep.py` (host fixed at 921600, FC baud swept **against a live link**) — only FC 921600 gave `distinct=218`; 460800→31, 230400→13, 115200→2.
3. Spurious `BRR` revert 0x002E→0x016C was just the FC rebooting when the operator power-cycled. `brr_watch.py` proved no further reverts (`xTickCount` monotonic 750044 → 999679).
4. `chunk_analysis.py` separated corruption from overflow by searching for the fixed ramp at every alignment — no frame sync needed.

## Analysis trap, hit for real

`float[0]` counts EVERY frame across ALL rungs, so diffing all rung-N frames in a long capture counts the other rungs as loss. v1 of `ladder_goodput.py` reported **85 % loss on a rung independently measured at 0.000 %**. Deltas must be taken only WITHIN a contiguous run of one rung. Fixed in the script.

## Seller contact — they gave the wrong knob

Asked 有没有办法设置连接间隔. Seller replied with `AT+AINTVL=NUM\r\n` (20–10000 ms, write-only, 重启后生效) = **广播间隔, the ADVERTISING interval**. Governs pre-bond discovery only, has no effect on throughput once connected. They also said 不会这么低的. **Do not send it.** Follow-up drafted asking specifically for 连接间隔 / MTU / DLE / 2M PHY, with the 52 B-vs-832 B iso-rate evidence attached.

## Firmware changes that came out of this session

- `BSP/usart3.h:19` `USART3_BAUD` **115200 → 921600**. `API/tests/stubs/usart3.h:4` kept in sync.
- `TASK/send_data.c` `USART3_TEST_FLOATS` **63 → 8** (256 B → 36 B frames) so offered load sits under measured air capacity.

Flashed: `rebuild_and_flash --yes`, `Code=81484`, 0 errors, 75 warnings, ARM_Status=0, attempt 1, `OBJ/JX_FLY.axf` matches.

Post-flash measurement `goodput.py COM7 921600 10 8`: 841 whole frames, stride histogram `[(36, 840)]`, byte integrity 100.00 %, ramp corruption 0, sequence deltas `[(1, 840)]`, **air loss 0.000 %**, goodput **2888 B/s @ 80.2 Hz**.

## Caveat at the time

Desk conditions only (props off, stationary, ~1 m). In-flight re-measure owed before trusting thesis dataset.