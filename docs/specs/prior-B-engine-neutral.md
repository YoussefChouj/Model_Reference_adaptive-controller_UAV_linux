# prior-B — Engine-neutral sim pipeline + relative scenario parametrisation

> **STATUS: ✅ DONE 2026-08-10** — recorder/aggregator/manifest are engine-neutral (no
> `gz`/`gazebo`/`sdf`/`urdf` strings, no subprocess; manifest records `plant_name`);
> scenarios_yaml parses relative `u_max`-fraction disturbances via `MagnitudeSpec`;
> `U_MAX_TORQUE` added to `sim/scenarios.py`. `sim/tests/` is now **276 passed / 0 failed**
> (incl. the engine-neutrality + relative-parameterisation tests). Acceptance criteria 2–5
> all verified.
>
> **Pre-reading**: `docs/adr/0014-dimensionless-priors-and-declared-regressor-variants.md` (D5),
> `docs/adr/0012-retire-gazebo-mujoco-plant-ladder.md` (D7).
>
> **Original spec**: `.agent_contracts/prior-B-engine-neutral/spec.md` (gitignored, identical content).

## Goal

Refactor the sim-side recorder, aggregator, manifest, and scenarios_yaml modules to be
**engine-agnostic** (no Gazebo references), and update `sim/scenarios.py` so scenarios
are defined in **relative** magnitudes (fractions of `u_max`, `J`, `e_sat`, ref_model_bw).

The MuJoCo parallel session provides the new plant; this slice provides the infrastructure
to drive any plant behind the `Plant` seam.

## What's already done

- `sim/runner.py`: engine-agnostic `Runner` class (prior-C rewrite)
- `sim/sanity.py`: per-plant SysID gain-matching gate (prior-C rewrite)
- `sim/plant.py`: `PLANT_REGISTRY`, `build_plant()` factory

## What's remaining

### 1. Recorder — strip Gazebo-specific column names

- `sim/recorder.py`: column schema should match `state_dict` returned by `Plant.step()` for any plant
- Remove any Gazebo-specific column names
- Replace `runner.run_experiment` references with the new `loop.tick`-driven runner

### 2. Aggregator — remove Gazebo subprocess calls

- `sim/aggregator.py`: operate on generic schema; remove hard-coded `gz sim --version` subprocess call
- No `gz` / `gazebo` / `sdf` substrings in summary keys or values

### 3. Manifest — split engine-agnostic from Gazebo

- `sim/manifest.py`: engine-agnostic run receipt (plant name, `sim_sha`, scenario, config)
- Remove Gazebo version capture (it was never needed after deletion)

### 4. Scenarios YAML — relative parameterisation

- `sim/scenarios_yaml.py`: add `_RELATIVE_KEYS` set and `MagnitudeSpec` parser
- Convert `disturbance: { value: 0.1, unit: "u_max" }` into per-axis torque
- Remove `vx, vy, vz, phi, theta, psi, p, q, r` from `_INITIAL_KEYS` (let plants default from `Airframe`)

### 5. Scenarios — relative magnitudes

- `sim/scenarios.py`: update existing scenarios to express disturbance torques as fractions of `u_max`
- Inertia offsets as fractions of `J`
- Keep absolute values as fallback if `u_max` unavailable

### 6. Tests

- `sim/tests/test_recorder.py`: engine-neutrality assertions (no Gazebo strings in output)
- `sim/tests/test_aggregator.py`: no subprocess calls
- `sim/tests/test_manifest.py`: no external binary calls
- `sim/tests/test_scenarios_yaml.py`: relative parameterisation parses and runs

## Files to touch

- `sim/recorder.py`
- `sim/aggregator.py`
- `sim/manifest.py`
- `sim/scenarios_yaml.py`
- `sim/scenarios.py`
- `sim/tests/test_recorder.py`
- `sim/tests/test_aggregator.py`
- `sim/tests/test_manifest.py`
- `sim/tests/test_scenarios_yaml.py`

### Must NOT touch

- `sim/plant.py`, `sim/mujoco_bridge.py`, `sim/models/` (parallel MuJoCo session)
- `sim/runner.py`, `sim/sanity.py` (prior-C already rewrote)
- `sim/delay.py`, `sim/priors.py`, `sim/adaptive_law.py`, `sim/regressor.py` (prior-A)
- `API/`, `TASK/`, `BSP/`, `ground_station/`

## Acceptance criteria

1. `pytest sim/tests/ -q` — all green, no regressions
2. A scenario YAML using relative parameterisation loads and runs against `IdentifiedPlant` with equivalent disturbance magnitude to pre-change absolute-value version (within 1% tolerance)
3. Aggregator output contains no `gz` / `gazebo` / `sdf` substrings
4. Manifest module no longer shells out to any external binary
5. `scenarios/*.yaml` files parse with `yaml.safe_load`

## Hard rules

- Do NOT delete `sim/gazebo_bridge.py` — that is a separate slice
- Keep `scenarios.py`'s public API (`step_roll`, `disturbance_rejection`, etc.) intact
- New YAML scenarios are additive