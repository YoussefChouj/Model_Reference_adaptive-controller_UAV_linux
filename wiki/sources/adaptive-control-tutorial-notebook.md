---
title: Adaptive Control Tutorial Notebook
type: source
tags: [adaptive-control, tutorial, mrac, rbf, sigma-modification, projection, performance-recovery, mass-spring-damper]
created: 2026-04-14
updated: 2026-06-20
sources:
  - "C:/Users/Acer/Desktop/Pich_yaw_roll_experimental_drone_setup/[Demonstration] - Microcontroller Control - Experiment 4 - Cascaded PID - dShot - FreeRTOS - Suspended/Adaptive_Control_Tutorial.ipynb"
---

18-cell progression notebook: scalar toy system → 2D mass-spring-damper. Each cell isolates one concept. Common settings across all cells: `dt = 0.005 s`, Euler integration. Treat all code cells as user-validated baselines.

---

## Cell-by-cell experiment map

### Cell 0 — Fixed-gain baseline (no adaptation)

**Plant:** `ẋ = wx + u`, `w = 5` (unknown), `u = -kx`, `k = 10`, `ft = 20 s`, `x₀ = 1`

**Purpose:** Confirm that a fixed gain `k > w` stabilizes the scalar unstable plant. With `k = 10 > w = 5`, state converges to zero.

**Finding:** Works only because `k` was manually chosen larger than `w`. If `w` is unknown or time-varying, this breaks — motivating adaptation.

---

### Cell 1 — Adaptive gain (regulation)

**Law:** `u = -ŵx`, `ŵ̇ = γx²`, `γ = 25`, `ŵ₀ = 0`, `w = 5`

**Update order:** control → weight update → state update (crucial: weight is updated after control is applied, not before).

**Finding:** ŵ converges toward w and state stabilizes. Increasing γ speeds up initial convergence but can cause oscillation if too large. The weight drifts upward past the true `w = 5` because there is no leakage — the Lyapunov proof guarantees state convergence, not weight convergence.

---

### Cell 2 — Point-reference tracking

**Law:** `u = -α(x - c) - ŵx`, `ŵ̇ = γxe`, `e = x - c`, `α = 2`, `γ = 50`

**Command:** `c = 1` for `t ≤ 5`, `c = -1` for `t > 5`

**Finding:** Tracks step commands but steady-state weight drift is significant — the adaptation keeps updating even when `e ≈ 0` because the regressor `x` is nonzero at the setpoint. Adding leakage or a deadzone would fix this.

---

### Cell 3 — Reference model MRAC

**Reference model:** `ẋr = -α(xr - c)`, same `α = 2`

**Adaptation:** `ŵ̇ = γx(x - xr)`, `γ = 50`

**Control:** `u = -α(x - c) - ŵx`

**Finding:** Adding a reference model means the adaptation signal `(x - xr)` goes to zero when the plant matches the model, which naturally terminates weight drift. Better steady-state weight behavior than Cell 2.

---

### Cell 4 — Projection operator

**New:** `w(t) = 1.5 + 0.25cos(0.5t)` (time-varying unknown), `wbd = 5`, `ε = 0.2`

**Projection rule:**
```
PR = x(x - xr)
if ŵ > wbd - ε and PR > 0:
    PR = (wbd - ŵ)/ε × PR
elif ŵ < -wbd + ε and PR < 0:
    PR = (ŵ + wbd)/ε × PR
ŵ̇ = γ × PR
```
This is a linear (smooth) projection — not the hard-clamp form. It scales the gradient down near the bound rather than zeroing it.

**Finding:** With time-varying `w(t)` oscillating between 1.25 and 1.75, projection keeps ŵ bounded in `[-wbd, wbd]` = `[-5, 5]`. The bounds are generous (`wbd = 5` vs true max ~1.75) so projection rarely activates during normal operation — it's a safety net.

**Firmware mapping:** [API/mrac.c](../../API/mrac.c) implements a similar linear projection in `mrac_projection_scalar()`. The `eps` parameter in firmware corresponds to this `ε = 0.2`.

---

### Cell 5 — Sigma modification (⚠ BUG)

