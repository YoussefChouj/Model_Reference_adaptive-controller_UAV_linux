# 0006 - Simulation Package Architecture (sim/ rebuild, Phase 1)

*   **Status:** Accepted
*   **Date:** 2026-06-23
*   **Depends on:** ADR-0003 (inner-loop MRAC), ADR-0005 (identified ref models + adaptive law), `docs/sysid_results.md`
*   **Supersedes:** the legacy Jupyter-notebook simulations (hanging-rig 3-DOF, 366 g mass) as the source of truth for adaptive-control behaviour.

## Context

The MRAC simulation lived in several large notebooks that are no longer navigable or
trustworthy: they model a constrained 3-DOF hanging rig, use a wrong mass (366 g vs the
measured **988.5 g**), and have drifted from the firmware in `API/mrac.c`. We are rebuilding
a clean, test-driven `sim/` Python package that is the single source of truth for
adaptive-control behaviour and serves two scenarios from one codebase:

1.  **Hardware-param derivation** — produce reference-model matrices, Lyapunov P, and PID/LQR
    gains pasted into `API/mrac.c` (firmware parity is a hard requirement).
2.  **Virtual simulation** — a pluggable plant so the same controller runs against the
    identified linear models *and* (later) a higher-fidelity 6-DOF / Gazebo model. The
    controller and adaptive law must not know which plant is behind the seam.

## Decisions

### D1 — Controller timestep `dt = 0.005 s` (200 Hz), matching `MRAC_DT`
The firmware MRAC loop runs at 200 Hz (`mrac.h: MRAC_DT = 0.005f`), **not** 500 Hz. The
adaptive update `Theta += MRAC_DT * y` is dt-sensitive, as are `gamma`, `sigma`, and `omega_u`.
The sim controller steps at exactly 5 ms so every gain pastes from `mrac.c` with zero rescaling.
A finer *plant* integration sub-step is permitted internally (for the delay term) but the
*controller/adaptation* step is fixed at 5 ms.

### D2 — Canonical frame is NED (firmware convention)
Inside `sim/`, Z is positive-down, matching the firmware. A thin ENU adapter is added at the
Gazebo seam only (ROS 2/Gazebo are ENU). No sign flips leak into the controller.

### D3 — Plant boundary is the rate loop: torque/thrust in, rate out
The identified plants model **inner-loop rate dynamics only** (what SysID trustfully produced).
Outer position/attitude PID loops live in `baseline.py`, never in the plant. The plant contract
is `plant.step(u_dict) -> state_dict`:
*   `u_dict   = {'pitch','roll','yaw','z'}` — SI torques (Nm) / thrust (N), i.e. `u_nom + u_ad`.
*   `state_dict` carries rates `{p, q, r, vz}` (rad/s, m/s) in Phase 1, but is an **extensible
    dict** so a later plant can return full 6-DOF state (`x,y,z,φ,θ,ψ,…`) without breaking callers.
Keyed dicts (not numpy index vectors) make the axis mapping explicit and eliminate
silent index-order bugs; the cost is negligible at 200 Hz in Python.

### D4 — Identified plant: integer delay buffer + ZOH discretization
`G(s) = K/(s(1+s/p))·e^{-sT}` is realised as: the rational part `K/(s(1+s/p))` discretized by
**ZOH** (matches the ESC holding PWM constant between ticks), in series with an **integer delay
ring buffer** of `N = round(T/dt)` samples (T≈12–15 ms ≈ 2–3 steps at 200 Hz). The delay is
*not* cosmetic — it caps how aggressively the adaptive law can learn; dropping it makes the sim
falsely stable. Per-axis structure: roll/pitch = rel-degree-2 + delay; yaw = pure integrator
`37/s` (rel-degree 1, no pole/delay).

### D5 — Implement dynamics-affecting limits; defer operational ones
In-loop limits that change the closed-loop response are in Phase 1; operational/position guards
are deferred or modelled as scenario events:

| Limit | Phase 1? | Rationale |
|---|---|---|
| `u_max` torque/thrust saturation | **Yes** | Interacts with adaptation; reason Pseudo-Control-Hedging exists. |
| Projection, `e_freeze`, `e_sat`, `e_deadzone`, σ/e-mod | **Yes** | These *are* the adaptive law; mirror `mrac.c` line-for-line. |
| Setpoint rate limiters (Z ±0.005 m/cycle) | Later | Lives in outer loop; relevant once baseline drives trajectories. |
| Green-zone geofence | Later (scenario event) | Position-level abort; no rate-loop dynamics value. |
| `DANGEROUS_STOP` kill | No | Pure operational safety. |

### D6 — Gazebo is a reserved stub in Phase 1
`GazeboPlant` documents the `step(u_dict)->state_dict` contract and raises `NotImplementedError`.
Real bring-up is a later session on the **dual-boot Linux partition** (Gazebo Harmonic + ROS 2,
the PX4-SITL-native stack), not Windows/WSL. The seam is what we protect now, not the install.

### D7 — Per-run artifact folder
Each run writes `sim/runs/<timestamp>_<scenario>/` containing `plots/`, `report.md`, `data.csv`,
and `metrics.json` (machine-readable for later scripted comparison). No global parity check against
old notebooks — generated plots/reports are the validation surface.

## Consequences

*   Gains/flags transfer byte-for-byte between `mrac.c` and `sim/` (D1, D3, D5) — the package
    doubles as the firmware-param derivation tool.
*   The controller/adaptive law is plant-agnostic (D3, D6); swapping identified-linear → 6-DOF →
    Gazebo is a one-file plant change.
*   The package is honest about scope: it simulates what was identified (rate loops) and reserves —
    rather than fabricates — the un-identified 6-DOF/position dynamics.
*   Swapping the adaptive law (classical → σ-mod → e-mod → DF-MRAC → NN) stays a one-file change
    in `adaptive_law.py`, consistent with the thesis direction (ADR-0005).
