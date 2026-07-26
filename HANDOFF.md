# Session Handoff — 2026-07-26

Telemetry logging + UART5 baud characterisation. Read this before touching the
drone, `ground_station/livewatch/`, or `TASK/send_data.c`.

---

## 1. SAFETY CONSTRAINT — repeat verbatim, never relax

Drone is **disarmed on the bench, props ARE installed**. All live-target reads must be
read-only/non-halting (pyOCD attach mode via `ground_station/livewatch`). **NEVER**
halt/reset/write the core except through `ground_station/flashtool`'s gated flash path,
which refuses unless `DroneStatus.ARM_Status == DisArmed(0)` and `motor_test_active == 0`,
read live. Never bypass that gate. **Motors must never spin.** Direct pyOCD RAM writes are
user-authorized for non-motor/non-arm-state globals only.

**Additionally authorized this session (2026-07-26), by explicit user OK:** writing
`UART5->BRR` (`0x40005008`) over SWD to retune telemetry baud. Conditions that made it
safe, keep them: never transmit toward the drone while baud is mismatched; only sweep
*upward* from 115200; verify `stabilizerTask_cnt` still advances after each write; always
restore in a `finally`. **BRR is currently restored to `0x016C` (115200) — verified.**

**Standing design intent:** the OF-bias estimator stays the default position source. The
EKF stays shadow-mode/compute-only. Do **not** wire `s_ekf` into any control path without
an explicit go-ahead.

---

## 2. Headline results

### 2a. The EKF D5 gravity fix WORKED (verified on flashed firmware)

The previous session's falsifiable prediction is now answered. Logged 161 samples via the
new tooling (`logs/livewatch/ekf_ba_check_20hz_20260726-010912.csv`), `s_ekf.active == 1`:

| axis | `b_a` now | `Acc_*_Real` | ratio before | **ratio now** |
|---|---|---|---|---|
| x | −2.46 mg | 21.34 mg | 0.999 | **−0.115** |
| y | +0.86 mg | −5.54 mg | 1.004 | **−0.156** |
| z | **+11.87 mg** | 1008.37 mg | 1.000 | **0.012** |

`b_a.z` fell from a full **1 g to 11.9 mg** (83×). **NIS went from ~1e-5 to mean 0.064 /
max 0.78** — real innovation, no longer a passthrough. The filter is genuinely fusing.

Refinement to the earlier prediction: `b_a` decaying to zero on a static bench is right for
**x/y only**. `b_a.z = 11.87 mg` tracks `Lin_Acc_Z_body = 12.06 mg` almost exactly, because
`Ekf9_UpdateZRate` pins `v_z ≈ 0` at rest and makes `b_a.z` observable without motion. That
is correct behaviour. **x/y still need a flight log to validate.**

### 2b. The wireless module is NOT the telemetry bottleneck

Swept `UART5->BRR` live, receive-only measurement on COM6. PCLK1 = **42 MHz** (read from
live RCC: `RCC_CFGR=0x0000940A`, HPRE/1 PPRE1/4).

| baud | line util | Frame A Hz | crc bad |
|---|---|---|---|
| 115200 | 74.5% | 47.9 | 0.56% |
| 230400 | 37.3% | 47.7 | 0.00% |
| 460800 | 18.6% | 47.7 | 0.00% |
| 921600 | 9.3% | 47.7 | 0.00% |
| 1000000 | 8.6% | 47.9 | 0.00% |
| 1500000 | 5.7% | 47.9 | 0.00% |
| 2000000 | 4.3% | 47.9 | 0.00% |

**Clean to 2 Mbaud, `resync=0`.** 115200 is the *only* rate with errors, because it is the
only one near saturation. On 42 MHz PCLK1, **1.0 / 1.5 / 2.0 Mbaud divide exactly (0.00%
error)** while 921600 is −0.93% — prefer **1 Mbaud over 921600**.

### 2c. ROOT CAUSE of the 60 Hz cap: `usart3_send()` at 9600 baud

Frame rate is identical at every baud, so UART5 was never the limiter. `Send_Task`
(`USER/main.c:200`) calls `usart3_send()` (`TASK/send_data.c:317`), which busy-waits
`while(DMA_GetCurrDataCounter(DMA1_Stream3));` and pushes **16 bytes at 9600 baud**
(`BSP/usart3.c:48`):

