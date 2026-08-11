# `sim/` — MRAC simulation package

Clean, test-driven rebuild of the MRAC simulation. Single source of truth for
adaptive-control behaviour, replacing the legacy hanging-rig notebooks (wrong
mass, drifted from firmware). Design rationale: [ADR-0006](../docs/adr/0006-sim-package-architecture.md).
Identified plant numbers: [docs/sysid_results.md](../docs/sysid_results.md).

Everything runs at **`dt = 0.005 s` (200 Hz) = `MRAC_DT`**, so every gain/flag
transfers between `API/mrac.c` and here with **zero rescaling** (ADR-0006 D1).

## Two scenarios, one codebase

1. **Hardware-param derivation** — compute the reference-model matrices, Lyapunov
   `P`, and gains that get pasted into `API/mrac.c`. The design-time calculator is
   [`ground_station/scripts/compute_reference_model.py`](../ground_station/scripts/compute_reference_model.py)
   (continuous `Am/Bm`, matrix `P` via Lyapunov). The in-loop `reference_model.py`
   here mirrors what the firmware *executes* each tick (Euler recurrence + the
   *scalar heuristic* `P = 1/(2·wn)` it actually uses, ADR-0003) — keep the two apart.

2. **Virtual simulation** — run the firmware-parity controller against a pluggable
   plant. Phase 1 = identified linear rate models; 6-DOF = ``MujocoPlant``,
   swapped behind the `Plant` seam without the controller knowing (ADR-0006 D3/D6).

## Module map

| Module | Mirrors | Role |
|---|---|---|
| `plant.py` | — (identified models) | Rate-loop plant seam `step(u_dict)->state_dict`; ZOH + integer transport-delay buffer. `IdentifiedPlant`, `RigidBodyPlant`, `MujocoPlant`. `CANONICAL_MODELS` is the **single source of truth** for the identified per-axis plants (scenarios reads it too). |
| `reference_model.py` | `mrac.c:168-196` | Per-axis `xm` recurrence + adaptive-law gains (`P`, and `Pe`/`Pedot` for 2nd order). `for_axis(..., ref_model_type=)` mirrors the firmware CMD-0x13 runtime switch — pass `0/1/2` to force passthrough/1st/2nd on any axis. `l1`/`l2` = CRM feedback gain `L` (ADR-0008); `Pe`/`Pedot` are the analytic 2×2 Lyapunov solution for `Am−L·C`, collapsing to ADR-0007 when `L=0`. |
| `regressor.py` | `mrac.c:65-91` | 6-basis structured regressor `[bias, x, x·tanh x, cross, u_nom, xm]`. |
| `drive.py` | (the `s` in `mrac.c`) | **Lyapunov-drive seam**: `s = eᵥᵀ P B`. Two adapters — `scalar_drive` (ADR-0003) and `state_space_drive` (ADR-0007). A new law (CRM, set-theoretic) is a new Drive, not another branch in `update()`. |
| `adaptive_law.py` | `mrac.c:93-276` | Lyapunov gradient update: projection / σ- & e-mod / deadzone / hard-freeze / tanh-sat / L1 / perf-recovery. Selects a `drive.py` adapter; one-file swap point for new laws. |
| `baseline.py` | `pid.c` ComputePID | Inner rate PID (`gyrox/gyroy/gyroz` gains), deg/s in → mixer `U` → `u_nom = U/mrac_to_mixer` (Nm). |
| `loop.py` | `mrac.c:424-485` | **Wiring seam** `ControlLoop.tick`: one closed-loop tick (ref → e → PID → regressor → law → plant), separate from logging. Where a closed-loop reference model would plug in. |
| `scenarios.py` | — | Step / doublet / yaw-test (tracking) + inertia-offset / disturbance (dynamics change). |
| `metrics.py` | — | **Run evaluation** (pure, log-only): tracking (IAE/ISE/ITAE/settling/overshoot), control effort + saturation, adaptation health (active fraction, bound saturation), robustness (`ė` RMS, zero-crossings), disturbance recovery. Tested on synthetic logs. |
| `run.py` | — | Closed-loop runner: owns the clock + log arrays, calls `loop.tick`, then `metrics.compute`; writes the per-run artifact folder. |
| `runner.py` | — | **Deleted** (ADR-0012 D1). Scenario execution lives in `run.py`. |
| `sanity.py` | — | Per-plant SysID gain-matching gate (ADR-0012 D5). Instantiates a plant, runs a step excitation, compares measured `(K, p, T)` against `CANONICAL_MODELS`. Replaced the Gazebo-era hover gate. |

