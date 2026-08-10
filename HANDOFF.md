# Handoff — prior-00/00b work (`prior/00-00b-parity-fix` branch)

## Branch

```
prior/00-00b-parity-fix
```
On GitHub: `https://github.com/YoussefChouj/Model_Reference_adaptive-controller_UAV/tree/prior/00-00b-parity-fix`

```
git fetch origin
git checkout prior/00-00b-parity-fix
```

---

## What was done

### Spec 00 — `What_lower_limit` sign-gate (investigation, no code change)

Confirmed from firmware source (`API/mrac.c`, `API/mrac.h`) that on the **active build**:

| Finding | Value | Source |
|---------|-------|--------|
| Slots 1–5 lower bound | `0.0` on every axis | file-scope zero-init, no memset |
| Slot 0 lower bound | `-What_limit[0]` for pitch/roll/yaw; `0.0` for z | `mrac.c:353–355` |
| Gradient clamp | Clamps (zeros gradient at bound) | `mrac.c:113, 129–131` |
| `INCLUDE_CONTROL_IN_REGRESSOR` | `1` | `mrac.h:66` |
| `MAX_NUM_BASIS` | `6` | `mrac.h:85` |
| Active build | `PAYLOAD_LIGHT` | `mrac.h:25` |

**Binary answer: slots 1–5 cannot hold negative weights on any axis today.** A symmetric unlock
(firmware change) is a hard prerequisite for spec 05.

### Spec 00b — Sim parity fix (code change)

**Root cause**: `sim/adaptive_law.py` carried a stale comment ("firmware never sets it")
and wrong default (`[0.0] * 6` for all axes). Firmware had actually unlocked slot 0 for
pitch/roll/yaw at `mrac.c:353–355` but the sim was never updated.

**Files changed** (all committed):

| File | Change |
|------|--------|
| `sim/adaptive_law.py` | `for_axis()`: slot 0 unlocked for pitch/roll/yaw; z explicit `[0.0]*6` with comment |
| `sim/tests/test_adaptive_law.py` | Parity assertions updated for all 4 axes |
| `sim/experiments.py` | Sweep A docstring updated — corrected parity is now the baseline |
| `sim/README.md` | Phase-1 findings rewritten against measured before/after data |
| `docs/decisions.md` | ADR-0014 appended: drift recorded, prevention = parity test |
| `docs/adr/0012-0014.md`, `docs/glossary.md` | New ADR files and glossary (context for the whole prior_transfer pipeline) |
| `SESSION_SUMMARY_2026-08-05.md` | Session artifact (Gazebo hybrid SDF work from 2026-08-05 morning) |

**Test results**: `pytest sim/tests/` → **206 passed, 3 skipped** (no regressions).

---

## Empirical result (the deliverable)

Ran `disturbance_rejection` on roll/pitch/yaw before and after the fix:

| Axis | Config | rmse_track | max_abs_err | θ₀ final | θ₀ min |
|------|--------|------------|-------------|----------|--------|
| roll | OLD (all 0) | 0.2982 | 0.5216 | +0.00162 | 0.0 |
| roll | NEW (slot 0) | 0.2885 | 0.5205 | **−0.00143** | **−0.00220** |
| pitch | OLD | 0.2968 | 0.5036 | +0.00128 | 0.0 |
| pitch | NEW | 0.2878 | 0.5023 | **−0.00146** | **−0.00215** |
| yaw | OLD | 0.2771 | 0.3226 | 0.0 | 0.0 |
| yaw | NEW | 0.2703 | 0.3194 | **−0.00432** | **−0.00432** |

**Delta: roll −3.3%, pitch −3.0%, yaw −2.4%.**

**Verdict**: Real but modest improvement. The bias weight now correctly goes negative
(physically correct response to a positive-rate standing disturbance). However, **`e_deadzone = 0.05`
is still the dominant suppressor** — adaptation halts ~0.2 s after the disturbance onset.
This is a null result on the hypothesis "bias unlock alone makes MRAC produce meaningfully
better long-term disturbance rejection". The open research question is unlocking slots 1–5
(Sweep A).

