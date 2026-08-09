# ADR-0014 — Dimensionless priors and declared regressor variants

*   **Status:** Proposed
*   **Date:** 2026-08-05
*   **Supersedes in part:** [ADR-0013](0013-scenario-conditioned-adaptive-priors.md) — the
    prior is redefined as a dimensionless object. ADR-0013's injection channels,
    mismatch-signature feature space, and envelope reasoning all stand unchanged.
*   **Refines:** [ADR-0012](0012-retire-gazebo-mujoco-plant-ladder.md) D8 (plant-tagged
    priors).

> **Novelty framing HELD, 2026-08-06.** The literature review returned and found prior art for
> the *mechanism* this ADR treats as unprecedented: Girard, "Dimensionless Policies based on
> the Buckingham π Theorem", *Mathematics* 12(5):709, 2024, establishes dimensionless transfer
> of control policies between dimensionally similar systems; Chowdhary, Wu, Cutler & How, ICRA
> 2013, transfers an adaptive controller across quadrotors with concurrent learning. The
> surviving unclaimed slice is narrower — dimensionless **MRAC weight vectors** via the `1/K`
> matching argument.
>
> **The eight decisions below are unaffected and remain in force** — they are engineering
> decisions about how this project stores and converts priors, and prior art does not change
> whether `Θ̃ = K·Θ` is the right stored form. What is held is the *contribution claim* in the
> Context and Consequences sections. It is not rewritten here because the author has not yet
> read the primary sources, and a framing that rests on an agent's summary is not a framing.
> Resolve in a dedicated grilling session; reading path in
> [`docs/literature-review-findings/SYNTHESIS.md`](../literature-review-findings/SYNTHESIS.md) §7.

## Context

ADR-0013 framed the thesis as *scenario-conditioned priors learned in simulation and
applied on hardware*. It implicitly assumed the target of transfer was one airframe —
JX_FLY — and ADR-0012 D8 therefore treated the plant tag as a **barrier**: a prior learned
on plant A is not valid on plant B.

That framing is too narrow, and it makes the weaker of the two available claims. The
thesis hypothesis is that the knowledge captured by a prior is a property of the
**scenario**, not of the airframe: the adaptation required to reject a standing asymmetric
load, or to handle gyroscopic coupling in an aggressive turn, is the *same knowledge* on
any quadrotor. If that holds, the contribution is a transferable library of scenario
priors, not a lookup table for one vehicle.

The obstruction is dimensional, not conceptual. For the axis plant
`ẋ = −p·x + K·(u_nom + u_ad) + Δ`, the matching condition is `K·Θ*ᵀΦ = −Δ`, so

```
Θ* = −Δ_coeffs / K
```

Every weight carries a `1/K`. `K` is the lumped input→output gain — it folds mixer torque
effectiveness and `1/J` together and differs across airframes by large factors (the
Menagerie Crazyflie 2 is ~5× more agile per unit command than JX_FLY). A prior stored as a
raw `Θ` in firmware command units therefore cannot transfer, and the failure mode is
silent: the weights saturate the authority limit and the *method* appears to have failed.

Two further facts, established from the firmware:

1.  **Basis count is already a compile-time variable.** `mrac.h:82-94` derives
    `MAX_NUM_BASIS` from `USE_STRUCTURED_UNCERTAINTY` and `INCLUDE_CONTROL_IN_REGRESSOR`,
    spanning `NUM_BASIS`, `NUM_BASIS+2`, `2*NUM_BASIS`, `2*NUM_BASIS+2`. Every config array
    is sized off it. The regressor is a **design variable**, not a fixture.
2.  **The regressor-scaling problem was already hit and patched by hand.** `mrac.h:132`:
    *"Per-component learning rates: `gamma[i]` compensates for regressor magnitude
    imbalance. Rule of thumb: `gamma[i] = gamma_base / (typical |theta[i]|^2)` …
    `gamma[1]=3.30` (angle, `theta^2=0.023`, needs 44× more gain)."* That table is a
    manual, per-airframe normalisation. It is tuned against JX_FLY's typical `|θ|` and
    would not survive an airframe change.

3.  **The normalisation scales already exist in the config.** `MRAC_AxisConfig_t` carries
    `u_max` [Nm or N], `J` [kg·m² or kg], `mrac_to_mixer` [mixer units per torque], and
    `e_sat` [rad/s, characteristic rate]. Non-dimensionalisation requires no new
    measurement.

## Decision

### D1 — A prior is a dimensionless object

The canonical stored form of a prior is `Θ̃`, non-dimensional. The raw `Θ` and the
identifying triple `(K, p, T)` of the plant it was learned on are stored **alongside** it,
never in place of it.

Deployment on any target is `Θ = Θ̃ / K_target` (modulo per-slot scales, D3). Learning and
storage are plant-independent; only the final conversion is plant-specific.

### D2 — Plant tags are rescaling metadata, not a transfer barrier

ADR-0012 D8 is refined. Every prior still carries its plant identity and `(K, p, T)` — but
the purpose is to make the dimensionless form *computable and invertible*, not to forbid
cross-plant use. Applying a prior across plants is the experiment, not a defect.

`prior-04` (SysID on every simulated plant) is consequently re-scoped from a *gate that
blocks prior learning* to the *service that enables transfer*: `K` must be known per plant
precisely so it can be divided out.

### D3 — Dimension is a declared property of each basis function

