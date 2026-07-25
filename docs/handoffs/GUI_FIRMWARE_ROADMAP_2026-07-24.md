# GUI + Firmware Feature Roadmap — 2026-07-24

> **Audience:** the next coding agent (human or AI) picking up from this session.
> **Goal:** catalog every feature the user discussed and hasn't yet shipped for the GUI (`ground_station/`) and the firmware (`API/`, `TASK/`, `BSP/`), plus cross-cutting items, so work can resume without re-deriving intent.
> **Sources:** 24+ chat transcripts in `C:\Users\Acer\.cursor\projects\c-Users-Acer-Desktop-UAV-lab-FreeRTOS-Six-Degrees-of-Freedom-Adaptive-controller\agent-transcripts\` (filtered extract at `docs/handoffs/_transcript_extract.txt`), the project's `CLAUDE.md` Knowledge Stack, and the live tree at this workspace.

---

## Status snapshot (2026-07-24)

| Subsystem | Status | Evidence |
|---|---|---|
| **Communication module** (telemetry ⇄ firmware via `serial_bridge.py` ↔ Frame 0x03 stream over UART5 wireless + USB-Serial dongle COM3) | ✅ **Working & stable** | Live probe 2026-07-23 8:40 PM: `COM3: 12.3 KB/s` telemetry, all variables decoded (transcript `cb29de41`) |
| **Keil uVision build** (firmware `JX_FLY.axf`) | ✅ **GREEN** (0 errors, ~65 pre-existing warnings) | Build log 2026-07-23 12:11 PM transcript `ff9e71e8` after two surgical fixes (uvprojx `<File>` add for `ekf.c`/`calib.c` + `static` removal on `s_cal_hot`/`s_cal_trim`) |
| **Sim package** (`sim/`) | ✅ **108/108 sim tests + 18/18 ground-station tests green** | ADR-0011 implementation sessions (transcripts `18c1dfa0`, `26fc2719`, `ff9e71e8`) |
| **Flight log analysis** (`flight_analysis/` CLI) | ✅ **42/42 tests; deployed as `/flight-analysis` skill** | Commit `4c69cdf`, transcript `df0a52b1` |
| **Hardware swap** (Rainsun → DeveBox PARE-COM air-side + USB 2.4RF-V4+ ground-side) | ✅ **Done; COM-port auto-detection live** | ADR-0007 (`docs/decisions.md`), transcript `cb29de41` |
| **MRAC + PID firmware core** (inner-loop control) | ✅ **Closed-loop with v13 telemetry** | Working-tree `mrac.c` / `pid.c`, telemetry green |

**This handoff covers what is *left to build***, not what's shipped. Items already shipped are summarized only enough to anchor the next agent.

---

## 1. Firmware — proposed features

### 1.1 Auto IMU Calibration (ADR-0011) — **✅ IMPLEMENTED, awaiting in-flight validation**

| What | Four-phase FSM: BOOT (Mahony fast-converge) → COLD (gyro bias only) → AIRBORNE_HOVER_TRIM (accel bias, 5–10 s in-flight) → HOT_HOVER (continuously updates gyro, frozen accel). Implemented end-to-end sim → firmware → GS → docs. GS_PROTO bumped 13 → 14; new `CMD 0x18 force_recal`. |
|---|---|
| Why | Pilot saw `+1.3°` pitch reading at level ground; suspected either physical tilt (crash-bent legs) or accel offset. Better to remove bias automatically than to chase it. |
| Files touched | `sim/calibrator.py` (new), `sim/ekf.py` (new), `API/calib.{h,c}` (new), `API/ekf.{h,c}` (new), `API/imu_update.c` (export `Lin_Acc_Z_body`, `Gravity_Body_*`), `TASK/StabilizerTask.c` (calibrator tick + cal_health bits), `TASK/send_data.c` (0x05 v14 frame + CMD 0x18), `Global_file/global_declare.h` (version bump), `docs/adr/0011-auto-imu-calibration.md`, `wiki/concepts/auto-imu-calibration.md` |
| Citations | transcripts `18c1dfa0` (initial design + grilling), `26fc2719` (4-phase restructure + sensor identification), `ff9e71e8` (build fixes + EKF replay), `3550d532` (sim scenarios wired) |
| Tests | 126/126 unit tests green. EKF replay on `flight_1784725604.csv` (~202 s, 40 324 OF ticks): v_body RMSE 0.014 m/s; b_a_x = +1.04 mg, b_a_y = −1.69 mg, b_a_z = 0, b_g ≈ 0 |
| **Status** | ✅ **Code complete & green. NEXT: real flight validation** to confirm Phase 3+4 calibrators land on the FC, then update ADR to "validated end-to-end" |
| Pending risks | Sensor identity was a Taobao-screenshot-derived confusion (`匿名` vs `无名`) — *resolved as Anonymous (匿名) 0xAA-header protocol*; old flight logs (v13) lack `of.lin_acc_x_mg`, so replay can't end-to-end validate v14 bias convergence yet |

### 1.2 Z-axis optical-flow noise mitigation — **🟡 Proposed, NOT implemented**

| What | Tighten the existing Z acceptance band at `TASK/StabilizerTask.c:281–308` (`of_alt_cm ∈ [5, 500] cm`, per-tick jump `< 0.10 m`, 20-tick force-resync) — add a median filter *before* the band gate, or tighten thresholds. |
|---|---|
| Why | Pilot sees "Z axis measurements suffering from sudden measurements that don't make sense" — likely rangefinder noise (laser or ultrasonic). |
| Citations | transcript `18c1dfa0` ("the z axis measurements are also suffering from some kind of measurement noise..."), `26fc2719` (Z-axis acceptance gate is already there) |
| **Status** | 🟡 **Decision pending.** Median-filter-before-gate vs. tighter-band only. Use sim replay (`flight_1784*.csv`) to validate before changing firmware. |

### 1.3 EKF-augmented MRAC (covariance-informed adaptation) — **🔵 Future work, thesis track**

| What | Replace the static `Γ_max` adaptive gain with a per-tick `Γ_eff(k) = Γ_max · diag(P_attitude(k)) / (diag(P_attitude(k)) + ε)` so adaptation slows when EKF is uncertain. Extend to multi-source trust (more sensors → smaller `P` diagonal → more trust). |
|---|---|
| Why | Active research area; aligns with user's thesis on adaptive-control trust metrics. Currently the v3 OF-bias estimator is a scalar Kalman filter; the 9-state EKF is already wired (feature 1.1); this connects them. |
| Citations | transcripts `18c1dfa0`, `26fc2719` (1.31 AM message: "exactly adaption should be guided by how much we trust the measurements"), ADR-0011 "Future work — thesis track" section |
| **Status** | 🔵 **ADR-recorded future work. NOT a near-term target.** Two literature citations to land in `wiki/literature/` are pending. |

### 1.4 EKF Q / R empirical tuning — **🟡 ADR-recorded "verify" item**

| What | Replace ADR-0011 defaults (`R_OF = 6.16e-4`, `R_acc = 0.005`, `R_z = 0.04`) with values empirically tuned from real flight-log replay on v14 firmware (after the first v14 flight lands). |
|---|---|
| Why | Defaults are reasonable starting points but real-sensor noise floor differs from sensor-to-sensor. |
| Citations | ADR-0011 validation step 2; transcript `ff9e71e8` (`b_a_x` residual analysis) |
| **Status** | 🟡 **Pending first v14 flight** — until then, defaults stay. |

### 1.5 SysID deferred safety gates — **🟡 Proposed (ADR-0004 items #2/#3)**

| What | Add to `sysid_abort_condition()`: battery-low (`bat_warn` symbol), telemetry/OF-stale, sustained-saturation aborts. Hard-zone boundary (±0.7 m → controlled descent), not just soft ±0.5 m → RECOVERY. |
|---|---|
| Why | Pre-SysID output-injection-ON flights need stronger gates. RC dead-man remains final authority. |
| Blocker | No clean `bat_warn` / `of_valid` symbols exist yet — thresholds need defining first. |
| Citations | `CLAUDE.md` "Known Remaining Issues" #2/#3; transcript `0bb296d5` (SysID safety discussion) |
| **Status** | 🟡 **Do before output-injection-ON SysID flights.** |

### 1.6 SysID Z-axis excitation — **🟡 Rejected for now (ADR-0004 #1)**

| What | `SYSID_AXIS_Z` is currently rejected in `SysID_Start`. Full Z excitation needs a `Z_ratePID.Des` injection site + its own altitude/ground-effect abort guards. |
|---|---|
| Citations | `CLAUDE.md` "Known Remaining Issues"; ADR-0004 item #1 |
| **Status** | 🟡 **Future work.** Not in current flight-test scope. |

### 1.7 ADR-0004 doc drift amendments — **🟢 Cosmetic (no code impact)**

| What | Amend ADR-0004: dec.7 says 200 Hz but firmware emits the 0x03 ID frame at 100 Hz; no separate `PRECHECK` FSM state (gates run synchronously in `SysID_Start`); manual abort is CMD `0x14` idx6 not `0x0D`. |
|---|---|
| **Status** | 🟢 **Amend ADR when convenient.** Functionally fine. |

### 1.8 RPM IR-sensor wiring (4 independent channels) — **✅ Done, but ADR note pending**

| What | Re-targeted `BSP/rpm.c/.h` to PA0/PA1/PC6/PC7 (originally PA5/PB3/PB10/PB11). Wrap `UART4_Configuration()` call in `#if 0` in `BSP.c` so PA0/PA1 stay clean for EXTI input. |
|---|---|
| Why | 4 IR sensors per motor for live RPM during flight — replaces motor bench-only RPM. |
| Files touched | `BSP/rpm.h`, `BSP/rpm.c`, `BSP/BSP.c` (`UART4_Configuration` wrapped), `TASK/stm32f4xx_it.c` (EXTI handlers rewritten) |
| Citations | transcript `b1360896` (full wiring walk-through: from "PA0/PA1/PC6/PC7 unused" → "UART4 is wired" → final design) |
| **Status** | ✅ **Code complete, build green, RPM measurements confirmed by Keil watch window.** Note: ADR-0010 (RPM bench acquisition) does not yet reflect the air-side wiring — minor doc drift. |
| Pending | Confirm with the user whether to keep UART4_Configuration `#if 0`'d or restore it once wiring is verified |

