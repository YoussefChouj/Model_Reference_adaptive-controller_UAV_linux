# Requirements — quantitative thresholds the system must meet

Each row identifies a measurable claim, the threshold (or baseline-
frozen value), the verification rung at which it is checked, and the
specific code that checks it. Rows the developer cannot yet measure
are marked **TBD** with a note on what would make them measurable.

Thresholds are raised only by deliberate edit with a recorded reason
in the journal. Where the developer has no target, **current measured
behaviour is frozen as the baseline** so "do not get worse" is
enforceable without inventing numbers.

Rung glossary:

  * **MIL** — Model-in-the-loop (the analytic 6-DOF plant + outer
    loops, no firmware). Host-only; runs on Windows and Linux.
  * **SIL** — Software-in-the-loop (host-compiled firmware C against
    the rate-loop sim). See spec 1.
  * **PIL** — Processor-in-the-loop (firmware running on the target,
    not yet flown). See spec 2/3.
  * **Build** — uVision build budget gate. See spec 2/3.
  * **Hardware** — actual flight, validated against recorded logs.
    See spec 4a flight-log validation.

| ID  | Requirement | Threshold | Rung | Verifier |
|-----|-------------|-----------|------|----------|
| RQ-001 | Identified rate-loop plants reproduce firmware `K`/`p` to within 1 % of `docs/sysid_results.md` | rms relative error < 1 % | MIL | `sim.tests.test_plant.py::test_roll_asymptotic_rate_slope_equals_K` |
| RQ-002 | Identified plant rate-K parity vs `mrac.c` (firmware-parity u-units) | controller steps identically with the same command | MIL | `sim.tests.test_plant.py` + `sim.tests.test_seams.py` |
| RQ-003 | Rate-loop SIL tolerance (host-compiled `mrac.c` vs `sim/`) | RMSE < 1e-6 rad/s | SIL | spec 1 verifier (`tasks.py test sim`) |
| RQ-004 | Free-fall acceleration = `g` (9.80665 m/s², body-z downward) to within 0.1 % | numerical vs analytic | MIL | `sim.tests.test_rigid_body_plant.py::test_free_fall_acceleration_equals_g` |
| RQ-005 | Hover equilibrium thrust = `m*g` (12.71 N for the canonical airframe) | numerical vs analytic, residual < 1 % | MIL | `sim.tests.test_rigid_body_plant.py::test_hover_equilibrium_total_thrust` |
| RQ-006 | Angular momentum conserved with zero applied torque | drift < 1e-6 kg m²/s over 1 s | MIL | `sim.tests.test_rigid_body_plant.py::test_angular_momentum_conservation_no_torque` |
| RQ-007 | Gyroscopic coupling produces the expected cross-axis response | sign + magnitude analytic vs numerical | MIL | `sim.tests.test_rigid_body_plant.py::test_gyroscopic_coupling_cross_axis_response` |
| RQ-008 | Roll/pitch inertia asymmetry (Iyy-Ixx = 9.16e-4) appears in rate response | free-decay period ratio = sqrt(Iyy/Ixx) within 1 % | MIL | `sim.tests.test_rigid_body_plant.py::test_inertia_asymmetry_period_ratio` |
| RQ-009 | Quaternion round-trips Euler (ZYX) without drift | `‖q‖` = 1 after 10 s of motion | MIL | `sim.tests.test_rigid_body_plant.py::test_quaternion_unit_norm_under_motion` |
| RQ-010 | Determinism: identical seed + initial state → identical trajectory | bytewise equal | MIL | `sim.tests.test_rigid_body_plant.py::test_determinism_after_reset` |
| RQ-011 | Frame transforms round-trip: world→body→world = identity | residual < 1e-12 | MIL | `sim.tests.test_rigid_body_plant.py::test_body_world_rotation_round_trip` |
| RQ-012 | Outer-loop tracking: commanded position reached within 0.3 m in 2 s (canonical baseline) | TBD — first-baseline freeze | MIL | `sim.tests.test_outer_loops.py::test_commanded_position_reached` |
| RQ-013 | Outer-loop tracking: commanded attitude reached within 5 deg in 1 s | TBD — first-baseline freeze | MIL | `sim.tests.test_outer_loops.py::test_commanded_attitude_reached` |
| RQ-014 | Loop rates mirror firmware structure (controller at 200 Hz, plant sub-step optional) | dt = 0.005 s | MIL | `sim.tests.test_outer_loops.py::test_loop_rates_match_firmware` |
| RQ-015 | Lemniscate trajectory RMS cross-track error ≤ 0.20 m (canonical baseline) | TBD — first-baseline freeze | MIL | `sim.tests.test_trajectories.py::test_lemniscate_cross_track_baseline` |
| RQ-016 | Square (4-side polygon) trajectory max cross-track error ≤ 0.40 m | TBD — first-baseline freeze | MIL | `sim.tests.test_trajectories.py::test_polygon_cross_track_baseline` |
| RQ-017 | Aggressiveness parameter increases cross-track error monotonically (within 10 % margin) | cross-track ratio close to aggressiveness ratio | MIL | `sim.tests.test_trajectories.py::test_aggressiveness_increases_difficulty` |
| RQ-018 | Path metrics are pure (computable on synthetic logs with known analytic answers) | cross-track RMSE equals known offset exactly | MIL | `sim.tests.test_metrics_path.py::test_known_constant_offset_yields_exact_cross_track` |
| RQ-019 | Path metrics computed on a perfectly-tracked path yield zero cross-track | numerically zero | MIL | `sim.tests.test_metrics_path.py::test_perfect_tracking_zero_cross_track` |
| RQ-020 | Flight-log validation reports fidelity + named modelling gaps on a real log | JSON sidecar written, gaps enumerated | MIL | `sim.tests.test_replay_flight_plant.py` |
| RQ-021 | Flight-log validation degrades gracefully on a log with no body-rate columns | fidelity numbers NaN, gaps still listed | MIL | `sim.tests.test_replay_flight_plant.py::test_replay_handles_missing_signals` |
| RQ-022 | OS-agnostic sim code: no `C:\\` paths, no backslash separators, no `.venv/Scripts` references | grep clean | Build | spec 4a pre-commit checks |
| RQ-023 | Build budget: code ≤ 80 KB, RO-data ≤ 2 KB, RW-data ≤ 4 KB, ZI-data ≤ 112 KB | documented in spec 3 | Build | spec 3 verifier |
| RQ-024 | Flash budget: ≤ 256 KB total image | documented in spec 3 | Build | spec 3 verifier |
| RQ-025 | Stack budget: no task overflow at 200 Hz worst-case | Send_Task 500 words verified | PIL | spec 3 verifier |
| RQ-026 | Gazebo bring-up cross-check: hover-equilibrium thrust agrees with analytic plant within 2 % | TBD until spec 4b lands | MIL | spec 4b verifier |
| RQ-027 | URDF inertial origin placed at CG (offset not applied twice) | URDF/SDF generator emits correct `<inertial>` | MIL | spec 4b verifier |
| RQ-028 | PIL: host-compiled firmware C identifies the same `K`/`p` on synthetic data as `sim/sysid_analysis.py` | K within 5 %, p within 10 % | PIL | spec 1 + spec 2 verifier |
| RQ-029 | Hardware: position hold RMSE within green-zone spec (±0.3 m steady-state) | TBD — first-baseline freeze | Hardware | post-flight replay (`sim.tools.replay_flight_plant`) |
| RQ-030 | Hardware: trajectory-tracking RMSE ≤ 0.5 m on a 1 m/s circular path | TBD — first-baseline freeze | Hardware | post-flight replay |
| RQ-031 | Free-flight log contains `of.lin_acc_x_mg` (EKF replay input) | byte present in frame A | Hardware | `ground_station.livewatch fields of.lin_acc_x_mg` |

