# Flight Analysis Report: exp_flight_twc_1781526906

**Date:** 2026-06-15T13:28:34.487340Z | **Duration:** 6.8s | **Samples:** 3060 | **Config:** PAYLOAD_LIGHT

---

## What Happened

- Planar XY tracking RMSE was **26.2 cm** (peak 32.4 cm).
- Worst-tracked position axis was **Y** (RMSE 21.62 cm).
- Yaw held **-0.2°** off command (drift +0.74°/s over the run) — expected heading-hold signature of bias/asymmetry.
- **Never settled** within 5 cm of target (final error 24.7 cm).
- ⚠ **1 CRITICAL** MRAC alert(s) — run is INELIGIBLE as a champion until resolved.
- MRAC was most active on **z** (ρ_mean 0.71).

## Path Tracking

![XY Trajectory](xy_trajectory.png)

| Metric | Value |
|--------|-------|
| Planar XY RMSE (cm) | 26.23 |
| Planar peak (cm) | 32.44 |
| Cross-track mean / p95 / max (cm) | - / - / - |
| Along-track lag (ms) | - |
| Rank score (planar_rmse_cm) | 26.23 |
| TWC settling time (s) | - |
| TWC final error (cm) | 24.74 |

| Axis | RMSE | MAE | Peak |
|------|------|-----|------|
| X | 14.87 | 12.72 | 21.95 |
| Y | 21.62 | 21.38 | 24.68 |
| Z | 0.03 | 0.03 | 0.08 |

![X](position_locx.png)
![Y](position_locy.png)
![Z](position_z_pos.png)

### Yaw heading-hold drift

| Cmd (°) | Final offset (°) | Mean offset (°) | Drift (°/s) | Total drift (°) | P2P (°) |
|---------|------------------|-----------------|-------------|-----------------|---------|
| 30.00 | -0.22 | -0.81 | 0.74 | 5.00 | 28.01 |

## MRAC Scoreboard (attitude / rate loops)

| Axis  | RMSE | RMSE_ss | RMSE_tr | ρ_mean | ρ_p95 | Phase | ‖Θ‖ | ⚠ | 🔴 |
|-------|------|---------|---------|--------|-------|-------|------|---|---|
| Pitch | 2.416 | 2.190 | 2.498 | 0.357 | 0.546 | reinforcing | 0.232 | 1 | 0 |
| Roll | 0.693 | 0.187 | 0.551 | 0.314 | 0.936 | decoupled | 0.214 | 0 | 1 |
| Yaw | 5.005 | 1.290 | - | 0.296 | 0.555 | decoupled | 0.142 | 1 | 0 |
| Z | 0.032 | 0.030 | - | 0.713 | 0.880 | reinforcing | 0.296 | 2 | 0 |

## Alerts

- [CRITICAL] **NEAR_SATURATION**: roll: MRAC near saturation (ρ_p95=0.94). Reduce gamma or increase u_max.
- [WARN] **REDUNDANT_EFFORT**: pitch: MRAC reinforcing PID (r=0.31) with significant authority. PID may need retuning.
- [WARN] **POOR_TRACKING**: yaw: Tracking degraded (RMSE=5.00).
- [WARN] **HIGH_AUTHORITY**: z: MRAC-dominant (ρ=0.71). PID gains may be insufficient.
- [WARN] **REDUNDANT_EFFORT**: z: MRAC reinforcing PID (r=0.37) with significant authority. PID may need retuning.

## Per-Axis Detail

### Pitch

#### Tracking
![Pitch Tracking](windowed_rmse_pitch.png)

| Metric | Value |
|--------|-------|
| RMSE | 2.416 |
| MAE | 2.377 |
| Peak Error | 3.697 |
| Steady-State RMSE | 2.190306869399112 |
| Transient RMSE | 2.498193884850891 |

#### Control Authority
![Pitch Authority](authority_timeline_pitch.png)
- ρ_mean = 0.357, ρ_p95 = 0.546
- u_ad RMS = 34.02 mixer units, u_nom RMS = 0.06 mixer units
- Phase relationship: reinforcing (r = 0.31)

#### Weight Health
![Pitch Adaptive Weights](weight_trajectory_pitch.png)
| Weight | θ_final | Drift (/s) | Proj. Hits | Oscillation (/s) |
|--------|---------|------------|------------|-------------------|
| W[0] bias | 0.000 | -0.0004 | 0.0% | 1.91 |
| W[1] angle | 0.001 | 0.0000 | 0.0% | 1.76 |
| W[2] rate | 0.002 | -0.0000 | 0.0% | 1.03 |
| W[3] drag | 0.007 | 0.0000 | 0.0% | 1.47 |
| W[4] un | 0.182 | 0.0000 | 0.0% | 1.18 |
| W[5] v | 0.144 | 0.0000 | 0.0% | 1.62 |

- ‖Θ‖ final = 0.232, trending: → STABLE/CONVERGING
- Hard-freeze fraction: 0.0%

### Roll

#### Tracking
![Roll Tracking](windowed_rmse_roll.png)

| Metric | Value |
|--------|-------|
| RMSE | 0.693 |
| MAE | 0.340 |
| Peak Error | 3.193 |
| Steady-State RMSE | 0.18662394352049608 |
| Transient RMSE | 0.5505437466714895 |

#### Control Authority
![Roll Authority](authority_timeline_roll.png)
- ρ_mean = 0.314, ρ_p95 = 0.936
- u_ad RMS = 28.28 mixer units, u_nom RMS = 0.06 mixer units
- Phase relationship: decoupled (r = 0.05)

