# prior-03-finish — MujocoPlant × RigidBodyPlant D7 oracle cross-check

> **STATUS: ✅ DONE 2026-08-10** — bridge torque convention **fixed** (was a roll/pitch
> swap — see "CORRECTION" below) and the two D7 oracle tests added to
> `sim/tests/test_plant.py`. MuJoCo stays the independent physics INTEGRATOR; the
> per-motor → wrench mapping is a shared model input. `sim/tests/` is now **276 passed /
> 0 failed**. This cross-check did exactly what ADR-0012 D7 was designed to do — it
> caught a real mixing-sign bug neither seam test could.
>
> **Status**: MujocoPlant class + PLANT_REGISTRY + bridge exist and pass seam tests.
> This spec covers the remaining work: the D7 oracle cross-check against RigidBodyPlant.
>
> **Pre-reading**: `docs/adr/0012-retire-gazebo-mujoco-plant-ladder.md` (D2, D3, D7).

## What's already done

- `sim/plant.py`: `MujocoPlant` class, `PLANT_REGISTRY`, `build_plant()`
- `sim/mujoco_bridge.py`: `MujocoBridge` + `MujocoBridgeConfig` (330 lines)
- `sim/models/jx_fly/jx_fly_mujoco.xml`: MuJoCo model (52 lines)
- `sim/tests/test_seams.py`: 4 MujocoPlant seam tests (subclass, registry, deterministic reset, importable)
- `sim/tests/test_mujoco_bridge.py`: 7 bridge unit tests (construct, missing XML, reset, hover, thrust, motor LPF, determinism)
- `pytest sim/tests/`: **263 passed, 0 failed**

## What's remaining

### 1. Cross-check: MujocoPlant vs RigidBodyPlant on a common scenario

ADR-0012 D7 says: "Two independent 6-DOF implementations agreeing is a genuine validation asset."

Write a test that:
- Instantiates both `MujocoPlant(dt=0.005)` and `RigidBodyPlant(dt=0.005)`
- Drives both with the same torque input `u = {"roll": 0.01, "pitch": 0.0, "yaw": 0.0, "z": 9.7}` (hover-ish thrust + small roll torque)
- Runs for 200 ticks (1 second)
- Compares the resulting state vectors (roll rate `p`, pitch rate `q`, yaw rate `r`, vertical velocity `vz`)
- **Acceptance**: the two plants agree within 20% on the steady-state rate response. The analytic plant is a rigid-body model; MuJoCo is a physics engine. They won't be bit-identical but should agree on the *sign and order of magnitude* of the rate response.

### 2. Step-response validation

Write a smoke test that:
- Creates a `MujocoPlant`
- Runs a step in roll torque: 0 → 0.02 Nm at t=0.1s, hold for 0.5s
- Verifies: roll rate `p` increases (positive), pitch/yaw rates stay near zero (no cross-coupling sign error), vertical velocity `vz` stays near hover (thrust is correct)
- **Acceptance**: no NaN, no instability, quaternion stays normalized, correct sign on all axes.

### 3. File to touch

- `sim/tests/test_plant.py` — add `test_mujoco_vs_rigid_body_roll_step` and `test_mujoco_step_response_smoke`

### CORRECTION — bridge was NOT done (2026-08-10)

The spec claimed `sim/mujoco_bridge.py` was done and must not be touched. The D7
cross-check **falsified that**: the bridge computed net torque via a raw
`position × force` cross-product, while the shared firmware-mirror mixing maps
`roll_cmd → [+,-,-,+]` — a PITCH differential at the X-frame motor positions — and
`pitch_cmd → [-,-,+,+]` (a −ROLL differential). So the bridge produced `roll_cmd →
pitch` and `pitch_cmd → roll` (τ_roll=0, τ_pitch=−0.004 mj vs τ_roll=+0.001 rigid for
roll_cmd=1). RigidBodyPlant's `_motor_thrust_to_force_torque` labels the same
patterns roll/pitch to match firmware, so the two plants disagreed by ~100% on the
roll axis.

**Fix**: `sim/mujoco_bridge.py` now computes the net body wrench using the SAME
per-motor → torque convention as `_motor_thrust_to_force_torque` (roll =
(F1+F4−F2−F3)·r/4, pitch = (F1+F2−F3−F4)·r/4, yaw via K_yaw = Izz/1872), applied as a
body wrench. MuJoCo stays the independent physics INTEGRATOR; the per-motor → wrench
mapping is a shared model input (ADR-0012 D7). After the fix the two plants agree on
the roll step to **~1%** (p) and **~5%** (vz).

Also: the spec's physical constants (mass 988.5 g) are **stale** — `CANONICAL_AIRFRAME`
is 1.2961 kg, so the cross-check uses hover thrust `m·g = 12.7 N` (not the spec's
z=9.7, which was 988.5 g·g).

### Must NOT touch

- `sim/plant.py`, `sim/models/`
- `API/`, `TASK/`, `BSP/`, `ground_station/`

## Acceptance criteria

1. `pytest sim/tests/test_plant.py -v -k mujoco` — 2 new tests pass
2. `pytest sim/tests/ -q` — 265 passed, 0 failed (the 263 baseline + 2 new)
3. Both new tests run on Windows without GPU (MuJoCo offscreen rendering)

## Physical constants

- Mass: 988.5 g
- Inertia: Ixx=0.00843, Iyy=0.00926, Izz=0.01485 (from `docs/sysid_results.md`)
- dt = 0.005 s (200 Hz)
- Motor layout: X-configuration, arm length ~0.1 m