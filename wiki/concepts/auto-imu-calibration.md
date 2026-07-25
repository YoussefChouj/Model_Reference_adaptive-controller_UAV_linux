---
title: Auto IMU Calibration (cold + air-trim + hot, with parallel 9-state EKF)
type: concept
tags: [imu, calibration, bias, estimator, cold-cal, air-trim, hot-cal, ekf, arming-gate]
created: 2026-07-22
updated: 2026-07-23
sources: [docs/adr/0011-auto-imu-calibration.md, API/imu_update.c, TASK/StabilizerTask.c, API/flight_fsm.c, API/ekf.c (planned)]
related_files: [API/imu_update.c, TASK/StabilizerTask.c, API/flight_fsm.c, TASK/send_data.c, API/ekf.c (planned)]
relations:
  - type: extends
    target: "[[SDK Arming State Machine]]"
  - type: consumes
    target: "[[IMU Update]]"
  - type: parallel_to
    target: "[[MRAC Control Law]]"  # for trust-measured adaptation future work
  - type: writes_to
    target: "[[StabilizerTask]]"
---

# Auto IMU Calibration — what runs and why

Resolves the pilot complaint from [[Tracking Baseline and Drift]] §"OF bias cal (v4)" and
[[Session Conclusions 2026-07-14]] §"Pitch trim fix order" that the previous manual
trigger (`CMD 0x10` style button) was **not** an acceptable permanent solution.

Owner code: [[ADR-0011]]. Implementation hooks live in:

- `API/imu_update.c` — Mahony integrator + cold-convergence detector (`s_settled` /
  `s_innov_lpf`, `IMU_EstimatorReady()`, `IMU_FAST_WINDOW`/`IMU_KP_BOOST`/`IMU_KI_BOOST`).
- `TASK/StabilizerTask.c` lines 46–143 — v3 optical-flow quiescence-gated bias
  estimator (the FSM we **generalize** for hot-cal) and `Reset_World_Origin()` at line 105
  (the existing "cold-cal origin pin" helper).
- `API/flight_fsm.c` — the pre-arm gate at line 40 is the **single** entry-point that
  blocks arming until cold-cal reports `IMU_EstimatorReady()` or budget-timeout fires.
- `API/ekf.c` (planned) — 9-state body-frame EKF running parallel to Mahony, gated by
  `EKFCFG.active` config flag.

## Four phases, one principle

```
POWER ON ─► CAL_BOOT  ─► CAL_COLD  ─► READY (or DEGRADED)
                                       │
                                       ▼ takeoff, sticks-centered ≥0.5 s
                                  CAL_AIRBORNE_HOVER_TRIM (5–10 s)
                                       │
                                       ▼ during FLYING
                                  CAL_HOT_HOVER  ─► commit (low α)
                                       │
                                  CAL_HOT_REJECT ←── gates broken mid-window
```

### `CAL_BOOT` — first ~10 s after boot (existing fast-converge window)
Mahony uses boosted gains (`IMU_KP_BOOST=4.0`, `IMU_KI_BOOST=0.02`) that decay linearly
across `IMU_FAST_WINDOW=10 s`. The same window naturally backs out the cold→warm
gyro-bias shift. No new estimator. Convergence proxy is `s_innov_lpf` (LP-filtered
cross-product innovation energy).

### `CAL_COLD` — boots immediately after `CAL_BOOT`, blocks arm, max 30 s
- **Gyro bias only** (deliberate scope limit, see ADR-0011 §"Phase 2"). The accelerometer
  is **not yet trusted** because the surface may be tilted; baking that tilt into `b_a`
  produces a flying-tilted drone.
- Gyro bias is the existing Mahony `exInt/eyInt/ezInt` walk — promoted from "boot" to
  "cold cal" but otherwise unchanged.
- Pin OF world origin to (0, 0) at the moment `IMU_EstimatorReady()` fires via the existing
  `Reset_World_Origin()` helper. (Already extracted in `StabilizerTask.c:105`, called by
  `CMD 0x10` *and* the new auto-pin on the rising edge of the estimator-ready flag.)
- Settled detector: `s_innov_lpf < IMU_SETTLE_E2` for ≥ 1 s *after* the 30 s window
  closes. **Abort-to-best-so-far** on timeout (pilot choice from grill round 1): keep the
  best residual, arm still unlocks, telemetry bit `COLD_DEGRADED` is set.