### 1.9 OF-hold lean-command sign-inversion fix — **✅ Fixed, needs v14 flight confirmation**

| What | `TASK/StabilizerTask.c:779-780` now negates both `locxsPID.U` and `locysPID.U` so positive velocity error produces correcting lean that opposes motion. |
|---|---|
| Why | Earlier flight (`flight_1784534170.csv`, OF-hold lunge) showed runaway: position loop asked for positive velocity, OF measurement went negative, controller commanded lean that *accelerated* motion. Positive feedback. |
| Citations | transcripts `7501e0ee` (root cause diagnosis), `df0a52b1` (handheld test confirms fix, drone flies great after) |
| **Status** | ✅ **Fixed.** Flight 1784538359 (next) showed oscillations traced to velocity-loop P-controller with `Ki=0 Kd=6.0` (pure D controller); gains retuned to `Kp=3.0 Ki=0.02 Kd=1.5` — see §1.10. |

### 1.10 Velocity-loop PID retune (flight_1784538359 oscillations) — **✅ Done**

| What | `API/pid.c:24-25` — velocity (`locxsPID`/`locysPID`): `Kp 3.0 → 3.0`, `Ki 0 → 0.02`, `Kd 6.0 → 1.5`. Same Kp, conservative I, halved D. |
|---|---|
| Why | Pure D controller (Ki=0) had no restoring force between OF sensor samples; Kd=6 amplified noise spikes into lean commands. |
| Citations | transcript `7501e0ee` (root cause: pure D controller); `docs/session_conclusions_2026-07-14.md` |
| **Status** | ✅ **Confirmed by next flight.** |

