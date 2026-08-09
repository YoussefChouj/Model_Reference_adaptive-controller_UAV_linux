# 0012 - Retire Gazebo; MuJoCo + the plant ladder for sim-to-real weight transfer

*   **Status:** Accepted
*   **Date:** 2026-08-05
*   **Amends:** ADR-0006 D6 (which reserved Gazebo as the Phase-2 high-fidelity plant)
*   **Supersedes:** `.agent_contracts/mbd_workflow/04b-gazebo-bringup.md` and the Gazebo
    backend half of `04c-agent-driven-experiments.md` (the *runner* half of 4c survives —
    see D7)
*   **Depends on:** ADR-0006 (sim package + `Plant` seam), `docs/sysid_results.md`
*   **Enables:** ADR-0013 (scenario-conditioned adaptive priors)

## Context

ADR-0006 D6 reserved `GazeboPlant` as a stub, with real bring-up deferred to a later
session. Specs 4b and 4c executed that bring-up. After two sessions the pipeline is
blocked on three defects, none of which are control-theory problems:

| Blocker | Nature | Session |
|---|---|---|
| `<include><pose>` silently ignored; model spawns at z≈0.024 interpenetrating the ground | Upstream gz-sim 10 (jetty) defect | 2026-08-05 |
| GUI hangs at "requesting list of world names" | UFW blocks gz-transport UDP multicast 224.0.0.0/4 | 2026-08-05 |
| White-screen freeze loading X500 DAE/PBR meshes | Ogre2 PBR on a GPU-less VM | 2026-08-05 |

A fourth (dynamic spawn via the `EntityFactory` service times out) is caused by
`gz sim -g` forking server and GUI into a private transport partition unreachable from
external Python.

The cost incurred is **2,049 LOC** (`gazebo_bridge.py` 762, `runner.py` 460, `urdf.py`
318, `urdf_conversion.py` 220, `spawn_drone.py` 150, `sanity.py` 139), five test files,
`sim/worlds/`, and 27 MB of `sim/models/`. Nothing in the production path imports any of
it; only its own tests do.

### Why the original justification no longer holds

ADR-0006 D6 justified Gazebo as "a higher-fidelity 6-DOF model." That requirement was
subsequently satisfied *inside* `sim/` by `RigidBodyPlant` (spec 4a): full 6-DOF
quaternion rigid body with mixer, motor-lag LPF, and gyroscopic coupling, covered by 17
tests including angular-momentum conservation, cross-axis gyroscopic response,
inertia-asymmetry period ratio, and free-fall = g. The justification was silently
consumed while the Gazebo work continued.

### What Gazebo is actually mature at

Gazebo's maturity is in **ROS 2 robot integration**: sensor drivers, perception, SLAM,
manipulation, hardware-abstraction plumbing. This project has no ROS 2. It has STM32F4
firmware and a Python firmware-parity model. The integration tax was paid in full and
none of the integration benefit was collected.

### The requirement that actually changed

The thesis direction (ADR-0013) is **sim-to-real transfer of adaptive weights**: learn
`What` per scenario in simulation, apply it on the real drone as a scenario-conditioned
prior. This makes *gain fidelity*, not *visual or contact fidelity*, the binding
requirement — and it inverts the usual "third-party engine = credibility" argument:

> `K` and the mixer torque effectiveness are coupled, so `K` is a lumped input→output
> gain, **not** a physical inertia — `docs/sysid_results.md`

MRAC weights are dimensional: `What` multiplies `Φ` to produce `u_ad` in Nm, so the ideal
`θ*` is a function of the plant's lumped input→output gain. A generic X500 SDF with
guessed inertia and a generic motor model is a *less* faithful model of JX_FLY than the
transfer function identified **from** JX_FLY (roll: `K ≈ 165`, `p ≈ 19.8 rad/s`,
`T ≈ 15 ms`, VAF ≈ 99 %, spread < 0.3 % over 7 multisine runs). An independent engine
buys credibility only if its own parameters are validated; nobody validated that X500
against this airframe.

## Decisions

### D1 — Retire Gazebo entirely
Commit the current working tree, then delete the six Gazebo-coupled modules, their five
test files, `sim/worlds/`, and `sim/models/`. Git history is the archive; the work is
recoverable by SHA. Rationale: dead code in-tree is not free — it costs test-suite time,
27 MB of repo, and (demonstrably) agent context pollution about which pipeline is live.

### D2 — MuJoCo replaces Gazebo behind the existing `Plant` seam
`MujocoPlant` implements `step(u_dict) -> state_dict` exactly as ADR-0006 D3 specifies.
Chosen because it is pip-installable (`mujoco` 3.11.0, prebuilt wheels), runs **in
process** (no subprocess boot, no transport bus, no multicast, no partition), is
deterministic and fast enough for sweeps, renders headless offscreen on a GPU-less VM,
and a model of this airframe already exists (sourced from a classmate). The `Plant` seam
is unchanged — this is the one-file plant swap ADR-0006 promised.

