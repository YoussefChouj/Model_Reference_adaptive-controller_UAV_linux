# Flight Summary: SINUSOID

**Date**: 2026-06-15 21:27:55  
**Source CSV**: `flight_sinusoid_1781527210.csv`  
**Mode**: `sinusoid`  
**Rank score** (planar_rmse_cm): 54.808106415371746  

## What Happened

- Planar XY tracking RMSE was **54.8 cm** (peak 78.3 cm).
- Worst-tracked position axis was **X** (RMSE 48.20 cm).
- Feedback trailed the reference by ~**1008 ms** (along-track/phase lag).
- **X** tracking error is dominated by **phase lag** (bias 19 / amp 24 / lag 44 / resid 16 cm RMS; gain 0.39).
- ⚠ **2 CRITICAL** MRAC alert(s) — run is INELIGIBLE as a champion until resolved.
- MRAC was most active on **z** (ρ_mean 0.80).

## Parameters


## Plots & Full Report

See `report.md` and the `.png` files in this folder (XY trajectory, position,
tracking, MRAC authority/weights/spectral).
