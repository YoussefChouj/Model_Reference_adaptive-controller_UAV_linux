# Estimation thread opened: Kalman filter, self-sourced; firmware has no KF anywhere

Session 2026-07-10. The user self-sourced a Kalman filter video ("This One Equation Powers GPS,
Rockets, and Robots", youtu.be/lIYYJMHAwMU) and brought back written notes + screenshots — the first
lesson driven by material *they* found, exactly the "pull from any source" behaviour the mission
wants to grow. Notes were substantially correct: 1-D Gaussian fusion, K as trust dial, K→0/K→1
limits, (1−K) uncertainty shrink, predict/update structure, EKF/UKF/PF extensions.

**One misconception corrected before it stuck:** their notes assigned covariance **Q** to the
measurement noise `v` (wrote "covariance Q" for both equations). Fixed in Lesson 4: process noise
w ~ N(0,Q), measurement noise v ~ N(0,R); tuning a KF = choosing the Q:R ratio, and swapping them
inverts every tuning intuition. Quiz Q2 targets this directly — check retention next session.

**Key codebase fact established (verified via ccc + wiki, not assumed):** there is *no Kalman
filter in the firmware*. Attitude = Mahony fixed-gain complementary filter (`imu_update.c`, 1 kHz,
constant Kp/Ki — classically a steady-state/converged-K Kalman filter, stable on SO(3)); position =
SINS fixed-gain observer corrections (`SINS.h` `in_est/in_obs/fix_ki`). Framing taught: the whole
estimator stack is predict/correct with frozen gains; the KF is the machine that computes that gain
per-tick from P/Q/R, and the trade-off is covariance CPU + adaptivity of trust (e.g. accel corrupted
by maneuvers) vs simplicity.

**Scope note:** estimator rewrite stays out of mission scope; this was taught as landscape
knowledge for the thesis (papers assuming "an EKF provides state"; digital-twin/Gazebo estimation).
A natural future prototype if the user asks: EKF for the known optical-flow XY drift issue, in
`sim/` only. Extends [[0001-anti-windup-already-present]]'s pattern of "understand what exists
before adding".

Assets: quiz widget extracted to `assets/quiz.js` (lessons 1–3 still carry inline copies — don't
touch them); new reusable `assets/gaussian-fusion.js` interactive. New reference:
`reference/kalman-filter.html` (symbols glossary incl. Q-vs-R trap, 1-D fusion, full recursion,
firmware mapping).
