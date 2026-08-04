---
title: Matched vs Unmatched Uncertainty
type: concept
tags: [adaptive-control, underactuation, quadrotor, theory]
created: 2026-07-31
updated: 2026-07-31
sources: [raw/papers/2026-07-21-Performance-Precision-and-Payloads-Adaptive-Nonlinear-MPC-for-Quadrotors.pdf]
---

A disturbance is **matched** if it enters the plant through the same channel as your control input, and **unmatched** if it does not. Formally, for `ẋ = f(x) + g(x)(u + σ_m) + g⊥(x)σ_um`, anything you can write inside the `(u + ·)` bracket is matched — you can cancel it exactly by subtracting it from `u`. Anything in `g⊥` lives in the null space of the input matrix and no choice of `u` touches it directly.

## Why this is unavoidable on a quadrotor

A quadrotor has 4 inputs (rotor thrusts) and 6 degrees of freedom. It produces linear force **only along body-z**. So, decomposing the acceleration uncertainty `ς = [ς_x, ς_y, ς_z]`:

- `ς_z` (body-z acceleration error — e.g. an unknown payload, thrust-coefficient drift, battery sag) is **matched**. Push harder on all four motors.
- `ς_x, ς_y` (body-x/y acceleration error — e.g. a crosswind, a slung load swinging) are **unmatched**. There is no rotor command that pushes sideways.
- All three angular-acceleration uncertainties `ξ = [ξ_x, ξ_y, ξ_z]` are **matched** — that is what the four thrusts differentially produce.

So on a quadrotor, matched = `[ς_z, ξ_x, ξ_y, ξ_z]` (4 components, matching the 4 inputs) and unmatched = `[ς_x, ς_y]`.

## What you do about the unmatched part

You do not cancel it in the inner loop — you **tilt**. Lateral force comes from rotating the thrust vector, which means the unmatched disturbance must be handled by the *outer* (position/attitude-reference) loop commanding a lean angle. This is precisely why the cascade exists.

Consequence for this project: the [[mrac-control-law]] runs on the **rate loop**, so by construction it can only ever address matched uncertainty. Optical-flow XY drift and lateral wind are outer-loop problems. No amount of inner-loop adaptation gain will fix them — a useful thing to be able to say cleanly in the thesis.

An L1 observer still *estimates* `σ̂_um` (it needs it for the state predictor to be accurate) but does not feed it to the control law.

## See also

- [[l1-adaptive-control]]
- [[l1-nmpc-adaptive-nonlinear-mpc-quadrotors]]
- [[mrac-control-law]]
- [[coordinate-conventions]]
