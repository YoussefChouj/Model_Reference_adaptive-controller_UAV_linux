# GatedLinear: Adaptive Routing of Complementary Linear Bases for Time Series Forecasting

- source: arXiv
- url: https://arxiv.org/abs/2607.09537v1
- published: 2026-07-10
- digest-date: 2026-07-30
- channel: #literature
- topic: literature
- signal: grabbed (?? reaction on the Discord digest)

## Abstract

Time series forecasting requires models to capture diverse, often mutually exclusive, temporal dynamics, from smooth trend continuation to nonstationary drift and strict phase-aligned recurrence. While recent deep learning models have improved accuracy, they typically force these diverse patterns through a single computational backbone governed by fixed algorithmic inductive biases (e.g., self-attention or spectral filtering). This single-mechanism approach often struggles with the profound heterogeneity of real-world series, where different variables and forecast horizons necessitate fundamentally different predictive treatments. To address this, we propose GatedLinear: a lightweight framework that frames forecasting as the adaptive routing of complementary linear bases. GatedLinear leverages a pool of three specialized mechanisms: a global trend-seasonal basis for smooth projection, a difference-based incremental basis for nonstationary drift, and a phase-aligned recurrence basis for explicit cyclic reuse. To dynamically orchestrate these distinct behaviors, we introduce a Tri-Factorized Fusion Gate that disentangles routing decisions into channel-specific preferences, horizon-aware offsets, and phase-indexed biases derived from known future time marks. This design allows the model to perform highly granular, point-wise soft routing across different predictive regimes without stacking computationally heavy neural modules. Experiments on standard benchmarks show that our method achieves state-of-the-art or highly competitive accuracy against recent complex foundational models, while offering explicitly interpretable routing patterns and operating with a substantially smaller parameter footprint.

## My notes (typed on Discord)

- (no typed notes provided)

## Deep summary (grab pipeline)

## GatedLinear: Adaptive Linear Basis Fusion for Efficient Time Series Forecasting
**Relevance to thesis:** HIGH – Introduces an efficient, interpretable linear basis fusion method with adaptive routing, directly applicable to resource-constrained forecasting tasks.
**Contribution:** Proposes GatedLinear, a lightweight forecasting model that fuses three specialized linear bases (trend-seasonal, difference-based incremental, phase-aligned recurrence) via a tri-factorized fusion gate, achieving state-of-the-art accuracy with minimal parameters and linear complexity.
**Method:** Combines three linear bases: global trend-seasonal projection, difference-based incremental evolution, and phase-aligned recurrence. A tri-factorized gate factorizes routing logits into channel-specific preferences, horizon-dependent offsets, and phase-indexed biases, enabling point-wise soft routing across predictive regimes without heavy neural modules.
**Key results:**
- Achieves best or second-best MSE/MAE on 11/16 dataset-level metrics across 8 benchmarks (ETT, Electricity, Traffic, Weather, Exchange) with lookback L=336 (p7, p19).
- Parameter complexity O(LH + C(H+P)) and computational complexity O(BCLH), avoiding quadratic self-attention overhead (p6).
- Ablation: removing any single branch degrades performance; removing phase-indexed logits from the gate increases average error by 2.11% (p7).
- Learned gate weights assign higher weight to difference branch at short horizons and to phase-aligned branch at long horizons, matching intuitive behavior (p8).
- Spearman correlations link difference branch preference to mean/scale shift traits and phase branch preference to seasonality strength and phase consistency (p9).
- On Electricity (L=336, H=96), GatedLinear achieves low error, short training time, and small GPU memory footprint (p9).
**Relevant to YOUR work (with pages):**
- The tri-factorized gate provides fine-grained, interpretable routing across forecasting mechanisms, which can be adapted to other mixture-of-experts or adaptive architectures (p3, p5, p8).
- The difference-based incremental basis theoretically eliminates level-shift bias by predicting stationary increments, offering a principled way to handle non-stationary data without complex normalization (p13).
- The phase-aligned recurrence basis with phase-indexed gate logits enables explicit periodic pattern reuse, useful for datasets with strong seasonality or phase-consistent cycles (p5, p12).
- The channel-independent design shares temporal branches across variates, drastically reducing parameters but limiting cross-variable modeling; this trade-off can inform lightweight multivariate extensions (p6, p12).
- Trait analysis (shift scores, seasonality strength, spectral entropy) links data characteristics to branch preferences, providing a diagnostic tool for model selection or dynamic architecture design (p9, p15-16).
- The convex combination of linear bases via a learned gate (Eq. gate logit) ensures deterministic O(BCLH) execution, making it suitable for real-time or edge deployment (p4, p6).
**How to apply / next step:**
- Integrate the tri-factorized gating mechanism into existing linear forecasters (e.g., DLinear, NLinear) to improve adaptive routing without adding significant parameters.
- Adopt the difference-based incremental basis for datasets with level shifts to avoid bias, and combine with phase-aligned recurrence for seasonal patterns; the gate can be trained end-to-end.
- Extend the channel-independent design with a lightweight cross-variable attention or graph module to capture inter-series dependencies while maintaining the efficiency gains of the linear bases.

---
*source:* https://arxiv.org/abs/2607.09537v1 · *29 pp* · *reviewer:* `deepseek/deepseek-v4-pro`
