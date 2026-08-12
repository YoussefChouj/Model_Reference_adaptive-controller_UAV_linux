---
title: "Neural-Fly — Rapid Learning for Agile Flight in Strong Winds"
type: literature
tags: [adaptive-control, quadrotor, meta-learning, wind-disturbance, composite-adaptive-law, daiml, thesis]
created: 2026-08-12
sources: [arXiv:2205.06908, Science Robotics, Science Robotics 2022]
---

Raw ar5iv source: raw/papers/2026-08-12-Neural-Fly-arxiv2205.06908.md

## Paper Identity

O'Connell, Shi, Shi, Tian, Liu, Kumar, Anandkumar, Yue, Chung (Caltech). *Science Robotics* 2022. DOI: 10.1126/scirobotics.abm6597. Code: `aerorobotics/neural-fly`.

## Core Claim

DAIML-learned wind-invariant aerodynamic basis + composite Kalman-filter adaptation → centimeter-level tracking in 12.1 m/s wind, extrapolates to unseen conditions.

## Method

**Offline (DAIML):**
- Spectral-normalized DNN learns wind-invariant aerodynamics representation.
- Output = basis functions; linear coefficients `a(w)` are wind-specific.
- 12 min flight data across 6 wind conditions.

**Online (composite adaptive law):**
- Augmented Kalman Filter on `a(w)` using prediction error.
- Tracking-error term added → guarantees closed-loop stability during rapid adaptation.
- Linear coefficient update: `Δa = Γ(Θ_e Ρ^T + e_e r^T)`, where `Θ_e` is tracking error, `e_e` prediction error, `r` regressor.

**Key insight:** Wind effects live in a low-dimensional subspace. DAIML finds the invariant basis; adaptation only touches a small set of linear mix coefficients online.

## Relevance to thesis

HIGH — direct comparison target (L1, nonlinear baseline, NF-Constant). The `Θ̃`-dimensionless prior concept maps to DAIML's wind-invariant basis. Their "basis + linear mix" = your "declared regressor + Θ̃". The Kalman filter composite law is the closest prior art to your augmented gradient law.

## Key differences from your work

- DAIML needs 12 min of flight data. You need zero.
- They adapt linear mix coefficients; you adapt dimensionless weight vectors.
- They have no delay plant; your transport-delay wrapper is a missing piece in their analysis.
- No trajectory density claim — they track one figure-8.

## What to grill on

1. Is the Kalman filter on `a(w)` guaranteed stable under time-varying wind if the basis is imperfect?
2. Does DAIML's "wind-invariant" property hold across payloads, not just wind?
3. Can their method bootstrap from a library of prior basis sets (your approach)?
4. What happens to adaptation when the DNN basis is overfit to the training wind regime?