```
16 B × 10 bits / 9600 = 16.67 ms → 59.99 Hz
```

Measured **59.6–60.1 Hz** across all seven rates. Zero frame loss: `frame_counter % 5 != 0`
(`send_data.c:709`) predicts A:B = 4:1, measured 47.9:12.1 = **3.96:1**, self-consistent.

**Consequence: `Ekf9_Predict` runs at 60 Hz, not the 100 Hz stated in CLAUDE.md.** dt ≈
16.7 ms. The measured-`dt` fix (`xTaskGetTickCount`) absorbs this correctly; a hardcoded
`0.005f` would have been **3.3× wrong, not 2×**.

Cheap fix if more telemetry rate is wanted: raise USART3 baud (16 B @ 115200 = 1.4 ms) or
drop `usart3_send` from the loop. **Raising UART5 baud without this changes nothing.**
NOT DONE — needs a firmware change + manual uVision rebuild.

**Separate unfixed bug spotted:** `usart3_send` hands DMA the address of `str_USART`, a
**local stack array**, then returns while the 16.67 ms transfer is still reading it.
Dangling stack buffer. Cosmetic here (VOFA attitude display only). Not touched.

---

## 3. What was built (all committed to working tree, NOT git-committed)

### New: manifest logging over SWD

- **`ground_station/livewatch/manifest.py`** (NEW) — `Manifest`, `ManifestStore`,
  `feasibility()` (offline cost model), `calibrate()` (measures against live target,
  median not mean), `unique_csv_path()`, `write_meta()`.
- **`ground_station/livewatch/manifests.yaml`** (NEW) — 5 manifests: `ekf_ba_check`,
  `ekf_vs_of`, `of_drift`, `pos_loop`, `health`.
- **`ground_station/livewatch/cli.py`** (MODIFIED) — added `manifests`, `budget`, `log`
  subcommands + `_manifest_args`; `main()` now returns an exit code.
- **`ground_station/livewatch/tests/test_manifest.py`** (NEW) — 14 tests.

Usage:
```bash
python -m ground_station.livewatch manifests
python -m ground_station.livewatch budget ekf_ba_check          # no hardware
python -m ground_station.livewatch log of_drift --secs 60
python -m ground_station.livewatch log --vars group:ekf s_of_bias_x --hz 100 --name probe
```

Rate feasibility is **checked, not assumed**: `log` calibrates against the real target and
**refuses** rather than silently producing a CSV that logs slower than its filename claims
(`--clamp` opts into the ceiling). Each run writes a unique CSV **plus a `.meta.json`** with
resolved addresses and an **ELF sha256 fingerprint** — address-resolved logs are meaningless
against the wrong build.

**Verified live end-to-end:** 161 samples @ effective 20.1 Hz; measured ceiling 97 Hz vs
offline model estimate 96 Hz (cost model validated).

### New: `verify` — proves the ELF matches the flashed firmware

- **`ground_station/livewatch/verify.py`** (NEW) + `livewatch verify` command +
  **`tests/test_verify.py`** (NEW, 9 tests).

```bash
python -m ground_station.livewatch verify
# -> "ELF matches target: 5 chunk(s), 320 B compared, 0 mismatches"   (exit 0)
# -> "STALE ELF: 3/5 chunk(s) differ (first at 0x...)"                (exit 2)
```

Compares evenly-spread chunks of the ELF's loadable flash segments against the same
addresses read off the target. **This closes the one hole a read-only tool still has:** a
stale `OBJ/JX_FLY.axf` resolves wrong addresses and returns plausible-looking garbage rather
than an error. **Ran clean 2026-07-26 — which independently proves the flashed image IS the
D5-fixed build**, beyond the `b_a` evidence in §2a.

### Agent access policy CHANGED (user-approved 2026-07-26)

`.cursor/rules/hardware-safety.mdc` previously banned Cursor from `livewatch` entirely. It now
**splits the ban by risk class**: `livewatch` is permitted (it has **no write path** — attach
mode, no `write_memory`/`halt`/`reset` in `reader.py`), while raw `pyocd`/`openocd`/`JLink` and
`ground_station.flashtool` stay fully banned. `verify` is **mandatory** before trusting any read.

