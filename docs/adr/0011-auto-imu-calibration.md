# ADR-0011: Automatic four-phase IMU calibration (cold + air-trim + hot), 9-state EKF parallel path, manual button removed

Date: 2026-07-22
Status: Implemented (firmware + sim + ground station; v14 telemetry landed 2026-07-23; build green 2026-07-23)
Deciders: pilot, architect
Revision: 2026-07-23 — added `CAL_AIRBORNE_HOVER_TRIM` phase (angled surfaces), 9-state EKF as flag-gated parallel path, trust-measured adaptation as thesis-track future work. **2026-07-23 implementation revision:** Phase 1+2 already in firmware (`IMU_EstimatorReady`, `IMU_READY_TIMEOUT=30 s`); Phase 3+4 added in `API/calib.c` + `TASK/StabilizerTask.c`; 9-state EKF ported in `API/ekf.c`; 0x05 telemetry frame grew 39→53 B (v14) / 73 B with `EKF_TELEM_ENABLED`; `CMD 0x18 force_recal` added; `GS_PROTO_VERSION` 13→14.

### Build-fix log (2026-07-23 session)

| # | Error | Fix | File |
|---|---|---|---|
| 1 | `L6218E: Undefined symbol Ekf9_Init`, `Ekf9_Predict`, `Ekf9_Update*`, `s_cal_hot`, `s_cal_trim` (9 symbols) | Add `ekf.c` + `calib.c` to API file group in uVision project | `USER/JX_FLY.uvprojx` |
| 2 | `L6218E: Undefined symbol s_cal_hot`, `s_cal_trim` (2 symbols) | Remove `static` from `s_cal_trim` / `s_cal_hot` definitions in `StabilizerTask.c` — they are extern'd by `send_data.c` for the v14 telemetry surface | `TASK/StabilizerTask.c` |

**Result:** 0 errors, 69 warnings (all pre-existing: asm register hints, missing newlines, dead code). Build green.

## Context

`docs/session_conclusions_2026-07-14.md` (previous session) identified three stacked sources of the residual ~3° pitch trim observed in free flight after the IMU swap: (a) IMU pitch calibration bias **+1.3°**, (b) pitch stick not centered **+0.8°**, (c) CG / thrust imbalance **+1.4°**. The agent in that session proposed fixing (a) via a manual `CMD` button press — a solution the pilot does not accept as the **permanent** answer:

1. Manual calibration depends on the pilot remembering to do it before every flight.
2. A bias that drifts with temperature (confirmed in `docs/tracking_baseline_and_drift.md` v1/v2 history: OF bias climbs ~13 % over 13 min) requires a runtime mechanism, not a one-shot at boot.
3. Frame-line disclosure only treats symptoms; the architectural gap is that **calibration should be a property of the flight state machine**, not a separate command.
4. Advanced drones (PX4, ArduPilot, DJI A3, Autel, Skydio) can lift off from **angled surfaces** without baking the tilt into the accelerometer offset. Our ground-only cold cal cannot do this — if the surface is tilted +1.3°, baking it into `b_a` produces a drone that flies tilted.

This ADR replaces the manual trigger with an automatic, state-aware estimator that runs:

- A bounded **cold-cal phase** at every power-on / boot (max 30 s, blocks arming). **Gyro bias only** — the accelerometer is not yet trusted because the surface may be tilted (this is the explicit trade-off from session 2026-07-23 grilling).
- An **airborne hover-trim phase** (5–10 s, runs on first stable hover after takeoff) that estimates `accel_bias` using the now-observable gravity vector in world frame. This handles angled surfaces.
- A **hot-cal phase** during in-flight quiescence (low-rate, gated by stick center + gyro stillness), covering gyro bias only, gated against any translational disturbance.

Two parallel estimators exist after this ADR lands:

- The **PI drift corrector** in `IMU_Update_Mahony` (unchanged — the existing safety net).
- A new **9-state EKF in body frame** (`API/ekf.c`, gated by `EKFCFG.active` config flag), running at 1 kHz alongside Mahony. Side-by-side comparison is the validation mode; on-flag-on, the EKF output is exposed for telemetry but does not replace Mahony's integrator until validated.

