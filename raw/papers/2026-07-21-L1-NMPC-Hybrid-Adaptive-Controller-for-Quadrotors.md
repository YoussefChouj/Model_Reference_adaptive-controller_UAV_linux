# L1-NMPC Hybrid Adaptive Controller for Quadrotors

- source: arXiv
- url: https://arxiv.org/abs/2109.04210
- published: 
- digest-date: 2026-07-21
- channel: #control-laws
- topic: control-laws
- signal: grabbed (?? reaction on the Discord digest)

## Abstract

(abstract not captured ? follow the source URL)

## My notes (typed on Discord)

- (no typed notes provided)

## Deep summary (grab pipeline)

## L1-NMPC Hybrid Adaptive Controller for Quadrotors
**Relevance to thesis:** HIGH — L1 adaptive control offers a decoupled robustness approach directly applicable to the inner-loop rate controller under large mismatches, aligning with Phase‑2 MRAC experiments and reference‑model design.
**Contribution:** Proposes an L1 adaptive controller cascaded with nonlinear model predictive control (NMPC) that compensates model uncertainties online with <5% computational overhead, achieving >90% tracking error reduction under unknown payloads and aggressive manoeuvres.
**Method:** The L1 adaptive law uses a piecewise‑constant adaptation mechanism and a linear reference model to enforce desired closed‑loop behaviour at the rotor‑thrust level, decoupling adaptation from robustness and requiring no online retraining. It runs in discrete time with a fast observer and is cascaded to the NMPC.
**Key results:**
- 90% tracking error reduction vs non‑adaptive NMPC under 60% unknown payload (p1, p5).
- 44% tracking error reduction with an unknown slung payload (p6).
- Rapid disturbance rejection with <1 cm steady‑state error (p6).
- Outperforms INDI‑NMPC and GP‑MPC by >90% under unknown payloads and aerodynamic disturbances (p7).
- Adaptation law executes in 10 μs with minimal overhead (p7).
- Maintains high tracking accuracy on agile trajectories up to 19.4 m/s without gain retuning (p8).

**Relevant to YOUR work (with pages):**
- The L1 controller compensates model uncertainties online with <5% computational overhead (p1) — a benchmark for our MRAC inner‑loop overhead on STM32F4.
- Decouples adaptation from robustness, enabling rapid compensation without gain tuning (p1) — directly relevant to our larger‑mismatch MRAC experiments where projection/leakage robustness is tested.
- Uses a linear reference model to enforce desired closed‑loop behaviour (p2) — analogous to our MRAC reference model; the design principle can inform our offline Lyapunov P‑matrix derivation for a chosen bandwidth (p2).
- Piecewise‑constant adaptation law and discrete‑time observer (p4) — an alternative adaptation structure to compare with our projection‑based MRAC law for robustness and implementation simplicity.
- Enforces the quadrotor to fly as the NMPC model describes (p8) — mirrors our goal of making the plant follow the reference model; suggests a reference‑model design that tightly couples with the outer‑loop trajectory controller.
- Cascaded inner‑loop adaptive control risks actuator constraint violations (p7) — a limitation we must address in our firmware when pushing the adaptive law near saturation.

**How to apply / next step:**
- Compare the L1 piecewise‑constant adaptation law (p4) to our MRAC projection/leakage approach in simulation under the same large‑mismatch scenarios (payload, inertia) to assess robustness and computational cost.
- Extract the reference‑model design rationale (p2, p8) to guide the offline Lyapunov P‑matrix derivation in `compute_reference_model.py`, ensuring the closed‑loop bandwidth matches the desired trajectory‑tracking performance.
- Analyse the actuator constraint violation risk (p7) and incorporate a saturation‑aware projection or anti‑windup scheme into our MRAC firmware before hardware tests.

---
*source:* https://arxiv.org/abs/2109.04210 · *8 pp* · *reviewer:* `deepseek/deepseek-v4-pro`
