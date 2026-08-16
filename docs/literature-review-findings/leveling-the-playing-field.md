# Kunapuli, Welde, Jayaraman, Kumar — *Leveling the Playing Field* (RSS 2025)

> Source: arXiv 2506.17832v1, RSS 2025. Code: [`PratikKunapuli/rl-vs-gc`](https://github.com/PratikKunapuli/rl-vs-gc).
> Grilling memo, 2026-08-14. Compared against the held primary sources —
> [Chowdhary ICRA 2013][chowdhary], [Girard *Mathematics* 2024][girard],
> [Neural-Fly *Science Robotics* 2022][neuralfly], [Parikh/Kamalapurkar/Dixon IJACSP 2019 (ICL)][parikh],
> [FAMLE IROS 2020][famle]. The held framing is recorded in [`../literature-review-findings/SYNTHESIS.md`](../literature-review-findings/SYNTHESIS.md).
>
> **Operative verdict.** Method paper. Does not infringe on any entry in the novelty ledger. Citable as third-party reinforcement of two findings already on the books, and as a procedural reference for the `prior-14` attention-ablation test frame.

## Abstract in two lines

Fair-comparison protocol for RL vs. geometric (PD/cascaded) controllers on a quadrotor and a quadrotor-with-fixed-arm. Holding tuning, data access, and feedforward horizon equal between the two controller classes **erodes** the headline RL-beats-GC gap reported in prior work — the gap is small, asymmetric-protocol bias is large. RL wins transient (agility); GC wins steady-state. Domain randomization and motor-dynamics fidelity confirm the result.

## What it claims that overlaps with held framing

| Claim | Closest held primary source | Verdict |
|---|---|---|
| Cross-vehicle controller transfer, baseline-PID augmented | [Chowdhary ICRA 2013][chowdhary] | **No overlap.** Kunapuli studies one vehicle, two controller classes; Chowdhary studies two vehicles, one adaptive controller. Different axis; both can be cited. |
| Bucking ham-π dimensionless policy transfer | [Girard 2024][girard] | **No overlap.** Girard is dimension-scaling of any policy; Kunapuli does not invoke scaling. Both can be cited. |
| Composite adaptation over a learned representation | [Neural-Fly 2022][neuralfly] | **Adjacent.** Neural-Fly is single-context wind rejection on one vehicle; Kunapuli is one vehicle, two controller classes. Different questions; both can be cited and the headline 2.9 cm error stands as the benchmark for any future disturbance-rejection result in this project. |
| Integral CL removes `ẋ` requirement | [Parikh 2019 (ICL)][parikh] | **No overlap.** Kunapuli has no CL machinery. Their adaptive updates are vanilla gradient on a single step. |
| Prior library with runtime selection | [FAMLE IROS 2020][famle] | **Adjacent.** FAMLE meta-trains several priors and selects at runtime; Kunapuli tunes *one* GC against the data. Different scale. |
| Motor-delay / learning-fidelity gap | `ADR-0006 D4` (delivered via `prior-00b`), called out in §History of this repo | **Direct reinforcement of our standing rule.** Kunapuli shows that a GC controller trained on a rigid-body (delay-free) plant is unstable when evaluated on a first-order-motor model. Our rule already forbids prior learning on a delay-free plant; this is third-party confirmation. **Cite in §Knowledge Stack.** |
| PID-as-feedforward-substitute worse than nothing in GC | `ADR-0013 D5` / `prior-11` envelope vs. integral | **Direct reinforcement.** Independent confirmation that *replacing* feedforward with integral action under auto-tuned gains can be net negative. Cite in `prior-11` journal and §Knowledge Stack. |

## Reusable artefacts (tool reuse, not contribution reuse)

1. **`eval_lissajous_curve` in `utils/trajectory_utilities.py` of the public repo** — analytic 0..4th derivatives of a Lissajous curve in a single tensorised call. `sim/trajectories.py` already has Lissajous-ish curves via `lemniscate.py` and `figure8.py`, but those expose derivatives only via finite differences. Analytic derivatives remove the need for a `get_desired_derivatives(n=4)` shim. Half a day to port to numpy + parity test against a Taylor series. Low-priority.

2. **Fig. 2 asymmetry grid as a comparison protocol** — for `prior-14`'s attention vs. uniform-stack-weighting ablation, the Kunapuli methodology (optimized × manual) × (hover × Lissajous) × (none × feedforward × PID) is a clean, paper-citable comparison frame that does not depend on GC.

3. **Optuna gain tuning in `gc_tuning.py`** — for any future controller-class tuning exercise, the Optuna-SQLite backend configuration is small enough to lift. Does not apply to `priors.py` directly: priors are state-dependent, not gain-dependent.

## What it does NOT change

- **No novelty-ledger entry is closed or opened** by Kunapuli et al. The four surviving unclaimed slices (dimensionless MRAC weights via `1/K` matching, prior library as σ-mod attractor, attention over a populated CL history stack, `Δs` as an independent experimental variable, and transferring a populated history stack) remain unclaimed.
- **No contribution claim is invalidated.** A naive reader could mistake Kunapuli's "fair RL vs. GC" framing for cross-vehicle transfer framing; this memo exists to prevent that mistake propagating.
- **No spec is opened or modified.** Wave 1 through wave 4 of `prior_transfer/` is unaffected.

## Reading order for the held-source review

If you only have time for one section: §IV (Methodology), pp. 4–6 in the arXiv HTML, focusing on §IV-C (Feedforward Terms) and the right column of Fig. 2 (the FF vs. PID-substitute ablation). The rest is reinforcement of known positions.

## Sources cited

- [arXiv HTML](https://arxiv.org/html/2506.17832v1)
- [Author project page](https://pratikkunapuli.github.io/rl-vs-gc/)
- [Code repository](https://github.com/PratikKunapuli/rl-vs-gc)

[chowdhary]: ../../../.agent_contracts/prior_transfer/README.md (Chowdhary ICRA 2013 entry, canonical citation list)
[girard]: ../literature-review-findings/SYNTHESIS.md (Girard 2024 entry, §2 verified citations)
[neuralfly]: ../literature-review-findings/SYNTHESIS.md (Neural-Fly 2022 entry, §2 verified citations)
[parikh]: ../literature-review-findings/SYNTHESIS.md (Parikh/Kamalapurkar/Dixon 2019 ICL entry, §2 verified citations)
[famle]: ../literature-review-findings/SYNTHESIS.md (FAMLE 2020 entry, §2 verified citations)