## Notes

- **Baseline freezing.** Rows RQ-012 through RQ-017 are "do not get
  worse" gates. The first run that passes them freezes the threshold;
  intentional tightening is a deliberate edit to this document.
- **TBD rows.** Where a threshold cannot yet be set (the developer has
  no target, or the verifier does not exist), the row is marked TBD
  with the smallest statement that would make it measurable.
- **No certification language.** This is a thesis, not a certification
  effort. Wording is plain; "must" + "shall" are avoided.

## Known model gaps (analytic plant — spec 4a)

The following effects are **deliberately not** modelled analytically.
They are the reason spec 4b exists. Any work that depends on them
must use Gazebo or hardware, not the analytic plant.

- Aerodynamic drag (body-frame linear and rotational)
- Ground effect (altitude-dependent thrust bias)
- Prop wash / inflow downwash on attitude loops
- Battery sag (voltage-dependent motor RPM)
- Frame flex (motor-to-CG arm compliance under load)
- Sensor noise and bias (gyro / accel)
- Motor / ESC non-linearity beyond the 1st-order LPF
- Wind / external disturbance

## How to update a threshold

1. Run the verifier listed in the row. Record the result.
2. Edit the row's `Threshold` column to the new value.
3. Append a one-line note in `.agent_contracts/mbd_workflow/journal.md`
   under the implementer/reviewer entry: `T:<row-id> <old> -> <new>,
   <reason>`.
4. Commit.