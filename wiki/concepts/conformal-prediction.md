---
title: Conformal Prediction
type: concept
tags: [uncertainty, machine-learning, stub]
created: 2026-07-09
updated: 2026-07-09
sources: [raw/papers/2026-07-09-motion-planning-in-dynamic-environments-a-survey-from-classi.md]
---

*Stub — expand when it next appears in a grabbed paper.*

A statistical wrapper that turns **any** predictor (neural net, physics model, anything) into one that outputs *calibrated* uncertainty sets: "the pedestrian will be inside this region with ≥95% probability", where 95% is a guarantee you chose, not a hope.

## How it works (intuition)

1. Hold out a calibration dataset the predictor never trained on.
2. Measure how wrong the predictor was on each calibration example (the "nonconformity score").
3. Take the 95th-percentile error, and inflate every future prediction by that margin.

The guarantee needs almost no assumptions about the predictor — only that calibration and future data are exchangeable (statistically alike).

## Why it shows up in robotics

Planning around moving obstacles needs to know *how wrong* trajectory predictions can be. Conformal prediction gives MPC planners principled safety margins instead of hand-tuned padding — the [motion-planning survey](../sources/motion-planning-dynamic-environments-survey.md) highlights MPC + conformal prediction for deadlock and uncertainty handling in dynamic scenes. See [[motion-planning-methods]].

## Possible thesis relevance (speculative)

A learned path-tracking policy (BC/Transformer) could carry a conformal bound on its tracking-error prediction — a statistically sound way to say "trust the NN this much" and fall back to PID/MRAC beyond the bound. Not planned; noted for the future.
