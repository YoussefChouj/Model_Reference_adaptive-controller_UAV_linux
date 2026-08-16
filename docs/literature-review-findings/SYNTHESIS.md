# Literature review — cross-report synthesis and verdict

> Source: three independent deep-research agents run against
> [`docs/literature-review-brief.md`](../literature-review-brief.md), 2026-08-05/06.
> Reports in this directory. This file is the operative summary; the reports are evidence.
>
> **Framing decisions are HELD.** ADR-0013 and ADR-0014 keep their current framing until a
> dedicated grilling session, because the framing must rest on primary sources the author has
> read, not on an agent's summary of them. See "Reading path" at the bottom.

## 1. Which report to trust

The three reports disagree, and the disagreement is not symmetric.

| | Chowdhary ICRA 2013 | Girard 2024 | FAMLE | Verdict |
|---|---|---|---|---|
| `deep-research-report1.md` | missed | missed | missed | Over-reports novelty. Contains an outright error (below). |
| `deep-research-report2-Fable.md` | found | found | found | **Operative.** Every spot-checked citation resolved. |
| `deep-research-report-3-qwen-3.8max.md` | missed | missed | missed | Thin. Useful only on Q3b. |

Reports 1 and 3 searched and reported "unclaimed". Report 2 searched and returned named,
resolvable papers. **Absence of evidence loses to a citation that resolves.**

Known defects in report 1, recorded so nobody quotes it downstream:

* Q4 states σ-modification guarantees "steady-state parameter error `Θ̃(∞) = 0` even in the
  absence of disturbances". This is backwards. σ-mod's defining cost is that it pulls weights
  toward zero and therefore leaves `Θ̃(∞) ≠ 0` even with no disturbance. That property is the
  whole reason this project wants a **non-zero** attractor.
* Q10 gives `Γ_max < K·2sin(φ_m)/T` with no citation. Use the NASA method instead (§5).
* Q9 lists UZH-FPV as carrying motor commands. Report 2 says its actuator logging is limited
  because it is a VIO dataset. Verify before relying on it.

Known defect in report 3: it treats classical **regressor normalisation** (dividing `Φ` by
`1 + ΦᵀΦ` for numerical boundedness) as evidence about **dimensionless transfer**. These are
different things — one is mathematical conditioning, the other is physical unit scaling. This
project resolved that confusion before the review ran; do not let the report reintroduce it.

## 2. Citations verified against primary sources

Checked directly, not taken from the reports:

| Citation | Status | What it settles |
|---|---|---|
| Chowdhary, Wu, Cutler & How, "Rapid Transfer of Controllers Between UAVs Using Learning-Based Adaptive Control", **ICRA 2013**. MIT DSpace `1721.1/96961` | **Real** | Cross-vehicle controller transfer using **concurrent learning**, flown in MIT RAVEN, on quadrotors with very different inertia and throttle mapping. Nearest prior art to this whole programme. |
| Girard, "Dimensionless Policies based on the Buckingham π Theorem", **arXiv 2307.15852 / *Mathematics* 12(5):709, 2024** | **Real** | Policies restated in dimensionless variables transfer *exactly* to dimensionally similar systems, with a reduced parameter count. The rigorous form of the `C_L` analogy. |
| Kaushik, Anne & Mouret, "FAMLE", **arXiv 2003.04663, IROS 2020** | **Real** | Meta-train *several* priors, select the most suitable at runtime, adapt with few steps. The prior-library-with-selection mechanism, in MBRL. |
| Parikh, Kamalapurkar & Dixon, "Integral concurrent learning", **IJACSP 33(12):1775–1787, 2019** (arXiv 1512.03464) | **Real** | Removes the state-derivative requirement from CL by integrating dynamics over a finite window. Load-bearing for firmware. |
| Pereida, Helwa & Schoellig, "Data-Efficient Multirobot, Multitask Transfer Learning for Trajectory Tracking", **RA-L 3(2):1260–1267, 2018** (arXiv 1709.04543) | **Real** | L1 + iterative learning control transferring across quadrotors. |
| Satharasi, Ogri, Qureshi, Volle & Kamalapurkar, "Adaptive Control with Sparse Identification of Nonlinear Dynamics", **arXiv 2604.06338** (7 Apr 2026) | **Real** | SP-ICL: sparsity-promoting integral CL. SINDy-style online basis selection *with* a Lyapunov ultimate-boundedness result. Directly answers "how do I choose regressor features". |

Not independently verified, taken on report 2's word, flagged as preprints by report 2
itself: RAPTOR (arXiv 2509.11481), "One Net to Rule Them All" (arXiv 2504.21586),
dimensionless MPC (arXiv 2512.08667), Adaptive SINDy (arXiv 2603.08863). Re-check at
submission.