### 1.11 Pitch/roll/yaw rate-loop gains (PM=30° fix) — **✅ Done**

| What | `API/pid.c` retune: pitch/roll Kp 3.0→2.6, Kd 8.0→9.5; yaw Kp 6.0→6.5, Kd 0→1.5; h-rate Kd 0→1.5. |
|---|---|
| Why | Phase-margin 30° = CRITICAL (target >45°); recommendations from `flight_analysis` skill applied. |
| Citations | transcript `df0a52a1` (subagent analysis on `flight_1784538359_analysis/report.md`); `flight_analysis/cli.py` thresholds |
| **Status** | ✅ **Done; included in v13/v14 build.** |

### 1.12 MRAC adaptive-weight EEPROM persistence — **🔵 Deferred to future work**

| What | Persist MRAC adaptive weights across power-cycles (currently lost on every boot). |
|---|---|
| Why | Each cold-boot forces re-convergence; would be valuable for repeat flights. |
| Citations | `CLAUDE.md` "Known Remaining Issues" |
| **Status** | 🔵 **Future work.** Not started. |

### 1.13 Optical-flow XY drift fix — **🔵 Deferred**

| What | `locxPID.FB` / `locyPID.FB` drift ~50 cm over short flights. Expected OF-sensor behavior but worth tightening if possible. |
|---|---|
| Citations | `CLAUDE.md` "Known Remaining Issues" |
| **Status** | 🔵 **Future work.** No active proposal yet. |