### `CAL_AIRBORNE_HOVER_TRIM` — 5–10 s after takeoff, sticks-centered, in FLYING phase
- Triggered when `flight_phase == FLYING`, altitude > 0.3 m, sticks centered for ≥ 0.5 s.
- Runs an **accel-offset least-squares estimator** using the gravity vector now observable
  in world frame (vehicle is stable in hover, so the only constant acceleration the accel
  sees is gravity):
 - Cost: `||  g·R(q(θ)) + b_a − a_meas  ||²` minimized for `b_a ∈ ℝ³`.
 - Closed-form update: `b_a ← b_a + μ · (g_ref − ĝ_meas)` with `μ = 0.02`.
 - Settled condition: `|g_ref − ĝ_meas| < 5 mg` for 1 s.
- This is what enables takeoff from angled surfaces (the +1.3° flat-surface reading is
  either an accel offset or a tilted rest; the air-trim resolves the ambiguity *without*
  the rotate-180° bench test).
- On settled: write `b_a` to `acc_offset[3]` exported by `API/imu_update.c`, set
  `cal_health.AIRBORNE_OK`. On timeout: best-so-far + `AIRBORNE_DEGRADED`, continue flight.
- The 9-state EKF (when `EKFCFG.active == 1`) supersedes this closed-form LS estimator —
  its 9-state coupling handles accel bias naturally through the Kalman update.

### `CAL_HOT_HOVER` — in flight, during sticks-centered hover only
Reuses the v3 OF-bias FSM (states `WAIT_STILL → ACCUM → COMMIT`) generalized for the
**gyro axis only** (accel was handled in Phase 3):

| Gate | Purpose |
| --- | --- |
| `HOT_HOVER_STILL_THRESH` | gyro stillness (3 deg/s, shared with cold phase) |
| `RCInput_IsActive(PITCH/ROLL/THR/YAW)` | sticks centered |
| `flight_phase == FLYING` | never active on GROUND_IDLE / LANDING / LANDED |
| `|of2_dx_fix| + |of2_dy_fix| < TRANSL_THRESH` | **translational guard** — pilot is hovering, not just sitting still |
| `|lin_acc_X_body| + |lin_acc_Y_body| < LIN_ACC_THRESH` | **translational guard (accel)** — disarms the gravity-reference ambiguity |

Commit step uses the same recursive `α=1e-4` as the existing v3 OF estimator to keep
behaviour identical in magnitude.

