# Flight Summary: TWC

**Date**: 2026-06-15 21:29:16  
**Source CSV**: `flight_twc_1781527176.csv`  
**Mode**: `twc`  
**Rank score** (planar_rmse_cm): 34.513865472893876  

## What Happened

- Planar XY tracking RMSE was **34.5 cm** (peak 47.0 cm).
- Worst-tracked position axis was **Y** (RMSE 32.33 cm).
- Feedback trailed the reference by ~**1207 ms** (along-track/phase lag).
- **Y** tracking error is dominated by **DC offset/drift** (bias 23 / amp 1 / lag 5 / resid 3 cm RMS; gain 0.77).
- **Never settled** within 5 cm of target (final error 11.4 cm).
- ⚠ **3 CRITICAL** MRAC alert(s) — run is INELIGIBLE as a champion until resolved.
- MRAC was most active on **z** (ρ_mean 0.91).

## Parameters


## Plots & Full Report

See `report.md` and the `.png` files in this folder (XY trajectory, position,
tracking, MRAC authority/weights/spectral).
