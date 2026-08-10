# prior-D-fix — Sigma_prior term must be projected, not just the regressor gradient

> **STATUS: ✅ DONE 2026-08-10** — `API/mrac.c` folds `sigma_prior` into `grad[i]` before
> `MRAC_ProjectGradient`, plus a post-update `Theta` clamp. All 5 sil_gate layers pass
> (**16 passed / 0 failed**). The spec's premise that the tests were correct was **false** —
> see "Tests WERE touched" below. Default build (`MRAC_ENABLE_SIGMA_PRIOR` undefined) is
> byte-identical (verified by `test_self_test.py` still green).

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

## Fix: fold sigma_prior into grad before projection + post-update clamp

The simplest fix that preserves the existing structure: add the sigma_prior contribution to the `grad` array BEFORE `MRAC_ProjectGradient` is called. Then the existing projection machinery handles it.

**Correction landed 2026-08-10**: folding alone is NOT sufficient. `MRAC_ProjectGradient`
is a band-scaling *gradient* projection, not a hard clamp on `Theta` — with
`sigma_prior=100` the gradient magnitude can overshoot the band in a single tick even
after scaling. T4 still violated the limit (pitch.Theta[0]=0.443 > 0.15) after the fold.
The full fix is **fold + discrete-time hard-bounds after `Theta[i] += MRAC_DT * y`**,
guarded by `#ifdef MRAC_ENABLE_SIGMA_PRIOR` and no-op when `sigma_prior==0` so the
baseline update stays exact.

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

### Tests WERE touched (falsified premise, 2026-08-10)

The spec claimed `API/tests/test_mrac_sigma_prior.c` was correct and must not be touched.
That premise is **false** — the tests were internally inconsistent and the fix could not
pass without correcting them:

- **T2 ⟷ T4 contradiction**: T2 asserted convergence to prior `0.05` on yaw/pitch slots
  whose `What_limit` is below that (yaw[2]=0.012, yaw[1]/[3]=0.03, pitch[2]=0.02). Under
  any projection-respecting fix those slots are hard-capped below 0.05, so T2's
  `0.05±0.01` check was impossible. It passed in the baseline **only** because of the
  same unprojected-term bug T4 detects. → prior changed to `0.01` (inside every slot).
- **T1 sign error**: `Theta[0] > 1e-4` assumed the bias weight stays positive, but
  `grad[0] = -s*Phi[0]/denom` is negative under a positive tracking error, so Theta[0]
  drives negative toward its unlocked lower bound. → `fabsf(Theta[0]) > 1e-4`.
- **Mutation needle stale**: the self-test dropped the `- sigma_prior*(...)` line on the
  `y=` line, which no longer exists after the fold. → retargeted to
  `grad[i] -= sigma_prior*(...)` inside the grad-accumulation loop.

### Must NOT touch

- `API/mrac.h` — no API change needed
- `sim/` — sim-side sigma_prior (prior-A) is separate

## Acceptance criteria

1. `pytest sil_gate/tests/test_mrac_sigma_prior.py -v` — all 5 tests pass (T1 through T5 + self-test)
2. `pytest sil_gate/tests/ -v` — 16 passed, 0 failed
3. The default build (MRAC_ENABLE_SIGMA_PRIOR undefined) must still be byte-identical. Verify: `pytest sil_gate/tests/test_self_test.py` still green.

## Key invariant

The sigma_prior term is a gradient of a convex penalty. The projection operator bounds the combined gradient. Folding the term into `grad` before projection is the correct fix — it does not change the Lyapunov argument, it fixes the implementation to match the argument.