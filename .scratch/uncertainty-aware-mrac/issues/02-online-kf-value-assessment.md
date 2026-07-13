# Online KF in firmware — value assessment

Type: research
Status: resolved (2026-07-10, decided by user)

## Question

Is an *online* Kalman filter in the firmware worth thesis time, or does offline smoothing capture most of the value?

- Make the three-way distinction precise for this codebase: (a) offline smoothing of logged (Mahony-filtered) data, (b) offline smoothing of raw logged IMU, (c) a true online estimator feeding the controller in real time.
- What would an online (error-state) KF buy that fixed-gain Mahony + SINS don't: adaptive trust during maneuvers, principled OF/baro fusion (known OF XY drift ~50 cm), covariance as a live signal the adaptive layer could consume (feeds ticket 03/04)?
- Costs: CPU at 1 kHz on STM32F4, SO(3) handling (ESKF vs UKF vs quaternion EKF), risk, and the MISSION.md fence (Mahony stays — anything online must be additive and flag-gated).
- Deliverable: markdown asset with a recommendation: pursue in this effort / park as fog / rule out of scope.

## Resolution (2026-07-10)

**Decided by the user, superseding the AFK research pass: pursue the online KF.** Direction:

- Build it **step by step, interactively** (`/grill-with-docs`-style), so the user fully understands each stage of the filter before it exists in code — this is a learning-driven build, not a delegated one. See ticket [08](08-online-kf-stepwise-build.md).
- **Bootstrap trust from the hand-tuned Mahony filter**: don't discard the tuning effort — design Q/R so the KF's *converged steady-state gain matches Mahony's effective fixed gain* (Mahony ≈ steady-state KF on SO(3)). Note for ticket 08: Mahony's Kp/Ki are not KF parameters directly; the equivalence is via the steady-state gain, so "same parameters" means *matched behavior at convergence*, with Q/R derived to produce it. That gives a safe starting point whose ON-vs-OFF diff is ~zero, then the time-varying gain earns its keep during transients.
- Standing rules apply: additive, flag-gated, default OFF = today's Mahony behaviour (MISSION.md fence intact — Mahony keeps flying the drone).
- Ticket 08 carries the remaining open sub-questions from this assessment (variant choice ESKF/EKF/UKF, CPU budget at 1 kHz, raw-vs-filtered measurement inputs, whether covariance is exported as a live signal for the adaptive layer).
