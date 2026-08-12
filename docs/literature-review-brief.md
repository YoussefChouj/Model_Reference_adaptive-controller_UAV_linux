# Literature review brief — MRAC prior transfer for dense trajectory tracking

> **Status:** ready to hand to an external deep-research agent.
> **Written:** 2026-08-05, from the `/grill-with-docs` sessions that produced ADR-0012,
> ADR-0013 and ADR-0014.
> **Purpose:** ground or falsify the design decisions below *before* six months of
> implementation. Several are currently held on intuition and one unverified memory of the
> literature.

---

## PROMPT — paste everything below this line into the research agent

You are doing a background/literature review for a master's thesis in adaptive flight
control. Your job is **not** to confirm the plan below. Your job is to find out which parts
are already solved, which are wrong, and which are worth doing.

### The system, in one paragraph

A quadrotor (1.30 kg, X-frame, 0.2 m arms) runs a Model Reference Adaptive Controller as an
inner rate loop on STM32F4 firmware at 200 Hz, layered on a nominal PID cascade. Control is
additive: `u = u_nom + u_ad`, where `u_ad = Θᵀ·Φ(x)`. The regressor is a hand-designed
6-term structured basis `Φ = [1, x, x·tanh x, cross_coupling, u_nom, xm]`, where `x` is the
body rate, `xm` the reference-model state, and `cross_coupling` the gyroscopic product term.
The adaptive law is gradient with projection, σ-modification, e-modification, an error
deadzone, and per-component learning rates. The plant per axis is identified from flight
data as `G(s) = K/(s(1+s/p))·e^{−sT}` — for roll, `K≈165`, `p≈19.8 rad/s`, `T≈15 ms`,
VAF≈99%. A Python simulation package mirrors the firmware algorithm exactly, pinned by
golden-vector parity tests.

### The thesis claim

**Primary:** dense trajectory tracking. The vehicle follows firmware-generated paths
(point-to-point, sinusoid, circle, figure-8) sampled at a controllable waypoint spacing
`Δs`; performance is measured by position-tracking RMSE, cross-track error (distance to the
closed-form ideal curve) and along-track lag. Denser references are smoother; sparser
references produce a staircase that stresses the adaptation.

**Instrumental:** learn a library of adaptive-weight **priors** per flight scenario in
simulation, then have the vehicle select among them at runtime based on the detected
situation and converge toward the selected one — rather than adapting from zero every
flight. A secondary, "bonus" claim is that these priors are **airframe-invariant** when
expressed dimensionlessly, so priors learned on one vehicle (or in simulation, or from
public flight logs) serve trajectory tracking on another.

### Ground rules for your report

1. **Try to falsify.** For every question, actively search for work that makes the idea
   unnecessary, already-published, or known-not-to-work. A finding of *"this was solved in
   2014, here is the paper"* is worth more than a confirmation.
2. **Citations must be real and verifiable.** Give authors, title, venue, year, and DOI or
   arXiv ID. If you cannot verify a citation, say so explicitly rather than producing a
   plausible-looking reference. Some claims below are held "from memory" and are exactly
   the kind of thing that turns out to be misremembered.
3. **Prioritise 2022–2026.** The project's internal knowledge is reliable up to roughly
   2024 and thin after that. Recent work matters most, especially anything that supersedes
   the older results cited below.
4. **Say when something is unknown.** An honest "no literature found on this" is a
   contribution — it tells the author where the novelty is.
5. Note the **maturity** of each result: theory only, simulation only, or flown on
   hardware. This project flies real hardware, so hardware-validated results carry more
   weight.

---

## Tier 1 — these decisions are already made and would be expensive to reverse

### Q1. Concurrent learning and the rank condition

The plan is to add concurrent learning to make adaptive weights converge without persistent
excitation, using a history stack of recorded `(Φⱼ, εⱼ)` pairs and a second update term
driving `Θ` toward consistency with all stored points.

The understanding to verify — **currently held from memory, not from the papers**:

- Chowdhary & Johnson, *"Concurrent learning for convergence in adaptive control without
  persistency of excitation"*, CDC 2010, plus Chowdhary's PhD thesis.
