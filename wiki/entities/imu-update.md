---
title: IMU Update
type: sensor
tags: [imu, mahony, attitude-estimation, sensor-fusion, 1khz]
created: 2026-04-13
updated: 2026-04-14
sources: [API/imu_update.c, USER/main.c]
related_files: [API/imu_update.c, USER/main.c]
relations:
  - type: reads_from
    target: "IMU sensor pipeline (Sensor_Data_Prepare path)"
  - type: writes_to
    target: "[[StabilizerTask]]"
---

`IMU Update` is the Mahony-based attitude estimator running at 1 kHz. The call site is `IMU_Update_Mahony(&imu_data,1e-3f)` in `IMU_DataDeal_Task` (`USER/main.c:150`) with `vTaskDelayUntil(..., pdMS_TO_TICKS(1))` (`USER/main.c:144,152`), so its design dt is 1 ms.

## Function Signatures and Entry

- `void IMU_Update_Mahony(_imu_st *imu,float dt)` (`API/imu_update.c:43`)
- `float invSqrt(float x)` (`API/imu_update.c:33`)

Persistent states and gains:
- Quaternion state: `q0..q3` (`API/imu_update.c:27-30`)
- PI gains: `float Kp = 0.5f; float Ki = 0.001f;` (`API/imu_update.c:20-21`)
- Integral drift terms: `exInt`, `eyInt`, `ezInt` (`API/imu_update.c:23-25`)
- Output struct: `_imu_st imu_data` (`API/imu_update.c:11`)

## Sensor Read / Conversion Path

This file consumes already scaled physical channels (`Acc_X_Real`, `Gyro_X_Real`, etc.) instead of reading registers directly; register sampling happens in the IMU sample task (`Sensor_Data_Prepare()` at `USER/main.c:167`). Within this update:
- Accelerometer vector is normalized (`API/imu_update.c:70-73`)
- Gravity-direction error is cross-product based (`ex/ey/ez` at `API/imu_update.c:77-79`)
- Gyro correction applies PI: `Gyro_*_Real += Kp*e + eInt` (`API/imu_update.c:87-89`)

Direct register transaction details (device address, register map, raw LSB-to-float scale) are **not** present in `API/imu_update.c`; they live in lower-level sensor driver code invoked through `Sensor_Data_Prepare()`. In this branch, board init calls `bmi088_init()` (`BSP/BSP.c:14`), so this page should be interpreted as filter-layer behavior rather than raw bus-layer behavior.

Gyro-drift correction integral is accumulated with dt scaling: `exInt += Ki * ex * dt` etc. (`API/imu_update.c:82-84`). There is no explicit clamp/saturation on `exInt/eyInt/ezInt` in this source, so long-term bias protection relies on Mahony gain tuning and valid acceleration normalization.

## Quaternion Propagation and Euler Output

The propagation uses half-step integration (`half_T = 0.5f*dt`, `API/imu_update.c:53`) and updates quaternion with `delta_theta` terms (`API/imu_update.c:93-109`). Quaternion normalization is mandatory each cycle (`API/imu_update.c:112-116`) to avoid drift. Euler outputs are then written:
- `imu->pit = -asinf(vecxZ) * RAD2DEG` (`API/imu_update.c:135`)
- `imu->rol = atan2f(vecyZ, veczZ) * RAD2DEG` (`API/imu_update.c:136`)
- `imu->yaw = atan2f(R21, R11) * RAD2DEG` (`API/imu_update.c:137`)

These fields are consumed in `Update_Data()` by `StabilizerTask` (`TASK/StabilizerTask.c:154-160`).

## Timing and Failure Modes

Estimator timing invariant is explicitly documented in code comments: dt must match the 1 kHz loop (`API/imu_update.c:51-53`). If dt drifts upward, PI bias correction and quaternion integration both over-accumulate, typically appearing first as yaw wander and then pitch/roll bias under vibration. If dt drifts downward, correction becomes too weak and response lags. Because no queue/semaphore synchronizes sample and fusion tasks, the design assumes stable periodic execution from FreeRTOS scheduling.

## See Also

- [[Control Loop Timing]]
- [[Multi-rate Task Partitioning]]
- [[StabilizerTask]]
- [[Mahony Filter Theory]] — SO(3) observer math mapped to this file's variables