Dedicated skills created for future agents:
- **`.claude/skills/livewatch/SKILL.md`** — Claude Code skill (auto-discovered)
- **`.cursor/commands/livewatch.md`** — Cursor `/livewatch` command
- `.cursorrules` updated to point at both

### Fixed: 2 PRE-EXISTING broken tests (not caused by this work)

`ground_station/livewatch/tests/test_livewatch.py` pinned absolute addresses that the user's
rebuild shifted by 12 bytes (new `s_ekf_last_tick` static in `send_data.c`). The resolver was
correct; the goldens were stale. Changed to parse `OBJ/JX_FLY.map` dynamically so they survive
rebuilds. **Suite now 25/25 green.**

### Measured cost model for the wireless CMSIS-DAP probe

`t_ms ≈ 1.9·regions + 0.0297·bytes` → **~33 KB/s**, ~1.9 ms/transaction. SWD is **~2.9×
faster than UART5 at 115200**. Sustainable sample rates: 8 vars 323 Hz, 16 vars 247 Hz,
32 vars 168 Hz, 64 vars 102 Hz. `manifest.py` rounds these UP (2.2 / 0.031) so offline
estimates under-promise.

### Scratchpad tools (temp dir, NOT in repo — recreate if needed)

`read_clocks.py` (live RCC/UART5 register dump + BRR table), `swd_bench.py` (cost model),
`uart_probe.py` (receive-only link meter), `baud_sweep.py` (the sweep, with all 5 safety
rules enforced in code).

---

## 4. IN FLIGHT — the next thing, not started

*(none — Live Log tab was implemented 2026-07-26 in `ground_station/gui/dashboard.py`. See CLAUDE.md Session State "Live Log dashboard tab".)*

---

## 5. Remaining work

1. **UART address-subscription firmware feature** — **shipped 2026-07-26** via the full
   `/uav-conductor uart5_address_subscription_cmd` pipeline (planner → implementer-1 → 
   reviewer-1 REJECT [3 HIGH: RX buffer overflow, Send_Task stack constraint, host error-routing]
   → implementer-2 → reviewer-2 ACCEPT WITH FIXES [MEDIUM + LOW] → conductor applies two surgical
   fixes → ACCEPT). 56/56 livewatch+gui tests green; spec + journal in
   `.agent_contracts/uart5_address_subscription_cmd/`. **Firmware-side producer implemented:**
   - `BSP/usart5.c` extended with a second `0xCC 0xDE` branch in the existing parser loop
     (the `0xCC 0xDD` IF-01 9-byte parser is untouched, runs in the `else if`).
   - `API/subscribe.{c,h}` (NEW) — `Subscribe_ValidateTuple`, `Subscribe_ParseRequest`,
     `Subscribe_BuildReply`, `Subscribe_BuildError`, `Uart5_Subscribe_HandleRequest`. File-scope
     `tx_buf[512]`, `err_buf[256]`, `err_truncate_tmp[241]`, `s_pending` (193 B).
   - `BSP/usart5.h` — `USART5_RXDMA_LEN` and `USART5_RXMB_LEN` enlarged from 128 to 256 B
     so 32-tuple requests (199 B) pass the `offset + frame_len > total` gate.
   - `TASK/send_data.c` — `Send_Task` picks up the staged request off the back of the existing
     `Send_Groundstation_Telemetry_UART4` DMA1_Stream7 hand-off; reply is on a second DMA turn.
     No new FreeRTOS task.
   - `USER/JX_FLY.uvprojx` — `API/subscribe.c` added to the API file group.
   - **Host-side header rename** — `ground_station/livewatch/transport.py` and
     `test_transport.py`: the request frame's leading bytes changed from `b"\xAA\xBB"` to
     `b"\xCC\xDE"` (the `0xAA 0xBB` was the REPLY header per IF-02 — a reviewer-pinned bug
     in the host spec). The reply frame is unchanged (`_REPLY_FRAME = 0x07`, header `0xAA 0xBB`).
   - **0x7F error-reply surfacing** — host's `_wait_for_frame` decodes 0x7F frames as
     `LiveTransportError` with the payload string ("E:bad addr" etc.). New test
     `test_uart5_error_reply_surfaced` covers the path.
   - **Address allowlist derived from `OBJ/JX_FLY.map`** — SRAM `[0x20000000, 0x2001FFFF]`
     (RW_IRAM1 Max 0x20000; current size 0x1B388), CCM `[0x10000000, 0x1000FFFF]` (STM32F407
     datasheet, no symbols currently placed there).
   - **MAX_TUPLES = 32** per request. `sizeof(Subscribe_Request_t) = 193 B` (file-scope).
   - **C89 declaration placement** — all locals at block top; ARMCC V5.06 compatible.
   **Binding acceptance check: operator's uVision GUI rebuild + reflash** (the headless
   `UV4 -b` build is a documented dead end per §6). Once flashed, `python -m
   ground_station.livewatch log --transport uart5 group:<manifest>` should return real data
   instead of timing out. **Remaining open followups for this feature:**
   - `uart5_demux_with_bridge` — the COM-port conflict between the dashboard's `SerialBridge`
     and `Uart5LongRange` is currently resolved by "disconnect the dashboard's COM6 link first,
     then retry." A unified demux is owed by a separate workstream.
   - ADR documenting the `0xCC 0xDE` host→FC header and the 0x7F error-reply envelope.