- Claim: exponential convergence of **both** tracking error and parameter error, requiring
  only a rank condition on the recorded data (rank = number of basis functions), with **no
  persistent excitation**.

Please: verify these citations exist and say what they actually prove. Then:

- What are the **exact** assumptions? Does the guarantee need the uncertainty to lie in the
  span of the basis (structured matching)? What happens under unmodelled dynamics?
- How is the history stack **populated and evicted** in practice? What are the standard
  algorithms (singular-value maximisation, etc.) and their costs?
- What has **superseded** this since 2010 — integral concurrent learning, composite
  adaptation, derivative-free approaches, anything from 2022–2026?
- Has anyone **transferred a history stack between different vehicles**? That is the
  project's intended use and we have found no precedent.
- Practical minimum: how many stored points are actually needed for a 6-basis problem, and
  what does that imply for onboard memory on a Cortex-M4?

### Q2. Non-dimensionalisation of adaptive weights — is there precedent?

The reasoning: the matching condition `K·Θ*ᵀΦ = −Δ` places a factor `1/K` in every weight,
where `K` is the lumped input→output gain (torque effectiveness folded with `1/J`). So a raw
`Θ` in command units is vehicle-specific and cannot transfer. The plan stores a
dimensionless `Θ̃` — dividing out plant scales already present in the controller config
(`u_max`, `J`, `mixer effectiveness`, a characteristic rate) — by analogy with
non-dimensional aerodynamic coefficients such as `C_L`.

**This is the decision we are least confident has precedent.** Please search hard for:

- Any work on **normalised or dimensionless parameterisation of adaptive weights**,
  Buckingham-Pi analysis applied to adaptive control, or scaling laws for MRAC parameters.
- **Normalised regressors** in adaptive control — how is regressor normalisation usually
  motivated? Numerical conditioning? Robustness? Transfer? Does normalisation change the
  stability proof or the convergence rate?
- Any work on **transferring adaptive-control parameters between different plants** at all,
  under any name: parameter transfer, controller transfer, cross-platform adaptive control,
  scaling of adaptive gains.
- Adjacent fields that solved this: is there a standard non-dimensionalisation for
  quadrotor control parameters (analogous to `C_L`) that we should simply adopt rather than
  invent?

If this genuinely has no precedent, say so — that changes it from a mechanism into a
contribution.

### Q3. Scenario-conditioned priors — what is the closest prior art?

The idea: a library of pre-learned weight vectors indexed by flight scenario; at runtime the
vehicle detects the situation and converges toward the matching prior, implemented as a
σ-modification whose attractor is the prior rather than zero.

Identify the closest existing work and say plainly whether this is a re-derivation:

- **Multiple Model Adaptive Control / Estimation** (MMAC / MMAE), switching and blending
  supervisory control — Narendra & Balakrishnan's multiple-model architectures. How close
  is this already?
- **Gain scheduling and LPV control** — the classical answer to "different gains for
  different operating points."
- **GP-MRAC** (Gaussian-process MRAC, Chowdhary et al.) and Bayesian adaptive control, where
  a prior over the uncertainty is explicit and principled.
- **Meta-learning / learning-to-adapt for control** — MAML-style fast adaptation, and in
  particular the *Neural-Fly* line of work (Caltech, ~2022) which learns a basis offline and
  adapts coefficients online. That may be extremely close to this thesis. Report precisely
  what it does and how it differs.
- **L1 adaptive control** with pre-specified filters.

For each: what does it guarantee, what has been flown, and what specifically is left
unclaimed that this thesis could contribute?

### Q3b. σ-modification with a non-zero attractor — does the stability argument survive?

The planned injection mechanism replaces the standard σ-modification leakage term

```
   Theta_dot  =  -Gamma ( e P Phi )  -  sigma * Theta          (leaks toward ZERO)
```

with one that leaks toward the selected prior:

```
   Theta_dot  =  -Gamma ( e P Phi )  -  sigma_prior * (Theta - Theta_prior)
```

