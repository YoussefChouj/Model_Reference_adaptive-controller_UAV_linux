# Flight Summary: TWC

**Date**: 2026-06-15 21:28:27  
**Source CSV**: `flight_twc_1781526892.csv`  
**Mode**: `twc`  
**Rank score** (planar_rmse_cm): 37.62818995711192  

## What Happened

- Planar XY tracking RMSE was **37.6 cm** (peak 75.4 cm).
- Worst-tracked position axis was **Y** (RMSE 27.70 cm).
- Feedback trailed the reference by ~**1616 ms** (along-track/phase lag).
- **Y** tracking error is dominated by **DC offset/drift** (bias 23 / amp 0 / lag 6 / resid 3 cm RMS; gain 0.93).
- Yaw held **+0.4°** off command (drift -0.67°/s over the run) — expected heading-hold signature of bias/asymmetry.
- **Never settled** within 5 cm of target (final error 27.6 cm).
- ⚠ **3 CRITICAL** MRAC alert(s) — run is INELIGIBLE as a champion until resolved.
- MRAC was most active on **z** (ρ_mean 0.83).

## Parameters


## Plots & Full Report

See `report.md` and the `.png` files in this folder (XY trajectory, position,
tracking, MRAC authority/weights/spectral).
