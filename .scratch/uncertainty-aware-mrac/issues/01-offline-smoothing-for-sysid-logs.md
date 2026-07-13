# Offline smoothing for SysID logs

Type: research
Status: open

## Question

What is the right offline data-quality upgrade for the SysID pipeline (`sysid_analysis.py`), and what does it require from logging?

- RTS (Kalman) smoother vs zero-phase filtering (filtfilt) vs current approach — which, on which signals, with what expected gain in model-fit quality?
- Critical sub-question: what do the flight logs actually capture today — raw gyro/accel, or only Mahony-filtered attitude and SINS outputs? Smoothing on top of estimator outputs cannot recover information the estimator destroyed (its lag/bias is baked in); if raw IMU isn't logged, does the telemetry protocol need a flag-gated raw-log frame first?
- Deliverable: a short markdown asset recommending the method + any logging change, with citations (Labbe ch. 13 for RTS).