so the bounded set is `‖Θ − Θ_prior‖` rather than `‖Θ‖`. The project's working assumption is
that the Lyapunov argument carries over unchanged, with the bound simply re-centred on the
prior. **This has not been checked against the literature and it is load-bearing** — it is
the primary of three planned injection channels.

- Is leakage toward a **non-zero reference weight** an established modification? Under what
  name — σ-modification with a non-zero centre, "leakage to a prior", Bayesian-style
  regularisation toward a nominal parameter, damped least-squares?
- Does the uniform ultimate boundedness result carry over directly, and what does the final
  bound become? Specifically: does the guaranteed bound now depend on `‖Θ_prior − Θ*‖`,
  i.e. does a **wrong** prior enlarge the ultimate bound rather than merely slowing
  convergence?
- What happens when the prior is switched **during flight** as the detected scenario
  changes? Switched-system stability, dwell-time conditions, and whether blending (rather
  than switching) is required for a guarantee.
- Is `σ_prior → ∞` (hard initialisation to the prior) a degenerate case with its own known
  behaviour?

This question is the theoretical counterpart to Q3's prior-art search, and it decides
whether the primary injection channel is defensible.

### Q4. The robustness-versus-learning tension

The controller carries σ-modification, e-modification, projection bounds and an error
deadzone. A measurement in this project found the deadzone (`e_deadzone = 0.05`) halts
adaptation roughly 0.2 s into a run against a well-tuned baseline — so almost nothing is
learned, and a recent bounds fix changed RMSE by only 2–3 %.

The proposed response is to **separate a permissive "learning" configuration used in
simulation from a conservative "deployment" configuration used in flight**, and to argue
that concurrent learning removes the drift that motivated the deadzone in the first place.

- Is this two-configuration split established practice, or naive? What is it called?
- What does the literature say about deadzone / σ-mod / e-mod **preventing parameter
  convergence**, as opposed to merely biasing it?
- Does concurrent learning genuinely **replace** these robustness modifications, or is it
  normally used alongside them? What do the papers actually recommend?
- Is there a principled way to set a deadzone from the noise floor rather than by tuning?

---

## Tier 2 — open design questions where a good answer changes the approach

### Q5. How should the regressor basis be chosen?

Current basis is hand-designed from physics. The intent is to test alternatives and possibly
use different bases for different flight regimes.

- What are the **principled basis-selection methods** for adaptive control? In particular:
  is **SINDy** (sparse identification of nonlinear dynamics, Brunton et al.) used for
  selecting adaptive-control regressors, and does that combine with stability guarantees?
- **Structured / physics-based** versus **RBF or other universal approximators**: what is
  the current consensus on the trade-off? Specifically, what does the unstructured choice
  cost in terms of the concurrent-learning rank condition (N basis functions require ≥N
  independent recorded points)?
- Is switching or blending **different bases per flight regime** something anyone has done?
  What broke?
- How are **RBF centres** placed in practice, and does anyone normalise the state so that
  centres transfer between vehicles?

### Q6. Attention, Takagi–Sugeno fuzzy systems, and gain scheduling

This project has internally derived (and numerically verified) that softmax attention is
identical to a Takagi–Sugeno fuzzy blend and to LPV gain scheduling: query ↔ operating
point, keys ↔ stored conditions, values ↔ stored gains, softmax ↔ normalised membership
functions. It also verified that attention with an exponential dot-product kernel is
Nadaraya–Watson kernel regression, reducing exactly to a Gaussian RBF when query and key
norms are constant. The consequence claimed is that **TS/LPV stability theory (common
quadratic Lyapunov function, one LMI per local model) applies directly**, so a stability
proof route already exists.

