---
title: Motion Planning Methods (Taxonomy)
type: concept
tags: [motion-planning, mpc, reinforcement-learning, taxonomy, thesis]
created: 2026-07-09
updated: 2026-07-09
sources: [raw/papers/2026-07-09-motion-planning-in-dynamic-environments-a-survey-from-classi.md]
---

Beginner map of how robots decide *where to go* — the layer above trajectory tracking (where the MRAC/NN thesis work lives). Source: [Motion Planning in Dynamic Environments survey](../sources/motion-planning-dynamic-environments-survey.md).

## Where planning sits in the robot stack

```
Perception  →  Planning  →  Tracking control  →  Actuation
(sensors,      (this          (PID/MRAC/NN —       (motor
 state est.)    page)          YOUR thesis)          mixer)
```

The planner outputs a path or trajectory; the tracking controller's job is to follow it despite disturbances and model error. A faster-replanning planner produces more abruptly-changing references — which is exactly when adaptive tracking (MRAC) matters.

## The three families

### 1. Sampling-based (classical, geometric)
Randomly sample robot configurations, connect collision-free ones into a tree/graph, search for a path.
- **RRT** — grow a random tree from start until it reaches the goal; good in high dimensions.
- **PRM** — pre-build a random roadmap of free space, then query it.
- Trade-off: (probabilistically) complete and well understood, but static-world at heart; when obstacles move you replan, which is costly.

### 2. Reactive (local, instantaneous)
No long plan — pick the next velocity from what sensors see *right now*.
- **Potential fields** — goal attracts, obstacles repel; simple but gets stuck in local minima.
- **Dynamic Window Approach** — search directly over feasible velocities for the next instant.
- **Velocity obstacles / RVO** — compute the set of velocities that lead to collision with a moving obstacle and steer outside it; the *reciprocal* variant has both agents yield half each, preventing mutual oscillation.
- Trade-off: fast and dynamic-friendly, but short-sighted → deadlocks and detours.

### 3. Learning-based (the thesis family)
A neural network maps observations → actions/paths, trained by reinforcement learning (PPO, hierarchical RL) or **imitation learning** — which includes the thesis' behavioral cloning from an expert pilot.
- Trade-off: fast inference and rich behaviours, but data-hungry, hard to certify, and hit by the [[sim-to-real-gap]].

## MPC — the cross-cutting fourth player

**Model Predictive Control**: every control cycle, solve "best trajectory over the next N steps" with a model of the robot, apply the first action, repeat (receding horizon). Sits between classical and modern: model-based like classical control, re-optimizing online like a planner.
- *Goal-oriented MPC* — cost shaped directly toward the goal in dynamic scenes.
- *Topology-driven MPC* — enumerate qualitatively distinct ways around obstacles (left vs right) and optimize within each, avoiding indecision between them.
- MPC + [[conformal-prediction]] — inflate obstacle predictions to calibrated uncertainty bounds so safety margins are principled, easing deadlocks.

Thesis hook: MPC-style *reference generation* feeding the MRAC loop is a possible post-Phase-2 extension — see the [survey source page](../sources/motion-planning-dynamic-environments-survey.md) for the "later, maybe" framing.