The historical manual button (`CMD 0x10`) keeps existing for SysID init but is renamed to "Reset World Origin (debug)" in the dashboard.

### Established practice (literature review)

| Stack | Cold (boot/power-on) | Air-trim (first hover) | Hot (steady hover) |
| --- | --- | --- | --- |
| PX4 | Auto gyro+accel cal at boot (vehicle-still detector, `CAL_GYRO0`, `CAL_ACCEL0`). Explicit user "mag+level" step in QGC for full accuracy. Gyro bias only updated while `CAL_GYRO_PHI` (stddev of rotation rate) is below a gate. | `COM_DISARM_PRFLT` + `COM_INAIR_PREFLT` flags — preflight in-air accel trim runs automatically when first hovering. | EKF2 in-flight updates `accel_bias[xyz]` from GPS-aided, low-innovation phases only. Gyro bias **frozen** in flight. (`EKF2::controlFusionModes()` / `setAccelBias()`.) |
| ArduPilot | `INS_GYRO_RATE` & `INS_GYRO_CAL` auto-bias every boot against a vehicle-still detector; EKF3 perturbs `ACCEL_BIAS` continuously, bounded by `EK3_ACC_BIAS_LIM`. | `INS_TRIM_AUTO` — automatic accel trim on takeoff if enabled. | Gyro bias drift updated in-flight during quiescence; accelerometer bias **never** updated in flight in classic EKF3 (3.x: relaxed this). (`EKF3::CorrectIMU()`.) |
| Betaflight | Average ~1 s of gyroscopes with zero throttle command at arm. No accel cal in flight. | None. | None in flight — drift tolerated by high loop rate. |

**Consensus:** cold (always), air-trim (industry-standard, handles tilted surfaces), hot (gyro only during quiescence). Our design matches this.

## Decision

Replace `CMD 0x10` semantics with a state-owned estimator. Four phases:

### Phase 1 — `CAL_BOOT` (≤5 s, automatic, runs every power-on)
- Reuses the existing Mahony fast-converge window `IMU_FAST_WINDOW = 10 s` decayed across `IMU_KP_BOOST`/`IMU_KI_BOOST`.
- Convergence metric: `s_innov_lpf` (LP-filtered cross-product innovation energy `|e|²`).
- No new estimator. Output: attitude estimate roughly aligned to gravity.

### Phase 2 — `CAL_COLD` (≤30 s, automatic, blocks arm) — gyro bias only
- Begins after `CAL_BOOT` completes and `IMU_EstimatorReady()` fires.
- **Gyro bias only** via the existing Mahony integrator (`exInt`/`eyInt`/`ezInt`) which already does the right thing.
- **Accel bias intentionally not estimated here.** The surface may be tilted (legs crash-bent, takeoff from a slope). Baking that tilt into `b_a` would produce a flying-tilted drone. Pin OF world origin to zero at `IMU_EstimatorReady()` rising edge via `Reset_World_Origin()` (existing helper, `TASK/StabilizerTask.c:105`).
- Settled detector: `s_innov_lpf < IMU_SETTLE_E2` for ≥ 1 s after the window closes. **Abort-to-best-so-far** on timeout (pilot choice from grill round 1): keep the best residual, arm still unlocks, telemetry bit `COLD_DEGRADED` is set.
- Existing `IMU_EstimatorReady()` becomes the **single pre-arm gate**.
- **Optional, non-mandatory:** the rotate-180° bench test from `docs/session_conclusions_2026-07-14.md` §3 is documented in `docs/drone_control_guide.md` as a one-time diagnostic. Not a firmware gate; not part of the cold-cal flow. The pilot opted not to make this recurring because the drone crashes frequently.

