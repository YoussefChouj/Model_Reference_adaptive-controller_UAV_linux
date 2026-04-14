---
title: RemoterTask
type: entity
tags: [rc, sbus, arming, flymode, freertos]
created: 2026-04-14
updated: 2026-04-14
sources: [TASK/RemoterTask.c, USER/main.c, Global_file/global_declare.h]
related_files: [TASK/RemoterTask.c, TASK/StabilizerTask.c, TASK/stm32f4xx_it.c]
relations:
  - type: reads_from
    target: "[[UART Peripheral Map]]"
  - type: writes_to
    target: "[[StabilizerTask]]"
  - type: safety_critical_for
    target: "[[SDK Arming State Machine]]"
---

`RemoterTask` handles all RC input processing, SBUS loss detection, stick gesture recognition, and flight mode determination. It runs at 100 Hz as `Remoter_Task` wrapper (`USER/main.c:200-211`) calling `remoter_task()` + `Check_Fly_Mode()` each cycle.

## Function Signatures

- `void remoter_task(void)` (`TASK/RemoterTask.c:11`) — channel scaling + SBUS loss detection
- `void Check_Stick_Motion(void)` (`TASK/RemoterTask.c:61`) — arm/disarm gesture counters
- `void Check_Fly_Mode(void)` (`TASK/RemoterTask.c:120`) — dangerous-stop vs SDK mode selection

## Channel Scaling

Raw SBUS values (`sbus_channel[0..3]`, range ~200-1800, center 1000) are scaled to the internal 2000-4000 range (center 3000) used by all downstream stick consumers (`TASK/RemoterTask.c:21-24`):

```c
channel[i] = (sbus_channel[i] - 1000) / 800.0 * 1000.0 + 3000.0;
```

Out-of-range values are clamped to center (`TASK/RemoterTask.c:31-34`):
```c
if (channel[0] < 1800 || channel[0] > 4200) channel[0] = 3000;
```

Channel-to-stick mapping (`TASK/RemoterTask.c:36-39`):
- `channel[0]` → `Remoter.RolCtrler` (roll)
- `channel[1]` → `Remoter.PitCtrler` (pitch)
- `channel[2]` → `Remoter.ThrCtrler` (throttle)
- `channel[3]` → `Remoter.YawCtrler` (yaw)

## SBUS Loss Detection

After channel scaling, `remoter_task()` evaluates `sbus_lost` (`TASK/RemoterTask.c:41-54`):

- If `sbus_last_valid_tick == 0` (no frame ever received) AND uptime > 500 ms → `sbus_lost = 1`
- Else if last valid frame was > 500 ms ago → `sbus_lost = 1`
- Otherwise → `sbus_lost = 0`

`sbus_last_valid_tick` is written in ISR context by the SBUS decoder: `sbus_last_valid_tick = xTaskGetTickCountFromISR()` (in `USART1_IRQHandler` → `DrvSbusGetOneByte()`, see [[Interrupt Map]]).

This 500 ms timeout is the threshold for transferring control authority to the ground station via [[Virtual RC Authority]].

## Stick Gesture Detection: Check_Stick_Motion

This function runs on effective sticks (respecting `sbus_lost` for SDK compatibility, `TASK/RemoterTask.c:63-66`):

```c
float eff_thr = sbus_lost ? virtual_rc_sticks[0] : (float)Remoter.ThrCtrler;
float eff_yaw = sbus_lost ? virtual_rc_sticks[3] : (float)Remoter.YawCtrler;
```

Eight corner-hold counters track stick positions using macros (`TASK/RemoterTask.c:57-59`):
- `is_Stick_MAX(value)`: value in 3900-4100
- `is_Stick_MIN(value)`: value in 1900-2100
- `is_Stick_MID(value)`: value in 2900-3100

**Arming** (`TASK/RemoterTask.c:68-70, 103-107`): Left stick right-down (throttle MIN + yaw MAX). Counter increments each cycle; when `LeftStick_RightDown_cnt >= ARM_Delay_time (150)` → `ARM_Status = Armed`. At 100 Hz task rate, this requires ~1.5 s hold.

**Disarming** (`TASK/RemoterTask.c:72-74, 109-113`): Left stick left-down (throttle MIN + yaw MIN). Counter threshold is `DISARM_Delay_time (50)` → ~0.5 s hold.

Other stick corners (left-up, right-up, right stick combos) have counters that may be used for calibration and debug modes.

## Flight Mode: Check_Fly_Mode

Called inside `Check_Stick_Motion` wrapper (`TASK/RemoterTask.c:120-143`).

Mode is determined by SBUS channel 5 (`sbus_channel[4]`):
- `sbus_channel[4] == 200` (switch in top position) and held for >10 cycles (~100 ms) → `FlyMode = FlyMode_DangerousStop` (`TASK/RemoterTask.c:125-138`)
- Otherwise → `FlyMode = FlyMode_SDK` (`TASK/RemoterTask.c:141`)

This means the default mode is SDK when no physical RC override switch is active.

## Data Flow Summary

```
SBUS ISR (USART1_IRQHandler)
  └→ DrvSbusGetOneByte() → sbus_channel[], sbus_last_valid_tick

remoter_task() [100 Hz]
  ├→ Scale sbus_channel[] → Remoter.PitCtrler/RolCtrler/ThrCtrler/YawCtrler
  ├→ Evaluate sbus_lost from sbus_last_valid_tick
  └→ Check_Fly_Mode()
       ├→ Check_Stick_Motion() → ARM_Status, gesture counters
       └→ sbus_channel[4] → DroneStatus.FlyMode
```

## See Also

- [[Virtual RC Authority]] — what happens when sbus_lost = 1
- [[SDK Arming State Machine]] — full arming state transitions
- [[Data Dictionary]] — RemoterTypeDef, StickMotionTypeDef, DroneStatusTypeDef
- [[Interrupt Map]] — USART1 SBUS ISR path
