# Flight Summary: TWC

**Date**: 2026-06-15 21:29:24  
**Source CSV**: `flight_twc_1781527181.csv`  
**Mode**: `twc`  
**Rank score** (planar_rmse_cm): 35.41960781671677  

## What Happened

- Planar XY tracking RMSE was **35.4 cm** (peak 46.6 cm).
- Worst-tracked position axis was **Y** (RMSE 33.63 cm).
- Feedback trailed the reference by ~**1406 ms** (along-track/phase lag).
- **Y** tracking error is dominated by **DC offset/drift** (bias 25 / amp 0 / lag 6 / resid 2 cm RMS; gain 1.02).
- **Never settled** within 5 cm of target (final error 22.2 cm).
- ⚠ **3 CRITICAL** MRAC alert(s) — run is INELIGIBLE as a champion until resolved.
- MRAC was most active on **z** (ρ_mean 0.94).

## Parameters


## Plots & Full Report

See `report.md` and the `.png` files in this folder (XY trajectory, position,
tracking, MRAC authority/weights/spectral).
