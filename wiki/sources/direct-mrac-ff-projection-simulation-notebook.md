---
title: Direct MRAC + FF + Projection Notebook
type: source
tags: [mrac, projection-operator, barrier-function, quadrotor, simulation]
created: 2026-04-14
updated: 2026-04-14
sources:
  - "C:/Users/Acer/Desktop/Pich_yaw_roll_experimental_drone_setup/Drone_experiments_python_jypeter_code/Roll_Pitch_Yaw_Adaptive_Control_Direct_MRAC_FFcontroller_Projection_operator v2.ipynb"
---

Structured digest of the user-built 60-cell simulation notebook for roll/pitch/yaw adaptive control. This source captures the tested code architecture and retains theory text as secondary context.

## End-to-end implementation diagram

```mermaid
flowchart LR
    REF[Reference trajectory] --> RM[Reference model]
    RM --> ERR[Tracking error]
    STATE[Current state] --> ERR
    STATE --> REG[Regressor construction]
    ERR --> LAW[Adaptive law update]
    REG --> LAW
    CFG[Config/PerfRec/Barrier flags] --> LAW
    LAW --> UAD[Adaptive control term]
    NOM[Nominal control term] --> SUM((+))
    UAD --> SUM
    SUM --> MIX[Mixer + actuator dynamics]
    MIX --> UAPP[Applied control]
    UAPP --> PLANT[State propagation]
    PLANT --> STATE
    STATE --> LOG[Diagnostics + plots]
```

## What this notebook implements (code-confirmed)

- Unified state-space reference model setup with explicit `wn`/`zeta` selection.
- Nominal controller + direct MRAC term with configurable adaptive features.
- Projection operator and sigma-modification toggles.
- Optional actuator dynamics and mixer/inverse-mixer loop for realistic motor lag effects.
- Set-theoretic error barrier utilities and integration into adaptation updates.
- Performance recovery, diagnostics, and rich post-run plotting/analysis pipeline.

## Core configurable modules

- `Config`: feature flags including projection, sigma-mod, actuator dynamics, structured uncertainty.
- `PerfRec`: performance recovery parameters and filtered augmentation terms.
- `BarrierConfig`: hard error limits, activation threshold, barrier gain, smoothing.
- Helper functions for scheduled adaptation gain, trajectory generation, uncertainty injection, and projection-aware weight updates.

## Theory-to-code implementation notes

- **Reference dynamics**: `wn` and `zeta` are explicit knobs that define the target transient behavior.
- **Adaptive core**: weight updates are built from error-correlated regressor terms with optional normalization.
- **Robustness layering**: projection, sigma-modification, deadzone/e-modification, and low-frequency shaping are composable via flags.
- **Constraint layer**: barrier gradients are injected into adaptation rather than replacing base MRAC terms.
- **Plant realism**: optional actuator and mixer block converts commanded torque to delayed applied torque, closing the realism gap.

## High-value implementation notes

- **Projection + sigma ordering**: notebook documents and applies a corrected update sequence where projection is applied to the gradient before sigma leakage is added.
- **Mixer realism**: forward/inverse mixer math is paired with hover-throttle normalization and actuator lag, then fed back as applied control.
- **Barrier integration**: logarithmic barrier gradient is added to adaptive updates with activation thresholding.
- **Debug depth**: includes numerical checks for overflow/NaN, saturation diagnostics, and tuning recommendation cells.

## Reliability guidance for agents

- Prioritize code cells and parameter definitions over markdown claims.
- Reuse this notebook as the main multi-axis benchmark environment.
- Validate any new theoretical edits against the existing simulation diagnostics.

## Related pages

- [[Adaptive Control Simulations]]
- [[MRAC Theory]]
- [[Timer & PWM Configuration]]
- [[Motor Mixer]]