**Intended law:** `ŵ̇ = γ(x(x-xr) - σŵ)`, `σ = 0.5`, `wbd = 2`, `ε = 0.2`

**BUG:** The code uses the variable name `gamma` but the local variable is named `gam`. This throws a `NameError` at runtime. Correct by replacing `gamma` with `gam` in the update line.

**Corrected law:** `ŵ = ŵ + dt*(gam*(x*(x-xr) - sigma*ŵ))`

**Theory:** σ-modification adds a damping term `−σŵ` that pulls weights toward zero, preventing parameter drift at the cost of non-zero weight error at steady state (UUB stability, not asymptotic). Necessary when the plant is persistently excited.

**Firmware mapping:** `mrac.h` exposes `sigma_mod` flag; [API/mrac.c](../../API/mrac.c) applies `- sigma * What` in the weight update.

---

### Cell 6 — e-modification

**Law:** `ŵ̇ = γ(x(x-xr) - σ|x - xr|ŵ)`, `σ = 2`, `γ = 50`

**Difference from σ-modification:** leakage term is scaled by `|e| = |x - xr|`. When tracking is good and `e ≈ 0`, leakage vanishes — the adaptive law is locally equivalent to pure MRAC. Only activates leakage during transients.

**Finding:** Better weight recovery after disturbances compared to fixed σ-modification, but the manual `σ = 2` needs re-tuning per scenario. In the simulation the weight estimate settles closer to the true `w` than the σ-modification case.

---

### Cell 7 — Neuro-adaptive, 6 RBF neurons + σ-modification

**Plant:** `ẋ = δ(x) + u`, `δ(x) = 1 + x² + sin(x)x³ + cos(x)x⁴` (nonlinear unknown)

**Network:** `θᵢ = exp(-0.1|x - cᵢ|²)`, centers `cᵢ ∈ {-5, -3, -1, 1, 3, 5}`

**Control:** `u = un + ua`, `un = -α(x - c)`, `ua = -ŵᵀθ`

**Adaptation:** `ŵ̇ = γ(θ(x - xr) - σŵ)`, `γ = 50`, `σ = 0.2`

**Finding:** The 6-neuron network partially approximates `δ(x)` but coverage is sparse. Estimation error is visible in the nonlinearity plot: the estimated `-ua` tracks the shape but not magnitude of `δ`. Tracking is still adequate because the nominal controller handles the stable part.

---

### Cell 8 — 7 neurons (6 RBF + bias)

**Change:** adds `θ₆ = 1` (constant bias term). Weight vector is now 7×1.

**Finding:** Bias term helps approximate the constant offset `+1` in `δ(x)`. The estimated nonlinearity matches the true one more closely near the operating points `x = ±1`.

---

### Cell 9 — 12 neurons

**Centers:** same 6 RBF positions, width=0.1, plus bias. `what = zeros(12,1)` — the extra 5 neurons appear to be additional RBFs (code matches the 6+bias pattern from Cell 8 but initializes 12 weights; the regressor loop only fills 7, leaving 5 at zero). Effectively still 7 active neurons with 5 dead weights — no impact on control but wastes adaptation bandwidth.

---

### Cell 10 — 21 neurons (dense grid)

**Centers:** `-5 + i×0.5` for `i ∈ 0…20`, width=0.25, bias=2 (scaled to `θ₂₁ = 2` instead of 1)

**Finding:** Denser coverage improves nonlinearity estimation. The true `δ(x)` and estimated `-ua` visually overlap after adaptation. Weight plot is intentionally commented out (21 lines is unreadable). The `bias = 2` scaling is unexplained — possibly a tuning artifact; changing it to 1 makes estimation slightly cleaner.

---

### Cell 11 — Performance recovery with 6 RBF neurons

**Recovery filter:** `ψ̇ = -λ(ψ - (x - xr))`, `λ = 5`

**Recovery control:** `v = λψ - (α + λ)(x - xr)`

**Modified reference model:** `ẋr = -α(xr - c) + v`

**Total control:** `u = un + ua + v`

