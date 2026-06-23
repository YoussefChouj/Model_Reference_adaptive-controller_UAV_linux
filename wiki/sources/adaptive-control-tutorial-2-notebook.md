---
title: Adaptive Control Tutorial 2 Notebook
type: source
tags: [adaptive-control, derivative-free, barrier, set-theoretic, low-frequency-learning, integral, pid-adaptive, tutorial]
created: 2026-04-14
updated: 2026-06-20
sources:
  - "C:/Users/Acer/Desktop/Pich_yaw_roll_experimental_drone_setup/[Demonstration] - Microcontroller Control - Experiment 4 - Cascaded PID - dShot - FreeRTOS - Suspended/Adaptive_Control_Tutorial_2.ipynb"
---

8-cell notebook extending the first tutorial with techniques that avoid velocity measurement or enforce explicit error constraints. All code cells user-validated. Common plant: `mẍ = u - αx - βẋ` or equivalent 2D linear system. `dt = 0.005 s` throughout.

---

## Cell 0 — Markdown intro

Motivates adaptive control for drones: unknown mass, battery drain, wind. Sets up the mass-spring-damper analogy. No code.

---

## Cell 1 — Integral nominal adaptive control

**Plant:** `A = [[0,1],[0,0]]`, `B = [[0],[1/m]]`, `m=5`, `α=2.5`, `β=1.0`, `Λ=1/m`

**Augmented system with integral action:**
```
ż = Ex - c    (integral of position error)
Augmented state ξ = [x; z]
Aa = [[A, 0]; [E, 0]],  Ba = [[B]; [0]],  E = [1, 0]
```

**LQR gain:** `K = ct.lqr(Aa, Ba, I₃, 0.1I₁)` → `K1 = K[:2]`, `K2 = K[2]`

**Reference model (augmented):** `Ar = [[A-BK1, -BK2]; [E, 0]]`, `Br = [[0],[0],[-1]]`

**Lyapunov matrix:** `P = ct.lyap(Ar.T, I₃)`

**Regressor and update:**
```
φ = [x₁, x₂³, un]
ua = -Ŵᵀφ
u = un + ua
Ŵ̇ = γ × φ × (ξ - ξr)ᵀPBa
```
`γ = 10`, `Ŵ₀ = 0₃×₁`

**Why augment with integral?** Without it, constant unknown parameters produce steady-state position offset even with perfect adaptation. The integral state `z` drives the reference model to zero steady-state error, and the regressor `un` lets the adaptive law compensate for the part that was absorbed into `K2`.

**Finding:** Position, velocity, and integral state all track their reference model counterparts. Weight `Ŵ[0]` converges toward true `-α = -2.5`, `Ŵ[1]` toward `-β = -1.0`. `Ŵ[2]` (control-related) remains small since `Λ = 1/m` is known here.

---

## Cell 2 — PID adaptive control under measurement noise

**Structure:** PID nominal with adaptive augmentation. Derivative approximated via first-order filter.

```
Filter:  q̇ = -λ(q - y),  λ = 50,  y = Ex (position output)
ẏd = -λ(q - y)           (filtered derivative estimate)
un = -K1(y-c) - K2·z - K3·ẏd,  K1=4, K2=0.5, K3=2.5
```

**Augmented state for reference model:** `ξ = [x; z]`

```
F = I + B·K3·E,  G = A - B·K1·E
Ar = F⁻¹[[G, -B·K2]; [E, 0]],  Ba = F⁻¹[[B];[0]]
Br = F⁻¹[[B·K1];[-1]]
```

**Adaptation:** same `φ = [x₁, x₂³, un]`, `Ŵ̇ = γ × φ × (ξ - ξr)ᵀPBa`

**Noise:** `noise_std = 0.05`, but the noise addition line is **commented out** (`x_meas = x`, not `x + noise`). The noise infrastructure is there for future experiments.

**Finding:** Tracking is clean because noise is off. The filtered derivative `ẏd` avoids algebraic differentiation noise even when noise would be present — the `λ = 50` filter is aggressive enough to suppress 0.05 std noise. Reduce `λ` if chatter appears.

---

## Cell 3 — Markdown: derivative-free MRAC explanation

Explains DF-MRAC for a non-technical reader: why derivatives are noisy, what the filter `τ` does. Key quote from the embedded tuning summary (Cell 5):

