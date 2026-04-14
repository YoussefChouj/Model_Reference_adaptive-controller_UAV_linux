---
title: Coordinate Conventions
type: concept
tags: [coordinates, signs, motors, sticks, body-frame, world-frame]
created: 2026-04-14
updated: 2026-04-14
sources: [TASK/StabilizerTask.c, TASK/RemoterTask.c, BSP/pwm.h, API/imu_update.c, Global_file/global_declare.h]
---

This page defines the sign conventions used throughout the codebase. Getting any of these wrong causes motor spin reversal, inverted control, or coordinate frame mismatch. Any agent modifying mixer signs, stick mappings, or path generators must consult this page.

## Stick Range Convention

All stick values use a **2000-4000** range with **3000** as center neutral:

| Value | Meaning |
|-------|---------|
| 2000 | Full negative / minimum |
| 3000 | Center / neutral |
| 4000 | Full positive / maximum |

Source: channel scaling in `remoter_task()` (`TASK/RemoterTask.c:21-24`) and validity macros (`TASK/RemoterTask.c:57-59`).

Stick vector layout for `virtual_rc_sticks[4]` (`TASK/StabilizerTask.c:29`):

| Index | Axis | 2000 means | 4000 means |
|-------|------|------------|------------|
| 0 | Throttle | Minimum thrust | Maximum thrust |
| 1 | Pitch | Pitch forward (nose down) | Pitch backward (nose up) |
| 2 | Roll | Roll left | Roll right |
| 3 | Yaw | Yaw left (CCW) | Yaw right (CW) |

## Euler Angle Convention

Computed by [[IMU Update]] Mahony filter (`API/imu_update.c:135-137`):

- **Pitch** (`imu_data.pit`): Nose-down is negative, nose-up is positive. From `pit = -asinf(vecxZ) * RAD2DEG`.
- **Roll** (`imu_data.rol`): Left wing down is negative, right wing down is positive. From `rol = atan2f(vecyZ, veczZ) * RAD2DEG`.
- **Yaw** (`imu_data.yaw`): Increasing clockwise (CW). From `yaw = atan2f(R21, R11) * RAD2DEG`.

Maximum commanded angles from sticks: `Stick_to_MAX_Angle = 18.0°` for pitch/roll (`Global_file/global_declare.h:23`).

## Motor Mixing Sign Convention

From `Compute_Motor()` (`TASK/StabilizerTask.c:333-351`):

```
motor1 = Throttle_out - u_gyroy - u_gyrox + u_gyroz
motor2 = Throttle_out + u_gyroy + u_gyrox + u_gyroz
motor3 = Throttle_out - u_gyroy + u_gyrox - u_gyroz
motor4 = Throttle_out + u_gyroy - u_gyrox - u_gyroz
```

Where `u_gyrox` is pitch-rate output, `u_gyroy` is roll-rate output, `u_gyroz` is yaw-rate output.

Motor-to-physical mapping (`BSP/pwm.h:8-11`):

| Macro | TIM3 Channel | GPIO |
|-------|-------------|------|
| M1 | CCR1 | PA6 |
| M4 | CCR2 | PA7 |
| M2 | CCR3 | PB0 |
| M3 | CCR4 | PB1 |

The macro numbering is intentionally **non-sequential** relative to TIM3 channels. M1 uses CH1, but M4 uses CH2 (not M2). This mapping must be preserved during any rewiring or PCB changes.

Assuming standard X-quad layout:
```
    Front
  M1     M2
    \   /
     [X]
    /   \
  M3     M4
    Back
```

Positive `u_gyroz` (yaw CW) increases M1+M2 and decreases M3+M4, consistent with diagonal motor pairs sharing CW/CCW spin direction.

## World Frame (Position Loops)

Position PID uses world-frame coordinates:
- **X** (`Ctrler.locxPID`): forward positive
- **Y** (`Ctrler.locyPID`): rightward positive
- **Z** (`Ctrler.Z_posPID`): upward positive

Body-to-world rotation is applied in `ComputePID_locx` / `ComputePID_locy` (`API/pid.c:94, 123`):
```c
body_x_error = world_x_error * cos(yaw) - world_y_error * sin(yaw)
body_y_error = world_y_error * cos(yaw) + world_x_error * sin(yaw)
```

## Altitude Convention

- Altitude is measured upward-positive
- Throttle stick above center (>3000) commands upward velocity
- `Ctrler.Z_posPID.Des` and `Ctrler.Z_ratePID.Des` follow upward-positive convention
- `Stick_to_MAX_V_height = 1.0 m/s` (`Global_file/global_declare.h:26`)

## PWM Value Convention

| Constant | Value | Meaning |
|----------|-------|---------|
| `Motor_PWM_ZERO` | 2000 | Motors off (ESC idle/disarmed) |
| `Motor_PWM_IDLE` | 2150 | Minimum spin (armed but low thrust) |
| `Motor_PWM_MAX` | 4000 | Maximum thrust command |

Higher PWM count = more thrust. ESC calibration must match this range.

## Critical Invariants

1. **Stick index order** must match between `virtual_rc_sticks[]` write in `Process_GroundStation_Command` (`TASK/send_data.c:522-527`) and `eff_rc_*` reads in `StabilizerTask` (`TASK/StabilizerTask.c:29-44`).

2. **Motor macro-to-CCR mapping** must match physical motor wiring. Swapping M1↔M2 in `pwm.h` without updating mixer signs causes immediate flip on takeoff.

3. **Yaw-rotation in position PID** uses `Cos_Yaw` / `Sin_Yaw` computed from `imu_data.yaw` in `Update_Data()`. If the IMU yaw sign convention changes, position tracking will spiral.

## See Also

- [[Motor Mixer]] — mixer equations and PWM mapping
- [[PID Controller]] — locx/locy rotation details
- [[Data Dictionary]] — stick and constant values
- [[IMU Update]] — Euler angle computation
