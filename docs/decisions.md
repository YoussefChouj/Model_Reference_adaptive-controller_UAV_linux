# Architectural Decisions

## 2026-04-12: Multi-rate FreeRTOS Task Partitioning
- **Problem:** The firmware must run sensing, control, autonomy, and telemetry at different cadences without starving critical loops.
- **Options considered:** Single super-loop; interrupt-heavy design; dedicated periodic RTOS tasks.
- **Chosen:** Dedicated FreeRTOS tasks with fixed periods using `vTaskDelayUntil` (1000 Hz IMU sample/update, 200 Hz stabilizer/autofly, 100 Hz remoter/send, 1 Hz monitor).
- **Rationale:** Predictable loop timing and separation of responsibilities reduce coupling between fast control logic and slower communication paths. [VERIFY]
- **Files affected:** `USER/main.c`, `TASK/StabilizerTask.c`, `TASK/AutoflyTask.c`, `TASK/send_data.c`, `API/imu_update.c`.
- **Constraints created:** Task period constants and function-level `dt` assumptions must remain aligned (for example, 1 ms IMU update and 5 ms autopilot path integration).

## 2026-04-12: Lightweight Ground-Station Binary Protocol with XOR CRC
- **Problem:** Ground-station communication needs low overhead and simple parser logic on STM32.
- **Options considered:** Text protocol (CSV/JSON), framed protocol with heavy CRC, fixed sync + compact binary payload.
- **Chosen:** Sync-framed binary messages with XOR checksum.
- **Rationale:** XOR checksum plus fixed-byte framing is cheap on MCU and straightforward to validate in both firmware and Python bridge.
- **Files affected:** `TASK/send_data.c`, `BSP/usart4.c`, `BSP/usart5.c`, `ground_station/comm/serial_bridge.py`.
- **Constraints created:** Command and telemetry byte layouts and CRC coverage rules must match exactly across firmware and host parser.

## 2026-04-12: Virtual RC Gating by SBUS Loss and SDK Mode
- **Problem:** Host commands must not override active physical RC control in normal operation.
- **Options considered:** Always accept virtual sticks; separate mode with no SBUS dependency; gate virtual sticks by SBUS loss and SDK mode.
- **Chosen:** Accept CMD `0x06` virtual stick writes only when `sbus_lost == 1` and `FlyMode == FlyMode_SDK`.
- **Rationale:** Protects against mixed-authority control conflicts and keeps physical RC as primary authority when available. [VERIFY]
- **Files affected:** `TASK/send_data.c`, `TASK/StabilizerTask.c`, `Global_file/global_declare.h`, `BSP/usart4.c`, `BSP/usart5.c`.
- **Constraints created:** Stick vector ordering (`[thr, pit, rol, yaw]`) and neutral value (`3000`) become cross-module contracts.

## 2026-04-12: Single Active Path Arbitration
- **Problem:** Multiple path generators (TWC, sinusoid, circle) can conflict if enabled simultaneously.
- **Options considered:** Run all path modes concurrently; last-writer-wins behavior; explicit arbitration to keep one active mode.
- **Chosen:** `AutoflyTask_PathArbitrate` enforces one active path family at a time.
- **Rationale:** Prevents contradictory setpoint writers and simplifies safety reasoning for autonomous behavior.
- **Files affected:** `TASK/AutoflyTask.c`, `TASK/send_data.c`, `Global_file/global_declare.h`.
- **Constraints created:** Path activation flags must be mutually consistent, and abort logic must clear all path-active state.

## 2026-05-23: Mixed-Unit XY/Z Coordinate Contract
- **Problem:** `locxPID` and `locyPID` operate in centimetres; `Z_posPID` operates in metres. The TWC_arrived distance check combined these without conversion, causing the distance to be ~100× too large and TWC_arrived to never fire.
- **Options considered:** Convert all PIDs to metres; convert all PIDs to cm; leave internal units and add explicit conversions at every boundary.
- **Chosen:** Leave internal units unchanged. Add explicit ×0.01f conversion in `TWC_arrived` distance calculation. Add ×100 multiplier in ground station before sending XY targets. Add ÷100 in ground station before displaying XY.
- **Rationale:** PID gains (Kp=0.8, EMin=30 cm, vel saturation=120 cm/s) are tuned for cm. Changing internal units would require re-tuning all gains and invalidate flight logs.
- **Files affected:** `TASK/StabilizerTask.c` (distance calc), `ground_station/gui/dashboard.py` (send ×100, display ÷100).
- **Constraints created:** Every sender of CMD 0x0A index 0/1 must multiply by 100. Every display of locxPID/locyPID must divide by 100.

