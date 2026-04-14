---
title: Agent & Developer Quick-Start Guide
type: overview
tags: [onboarding, setup, build, workflow]
created: 2026-04-14
updated: 2026-04-14
sources: [USER/main.c, ground_station/config.yaml, BSP/BSP.h]
---

# Quick-Start Guide

This page is the **first thing** any new agent or developer should read before touching this codebase.

## What This Project Is

A 6-DOF quadcopter flight controller on STM32F4 + FreeRTOS, with PID attitude control augmented by a 4-axis MRAC adaptive layer. A Python ground station communicates over serial UART using a custom binary protocol. Visualization goes through VOFA+.

For full architecture see [[Project Overview]].

## Repository Layout

```
USER/              main.c — FreeRTOS task creation, entry point
TASK/              Control, telemetry, autonomy, interrupt handlers
  StabilizerTask.c   200 Hz PID+MRAC control pipeline
  AutoflyTask.c      200 Hz autonomous path generator
  send_data.c        100 Hz telemetry TX + command RX dispatch
  RemoterTask.c      RC input + SBUS loss + fly mode
  stm32f4xx_it.c     All UART/DMA IRQ handlers
API/               Algorithms: IMU fusion, MRAC, PID, GPS stub
  imu_update.c       1 kHz Mahony attitude estimator
  mrac.h / mrac_math.c  Adaptive control law
  pid.h              PID struct and compute declarations
BSP/               Board support: UART, PWM, SPI, LED
  pwm.c / pwm.h      TIM3 motor PWM generation
  usart1..6          UART peripheral configs
  BSP.c / BSP.h      BSP_Init() aggregator
Global_file/       Shared type defs and globals
  robot_types.h      ALL shared structs (PIDTypeDef, CtrlerTypeDef, ...)
  global_declare.h   Extern declarations, macros, path structs
  data_types.h       Primitive type aliases (FP32, UCHAR8, ...)
FreeRTOS/          RTOS kernel (do not modify)
stm32_lib/         ST peripheral library (do not modify)
ground_station/    Python ground station
  comm/serial_bridge.py   Serial decode, command TX, VOFA/UDP
  gui/dashboard.py        Operator GUI (tkinter)
  scripts/                Analysis, logging, diagnostics
  config.yaml             All runtime configuration
  presets/vofa/           VOFA+ workspace presets
wiki/              This knowledge base
docs/              decisions.md, interfaces.md, progress.md
```

## Build & Flash (Firmware)

**Toolchain**: Keil MDK-ARM (uVision 5)  
**Project file**: `USER/JX_FLY.uvprojx`

1. Open `USER/JX_FLY.uvprojx` in Keil
2. Build: `Project → Build Target` (or F7)
3. Flash: connect ST-Link, `Flash → Download` (or F8)

The MCU is STM32F4xx. Clock configuration is in `system_stm32f4xx.c`. BSP init (GPIO, timers, UART, SPI, sensors) runs in `BSP_Init()` (`BSP/BSP.c:4-30`) before FreeRTOS scheduler starts (`USER/main.c:16-27`).

## Ground Station Setup

**Requirements**: Python 3.10+, `pyserial`, `tkinter` (usually bundled), `pyyaml`

1. Edit `ground_station/config.yaml`:
   - `serial_port`: your COM port (e.g. `COM6`)
   - `baud_rate`: `115200` (must match firmware)
   - VOFA ports: `vofa_port_a: 1347`, `vofa_port_b: 1348`
   - See [[Config Reference]] for all keys

2. Launch dashboard:
   ```
   python -m ground_station.gui.dashboard
   ```

3. Connect serial → telemetry starts flowing → VOFA streams begin

See [[Dashboard]], [[Ground Station Bridge]], [[Config Reference]].

## Key Concepts to Understand First

Read these wiki pages in order for fastest ramp-up:

1. [[Project Overview]] — architecture in one page
2. [[Multi-rate Task Partitioning]] — how tasks are organized
3. [[Data Dictionary]] — the shared struct types that everything uses
4. [[StabilizerTask]] — the core control pipeline
5. [[Ground-Station Binary Protocol]] — how firmware and host talk
6. [[Virtual RC Authority]] — how SDK mode control works
7. [[SDK Arming State Machine]] — how to arm motors

## How to Arm and Fly in SDK Mode

This is the most common "nothing works" scenario. The complete flow:

1. **Power on** — motors start disarmed, all PWM at `Motor_PWM_ZERO` (2000)
2. **Ensure SBUS lost** — disconnect physical RC or wait 500 ms timeout (`TASK/RemoterTask.c:43-53`). `sbus_lost` must be `1`.
3. **Set SDK mode** — send CMD `0x04 idx=1` from dashboard. This sets `FlyMode = FlyMode_SDK` (`TASK/send_data.c:568-578`).
4. **Arm** — send CMD `0x0E idx=0 val=1.0` from dashboard. This sets `DroneStatus.ARM_Status = Armed` (`TASK/send_data.c:662-673`).
5. **Send throttle** — send CMD `0x06 idx=0 val=3500` (above center 3000). Virtual RC sticks are only accepted when `sbus_lost && FlyMode_SDK` (`TASK/send_data.c:525`).
6. **Motors spin** — `Update_Motor()` sees Armed + FlyMode_SDK and runs `Set_PWM_Motors()` (`TASK/StabilizerTask.c:170-185`).

See [[SDK Arming State Machine]] and [[Virtual RC Authority]] for details.

## Adding or Changing Code

### Before you edit:
- Read the relevant wiki pages for the subsystem you're touching
- Check [[Control Loop Timing]] if changing any task period or dt constant
- Check [[UART Peripheral Map]] if touching any serial communication
- Check [[Coordinate Conventions]] if touching motor mixing or stick signs

### After you edit:
- Verify that no timing contracts are broken (dt must match task period)
- Verify that command frame layouts match between firmware and Python
- Verify motor sign conventions haven't flipped

### Common recipes:
- [[Adding a Command]] — end-to-end guide for new CMD IDs
- [[Tuning Workflow]] — how to tune PID/MRAC parameters
- [[Common Pitfalls]] — troubleshooting checklist

## Wiki Query Priority

```
1. wiki/ pages      → conceptual understanding ("why was X designed this way?")
2. Grep/search      → exact code locations ("where is X?")
3. docs/decisions.md → architectural choices ("what was decided about X?")
4. docs/interfaces.md → cross-subsystem contracts
```

## See Also

- [[Project Overview]]
- [[Data Dictionary]]
- [[Common Pitfalls]]
