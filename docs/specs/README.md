# Remaining Work Specs

Specs for new session agents to pick up. Each is self-contained — read the spec, execute, report.

| # | Spec | Priority | Est. effort | Blocks on |
|---|------|----------|-------------|-----------|
| 1 | [prior-D-fix](prior-D-fix-silgate-projection.md) | **HIGH** | Small (1 file, 1 bug) | — |
| 2 | [prior-03-finish](prior-03-finish-mujoco-crosscheck.md) | HIGH | Small (2 tests) | — |
| 3 | [prior-A](prior-A-delay-priors-sigma.md) | MEDIUM | Medium (4 files + tests) | prior-D-fix (sim side mirrors firmware fix) |
| 4 | [prior-B](prior-B-engine-neutral.md) | MEDIUM | Medium (5 files + tests) | prior-A (scenarios use dimensionless priors) |
| 5 | [MicoAir follow-ups](micoair-followups.md) | LOW | Mixed (human + code) | — |

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

## Test baselines

| Suite | Passed | Failed |
|-------|--------|--------|
| `sim/tests/` | 263 | 0 |
| `ground_station/` | 314 | 0 |
| `sil_gate/tests/` | 14 | 2 (prior-D) |