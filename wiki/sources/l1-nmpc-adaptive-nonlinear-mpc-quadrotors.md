---
title: "L1-NMPC — Adaptive Nonlinear MPC for Quadrotors (Hanover et al., RA-L 2021)"
type: source
tags: [l1-adaptive-control, nmpc, quadrotor, adaptive-control, disturbance-rejection, thesis]
created: 2026-07-31
updated: 2026-07-31
sources: [raw/papers/2026-07-21-Performance-Precision-and-Payloads-Adaptive-Nonlinear-MPC-for-Quadrotors.md, raw/papers/2026-07-21-Performance-Precision-and-Payloads-Adaptive-Nonlinear-MPC-for-Quadrotors.pdf]
---

An adaptive inner loop bolted underneath a nonlinear MPC, flown on real hardware at 70 km/h with unknown payloads. Grabbed via 📥 from the #control-laws Discord digest on 2026-07-21. Thesis relevance: **HIGH** — this is the closest published analogue to what your firmware does, by the group (UZH RPG) that sets the performance bar in agile quadrotor control.

**Paper:** <https://arxiv.org/abs/2109.04210> · Deep briefing: [literature/arxiv-2109.04210.md](../literature/arxiv-2109.04210.md) · Video: <https://youtu.be/8oB1rG5iYc4>

## Why you grabbed it (no typed Discord note)

You reacted 📥 four separate times to four differently-titled digest entries of this same arXiv ID, all in #control-laws. Read that as: the topic kept surfacing and kept looking relevant.

## The one-paragraph mental model

Your firmware is **PID nominal + MRAC correction**, and this paper is **NMPC nominal + L1 correction**. Structurally the same sandwich: a *baseline* controller that assumes a model, plus an *adaptive* layer that learns what the model got wrong and cancels it in real time. Swap the baseline (PID → NMPC) and swap the adaptive law (MRAC → L1) and you have this paper. The reason it matters to you is not the MPC half — you will never run a 100 Hz SQP on an STM32F4 — it is the **L1 half**, which is a redesign of the same adaptive idea your `mrac.c` implements, with one specific architectural change that fixes MRAC's oldest practical problem: in classical MRAC, turning up the adaptation gain to react faster *also* makes you less robust, because the fast learning signal goes straight to the motors. L1 breaks that link by inserting a low-pass filter between the estimate and the actuator, so you can estimate the disturbance as fast as your sample rate allows and *separately* choose how much of it the actuators are allowed to see.

## Where it sits relative to your thesis

| Layer | Your stack | This paper |
|---|---|---|
| Path / reference generation | AutoflyTask trajectories; later the BC/Transformer net | NMPC over a prediction horizon |
| Outer position loop | Cascaded PID (`locxPID`, `locyPID`) | folded into the NMPC |
| Inner rate loop | PID + [[mrac-control-law]] at 200 Hz | L1 adaptive at rotor-thrust level |
| Actuation | Motor mixer → TIM3 PWM | closed-loop rotor-speed control on a Radix FC |

So: **the paper's L1 block occupies exactly the slot your MRAC block occupies.** The NMPC occupies the slot your PID cascade *plus* your future NN tracker will occupy. That makes this simultaneously a benchmark for your inner loop and a picture of the architecture your outer loop is heading toward.

## The four ideas worth extracting

### 1. Decoupling adaptation speed from robustness (p2, p4, Eq. 12–13)

The paper's stated reason for choosing L1 over MRAC: *"its inherent ability to provide rapid adaptation that is decoupled from the robustness of the controller"* (p2, citing Hovakimyan & Cao). Mechanically:

- **Estimate** the uncertainty `σ̂` as fast as you like (here: solved algebraically every sample, Eq. 11).
- **Filter** it before it becomes a control signal: `u_L1 = −C(s) σ̂`, a first-order low-pass with cutoff `ω_co`.
- Discrete form used in the paper (Eq. 13): `u_L1,k = u_L1,k−1·e^(−ω_co·T_s) − σ̂_m,k·(1 − e^(−ω_co·T_s))` — an exponential-smoothing one-liner.

Your MRAC has no such separation: `gamma[]` sets how fast `Theta[]` moves, and `Theta` immediately scales `u_ad` into the mixer. One knob, two jobs. See [[l1-adaptive-control]].

### 2. Matched vs unmatched uncertainty (p3–p4)

A quadrotor can only accelerate along body-z. So disturbances in body X/Y acceleration (`σ_um`) sit in the null space of the input matrix — no combination of the four rotor thrusts cancels them directly; the vehicle must *tilt* first, which is the outer loop's job. Everything else — body-z acceleration and all three angular accelerations (`σ_m`) — is directly cancellable. The paper estimates both but only feeds the matched part to the control law. See [[matched-unmatched-uncertainty]].

