---
title: Adaptive Control Tutorial 2 Notebook
type: source
tags: [adaptive-control, derivative-free, barrier, low-frequency-learning, tutorial]
created: 2026-04-14
updated: 2026-04-14
sources:
  - "C:/Users/Acer/Desktop/Pich_yaw_roll_experimental_drone_setup/[Demonstration] - Microcontroller Control - Experiment 4 - Cascaded PID - dShot - FreeRTOS - Suspended/Adaptive_Control_Tutorial_2.ipynb"
---

Second tutorial notebook focused on practical adaptive-control variants for beginners, including derivative-free adaptation and barrier-enabled neuro-adaptive control.

## Main sections

- Introductory adaptive-control framing for a simple mechanical system.
- Integral nominal adaptive controller on a 2D mass-spring-damper model.
- PID-style adaptive controller under measurement-noise conditions.
- Derivative-free adaptive controller (longer horizon test case).
- Set-theoretic neuro-adaptive controller with barrier function.
- Low-frequency-learning adaptive controller variant.

## Notable implementation patterns

- Reuses a consistent simulation skeleton (`dt = 0.005 s`) while changing adaptive laws.
- Demonstrates uncertainty switch logic in derivative-free experiments.
- Includes barrier-centric formulations as a bridge toward constrained adaptive control.
- Keeps tutorial-style progression while retaining runnable code blocks.

## Practical use in this project wiki

- Acts as the easiest entry point for quickly onboarding agents to adaptive-control experiment structure.
- Supplies smaller, focused templates before moving to full multi-axis simulation pages.
- Complements the first tutorial notebook by emphasizing derivative-free and barrier-related ideas.

## Related pages

- [[Adaptive Control Simulations]]
- [[Adaptive Control Tutorial Notebook]]
- [[Direct MRAC + FF + Projection Notebook]]
