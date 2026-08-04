---
title: "L1-NMPC — Performance, Precision, and Payloads: Adaptive Nonlinear MPC for Quadrotors"
type: literature
tags: [l1-adaptive-control, nmpc, quadrotor, disturbance-rejection, payload, thesis]
created: 2026-07-31
updated: 2026-07-31
sources: [raw/papers/2026-07-21-Performance-Precision-and-Payloads-Adaptive-Nonlinear-MPC-for-Quadrotors.md, raw/papers/2026-07-21-Performance-Precision-and-Payloads-Adaptive-Nonlinear-MPC-for-Quadrotors.pdf]
---

Raw page-cited briefing. Wiki-integrated beginner page: [sources/l1-nmpc-adaptive-nonlinear-mpc-quadrotors.md](../sources/l1-nmpc-adaptive-nonlinear-mpc-quadrotors.md).

**Paper:** Hanover, Foehn, Sun, Kaufmann, Scaramuzza (UZH Robotics & Perception Group), *IEEE RA-L* 2021. <https://arxiv.org/abs/2109.04210> (v2, 3 Dec 2021, 8 pp). DOI 10.1109/LRA.2021.3131690. Video: <https://youtu.be/8oB1rG5iYc4>

**Relevance to thesis:** HIGH — a direct, hardware-validated benchmark for what an adaptive inner loop buys you on a quadrotor, from the group whose results define the field's performance ceiling.

**Grabbed:** 📥 on the #control-laws Discord digest, 2026-07-21. Grabbed four times under four different titles (`L1-NMPC: An L1 Adaptive Controller Cascaded...`, `L1-NMPC Hybrid Adaptive Controller...`, `arxiv-2109.04210`, and the full title) — all the same arXiv ID.

## Contribution

Cascade an **L1 adaptive controller** underneath a **nonlinear MPC**, deriving the adaptation law at the *individual rotor thrust* level using the same nonlinear model the NMPC already carries. Result: online compensation of model mismatch and external disturbance with ~10 µs of extra compute, no gain retuning across wildly different scenarios.

## Method (p3–p4)

- **Plant model** (Eq. 1, p3): standard 6-DOF quadrotor, quaternion attitude, `J⁻¹[τ_B − ω_B × J ω_B]`, thrust allocation matrix `P` (Eq. 3), RK4 discretisation.
- **NMPC** (Eq. 5, p3): multiple-shooting quadratic OCP, SQP under a real-time iteration scheme, ACADO toolkit, 100 Hz onboard.
- **Uncertainty injection** (Eq. 6–7, p3): uncertainty `ς` enters linear acceleration, `ξ` enters angular acceleration.
  - **Unmatched** `σ_um = [ς_x, ς_y]` — lives in the null space of the controllability matrix (quadrotor can only push along body-z), *cannot* be directly cancelled.
  - **Matched** `σ_m = [ς_z, ξ_x, ξ_y, ξ_z]` — directly cancellable.
- **Reduced state** `z = [v_WB, ω_B]` (p4). `ż = f + g(u_L1 + σ_m) + g⊥ σ_um` (Eq. 8).
- **L1 state predictor / observer** (p4): `ż_hat = f + g(u_L1 + σ̂_m) + g⊥ σ̂_um + A_s z̃`, where `z̃ = ẑ − z` and `A_s` is Hurwitz.
- **Piecewise-constant adaptation law** (Eq. 11, p4): `[σ̂_m; σ̂_um] = −I₆ₓ₆ G⁻¹(iT_s) Φ⁻¹ µ(iT_s)`, with `Φ = A_s⁻¹(e^{A_s T_s} − I)`, `µ = e^{A_s T_s} z̃`, `G = [g, g⊥]`. No integration gain to tune — it solves for the uncertainty each sample.
- **Low-pass control law** (Eq. 12–13, p4): `u_L1 = −C(s) σ̂_m`, implemented discretely as
  `u_L1,k = u_L1,k−1 e^{−ω_co T_s} − σ̂_m,k (1 − e^{−ω_co T_s})`.
  **This filter is the whole design knob** — it decouples adaptation speed from robustness.

## Key results

