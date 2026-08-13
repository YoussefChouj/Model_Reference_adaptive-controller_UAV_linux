# GatedLinear: Adaptive Routing of Complementary Linear Bases for Time Series Forecasting

- source: arXiv
- url: https://arxiv.org/abs/2607.09537v1
- published: 2026-07-10
- digest-date: 2026-07-29
- channel: #control-laws
- topic: control-laws
- signal: grabbed (?? reaction on the Discord digest)

## Abstract

Time series forecasting requires models to capture diverse, often mutually exclusive, temporal dynamics, from smooth trend continuation to nonstationary drift and strict phase-aligned recurrence. While recent deep learning models have improved accuracy, they typically force these diverse patterns through a single computational backbone governed by fixed algorithmic inductive biases (e.g., self-attention or spectral filtering). This single-mechanism approach often struggles with the profound heterogeneity of real-world series, where different variables and forecast horizons necessitate fundamentally different predictive treatments. To address this, we propose GatedLinear: a lightweight framework that frames forecasting as the adaptive routing of complementary linear bases. GatedLinear leverages a pool of three specialized mechanisms: a global trend-seasonal basis for smooth projection, a difference-based incremental basis for nonstationary drift, and a phase-aligned recurrence basis for explicit cyclic reuse. To dynamically orchestrate these distinct behaviors, we introduce a Tri-Factorized Fusion Gate that disentangles routing decisions into channel-specific preferences, horizon-aware offsets, and phase-indexed biases derived from known future time marks. This design allows the model to perform highly granular, point-wise soft routing across different predictive regimes without stacking computationally heavy neural modules. Experiments on standard benchmarks show that our method achieves state-of-the-art or highly competitive accuracy against recent complex foundational models, while offering explicitly interpretable routing patterns and operating with a substantially smaller parameter footprint.

## My notes (typed on Discord)

- (no typed notes provided)

## Deep summary (grab pipeline)

## arxiv:2607.09537v1
**Relevance to thesis:** GENERAL - no clearly relevant content extracted.
Landing: https://arxiv.org/abs/2607.09537v1

---
*source:* https://arxiv.org/abs/2607.09537v1 ? *29 pp* ? *reviewer:* `deepseek/deepseek-v4-pro`