- Is this equivalence **published**? By whom, and stated how precisely?
- Does the TS/LPV stability machinery genuinely carry over to a softmax-blended controller,
  or are there conditions (membership-function smoothness, sector bounds, the fact that
  attention's "centres" are learned rather than designed) that break it?
- Has anyone used **attention specifically to query a concurrent-learning history stack**?
  This project believes that is unclaimed and is considering it as a contribution.
- What is the state of **attention- or transformer-based adaptive/flight control** in
  2024–2026, especially anything running on embedded hardware?

### Q7. Dense trajectory tracking — is the metric set defensible?

Performance is reported as position-tracking RMSE, cross-track error against the closed-form
ideal curve, and along-track lag, swept over waypoint spacing `Δs`.

- What are the **standard benchmarks and metrics** in the quadrotor trajectory-tracking
  literature? Is this metric set conventional, incomplete, or unusual?
- Is **reference density / waypoint quantisation** treated as an experimental variable
  anywhere? This project treats `Δs` as a first-class knob and would like to know whether
  that is novel or standard.
- What tracking performance do **comparable published controllers** achieve on comparable
  vehicles? The thesis needs numbers to be compared against.
- Are there standard trajectory sets (lemniscate, circle, aggressive) with published
  baselines that should be adopted for comparability?

### Q8. Where does MRAC actually sit in 2026?

An uncomfortable but necessary question. Given INDI, geometric control, L1 adaptive control,
NMPC, and learning-based controllers (NeuroBEM, RL-based, differentiable simulation):

- Is classical MRAC still competitive for quadrotor inner-loop control, or has it been
  superseded in practice? By what, and on what evidence?
- What do recent comparisons show — is there a fair head-to-head anywhere?
- If MRAC is dominated on raw performance, what is the honest remaining argument for it
  (interpretability, provable bounds, embedded cost, certifiability)? The thesis needs to
  state this defensibly rather than ignore it.
- Conversely: is there recent work that **revives** MRAC by combining it with learned
  components? That would be the most directly relevant related work.

---

## Tier 3 — useful, lower stakes

### Q9. Public quadrotor flight datasets

The plan is to fit priors from public flight logs. Crucially, the logs do **not** need to
come from a vehicle running this MRAC: rate and motor-command data are enough to identify
`(K, p, T)` per airframe, from which the ideal weights for a given reference model can be
computed analytically. This would give multi-airframe evidence cheaply.

- Which public datasets actually exist and are usable? Candidates believed relevant but
  **not verified**: PX4 / Betaflight blackbox log corpora, NeuroBEM (ETH), UZH-FPV,
  Blackbird (MIT). Confirm or correct.
- For each: what signals, what sample rate, whether motor commands and setpoints are
  included, vehicle diversity, licence.
- Has anyone used such corpora for **cross-vehicle system identification** or for learning
  transferable dynamics models?

### Q10. Transport delay and adaptation aggressiveness

This project treats the identified ~15 ms transport delay as load-bearing — dropping it from
simulation makes the plant falsely stable and permits unrealistically aggressive learning
rates.

- What does the literature say about **delay margins in adaptive control** and how delay
  bounds the achievable adaptation rate?
- Is there a standard way to compute a maximum safe `Γ` from an identified delay?

### Q11. Sim-to-real transfer for control parameters

- What is current practice for **domain randomisation** when transferring *controller
  parameters* (as opposed to RL policies)?
- Is randomising over an ensemble of airframes an established way to obtain
  vehicle-invariant control parameters, and what does it actually buy?

---

## Output format

Please structure the report as:

1. **Executive summary** — the five findings that most change the plan, stated bluntly,
   including anything that says "this is already published, don't build it."
2. **Per-question sections** in the order above. For each: what the literature says, the key
   citations with verifiable identifiers, maturity (theory / simulation / flown), and a
   direct answer to the decision at stake.
3. **Claims we hold that you could not verify** — explicitly list any assertion in this
   brief that you found no support for, or found contradicted. This section matters as much
   as the rest.
4. **Contribution assessment** — of the ideas here, which look genuinely unclaimed:
   dimensionless prior transfer, attention over a concurrent-learning history stack,
   per-regime basis switching, `Δs` as an experimental variable, cross-vehicle prior
   transfer. For each: novel, incremental, or already done.
5. **Reading list** — 15–25 papers, ranked, with a one-line reason for each and a note on
   which are essential versus optional.

Where a decision in this brief should be reversed, say so directly and name the alternative.