## 2026-05-23: UART RX Buffers Sized for Burst Coalescing
- **Problem:** Python serial bridge coalesces multiple rapid CMD writes into one OS-level burst. If burst > RXMB_LEN, the firmware USART_Receive() skips the mailbox copy → commands silently lost. Old RXMB_LEN was 50 bytes (5 frames). A burst of 6+ frames caused drops.
- **Options considered:** Slow down Python writes; increase buffer; add flow control.
- **Chosen:** Increase `UART4_RXDMA_LEN` and `UART4_RXMB_LEN` to 128 bytes. Replace single-frame parser with a loop-based multi-frame parser.
- **Rationale:** Flow control would require firmware-side handshaking. Slowing Python writes is fragile. Larger buffers with a robust parser are the simplest correct fix.
- **Files affected:** `BSP/usart4.h`, `BSP/usart4.c`.
- **Constraints created:** RXMB_LEN must be ≥ maximum expected burst size. Multi-frame parser assumes no partial frames span IDLE boundaries (safe given UART IDLE fires on line quiet).

## 2026-05-23: Z Setpoint Rate Limiter for Ceiling Safety
- **Problem:** When Execute TWC fires with a large Z target and the drone is on the ground, the full error is fed to the PID immediately → violent over-shoot → ceiling strike. Observed at 1.4 m target causing a 3 m ascent.
- **Options considered:** Reduce PID Kp; add integral windup limit; rate-limit the setpoint; add altitude cap.
- **Chosen:** Rate-limit `Z_posPID.Des` to ±0.005 m per control cycle (≈0.5 m/s max at 100 Hz) in `case_Update_height_Des`.
- **Rationale:** PID gain tuning trades off response vs. oscillation for all scenarios; a setpoint rate limiter caps only the maximum acceleration without affecting small-error behaviour. It is the minimal intrusion.
- **Files affected:** `TASK/StabilizerTask.c` (FLY branch of `case_Update_height_Des`).
- **Constraints created:** Maximum commanded climb/descent rate is now bounded by both the rate limiter and `gs_max_vertical_speed_mps`. Both limits are active simultaneously.

## 2026-05-23: Two-Phase TWC Safe Liftoff (Ground Station)
- **Problem:** Sending a high-Z TWC target from the ground caused the drone to attempt the full ascent in one step, exacerbated by optical-flow XY drift causing simultaneous XY excursion. Result: ceiling strike + crash.
- **Options considered:** Increase firmware rate limiter; add manual two-step UI; add automatic intermediate waypoint in software.
- **Chosen:** Ground station implements a two-phase sequence automatically: (1) ascend to 0.5 m, (2) wait 1 s at 0.5 m after TWC_arrived fires, (3) then send final XY/Z target.
- **Rationale:** The 0.5 m intermediate gives the closed-loop Z controller time to stabilize. The 1 s wait ensures horizontal drift has settled before XY setpoint is applied.
- **Files affected:** `ground_station/gui/dashboard.py` (`_twc_phase_update`, `_twc_arrive_time` state).
- **Constraints created:** TWC_arrived in firmware must correctly fire (unit contract above). The intermediate altitude (0.5 m) is hardcoded; if operational ceiling changes, this constant must be updated.

## 2026-05-23: SBUS Channel-Based Flight Mode Switch
- **Problem:** No mechanism existed to command a smooth landing or ground hold via the physical RC transmitter. Disarming mid-air via stick gesture caused instant motor cut.
- **Options considered:** Add GS button for landing mode; use SBUS auxiliary channels; implement velocity control for landing.
- **Chosen:** SBUS ch5 (3-position switch) → `drone_mode` global: 0=IDLE, 1=FLY, 2=LAND. SBUS ch8 (momentary) rising edge → `sbus_twc_trigger`. StabilizerTask reads both in `case_Update_height_Des`.
- **Rationale:** SBUS channels are already decoded at 100 Hz in RemoterTask. A 3-position switch for IDLE/FLY/LAND covers all in-flight mode transitions without requiring ground station connectivity.
- **Files affected:** `TASK/RemoterTask.h` (defines), `TASK/RemoterTask.c` (Check_Fly_Mode), `TASK/StabilizerTask.c` (mode branches), `Global_file/global_declare.h/.c` (drone_mode, sbus_twc_trigger).
- **Constraints created:** ch5 and ch8 must be physically assigned on the RC transmitter. ch10 remains the unconditional kill switch (sbus_channel[9] ≤ 500 → DANGEROUS_STOP), independent of drone_mode.