### Phase 3 — `CAL_AIRBORNE_HOVER_TRIM` (5–10 s, automatic, in FLYING phase, once per session)
- Triggered on transition to `FLIGHT_PHASE_FLYING` + altitude > 0.3 m + sticks-centered for ≥ 0.5 s.
- Runs an **accel-offset least-squares estimator** using the gravity vector now observable in world frame (vehicle is stable in hover, so the only constant acceleration the accel sees is gravity):
 - Cost: `||  g·R(q(θ)) + b_a − a_meas  ||²` minimized for `b_a ∈ ℝ³`.
 - Closed-form update: `b_a ← b_a + μ · (g_ref − ĝ_meas)` with `μ = 0.02` (small, slow convergence).
 - Settled condition: `|g_ref − ĝ_meas| < 5 mg` for 1 s.
 - On settled: write `b_a` to `acc_offset[3]` exported by `API/imu_update.c`, set `cal_health.AIRBORNE_OK`.
- Failure mode: if the window expires (drone bumped, wind, pilot took control), abort to best-so-far, surface `cal_health.AIRBORNE_DEGRADED` and continue flight. **No retry until next session.**
- 9-state EKF (when `EKFCFG.active == 1`) supersedes the closed-form LS estimator — its 9-state coupling handles this naturally.

### Phase 4 — `CAL_HOT_HOVER` / `CAL_HOT_HOLD` (in-flight, automatic, opt-in via gates)
Reuses the v3 OF-bias quiescence-gated logic in `TASK/StabilizerTask.c:46-143` and generalises the same finite-state machine for the **gyro** axis only:

| State | Condition | Action |
| --- | --- | --- |
| `WAIT_STILL` | `|Gyro|_x_y_z < HOT_HOVER_STILL_THRESH` AND `!RCInput_IsActive(PITCH/ROLL/THR/YAW)` AND `flight_phase == FLYING` | count to `HOT_HOVER_STILL_TICKS` |
| `ACCUM` | still in WAIT_STILL gate | integrate gyro samples over `HOT_HOVER_ACC_TICKS` |
| `COMMIT` | full window with no break | `b_g ← (1−α)·b_g + α·sample_mean` with `α = 1e-4` |

- **Translational guard.** Before entering `ACCUM`, require `|of2_dx_fix| + |of2_dy_fix| < TRANSL_THRESH` AND `|lin_acc_X_body| + |lin_acc_Y_body| < LIN_ACC_THRESH` over the still-tick window — same idea as "pilot is hovering, not just sitting still on the ground" so the gravity reference isn't perturbed by horizontal motion artefacts.
- `FlightPhase_t::FLYING` only: in `LANDING` / `LANDED` / `GROUND_IDLE` the hot-cal filter is frozen (literal frozen bias).
- **Hot cal never updates `accel_bias`** (already estimated in Phase 3).
- **Hot cal may update `gyro_bias`** (drives the `exInt`/`eyInt`/`ezInt` integral terms per existing Mahony code path).
- `cal_health` telemetry bit `HOT_REJECTED` is set whenever `WAIT_STILL` resets mid-window with a counted reason (stick-driven, OF drift, translational guard fired).

### Parallel estimator — 9-state body-frame EKF (`API/ekf.c`, gated by `EKFCFG.active`)

State vector `[v_body[3], b_a_body[3], b_g_body[3]]` — 9 states. Body-frame choice is the right one for this hardware:

- **Body-frame biases are sensor properties** (do not rotate with the vehicle), so the math decouples and the EKF converges faster.
- **Earth-frame "biases" are disturbances** (wind, off-CG torques), not state variables — they belong as process noise `Q`, not as Kalman states. The MRAC is the right tool for those.
- **PX4's hybrid ESKF is more elegant but requires ~50 tunable parameters.** Body-frame 9-state gives 80 % of the benefit with 20 % of the code; the ESKF upgrade is a post-thesis item.

Compute budget: ~80 µs/call at 1 kHz on STM32F4. Feasible. Fixed-step required.

`Q` (process noise) is initialized to match the existing Mahony integrator's behavior (so when the EKF is on but unused, the output matches Mahony to within numerical noise):

| State | Initial Q | Source |
| --- | --- | --- |
| `v_body` | `1e-3 m²/s³` (process noise per axis, scaled by dt² in the predict step) | matched to current PID response |
| `b_a_body` | `1e-6 m²/s⁵` | from BMI088 accel bias stability datasheet (~3 mg over 1 hour typical) |
| `b_g_body` | `5e-9 rad²/s³` | from BMI088 gyro bias stability datasheet (~5 deg/hr typical) |

