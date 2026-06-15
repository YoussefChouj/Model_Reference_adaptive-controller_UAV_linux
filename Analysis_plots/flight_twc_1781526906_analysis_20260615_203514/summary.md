# Flight Summary: TWC

**Date**: 2026-06-15 21:28:35  
**Source CSV**: `flight_twc_1781526906.csv`  
**Mode**: `twc`  
**Rank score** (planar_rmse_cm): 26.234871543500777  

## What Happened

- Planar XY tracking RMSE was **26.2 cm** (peak 32.4 cm).
- Worst-tracked position axis was **Y** (RMSE 21.62 cm).
- Yaw held **-0.2°** off command (drift +0.74°/s over the run) — expected heading-hold signature of bias/asymmetry.
- **Never settled** within 5 cm of target (final error 24.7 cm).
- ⚠ **1 CRITICAL** MRAC alert(s) — run is INELIGIBLE as a champion until resolved.
- MRAC was most active on **z** (ρ_mean 0.71).

## Parameters


## Plots & Full Report

See `report.md` and the `.png` files in this folder (XY trajectory, position,
tracking, MRAC authority/weights/spectral).
