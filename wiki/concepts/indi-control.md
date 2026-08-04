---
title: INDI — Incremental Nonlinear Dynamic Inversion
type: concept
tags: [control, indi, quadrotor, disturbance-rejection, stub]
created: 2026-07-31
updated: 2026-07-31
sources: [raw/papers/2026-07-21-Performance-Precision-and-Payloads-Adaptive-Nonlinear-MPC-for-Quadrotors.pdf]
---

**Stub.** Recorded because INDI is the method that *beat* L1 adaptive control on aggressive racing trajectories in [[l1-nmpc-adaptive-nonlinear-mpc-quadrotors]], and because it is the standard opponent any adaptive-control result gets compared against.

## The idea in one paragraph

Nonlinear Dynamic Inversion says: write the plant as `ẋ = f(x) + g(x)u`, then pick `u = g⁻¹(ẋ_desired − f(x))` to cancel the dynamics and leave a linear system. This requires knowing `f(x)` exactly — which you never do. **Incremental** NDI sidesteps that: instead of solving for the absolute input, solve for the *increment* around the current operating point, using a **measured** angular acceleration to stand in for everything the model would have had to supply:

```
Δu = g⁻¹ (ω̇_desired − ω̇_measured)
u_k = u_{k−1} + Δu
```

Because `ω̇_measured` already contains every real effect — aerodynamics, CG offset, prop damage, battery sag — the model dependence collapses to just the **control effectiveness matrix** `g` (how much angular acceleration one unit of thrust difference produces). Everything else cancels.

## Why it is fast, and where it fails

- **Fast**: it is essentially a feedback law, not a learning law. One tick of disturbance, one tick of response. No convergence transient at all, which is why it wins on 4 g racing trajectories.
- **Needs clean `ω̇`**: differentiating gyro data amplifies noise, so INDI lives or dies on filtering and on the delay between the filtered `ω̇` and the actuator.
- **No integral action on linear acceleration** (paper, p7): INDI is a *rate*-level method, so an unknown payload still produces a permanent Z-height offset. This is exactly where L1 beat it (slung-payload case, p6).
- **Model updates still required for mass changes** to maximise performance.

## Contrast with the adaptive family

| | INDI | MRAC / L1 |
|---|---|---|
| Source of truth about the disturbance | direct measurement (`ω̇`) | inferred from tracking / prediction error |
| Transient | none | convergence time |
| Sensor demand | high-quality, low-latency `ω̇` | ordinary state feedback |
| Handles unknown *mass* | no (no linear integral action) | yes |
| Handles unknown *inertia / CG* | yes, very well | yes, comparably |

Worth knowing for the thesis: in the paper's simulation table, INDI-NMPC and L1-NMPC were within **5 mm** of each other across all inertia and arm-length cases. They only diverge on mass.

## To expand later

Original INDI derivation and the delay/filter analysis; Sun et al.'s quadrotor INDI work; whether a `ω̇`-based increment is even feasible on this project's BMI088 + Mahony pipeline given filter delay.

## See also

- [[l1-nmpc-adaptive-nonlinear-mpc-quadrotors]]
- [[l1-adaptive-control]]
- [[mrac-control-law]]