- **Compute** (Table I, p4): L1-NMPC 0.82 ms/update vs plain NMPC 0.81 ms (so L1 itself ≈ **10 µs**), GP-MPC 4.13 ms, MPPI 23.13 ms. Intel i7-8750H.
- **Sim, no disturbance** (Fig. 3, p5): L1-NMPC beats INDI-NMPC and GP-MPC at all but the fastest circles even *without* an aero model — the adaptation absorbs unmodelled aerodynamics.
- **Sim, mass mismatch +660 g = +90 %** (Table II, p5): NMPC 0.434 m RMSE → L1-NMPC 0.007 m at 2.5 m/s (**98 % ↓**); ≥94 % ↓ at every speed up to 8 m/s. All controllers crash at 10 m/s (thrust-limited, not control-limited).
- **Sim, inertia doubled / arm length +25 %** (Table II, p5): L1-NMPC ≈ INDI-NMPC, within 5 mm across 10 cases. **NMPC+integrator is actively worse than baseline** (−65 % to −196 %) — integral action is the wrong tool for non-mass mismatch.
- **Real, nominal circles** (Table III, p6): L1-NMPC no-aero beats GP-MPC by ~70–80 %; with aero, 0.016–0.047 m RMSE at 2.5–10 m/s.
- **Real, 450 g unknown payload (+60 % mass)** (p6, Fig. 4–5): L1-NMPC <1 cm steady-state Z error vs **>35 cm** for non-adaptive NMPC. Adaptation is visible in the first second of thrust commands (Fig. 5).
- **Real, fan disturbance** (p6, Fig. 4 bottom): rapid rejection, degraded-but-acceptable tracking; baseline degrades sharply.
- **Real, 100 g slung payload @ 11.9 m/s** (p6): 44 % better than non-adaptive NMPC *carrying nothing*; 34 % better than INDI-NMPC. L1 with and without payload nearly identical → the adaptation genuinely drives the true plant onto the reference model.
- **Real, 19.4 m/s / >4 g racing** (p6–7, Fig. 6): 49 % better than baseline SRT-NMPC, but **INDI-NMPC wins by <5 cm RMSE**.

## Honest limits the authors state (p7)

- If the model is well known and you want max racing performance: **use INDI-NMPC, not this**.
- L1-NMPC wins when uncertainty is large, payloads vary, and you cannot update the model.
- INDI and plain NMPC have no integral action on linear acceleration → permanent Z steady-state error under payload.
- MPPI was dropped: an order of magnitude worse, 23 ms/update, oscillatory body rates (curse of dimensionality in 4D).

## Relevant to YOUR work (with pages)

- **The C(s) filter decoupling** (Eq. 12–13, p4) is the transferable idea: estimate the uncertainty as fast as the sample rate, then let a first-order low-pass decide how much reaches the actuator. Your MRAC couples both into `gamma[]`. See [[l1-adaptive-control]].
- **Matched vs unmatched split** (p3–p4) formalises why a quadrotor can never directly cancel X/Y acceleration disturbance — it must tilt. See [[matched-unmatched-uncertainty]].
- **Piecewise-constant adaptation** (Eq. 11, p4) replaces the integrating `Θ̇ = Γ Φ e` update with a per-sample algebraic solve — no adaptation-rate gain, no windup.
- **Table II's integrator row** (p5) is a warning: adding integral action to fight non-mass mismatch made tracking up to 196 % worse.
- **10 µs / 0.82 ms budget** (Table I, p4) — the L1 augmentation itself is trivially affordable on an STM32F4; the NMPC is not.
- **Both papers' reference-model philosophy**: L1 uses a *nonlinear* reference model (p3, citing [40]) precisely because linear reference models "can lead to unrealistic desired dynamics which cannot be achieved by the real system" (p2). Your firmware uses a linear second-order reference model.

## How to apply / next step

- Bench the L1 law against your MRAC in `sim/` under the same mass / inertia / arm-length mismatches Table II uses.
- Consider adding a `C(s)`-style output filter to the existing MRAC `u_ad` path as a cheap robustness knob independent of `gamma[]`.
- Cite Table II and the 44 % slung-payload result as the performance envelope your thesis metrics are measured against.

---
*source:* <https://arxiv.org/abs/2109.04210> · *8 pp* · *PDF on disk* · *briefing: Claude + full-text read*
