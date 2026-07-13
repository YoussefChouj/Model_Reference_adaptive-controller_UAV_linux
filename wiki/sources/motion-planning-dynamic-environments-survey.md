---
title: Motion Planning in Dynamic Environments — Survey (2015–2025)
type: source
tags: [motion-planning, survey, mpc, reinforcement-learning, perception, thesis]
created: 2026-07-09
updated: 2026-07-09
sources: [raw/papers/2026-07-09-motion-planning-in-dynamic-environments-a-survey-from-classi.md]
---

Survey of 138 works (2015–2025) on how mobile robots plan motion when the world is *moving* — obstacles that walk, drive, or drift. Grabbed via 📥 from the #research-planning Discord digest on 2026-07-09. Thesis relevance: **MEDIUM** — background/positioning material, not something to implement now.

**Paper:** <https://openalex.org/W7163597202> (OA PDF: arXiv 2606.02677) · Deep briefing: [literature/openalex-W7163597202.md](../literature/openalex-W7163597202.md)

## Why you grabbed it (your Discord note, verbatim)

> i like this papaer because of how it survey the dynamical planning problem , the methods used and their advantages and limitations, i also like how it represents what an inteligent control system needs to account for in the real world.

## The one-paragraph mental model

Your thesis stack is a hierarchy: **perception** (where am I, what's around me) → **planning** (what path should I take) → **tracking control** (follow that path — this is where your MRAC + NN work lives) → **actuation**. This survey is about the *planning* layer one level **above** your current work. Today your drone flies pre-scripted paths (lemniscate, circle) in an empty room, so there is no planning problem yet. The survey matters because (a) it maps the field your BC/Transformer path-tracking must be positioned against in the thesis literature review, and (b) it shows what the planning layer will demand from your tracking layer if dynamic obstacles ever enter the picture (fast replanning → reference signals that change abruptly → adaptive tracking earns its keep).

## The three planning families (the survey's core taxonomy)

1. **Sampling-based** (classical): throw random points into free space, connect them into a graph/tree, search it. Canonical algorithms: RRT (Rapidly-exploring Random Tree), PRM (Probabilistic Roadmap). Strength: handles high-dimensional spaces, probabilistically complete. Weakness: replanning from scratch when obstacles move is expensive.
2. **Reactive**: no long-horizon plan — steer moment-to-moment from current sensor data. Examples: artificial potential fields, Dynamic Window Approach, velocity obstacles. Strength: fast, natural fit for moving obstacles. Weakness: short-sighted, prone to local minima and deadlocks (robot freezes or oscillates).
3. **Learning-based**: a neural network maps observations → motions, trained by RL or imitation. Strength: reacts fast at inference, can encode behaviours hard to hand-model. Weakness: the [[sim-to-real-gap]] — policies trained in simulation degrade on real hardware. **This is your thesis family**: behavioral cloning is imitation learning, so the survey's RL taxonomy (p9, p21) is your related-work section scaffold.

Sitting across families: **MPC (Model Predictive Control)** — repeatedly solve a short-horizon optimal-control problem, apply the first step, re-solve. Variants surveyed: *goal-oriented MPC* and *topology-driven MPC* (p8), plus MPC with [[conformal-prediction]] for uncertainty-aware deadlock handling. See [[motion-planning-methods]] for the full jargon glossary.

## Jargon decoder (terms the paper assumes you know)

| Term | Plain meaning |
|---|---|
| Dynamic environment | Obstacles move; a plan valid now may be invalid in 1 s |
| PPO | Proximal Policy Optimization — the default workhorse RL training algorithm |
| Hierarchical RL | Split the policy: high level picks subgoals, low level executes them |
| Reciprocal velocity obstacles (RVO) | Multi-agent collision avoidance where each agent assumes the *other* also yields half — prevents oscillating "after you / no, after you" behaviour (p21) |
| Conformal prediction | Statistical wrapper giving *calibrated* uncertainty bounds on any predictor — see [[conformal-prediction]] |
| Spatiotemporal attention | Transformer-style attention over space *and* time, used to predict how a scene will evolve (p9) — same mechanism family as your thesis Transformer |
| Sim-to-real gap | Simulation-trained policy underperforms on hardware — see [[sim-to-real-gap]] |
| Event camera | Sensor reporting per-pixel brightness *changes* at microsecond latency instead of frames — used for fast obstacle detection (p14) |
| Deadlock | Planner freezes/oscillates because dynamic obstacles create no clearly safe action |

## What it means for the thesis (and what it does NOT)

- **Literature-review scaffold (main value):** position BC + Transformer path tracking inside the survey's learning-based family; cite RVO and RL navigation (p9, p21) as the neighbouring problem one level up, and name sim-to-real as the shared open challenge.
- **Later, maybe:** goal-oriented / topology-driven MPC (p8) as predictive *reference generation* feeding the MRAC loop — only after Phase-2 sim validation.
- **Later, maybe:** spatiotemporal perception ideas (p9, p14) for a secondary vision pipeline to supplement the drifting optical flow.
- **Does NOT touch:** MRAC inner loop, reference-model/P-matrix design, the sim rebuild. Nothing here changes current firmware or `sim/` priorities.

## Prerequisites if you read the full PDF

You already have the control background (PID, MRAC). Before the learning sections, skim: what an MDP is (state/action/reward), the RL objective (maximize expected return), and policy-gradient in one sentence (nudge network weights toward actions that got reward). For the MPC sections: receding-horizon idea only — the paper doesn't require you to know solvers.