Non-dimensionalisation is **not** a hand-derived table keyed to today's six slots. Each
basis function declares, as data:

*   the input it consumes,
*   its physical dimension,
*   the normalisation scale that renders it O(1) (drawn from `u_max`, `J`,
    `mrac_to_mixer`, `e_sat`, `ref_model_bw`).

The dimensionless form is then computed mechanically from the declaration, and works for
regressors that do not exist yet. This is the decision that keeps regressor design open.

Rationale: a hand-derived scaling table for the current
`Φ = [1, x, x·tanh x, cross, u_nom, xm]` is obsolete the moment a seventh basis function is
tried. The `x·tanh x` slot makes the point — `tanh` carries an implicit 1 rad/s scale, so
a vehicle operating at 20 rad/s and one at 5 rad/s sit on different parts of the curve and
that slot does not non-dimensionalise without an explicit characteristic rate. Declaring
the scale fixes it; enumerating slots does not.

### D4 — Regressor variants are named, registered, and tagged onto priors

`sim/` carries a registry of named regressor variants. Every prior records the variant ID
that produced it, exactly as it records the plant tag. A `Θ̃` learned under one variant can
never be silently applied under another.

The variant matching the currently-compiled firmware is the **pinned baseline** and keeps
the existing golden-vector parity test (`sim/tests/test_regressor.py` ↔ `mrac.c:65-91`).
Other variants are sim-only. Promoting one to firmware is a separate spec with its own
parity test, per governing principle 1 (`sim/` normative for the algorithm, firmware
normative for integration).

### D5 — Scenarios are parameterised in relative terms

A scenario definition states magnitudes as fractions, never absolutes:

*   disturbance torque as a fraction of `u_max`,
*   inertia offset as a fraction of `J`,
*   aggression as a fraction of achievable angular acceleration,
*   rates relative to the characteristic rate.

Rationale: a 100 g offset mass is a 3× overload on a 33 g Crazyflie and a 7.7 % trim
nuisance on JX_FLY. Under absolute parameterisation the same scenario name denotes
different physics on different airframes, no prior can transfer, and the experiment would
wrongly report that the method failed. **Non-dimensionalising the prior without also
non-dimensionalising the scenario is worse than doing neither**, because it produces a
clean-looking result that means nothing.

### D6 — Generalisation is tested by randomisation over an ensemble, not by picking a close model

The airframe ensemble is generated by runtime parameter randomisation over
`mujoco.MjModel` (`body_mass`, `body_inertia`, `site_pos`, actuator `gear` are writable
arrays), spanning well beyond JX_FLY. Menagerie's two real quadrotors — Bitcraze
Crazyflie 2 (MIT) and Skydio X2 (Apache-2.0) — are included as real-geometry members for
external validity.

Rationale: selecting one "close enough" airframe tests nothing, because closeness in mass
or appearance is not closeness in `K`. Skydio X2 is within 2 % of JX_FLY's mass and has a
30 % pitch-arm error against it. Invariance is a property demonstrated across a
distribution or not at all.

### D7 — The central experiment is cross-plant prior damage

Learn `Θ̃` on plant A, apply it on plant B, measure the degradation. Sweep across the
ensemble. Tight spread ⇒ a generalisable prior. Wide spread on a given slot ⇒ a specific,
named scope limit.

This promotes ADR-0013 D7's mismatched-prior damage test from a safety check to the
thesis's headline result. Both outcomes are publishable; the scope limit is worth more in
a defence than an unqualified claim.

### D8 — Normalisation invalidates the existing tuning, and that is scoped work

Under a normalised regressor, `gamma`, `What_limit`, `What_tol`, and `e_deadzone` are all
expressed in the old units and require re-derivation. This is the reason D4 keeps the
current regressor as a pinned baseline rather than replacing it: the baseline stays
runnable and comparable throughout.

The expected payoff is that the hand-tuned `gamma` table (`mrac.h:132`, up to 44× spread)
collapses toward uniform, and `gamma` itself becomes plant-independent — so learning rates
transfer with the prior instead of being re-tuned per airframe.

## Consequences

*   The claim strengthens from *"priors transfer from my sim to my drone"* to *"scenario
    priors are airframe-invariant in dimensionless form"* — falsifiable, and testable
    entirely in simulation.
*   Hardware deployment reduces to one scalar per axis: `Θ = Θ̃ / K_real`, with
    `K_roll ≈ 165` already measured (`docs/sysid_results.md`).
*   `sim/scenarios.py` and `sim/scenarios_yaml.py` need relative parameterisation (D5).
    Existing absolute-magnitude scenario definitions must be converted, and any result
    produced under the old parameterisation is not comparable across plants.
*   `prior-05`'s prior factory emits `Θ̃`. Catching this before the run corpus is logged
    avoids re-running the simulator to change representation.
*   `RigidBodyPlant` remains the oracle (ADR-0012 D3) and is unaffected.
*   Open: the characteristic rate used to normalise `x` (and therefore the `x·tanh x`
    slot). `e_sat` is the existing candidate. `prior-00b`'s finding on whether
    `e_deadzone = 0.05` dominates disturbance rejection feeds directly into this choice —
    which is a further reason to run it first.
*   Open: whether `Θ̃` should normalise per-slot against `What_limit` (fraction of
    authority) or against physical scales. The former makes the envelope channel
    (ADR-0013 D7) trivially transferable; the latter is more physically interpretable.
