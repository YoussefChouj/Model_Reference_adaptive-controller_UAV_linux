---
title: Scenario Priors and Cross-Airframe Transfer
type: concept
tags: [mrac, adaptive-control, sim-to-real, prior-library, dimensionless, thesis]
created: 2026-08-10
updated: 2026-08-10
sources: [docs/adr/0013-scenario-conditioned-adaptive-priors.md, docs/adr/0014-dimensionless-priors-and-declared-regressor-variants.md]
related_files: [docs/adr/0012-retire-gazebo-mujoco-plant-ladder.md, API/mrac.c, sim/adaptive_law.py]
---

The thesis hypothesis is that adaptive knowledge captured by a prior is a property of
the **scenario** — not the airframe. The same standing asymmetric load, or the same
gyroscopic coupling in an aggressive turn, demands the same adaptation on any
quadrotor. This page is the conceptual entry point for how that knowledge is stored,
indexed, and applied; the engineering decisions live in
[ADR-0013](../../docs/adr/0013-scenario-conditioned-adaptive-priors.md) and
[ADR-0014](../../docs/adr/0014-dimensionless-priors-and-declared-regressor-variants.md).

## The prior as a dimensionless object

For the axis plant `ẋ = −p·x + K·(u_nom + u_ad) + Δ` the matching condition is
`K·Θ*ᵀΦ = −Δ`, so every weight carries a `1/K`. A raw `Θ` in firmware command units is
therefore plant-specific and cannot transfer. The canonical stored form of a prior is
the dimensionless `Θ̃` (also written `Theta_tilde`):

```
Θ̃ = K · Θ
```

The raw `Θ` and the plant's identifying triple `(K, p, T)` are stored **alongside** it,
never instead (ADR-0014 D1). Deployment on any target is `Θ = Θ̃ / K_target`, per slot.

## The σ_prior attractor as the primary value channel

`API/mrac.c:274-279` already flies a leak-toward-target term `−σ_lf·(Θ[i] − Whatf[i])`
alongside `−σ_eff·Θ[i]`. The prior attractor is structurally identical — just leak
toward `Θ_prior` instead of `Whatf`:

```
dΘ/dt  ←  − σ_prior · (Θ − Θ_prior)
```

The Lyapunov argument is unchanged: σ-modification with a non-zero attractor bounds
`‖Θ − Θ_prior‖` instead of `‖Θ‖`; UUB survives (ADR-0013 D5). `σ_prior` spans the entire
design space — `0` is today's baseline, `∞` is hard initialisation, intermediate is the
intended soft target — which is why this one channel covers every point between "ignore
the prior" and "trust it completely".

## The plant-tagged transfer rule

Every prior is recorded with its plant identity and the `(K, p, T)` it was learned under.
Under [ADR-0014 D2](../../docs/adr/0014-dimensionless-priors-and-declared-regressor-variants.md) the
plant tag is **rescaling metadata**, not a transfer barrier:

```
apply(Θ̃, plant)  :=  Θ̃ / K_plant            # conversion
                     Θ̃ indexed by scenario   # selection
                     Γ, What_limit, e_deadzone per-scenario   # envelope
```

Applying a prior across plants is the experiment, not a defect. Scenarios themselves
are stated in relative terms — disturbance over `u_max`, inertia offset over `J`,
aggression over achievable angular acceleration — so the same scenario name denotes the
same physics regardless of airframe (ADR-0014 D5). The corresponding
[ADR-0012 D5](../../docs/adr/0012-retire-gazebo-mujoco-plant-ladder.md) SysID calibration
gate becomes the service that enables transfer: `K` must be measured per plant precisely
so it can be divided out.

Regressors are registered, not asserted: a `Φ` learned under one regressor variant
cannot be silently applied under another. The variant matching the compiled firmware is
the **pinned baseline** (ADR-0014 D4) and keeps the existing golden-vector parity test.

## The cross-plant damage test as the thesis headline

The thesis's headline result is the **cross-plant prior-damage sweep** (ADR-0014 D7):

1. Learn `Θ̃` on plant A.
2. Apply it on every plant in the airframe ensemble (seeded randomisation over
   `mujoco.MjModel` mass / inertia / arm / gear, plus Menagerie's Crazyflie 2 and Skydio
   X2 as real-geometry members — ADR-0014 D6).
3. Measure the degradation against two references: the no-prior baseline, and B's own
   learned prior.

Tight spread across the ensemble ⇒ a generalisable prior. Wide spread on a given slot
⇒ a specific, named scope limit. Both outcomes are publishable; the scope limit is
worth more in a defence than an unqualified claim. The mismatched-prior damage test
from ADR-0013 D7 is **promoted** by this decision from a safety check to the load-bearing
experimental result of the thesis.

## Honest failure mode

The honest failure mode is *"a confidently wrong prior is worse than no prior"*:
inject scenario A's prior while actually in scenario B and measure the harm. The
**damage threshold** — the plant mismatch (e.g. `K_A/K_B`) beyond which a transferred
prior performs worse than no prior — is the deployable safety statement. It must be
characterised, not avoided.
