# prior-A — Delay wrapper, dimensionless priors, σ_prior attractor (sim-side)

> **Pre-reading**: `docs/adr/0012-retire-gazebo-mujoco-plant-ladder.md` (D6),
> `docs/adr/0013-scenario-conditioned-adaptive-priors.md` (D5),
> `docs/adr/0014-dimensionless-priors-and-declared-regressor-variants.md` (D1–D4).
>
> **Original spec**: `.agent_contracts/prior-A-delay-priors-sigma/spec.md` (gitignored, identical content).

## What's already done

- `sim/delay.py`: `ActuatorDelayBuffer` class exists (107 lines), used by `_AxisSim` in `plant.py`
- `sim/priors.py`: `Prior` dataclass + stubs exist (198 lines)
- `sim/tests/test_delay.py`: exists (needs ≥8 tests)
- `sim/tests/test_priors.py`: exists (needs ≥10 tests)
- `sim/regressor.py`: basis declaration machinery exists

## What's remaining

### 1. Refactor `IdentifiedPlant` and `RigidBodyPlant` to use `ActuatorDelayBuffer`

`_AxisSim` already uses `ActuatorDelayBuffer`. The 6-DOF plants need the same treatment:
- `IdentifiedPlant.step()`: wrap thrust input through the delay buffer
- `RigidBodyPlant.step()`: wrap thrust input through the delay buffer
- Verify: behaviour unchanged (existing tests pass)

### 2. Complete dimensionless priors (`sim/priors.py`)

- `Prior` dataclass: `Theta_tilde`, `plant_tag` (K, p, T), `regressor_variant`
- `convert_to(target_plant_tag)` → raises if cross-plant without explicit conversion
- `RegressorVariant` enum/registry
- Round-trip: `Theta_tilde = K * Theta`, `Theta = Theta_tilde / K`

### 3. Add `sigma_prior` + `Theta_prior` to `sim/adaptive_law.py`

- Add `sigma_prior: float = 0.0` and `Theta_prior: Optional[np.ndarray] = None` to `AxisAdaptiveConfig`
- Add `sigma_prior` and `Theta_prior` fields to `AdaptiveFlags`
- When `sigma_prior > 0` and `Theta_prior is not None`, add `-sigma_prior * (Theta - Theta_prior)` to the gradient update
- Default: `sigma_prior=0.0` → bit-identical to pre-change behaviour
- Add parity tests proving `sigma_prior=0` matches pre-change

### 4. Tests

- `sim/tests/test_delay.py`: ≥8 tests (buffer size, FIFO order, reset, N=0 edge case, multiple axes, no NaN, deterministic)
- `sim/tests/test_priors.py`: ≥10 tests (round-trip Theta↔Theta_tilde, plant-tag preservation, cross-plant conversion rejection, variant mismatch, serialization)
- `sim/tests/test_adaptive_law.py`: parity tests for sigma_prior=0
- `sim/tests/test_plant.py`: delay wrapper refactor doesn't change dynamics

## Files to touch

- `sim/priors.py` — complete the Prior dataclass + conversion
- `sim/regressor.py` — RegressorVariant registry
- `sim/adaptive_law.py` — sigma_prior + Theta_prior fields
- `sim/plant.py` — refactor 6-DOF plants to use ActuatorDelayBuffer (if not already done)
- `sim/tests/test_delay.py` — ≥8 tests
- `sim/tests/test_priors.py` — ≥10 tests
- `sim/tests/test_adaptive_law.py` — sigma_prior=0 parity
- `sim/tests/test_plant.py` — delay refactor regression
- `sim/README.md` — add "Delay wrapper" and "Dimensionless priors" subsections

### Must NOT touch

- `sim/mujoco_bridge.py`, `sim/models/` (parallel MuJoCo session)
- `sim/runner.py`, `sim/sanity.py` (prior-C already rewrote these)
- `API/`, `TASK/`, `BSP/`, `ground_station/`

## Acceptance criteria

1. `pytest sim/tests/ -q` — 263+ baseline, 0 failed (target: ~290 with new tests)
2. `pytest sim/tests/test_delay.py -q` — ≥8 passed
3. `pytest sim/tests/test_priors.py -q` — ≥10 passed
4. `python -m sim.runner --scenario step_roll` with default config produces identical trajectory to pre-change
5. `Prior` refuses cross-plant conversion without explicit `convert_to(target_plant_tag)`

## Key invariants

- `dt = 0.005 s` (200 Hz) — never rescale
- Default behaviour must be bit-identical for all existing scenarios
- `Plant` seam `step(u_dict) → state_dict` is unchanged
- Cross-plant prior application without conversion is the thesis failure mode — do not silently allow it