### 3. Piecewise-constant adaptation instead of an integrating update law (Eq. 11, p4)

Classical MRAC (yours): `Θ̇ = Γ·Φ·e` — an integrator, so you need `Γ`, projection bounds, leakage, and deadzones to keep it from drifting or winding up. Your firmware has all four (`gamma[]`, `What_limit[]`, leak flags, `e_deadzone`).

L1's piecewise-constant law instead *solves* for the uncertainty each sample from the observer error `z̃`, using the known input matrix `G` and a matrix `Φ = A_s⁻¹(e^{A_s T_s} − I)`. There is no adaptation-rate gain to tune, and nothing integrates, so nothing winds up.

### 4. Integral action is not a substitute for adaptation (Table II, p5)

The authors added an integrator on position error to the NMPC as a fair-comparison baseline. Against **mass** mismatch it helped a lot (69–93 % error reduction). Against **inertia** and **arm-length/CG** mismatch it made things *catastrophically worse* — up to **−196 %**, i.e. tracking error roughly tripled. Integral action fixes constant offsets; it fights dynamics.

## Jargon decoder

| Term | Plain meaning |
|---|---|
| NMPC | Nonlinear Model Predictive Control — repeatedly solve a short-horizon optimal-control problem over the nonlinear model, apply only the first input, re-solve next tick. See [[motion-planning-methods]] |
| Multiple shooting | Discretise the horizon into segments, let the solver treat each segment's start state as a variable with a continuity constraint. More numerically robust than single shooting |
| SQP / real-time iteration | Sequential Quadratic Programming; RTI = do only *one* SQP iteration per control tick so the solve time is bounded and predictable |
| ACADO | Open-source toolkit that code-generates fast embedded NMPC solvers |
| Matched uncertainty | Disturbance entering through the same channel as your control input → directly cancellable |
| Unmatched uncertainty | Disturbance in the null space of the input matrix → not directly cancellable |
| State predictor / L1 observer | A model of the plant run in parallel; the *difference* between its state and the measured state is what reveals the uncertainty |
| Hurwitz matrix (`A_s`) | All eigenvalues have negative real part → the observer error decays. Here it sets observer bandwidth |
| Piecewise-constant adaptation law | Uncertainty estimate is recomputed and held for one sample period, rather than integrated continuously |
| `C(s)` / `ω_co` | The low-pass filter and its cutoff — the robustness knob of L1 |
| INDI | Incremental Nonlinear Dynamic Inversion — see [[indi-control]] |
| GP-MPC | MPC whose model residual is learned offline by a Gaussian Process; accurate but 5× the compute and cannot adapt online |
| MPPI | Model Predictive Path Integral — sampling-based MPC. Rejected here: 23 ms/update, oscillatory |
| SRT-NMPC | Single Rotor Thrust NMPC — the NMPC commands four individual rotor thrusts rather than collective thrust + body rates |
| Thrust-to-weight 4.5 | Their 750 g test drone can produce 4.5× its weight in thrust. **Yours is far lower** — relevant to whether their results transfer |

## Prerequisites if you read the full PDF

You already have PID, MRAC, Lyapunov adaptation, and quaternion attitude — that covers §III-A, §III-B and most of §III-D. Two gaps worth 20 minutes each before §III-C and Eq. 11:

1. **Receding horizon in one sentence:** at each tick, optimise a sequence of future inputs over N steps, apply input #1, throw the rest away, repeat. That is all you need; the solver internals are not load-bearing for your reading.
2. **Why `Φ = A_s⁻¹(e^{A_s T_s} − I)` appears:** it is the exact discrete-time integral of `e^{A_s t}` over one sample — the "how much did the observer error accumulate over this sample due to the unknown input" factor. Inverting it converts observed error back into the input that must have caused it.

## What it does NOT give you

- **No stability proof for the cascade.** The L1 theory guarantees bounds for the inner loop; the paper does not prove the NMPC+L1 cascade stable, it demonstrates it.
- **No path to running NMPC on your hardware.** 0.81 ms/solve on an i7 laptop, and they still needed a Jetson TX2 onboard.
- **No help with your optical-flow drift.** They fly on Vicon at 400 Hz. Their state estimate is essentially perfect; yours is the weak link, and every number in the paper implicitly assumes that away.

## See also

- [[l1-adaptive-control]] — the control law, and the honest MRAC-vs-L1 comparison
- [[matched-unmatched-uncertainty]] — why a quadrotor must tilt to reject lateral wind
- [[indi-control]] — the method that actually beat L1 on racing trajectories
- [[mrac-control-law]] — what your firmware does today
- [[MRAC Theory]] — your adaptation law's theory-to-code mapping