`R` (measurement noise) is initialized to match the existing OF-bias v3 estimator's effective measurement variance:

| Sensor | R | Source |
| --- | --- | --- |
| `of2_dx_fix`, `of2_dy_fix` | `R_OF = X² · var_of2 ≈ 0.0124² · 4 raw² ≈ 6.16e-4 m²/s²` | from `tracking_baseline_and_drift.md` Scenario 1 measurement |
| `Lin_Acc_X_body`, `Lin_Acc_Y_body` | `R_acc = var_lin_acc ≈ 0.005 m²/s⁴` (gravity-removed, low noise) | from `flight_1783845799.csv` ground session |
| `Z_rate` (baro or OF alt derivative) | `R_z = var_z_rate ≈ 0.04 m²/s²` | typical from existing 0x05 frame |

Side-by-side activation: when `EKFCFG.active == 0`, the EKF does not run (zero compute). When `EKFCFG.active == 1`, the EKF runs but **does not feed Mahony**; instead, its outputs (`v_body`, `b_a_body`, `b_g_body`, plus the per-axis `P` diagonal and `NIS`) are streamed in the `0x05` OF-calibration frame for offline replay comparison against the PI corrector. Only after a documented validation cycle (replay logs, then bench, then tethered, then free) does a separate decision gate the EKF output into the control loop. This is the "side-by-side" choice from grill round 1.

### Manual `CMD 0x10` — kept but renamed
- Stays callable for **SysID init** (`dashboard.py:3435` keeps sending it before each SysID run).
- Renamed to "Reset World Origin (debug)" in the dashboard; hover tooltip warns "Auto-cal owns normal flow; this button is for SysID init only."
- A new `CMD 0x18 force_recal` (idx 0) → from `GROUND_IDLE` only, re-enters `CAL_COLD` from the top. **Disarmed + GROUND_IDLE only**; refused if armed or in flight, refused if `FlightPhase_t::FLYING` ever observed before disarm.

### Telemetry surface (frames already in the project)
- New `cal_health` flags in Frame `0x01` (status byte 5–6): `0x01 BOOT_OK | 0x02 COLD_OK | 0x04 COLD_DEGRADED | 0x08 AIRBORNE_OK | 0x10 AIRBORNE_DEGRADED | 0x20 HOT_HOVER_OK | 0x40 HOT_REJECTED | 0x80 MANUAL_ORIGIN_RESET | 0x100 BOOT_TIMEOUT | 0x200 ESTIMATOR_READY`.
- Append `acc_bias[3]` (`s16`, mg) and `gyro_bias[3]` (`s16`, ×1e-4 rad/s) to the existing `0x05` OF-calibration frame.
- Append EKF outputs (when active): `v_body[3]` (s16, mm/s), `P_diag[3]` (s16, scaled), `NIS` (s16, ×1000), `kalman_gain[3]` (s16, ×1000) — 16 bytes total.
- Bumps `GS_PROTO_VERSION` v13 → v14.

## Consequences

### Positive
- The pilot can power on, wait ≤30 s, and arm — no manual steps, no `CMD 0x10` race with the SDK arming gesture.
- The drone can lift off from angled surfaces because `accel_bias` is not estimated on the ground; it converges in the air during Phase 3 (5–10 s after first stable hover).
- Hot-cal closes the residual steady drift observed in v1 (bench-fixed, single-shot) and v2 (climbing-bias) by re-applying the v3 "refresh, don't freeze" pattern to gyro bias.
- The 9-state EKF runs in parallel and provides **trust-measured data** for future EKF-augmented MRAC (thesis-track section below). No control-loop change today; pure telemetry + offline validation.
- Existing `IMU_EstimatorReady()` gate means the existing `flight_fsm.c:40` arm check continues to work with no FSM code changes.
- The 5-s air-trim phase is **bounded** so the drone never sits in trim mode — even on a worst-case aborted trim, the flight continues with best-so-far and a `DEGRADED` flag.

