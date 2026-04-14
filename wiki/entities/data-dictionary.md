---
title: Data Dictionary
type: entity
tags: [structs, types, shared-memory, global-state]
created: 2026-04-14
updated: 2026-04-14
sources: [Global_file/robot_types.h, Global_file/global_declare.h, Global_file/data_types.h]
related_files: [Global_file/robot_types.h, Global_file/global_declare.h]
relations:
  - type: reads_from
    target: "[[StabilizerTask]]"
  - type: reads_from
    target: "[[AutoflyTask]]"
  - type: reads_from
    target: "[[RemoterTask]]"
---

This page documents every shared struct and global variable that crosses task boundaries. These types are defined in `Global_file/robot_types.h` and declared extern in `Global_file/global_declare.h`. Any agent working in this codebase should understand these types before modifying control, telemetry, or command code.

## PIDTypeDef — Single PID Loop State

Defined at `Global_file/robot_types.h:7-31`. This is the fundamental control building block — every axis has one or more of these.

| Field | Type | Chinese | Meaning |
|-------|------|---------|---------|
| `Des` | float | 目标值 | Desired setpoint |
| `FB` | float | 反馈值 | Feedback (measured) value |
| `Kp` | float | 比例系数 | Proportional gain |
| `Ki` | float | 积分系数 | Integral gain |
| `Kd` | float | 微分系数 | Derivative gain |
| `Up` | float | 比例输出 | Proportional output term |
| `Ui` | float | 积分输出 | Integral output term |
| `Ud` | float | 微分输出 | Derivative output term |
| `E` | float | 本次偏差 | Current error (`Des - FB`) |
| `PreE` | float | 上次偏差 | Previous error (for derivative) |
| `SumE` | float | 总偏差 | Accumulated error (for integral) |
| `U` | float | PID输出 | Final PID output |
| `UMax` | float | 输出最大值 | Output clamp ceiling |
| `UpMax` | float | 比例最大值 | Proportional term clamp |
| `UiMax` | float | 积分最大值 | Integral anti-windup limit |
| `UdMax` | float | 微分最大值 | Derivative term clamp |
| `SumEMax` | float | 积分饱和值 | Integral saturation limit |
| `EMin` | float | 积分分离阈值 | Integral separation threshold (deadzone) |

These fields are written by `ComputePID()` and read by the mixer in [[StabilizerTask]]. Gains are updated at runtime by ground-station CMD `0x01` (`TASK/send_data.c:481-501`).

## CtrlerTypeDef — Complete Controller State

Defined at `Global_file/robot_types.h:33-50`. Contains all PID loops for the vehicle.

```c
typedef struct {
    PIDTypeDef pitchPID;      // Outer pitch angle loop
    PIDTypeDef rollPID;       // Outer roll angle loop
    PIDTypeDef yawPID;        // Outer yaw angle loop
    PIDTypeDef gyroxPID;      // Inner pitch rate loop
    PIDTypeDef gyroyPID;      // Inner roll rate loop
    PIDTypeDef gyrozPID;      // Inner yaw rate loop
    PIDTypeDef Z_posPID;      // Altitude position loop
    PIDTypeDef Z_ratePID;     // Altitude rate loop
    PIDTypeDef locxPID;       // X position loop
    PIDTypeDef locyPID;       // Y position loop
    PIDTypeDef locxsPID;      // X velocity loop
    PIDTypeDef locysPID;      // Y velocity loop
    PIDTypeDef stree_yaw_speed;   // Street-tracking yaw rate
    PIDTypeDef stree_pitch_speed; // Street-tracking pitch rate
} CtrlerTypeDef;
```

Global instance: `extern CtrlerTypeDef Ctrler;` (`API/pid.h:16`).

**Writers**: [[StabilizerTask]] (`Compute_Motor`, `Update_Data`, `Update_Des`), [[AutoflyTask]] (path setpoints into `*.Des` fields), `Process_GroundStation_Command` (gain updates).

**Readers**: [[StabilizerTask]] (mixer), telemetry packing (`TASK/send_data.c`).

**Critical invariant**: `Ctrler.*.Des` fields are written by both AutoflyTask and StabilizerTask with no mutex. Safety depends on small write footprints and deterministic 5 ms scheduling.

## DroneStatusTypeDef — Vehicle State Flags

Defined at `Global_file/robot_types.h:67-76`.

| Field | Type | Values | Meaning |
|-------|------|--------|---------|
| `PIDingDelayMS` | unsigned int | — | Startup PID hold delay |
| `SensorsStatus` | unsigned char | — | Sensor health flags |
| `AdjustStatus` | unsigned char | — | Calibration state |
| `ARM_Status` | unsigned char | `DisArmed=0`, `Armed=1` | Arming state (`Global_file/global_declare.h:34-35`) |
| `FlyMode` | unsigned char | `FlyMode_DangerousStop=0`, `FlyMode_SDK=1` | Flight mode (`Global_file/global_declare.h:29-30`) |
| `Is_GetingGyroZero` | _Bool | — | Gyro zero-offset calibration active |

