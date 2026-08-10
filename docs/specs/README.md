# Remaining Work Specs

Specs for new session agents to pick up. Each is self-contained — read the spec, execute, report.

**ALL WORK COMPLETE 2026-08-10.** This batch is done; the branch is ready to fold back
into `main`. Summary of the three premises that were falsified by execution (important —
the spec docs record the corrections):

| # | Spec | Priority | Verdict 2026-08-10 |
|---|------|----------|-----------|
| 1 | [prior-D-fix](prior-D-fix-silgate-projection.md) | **HIGH** | ✅ done — `sigma_prior` folded into `grad` before projection + post-update clamp. The spec's "tests are correct, don't touch" premise was **false** (T1 sign, T2/T4 contradiction, stale mutation needle). 16/16 sil_gate. |
| 2 | [prior-03-finish](prior-03-finish-mujoco-crosscheck.md) | HIGH | ✅ done — bridge had a real **roll/pitch swap** the D7 cross-check caught; fixed to firmware-mirror convention. 2 tests added. |
| 3 | [prior-A](prior-A-delay-priors-sigma.md) | MEDIUM | ✅ done — `thrust_delay_s` on RigidBodyPlant, `sigma_prior`/`Theta_prior` sim-side, parity at `sigma=0`. |
| 4 | [prior-B](prior-B-engine-neutral.md) | MEDIUM | ✅ done — recorder/aggregator/manifest engine-neutral, `MagnitudeSpec` relative parameterisation. |
| 5 | [MicoAir follow-ups](micoair-followups.md) | LOW | ⏸️ skipped as agent work — `USART3_THROUGHPUT_TEST` **already `0`** in source; rest is human/decision-gated. |

## Execution order

```
prior-D-fix → prior-03-finish (can run in parallel)
                    ↓
               prior-A → prior-B
```

## Branch

All work on `chore/agent-workflow-hardening`. Commits already landed:
- `0fbe981` docs(prior-E)
- `5fe3657` refactor(prior-C)
- `44871ec` feat(prior-D)
- `4f9365f` feat(prior-03)
- `0910b65` feat(usart3)
- `6f832f9` feat(ground_station)
- `6bd60cc` feat(sim)
- `fd9db1d` docs
- `53eed8c` chore(agent)
- `d2cfce8` docs(sessions)
- `1c2ddc6` feat(scratchpad)

## Test baselines (re-verified 2026-08-10)

| Suite | Passed | Failed | Notes |
|-------|--------|--------|-------|
| `sim/tests/` | **276** | 0 | was 265; +11 from prior-03 tests + prior-A/prior-B additions |
| `ground_station/` | 314 | 0 | run with `--ignore=ground_station/scripts/test_simulator_e2e.py` (that file is a script, not a test — module-level `sys.exit(0)` breaks whole-dir collection) |
| `sil_gate/tests/` | 16 | 0 | unchanged |