## 2026-07-23: FC Dongle Migration (Rainsun → ATK/DeveBox CH340) + Robust COM-Port Resolution
- **Problem:** Original Rainsun wireless UART bridge was retired. The replacement ATK/DeveBox CH340 dongle works electrically, but Windows enumerates it differently across replugs: yesterday the dongle came up as COM6 (then went phantom / CM_PROB_PHANTOM); after Device Manager "uninstall + remove driver" + replug it came up as COM3. Hard-coded `serial_port: COM6` in `ground_station/config.yaml` made the bridge fail silently on every COM drift. Driver-level recovery (`pnputil /disable`, `/enable`, `/restart-device`) returned ACCESS DENIED for the phantom.
- **Options considered:**
  1. Hard-code the new port (COM3). Works today; same class of failure the next time the user reboots, pairs a Bluetooth device, or changes USB hub.
  2. Document the swap and let the user edit `config.yaml` every time. No code change but pushes a recurring tax onto the operator.
  3. AUTO resolution: enumerate CH340 / CP210x / FTDI candidates, probe each at 115200 8N1, return the first that streams telemetry bytes within `com_probe_timeout_s`. Fall back to `serial_port_fallback` if no candidate streams.
- **Chosen:** Option 3 plus a one-shot PowerShell recovery script (`Recover-AtkComPort.ps1`) that diagnoses phantom / missing / healthy state and guides the operator through the only known working recovery (Device Manager → Uninstall + tick "remove driver" + physical replug). Add a `--scan-com` CLI flag for ad-hoc probing.
- **Rationale:** The dongle is electrically transparent to the firmware — the FC just sees USART3 with 115200 8N1. COM number drift is purely a Windows-host concern, so the fix belongs in the host bridge, not in firmware. AUTO resolution keeps the bridge usable across future port moves without operator edits. The PowerShell script documents the recovery path so the next operator doesn't need an interactive debugging session.
- **Files affected:** `ground_station/config.yaml` (new `serial_port: AUTO`, `serial_port_fallback`, `com_scan`, `com_probe_timeout_s`, `com_match_hints`), `ground_station/comm/serial_bridge.py` (new `_list_com_ports`, `_probe_port`, `scan_com_ports`, `resolve_serial_port`, `--scan-com` CLI flag; import `serial.tools.list_ports`), `ground_station/comm/Recover-AtkComPort.ps1` (new).
- **Constraints created:**
  - `serial_port` accepts the literal `AUTO` to enable probing; any other value is used verbatim (legacy behaviour preserved).
  - `serial_port_fallback` is the port the bridge opens when AUTO finds no live candidate, so the bridge fails loudly downstream (open / read error) instead of crashing at startup.
  - `com_scan` is a space-separated list, parsed by `_parse_simple_yaml`. Re-using the existing parser keeps the YAML dependency at zero.
  - `com_match_hints` filters the candidate set to known dongle-driver strings (CH340, CP210x, FTDI, USB-SERIAL). If no hint matches, all enumerated ports are probed (fallback).
  - Bridge firmware-side protocol is unchanged; this ADR is host-only.
  - Existing telemetry shows firmware reports `proto_version=13` while host expects 14 (pre-existing — see common-pitfalls drift). Not addressed by this ADR; will require separate firmware / bridge alignment work.

## 2026-08-05: Sim↔Firmware Parity Drift on `What_lower_limit` (spec `prior-00b`)

- **Problem:** `sim/adaptive_law.py` carried a stale comment and wrong default for
  `What_lower_limit`. The module docstring said "firmware never sets it → 0", and
  `AxisAdaptiveConfig.for_axis()` returned `[0.0] * 6` for all axes. The firmware
  (`API/mrac.c:353-355`) had actually set slot 0 to `-What_limit[0]` for pitch/roll/yaw
  in a partial asymmetric fix, but the comment and default were never updated. This
  is the defect class ADR-0006 and `mbd_workflow/README.md` exist to prevent.
- **Duration of drift:** Unknown — not dated, but the firmware fix dates from mid-2026
  (comments reference 2026-06-18 SysID work); the sim comment predates it.
- **Files affected:** `sim/adaptive_law.py` (`What_lower_limit` default and per-axis
  values), `sim/tests/test_adaptive_law.py` (parity assertions), `sim/README.md`
  (Phase-1 findings note).
