---
title: AutoflyTask
type: entity
tags: [autonomy, path-planning, freertos]
created: 2026-04-13
updated: 2026-04-14
sources: [TASK/AutoflyTask.c, USER/main.c, TASK/send_data.c]
related_files: [TASK/AutoflyTask.c, TASK/send_data.c]
relations:
  - type: writes_to
    target: "[[StabilizerTask]]"
---

`AutoflyTask` is the autonomous setpoint generator running at 200 Hz. The FreeRTOS wrapper `void Autofly_Task(void *pvParameters)` uses `pdMS_TO_TICKS(5)` (`USER/main.c:220`) and calls `AutoflyTask()` (`USER/main.c:224`) once each 5 ms period.

## Function Signatures

- `void AutoflyTask(void)` (`TASK/AutoflyTask.c:101`)
- `static void AutoflyTask_PathArbitrate(void)` (`TASK/AutoflyTask.c:15`)
- `void AutoflyTask_RunCircle(void)` (`TASK/AutoflyTask.c:29`)
- `void AutoflyTask_RunSinusoid(void)` (`TASK/AutoflyTask.c:57`)
- `void SDK_StateMachine_Loop(void)` (`TASK/AutoflyTask.c:192`)

## Arbitration and Activation Logic

Mutual-exclusion invariant is enforced by `AutoflyTask_PathArbitrate()`:
- If sinusoid active, clear circle + `TWC.execute` (`TASK/AutoflyTask.c:17-20`)
- Else if circle active, clear sinusoid + `TWC.execute` (`TASK/AutoflyTask.c:20-23`)
- Else if `TWC.execute != 0`, clear both path flags (`TASK/AutoflyTask.c:23-26`)

This is the central single-writer policy for [[Path Arbitration]].

## Path Implementations

Both procedural paths use `const float dt = 0.005f` (`TASK/AutoflyTask.c:31,59`) to integrate phase/time.

Circle path (`AutoflyTask_RunCircle`):
- State update: `t_elapsed += dt`, `theta += angular_speed*dt` (`TASK/AutoflyTask.c:42-43`)
- Setpoint writes: `Ctrler.locxPID.Des`, `Ctrler.locyPID.Des`, `Ctrler.Z_posPID.Des`, `Ctrler.yawPID.Des` (`TASK/AutoflyTask.c:45-48`)
- Auto-stop when `duration` exceeded (`TASK/AutoflyTask.c:50-54`)

Sinusoid path (`AutoflyTask_RunSinusoid`):
- Offset: `amplitude * sin(2*pi*frequency*t_elapsed)` (`TASK/AutoflyTask.c:73-74`)
- Axis selector (`axis` 0/1/2) routes offset to X/Y/Z setpoint (`TASK/AutoflyTask.c:75-86`)
- Yaw is pinned to zero in this path (`TASK/AutoflyTask.c:92`)
- Auto-stop on duration (`TASK/AutoflyTask.c:94-98`)

TWC point path writes are command-side in `send_data.c` (CMD `0x0A`, `TASK/send_data.c:581-595`) and consumed by `Update_Des` in [[StabilizerTask]] (`TASK/StabilizerTask.c:396,422,465`).

## Setpoint Handoff and Shared Memory

Handoff to [[StabilizerTask]] is direct shared-memory writes into `Ctrler.*.Des` and `TWC` globals; no mutex/queue/semaphore is used. This gives low latency but introduces potential read-write races between tasks, mitigated in practice by fixed-rate periodic loops and small critical sections in each iteration.

## Evidence vs Inference

Evidence-backed:
- Arbitration function behavior, path equations, and SDK state-machine effects are all anchored directly in `TASK/AutoflyTask.c`.
- Path parameter ingress is anchored in command handler branches in `TASK/send_data.c`.

Inference-labeled:
- “Mitigated in practice by periodic loops” is an engineering interpretation; no explicit lock-free proof or race detector output is present in the repo.

## SDK State Coupling

`AutoflyTask` also runs a mission state machine gated by stick hold (`KeyPressedTimeMS` at `TASK/AutoflyTask.c:111-133`). It can assert `DroneStatus.ARM_Status = DisArmed` and `FlyMode_DangerousStop` during land completion (`TASK/AutoflyTask.c:262-264`), so this task is not path-only; it participates in arming lifecycle.

## See Also

- [[Path Arbitration]]
- [[Autonomous Path Generation]]
- [[Control Loop Timing]]
- [[StabilizerTask]]
