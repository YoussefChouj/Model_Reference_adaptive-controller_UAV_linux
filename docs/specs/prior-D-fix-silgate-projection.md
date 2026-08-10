# prior-D-fix — Sigma_prior term must be projected, not just the regressor gradient

> **Root cause**: The sigma_prior attractor term is added to `y` **after** `MRAC_ProjectGradient`
> clamps the gradient. With a large sigma_prior, the term pushes Theta past What_limit.
> The 2 failing sil_gate tests are correctly detecting this real bug.
>
> **Pre-reading**: `API/mrac.c` lines 280–310 (the `MRAC_UpdateAxis` gradient update block).

## The bug

In `API/mrac.c`, the gradient update is:

```
MRAC_ProjectGradient(grad, Theta, ...)   // clamps grad[i] only
for i:
    y = gamma * (grad - sigma_lf*(...) - sigma_eff*Theta - sigma_prior*(Theta - Theta_prior))
    Theta[i] += dt * y                    // sigma_prior term unprojected → can exceed What_limit
```

The sigma_prior term is gradient-style (it's the gradient of `(1/2)*sigma_prior*||Theta - Theta_prior||^2`), so it SHOULD be projected. The regressor gradient `grad` is projected, but the sigma_prior contribution is added after projection and therefore bypasses it.

**Evidence**: T4 test sets `sigma_prior = 100`, `Theta_prior = [1.0, 1.0, ...]`, and `What_limit = [0.15, 0.05, ...]`. Theta converges to ~0.998 (near the prior) instead of being capped at 0.15. The projection is not touching the sigma_prior contribution.

## Fix: fold sigma_prior into grad before projection

The simplest fix that preserves the existing structure: add the sigma_prior contribution to the `grad` array BEFORE `MRAC_ProjectGradient` is called. Then the existing projection machinery handles it.

In `MRAC_UpdateAxis`, inside the `#ifdef MRAC_ENABLE_SIGMA_PRIOR` block:

```c
// BEFORE projection (currently around line 280):
for (i = 0; i < num_basis; i++) {
    grad[i] -= sigma_prior * (state->Theta[i] - Theta_prior[axis_id][i]);
}
MRAC_ProjectGradient(grad, state->Theta, num_basis, ...);  // now projects the combined gradient
```

Then remove the sigma_prior term from the `y = gamma * (...)` line (lines 288–299 and 301–308), since it's now folded into `grad[i]`.

**Important**: The sigma_prior contribution to grad must be added BEFORE the deadzone/hard-freeze check, which is correct — the deadzone gates whether adaptation runs at all; the sigma_prior term is part of adaptation.

## Files to touch

- `API/mrac.c` — move sigma_prior term from the `y = gamma * (...)` line to `grad[i]` before `MRAC_ProjectGradient`

### Must NOT touch

- `API/mrac.h` — no API change needed
- `sil_gate/`, `API/tests/test_mrac_sigma_prior.c` — the tests are correct; they should pass after the fix
- `sim/` — sim-side sigma_prior (prior-A) is separate

## Acceptance criteria

1. `pytest sil_gate/tests/test_mrac_sigma_prior.py -v` — all 5 tests pass (T1 through T5 + self-test)
2. `pytest sil_gate/tests/ -v` — 16 passed, 0 failed
3. The default build (MRAC_ENABLE_SIGMA_PRIOR undefined) must still be byte-identical. Verify: `pytest sil_gate/tests/test_self_test.py` still green.

## Key invariant

The sigma_prior term is a gradient of a convex penalty. The projection operator bounds the combined gradient. Folding the term into `grad` before projection is the correct fix — it does not change the Lyapunov argument, it fixes the implementation to match the argument.