**Hot cal never updates `accel_bias`** (gravity reference) — per PX4/ArduPilot precedent.
Updating in flight would slowly tilt the gravity vector, which is the exact bug class we
are eliminating. Hot cal **may** update `gyro_bias** only (steady drift compensation for
the BMI088 gyro's known temperature dependence).

`HOT_REJECTED` telemetry bit fires whenever the WAIT_STILL→ACCUM→COMMIT window breaks with
a counted reason.

## Parallel estimator — 9-state body-frame EKF (`API/ekf.c`)

State vector `[v_body[3], b_a_body[3], b_g_body[3]]` — 9 states. Runs at 1 kHz,
parallel to Mahony, **no replacement** of Mahony on first validation cycle.

Why body-frame:
- Body-frame biases are sensor properties (do not rotate with the vehicle) — easier to identify.
- Earth-frame "biases" are disturbances (wind, off-CG torques) — they belong as process noise `Q`, not as Kalman states. MRAC handles those.
- PX4's hybrid ESKF is more elegant but requires ~50 tunable parameters; body-frame 9-state gives 80% of the benefit with 20% of the code.

Why side-by-side (per pilot grill round 1 choice):
- EKF outputs (`v_body`, `b_a_body`, `b_g_body`, plus `P_diag` and `NIS`) streamed in `0x05` for offline replay comparison against the PI corrector.
- Only after a documented validation cycle (replay → bench → tethered → free) does a separate decision gate the EKF output into the control loop.

Initial `Q`/`R` table (defaults until sensor datasheets land):
- `Q_v = 1e-3 m²/s³`, `Q_ba = 1e-6 m²/s⁵`, `Q_bg = 5e-9 rad²/s³` (BMI088 datasheet estimates)
- `R_OF = 6.16e-4 m²/s²` (from `flight_1783845799.csv` Scenario 1 measurement, `X = 0.0124 m/raw·s`)
- `R_acc = 5e-3 m²/s⁴` (gravity-removed)
- `R_z = 0.04 m²/s²` (altimeter noise floor)

## Manual `CMD 0x10`

- **Stays callable for SysID init** — `dashboard.py:3435` sends it before each SysID run.
- **Renamed** to "Reset World Origin (debug)" in the dashboard with a hover tooltip
  warning "Auto-cal owns normal flow; this button is for SysID init only."
- A new `CMD 0x18 force_recal` (idx 0) re-enters `CAL_COLD` from `GROUND_IDLE` — but
  **refused** if armed or if `flight_phase == FLYING` was ever observed before disarm.
  This is the deliberate escape hatch.

## Telemetry surface

| Frame | Field | Type | Notes |
| --- | --- | --- | --- |
| `0x01` status | `cal_health` | u16 | `0x01 BOOT_OK \| 0x02 COLD_OK \| 0x04 COLD_DEGRADED \| 0x08 AIRBORNE_OK \| 0x10 AIRBORNE_DEGRADED \| 0x20 HOT_HOVER_OK \| 0x40 HOT_REJECTED \| 0x80 MANUAL_ORIGIN_RESET \| 0x100 BOOT_TIMEOUT \| 0x200 ESTIMATOR_READY` |
| `0x05` OF-fusion | `acc_bias[3]`, `gyro_bias[3]` | s16×6 | appended, mg and 1e-4 rad/s |
| `0x05` OF-fusion (when EKF active) | `v_body[3]`, `P_diag[3]`, `NIS`, `kalman_gain[3]` | s16×8 | appended; bumps `GS_PROTO_VERSION` v11 → v12 |

The dashboard's existing "Reset World Origin" button (lines 1972–1974, 2061–2064 in
`dashboard.py`) is renamed and its tooltip rewritten in the same patch.

## Why this matters (background)

The +1.3° pitch reading on a flat surface in `docs/session_conclusions_2026-07-14.md` is
either accelerometer zero offset **or** a tilted rest surface. Phase 2 (cold cal) refuses
to resolve this; Phase 3 (air-trim) resolves it in the air using the now-observable
gravity vector. The 9-state EKF generalizes Phase 3 to a Kalman framework.

The 13 % warmup drift over 13 min (`docs/tracking_baseline_and_drift.md` v1/v2 history)
motivates the hot phase: the steady `α=1e-4` recursive update follows temperature without
disturbing the gravity reference.

## Future work — thesis track (Trust-measured adaptation)

Once the 9-state EKF's covariance matrix `P` is validated against flight data, the MRAC
law in `API/mrac.c` is extended to consume the EKF's posterior covariance directly:

```
Γ_eff(k) = Γ_max · diag(P_attitude(k)) / (diag(P_attitude(k)) + ε)
```

Interpretation: when the EKF is confident (small `P`), `Γ_eff → Γ_max` (full adaptation);
when uncertain (large `P`, model disagrees with measurements), `Γ_eff → 0` (no adaptation
because we don't trust the data driving it). This is the principled version of "adapt
when measurements are trustworthy."

Each new measurement source (OF → GPS → baro → vision) **mechanically reduces** the
corresponding `P` diagonal through the Kalman update step, which raises `Γ_eff`
automatically. So "more sources = more trust" is a property of the architecture, not a
knob. Citations to land in `wiki/literature/`:
- **Yucelen & Johnson**, "Actuator Command Limiting and Bias Correction for Adaptive Control"
- **Yucelen et al.**, "Composite Model Reference Adaptive Control"

## See Also

- [[ADR-0011]] — full decision record
- [[IMU Update]] — Mahony filter, including `s_innov_lpf` convergence metric
- [[Mahony Filter Theory]] — the observer math behind the `exInt`/`eyInt`/`ezInt` walk
- [[Tracking Baseline and Drift]] — the v1/v2/v3 history that motivated this
- [[SDK Arming State Machine]] — flight FSM that gates on `IMU_EstimatorReady()`
- [[MRAC Control Law]] — target of the trust-measured adaptation future work

**Confidence:** Proposed (ADR-0011); sensor identity **RESOLVED** (Anonymous 匿名 OF module,
firmware protocol authoritative); implementation deferred until pilot sign-off on the
four-phase restructure. Empirical `R_OF`/`Q_OF_BIAS` tuning will run on first replay cycle.
**Tags:** #imu #calibration #bias #estimator #cold-cal #air-trim #hot-cal #ekf #arming-gate #of-sensor
