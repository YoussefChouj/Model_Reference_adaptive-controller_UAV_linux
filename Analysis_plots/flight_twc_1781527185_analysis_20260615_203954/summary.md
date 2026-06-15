# Flight Summary: TWC

**Date**: 2026-06-15 21:29:33  
**Source CSV**: `flight_twc_1781527185.csv`  
**Mode**: `twc`  
**Rank score** (planar_rmse_cm): 32.340892270963934  

## What Happened

- Planar XY tracking RMSE was **32.3 cm** (peak 35.5 cm).
- Worst-tracked position axis was **Y** (RMSE 26.49 cm).
- Feedback trailed the reference by ~**646 ms** (along-track/phase lag).
- **Y** tracking error is dominated by **DC offset/drift** (bias 7 / amp 1 / lag 2 / resid 2 cm RMS; gain 0.62).
- **Never settled** within 5 cm of target (final error 32.5 cm).
- ⚠ **2 CRITICAL** MRAC alert(s) — run is INELIGIBLE as a champion until resolved.
- MRAC was most active on **z** (ρ_mean 0.90).

## Parameters


## Plots & Full Report

See `report.md` and the `.png` files in this folder (XY trajectory, position,
tracking, MRAC authority/weights/spectral).