### Negative
- Cold phase is a hard 30 s block on arming — pilot has to wait longer than today. Mitigated by clear telemetry `cal_phase` progress %. PX4 ships similarly long "pre-arm checks" so this is standard.
- Hot-cal may temporarily perturb the integrator if the drone gently rocks; the translational guard prevents this. Closing the bias window during flight with `α=1e-4` is the same magnitude as the existing v3 OF bias estimator, which is shown to be safe.
- The 9-state EKF adds ~80 µs of CPU load on the 1 kHz IMU task. Marginal — to be measured.
- The 5–10 s air-trim phase means the drone has a slight in-flight settling period on first hover each session. PX4/ArduPilot do the same; pilots accept it.
- If cold cal can't converge in 30 s (vibration bench), we use best-so-far and arm. **Deliberate departure** from PX4/ArduPilot (which refuse arm). Documented, called out to reviewer.

### Constraints created
- The cold-cal path **must** finish before `IMU_EstimatorReady()` returns 1. Both code paths share the existing `s_settled` flag, so the new "30 s budget" is just an upper bound on the existing detector — no new state.
- `CAL_AIRBORNE_HOVER_TRIM` **must** run only in `FLIGHT_PHASE_FLYING` with `|Gyro| < HOT_HOVER_STILL_THRESH` for 0.5 s before activation.
- Hot-cal `WAIT_STILL` requires `flight_phase == FLIGHT_PHASE_FLYING`; freeze on `LANDING` / `LANDED` / `GROUND_IDLE`. Stated explicitly in `TASK/StabilizerTask.c`.
- Hot-cal **never** updates `accel_bias`. `API/imu_update.c` gains a unit test asserting this (or a `// DO NOT REMOVE` comment on the relevant branch).
- The 9-state EKF **never** feeds Mahony when `EKFCFG.active == 1` for the first validation cycle. Only after offline replay + bench + tethered + free-flight validation does a separate decision gate it in.
- All dashboards that depend on `cal_health` (existing dashboard + SysID dashboard) must update the version flag simultaneously — protocol bump.
- Manual `CMD 0x10` stays callable for SysID init but is **not** a flight-assist command. New `CMD 0x18` rejects any caller that isn't `GROUND_IDLE`.

## Future work — thesis track

### Trust-measured adaptation (EKF-augmented MRAC)
Once the 9-state EKF's covariance matrix `P` is validated against flight data, the MRAC law in `API/mrac.c` is extended to consume the EKF's posterior covariance directly:

```
Γ_eff(k) = Γ_max · diag(P_attitude(k)) / (diag(P_attitude(k)) + ε)
```

