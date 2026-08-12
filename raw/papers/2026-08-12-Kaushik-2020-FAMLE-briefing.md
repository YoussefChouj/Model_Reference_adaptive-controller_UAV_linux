---
title: "FAMLE — Fast Adaptation through Meta-Learning Embeddings of Simulated Priors"
type: literature
tags: [meta-learning, prior-library, few-shot, mbrl, minitaur, simulation-to-real, thesis]
created: 2026-08-12
sources: [arXiv:2003.04663, IROS 2020]
---

Raw ar5iv source: raw/papers/2026-08-12-Kaushik-2020-FAMLE-iros2003.04663.md

## Paper Identity

Kaushik, Anne, Mouret (Inria/CNRS). IROS 2020. DOI: 10.1109/IROS45743.2020.9341462. Code: `resibots/kaushik_2020_famle`.

## Core Claim

When meta-training situations have diverse dynamics, a single set of meta-trained parameters (MAML) is insufficient. FAMLE meta-trains *multiple* initial parameter sets (embeddings), one per situation class, enabling rapid selection + gradient fine-tuning on the real robot with few shots.

## Method

**Offline:**
- Meta-train multiple initial model parameters `θ_0^s` for different simulated situations `s` (e.g., different floor friction values, motor failures).
- Each `θ_0^s` is a "simulated prior" on dynamics.

**Online:**
- Collect a few real-robot rollouts.
- Select the best-matching `θ_0^s` via Bayesian optimisation over the latent context.
- Fine-tune selected `θ_0^s` with gradient steps on real data.

**Key insight:** A *library* of priors beats a single prior when the deployment regime is unknown and diverse.

## Relevance to thesis

HIGH — the "prior library as σ-mod attractor" idea parallels FAMLE's multiple-prior selection. Their Bayesian context selection is analogous to your scenario-conditioned prior selection.

## Key differences from your work

- FAMLE is model-based RL (learn dynamics model). You are direct MRAC (no plant model).
- FAMLE fine-tunes model parameters; you adapt control gain vectors.
- FAMLE needs a few real-robot rollouts before adapting. You adapt from the first flight.
- No dimensionless framing — their priors are situation-class parameters, not dimensionless invariants.

## What to grill on

1. How many simulated priors are needed for the prior library to cover the deployment space with high probability?
2. Can the prior library be compressed via dimensionality reduction (your `Δs` approach)?
3. What is FAMLE's worst-case adaptation time before the robot is safe to operate?
4. Does FAMLE guarantee stability during the fine-tuning phase?