### 1.14 Stick-neutral auto-calibration — **✅ Stashed**

| What | `s_neutral[]` averaged over 50 frames gated by `RC_NEUTRAL_WINDOW=200`. From `stash@{0}` commit `0d1c39b6` ("WIP: today's changes before rollback 2026-07-21"). |
|---|---|
| **Status** | 🟢 **Stashed, no conflict with SBUS parsing.** To be re-applied post-validation (transcript `0bb296d5`). |

### 1.15 GS_PROTO_VERSION drift — **🟡 Need to align**

| What | Working tree has `GS_PROTO_VERSION = 10U` (firmware) and `13U` (per stashed send_data.c). Bridge expects `10U`. ADC-0011 implementation bumped to `14U`. Three competing values. |
|---|---|
| Citations | transcripts `0bb296d5` (PHASE 1 verification), `b06b68a2` (initial framing: HEAD=10, stash=13, but per ADR-0011 implementation now at 14), `cb29de41` (smoke test shows firmware reports `proto_version=13` on live COM3) |
| **Status** | 🟡 **Resolve on next reflash.** The user is mid-test-flight with proto_version=13 working. Once reflash happens, both sides go to 14 (per ADR-0011). |

---

## 2. GUI (`ground_station/`) — proposed features

### 2.1 GUI rebuild / clone decision — **🟡 Decision pending**

| What | The user wants: "conveniant and efficient way to interface with my drone, allowing me to record data, run python scripts for analysis, generate plots for me to click and directly go to [source]. Also envisioned as the intermediaty control connection between pc and drone for running autonomous flights, parameter sweeps, like keil debug watch window for live parameter values and fast diagnosis, not limited by choosing a frame and sending limited amount [of variables]". |
|---|---|
| Options | **Option A (recommended):** Clone a mature GUI and customize. The hard parts (serial/UDP parsing, live-plot updating, frame layout) are framework-independent. **Option B:** Build from scratch on existing `dashboard.py` (DearPyGui). |
| Why | Building a full GCS from scratch is a 6–12 month project. Starting from a mature Qt/PyQt project months the development timeline. |
| Candidates | PyQt/PySide6 + PyQtGraph (recommended), QGroundControl fork (Qt/QML, heavy), Electron, Flask/SocketIO+Plotly |
| Citations | transcripts `18c1dfa0` (full GUI vision grilling), `ff9e71e8` (12:11 PM "in the following lets build the gui test harness"), `1a7cff88` (research report on GUI options, subagent recommendation) |
| **Status** | 🟡 **Decision pending.** User leaned "clone a mature GUI"; not yet committed to a specific source. |

### 2.2 GUI test harness — **🟡 Proposed, deferred to own session**