**Datasets — also verified directly, because `prior-13` Phase B depends on them.** NeuroBEM
carries time-aligned quadrotor state **and motor commands at 400 Hz**, plus rotor speeds and
ground-truth force, over >1 h 15 min of flight to 65 km/h. Blackbird carries **~190 Hz motor-
speed measurements from dedicated optical motor encoders**, 100 Hz IMU and 360 Hz motion
capture, over >10 h and 168 flights. Both therefore satisfy the identification requirement
(a commanded actuator channel time-aligned with body rate) and both sample **above** this
project's own 100 Hz 0x03 ID frame. Public-dataset prior fitting is practical; see `prior-13`
change 4 for the selection rule and the UZH-FPV caveat.

## 3. Novelty ledger

| Claim as previously held | Status after review |
|---|---|
| Cross-vehicle transfer of an adaptive controller is open | **Prior art.** Chowdhary ICRA 2013; Pereida RA-L 2018; Neural-Fly 2022. |
| Dimensionless transfer is an invented mechanism | **Prior art.** Girard 2024 established the mechanism for control policies generally. |
| Prior library + runtime selection is a new idea | **Prior art.** FAMLE does exactly this in MBRL; Neural-Fly does the continuous version; MMAC is the classical version. |
| Dimensionless **MRAC weight vectors** via the `1/K` matching argument | **Unclaimed.** Narrow but real. |
| Prior library realised **in MRAC weight space as a σ-mod attractor** | **Unclaimed.** |
| **Attention over a concurrent-learning history stack** | **Unclaimed — all three reports agree.** Highest novelty on the board. |
| **`Δs` (waypoint spacing) as an independent experimental variable** | **No literature either way.** Genuine white space. |
| Transferring a *populated* history stack across airframes | **Unclaimed**, and report 2 notes it is arguably ill-posed without rescaling. |

**The interlock.** A history stack recorded on plant A has `εⱼ` scaled by plant A's dynamics.
Transferring the stack is ill-posed *until* it is non-dimensionalised. So the two surviving
unclaimed slices are not two contributions — the `Θ̃` work is the precondition for the
transfer work. This is the strongest available framing, and it is exactly what the held
grilling session must test against the primary sources.

**Where the white space landed:** `Δs` is unclaimed *and* it is the primary claim. The
thesis priority settled on 2026-08-05 survives contact with the literature.

## 4. Falsified or reframed

1.  **Classical concurrent learning is the wrong algorithm here.** It requires `ẋ` — angular
    acceleration — which on an STM32F4 means differentiating a noisy gyro. Integral CL
    (Parikh/Kamalapurkar/Dixon 2019) removes the requirement. `prior-12` is rewritten to ICL.
2.  **"Concurrent learning replaces σ-mod / e-mod / deadzone" — falsified**, independently by
    reports 1 and 2. CL removes drift caused by *lack of excitation*. It does not remove
    drift caused by sensor noise, unmodelled dynamics, or the 15 ms transport delay.
    Projection is retained in essentially every published CL implementation.
3.  **Removing the deadzone entirely is unsafe.** Report 2 raises **bursting** (Ioannou &
    Sun): without a sufficient deadzone, the loop can cycle indefinitely between parameter-
    error growth and tracking-error peaks. `prior-11`'s learning envelope therefore may not
    set `e_deadzone → 0`.
4.  **`e_deadzone = 0.05` as a hand-tuned constant is not defensible.** The principled form is
    the *relative deadzone*: `e_deadzone ≈ k·σ_noise`, `k ∈ [2,3]`, from the **measured** gyro
    noise floor. This is the direct fix for the `prior-00b` finding that adaptation halts
    ~0.2 s into every run.
5.  **The RBF branch is closed on this hardware, for a principled reason.** The CL rank
    condition scales with basis dimension. Five Gaussians per axis over three rate axes is
    5³ = 125 basis functions, requiring ≥125 linearly independent recorded points. The 6-term
    structured basis requires 6 (15–30 for conditioning margin; under 1 kB). Structured also
    extrapolates better — GP-MRAC exists precisely because fixed-centre RBF networks fail
    outside their training domain.
6.  **The attention-stability claim in `wiki/concepts/attention-mechanism.md` is overstated.**
    TS/LPV stability machinery (common quadratic Lyapunov function, one LMI per local model)
    applies to *fixed, designed* membership functions. Attention has **learned** keys and a
    **moving** query, so a proof additionally requires bounding the membership functions'
    time derivatives. A route exists only if the keys are frozen. State it as an assumption,
    not a result.
