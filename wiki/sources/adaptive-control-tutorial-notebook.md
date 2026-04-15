---
title: Adaptive Control Tutorial Notebook
type: source
tags: [adaptive-control, tutorial, mrac, rbf, mass-spring-damper]
created: 2026-04-14
updated: 2026-04-14
sources:
  - "C:/Users/Acer/Desktop/Pich_yaw_roll_experimental_drone_setup/[Demonstration] - Microcontroller Control - Experiment 4 - Cascaded PID - dShot - FreeRTOS - Suspended/Adaptive_Control_Tutorial.ipynb"
---

This notebook is a progression-style simulation suite (18 code cells) moving from simple adaptive examples to neuro-adaptive and 2D mass-spring-damper cases. Code is treated as validated by the user.

## Coverage map

- Fixed-gain baseline (no adaptation).
- Scalar adaptive gain example and point-reference tracking variant.
- Reference-model-based adaptive gain configuration.
- Robustness modifiers:
  - projection operator,
  - sigma modification,
  - e-modification.
- Neuro-adaptive controllers with RBF bases:
  - 6-neuron,
  - 12-neuron,
  - 21-neuron,
  - variants with/without explicit bias and performance recovery.
- 2D mass-spring-damper adaptive control:
  - linear-parametric uncertainty form,
  - LQR-derived reference model terms,
  - feedforward gain shaping,
  - RBF versions with per-state and joint feature grids.

## Typical simulation settings observed

- `dt = 0.005 s` across sections.
- `ft = 10/20/40 s` depending on scenario.
- Initial-state and gain values adjusted per experiment cell.

## Why this source matters

- Provides a clean "ladder" of adaptive-law complexity.
- Useful for quick A/B comparisons before porting ideas to multi-axis drone simulations.
- Contains multiple ready-made RBF basis constructions and adaptation update templates.

## Related pages

- [[Adaptive Control Simulations]]
- [[Direct MRAC + FF + Projection Notebook]]
- [[MRAC Theory]]
