# L1-NMPC: An L1 Adaptive Controller Cascaded with Nonlinear Model Predictive Control for Quadrotors

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

## L1-NMPC: An L1 Adaptive Controller Cascaded with Nonlinear Model Predictive Control for Quadrotors

**Relevance to thesis:** HIGH — proposes an L1 adaptive inner loop cascaded with a model-based outer loop, directly analogous to the project's MRAC inner-loop architecture, and demonstrates robustness to large mass/inertia mismatches and aerodynamic disturbances without gain tuning.

**Contribution:** A hybrid control architecture that cascades an L1 adaptive controller with a Nonlinear Model Predictive Controller (NMPC) to compensate for model uncertainties and disturbances online, with minimal computational overhead (10 μs).

**Method:** An L1 adaptive controller is placed at the rotor thrust level, using a piecewise-constant adaptation law and a first-order low-pass filter to decouple adaptation from robustness. This inner loop forces the physical quadrotor to behave like the nominal model used by the outer NMPC, which handles trajectory planning.

**Key results:**
- Over 90% tracking error reduction compared to non-adaptive NMPC under unknown payloads (up to 60% mass) and aggressive trajectories (p1, p5).
- Outperforms INDI-NMPC by 34% and GP-MPC by >90% in aggressive tracking with payloads (p6, p7).
- Real-time compensation of aerodynamic disturbances and rapid payload disturbance rejection with <1 cm steady-state error (p6).
- Achieves high-speed flight (peak 19.4 m/s) and agile tracking without updating controller gains or model parameters (p8).

**Relevant to YOUR work (with pages):**
- The L1 adaptive law decouples adaptation from robustness, enabling rapid compensation while maintaining stability under large mismatches — a property highly desirable for the project's MRAC experiments with larger mismatches (p2).
- The architecture cascades an adaptive inner loop with a model-based outer loop, mirroring the project's MRAC rate loop inside a trajectory tracker, and demonstrates that the adaptive controller enforces the physical plant to match the nominal model used by the outer controller (p8).
- The adaptation law operates at the actuator level (rotor thrust) using the same nonlinear dynamics as the outer controller, a design choice that could inform the project's MRAC placement and model structure (p7).
- The controller requires no online model retraining or gain tuning, directly addressing the project's goal of robust adaptation to parametric and non-parametric disturbances without manual intervention (p7).
- The L1 architecture's robustness to inertia and arm-length uncertainties suggests a path for handling the project's lumped parameter mismatches (J/b) identified during SysID (p5).

**How to apply / next step:**
- Compare the L1 piecewise-constant adaptation law and low-pass filter structure against the current MRAC law; evaluate if the decoupling of adaptation and robustness can simplify the Lyapunov P-matrix derivation or improve mismatch tolerance.
- Implement a simplified L1 inner loop in the 6-DOF Gazebo simulation for a single axis, cascaded with the existing outer-loop trajectory tracker, to benchmark tracking error reduction under the project's mass/inertia mismatch scenarios.
- Analyze the 10 μs computational overhead claim for feasibility on the STM32F4 target, considering the project's RTOS constraints and current MRAC loop timing.

---
*source:* https://arxiv.org/abs/2109.04210 · *8 pp* · *reviewer:* `deepseek/deepseek-v4-pro`