| τ value | RMS position error |
|---------|-------------------|
| 1.0 | 3.20° |
| 0.1 | 2.58° |
| γ₂=10 | 0.42° |
| γ₁=0.9 | 0.42° → 0.12° |

Best result: `γ₁ = 0.9`, `γ₂ = 10`, `τ = 0.1` → RMS position error **0.12°**.

---

## Cell 4 — Derivative-Free MRAC (DF-MRAC)

**Plant:** `ẋ = Ax + B(u + Wᵀβ)` (2D linear with matched nonlinear uncertainty)

```
A = [[0,1],[0,0]],  B = [[0],[1]]
Reference model Am/Bm:  wn=0.4, rn=0.707
Am = [[0,1],[-wn², -2*rn*wn]],  Bm = [[0],[wn²]]
```

**Nominal gains:**
```
K1 = B⁺(A - Am)     (state feedback to cancel model mismatch)
K2 = B⁺Bm           (feedforward to track reference)
```

**Basis functions (5-dimensional):**
```
β = [x₁, x₂, |x₁|x₂, |x₂|x₂, x₁³]
```

**True uncertainty (activated at t=20 s):**
```
W = [0.1414·sin(2.5t), 0.5504, -0.0624, -0.0095, 0.0215]ᵀ
```
Before t=20: `W = 0` (clean plant). After t=20: time-varying sinusoidal + constant components.

**Weight update law (frozen-time approximation):**
```
Ŵ(t) = γ₁ × Ŵ(t-τ) + γ₂ × β × (x - xm)ᵀPB
```
`γ₁ = 0.9` (memory factor), `γ₂ = 10` (learning rate), `τ = 0.1` s (delay)

**Implementation detail:** The delay is implemented by saving `What_rec` history and indexing back by `int(τ/dt)` steps. The `W_hat_Tau` variable is the delayed weight snapshot. This is NOT a true L1 adaptive controller — it is a simpler frozen-time approximation.

**Why no derivative?** The update uses only `(x - xm)` which is the state tracking error — requires only position measurement if the reference model state is tracked separately. No velocity measurement needed for the adaptation law itself (velocity appears only in `β` which is observable from state).

**Finding:** Without adaptation (`Adaption_on=0`), uncertainty at t=20 causes large tracking error. With adaptation, error recovers within a few seconds. The weight estimate of `Ŵ[1]` (constant term 0.5504) converges most reliably; the sinusoidal `Ŵ[0]` lags because `γ₁ = 0.9` limits fast weight changes.

**Gotcha:** `γ₁` must be in `[0, 1)`. `γ₁ = 1` means "pure memory" — weights never grow from the gradient term, only from the frozen snapshot. Setting `γ₁ = 0` gives standard MRAC with no frozen-time benefit.

---

## Cell 5 — Markdown: tuning results table

Contains the numerical RMS results from tuning runs (shown in Cell 3 above). Treat as validated experimental data.

---

## Cell 6 — Set-theoretic neuro-adaptive with barrier function

**Plant:** `ẋ = Ax + B(u + Δ(x))`, `Δ(x) = 1 + x₁² + 2x₁²x₂² + sin(x₁)x₂³ + cos(x₂)x₁⁴`

**Reference model:** LQR-based (same as Tutorial Cell 12).

**Prescribed error bound:** `ε = 0.005` (tight)

**Barrier function derivative:**
```
φ' = (ε - 0.5√(eᵀPe)) / (ε - √(eᵀPe))²
```
This grows large as `√(eᵀPe) → ε`.

**Barrier-modified control:**
```
v = tanh(φ' BᵀPe) × q̂     (barrier forcing term)
u = -K1x + K2c - v - ŴᵀΘ
```

**Two adaptive parameters:**

1. Neural weights `Ŵ` (11×1: bias + 5 pos RBF + 5 vel RBF):
```
PR = φ' × Θ × eᵀPB   (projected gradient)
Ŵ̇ = γ₁ × PR,  γ₁ = 0.25
Projection bounds: web1L = web1U = 10
```

2. Scalar gain `q̂` (estimates unknown uncertainty magnitude):
```
PR₂ = φ' × eᵀPB × tanh(φ'BᵀPe) - ζ × q̂
q̂̇ = γ₂ × PR₂,  γ₂ = 0.25,  ζ = 0.25
Projection bounds: qb1L = 0, qb1U = 10
```

