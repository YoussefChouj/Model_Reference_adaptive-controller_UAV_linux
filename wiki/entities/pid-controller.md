---
title: PID Controller
type: controller
tags: [pid, control, attitude, position]
created: 2026-04-14
updated: 2026-04-14
sources: [API/pid.c, API/pid.h, Global_file/robot_types.h]
related_files: [API/pid.c, API/pid.h, TASK/StabilizerTask.c]
relations:
  - type: reads_from
    target: "[[Data Dictionary]]"
  - type: writes_to
    target: "[[StabilizerTask]]"
---

The PID module implements position-form PID with integral separation, anti-windup clamping, and per-term output limits. All PID loops share the same `PIDTypeDef` struct (see [[Data Dictionary]]) and the same core compute function, with specialized variants for yaw wrapping and body-to-world coordinate rotation.

## Function Signatures

- `void ComputePID(PIDTypeDef *pPID)` (`API/pid.c:32`) — standard PID
- `void ComputeYawPID(PIDTypeDef *pPID)` (`API/pid.c:58`) — yaw with ±180° wrapping
- `void ComputePID_locx(PIDTypeDef *pPID)` (`API/pid.c:90`) — X position with yaw rotation
- `void ComputePID_locy(PIDTypeDef *pPID)` (`API/pid.c:119`) — Y position with yaw rotation
- `void Clear_Structure(void)` (`API/pid.c:148`) — reset all integral accumulators

## Core Algorithm: ComputePID

The standard PID follows this exact sequence (`API/pid.c:32-55`):

```c
E = Des - FB;                          // current error

// Integral separation: only accumulate when output not saturated AND error within threshold
if (((U <= UMax && E > 0) || (U >= -UMax && E < 0)) && ABS(E) < EMin)
    SumE += E;

value_limit(SumE, -SumEMax, SumEMax);  // integral saturation clamp
Ui = Ki * SumE;
value_limit(Ui, -UiMax, UiMax);        // integral output clamp

Up = Kp * E;
value_limit(Up, -UpMax, UpMax);        // proportional output clamp

Ud = Kd * (E - PreE);                  // derivative on error (not on measurement)
value_limit(Ud, -UdMax, UdMax);        // derivative output clamp

U = Up + Ui + Ud;                      // position-form PID
value_limit(U, -UMax, UMax);           // total output clamp

PreE = E;                              // save for next derivative
```

### Anti-Windup Strategy

Two-layer protection against integral windup:

1. **Integral separation** (`API/pid.c:36-40`): Integral accumulation only happens when:
   - The output is not yet saturated (conditional on sign of error vs output limit)
   - AND the error magnitude is below `EMin` (integral separation threshold)
   
   This prevents integral buildup during large transients or when output is already at limits.

2. **Saturation clamping** (`API/pid.c:41`): `SumE` is hard-clamped to `±SumEMax` regardless of the separation gate.

### Per-Term Clamping

Every term (P, I, D) has its own independent clamp (`UpMax`, `UiMax`, `UdMax`), and the total output is clamped by `UMax`. This prevents any single term from dominating the output.

## Yaw Variant: ComputeYawPID

Identical to `ComputePID` except for angle wrapping before PID computation (`API/pid.c:62-63`):

```c
if (E >= 180)  E -= 360;
if (E <= -180) E += 360;
```

This ensures the yaw controller always takes the shortest angular path, avoiding the 0°/360° discontinuity.

## Position Variants: ComputePID_locx / locy

These variants perform **world-to-body frame rotation** of position error before standard PID computation (`API/pid.c:94, 123`):

```c
// locx: body-frame X error from world-frame errors
locxPID.E = (locxPID.Des - locxPID.FB)*Cos_Yaw - (locyPID.Des - locyPID.FB)*Sin_Yaw;

// locy: body-frame Y error from world-frame errors  
locyPID.E = (locyPID.Des - locyPID.FB)*Cos_Yaw + (locxPID.Des - locxPID.FB)*Sin_Yaw;
```

This rotation means position controllers always compute error relative to the vehicle's heading, so pitch commands map to forward/backward motion regardless of yaw orientation. `Cos_Yaw` and `Sin_Yaw` are computed in `Update_Data()` of [[StabilizerTask]].

## Clear_Structure — Integral Reset

Called on disarm and mode transitions (`API/pid.c:148-167`). Zeros all `SumE` accumulators for the 8 core loops and resets position/yaw desired values to current feedback:

```c
Ctrler.locxPID.Des = Ctrler.locxPID.FB;  // prevent jump on re-arm
Ctrler.locyPID.Des = Ctrler.locyPID.FB;
Ctrler.yawPID.Des  = Ctrler.yawPID.FB;
```

This prevents integral windup carryover between flights and avoids setpoint discontinuities when transitioning from disarmed to armed.

## Loop Hierarchy in StabilizerTask

The 14 PID loops in `CtrlerTypeDef` are computed in a cascaded hierarchy:

```
Outer position loops (10 Hz effective from sensor updates):
  locxPID → locxsPID → pitchPID → gyroxPID → mixer
  locyPID → locysPID → rollPID  → gyroyPID → mixer
  Z_posPID → Z_ratePID → throttle
  yawPID → gyrozPID → mixer
```

All compute calls happen in `Compute_Motor()` (`TASK/StabilizerTask.c:237-351`).

## Gain Update at Runtime

Ground-station CMD `0x01` updates individual PID gains by loop index and parameter index (`TASK/send_data.c:481-501`). Each gain write is immediate (no double-buffer or atomic swap), so brief transients are possible during tuning. See [[Tuning Workflow]] and [[Ground-Station Binary Protocol]].

## See Also

- [[Data Dictionary]] — PIDTypeDef field reference
- [[StabilizerTask]] — where PID loops are invoked
- [[MRAC Control Law]] — adaptive augmentation layered on PID
- [[Tuning Workflow]] — how to tune gains via dashboard