#### Weight Health
![Roll Adaptive Weights](weight_trajectory_roll.png)
| Weight | θ_final | Drift (/s) | Proj. Hits | Oscillation (/s) |
|--------|---------|------------|------------|-------------------|
| W[0] bias | 0.028 | -0.0000 | 0.0% | 1.47 |
| W[1] angle | 0.000 | -0.0000 | 0.0% | 1.47 |
| W[2] rate | 0.007 | -0.0000 | 0.0% | 1.62 |
| W[3] drag | 0.003 | -0.0000 | 0.0% | 1.47 |
| W[4] un | 0.167 | 0.0002 | 0.0% | 1.03 |
| W[5] v | 0.132 | -0.0001 | 0.0% | 1.32 |

- ‖Θ‖ final = 0.214, trending: → STABLE/CONVERGING
- Hard-freeze fraction: 0.0%

### Yaw

#### Tracking
![Yaw Tracking](windowed_rmse_yaw.png)

| Metric | Value |
|--------|-------|
| RMSE | 5.005 |
| MAE | 1.571 |
| Peak Error | 25.026 |
| Steady-State RMSE | 1.2904912717931376 |
| Transient RMSE | - |

#### Control Authority
![Yaw Authority](authority_timeline_yaw.png)
- ρ_mean = 0.296, ρ_p95 = 0.555
- u_ad RMS = 50.58 mixer units, u_nom RMS = 0.03 mixer units
- Phase relationship: decoupled (r = 0.16)

#### Weight Health
![Yaw Adaptive Weights](weight_trajectory_yaw.png)
| Weight | θ_final | Drift (/s) | Proj. Hits | Oscillation (/s) |
|--------|---------|------------|------------|-------------------|
| W[0] bias | 0.004 | -0.0002 | 0.0% | 1.32 |
| W[1] angle | 0.001 | -0.0001 | 0.0% | 1.18 |
| W[2] rate | 0.001 | -0.0000 | 0.0% | 1.47 |
| W[3] drag | 0.000 | 0.0000 | 0.0% | 0.00 |
| W[4] un | 0.114 | -0.0000 | 0.0% | 1.32 |
| W[5] v | 0.084 | -0.0000 | 0.0% | 1.32 |

- ‖Θ‖ final = 0.142, trending: → STABLE/CONVERGING
- Hard-freeze fraction: 0.0%

### Z

#### Tracking
![Z Tracking](windowed_rmse_z.png)

| Metric | Value |
|--------|-------|
| RMSE | 0.032 |
| MAE | 0.028 |
| Peak Error | 0.077 |
| Steady-State RMSE | 0.029915280371824515 |
| Transient RMSE | - |

#### Control Authority
![Z Authority](authority_timeline_z.png)
- ρ_mean = 0.713, ρ_p95 = 0.880
- u_ad RMS = 40.22 mixer units, u_nom RMS = 0.12 mixer units
- Phase relationship: reinforcing (r = 0.37)

#### Weight Health
![Z Adaptive Weights](weight_trajectory_z.png)
| Weight | θ_final | Drift (/s) | Proj. Hits | Oscillation (/s) |
|--------|---------|------------|------------|-------------------|
| W[0] bias | 0.176 | 0.0058 | 0.0% | 1.47 |
| W[1] angle | 0.000 | -0.0000 | 0.0% | 1.03 |
| W[2] rate | 0.003 | 0.0000 | 0.0% | 1.32 |
| W[3] drag | 0.000 | 0.0000 | 0.0% | 0.00 |
| W[4] un | 0.198 | -0.0000 | 0.0% | 1.18 |
| W[5] v | 0.132 | -0.0000 | 0.0% | 1.18 |

- ‖Θ‖ final = 0.296, trending: → STABLE/CONVERGING
- Hard-freeze fraction: 0.0%

## Firmware Parameters (Snapshot)
```json
{
  "payload": "PAYLOAD_LIGHT",
  "mrac_dt": 0.005,
  "num_basis": 6,
  "mixer": {
    "pitch": 1170.0,
    "roll": 1170.0,
    "yaw": 1872.0,
    "z": 222.0
  },
  "gamma": {
    "pitch": [
      0.5,
      3.3,
      1.0,
      2.0,
      0.1,
      1.0
    ],
    "roll": [
      0.5,
      3.3,
      1.0,
      2.0,
      0.1,
      1.0
    ],
    "yaw": [
      0.3,
      2.0,
      0.7,
      1.5,
      0.1,
      1.0
    ]
  },
  "wlim": {
    "pitch": [
      0.5,
      0.6,
      0.4,
      0.1,
      0.4,
      0.2
    ],
    "roll": [
      0.5,
      0.6,
      0.4,
      0.1,
      0.4,
      0.2
    ],
    "yaw": [
      0.3,
      0.4,
      0.2,
      0.05,
      0.3,
      0.2
    ]
  },
  "sigma": {
    "pitch": "from_config",
    "roll": "from_config",
    "yaw": "from_config"
  },
  "features": {
    "projection": true,
    "sigma_mod": true,
    "deadzone": true,
    "l1_filter": true,
    "pch": true,
    "perf_recovery": true
  },
  "_comment": "Manual overrides for firmware params. Edit before a test session. deep_analysis.py merges this into the experiment record.",
  "_instructions": "Update the fields below when you change firmware params that aren't in telemetry yet.",
  "sigma_pitch": null,
  "sigma_roll": null,
  "sigma_yaw": null,
  "omega_u_pitch": null,
  "omega_u_roll": null,
  "omega_u_yaw": null,
  "e_deadzone": null,
  "e_freeze": 8.0,
  "notes": ""
}
```
