---
title: Virtual RC Authority
type: concept
tags: [safety, sdk-mode, arming, sbus]
created: 2026-04-13
updated: 2026-04-14
sources: [TASK/send_data.c, TASK/StabilizerTask.c, TASK/RemoterTask.c, Global_file/global_declare.h]
related_files: [TASK/send_data.c, TASK/StabilizerTask.c, Global_file/global_declare.h]
relations:
  - type: safety_critical_for
    target: "[[StabilizerTask]]"
---

Virtual RC is a gated authority layer: host stick commands are only accepted when physical RC is considered lost and flight mode is SDK. The exact firmware condition is:

`if (sbus_lost == 1 && DroneStatus.FlyMode == FlyMode_SDK && idx < 4)` (`TASK/send_data.c:525`)

## Data Model and Signatures

- Command handler: `void Process_GroundStation_Command(void)` (`TASK/send_data.c:471`)
- Effective stick readers: `eff_rc_thr/pit/rol/yaw` (`TASK/StabilizerTask.c:27-44`)
- Loss detector task: `void remoter_task(void)` (`TASK/RemoterTask.c:11`)

Global declarations:
- `extern volatile uint8_t sbus_lost;` (`Global_file/global_declare.h:135`)
- `extern volatile uint32_t sbus_last_valid_tick;` (`Global_file/global_declare.h:136`)
- `extern float virtual_rc_sticks[4];` (`Global_file/global_declare.h:137`)

Fly mode constants are macros:
- `FlyMode_DangerousStop = 0` (`Global_file/global_declare.h:29`)
- `FlyMode_SDK = 1` (`Global_file/global_declare.h:30`)

## Constraints

Stick vector layout is explicitly documented near throttle helper:
- Ordering: `[thr, pit, rol, yaw]` (`TASK/StabilizerTask.c:29`)
- Neutral nominal center: `3000.0f` used by validity tests (`TASK/StabilizerTask.c:49,56,63,70`)

CMD `0x06` writes by index:
- `idx 0 -> throttle`
- `idx 1 -> pitch`
- `idx 2 -> roll`
- `idx 3 -> yaw`

When gate is closed (SBUS present or non-SDK mode), command write is ignored (`TASK/send_data.c:524-527`) and control falls back to `Remoter.*Ctrler` via `eff_rc_*` helpers.

## How `sbus_lost` is Set

SBUS decoder updates freshness tick in ISR context:
- `sbus_last_valid_tick = xTaskGetTickCountFromISR();` (`BSP/usart1.c:87`)

`remoter_task` converts tick age into `sbus_lost`:
- If no valid frame ever seen and uptime > 500 ms -> lost (`TASK/RemoterTask.c:43-46`)
- Else if last frame older than 500 ms -> lost (`TASK/RemoterTask.c:48-49`)
- Otherwise -> not lost (`TASK/RemoterTask.c:50-52`)

This means virtual RC becomes authoritative only after receiver timeout and automatically yields back when SBUS resumes.

## Safety Implications

Authority handoff is single-source by design: every place that reads sticks in `StabilizerTask` uses `eff_rc_*` wrappers (`TASK/StabilizerTask.c:27-73`). Combined with command-side gate enforcement, this prevents mixed-control blending and makes behavior deterministic for [[SDK Arming State Machine]] and [[Path Arbitration]].

## See Also

- [[Path Arbitration]]
- [[Ground-Station Binary Protocol]]
- [[StabilizerTask]]
- [[SDK Arming State Machine]]