**Projection:** Linear smooth projection applied to both `Ŵ` and `q̂`, tolerance `tol = 0.1`.

**RBF centers:** 5 positions in `[-2, 2]` and 5 velocities in `[-2, 2]`, `width = 0.25`.

**Finding:** The Lyapunov-weighted error norm `√(eᵀPe)` stays below `ε = 0.005` for most of the run. The barrier activates strongly at setpoint transitions (command switches at t=10, 20, 30). The `tanh` saturation prevents the barrier from generating infinite control effort at the boundary. `q̂` adapts slowly due to low `γ₂ = 0.25` — increase to 2–5 for faster uncertainty estimation.

**Gotcha:** `ε = 0.005` is very tight for a system with large uncertainty. If the initial transient exceeds `ε` (which it can at startup), `φ'` becomes negative (numerator goes negative before denominator), which flips the barrier direction and can cause instability. The code does not guard against this — add an `if √(eᵀPe) >= ε: clip` guard in firmware.

---

## Cell 7 — Low-Frequency Learning (LFL) adaptive control

**Plant:** `ẋ = Ax + B(u + Wᵀθ)`, true `W = [1, -1, 2]ᵀ`

**Regressor:** `θ = [sin(x₁)x₁, x₂³, |x₁|x₂]ᵀ`

**Control:** `u = un + ua`, `ua = -Ŵᵀθ`

**Two-timescale weight law:**
```
Ŵ̇ = γ(θ(x-xr)ᵀPB - σ(Ŵ - Ŵf))     [fast weights]
Ŵ̇f = γf(Ŵ - Ŵf)                      [slow filtered weights]
```
`γ = 250`, `σ = 0.1`, `γf = 0.5`

**Key idea:** Ŵf is a low-pass-filtered version of Ŵ. The leakage term `σ(Ŵ - Ŵf)` penalizes the fast weights for drifting away from the slow filtered weights rather than penalizing them for drifting from zero (as in standard σ-modification). This preserves learned information across slow timescales while still preventing fast drift.

**Finding:** With `γ = 250` (very high), the system learns quickly but the slow filter `γf = 0.5` means Ŵf lags significantly. At `γ = 250` there can be high-frequency chatter in the fast weights — visible in the position tracking as small oscillations. Reducing `γ` to 50 gives smoother behavior at the cost of slower convergence.

**Comparison to standard σ-modification (Tutorial 1, Cell 5):** LFL has better weight retention during setpoint changes because the leakage attractor `Ŵf` moves with the learned weights. Standard σ-modification always pulls weights toward zero.

**Firmware status:** The [API/mrac.c](../../API/mrac.c) `USE_LOW_FREQUENCY_LEARNING` flag corresponds directly to this structure. The `sigm` and `gamf` parameters map to `SIGMA_MOD_GAIN` and `LF_LEARN_GAIN` in `mrac.h`.

---

## Cross-notebook findings

| Technique | Regressor type | Needs velocity? | Tracks time-varying W? | Error bound guaranteed? |
|-----------|---------------|-----------------|------------------------|------------------------|
| Integral adaptive (Cell 1) | Linear parametric | Yes | No | No |
| PID adaptive (Cell 2) | Linear parametric | Filter-based | No | No |
| DF-MRAC (Cell 4) | Nonlinear basis | No | Partial | No |
| Set-theoretic (Cell 6) | RBF neural | Yes | Yes | Yes (UUB to ε) |
| LF-Learning (Cell 7) | Arbitrary | Yes | Yes | No |

---

## Reuse guidance

- **Integral adaptive (Cell 1):** use as template for position-holding mode where steady-state accuracy matters.
- **DF-MRAC (Cell 4):** use when velocity measurement is unreliable. Tune `γ₁` close to 0.9, `γ₂ = 10`, `τ = 0.1 s`.
- **Set-theoretic (Cell 6):** use when hard error bounds are required (e.g., close-proximity flight). Set `ε` 2–3× larger than expected initial transient to avoid barrier sign flip.
- **LF-Learning (Cell 7):** use for repeating trajectories where the uncertainty structure is stationary. `γf = 0.5` is conservative — increase to 2–5 for faster slow-timescale learning.

## Related pages

- [[Adaptive Control Tutorial Notebook]]
- [[Direct MRAC + FF + Projection Notebook]]
- [[Adaptive Control Simulations]]
- [[MRAC Theory]]
- [[MRAC Control Law]]