Interpretation: when the EKF is confident (small `P`), `Γ_eff → Γ_max` (full adaptation); when uncertain (large `P`, model disagrees with measurements), `Γ_eff → 0` (no adaptation because we don't trust the data driving it).

This is the principled version of "adapt when measurements are trustworthy." Concrete citations to add to `wiki/literature/`:
- **Yucelen & Johnson**, "Actuator Command Limiting and Bias Correction for Adaptive Control" — the original σ-mod line.
- **Yucelen et al.**, "Composite Model Reference Adaptive Control" — the closest precedent to "trust-measured adaptation."

Each new measurement source (OF → GPS → baro → vision) **mechanically reduces** the corresponding `P` diagonal through the Kalman update step, which raises `Γ_eff` automatically. So "more sources = more trust" is a property of the architecture, not a knob.

### Body-frame → error-state Kalman (ESKF) upgrade
If/when you add GPS and want to push the firmware to PX4-class sensor fusion, the body-frame 9-state EKF is the natural foundation for a 15-state ESKF (`[δθ (3), δv (3), δp (3), δb_a (3), δb_g (3)]`). Interface doesn't change; only the predict step and covariance reset need new code. Post-thesis scope; today's 9-state ships first.

## Alternatives considered

- **Keep the manual button as the only path.** Rejected: pilot explicitly rejected, and it doesn't fix the warmup drift (v2 history).
- **Estimate accel bias on the ground in cold-cal.** Rejected in the 2026-07-23 grilling — angled surfaces would bake tilt into `b_a`. Replaced with Phase 3 in-flight trim.
- **Run cold cal with the existing fast-converge boost always-on instead of decaying it.** Rejected: existing boost is intentionally aggressive to walk out the cold→warm gyro-bias shift; keeping it on permanently causes attitude to over-track short-term vibration.
- **Use only `s_innov_lpf` for cold cal (no accel step).** This was the previous-session proposal — landed as Phase 1 + Phase 2 (gyro only). Replaced because we now know surface tilt can fool the cold-cal accel step. The accel step moved to Phase 3.
- **Force arm refusal on cold-cal timeout.** Rejected by pilot choice "abort → best-so-far + warn". Documented as a deviation.
- **Update accel bias in hot phase too.** Rejected per PX4/ArduPilot precedent — gravity reference perturbation produces a slow tilt (the exact bug we are fixing).
- **Full PX4-style 15-state ESKF on day one.** Rejected: 50 tunable parameters vs. ~10 in 9-state body-frame; insufficient sensor sources to constrain 15 states (OF + IMU is one velocity channel). Post-thesis scope.
- **Earth-frame biases instead of body-frame.** Rejected: yaw couples earth-frame biases to velocity state, harder to identify. Body-frame matches Mahony (which is implicitly body-frame via `exInt/eyInt/ezInt`) and matches the literature.

## Implementation outline (not in this ADR)

| File | Change |
| --- | --- |
| `API/imu_update.c` | Promote `s_settled` to be gated by a budget-clock; export cold-cal `gyro_bias[3]` from `exInt/eyInt/ezInt`. (Accel bias exported via Phase 3, not Phase 2.) |
| `API/ekf.c` (NEW) | 9-state body-frame EKF. Q/R initialized per table above. Streams NIS, P_diag, gains in `0x05`. |
| `API/flight_fsm.h` / `.c` | Add `CAL_PHASE_t` enum (`BOOT`/`COLD`/`READY`/`DEGRADED`/`AIRBORNE_TRIM`/`HOT_HOVER`/`HOT_REJECTED`) on `flight_phase`. Hold in `CAL_COLD` until `IMU_EstimatorReady()` or 30-s budget expires. |
| `API/flight_fsm.c` (line 40) | Replace `if (... && IMU_EstimatorReady())` with `if (... && (IMU_EstimatorReady() || imu_cold_budget_expired_with_best))` (best-so-far fallback). |
| `TASK/StabilizerTask.c` (`Reset_World_Origin`) | Hook the rising edge of `IMU_EstimatorReady()` so cold cal auto-pins origin. Add `CAL_AIRBORNE_HOVER_TRIM` and `CAL_HOT_HOVER` FSMs mirroring `OF_BIAS_*` (lines 46–143). |
| `TASK/send_data.c` | Add `CMD 0x18 force_recal` (GROUND_IDLE only); rename `CMD 0x10` semantics comment; append EKF fields to `0x05` frame. |
| `ground_station/gui/dashboard.py` | Rename "Reset World Origin" buttons to "Reset World Origin (debug)" with tooltip; surface `cal_health` flags; add EKF active toggle. |
| `ground_station/comm/serial_bridge.py` | Add `CMD 0x18`; bump `GS_PROTO_VERSION` v13 → v14. |
| `docs/architecture.md` | Add `CAL_*` to the state diagram. |
| `docs/drone_control_guide.md` | Document the optional rotate-180° bench test (non-mandatory). |

### Validation plan (offline first, then bench, then flight — no skipped steps)
1. **Sim rebuild reuse:** `sim/` package's `plant.py` reference model already accepts a bias injection; add "cold + air-trim" mode to a new scenario and verify it removes injected bias.
2. **Replay tests:** replay `flight_1783845799.csv` (Scenario 1, ±1 m slides, both axes ground truth known) and `flight_1783831920.csv` (rigid mount, 13-min thermal drift) through both the PI estimator and the new 9-state EKF offline. Assert EKF residual < PI baseline by ≥30 %.
3. **Bench unit test, disarmed, motors off:** confirm cold cal reaches `READY` in <30 s.
4. **Bench unit test, motors off, gentle tap:** confirm `HOT_REJECTED` flag fires.
5. **Tethered hover, 30 s:** confirm `AIRBORNE_OK` fires during sticks-centered window and `HOT_HOVER_OK` follows.
6. **Angled-surface takeoff (deliberately tilted ±10°):** confirm the drone lifts off level within 5–10 s of stable hover (Phase 3 trim converges).
7. **Free flight (only after steps 1–6):** 5-min hover, log `cal_health` flags + `acc_bias[3]` + `gyro_bias[3]` + EKF `NIS`/`P_diag`. Compare EKF vs PI in offline replay.

### Sensor factory information — *requested from pilot*
To pin the EKF's `Q`/`R` defaults to datasheet-grade values rather than educated guesses, the pilot will share:
- BMI088 datasheet (accel & gyro noise density, bias stability specs, self-test register behavior).
- Optical-flow sensor datasheet (variants under consideration: PMW3901, PMW3360). Integration time per frame, pixel clock, scale factor — these resolve the unknown `X` from `tracking_baseline_and_drift.md` and let us derive `R_OF` numerically.
- Altimeter datasheet (Lidar Lite / VL53L0X / ultrasonic — whichever is wired).
- Logic-analyzer trace of the IMU SPI lines at boot if available (validates actual sample rate).

Sensor factory information — *received from pilot 2026-07-23*

The pilot shared screenshots and an AI-generated reference for the Nameless Kechuang V400 wide-angle optical flow sensor. Reconciled against the firmware's actual protocol, the following is now established:

| Item | Taobao/AI claim | Firmware truth | Source |
| --- | --- | --- | --- |
| Sensor brand | Nameless (无名) V400 wide-angle | **Anonymous (匿名) OF module** (frame header `0xAA`, payload-length protocol) | `API/Ano_OF.c:57` |
| Frame header | `0xFE 0x04` (per AI summary) | `0xAA … payload_len …` (Anonymous protocol) | `API/Ano_OF.c:57-105` |
| Sample rate | 66 Hz | 66 Hz update, **200 Hz control integration** (5 ms tick) | `TASK/StabilizerTask.c:249` (`*0.005f`) |
| Baud rate | 19200 8N1 | Same (matches the AI summary; no conflict) | implicit from `Ano_OF.c` UART driver |
| Altitude sensor | Laser 10–500 cm OR ultrasonic 20–300 cm | **Laser, range matches ~5–500 cm firmware band** | `TASK/StabilizerTask.c:289` |
| OF quality byte | `SQUAL` (0–255) | `of_quality` (0–255) at byte 18 of inertial-fused frame | `API/Ano_OF.c:151` |
| OF quality threshold (firmware) | "SQUAL < 25 reject" (AI suggestion) | **`OF_MIN_QUALITY = 50`** — already in firmware | `TASK/StabilizerTask.c:79` |
| Post-bias velocity | (implied body-frame) | `of2_dx_fix`, `of2_dy_fix` (s16, **already inertial-decoupled and bias-fixed by sensor firmware**) | `API/Ano_OF.c:147-148` |
| Sensor-side integration | "MCU + IMU internal fusion" | **Confirmed** — `of2_dx_fix/dy_fix` are post-fusion output | `API/Ano_OF.c:142-152` |

**[VERIFY] sensor identity with pilot.** ~~OPEN — needs resolution.~~ **RESOLVED 2026-07-23 by pilot:** seller is **匿名光流 (Anonymous Optical Flow)** store → sensor is the **Anonymous (匿名)** OF module, not the Nameless V400. The Taobao screenshots are marketing material for a related/look-alike product; the actual sensor on the drone is Anonymous. **The firmware's `0xAA`-header protocol parser is the source of truth** and stays as-is (`API/Ano_OF.c:57-105`).

Consequences for the EKF:
- `R_OF` and `Q_OF_BIAS` will be **derived empirically from flight log replay** (validation plan step 2), not from a V400 datasheet — Anonymous-specific noise figures will come from logged residuals.
- The cross-cutting spec items that match both Anonymous and V400 (laser altimeter 10–500 cm, 19200 baud 8N1, 66 Hz sensor / 200 Hz control integration, 0–255 quality byte, post-fusion `of2_dx_fix`/`of2_dy_fix` body-frame velocity) are de-facto correct and the firmware's existing constants stand.
- The wide-angle FoV caveat (more yaw-rotation feature drift, more pronounced feature motion during yaw) applies to the Anonymous wide-angle module. The EKF's R-matrix for yaw-coupling will need an empirical cross-coupling term derived from replay.

### Firmware-side constants pinned (de-facto values from existing code)

| Constant | Value | Where | Used for |
| --- | --- | --- | --- |
| `OF_MIN_QUALITY` | `50` | `TASK/StabilizerTask.c:79` | gate OF measurements into EKF update and into control |
| `OF_BIAS_STILL_THRESH_RADPS` | `0.05236f` (~3 deg/s) | `TASK/StabilizerTask.c:73` | hot-phase stillness gate |
| `OF_BIAS_STILL_TICKS` | `100` @ 200 Hz = 0.5 s | `TASK/StabilizerTask.c:74` | quiescence dwell before bias sample |
| `OF_BIAS_CAL_TICKS` | `400` @ 200 Hz = 2.0 s | `TASK/StabilizerTask.c:75` | bias-averaging window |
| `of_alt_cm` band | `[5, 500]` cm | `TASK/StabilizerTask.c:289` | altitude acceptance gate |
| `\|h_new − h_last\|` jump | `< 0.10` m/tick | `TASK/StabilizerTask.c:296` | altitude jump-rejection (Z-axis adaptive gate; see Phase 4 of Z-axis redesign below) |
| `s_alt_reject_cnt` force-resync | `≥ 20` ticks | `TASK/StabilizerTask.c:296` | hung-state recovery |
| OF scale (s16 → m/s) | `1 LSB = 0.01 m/s` (assumption, to verify) | derived from `s16 of2_dx_fix` range × `0.005` integration | **REQUIRES V400 datasheet or live measurement to confirm** |
| Control integration tick | `0.005f` (5 ms = 200 Hz) | `TASK/StabilizerTask.c:249-255` | matches FreeRTOS task rate |

### What the AI agent suggested that we **rejected** (with reasons)

| AI suggestion | Why we did not adopt it |
| --- | --- |
| 11-state EKF `[px, py, vx, vy, euler, gyro_bias, of_bias]` | Position `px, py` integration has no measurement to bound it without GPS — would drift unbounded and reintroduce the bug class we're eliminating. Body-frame 9-state `[v_body[3], b_a_body[3], b_g_body[3]]` is the principled alternative. |
| 30 s static ground bias calibration for OF | **Explicitly rejected** in 2026-07-23 grill. Angled surfaces would bake the tilt into the OF bias. Phase 3 (in-flight trim) handles accel bias. OF bias is already handled by the v3 quiescence-gated estimator (lines 46–143). |
| `SQUAL < 25` reject threshold | Too aggressive. Firmware uses `OF_MIN_QUALITY = 50`; tightening further would reject ~half of all flights on typical indoor textures (PMW3901-class `SQUAL` hovers at ~150–250 on good surfaces). |
| Rotate body-frame velocity through Euler angles inside the EKF predict | Wrong direction for body-frame state. Body-frame EKF *never* rotates velocity in the predict step; rotation to world-frame happens **at the dashboard output stage only** (already done at `StabilizerTask.c:253-255`). The EKF inherits the sensor's pre-fused body-frame velocity directly. |
| Recommended 9-state parameters as final | The AI's `Q_flow_vel = 0.01–0.04` and `R_flow_meas = 0.08–0.3` ranges are **estimates**, not measurements. Our `Q_OF`/`R_OF` values in the EKF table above are derived from the firmware's `s16` scale and the existing v3 estimator's effective variance; they will be **re-tuned by replay against logged flight data** (validation plan step 2). |

[VERIFY] Single-source-of-truth invariant for `IMU_EstimatorReady()` after the budget clock lands.
[VERIFY] EKF `Q`/`R` re-tune against logged residuals (empirical, Anonymous-specific, post-replay).
