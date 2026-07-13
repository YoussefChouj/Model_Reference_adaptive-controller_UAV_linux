# Uncertainty-aware adaptation mechanisms — survey with stability arguments

Type: research + grilling (user wants the literature walked through *with* them, grilling-style, before sim/firmware)
Status: open
Blocked by: 08

## Question

Which uncertainty-aware adaptation mechanisms fit the firmware's existing MRAC structure (gradient law + projection + `What` limits + `e_deadzone`, `mrac.c`), and what citable stability argument does each carry?

Candidates to cover, minimum:
1. **Matrix adaptation gain Γ** (per-weight fixed rates) — standard Lyapunov proof holds for any constant symmetric positive-definite Γ; the free-proof baseline.
2. **RLS / KF-based adaptation** (P as time-varying per-parameter learning rate) — forgetting factor, covariance bounds, persistent-excitation wind-up; proofs in Ioannou & Sun ch. 4.
3. **Composite / Kalman-modified MRAC** (tracking-error + prediction-error driven) — recent literature; what it adds over 1–2.
4. Interaction with the existing robustness modifications (projection, deadzone, leakage): which combinations keep their proofs?

Deliverable: markdown asset — comparison table (mechanism, stability argument + citation, firmware fit, CPU cost, risk), feeding the mechanism-choice grilling. Use /free-reason for derivation checks.
