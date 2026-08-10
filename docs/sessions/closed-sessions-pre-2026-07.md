# Closed sessions: ADR-0011, Sim rebuild, Sysid (<= 2026-07-23)

> Moved verbatim out of CLAUDE.md on 2026-08-09 to cut per-turn
> context churn. CLAUDE.md keeps a compact index pointing here.

### ADR-0011 Session (2026-07-23)

| # | Task | Status |
|---|------|--------|
| 1 | Build fix: `USER/JX_FLY.uvprojx` — add `ekf.c` + `calib.c` to API file group | ✅ done → commit `3e1c828` |
| 2 | Build fix: `TASK/StabilizerTask.c` — remove `static` from `s_cal_trim`/`s_cal_hot` (extern needed by `send_data.c`) | ✅ done → commit `3e1c828` |
| 3 | Build green: uVision rebuild with 0 errors | ✅ done (69 warnings, all pre-existing) |
| 4 | v14 free-flight validation | pending → produce flight log with `of.lin_acc_x_mg` for EKF replay tool |
| 5 | EKF offline replay (`sim/tools/replay_ekf_flight.py`) against v14 flight log | pending |
| 6 | ADR-0011 build-fix log + ADR status update | ✅ done → docs/adr/ADR-0011-auto-imu-calibration.md |


### Sim Rebuild Session (closed) — 2026-06-23

| # | Task | Status |
|---|------|--------|
| 1 | `/grill-with-docs` — package design, plant fidelity, regressor alignment, 6-DOF seam | ✅ done → ADR-0006 + CONTEXT.md |
| 2 | `/tdd` slice 1 — `plant.py` | ✅ done → 6 tests green (yaw integrator, roll ramp-slope=K, ZOH+N=3 delay, Plant seam, Gazebo stub) |
| 3 | `/tdd` slice 2 — `reference_model.py` | ✅ done → 7 tests green (firmware-parity Euler recurrence, scalar P=1/2wn, passthrough/1st/2nd, bumpless reset, for_axis factory) |
| 4 | `/tdd` slice 3 — `adaptive_law.py` + `regressor.py` | ✅ done → 17 tests green (regressor golden-vector parity mrac.c:65-91 + cross-coupling; adaptive law gradient/projection/freeze/deadzone/tanh-sat/perf-recovery LPF, lower-bound=0 firmware quirk, for_axis gains) |
| 5 | `/tdd` slice 4 — closed-loop wiring (`baseline.py` + `scenarios.py` + `run.py`) | ✅ done → 14 tests green (RatePID parity pid.c ComputePID incl EMin conditional-integ/clamps/u_nom÷mrac_to_mixer; closed-loop runner mrac.c:424-485 unit chain rad/s↔deg/s↔Nm; per-run artifacts ADR-0006 D7). 44 tests total. |
| 6 | `sim/README.md` + session-end distill | ✅ done → README (two scenarios, unit chain, findings); ADR-0006 D7 artifacts gitignored |


### Sysid Session (closed) — 2026-06-16

Audited firmware (MRAC/leakage/gyro_filter/bypass/FSM clean); fixed Z-axis no-op + OF self-reset; wrote `sysid_analysis.py`; added live FSM-state telemetry (0x03 frame 90→91 B, proto 3→4). See `docs/progress.md` / git history. Deferred: uVision build, SysID safety gates, full Z wiring.