Global instance: `extern DroneStatusTypeDef DroneStatus;` (`Global_file/global_declare.h:131`).

**Writers**: `Check_Fly_Mode()` sets `FlyMode` (`TASK/RemoterTask.c:120-143`), `Check_Stick_Motion()` sets `ARM_Status` (`TASK/RemoterTask.c:103-113`), CMD `0x0E` sets `ARM_Status` (`TASK/send_data.c:662-673`), CMD `0x04` sets `FlyMode` (`TASK/send_data.c:568-578`).

**Readers**: `Update_Motor()` gates motor output on `ARM_Status` and `FlyMode` (`TASK/StabilizerTask.c:170-197`).

## RemoterTypeDef — Physical RC Stick Values

Defined at `Global_file/robot_types.h:104-113`.

| Field | Type | Range | Meaning |
|-------|------|-------|---------|
| `PitCtrler` | unsigned short | 2000-4000 | Pitch stick (center 3000) |
| `RolCtrler` | unsigned short | 2000-4000 | Roll stick (center 3000) |
| `YawCtrler` | unsigned short | 2000-4000 | Yaw stick (center 3000) |
| `ThrCtrler` | unsigned short | 2000-4000 | Throttle stick (center 3000) |
| `DinggaoSwitch` | unsigned short | — | Altitude-hold switch |
| `DingdianSwitch` | unsigned short | — | Position-hold switch |
| `StopSwitch` | unsigned short | — | Emergency stop switch |

Global instance: `extern RemoterTypeDef Remoter;` (`Global_file/global_declare.h:130`).

Written in `remoter_task()` from SBUS channel scaling (`TASK/RemoterTask.c:21-39`). Read in `eff_rc_*` helpers in [[StabilizerTask]] (`TASK/StabilizerTask.c:27-73`) and `Check_Stick_Motion()` in [[RemoterTask]].

## StickMotionTypeDef — Stick Gesture Counters

Defined at `Global_file/robot_types.h:53-64`.

Eight counters (`LeftStick_LeftDown_cnt`, `LeftStick_RightDown_cnt`, etc.) that increment each 10 ms cycle when the corresponding stick corner is held. Used for arm/disarm gesture detection in `Check_Stick_Motion()` (`TASK/RemoterTask.c:61-113`).

- Arm threshold: `LeftStick_RightDown_cnt >= ARM_Delay_time (150)` → ~1.5 s hold at 100 Hz
- Disarm threshold: `LeftStick_LeftDown_cnt >= DISARM_Delay_time (50)` → ~0.5 s hold

## _imu_st — Attitude Estimation Output

Defined at `Global_file/robot_types.h:318-339`.

| Field | Type | Meaning |
|-------|------|---------|
| `q0..q3` | float | Quaternion state |
| `gkp`, `gki` | float | Filter gains (shadows of Mahony Kp/Ki) |
| `x_vec[3]`, `y_vec[3]`, `z_vec[3]` | float[3] | DCM row vectors |
| `a_acc[3]` | float[3] | Accelerometer reading |
| `gacc_deadzone[3]` | float[3] | Gravity-corrected accel deadzone |
| `gra_acc[3]` | float[3] | Gravity-component acceleration |
| `rol`, `pit`, `yaw` | float | Euler angles (degrees) |

Global instance: `extern _imu_st imu_data;` (`API/imu_update.c:11`, `API/imu_update.h:8`).

Written by `IMU_Update_Mahony()` at 1 kHz (`API/imu_update.c:43`). Read by `Update_Data()` in [[StabilizerTask]] (`TASK/StabilizerTask.c:154-160`).

## SYSTEM_MONITOR — Task Health Counters

Defined at `Global_file/robot_types.h:79-102`.

Contains `*_cnt` fields incremented each task loop cycle and `*_fps` fields computed by `SystemErrorDetect()` at 1 Hz (`USER/main.c:100-111`). Used to detect if any task has stalled. If a task's fps drops to zero, the monitor can flag it.

Global instance: `extern SYSTEM_MONITOR system_monitor;` (`Global_file/global_declare.h:129`).

## USART_RX_TypeDef — UART DMA Receive Descriptor

Defined at `Global_file/robot_types.h:115-126`.

