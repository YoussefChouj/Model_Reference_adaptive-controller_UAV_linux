---
title: Control Loop Timing
type: concept
tags: [real-time, dt, timing-contract]
created: 2026-04-13
updated: 2026-04-14
sources: [USER/main.c, API/imu_update.c, TASK/StabilizerTask.c, TASK/AutoflyTask.c, API/mrac.h]
related_files: [USER/main.c, API/imu_update.c, TASK/StabilizerTask.c, TASK/AutoflyTask.c]
relations:
  - type: must_match
    target: "[[IMU Update]]"
  - type: must_match
    target: "[[StabilizerTask]]"
---

This firmware depends on explicit dt contracts across estimator, controller, and path generators. The scheduler is FreeRTOS `vTaskDelayUntil` based, so dt is assumed periodic rather than measured each loop.

## Declared `dt` Constants and Periods

Estimator:
- `IMU_Update_Mahony(&imu_data,1e-3f)` (`USER/main.c:150`) with task period `pdMS_TO_TICKS(1)` (`USER/main.c:144`)
- Mahony uses `half_T = 0.5f * dt` internally (`API/imu_update.c:53`)

Control and autonomy:
- Stabilizer task period `pdMS_TO_TICKS(5)` (`USER/main.c:180`)
- Autofly task period `pdMS_TO_TICKS(5)` (`USER/main.c:220`)
- Path integrators declare `const float dt = 0.005f` in circle/sinusoid runners (`TASK/AutoflyTask.c:31,59`)
- MRAC compile-time control dt is `#define MRAC_DT 0.005f` (`API/mrac.h:194`)
- Optical-flow derivative terms in stabilizer also use `0.005f` (`TASK/StabilizerTask.c:107-147`)

## Jitter Risk and Timing Source

IMU update does not run from a dedicated hardware timer ISR in this path; it runs in FreeRTOS task context with `vTaskDelayUntil` (`USER/main.c:141-153`). This reduces complexity but introduces RTOS scheduling jitter risk if higher-priority work blocks CPU.

Similarly, stabilizer/autofly are task periodic loops, not semaphore-locked producer/consumer stages.

## Phase Relationship

There is no queue or semaphore forcing “IMUSample -> IMU_Update -> Stabilizer” immediate sequencing. Instead:
- `IMUSample_Task`, `IMU_DataDeal_Task`, and `Stabilizer_Task` are independent periodic loops (`USER/main.c:160-193`)
- Data exchange is shared globals (`imu_data`, `Ctrler`, path structs)

Therefore phase offsets are soft and scheduler-dependent. The design assumes bounded jitter and slow dynamics relative to 1 ms / 5 ms periods.

## What Breaks if `dt` Drifts

First failure is usually in [[IMU Update]] because Mahony correction and quaternion integration both multiply by dt (`API/imu_update.c:82-89,93-109`). Observable symptoms:
- yaw drift or oscillation
- pitch/roll lag under aggressive maneuvers

Then control degrades:
- MRAC adaptation scales with fixed 5 ms assumptions (`API/mrac.h:194`)
- path phase (`theta`, sinusoid time) mis-tracks real elapsed time (`TASK/AutoflyTask.c:42-43,70-74`)
- altitude/velocity derivative terms in stabilizer become biased (`TASK/StabilizerTask.c:145`)

Net symptom at the vehicle level is either sluggish tracking (dt too small assumption) or over-aggressive/oscillatory behavior (dt too large assumption).

## Evidence vs Inference

Evidence-backed:
- dt constants and scheduling periods are anchored in `USER/main.c`, `TASK/AutoflyTask.c`, and `API/mrac.h`.
- Mahony dt scaling on PI and quaternion propagation is explicit in `API/imu_update.c`.

Inference-labeled:
- The “first failure likely appears in yaw drift” statement is a control-behavior inference from Mahony structure and typical IMU noise behavior, not a logged runtime trace in this repo. Treat this as expected diagnostic guidance, not a proven incident record for this exact build.

## Timing Invariant

If any task period changes in `USER/main.c`, all dependent dt constants and gains must be updated together. This is a cross-file contract tied to [[Multi-rate Task Partitioning]], [[StabilizerTask]], and [[IMU Update]].

## See Also

- [[Multi-rate Task Partitioning]]
- [[IMU Update]]
- [[StabilizerTask]]
- [[AutoflyTask]]