**Theory:** The recovery term `v` forces the reference model to follow the actual plant when it diverges, then gradually pulls the plant back. This is related to L1 adaptive control's predictor-based approach. The reference model `xr` is no longer a fixed ideal trajectory — it bends toward `x`.

**Finding:** Transient tracking is dramatically tighter during disturbances. The ideal reference `xri` (without recovery) diverges transiently; the actual state follows `xr+` (with recovery) closely. Weight estimates converge faster because the error signal `(x - xr)` is smaller.

**Firmware mapping:** [API/mrac.c](../../API/mrac.c) implements a filtered performance recovery block; `PerfRec.LAMBDA` and `TAU_V` in the v2 notebook correspond to this.

---

### Cells 12–17 — 2D mass-spring-damper extensions

**Plant:** `mẍ = u - αx - βẋ`, `m = 5`, `α = 2.5`, `β = 1.0`

**State space:** `A = [[0,1],[0,0]]`, `B = [[0],[1/m]]` → `Λ = 1/m = 0.2`

**Reference model:** LQR-designed, `K1` from `ct.lqr(A, B, I₂, 0.1I₁)`, feedforward gain `K2 = -1/(CAr⁻¹B)`

**Lyapunov matrix P:** solved from `ArᵀP + PAr = -I₂`

**Weight update:** `Ŵ̇ = γ × φ × (eᵀPB)` where `φ` is the regressor

| Cell | Regressor φ | Notes |
|------|-------------|-------|
| 12 | `[x₁, x₂³, un]` | Linear uncertainty, true weights → `[-α, -β]` |
| 13 | 12 RBF: bias + 5 pos + 5 vel + un | `Λ = 0.75`, nonlinear uncertainty, σ-mod |
| 14 | 27 joint RBF: 5×5 grid + bias + un | `Λ = 0.75`, joint (2D) Gaussians |
| 15 | **BUG:** incomplete θ fill + `theta[11]` OOB | `IndexError` at runtime |
| 16 | 12 RBF (corrected coeff `2*x₀²*x₁²`) | Fixed uncertainty formula from Cell 13 |
| 17 | `[x₁, x₂³, un, v]` 4-weight + recovery | LQR + performance recovery, `f` filter |

**Cell 15 is broken:** the regressor construction loop sets `center_x0 = -2` but never assigns `theta[i]` for most neurons. Then `theta[11] = un` is attempted on a 27-dim theta — valid index but the prior neurons are all zero. The weight estimates drift arbitrarily. **Do not reuse Cell 15 as a template.**

**Cell 12 finding:** estimated weights `Ŵ` converge toward true values `[-α, -β] = [-2.5, -1.0]` with `γ = 10`. Convergence is slow (true weights visible as red dashed lines in the plot). Increasing `γ` speeds this up but the regressor `[x, v³, un]` has `x` at steady state ≠ 0 for `c = ±1` commands, so drift persists.

**Cell 13 finding:** `Λ = 0.75` ≠ 1/m creates input effectiveness uncertainty. Including `un` in the regressor (`theta[11] = un`) allows the network to adapt for this gain uncertainty. The `un` term compensates for `(1 - Λ)un = 0.25un` that the plant "sees" differently from the model.

---

## Known bugs

| Cell | Bug | Fix |
|------|-----|-----|
| 5 | `gamma` undefined (should be `gam`) | `s/gamma/gam/` in adaptation line |
| 15 | `center_x0 = -2` never used; `theta[11]` on 27-dim | Rebuild regressor loop or skip |

---

## Reuse guidance

- **Template for scalar MRAC**: Cell 3 (reference model) + Cell 4 (projection). Most stable starting point.
- **Template for neuro-adaptive**: Cell 7 (6 RBF + sigma) with centers chosen to cover expected operating range.
- **Template for 2D**: Cell 13 (12 RBF, σ-mod) — Cell 16 has the corrected uncertainty formula.
- **Do not copy Cell 5 or 15 verbatim.**

## Related pages

- [[Adaptive Control Tutorial 2 Notebook]]
- [[Direct MRAC + FF + Projection Notebook]]
- [[Adaptive Control Simulations]]
- [[MRAC Theory]]
- [[MRAC Control Law]]
