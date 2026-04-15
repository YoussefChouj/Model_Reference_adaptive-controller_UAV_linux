---
title: Multi-rate Task Partitioning
type: concept
tags: [freertos, scheduling, real-time]
created: 2026-04-13
updated: 2026-04-14
sources: [USER/main.c, TASK/StabilizerTask.c, TASK/AutoflyTask.c, API/imu_update.c]
related_files: [USER/main.c, TASK/StabilizerTask.c, TASK/AutoflyTask.c, API/imu_update.c]
---

The firmware is partitioned into periodic FreeRTOS tasks created in `start_task()` (`USER/main.c:31`). Each task is created with `xTaskCreate(...)` and then runs with deterministic `vTaskDelayUntil` cadence rather than best-effort delays.

## Task Creation Calls (Stack / Priority Sources)

Creation points:
- `SystemMonitor_Task` (`USER/main.c:36-41`)
- `IMU_DataDeal_Task` (`USER/main.c:44-49`)
- `IMUSample_Task` (`USER/main.c:52-57`)
- `Stabilizer_Task` (`USER/main.c:61-66`)
- `Remoter_Task` (`USER/main.c:69-74`)
- `Autofly_Task` (`USER/main.c:77-82`)
- `Send_Task` (`USER/main.c:84-89`)

Stack size and priority values come from macros passed as `..._STK_SIZE` and `..._PRIO` arguments in each `xTaskCreate` call above.

## Effective Rates and Delay Style

All major tasks use `vTaskDelayUntil` (not ISR timers):
- 1 Hz monitor: `pdMS_TO_TICKS(1000)` (`USER/main.c:103,109`)
- 100 Hz comms (`Send_Task`) and remote (`Remoter_Task`): `pdMS_TO_TICKS(10)` (`USER/main.c:120,203`)
- 1 kHz IMU sample + fusion: `pdMS_TO_TICKS(1)` (`USER/main.c:144,163`)
- 200 Hz stabilizer + autofly: `pdMS_TO_TICKS(5)` (`USER/main.c:180,220`)

No hardware timer ISR directly runs control/filter equations in this code path; timing is RTOS tick-driven.

## Priority Intent and Control Flow

Although numeric priorities are macro-defined elsewhere, architecture intent is clear from cadence and role:
- IMU sample/fusion must be highest practical urgency (sensor freshness for closed loop)
- Stabilizer follows IMU with next urgency (200 Hz control output)
- Autofly is slower supervisory setpoint generation
- Comms and monitoring are lower criticality

`Stabilizer_Task` explicitly initializes MRAC once (`MRAC_Init()`, `USER/main.c:182`) before entering the 200 Hz loop.

## Evidence vs Inference

Evidence-backed:
- Task creation locations and periods are directly visible in `USER/main.c:36-89` and task loops (`USER/main.c:100-228`).
- Shared globals and cross-task access patterns are visible in task/control/command modules (`TASK/AutoflyTask.c`, `TASK/StabilizerTask.c`, `TASK/send_data.c`).

Inference-labeled:
- The ordering statement “IMU > Stabilizer > Autofly > comms” is architecture intent inferred from cadence and control dependency, not a direct printout of numeric priority macro values in this file set. It should be revalidated against the actual `..._PRIO` macro definitions when tuning scheduler behavior.

## Shared-Memory Hazards

The system relies on shared globals instead of queues/mutexes for core control state:
- `Ctrler` fields written in both `AutoflyTask` and `StabilizerTask` (`TASK/AutoflyTask.c:45-48`, `TASK/StabilizerTask.c:245-282`)
- `TWC`, `sinusoid_path`, `circle_path` written in command handler and read in control/autofly tasks (`TASK/send_data.c:581-653`, `TASK/AutoflyTask.c:15-27`, `TASK/StabilizerTask.c:373-381`)
- `sbus_lost` and `sbus_last_valid_tick` cross ISR/task boundaries (`BSP/usart1.c:87`, `TASK/RemoterTask.c:42-53`)

This is intentional for low latency, but it means temporal consistency depends on periodic task timing and small write footprints rather than explicit synchronization primitives.

## See Also

- [[Control Loop Timing]]
- [[StabilizerTask]]
- [[IMU Update]]
- [[AutoflyTask]]
- [[FreeRTOS Primitives Used]] — exact API primitives, what's used and what's deliberately omitted
- [[STM32F4 Peripherals Reference]] — timer and NVIC configuration underlying task scheduling
