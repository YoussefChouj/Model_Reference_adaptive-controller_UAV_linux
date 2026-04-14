---
title: Motor Mixer
type: actuator
tags: [pwm, motors, mixing, quadcopter]
created: 2026-04-13
updated: 2026-04-14
sources: [TASK/StabilizerTask.c, BSP/pwm.c, BSP/pwm.h]
related_files: [TASK/StabilizerTask.c, BSP/pwm.c, BSP/pwm.h]
relations:
  - type: reads_from
    target: "[[StabilizerTask]]"
  - type: writes_to
    target: "TIM3 PWM outputs"
---

The motor mixer converts controller outputs into four PWM compare values, then maps them onto TIM3 channels. Mix arithmetic is implemented in `void Compute_Motor(void)` (`TASK/StabilizerTask.c:237`) and hardware write-out is implemented in `void Set_PWM_Motors(void)` (`BSP/pwm.c:270`).

## Key Signatures

- `void Compute_Motor(void)` (`TASK/StabilizerTask.c:237`)
- `void Set_PWM_Motors(void)` (`BSP/pwm.c:270`)
- `void Set_Zero_Motors(void)` (`BSP/pwm.c:288`)
- `void Set_IDLE_Motors(void)` (`BSP/pwm.c:296`)

## Mixing Matrix (Exact Arithmetic)

The pre-mix variables are:
- `Throttle_out` (`TASK/StabilizerTask.c:307/314`)
- `u_gyrox`, `u_gyroy`, `u_gyroz` (`TASK/StabilizerTask.c:308-310,316-318`)

Motor equations:
- `motor1 = Throttle_out - u_gyroy - u_gyrox + u_gyroz` (`TASK/StabilizerTask.c:333-337`)
- `motor2 = Throttle_out + u_gyroy + u_gyrox + u_gyroz` (`TASK/StabilizerTask.c:338-342`)
- `motor3 = Throttle_out - u_gyroy + u_gyrox - u_gyroz` (`TASK/StabilizerTask.c:343-347`)
- `motor4 = Throttle_out + u_gyroy - u_gyrox - u_gyroz` (`TASK/StabilizerTask.c:348-351`)

## PWM Register Mapping

`pwm.h` defines the binding:
- `M1 -> TIM3->CCR1` (`BSP/pwm.h:8`)
- `M4 -> TIM3->CCR2` (`BSP/pwm.h:9`)
- `M2 -> TIM3->CCR3` (`BSP/pwm.h:10`)
- `M3 -> TIM3->CCR4` (`BSP/pwm.h:11`)

So physical channel order is intentionally non-sequential in macro names. `Set_PWM_Motors()` writes `M1..M4` from `mymotor.motor1..motor4` after clamping (`BSP/pwm.c:274-284`).

## Clamp and Arming Guards

Clamp limits come from:
- `Motor_PWM_ZERO = 2000` (`BSP/pwm.h:13`)
- `Motor_PWM_IDLE = 2150` (`BSP/pwm.h:14`)
- `Motor_PWM_MAX = 4000` (`BSP/pwm.h:15`)

Per-motor clamp is `value_limit(..., Motor_PWM_ZERO, Motor_PWM_MAX)` in `Set_PWM_Motors` (`BSP/pwm.c:274,277,280,283`). Throttle pre-clamp is also applied in control space via `Constrain_Float` on `Throttle_out` (`TASK/StabilizerTask.c:321-329`).

Before arming, `Update_Motor()` keeps motors off: in disarmed branch it calls `Set_Zero_Motors()` (`TASK/StabilizerTask.c:199-204`). In SDK arming/takeoff edge cases it may use idle output only (`TASK/StabilizerTask.c:175-182`), preventing full spin while altitude/throttle conditions are unsafe.

## See Also

- [[StabilizerTask]]
- [[Timer & PWM Configuration]]
- [[SDK Arming State Machine]]
