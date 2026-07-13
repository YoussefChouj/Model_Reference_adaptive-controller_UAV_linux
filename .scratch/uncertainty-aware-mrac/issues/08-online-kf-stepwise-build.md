# Online KF — step-by-step interactive design & build (Mahony-matched)

Type: grilling (HITL, multi-session)
Status: open
Assignee: Youssef (claimed 2026-07-10 — stage 1 in progress)

## Question

Design — and then build, stage by stage — the online Kalman filter for the firmware, with the user understanding each step before it is coded (`/grill-with-docs` interactive style; the user is a beginner and this is explicitly a learning-driven build). Spans several sessions; each session closes one stage.

Stages (each ends with the user able to explain the step back, then the step gets implemented — sim first, firmware behind a flag):

1. **Ground the equivalence**: derive how Mahony's hand-tuned Kp/Ki correspond to a steady-state Kalman gain, and what Q/R must be for the KF's converged gain to match it. This is the "reuse the hand tuning" requirement made precise — matched *behavior*, not copied parameters.
2. **Choose the variant**: ESKF vs quaternion EKF vs UKF for attitude on SO(3); CPU budget at 1 kHz on STM32F4; what PX4/ArduPilot do and why.
3. **State/measurement design**: what states, which raw signals feed it (gyro/accel; OF/baro later?), and where it taps in relative to `imu_update.c` — additive, flag-gated, default OFF.
4. **Predict/update in sim**: implement in `sim/` or a standalone Python harness against logged flight data; verify Mahony-matched startup (ON-vs-OFF ≈ 0 at convergence) before any transient-advantage claims.
5. **Firmware port plan**: injection points, fixed vs float costs, telemetry for covariance/gain so the adaptive layer (tickets 03/04) can later consume them.

Constraints: MISSION.md fence — Mahony keeps flying the drone; the KF is additive. Every firmware change behind a flag, default OFF.

Resolved when the filter runs Mahony-matched in sim against real logs and the firmware port plan is written; the actual firmware coding proceeds via /tdd.
