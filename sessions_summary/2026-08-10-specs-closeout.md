---
session: 2026-08-10-specs-closeout
status: closed
updated: 2026-08-10
superseded_by: null
supersedes: null
---

# Session 2026-08-10 — Executed the 5 remaining-work specs, corrected 3 false premises

**Goal:** execute the self-contained specs in `docs/specs/` (read → execute → report), then
do the final documentation pass and leave the repo consistent.

**Outcome:** 4 of 5 specs **done**, 1 (MicoAir) skipped as agent work because its only safe
code edit was already satisfied. **Three of the five specs contained falsified premises** —
the docs now record the corrections rather than the aspirational "it's done" framing. Test
count re-verified: `sim/tests/` **276** passed, `ground_station/` **314**, `sil_gate/tests/` **16**.

Per `sessions_summary/POLICY.md`, this is a `closed` session: the block is delivered. The
spec docs (`docs/specs/*.md`) carry the full detail; this file is the archive entry.

## What ran

The batch, in the recommended order (parallel pair → serial tail):

| Spec | Verdict | Key deliverable |
|------|---------|-----------------|
| prior-D-fix | ✅ done | `sigma_prior` folded into `grad` before `MRAC_ProjectGradient` + post-update `Theta` clamp |
| prior-03-finish | ✅ done | MuJoCo bridge roll/pitch swap **fixed** + 2 D7 oracle cross-check tests |
| prior-A | ✅ done | `thrust_delay_s` transport-delay buffer on RigidBodyPlant; `sigma_prior`/`Theta_prior` sim-side |
| prior-B | ✅ done | recorder/aggregator/manifest engine-neutral; `MagnitudeSpec` relative u_max parameterisation |
| MicoAir | ⏸️ skipped | `USART3_THROUGHPUT_TEST` **already `0`** at `TASK/send_data.c:472`; rest human/decision-gated |

## Falsified premises (the load-bearing lesson)

These specs were written as "the class is done, just finish the last step". Execution
showed the *premises* were wrong — each correction is recorded in the spec file itself:

1. **prior-D**: the spec claimed `API/tests/test_mrac_sigma_prior.c` was correct and
   must-not-touch. It was internally inconsistent: T2 asserted convergence to a prior
   above several slots' `What_limit` (impossible under any projection-respecting fix), T1
   had a sign error (bias weight drives negative, so `> 1e-4` always failed), and the
   mutation needle targeted a `y=` line the fold removes. Fixed all three → 16/16 sil_gate.
2. **prior-03**: the spec claimed `sim/mujoco_bridge.py` was "done, don't touch". The D7
   cross-check **falsified that** — the bridge computed net torque via a raw cross-product,
   but the shared firmware-mirror mixing maps roll_cmd→PITCH differential at X-frame motor
   positions, so the bridge fed roll_cmd→pitch. A ~100 % roll-axis disagreement the seam
   tests could never catch. Fixed to the `_motor_thrust_to_force_torque` convention.
3. **prior-B test baseline**: the README's `sim/tests/` was stale (265). Re-ran: **276**.

## Files this batch touched

- `API/mrac.c`, `API/tests/test_mrac_sigma_prior.c`, `sil_gate/tests/test_mrac_sigma_prior.py` (prior-D)
- `sim/mujoco_bridge.py`, `sim/tests/test_plant.py` (prior-03)
- `sim/plant.py`, `sim/README.md`, `sim/adaptive_law.py`, `sim/tests/` (prior-A)
- `sim/manifest.py`, `sim/recorder.py`, `sim/aggregator.py`, `sim/scenarios_yaml.py`,
  `sim/scenarios.py`, `sim/runner.py`, `scenarios/hover.yaml`, `scenarios/step_roll.yaml` (prior-B)
- `docs/specs/*.md` (status headers + corrections), `docs/specs/README.md` (this file's index)

## Gotchas re-confirmed

- `ground_station/scripts/test_simulator_e2e.py` is a **script**, not a test — module-level
  print + `sys.exit(0)` breaks whole-dir `pytest ground_station/` collection. Run with
  `--ignore=<that file>`. (Pre-existing; not introduced this batch.)
- graphify's `_rebuild_code` hook target isn't installed in `.venv` (or system python) —
  not run this session.

## Next / outstanding

None for this batch. The branch `chore/agent-workflow-hardening` is ready to fold into
`main`. Human-gated MicoAir items (in-flight re-measure, USART3 command-dispatch decision,
com0com bridge, TX-error recovery) remain on the operator's side per the hard safety
constraints — never routed through an agent pipeline.