### D3 — `RigidBodyPlant` is retained as the independent oracle
Its own docstring already assigns it this role ("the analytic plant is the **independent
oracle** against which Gazebo is cross-checked"); only the engine name changes. Two
independent 6-DOF implementations agreeing is a genuine validation asset. It is not
retired.

### D4 — The plant ladder, with per-plant identification
Four plants sit behind the seam, in increasing order of physical reality:

| Plant | Role | Identified parameters |
|---|---|---|
| `IdentifiedPlant` | Fast search bench; **gain-matched by construction** | `sysid_results.md` (free flight) |
| `MujocoPlant` | 6-DOF coupling, aggressive maneuvers, rendering | must be measured (D5) |
| `RigPlant` | Constrained 4-DOF hardware (roll/pitch/yaw/z), safe validation | must be measured on the rig |
| Free flight | Final evidence | `sysid_results.md` |

`RigidBodyPlant` sits alongside as the oracle, not as a rung.

### D5 — Gain matching is established by measurement, not assertion
Any plant used to learn priors must be characterised with the **existing** SysID
pipeline (`ground_station/scripts/sysid_analysis.py`, multisine excitation, model
structure `G(s) = K/(s(1+s/p))·e^{−sT}`) and its `(K, p, T, VAF)` recorded in
`docs/sysid_results.md` alongside the free-flight numbers. This becomes an automated
gate, replacing the Gazebo-era hover sanity check in `sim/sanity.py`. Rationale: it
reuses tooling already trusted, produces a defensible VAF number for the thesis, and
converts "the sim is close enough" from an opinion into a measurement.

### D6 — A transport-delay buffer is mandatory on every plant used for prior learning
`RigidBodyPlant` currently models motor lag as a 1st-order LPF but has **no transport
delay**; MuJoCo has none natively. ADR-0006 D4 already established why this matters:

> The delay is *not* cosmetic — it caps how aggressively the adaptive law can learn;
> dropping it makes the sim falsely stable.

Weights learned on a delay-free plant are systematically over-confident. The integer
delay ring buffer (`N = round(T/dt)`) is lifted out of `_AxisSim` into a reusable
actuator-input wrapper applied to every 6-DOF plant.

### D7 — The agent-facing run surface is engine-agnostic and survives untouched
`recorder.py`, `aggregator.py`, `manifest.py`, `scenarios_yaml.py`, `plot_trajectory.py`,
`metrics.py`, `run.py` and `experiments.py` contain no Gazebo coupling and are kept
as-is. This is the empirical proof that the physics engine was never the load-bearing
part of the "AI-agent-driven experiments" requirement — the runner was, and the runner
already exists and is green.

### D8 — Priors are plant-tagged; cross-plant transfer requires an explicit scaling
Because `K_identified ≠ K_mujoco ≠ K_rig ≠ K_free`, every learned prior is recorded with
the plant identity and the `(K, p, T)` under which it was learned. Applying a prior
across plants without a stated scaling is a defect, not a shortcut.

## Consequences

*   **Positive.** ~2,049 LOC and 27 MB deleted. No subprocess, no gz-transport bus, no
    UDP multicast, no firewall dependency, no GPU dependency, no `sudo` requirement, no
    stray-process hygiene ritual. Runs go from seconds-per-boot to in-process. Sweeps
    become tractable, which is the actual requirement for ADR-0013.
*   **Positive.** Two of the three chosen scenario families (parametric plant change,
    external disturbance) already run today on `IdentifiedPlant` via
    `scenarios.inertia_offset` and `scenarios.disturbance_rejection`, so the ADR-0013
    loop is not blocked on MuJoCo bring-up.
*   **Negative.** Contact, ground effect and crash physics are out of scope. Accepted:
    adaptation during contact is a separate research problem, the runtime scenario
    detector cannot act mid-crash, and nothing in the current thesis direction needs it.
*   **Negative.** MuJoCo model provenance is external (classmate's MJCF). D5 mitigates
    this by forcing measurement before use.
*   **Cost.** `sim/sanity.py` is rewritten from a Gazebo hover gate into the SysID
    calibration gate of D5. The delay wrapper (D6) is new work that would have been
    required for Gazebo too.
*   **Reversible.** If a future requirement genuinely demands contact physics or ROS 2
    integration, Gazebo is recoverable from git history and the `Plant` seam accepts it
    unchanged.

## Validation

1.  `pytest sim/` green after deletion, with the five Gazebo test files removed and no
    other test referencing the deleted modules.
2.  `MujocoPlant` passes the same seam-conformance tests as `RigidBodyPlant`
    (`test_seams.py`, `test_rigid_body_plant.py::test_seam_conformance_*`).
3.  MuJoCo multisine → `sysid_analysis.py` → `(K, p, T)` recorded and compared against
    `165 / 19.8 rad/s / 15 ms` with the VAF reported. Gate, not vibe check.
4.  Delay wrapper: a step response on `RigidBodyPlant` with `N = 3` shows the same
    3-sample dead time as `IdentifiedPlant`.
5.  `RigidBodyPlant` vs `MujocoPlant` agreement on a common scenario, reported as a
    two-engine cross-check.