- **Evidence:** `prior-00-sign-gate` (spec) confirmed firmware state from source.
  `prior-00b-sim-parity-fix` confirmed the sim was stale. Before/after re-run on
  `disturbance_rejection` (roll/pitch/yaw) showed the bias weight correctly goes
  negative in the new sim (θ₀ ≈ −0.002 roll/pitch, −0.004 yaw) vs pinned at 0
  in the old sim, and RMSE improves ~2–3%. The effect is real but modest — `e_deadzone`
  remains the dominant adaptation suppressor.
- **Prevention:** New parity test `test_for_axis_matches_firmware_init_gains` asserts
  the exact per-axis table from `mrac.c:353-355`. Any future drift on these values
  will be caught by `pytest sim/tests/test_adaptive_law.py`.
- **Chosen fix:** Restore correct firmware parity in `sim/adaptive_law.py` for_axis(),
  correct the docstring, add the parity test. No firmware change (firmware is correct).
  Slots 1–5 remain locked at 0 — unlocking them is the open Sweep A research question
  and requires evidence plus a flight-safety argument.
- **Constraints created:** `for_axis()` is now the only sanctioned constructor path for
  `AxisAdaptiveConfig`. Bare construction bypasses the per-axis values and gets the
  all-zeros default; callers must use `for_axis()` to get parity. The `z` axis
  explicitly sets `What_lower_limit = [0.0] * 6` with a comment matching firmware.

## 2026-08-05: ADR-0012 — Retire Gazebo; MuJoCo + the plant ladder (accepted)

- **Topic:** Sim-to-real weight transfer needs *gain* fidelity, not visual/contact fidelity; MuJoCo replaces Gazebo behind the existing `Plant` seam (`MujocoPlant`), `RigidBodyPlant` is retained as the oracle, four-rung ladder (`IdentifiedPlant → MujocoPlant → RigPlant → free flight`).
- **Full text:** [docs/adr/0012-retire-gazebo-mujoco-plant-ladder.md](adr/0012-retire-gazebo-mujoco-plant-ladder.md).
- **Status:** Accepted. Amends ADR-0006 D6; supersedes Gazebo half of spec 4b/4c.

## 2026-08-05: ADR-0013 — Scenario-conditioned adaptive priors (proposed)

- **Topic:** Learn `Theta` priors per scenario in simulation, inject at runtime via three orthogonal channels (value / authority / envelope); the σ-mod attractor is the primary value channel; a soft-attention detector is the leading indexing candidate.
- **Full text:** [docs/adr/0013-scenario-conditioned-adaptive-priors.md](adr/0013-scenario-conditioned-adaptive-priors.md).
- **Status:** Proposed. Architecture accepted; mechanisms left open.

## 2026-08-05: ADR-0014 — Dimensionless priors and declared regressor variants (proposed)

- **Topic:** Redefine the prior as a dimensionless object `Theta_tilde` so scenarios — not airframes — are the unit of transfer; declare per-basis normalisation scales as data; randomise over an airframe ensemble; the headline experiment is cross-plant prior damage.
- **Full text:** [docs/adr/0014-dimensionless-priors-and-declared-regressor-variants.md](adr/0014-dimensionless-priors-and-declared-regressor-variants.md).
- **Status:** Proposed. Refines ADR-0012 D8.

## 2026-08-10: prior-E-docs slice — HELD novelty-framing carve-out (ADR-0012 / 0013 / 0014)

- **Scope:** This doc-integration slice (spec `prior-E-docs`) deliberately excludes the **novelty-framing claims** that the three ADRs marked "HELD, 2026-08-06" following the literature review.
- **What is excluded from this slice:**
  - The "no published analogue" claims for soft attention + σ-mod attractor + mismatched-prior damage (ADR-0013 Context / Open questions).
  - The "no published analogue" claim for dimensionless transfer of MRAC weights (ADR-0014 Context).
- **What is included:** every **engineering decision** in D1–D8 stands; the eight engineering decisions and their `Chosen fix` / `Constraints created` content are the project-of-record. Only the contribution claim (Context / Consequences framing) is held.
- **Reason:** The author has not yet read the primary sources (Chowdhary ICRA 2013, Girard *Mathematics* 2024, Neural-Fly 2022, FAMLE IROS 2020, CDC 2010 + ICL 2019). Resolving framing requires a dedicated grilling session against those papers.
- **Reading path to resolve the held claims:** [docs/literature-review-findings/SYNTHESIS.md §7](literature-review-findings/SYNTHESIS.md).
- **Until resolved:** downstreams citing these ADRs should cite the **engineering decisions** (numbered D-numbers) and avoid the held contribution claims in their own write-ups.