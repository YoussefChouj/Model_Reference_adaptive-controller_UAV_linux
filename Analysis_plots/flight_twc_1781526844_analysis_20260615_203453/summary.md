# Flight Summary: TWC

**Date**: 2026-06-15 21:28:18  
**Source CSV**: `flight_twc_1781526844.csv`  
**Mode**: `twc`  
**Rank score** (planar_rmse_cm): 25.88274863195769  

## What Happened

- Planar XY tracking RMSE was **25.9 cm** (peak 48.1 cm).
- Worst-tracked position axis was **Y** (RMSE 23.24 cm).
- Feedback trailed the reference by ~**0 ms** (along-track/phase lag).
- **Y** tracking error is dominated by **DC offset/drift** (bias 5 / amp 4 / lag 1 / resid 4 cm RMS; gain 1.76).
- Yaw held **+0.2°** off command (drift -0.17°/s over the run) — expected heading-hold signature of bias/asymmetry.
- **Never settled** within 5 cm of target (final error 88.5 cm).
- ⚠ **2 CRITICAL** MRAC alert(s) — run is INELIGIBLE as a champion until resolved.
- MRAC was most active on **z** (ρ_mean 0.54).

## Parameters


## Plots & Full Report

See `report.md` and the `.png` files in this folder (XY trajectory, position,
tracking, MRAC authority/weights/spectral).
