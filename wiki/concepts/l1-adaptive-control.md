---
title: L1 Adaptive Control
type: concept
tags: [adaptive-control, l1, mrac, robustness, thesis]
created: 2026-07-31
updated: 2026-07-31
sources: [wiki/sources/l1-nmpc-adaptive-nonlinear-mpc-quadrotors.md, raw/papers/2026-07-21-Performance-Precision-and-Payloads-Adaptive-Nonlinear-MPC-for-Quadrotors.pdf]
---

L1 adaptive control is MRAC with one structural change: **a low-pass filter between the uncertainty estimate and the control signal.** That single insertion is what the whole method is named after and what the whole method buys.

## The problem it solves

In classical MRAC the adaptation gain `Γ` (your `gamma[]` in `API/mrac.h`) does two jobs at once:

1. how *fast* the estimate converges, and
2. how much high-frequency content reaches the actuators.

Turn `Γ` up to react quickly to a payload and you also feed estimator noise, unmodelled flexible modes, and sensor jitter straight into the motors. Turn it down for smoothness and you adapt too slowly to be useful. This coupling is the classic practical objection to high-gain MRAC.

## The L1 architecture

```
             ┌──────────────┐
  measured z │              │  z̃ = ẑ − z
 ────────────┤ state        ├───────────────┐
             │ predictor ẑ  │               │
             └──────┬───────┘               ▼
                    ▲                ┌─────────────┐
                    │                │ adaptation  │  σ̂  (fast, unfiltered)
                    │                │    law      │
                    │                └──────┬──────┘
                    │                       ▼
                    │                ┌─────────────┐
                    └────────────────┤    C(s)     │  low-pass, cutoff ω_co
                       u_L1          │  filter     │
                                     └──────┬──────┘
                                            ▼
                                        to actuators
```

Three pieces:

1. **State predictor (observer)** — run a copy of the model in parallel. `ż_hat = f + g(u_L1 + σ̂_m) + g⊥σ̂_um + A_s(ẑ − z)`. The prediction error `z̃` is the *only* place uncertainty shows up.
2. **Adaptation law** — convert `z̃` into an uncertainty estimate `σ̂`. Can be arbitrarily fast; the piecewise-constant form solves for it algebraically each sample with no gain at all: `σ̂ = −G⁻¹Φ⁻¹µ`.
3. **`C(s)` filter** — `u_L1 = −C(s)σ̂`. This is the robustness knob, and it is *separate* from the adaptation speed.

Discrete implementation is a one-line exponential smoother:

```c
/* alpha = exp(-w_co * Ts) */
u_l1 = u_l1 * alpha - sigma_hat * (1.0f - alpha);
```

## Honest comparison to this project's MRAC

| | This firmware's MRAC | L1 |
|---|---|---|
| Where uncertainty is inferred | tracking error `e = x − x_m` vs a reference model | prediction error `z̃ = ẑ − z` vs a state predictor |
| Update law | integrating: `Θ̇ = Γ Φ e` | algebraic per-sample solve (piecewise constant) |
| Speed knob | `gamma[]` | observer bandwidth `A_s` |
| Robustness knob | *same* `gamma[]` (+ projection, leakage, deadzone) | `ω_co`, independent |
| Anti-divergence machinery | `MRAC_Projection`, `What_limit[]`, `What_tol[]`, leakage, `e_deadzone`, `e_freeze` | mostly unnecessary — nothing integrates |
| Basis functions | yes, `Phi[]`, `NUM_BASIS 4` — structured uncertainty | none; estimates the lumped uncertainty directly |
| What you learn | physically interpretable weights `Theta[]` | an opaque disturbance signal |

The last row is the real trade-off and it cuts **toward** MRAC for a thesis: `Theta[]` converging to a physically meaningful value is a *result you can plot and defend*. L1's `σ̂` is a disturbance estimate that vanishes the moment you fix the model — there is no parameter convergence story to tell.

## Caveat on "adaptation decoupled from robustness"

The decoupling is real but not free: `ω_co` must be low enough for robustness and high enough to actually cancel the disturbance. If your disturbance is faster than `ω_co`, L1 filters out exactly the thing you wanted to cancel. The method moves the tuning problem, it does not delete it.

## See also

- [[l1-nmpc-adaptive-nonlinear-mpc-quadrotors]] — the source paper, with hardware numbers
- [[mrac-control-law]] — the firmware implementation this is compared against
- [[matched-unmatched-uncertainty]]
- [[MRAC Theory]]
