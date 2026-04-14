---
title: Tuning Workflow
type: concept
tags: [tuning, pid, mrac, dashboard, workflow]
created: 2026-04-14
updated: 2026-04-14
sources: [TASK/send_data.c, ground_station/gui/dashboard.py, API/mrac.h]
---

This page provides a step-by-step guide for tuning PID and MRAC parameters using the ground station dashboard and VOFA+ visualization. Follow this workflow to avoid common tuning mistakes.

## Prerequisites

1. Ground station connected and telemetry flowing (see [[Agent & Developer Quick-Start Guide]])
2. VOFA+ running with correct workspace presets for Frame A and Frame B
3. Drone armed in SDK mode with virtual RC authority (see [[SDK Arming State Machine]])

## PID Tuning

### Step 1: Identify the Loop

Refer to [[PID Controller]] for the loop hierarchy. Typical tuning order (inner loops first):

1. **Rate loops** (`gyroxPID`, `gyroyPID`, `gyrozPID`) — fastest response, tune first
2. **Angle loops** (`pitchPID`, `rollPID`, `yawPID`) — outer cascade, tune after rate loops are stable
3. **Altitude loops** (`Z_ratePID`, `Z_posPID`) — vertical axis
4. **Position loops** (`locxsPID/locysPID`, `locxPID/locyPID`) — slowest, tune last

### Step 2: Send Gain Updates

Use the dashboard "PID Tuning" tab, or send raw commands:

```
CMD 0x01, index = loop_offset + param, value = gain_value
```

The index encodes both which PID loop and which parameter (Kp/Ki/Kd/limits). See `Process_GroundStation_Command` CMD `0x01` branch (`TASK/send_data.c:481-501`) for the exact index-to-field mapping.

Dashboard sliders generate these commands automatically with debounce (`DebouncedSender` in `ground_station/gui/dashboard.py`).

### Step 3: Observe in VOFA+

Frame B telemetry exposes all 12 PID loops with three channels each (`TASK/send_data.c:380-428`):
- `pid.<loop>.FB` — feedback (actual)
- `pid.<loop>.Des` — desired (setpoint)
- `pid.<loop>.U` — controller output

In VOFA+ Stream B workspace:
- Plot `Des` vs `FB` for tracking quality
- Plot `U` to watch for saturation (hitting ±UMax)
- Watch for oscillation (sign of over-gain) or sluggish response (under-gain)

### Step 4: Iterate

Standard tuning heuristic:
1. Start with Kp only (Ki=0, Kd=0), increase until oscillation begins
2. Back off Kp by ~30%
3. Add Ki slowly to eliminate steady-state error
4. Add Kd to dampen overshoot if needed
5. Adjust limits (`UMax`, `UiMax`, `SumEMax`) if output is saturating

### Important: Gains Are Volatile

All gain updates are RAM-only. Power cycling restores compile-time defaults. See [[Flash Memory]] for persistence status. If you find good gains, record them manually and update source code defaults.

## MRAC Tuning

### Understanding the Adaptive Law

MRAC runs after PID and adds `u_ad` correction to each axis. See [[MRAC Control Law]] for theory. Key tunable parameters per axis:

| Parameter | CMD | Purpose |
|-----------|-----|---------|
| `gamma[i]` | `0x02` | Adaptation rate per basis function |
| `What_limit[i]` | `0x05` | Weight saturation bound |
| `What_tol[i]` | `0x08` | Tolerance shell width for projection |
| `u_max` | `0x03 idx 5` | Output clamp for adaptive term |
| `mrac_to_mixer` | `0x03 idx 0-3` | Scaling from u_ad to mixer units |

### MRAC Tuning Steps

1. **Start with MRAC in shadow mode**: Ensure `ENABLE_MRAC_OUTPUT_INJECTION = 0` (`API/mrac.h`). This lets you observe adaptive weight evolution without affecting flight.

2. **Enable injection**: Set `ENABLE_MRAC_OUTPUT_INJECTION = 1` (requires recompile), or use future runtime toggle if implemented.

3. **Monitor in VOFA+ Frame A**: 
   - `mrac.pitch.e` — tracking error
   - `mrac.pitch.u_ad` — adaptive correction magnitude
   - Same for roll, yaw, z axes

4. **Monitor in VOFA+ Frame B**:
   - `mrac.*.theta_i` — individual weight evolution
   - `mrac.*.u_nom` — nominal PID output being augmented
   - `mrac.*.xm` — reference model state

5. **Tune gamma**: Higher gamma = faster adaptation but more noise sensitivity. Start low (0.01-0.1), increase until tracking improves without weight chattering.

6. **Tune limits**: `What_limit` prevents weight divergence. Set based on expected disturbance magnitude. Too tight = adaptation stops early; too loose = risk of large transients.

7. **Tune mrac_to_mixer**: This scales the adaptive output into mixer units. Start conservative (0.5x of PID authority), increase as confidence grows.

### Analysis Scripts

After a tuning flight:

1. Stop recording in dashboard (Flight Log tab)
2. Run quick analysis: `FlightLogger.analyze(path)` for summary stats
3. Run deep analysis: `python ground_station/scripts/deep_analysis.py <log_file>` for frequency-domain analysis, weight convergence plots, and phase relationships
4. Compare across flights: `python ground_station/scripts/experiment_db.py --dir ground_station/results/` for cross-experiment ranking

See [[Ground Station Tooling]] for script details.

## Safety During Tuning

- Always have the STOP button visible in dashboard sidebar
- Keep `gs_throttle_max_pct` conservative (e.g., 0.6) until gains are validated
- Monitor `status.arm` and `status.flymode` telemetry to confirm vehicle state
- If oscillation appears, reduce gains immediately — don't wait for it to settle
- MRAC NaN guards (`TASK/StabilizerTask.c:303-306`) will zero bad adaptive outputs, but the transient may still cause attitude disturbance

## See Also

- [[PID Controller]] — algorithm details
- [[MRAC Control Law]] — adaptive law structure
- [[Ground-Station Binary Protocol]] — CMD ID reference
- [[Dashboard]] — UI layout and command dispatch
- [[Ground Station Tooling]] — analysis scripts
