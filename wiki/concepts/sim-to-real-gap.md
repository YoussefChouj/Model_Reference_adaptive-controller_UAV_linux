---
title: Sim-to-Real Gap
type: concept
tags: [simulation, machine-learning, gazebo, thesis, stub]
created: 2026-07-09
updated: 2026-07-09
sources: [raw/papers/2026-07-09-motion-planning-in-dynamic-environments-a-survey-from-classi.md]
---

*Stub — central to the thesis; expand as the Gazebo/digital-twin work matures.*

A policy trained in simulation performs worse on the real robot, because simulation is never the real world: simplified dynamics (motor lag, battery sag, frame flex), clean sensors vs. noisy/delayed real ones, and rendering vs. real cameras.

## Standard mitigation techniques

- **Domain randomization** — randomize sim parameters (mass, friction, latency, sensor noise) during training so the real world looks like "just another sample".
- **System identification** — measure the real plant and make the sim match it. *The project already does this*: the SysID excitation module + torque-stand and moment-of-inertia measurements exist precisely to shrink this gap for the digital twin.
- **Fine-tuning on real data** — collect a small real-world dataset and adapt the policy.
- **Adaptive control at runtime** — let the low-level controller absorb residual model error. This is the quiet synergy in the thesis: the NN tracks in a slightly-wrong world, and **MRAC adapts away part of the mismatch online**.

## Why it matters for the thesis

The plan — behavioral cloning from an expert pilot, trained/validated in a Gazebo digital twin, deployed on the STM32 quadrotor — crosses this gap by construction. The [motion-planning survey](../sources/motion-planning-dynamic-environments-survey.md) flags sim-to-real as the key open challenge for all learned navigation (p9, p21); cite it in the thesis when motivating the digital-twin fidelity work and the MRAC safety net. See [[motion-planning-methods]].