| Field | Chinese | Meaning |
|-------|---------|---------|
| `USARTx` | 串口 | USART peripheral pointer |
| `DMAy_Streamx` | DMA数据流 | DMA stream for this UART |
| `pMailbox` | 邮箱 | Effective data buffer (post-DMA copy) |
| `pDMAbuf` | DMA数组 | Raw DMA circular buffer |
| `MbLen` | mailbox长度 | Mailbox buffer size |
| `DMALen` | DMA长度 | DMA buffer size |
| `rxConter` | 本次DMA长度 | Current DMA fill position |
| `rxBufferPtr` | 上次的长度 | Previous fill position |
| `rxSize` | 本次接收长度 | Bytes received this cycle |

Used by `USART_Receive()` (`TASK/stm32f4xx_it.c:113-143`) to extract received bytes from DMA circular buffer on IDLE interrupt. Each UART that uses DMA-based reception (UART4, UART5, USART3) has one of these.

## Virtual RC and Safety Globals

Declared in `Global_file/global_declare.h:134-149`:

| Variable | Type | Meaning |
|----------|------|---------|
| `sbus_lost` | `volatile uint8_t` | 1 when physical RC signal timed out |
| `sbus_last_valid_tick` | `volatile uint32_t` | FreeRTOS tick of last good SBUS frame |
| `virtual_rc_sticks[4]` | `float` | Host-injected sticks [thr, pit, rol, yaw] |
| `bench_mode_active` | `volatile uint8_t` | Bench test mode flag |
| `gs_max_horizontal_speed_mps` | `float` | GS safety: max XY speed |
| `gs_max_vertical_speed_mps` | `float` | GS safety: max Z speed |
| `gs_max_pitch_deg` | `float` | GS safety: max pitch angle |
| `gs_max_roll_deg` | `float` | GS safety: max roll angle |
| `gs_throttle_min_pct` | `float` | GS safety: throttle floor (0-1) |
| `gs_throttle_max_pct` | `float` | GS safety: throttle ceiling (0-1) |
| `TWC_arrived` | `volatile uint8_t` | TWC point arrival flag |
| `GS_KeySDKflag` | `volatile uint8_t` | GS trigger for SDK state machine |

## Path Structs

### SinusoidPath_t (`Global_file/global_declare.h:152-162`)

| Field | Type | Set by |
|-------|------|--------|
| `center_x/y/z` | float | CMD `0x0B` idx 0-2 |
| `amplitude` | float | CMD `0x0B` idx 3 |
| `frequency` | float | CMD `0x0B` idx 4 |
| `duration` | float | CMD `0x0B` idx 5 |
| `axis` | uint8_t | CMD `0x0B` idx 6 (0=X, 1=Y, 2=Z) |
| `active` | uint8_t | CMD `0x0B` idx 7 |
| `t_elapsed` | float | Runtime integrator |

### CirclePath_t (`Global_file/global_declare.h:167-179`)

| Field | Type | Set by |
|-------|------|--------|
| `center_x/y/z` | float | CMD `0x0C` idx 0-2 |
| `radius` | float | CMD `0x0C` idx 3 |
| `angular_speed` | float | CMD `0x0C` idx 4 |
| `duration` | float | CMD `0x0C` idx 5 |
| `active` | uint8_t | CMD `0x0C` idx 6 |
| `theta` | float | Runtime phase angle |
| `t_elapsed` | float | Runtime time integrator |

## Key Constants

From `Global_file/global_declare.h`:

| Constant | Value | Meaning |
|----------|-------|---------|
| `SBUS_MID` | 1000 | SBUS channel center value |
| `SBUS_MAX` | 1800 | SBUS channel maximum |
| `SBUS_MIN` | 200 | SBUS channel minimum |
| `SBUS_OFFSET` | 100 | Stick validity deadzone |
| `Stick_to_MAX_Angle` | 18.0 | Max pitch/roll angle from stick (deg) |
| `Stick_to_MAX_GyroZ` | 200.0 | Max yaw rate from stick (deg/s) |
| `Stick_to_MAX_V_height` | 1.0 | Max vertical speed (m/s) |
| `FlyMode_DangerousStop` | 0 | Emergency stop mode |
| `FlyMode_SDK` | 1 | SDK/computer control mode |
| `ARM_Delay_time` | 150 | Arm gesture hold cycles (~1.5 s at 100 Hz) |
| `DISARM_Delay_time` | 50 | Disarm gesture hold cycles (~0.5 s) |
| `DisArmed` | 0 | Disarmed state constant |
| `Armed` | 1 | Armed state constant |
| `GRAVITY_MSS` | 9.80665 | Standard gravity (m/s²) |
| `DEG2RAD` | PI/180 | Degree to radian conversion |
| `RAD2DEG` | 180/PI | Radian to degree conversion |

## See Also

- [[PID Controller]]
- [[StabilizerTask]]
- [[RemoterTask]]
- [[MRAC Control Law]]
