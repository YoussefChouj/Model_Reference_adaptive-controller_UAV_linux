---
title: "Concurrent Learning — History Stack for Parameter Convergence without PE"
type: literature
tags: [concurrent-learning, history-stack, parameter-convergence, persistency-of-excitation, adaptive-control, mrac, integral-correction, thesis]
created: 2026-08-12
sources: [Chowdhary & Johnson, CDC 2010; Chowdhary PhD thesis arXiv:1012.0806]
---

Raw ar5iv source: raw/papers/2026-08-12-Chowdhary-2010-ConcurrentLearning-CDC-arxiv1012.0806.md

## Paper Identity

Chowdhary & Johnson. CDC 2010 + Chowdhary PhD thesis (Georgia Tech, arXiv:1012.0806). 408 citations. The foundational concurrent learning paper.

## Core Claim

Using both instantaneous and recorded data concurrently for adaptation, a verifiable *linear independence condition on recorded data* is sufficient to guarantee exponential tracking and parameter error convergence — without requiring persistent excitation (PE) of the reference input.

## Method

**Standard MRAC adaptive law** (only instantaneous data):
- `ΔW = Γ(eΘ)` — needs PE for `W → W*`.

**Concurrent learning adaptive law** (instantaneous + recorded):
- `ΔW = Γ(eΘ) + Σ_i Γ_c(e_i Θ_i)` — history stack `{(e_i, Θ_i)}` updated online.
- **Rank condition:** The recorded data matrix `Θ^T Θ` must be full rank (all basis directions excited in the stack).
- If rank condition is met and the system is bounded, exponential convergence of `e → 0` and `W → W*` follows — even without PE.

**Implementation:** Fixed-size stack, FIFO replacement when full, rank-monitored online.

## Relevance to thesis

DIRECT — your spec 12 (integral CL with history stack + rank condition) is the direct descendant of this work. The dimensionless twist (dimensionless error `ẽ` and dimensionless regressor `Θ̃`) is yours — Chowdhary does not dimensionless.

## Key differences from your work

- No dimensionless framing — convergence is in physical units.
- No delay plant — assumes instantaneous plant.
- No σ-modification or deadzone — pure CL convergence claim.
- No prior transfer — they assume `W(0) = 0`; you assume `W(0) = Θ_prior`.

## What to grill on

1. Does the rank condition on `Θ^T Θ` translate directly to your dimensionless regressor? Is rank preserved under the `1/K` scaling?
2. If the delay plant shifts the effective regressor `Θ` in time, does the rank condition still hold?
3. How does σ-modification interact with CL convergence guarantees? Does σ-mod kill the exponential convergence?
4. Can a *dimensionless* rank condition be stated that is airframe-invariant?