| What | Refactor `ground_station/gui/dashboard.py` so that command dispatch + serial parsing live in a pure module (e.g. `ground_station/gui/controller.py`). Add `pytest ground_station/gui/test_*.py` covering pure-logic regressions in <2 s. |
|---|---|
| Why | Currently every dashboard change requires a manual `dashboard.py` smoke test (start app, click button, watch for serial output). Wire-up regressions (like `CMD 0x18 force_recal` button going un-wired because there's no test surface) keep slipping through. |
| Anti-pattern to avoid | Don't try to test tkinter/DearPyGui widgets directly — that's a tar pit. Test the pure logic layer. |
| Citations | transcripts `18c1dfa0` (the question that surfaced it), `ff9e71e8` (high-leverage answer), `df0a52b1` (high-leverage answer restated) |
| **Status** | 🟡 **User agreed it would be useful. Separate session.** |

### 2.3 Keil-like Watch window — **🔵 Proposed, not started**

| What | Live variable inspector — pick any firmware-side variable by name, stream its value at high rate without firmware rebuild. Currently new variables require touching `send_data.c`, recompiling, flashing. |
|---|---|
| Why | Pilot (and AI agent) needs ad-hoc access to live memory values without a 5-minute flash cycle. Matches the user's vision of "keil debug watch window for live parameter values and fast diagnosis". |
| Implementation paths | (a) extend Frame 0x05 with a "watchlist" segment, or (b) define a new CMD that pulls named globals on demand, or (c) SWD/RTT channel (heavier). |
| Citations | transcript `18c1dfa0` (user vision at 4:23 PM: "it would be great if it was like keil debug watch window") |
| **Status** | 🔵 **Concept only.** Needs architectural design before coding. |

### 2.4 Protocol: Push vs Pull — **🔵 Architectural question**

| What | Today everything is push (firmware streams 4 fixed frames; bridge forwards; GUI consumes). Vision needs pull (GUI requests specific variables on demand). |
|---|---|
| Citations | transcript `18c1dfa0` (grill question 1, "Push vs. Pull") |
| **Status** | 🔵 **Architectural decision pending.** Strongly tied to §2.3. |

### 2.5 Parameter sweep + autonomous flight scripting — **🔵 Vision, not started**

| What | Run scripted autonomous flights and parameter sweeps from the GUI. Python scripts that drive the ground-station bridge to execute e.g. "sweep Kp from 2.0 to 4.0 in 0.2 steps, log responses". |
|---|---|
| Citations | transcript `18c1dfa0` user vision message |
| **Status** | 🔵 **Vision.** Blocked on §2.1 (which GUI framework) and §2.2 (test harness). |

### 2.6 Integrated analysis → plot → click-to-source workflow — **🔵 Vision**

| What | From any analysis plot (RMSE window, spectral peak, weight trajectory), click on a data point and jump to (a) the flight-log row, (b) the firmware code that produced it, (c) the ADR/decision that produced the algorithm. |
|---|---|
| Citations | transcript `18c1dfa0` user vision message |
| **Status** | 🔵 **Vision.** Heavy lift; not started. |

### 2.7 RPM live traces in dashboard — **🟡 Patches existing dashboard; small**

| What | Live RPM gauges for all 4 motors in the dashboard's motor bench tab + flight-mode monitor tab. RPM already in Frame 0x04 (bench) and Frame C 0x06 (flight). |
|---|---|
| Why | Visual confirmation of motor health during flight; complements the existing RPM data in `frame_c`. |
| Citations | transcript `df0a52b1` (RPM added to Frame C, dashboard tab to be updated) |
| **Status** | 🟡 **Easy follow-up; small.**

### 2.8 Updated Frame C plots (gyro + earth-position) — **🟡 Cosmetic**

| What | Once Frame C 0x06 is live, add live plots for `body.rol/pit/yaw` (deg), `body.gyro_x/y/z` (rad/s), `body.earth_x/y` (m), `body.altitude` (m). The plot machinery (`flight_analysis/`) already exists; just add to dashboard render loop. |
|---|---|
| Citations | transcript `df0a52b1` ("if you want live dashboard plots, those would be new additions but are not strictly required") |
| **Status** | 🟡 **Defer until v14 flight lands.** |

### 2.9 Stale-data guards on Frame B workspace — **🟢 Done (recent)**

| What | `_last_frame_b_t = 0.0` stale guard added so dashboard Frame B panel blanks out when frames stop arriving instead of showing garbage like -1e+33. |
|---|---|
| Why | Live capture showed Frame B decoding produced -1.503e+29 garbage when firmware emitted v13 layout but bridge expected v14. |
| Citations | transcript `cb29de41` (live probe at 8:40 PM, root cause diagnosis, fix applied directly to `serial_bridge.py`) |
| **Status** | ✅ **Done; verified live.** |

### 2.10 COM-port auto-detection (`AUTO` mode) — **✅ Done**

| What | `ground_station/config.yaml` `serial_port: AUTO`. Bridge scans COM ports, probes candidates, picks the one streaming telemetry at 115200 8N1. `--scan-com` CLI for diagnostic. |
|---|---|
| Why | Rainsun→DeveBox swap caused COM6 phantom; explicit "let bridge find the right COM" removes a class of fragile wiring issues. |
| Citations | transcript `cb29de41`, ADR-0007 |
| **Status** | ✅ **Live; resolves to COM3.** |

### 2.11 Frame B length-formula fix — **✅ Done**

| What | Corrected `_rx_loop` and `_unpack_frame_b` length formulas to match firmware's `4*max_num_basis + 24` (instead of incorrectly hardcoded `4*(8+2)+36`). |
|---|---|
| Citations | transcript `cb29de41` (live capture: firmware sends 298 B Frame B; bridge was rejecting all of them) |
| **Status** | ✅ **Done.** |

---

## 3. Cross-cutting / infrastructure

### 3.1 Skills parity (Claude Code ↔ Cursor) — **🟢 Done**

| What | Sync Claude Code skills to Cursor's skill loader, so a single skills directory covers both clients. |
|---|---|
| Citations | transcript `df0a52b1` ("i am planning to move to using cursor agents in the future and stop using claude code") |
| **Status** | ✅ **41 new skills synced** (2026-07-20); subagent report in transcript `df0a52b1`. |

### 3.2 ccc search DB exclude patterns — **✅ Done**

| What | Excluded `OBJ/**`, `Analysis_plots/**`, `ground_station/results/**`, `ground_station/logs/**`, `control-teaching/learning-records/**`, `control-teaching/reference/**`, `graphify-out/**` from `cocoindex_code` indexing. |
|---|---|
| Impact | 18 793 → 8 558 chunks (54% fewer); 9 699 → 189 JSON chunks (51× fewer); firmware C chunks preserved. |
| Citations | transcript `4822d847` |
| **Status** | ✅ **Done.** |

### 3.3 `ccc` daemon model loading / cold-start behavior — **🟢 Documented**

| What | ccc runs `sentence-transformers/all-MiniLM-L6-v2` (384-dim) on CUDA (`cuda:0`). Cold-start ~6 s; refresh-on-search adds another ~6 s. Set `refresh_index: false` for repeated queries on unchanged code. Path-filtering (`paths=`) bypasses vec0 ANN and does a SQL scan. |
| Citations | transcript `4822d847` |
| **Status** | ✅ **Documented.** |

### 3.4 Defensive build discipline (Rebuild-after-every-flash) — **🟢 Lesson logged**

| What | After a reflash in Keil, ALWAYS Project → Clean Target → Rebuild All Target Files. Otherwise stale `.o` files from a previous configuration can cause `s_cal_hot` / `s_cal_trim` undefined-symbol errors (transcript `ff9e71e8`). |
| Citations | transcript `ff9e71e8` (build-fix writeup); `CLAUDE.md` "Known Remaining Issues" → lessons.jsonl entry planned |
| **Status** | ✅ **Lesson logged; not formally written to lessons.jsonl yet.** |

### 3.5 Doc-skepticism discipline — **🟢 Lesson logged**

| What | Don't treat project docs and ADRs as ground truth. Cross-check with the live code; surface facts that need re-confirmation; raise them to user attention before assuming. |
| Citations | transcript `26fc2719` "you are a beginner" teaching moments, `18c1dfa0` cross-checks of Taobao screenshot vs firmware parser |
| **Status** | ✅ **Lesson logged.** |

### 3.6 Revert hygiene — **🟢 Lesson logged**

| What | Don't do back-and-forth bisection/revert loops. They hide bugs and break previously-working features. Branch from a known-good state; cherry-pick forward. |
| Citations | transcript `26fc2719` "i also experienced the problem of not a clean revertion of code to previous commited versions" |
| **Status** | ✅ **Lesson logged.** |

### 3.7 Paper-grab pipeline (Discord → `raw/papers/`) — **✅ Done**

| What | Discord `📥` reaction on digest messages writes a structured markdown artifact to `raw/papers/<date>-<slug>.md` with proper frontmatter (source, url, digest-date, channel, topic, signal), abstract, notes, and "Deep summary (grab pipeline)" section. |
| Citations | transcripts `fcc59020`, `530681f3` |
| **Status** | ✅ **Done; tested with L1-NMPC paper.** |

### 3.8 `flight_analysis` CLI + skill — **✅ Done**

| What | `flight_analysis/` Python package (oscillation, stability, parameter correlation, frame abstraction, expert diagnostics, reports). `/flight-analysis` skill. |
| Citations | commit `4c69cdf`; transcript `df0a52b1` |
| **Status** | ✅ **Done.** |

---

## 4. Open questions for next chat

1. **GUI framework decision** (§2.1) — clone mature Qt project vs. extend `dashboard.py`. User is leaning toward "clone a mature GUI" but hasn't picked a specific source. **This unblocks §2.2, §2.3, §2.4, §2.5, §2.6.**
2. **Reflash decision** (§1.15) — when to reflash to v14 (with all ADR-0011 changes). Currently bench is on v13 working.
3. **Sensor identity (匿名 vs 无名)** — resolved as Anonymous (匿名) 0xAA-header; no remaining decision.
4. **First v14 flight** (§1.1, §1.4) — needed to validate EKF/calibrator end-to-end with `lin_acc_x_mg` field present. Once flight logs accumulate, run `/flight-analysis` on them.
5. **Flight FSM ADR-0011 documentation update** — when first v14 flight validates Phase 3+4 in the air, ADR status moves from "implemented" to "validated end-to-end".
6. **Z-axis noise root cause** (§1.2) — median filter or tighter band? Need a sim replay against a flight log to compare.

---

## 5. How to use this document

- **Picking a feature to work on next?** Check the Status column. 🔵 = needs architectural design first. 🟡 = ready to implement. 🟢 = done. ✅ = in main/committed.
- **Tracing a feature's history?** Each row has Citations pointing to one or more transcript UUIDs in the `agent-transcripts/` folder. Read those transcripts to see the original conversation.
- **Verifying "did the previous agent claim this works"?** Each row has a Tests column where applicable. Run `python -m pytest sim/tests/ ground_station/comm/ -q` from the repo root for the 126-test baseline.
- **Adding a new feature?** Update this doc with the new row, Status=`🟡 proposed`, and reference the chat UUID where it was discussed.

---

## 6. Lessons / behavioral feedback from past sessions

From `CLAUDE.md` "Coding Behavior Guidelines" (Karpathy-derived) and feedback captured across transcripts:

1. **Surface confusion** — when uncertain, ask; don't silently pick. (Transcript `1648311b` caught a wrong-environment assumption early.)
2. **Simplicity first** — minimum code that solves the problem; nothing speculative. (Transcript `26fc2719` calibration FSMs are minimal, ~120 lines of C.)
3. **Surgical changes** — touch only what was asked; match existing style; every changed line traces to user's request.
4. **Goal-driven execution** — define verifiable success criteria; loop until verified. (EKF replay validation against `flight_1784*.csv` was a verifiable goal.)
5. **Manage context window** — read only what you need; don't re-read; summarize long outputs. (This handoff itself is a context-management artifact.)

---

## 7. File index (this handoff's inputs)

| Path | Purpose |
|---|---|
| `docs/handoffs/GUI_FIRMWARE_ROADMAP_2026-07-24.md` | This document |
| `docs/handoffs/HANDOFF_QUICK.md` | 1-page summary for fast scanning |
| `docs/handoffs/_transcript_extract.txt` | Filtered extract of all agent transcripts (546 KB) |
| `docs/handoffs/_extract_transcripts.py` | Script that produced the extract |
| `docs/adr/0011-auto-imu-calibration.md` | The auto-IMU-calibration contract (most-recent feature work) |
| `docs/decisions.md` | ADR-0007 (DeveBox swap) and earlier decisions |
| `docs/interfaces.md` | Telemetry protocol contract |
| `wiki/concepts/auto-imu-calibration.md` | Wiki entry for ADR-0011 |
| `CLAUDE.md` | Project-level rules and session state |
| `.agent_memory/lessons.jsonl` | Accumulated project lessons |
