# Trajectory tracking baseline + X/Y drift diagnosis (2026-06-14)

Source: 8 `flight_sinusoid_*.csv` logs in `ground_station/logs/`. Per-axis position
tracking computed from `pid.loc{x,y}.Des − .FB` (both in **cm**, see
[protocol contract]) over the window where `path.active_path_mode ≥ 1`.
Attitude RMSE (pitch/roll/yaw/z, in deg) comes from `deep_analysis.py` → `results/*.json`.

## Position tracking baseline (the trajectory metric)

| Run (ts) | Driven axis | Pos RMSE | Peak err | Amplitude vs commanded |
| --- | --- | --- | --- | --- |
| 1781275324 | locx | 13.0 cm | 18.5 cm | +50% (overshoot) |
| 1781275730 | locx | 42.7 cm | 68.1 cm | −9% (undershoot/lag) |
| 1781276093 | locx | 46.2 cm | 80.1 cm | −18% |
| 1781276599 | locx | 46.2 cm | 72.4 cm | −35% |
| 1781444507 | locx | 59.8 cm | 111.2 cm | −17% |
| **mean (driven locx)** | | **41.6 cm** | | |

Runs 287/304/311 drove neither X nor Y >2 cm → these were **Z-axis** sinusoids; their
12–17 cm "error" on the *static* X/Y axes is pure position hold wander (see drift below).
The overshoot-% metric is only meaningful on a driven axis (static axis amplitude ≈ 0
makes the ratio explode — ignore those numbers).

### Read of the baseline
- Horizontal trajectory tracking is **poor and degrading**: locx RMSE grows 13 → 60 cm
  across the session; later runs show **amplitude undershoot + phase lag** (negative
  "overshoot"), the signature of a position loop that can't keep up with the reference.
- This is exactly the case for the **waypoint-density** knob just added: a denser/slower
  reference should cut this lag-driven error; a sparse reference will expose it. The new
  Δs control lets you sweep this directly.
- Attitude (inner MRAC) RMSE is small (pitch ~2.4°, roll ~1.4°, z ~0.07 m) → the inner
  loop is healthy; the error budget is dominated by the **position layer**, not attitude.

## X/Y drift diagnosis

**Signature:** on axes the path did NOT command, position FB still wanders 12–18 cm RMSE
from a fixed Des within a single flight — consistent with the known optical-flow drift
(`ano_of.earth_x/y`, integrated from OF velocity).

**Root cause (why no controller "fixes" it):** the drift is a **measurement** error, not a
plant disturbance. `loc{x,y}.FB` is OF velocity integrated to position; a small constant
velocity bias `b` integrates into unbounded position error `b·t`. The position controller
faithfully drives the drone to hold the *corrupted* measurement, so it cannot reject an
error it cannot observe. Integral action makes it worse (chases the drift).

## Mitigation proposal (ranked — NOT yet implemented)

1. **(Recommended) OF velocity-bias calibration.** During the initial armed hover (known
   stationary), average `loc{x,y}s.FB` (OF velocity) for ~2 s, store as bias `b_x,b_y`,
   subtract from the OF velocity before integration. Kills the dominant linear drift term
   at the source. Cheap, firmware-local (`Ano_OF.c` / SINS integration), no new sensor.
2. **Periodic / event origin re-zero.** CMD `0x10` already re-zeros the OF origin; expose a
   "re-zero before run" toggle in the path panel so each trajectory starts from a clean
   origin. Bounds accumulated drift per run; does not fix in-run drift.
3. **Absolute-reference fusion (future).** Fuse OF with GPS/SLAM/UWB for an un-drifting
   position. Currently blocked — `path_executor` reports SLAM/GPS "not available yet".

**Battery → overshoot:** un-analysable from these logs (no Vbat pre-v3). Now instrumented
as `status.vbat` (proto v3). After reflash + a few runs, correlate `status.vbat` against
locx peak error / undershoot; if overshoot tracks Vbat sag, re-enable the disabled Vbat→
throttle feedforward at `StabilizerTask.c:310` as the test mitigation.

[protocol contract]: ../CONTEXT.md