7.  **The two-configuration split is not an established theoretical method** — it is an
    engineering heuristic. Reports 1 and 2 agree. It remains defensible if argued as: the
    learning envelope *discovers* the priors, the deployment envelope *deploys* them, and only
    the deployment envelope's guarantee has to hold in flight. `prior-11` must make that
    argument explicitly rather than assume it.
8.  **σ-modification with a non-zero attractor survives** (report 3, Q3b — its one useful
    contribution). Shifting the adaptation equilibrium from the origin to `θ₀` preserves UUB;
    the hard part is that switching priors mid-flight makes it a **switched system**, needing
    switched-system stability tools. No paper does exactly this. Maturity: theory. The proof
    is the author's to write.
9.  **Independent third-party reinforcement from Kunapuli et al., RSS 2025** (grilling memo
    [`leveling-the-playing-field.md`](leveling-the-playing-field.md), 2026-08-14). Two of their
    ablations land on positions we already hold: (a) training on a delay-/dynamics-free plant
    produces a controller that fails when evaluated under realistic motor dynamics — direct
    reinforcement of `ADR-0006 D4` and the `prior-00b` finding that drives `prior-02`; (b)
    substituting PID integral action for trajectory feedforward terms in GC is **worse** than
    no feedforward at all — direct reinforcement that the `prior-11` envelope cannot be
    replaced by integral action. Neither closes a novelty-ledger entry; both are citable
    corroborations.

## 5. Numbers the thesis must now answer to

Benchmark anchors, from report 2, for comparable trajectories:

| Result | Value |
|---|---|
| Neural-Fly, still air | **2.9 cm** mean tracking error |
| Neural-Fly margins | 42 % better than L1, 35 % better than INDI |
| RAPTOR, Crazyflie, 5.5 s figure-8 | **0.19 m** RMSE, zero-shot across 10 unseen quadrotors |
| NMPC + INDI vs NMPC + PID | 0.102 m vs 0.343 m position RMSE |
| Pereida/Schoellig cross-quadrotor transfer | **74 %** first-iteration error reduction |

That last one is the bar for the invariance claim: if dimensionless transfer does not reduce
cross-airframe first-flight error by a comparable margin, the airframe-invariance bonus
becomes a negative result — still publishable, but demoted.

**Adaptation gain under delay.** Time-delay margin → 0 as `Γ → ∞` for standard MRAC. Use
Nguyen et al., "On Time Delay Margin Estimation for Adaptive Control", NASA NTRS
20110016044 — matrix-measure method (least conservative) — to invert the identified 15 ms
delay into a `Γ_max`. Neglecting delay in simulation permits a `Γ` that is unstable in flight.

## 6. Honest position of MRAC in 2026

Plain MRAC is not the raw-performance leader for quadrotor inner loops. INDI and NMPC+INDI
lead agile tracking; learning-based methods lead disturbance rejection and cross-platform
generality. Fair head-to-heads generally do not favour plain MRAC.

The defensible arguments are interpretability (a 6-term physical regressor is human-readable),
provable Lyapunov/UUB bounds, embedded cost (200 Hz on an M4 where NMPC cannot run), and
certifiability. The live frontier is **MRAC as the stable online layer under a learned
representation** — Deep-MRAC, GP-MRAC, Neural-Fly. That is where this thesis sits. Do not
claim performance parity with L1/INDI; claim the properties they do not have.

## 7. Reading path for the held framing session

Ordered by how much each one moves the framing. Read the paper, not the report's summary.

1.  **Chowdhary, Wu, Cutler & How, ICRA 2013** (MIT DSpace `1721.1/96961`). The nearest prior
    art. Read to answer one question precisely: does it port the recorded `(Φⱼ, εⱼ)` pairs or
    the learned weights across airframes, or does it transfer only the *baseline* controller
    and re-learn on the target? Report 2 says the latter, and the whole remaining contribution
    depends on that being right.
2.  **Girard, *Mathematics* 12(5):709, 2024.** Read to check whether its dimensional-similarity
    condition is satisfiable between real quadrotors, or only between exact scale models. If
    only the latter, the transfer claim narrows again.
3.  **O'Connell et al., Neural-Fly, *Science Robotics* 7(66):eabm6597, 2022.** The primary
    baseline. Read the composite adaptation law and the stability result specifically.
4.  **Chowdhary & Johnson, CDC 2010** + **Parikh/Kamalapurkar/Dixon, IJACSP 2019.** The
    foundation and the fix. Read the rank condition and what ICL replaces it with.
5.  **FAMLE, arXiv 2003.04663.** Read the prior-selection rule — it is the closest published
    analogue to "the drone selects which prior to converge toward".
6.  *(as needed)* Ioannou & Sun, *Robust Adaptive Control* — deadzone, σ-mod, bursting,
    normalisation. The canonical reference for §4 items 3, 4 and 7.