## Delay wrapper (ADR-0012 D6)

Every 6-DOF plant used for prior learning carries an **actuator transport delay**
on per-motor thrust, because weights learned on a delay-free plant are
systematically over-confident. One primitive, `sim/delay.py:ActuatorDelayBuffer`,
is shared by all plants (`N = round(T/dt)` integer-sample FIFO, `N=0` passthrough):

- `_AxisSim` (the `IdentifiedPlant` rate axis) delays its scalar input.
- `RigidBodyPlant(thrust_delay_s=...)` delays the 4-per-motor thrust target,
  pre-loading the FIFO with hover thrust so a plant holding hover keeps producing
  hover during the lag (matching the MujocoPlant bridge's reset warm-up).
- `MujocoPlant(thrust_delay_s=...)` delays per-motor thrust inside `mujoco_bridge`.

Default `thrust_delay_s=0` (or `delay=0`) is a pure passthrough — bit-identical to
the pre-change plants. The delay and the motor LPF commute as LTI operators, so a
delayed plant's response is exactly the undelayed response shifted by N ticks
(verified in `test_plant.py::test_rigid_body_plant_thrust_delay_shifts_response_by_N`).

## Dimensionless priors (ADR-0014 D1–D4, ADR-0013 D5)

`sim/priors.py` defines the dimensionless adaptive prior `Prior`, the stored form
`Theta_tilde = K * Theta` learned on a source plant tagged by `plant_tag = (K, p, T)`.
Deployment on any target is `Theta = Theta_tilde / K_target` — the `1/K` matching
argument is what makes priors airframe-invariant. The raw `Theta` and the source
`(K, p, T)` are stored alongside, never instead.

- `Prior.convert_to(target_plant_tag)` rescales for a target plant; **cross-plant
  application without an explicit `convert_to` is refused** — the failure mode
  ADR-0014 D7 identifies as the thesis headline result.
- Cross-variant transfer is forbidden (`RegressorVariant` registry, ADR-0014 D4).
- `sim/adaptive_law.py` carries the `sigma_prior` / `theta_prior` attractor
  (ADR-0013 D5): `-sigma_prior·(Theta − theta_prior)` added to the gradient when
  `sigma_prior_on` is set. Default `sigma_prior=0` is bit-identical to pre-change
  (parity tests in `test_adaptive_law.py`).

## The unit chain (firmware-faithful)

```
scenario r(t) [rad/s] ──▶ reference_model ──▶ xm [rad/s]
        │                                        │  e = x - xm
        ├─▶ ×57.3 ─▶ RatePID (deg/s) ─▶ U [mixer] ─▶ ÷mrac_to_mixer ─▶ u_nom [Nm]
        │                                        │            │ (regressor slot 4)
        │                              regressor(x, u_nom, xm) ─▶ Φ ─▶ adaptive_law ─▶ u_ad [Nm]
        ▼                                                                              │
   plant.step({axis: u_nom + u_ad + disturbance})  ──▶  x [rad/s]
```

`mrac_to_mixer` uses the active build (`ACTIVE_PAYLOAD = PAYLOAD_LIGHT` →
1170 P/R, 1872 yaw; `mrac.h:36-40`). The identified plant was characterised as
`u_nom (Nm) → rate (rad/s)` in shadow mode (`sysid_results.md`).

## Running

```bash
python -m sim.run step_roll          # any key in scenarios.ALL
python -m sim.run yaw_test
pytest sim/tests/ -q                  # 75 tests
```

Each run writes `sim/runs/<timestamp>_<scenario>/` (gitignored, ADR-0006 D7):
`plots/{tracking,error,control,weights}.png`, `data.csv` (12 columns incl. `d`, `edot`),
`metrics.json` (grouped `track_*/ctrl_*/adapt_*/robust_*/dist_*`), `report.md`.
Programmatic use: `from sim.run import run; res = run(scenarios.step("roll"), injection=True)`.
Reproduce the as-flown power-on default (passthrough): `run(sc, ref_model_type=0)`.

## Phase-1 findings (firmware behaviour confirmed by spec 00 + 00b)

* **`What_lower_limit[0] = -What_limit[0]` for pitch/roll/yaw; 0.0 for all other slots/axes.**
  Slot 0 was unlocked in `MRAC_Init` (mrac.c:353-355) to let the bias weight cancel a
  standing torque imbalance. Slots 1-5 stay at 0 on every axis. The old README said
  "never set in MRAC_Init" — stale for slot 0 on pitch/roll/yaw, correct for the rest.
  The drift existed because `sim/adaptive_law.py`'s comment and `for_axis()` default were
  never updated after the firmware fix landed.
  Measured before/after on `disturbance_rejection` (0.08 Nm bias, r=0): with slot 0
  locked at 0, θ₀ stays at 0 and the PID bears the full disturbance. With slot 0 unlocked
  to -What_limit[0], θ₀ converges to ≈ −0.002 (roll/pitch) or −0.004 (yaw), and RMSE
  improves ~2-3%. The improvement is real but modest — `e_deadzone = 0.05` is the
  dominant adaptation suppressor (adaptation halts ~0.2 s after disturbance onset).
  Slots 1-5 remain locked; unlocking them is Sweep A's open research question.
* **`e_deadzone = 0.05` rad/s + a well-tuned baseline** — with the identified plant
  the inner PID already reaches ≈ the reference bandwidth (44 rad/s), so the error
  falls into the deadzone within ~0.2 s and adaptation halts. MRAC's footprint is
  small by design here; the big adaptation wins come from larger plant mismatch
  (try `inertia_offset_*` with a smaller `factor`).

## Two named envelopes: learning vs deployment (spec-11)

A simulation cannot crash. The flight-safety constraints on adaptation do not apply there.

Three mechanisms suppress learning in firmware, each with a flight-safety justification:

| | Flight purpose | Cost when learning |
|---|---|---|
| `e_deadzone = 0.05` | stops drift when error is noise | adaptation halts ~0.2 s after onset |
| `What_limit` | bounds authority | clipped weight = censored observation, not a converged one |
| `Γ` | bounds aggressiveness | too low to converge inside a run |

One configuration was doing both jobs, and the safety job wins. `for_deployment()`
returns exact firmware parity (default everywhere). `for_learning()` relaxes:

- `e_deadzone = 0.01 rad/s` — derived from the measured gyro-noise RMS of
  ~0.005 rad/s on the identified plant (k=2 in `e_deadzone ≈ k·σ_noise`). Zero is
  forbidden: Ioannou & Sun show that a zero deadzone causes **bursting** (parameter
  error and tracking error cycle without converging).
- `What_limit = 5× deployment` — projection stays on; a clipped weight is still
  a censored observation, so widening the bound lets every slot explore.
- `What_lower_limit` symmetric on all slots — deployment only unlocks slot 0;
  learning symmetrically unlocks all slots so slots 1–5 can explore in both
  directions.
- `Γ` not raised — prior-02 (transport-delay wrapper) is required first.
  A gain that is stable against a delay-free plant can be unstable against the
  real 15 ms delay; raising Γ without prior-02 produces an over-confident prior.

**The learning envelope is simulation-only.** It must never be proposed as a
firmware config. Every prior is validated under the deployment envelope before it
counts. The paired experiment (`python -m sim.experiments`) is the key deliverable:
learn under learning → replay under deployment → report the gap. If the gap is zero,
priors buy nothing and the programme needs rethinking.

## 2nd-order state-space matrix-P law (ADR-0007)

For `ref_model_type = 2` (roll/pitch) the scalar `P = 1/(2·wn)` is replaced by the full
Lyapunov matrix-`P` drive `s = e·Pe + ė·Pedot` (only the 2nd column of `P` matters with
`B = [0;1]`; `Pe,Pedot` are closed forms in `wn, ζ, Q`). `ė` is a filtered finite
difference of the rate (noisy on hardware — modelled the same lossy way here). `Q` is the
gain knob: `run(..., q1=, q2=)`; `q1 = wn` recovers the old scalar e-gain. Sweep it with
`python -m sim.experiments` (Sweep B). This is firmware-parity with `MRAC_UpdateAxis` and
gated identically on `ref_model_type == 2`.

## Closed-loop reference model / CRM (ADR-0008)

For `ref_model_type = 2`, a feedback term `L·(x − xm)` (gains `crm_l1`, `crm_l2`) pulls the
reference toward the plant, suppressing the adaptation transient — the modern-MRAC step.
The error dynamics become `Am − L·C`, so `Pe`/`Pedot` are recomputed from the **analytic
2×2 Lyapunov** closed form (still live, no matrix library; `scipy` is only the test oracle
in `test_crm.py`). `L = [0,0]` (default) = open-loop RM, byte-identical to ADR-0007. `l1`
(observer pole on the measured rate error) dominates; `l2` only shifts effective stiffness.
Run: `run(sc, crm_l1=40)`. Sweep on the identified roll plant: `l1` 0→80 cuts
`disturbance_roll` RMSE ~4× and `step_roll` overshoot 61%→10%, all stable. **Sim only so
far — firmware port pending** (ADR-0008 Consequences).

**Robustness — measured, not assumed** (Sweep C, `python -m sim.experiments`; ADR-0008
Validation): the expected Lavretsky "large `L` narrows the delay margin" did **not** appear
for this identified-linear + pure-delay plant — CRM actually *widened* it (critical delay
15→45 ms as `l1` 0→80). The binding limit is instead **numerical**: the reference model's
forward-Euler update is stable only for `l1·DT < 2` → `l1 < 2/DT` (≈400 at `DT=5 ms`),
delay-independent. The closed loop masks it (PID/`What` clamps keep the plant rate bounded
while `xm` diverges), so the firmware port must clamp `crm_l1` against `DT`; recommended cap
`l1 ≤ ~0.4/DT`. Re-test the Lavretsky tradeoff on MuJoCo, where real HF/actuator dynamics
exist.

## Phase 3 + Phase 4 calibrators (ADR-0011)

Phases 3 and 4 of the IMU auto-calibration sequence are implemented in
[`sim/calibrator.py`](sim/calibrator.py) with 10 unit tests (see
[`sim/tests/test_calibrator.py`](sim/tests/test_calibrator.py)).

**Phase 3 — `AccBiasTrim`** (CAL_AIRBORNE_HOVER_TRIM): closed-form least-squares
accel-bias estimator using the gravity vector as a reference.  Cost
`||g_ref − (g_meas + b_a)||²` is minimised with gain `μ=0.02`; settled when
residual < 5 mg for 200 consecutive ticks (1 s at 200 Hz).  Degrades to
best-so-far after 10 s.

**Phase 4 — `GyroBiasHotFsm`** (CAL_HOT_HOVER): finite-state machine mirroring
the OF-bias FSM in `TASK/StabilizerTask.c:46-143`.  Awaits 0.5 s of stillness
(still_ticks=100), accumulates 2 s of gyro samples (acc_ticks=400), then refreshes
`b_g` with an EWMA filter at `α=1e-4` — intentionally very slow to avoid
upsetting the loop during flight.  Any guard violation (RC active, not flying,
translational acceleration, gyro motion) resets to WAIT_STILL and sets
`rejected=True`.

Integration into the closed-loop runner: [`sim/run.py`](sim/run.py) steps both
calibrators **every tick** at 200 Hz.  `AccBiasTrim` is gated on `|r| < 0.1`
(≈ hover setpoint) and `elapsed_t > 0.3 s` (the combined sticks-centred +
altitude gate, approximated).  `GyroBiasHotFsm` carries its own internal guards.

Two new integration scenarios are registered in `scenarios.py`:

| Scenario | What it tests | Key assertion |
|---|---|---|
| `cold_with_bias` | Phase 3 on tilted surface; 50 mg X-accel bias; cold-cal gate 0-2 s then AccBiasTrim | `\|b_a_x − 50\| < 5` mg |
| `hot_gyro_drift` | Phase 4; 0.02 rad/s Y-gyro bias; clean hover | `0 < b_g_y < 0.01` rad/s (correct direction, < 50% of injected) |

Run the calibrator integration tests:

```bash
cd sim && python -m pytest tests/test_scenarios_cal.py -v
```

6-DOF plant is now `MujocoPlant` (ADR-0012 D2). Outer position/attitude
loops, operational/geofence limits, and the Z axis (un-wired in firmware). See
ADR-0006 D5/D6.