2. **ADR-0011 amendment** — still owed, documents the predict-input / `UpdateAccXY` removal.
3. **`usart3_send` 60 Hz cap** — decided but not implemented; needs a manual uVision rebuild.
4. **D3, OF scale** — code uses `OF_LSB_MPS = 0.01`; `docs/tracking_baseline_and_drift.md:224`
   measured `0.0124 ± 0.0009`, and ADR-0011:131 derives `R_of` from 0.0124. User chose to keep
   0.01 to isolate variables. Now that the rebuild is verified, this can be revisited.
5. **Flight log for EKF x/y validation** — `b_a` x/y need motion; bench can't confirm them.

---

## 6. Gotchas worth knowing

- **`UV4 -b` headless build is a fully-investigated DEAD END.** Build in the uVision GUI.
- **`system_monitor.USART2_task_cnt` is useless for rate measurement** — incremented in BOTH
  the USART2 RX ISR (`stm32f4xx_it.c:92`) and `Send_Task` (`main.c:233`), AND zeroed every
  period by `systemmonitor_task.c:21`. Reads ~7400 Hz (the OF RX ISR).
  The `*_fps` fields also read as `1` and are not usable.
- **`Send_Groundstation_Telemetry_UART4()` sends via UART5**, not UART4. Legacy name.
- **Telemetry frame header is 6 bytes**, not 5: `AA BB | type | len_hi len_lo (BE) |
  MAX_NUM_BASIS`, then payload. Frame A = `6+41+1` (XOR CRC8); **Frame C (`0x06`) =
  `6+46+2`, a CRC16** — different trailer width. Getting this wrong makes every CRC fail
  while the sync bytes still land at the right rate, which looks like link corruption.
- **pyOCD `read_memory_block8` degrades to byte-at-a-time `read8`** for unaligned/sub-word
  symbols (e.g. 1-byte `motor_test_active`), and that path fails **far** more often on this
  wireless probe. Read the **enclosing aligned word with `read32`** and mask instead.
- **The probe throws TransferError in clusters**, not uniformly — use exponential backoff,
  a fixed short delay burns all retries inside one bad patch.
- **The probe is ONE composite USB device** (`ATK_20190528`): CMSIS-DAP on `MI_02` (HID) +
  UART5 CDC bridge on `MI_00` = **COM6**. They share one USB pipe.
- The repo has an **auto-commit hook** — commits can appear without you running git.
- `CLAUDE.md` "Session State" has been rolled back by repo machinery before; re-checkpoint
  if it reverts.

---

## 7. Open questions (carried, still unanswered)

- Whether swapping the wireless probe and the comm module on UART5 interferes if it is not a
  clean physical swap.
- Possible `Ctrler.locxPID.FB` ↔ `earth_y` axis-swap oddity (deferred).
- **CLAUDE.md states `Send_Task` runs at 100 Hz — this is now measured as 60 Hz.** Correct
  it when convenient.
