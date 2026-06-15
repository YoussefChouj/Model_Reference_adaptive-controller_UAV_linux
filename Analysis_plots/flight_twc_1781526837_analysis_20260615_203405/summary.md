# Flight Summary: TWC

**Date**: 2026-06-15 21:28:02  
**Source CSV**: `flight_twc_1781526837.csv`  
**Mode**: `twc`  
**Rank score** (planar_rmse_cm): 35.85542855151057  

## What Happened

- Planar XY tracking RMSE was **35.9 cm** (peak 63.2 cm).
- Worst-tracked position axis was **X** (RMSE 31.05 cm).
- Feedback trailed the reference by ~**625 ms** (along-track/phase lag).
- **X** tracking error is dominated by **DC offset/drift** (bias 13 / amp 2 / lag 10 / resid 11 cm RMS; gain 0.77).
- **Never settled** within 5 cm of target (final error 30.1 cm).
- 3 warning-level MRAC alert(s); no critical issues.
- MRAC was most active on **pitch** (ρ_mean 0.44).

## Parameters


## Plots & Full Report

See `report.md` and the `.png` files in this folder (XY trajectory, position,
tracking, MRAC authority/weights/spectral).
