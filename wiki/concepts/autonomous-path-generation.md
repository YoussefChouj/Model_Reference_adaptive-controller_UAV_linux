---
title: Autonomous Path Generation
type: concept
tags: [autonomy, path, twc, sinusoid, circle]
created: 2026-04-14
updated: 2026-04-14
sources: [TASK/AutoflyTask.c, TASK/send_data.c, TASK/StabilizerTask.c]
related_files: [TASK/AutoflyTask.c, TASK/send_data.c, TASK/StabilizerTask.c]
---

Autonomous path generation in this codebase is split between command-side parameter loading (`Process_GroundStation_Command`) and runtime execution in `AutoflyTask` at 200 Hz (`USER/main.c:220-227`). All paths ultimately write setpoint targets consumed by [[StabilizerTask]].

## Runtime Signatures

- `void AutoflyTask(void)` (`TASK/AutoflyTask.c:101`)
- `void AutoflyTask_RunCircle(void)` (`TASK/AutoflyTask.c:29`)
- `void AutoflyTask_RunSinusoid(void)` (`TASK/AutoflyTask.c:57`)
- `void Update_Des(unsigned char which_level)` (TWC consumption, `TASK/StabilizerTask.c:361`)

Each procedural path integrates with `dt = 0.005f` (`TASK/AutoflyTask.c:31,59`), matching the task period.

## TWC (Point-to-Point) Path

TWC parameters are loaded by `CMD 0x0A`:
- `idx 0..2`: `TWC.target_x/y/z`
- `idx 3`: `TWC.set_yaw`
- `idx 4`: `TWC.execute`
(`TASK/send_data.c:584-594`)

Execution happens in `StabilizerTask::Update_Des` where `TWC.execute == 1` overrides local desired values for position/yaw (`TASK/StabilizerTask.c:396,422,465`). Arrival is computed as 3D distance `< 0.15f` and published as `TWC_arrived` (`TASK/StabilizerTask.c:373-381`).

## Sinusoid Path

Parameter source is `CMD 0x0B` (`TASK/send_data.c:597-626`):
- center coordinates (`idx 0..2`)
- amplitude (`idx 3`)
- frequency (`idx 4`)
- duration (`idx 5`)
- axis selector 0/1/2 (`idx 6`)
- active toggle (`idx 7`)

Trajectory equation in runtime:
`off = amplitude * sin(2*pi*frequency*t_elapsed)` (`TASK/AutoflyTask.c:73-74`)

Axis routing:
- `axis 0`: vary `Ctrler.locxPID.Des`
- `axis 1`: vary `Ctrler.locyPID.Des`
- `axis 2`: vary `Ctrler.Z_posPID.Des`
(`TASK/AutoflyTask.c:75-86`)

## Circle Path

Parameter source is `CMD 0x0C` (`TASK/send_data.c:628-653`):
- center xyz (`idx 0..2`)
- radius (`idx 3`)
- angular speed omega (`idx 4`)
- duration (`idx 5`)
- active (`idx 6`)

Runtime parametric equations:
- `x_des = center_x + radius*cos(theta)`
- `y_des = center_y + radius*sin(theta)`
- `theta += angular_speed*dt`
(`TASK/AutoflyTask.c:43-47`)

Yaw is coupled to path phase: `Ctrler.yawPID.Des = theta * RAD2DEG` (`TASK/AutoflyTask.c:48`).

## Arbitration Interface and Exclusivity

Path activity flags are:
- `TWC.execute`
- `sinusoid_path.active`
- `circle_path.active`

`AutoflyTask_PathArbitrate()` enforces single-active behavior (`TASK/AutoflyTask.c:15-27`), so each generator can assume no competing writer should remain active after arbitration.

## Setpoint Handoff Contract

The handoff is direct shared writes into `Ctrler.*.Des` and `TWC` globals; no lock/queue is used. This keeps latency low but depends on deterministic loop timing and small critical updates.

## Evidence vs Inference

Evidence-backed:
- CMD-to-parameter mapping and runtime equations are directly anchored in `TASK/send_data.c` and `TASK/AutoflyTask.c`.
- TWC consumption path is anchored in `TASK/StabilizerTask.c`.

Inference-labeled:
- Frame interpretation as “world-frame trajectory generation” is based on variable naming and update equations; if coordinate conventions are changed elsewhere, this interpretation must be revalidated against interface docs and flight tests.

## See Also

- [[AutoflyTask]]
- [[Path Arbitration]]
- [[Control Loop Timing]]
