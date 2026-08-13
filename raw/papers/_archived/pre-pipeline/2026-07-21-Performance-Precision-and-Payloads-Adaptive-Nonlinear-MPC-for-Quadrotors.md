# Performance, Precision, and Payloads: Adaptive Nonlinear MPC for Quadrotors

- source: arXiv
- url: https://arxiv.org/abs/2109.04210
- published: 2021-09-09
- digest-date: 2026-07-21
- channel: #literature
- topic: literature
- signal: grabbed (?? reaction on the Discord digest)

## Abstract

Agile quadrotor flight in challenging environments has the potential to revolutionize shipping, transportation, and search and rescue applications. Nonlinear model predictive control (NMPC) has recently shown promising results for agile quadrotor control, but relies on highly accurate models for maximum performance. Hence, model uncertainties in the form of unmodeled complex aerodynamic effects, varying payloads and parameter mismatch will degrade overall system performance. In this paper, we propose L1-NMPC, a novel hybrid adaptive NMPC to learn model uncertainties online and immediately compensate for them, drastically improving performance over the non-adaptive baseline with minimal computational overhead. Our proposed architecture generalizes to many different environments from which we evaluate wind, unknown payloads, and highly agile flight conditions. The proposed method demonstrates immense flexibility and robustness, with more than 90% tracking error reduction over non-adaptive NMPC under large unknown disturbances and without any gain tuning. In addition, the same controller with identical gains can accurately fly highly agile racing trajectories exhibiting top speeds of 70 km/h, offering tracking performance improvements of around 50% relative to the non-adaptive NMPC baseline.

## My notes (typed on Discord)

- (no typed notes provided)

## Deep summary (grab pipeline)

## arxiv:2109.04210
**Relevance to thesis:** HIGH — directly demonstrates an adaptive control law for quadrotors that handles large model mismatches (mass, inertia, arm length) and external disturbances, which is the core of the Phase‑2 larger‑mismatch MRAC experiments.
**Contribution:** Proposes an L1 adaptive controller cascaded with nonlinear model predictive control (NMPC) that achieves robust trajectory tracking under severe parametric and non‑parametric uncertainties without any gain tuning.
**Method:** The L1 adaptive law compensates for model mismatch and disturbances in real time (10 μs) at the rotor thrust level, driving the system toward a desired reference model behaviour. It is cascaded with an NMPC that generates optimal trajectories, and the adaptation uses the same nonlinear dynamics as the NMPC.
**Key results:**
- L1‑NMPC reduces tracking error by >90 % compared to non‑adaptive NMPC under large disturbances (p1).
- Over 90 % error reduction in mass‑mismatch cases (p5).
- Robustness to inertia and rotor‑arm length uncertainties (p5).
- Rapid compensation for unknown payloads and aerodynamic disturbances (p6).
- 44 % tracking error reduction with an unknown slung payload (p6).
- Outperforms INDI‑NMPC and GP‑MPC by >90 % under unknown payloads and disturbances (p7).
- Achieves peak speeds of 11.9 m/s and velocities of 19.4 m/s (p8).

**Relevant to YOUR work (with pages):**
- The L1 adaptive law compensates for large parametric uncertainties (mass, inertia, arm length) without gain tuning (p5, p6), providing a direct benchmark for the MRAC’s robustness in the planned larger‑mismatch experiments.
- Real‑time adaptation with minimal overhead (10 μs) (p7) is feasible for the STM32F4 firmware and could be compared with the MRAC’s computational load.
- The cascaded L1+NMPC architecture (p2, p7) suggests a similar cascaded adaptive‑inner‑loop + trajectory‑planner structure that could be applied to the thesis’s NN path‑tracking outer loop.
- The paper’s demonstration on aggressive trajectories up to 70 km/h and unknown payloads (p2, p6) sets a performance envelope that the thesis’s trajectory‑tracking metric can be measured against.

**How to apply / next step:**
- Benchmark the thesis’s MRAC against the L1 adaptive law in the 6‑DOF simulation under the same mass/inertia/arm‑length mismatches to quantify robustness and computational trade‑offs.
- Implement the L1 adaptation law on the STM32F4 as an alternative inner‑loop controller, leveraging its 10 μs overhead, and compare tracking performance with the existing MRAC.
- Use the paper’s disturbance scenarios (slung payload, aerodynamic disturbances) as test cases for the Phase‑2 MRAC validation to ensure the Lyapunov‑based adaptation matches or exceeds the L1 performance.

---
*source:* https://arxiv.org/abs/2109.04210 · *8 pp* · *reviewer:* `deepseek/deepseek-v4-pro`
