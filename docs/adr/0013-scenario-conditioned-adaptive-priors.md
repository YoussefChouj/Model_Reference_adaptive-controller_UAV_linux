# 0013 - Scenario-conditioned adaptive priors: indexing and injection seams

*   **Status:** Proposed (architecture accepted; mechanisms deliberately left open)
*   **Date:** 2026-08-05
*   **Depends on:** ADR-0003 (inner-loop MRAC), ADR-0005 (identified ref models +
    adaptive law), ADR-0006 (sim package, `Plant` seam), ADR-0012 (plant ladder)
*   **Relates to:** ADR-0007 (state-space drive), ADR-0008 (CRM)

> **Novelty framing HELD, 2026-08-06.** The literature review found the closest published
> analogue to a prior library with runtime selection: **FAMLE** (Kaushik, Anne & Mouret, IROS
> 2020, arXiv 2003.04663) meta-trains several priors and selects the most suitable at runtime.
> Neural-Fly (*Science Robotics* 2022) is the continuous-basis version; MMAC is the classical
> version. σ-modification with a **non-zero attractor** survives the review as theoretically
> defensible — UUB is preserved when the adaptation equilibrium shifts from the origin to
> `θ₀` — but switching priors mid-flight makes the closed loop a **switched system**, and no
> paper does exactly this. That proof is the author's to write.
>
> **The architecture and injection seams below stand.** What is held is the *contribution
> claim*, pending a dedicated grilling session on the primary sources; reading path in
> [`docs/literature-review-findings/SYNTHESIS.md`](../literature-review-findings/SYNTHESIS.md) §7.

## Context

The working thesis hypothesis: **learn adaptive weights in simulation, per scenario, and
supply them to the real drone as scenario-conditioned priors / soft targets that its
online adaptation converges toward.** The runtime selection among priors is intended to
resemble soft attention — a similarity-weighted blend over stored scenario prototypes
rather than a hard switch.

Today the firmware starts every flight from `Theta = 0` and re-learns from scratch. A
known limitation already recorded in `CLAUDE.md` is that adaptive weights are lost on
power cycle (no EEPROM persistence). The prior mechanism addresses the more general
version of that problem: the drone should not begin each flight ignorant of dynamics it
has already characterised.

Two constraints bound the design space and were established before any mechanism was
chosen:

1.  **Dimensional validity.** `What` multiplies `Φ` to produce `u_ad` in Nm, so `θ*`
    depends on the plant's lumped input→output gain `K`. A prior is only meaningful on a
    plant with the `K` it was learned under (ADR-0012 D5, D8).
2.  **Target feasibility.** The detector and the injection both run on an STM32F4 (FPU
    present) inside a 200 Hz control loop. A transformer is infeasible. A softmax over
    `K` stored centroids with a `D`-dimensional feature vector is `K·D` MACs — trivially
    affordable.

## Decisions

### D1 — Prior *indexing* is a seam, not a fixed mechanism
Four candidate mechanisms are in scope and none is committed to:

| Mechanism | Runtime cost | Note |
|---|---|---|
| Soft attention over mismatch features → convex blend of `K` priors | `K·D` MACs | **Leading candidate.** Continuous; degrades to the mean prior when the scenario is unrecognised. |
| Hard nearest-scenario classification | `K·D` MACs | Discontinuous; needs hysteresis / dwell logic to avoid mid-flight prior swaps. |
| Commanded a priori (RC switch / mission phase) | 0 | **Retained as the control condition** — isolates "do priors help?" from "does detection work?". |
| Direct regression features → `What` | MLP forward pass | Most expressive; hardest to bound for safety and to defend. |

Follows the established pattern of `drive.py` (ADR-0007): "a new law is a new Drive, not
another branch in `update()`."

### D2 — The run log is the union, so mechanisms are fitted offline from one corpus
Every simulation run records:

*   scenario identity and its generating parameters,
*   the full feature time-series a runtime detector would have seen,
*   the converged `What` per axis,
*   the plant identity and its `(K, p, T)` (ADR-0012 D8),
*   the existing `metrics.json` block.

Consequence: **all four D1 mechanisms are fitted and compared offline against the same
corpus.** Trying a new indexing mechanism never requires re-running the simulator. This
is the decision that makes "test many ideas independently and in combination" affordable.

### D3 — The detector's feature space is the inner-loop mismatch signature
Features are windowed statistics of quantities the control loop **already computes**:
`e`, `ė`, `Φ`, `u_nom`, `u_ad`, and rate-response residuals. Rationale: the scenarios in
scope *are* plant changes, and a plant change is by definition observable in the tracking
error. No new sensors, no dependency on optical flow (which has a documented ~50 cm drift
issue), nothing that does not already live in RAM at 200 Hz.

### D4 — Prior *injection* is three orthogonal, independently switchable channels

