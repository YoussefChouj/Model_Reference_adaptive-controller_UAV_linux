# Flight Summary: TWC

**Date**: 2026-06-15 21:29:41  
**Source CSV**: `flight_twc_1781527193.csv`  
**Mode**: `twc`  
**Rank score** (planar_rmse_cm): 45.194274147849264  

## What Happened

- Planar XY tracking RMSE was **45.2 cm** (peak 56.6 cm).
- Worst-tracked position axis was **X** (RMSE 37.52 cm).
- Feedback trailed the reference by ~**1944 ms** (along-track/phase lag).
- **X** tracking error is dominated by **DC offset/drift** (bias 20 / amp 0 / lag 9 / resid 14 cm RMS; gain 1.02).
- **Never settled** within 5 cm of target (final error 30.9 cm).
- 5 warning-level MRAC alert(s); no critical issues.
- MRAC was most active on **z** (ρ_mean 0.88).

## Parameters


## Plots & Full Report

See `report.md` and the `.png` files in this folder (XY trajectory, position,
tracking, MRAC authority/weights/spectral).