---

## What to do next

Per `.agent_contracts/prior_transfer/README.md` wave structure:

| Task | Blocks on | Wave | Status |
|------|-----------|------|--------|
| `prior-01-retire-gazebo` | 00 | 1 | May start now (parity fix landed) |
| `prior-02-delay-wrapper` | 01 | 2 | After 01 lands |
| `prior-03-mujoco-plant` | 01 | 2 | After 01 lands |
| `prior-05-prior-factory` | 00b | 2 | **May start now** |
| `prior-07-rig-model` (Phase A) | 00 | 2 | May start now |
| `prior-04-sysid-gate` | 02, 03 | 3 | After 02+03 merged |
| `prior-06-injection-seam` | 05 | 3 | After 05 lands |

---

## Instructions for the resuming agent

1. **Read these first** (in order):
   - `.agent_contracts/prior_transfer/README.md` — shared context, wave structure, ownership map
   - `.agent_contracts/prior-00-sign-gate/journal.md` — conductor's findings with file:line evidence
   - `.agent_contracts/prior-00b-sim-parity-fix/journal.md` — implementer journal with before/after data
   - `docs/glossary.md` — shared vocabulary

2. **Key invariants** (do not change without a spec):
   - `dt = 0.005 s` (200 Hz), never rescale gains
   - `Plant` contract `step(u_dict) → state_dict` is unchanged
   - Every run writes `sim/runs/<timestamp>_scenario/`
   - `pytest sim/` must be green at the end of every task
   - Never touch the target board

3. **File ownership map** — `prior-05` and `prior-06` collide on `sim/adaptive_law.py`.
   `prior-00b` has already landed; `prior-05` must not start until `prior-00b` is merged.
   Since you've merged `prior/00-00b-parity-fix` into your checkout, you're clear to proceed.

4. **`What_lower_limit` constraint**: slots 1–5 are locked at 0 on every axis.
   **Do not unlock them** — that is Sweep A's open research question.
   If a task tries to change this without a spec, reject it.

5. **Soft constraint on `e_deadzone`**: empirical result shows it dominates adaptation.
   Any task that modifies it should note this in its journal.

6. **To run the sim tests**:
   ```bash
   cd Model_Reference_adaptive-controller_UAV
   . .venv/bin/activate
   python -m pytest sim/tests/ -q
   ```

7. **To reproduce the before/after comparison**:
   ```python
   PYTHONPATH=. python - <<'EOF'
   import numpy as np
   from dataclasses import replace
   from sim import scenarios
   from sim.adaptive_law import AdaptiveFlags, AxisAdaptiveConfig
   from sim.run import run

   def make_cfg(axis, slot0_unlocked=False):
       base = AxisAdaptiveConfig.for_axis(axis)
       if not slot0_unlocked:
           return replace(base, What_lower_limit=[0.0]*6)  # OLD (bug)
       return base  # NEW (correct parity)

   for axis in ["roll", "pitch", "yaw"]:
       r_old = run(scenarios.disturbance_rejection(axis), config=make_cfg(axis, False), write_artifacts=False)
       r_new = run(scenarios.disturbance_rejection(axis), config=make_cfg(axis, True), write_artifacts=False)
       print(f"{axis}: old rmse={r_old['metrics']['rmse_track']:.4f}  new rmse={r_new['metrics']['rmse_track']:.4f}")
   EOF
   ```

8. **Uncommitted work remaining on `chore/agent-workflow-hardening`**:
   - `sim/runner.py`, `sim/gazebo_bridge.py`, `sim/models/jx_fly/jx_fly.urdf` — Gazebo hybrid SDF work
   - `wiki/` — knowledge base updates
   - `sim/models/jx_fly/materials/`, `sim/models/jx_fly/meshes/`, `sim/models/jx_fly/model.sdf` — new Gazebo model files
   - `sim/plot_trajectory.py`, `sim/spawn_drone.py` — Gazebo helper scripts
   - `docs/literature-review-brief.md`, `docs/literature-review-findings/` — research artifacts

   These are **not** on the `prior/00-00b-parity-fix` branch and need separate handling.