| Channel | Mechanism | Knob | Controls |
|---|---|---|---|
| **Value** | σ-mod attractor: `−σ_prior·(Θ − Θ_prior)` replacing `−σ_eff·Θ` | `σ_prior` | where weights are pulled toward |
| **Authority** | additive feedforward `Θ_priorᵀΦ`, adaptation untouched | on/off, rate limit | direct control exerted by the prior |
| **Envelope** | scenario-conditioned `Γ`, `What_limit`, `e_deadzone` | per-scenario table | worst-case adaptation bounds |

They compose, giving an 8-cell experiment matrix driven from the existing run harness.

### D5 — The σ-mod attractor is the primary value channel
`API/mrac.c:274-279` already contains a leak-toward-a-target term — the L1 low-frequency
leakage `− σ_lf·(Θ[i] − Whatf[i])` — alongside the leak-toward-zero term `− σ_eff·Θ[i]`.
The prior attractor is structurally identical to a term already flying. The Lyapunov
argument carries over unchanged: σ-modification with a non-zero attractor bounds
`‖Θ − Θ_prior‖` instead of `‖Θ‖`.

**`σ_prior` spans the entire design space**, which is why it is the primary knob:

*   `σ_prior → 0` — today's baseline, prior has no effect,
*   `σ_prior → ∞` — hard initialisation `Θ = Θ_prior`,
*   intermediate — soft target, the intended regime.

One sweep therefore covers every point between "ignore the prior" and "trust it
completely", including the hard-init variant, without a separate implementation.

### D6 — The feedforward channel is the safe first hardware test
`u = u_nom + u_ad + Θ_priorᵀΦ` leaves the adaptive law **bit-identical** to the version
already validated, and the prior term can be rate-limited or killed independently of the
adaptation. This is the channel to enable first on the rig. Note that adaptation then
learns `θ* − Θ_prior`, so the two terms must be analysed jointly, not independently.

### D7 — The envelope channel is a safety result, not a performance result
Scenario-conditioned `What_limit` bounds the *failure mode* rather than chasing tracking
error: if the detector says "high-inertia payload", the adaptation's authority is capped
to what that regime can tolerate. This is reportable independently of whether the value
or authority channels help at all, and it degrades safely (an undetected scenario yields
the conservative default envelope).

### D8 — The prior factory requires no machine learning
Learning `Θ_prior` for a scenario is not a search: run the scenario, let the existing
adaptive law converge, record `Θ_final`. **The MRAC is the learner.** The factory is a
deterministic, seeded pass over `scenarios.ALL`.

Numerical search is needed only at the meta level (`σ_prior`, `Γ`, centroid placement),
and that search is **seeded deterministic code** (scipy / Optuna / CEM), never an LLM
choosing values — a search procedure must be reproducible by a reader to be defensible.

### D9 — AI agents are experimentalists, not optimizers
Agents implement controller variants, author scenario definitions, read `metrics.json`
across runs, propose design-level next steps, and write up findings. All numeric search
is deterministic code. The human remains the decision-maker; implementation and iterative
experimentation are delegated, understanding is not.

### D10 — The `What_lower_limit` sign constraint is a hard precondition
`API/mrac.c:353` sets `What_lower_limit[0] = −What_limit[0]` for the bias slot. If slots
1–5 remain clamped at 0, then weights live in `[0, What_limit]` and **any learned prior
with a negative component is unrepresentable on the target** — the projection clips it on
the first tick. This must be verified in firmware before any prior is learned. It is a
serial gate ahead of all parallel work.

Related known behaviour (`sim/README.md`): `What_lower_limit = 0` also means MRAC cannot
produce a negative `u_ad` at all, which is why `sim/experiments.py` Sweep A exists.

## Consequences

*   Priors are **plant-tagged** (ADR-0012 D8). A free-flight prior is not valid on the
    rig and vice versa. The rig is a distinct plant with its own pivot friction, added
    inertia and absent thrust-attitude coupling.
*   The validation chain is `sim → rig → free flight`. Transfer surviving two plant
    changes is a materially stronger claim than in-simulation performance.
*   A **mismatched-prior damage test** is a required experiment, not an optional one:
    inject the prior for scenario A while running scenario B and measure the harm. The
    honest failure mode of this thesis is "a confidently wrong prior is worse than no
    prior", and it must be characterised, not avoided.
*   `−σ_prior·(Θ − Θ_prior)` is a small firmware change to `MRAC_UpdateAxis`, mirroring
    an existing term. It requires firmware-parity implementation in `sim/adaptive_law.py`
    first (`sim/` is normative for the algorithm).
*   Prior persistence on the target is **not** solved here; it inherits the existing
    no-EEPROM limitation. Priors are ground-station-loaded until that is addressed.

## Open questions

*   Scenario centroid placement and count `K` — falls out of the first prior-factory
    runs; not decidable a priori.
*   Whether `σ_prior` needs to be separate from `σ_eff` in the firmware config (expected
    yes: `σ_eff` is doing robustness duty and should not be repurposed as a binding rate).
*   Feature window length and normalisation, which trade detection latency against
    scenario discriminability.
*   Whether the rig's constrained dynamics discriminate scenarios the same way free
    flight does — i.e. whether the detector itself transfers, not just the priors.
