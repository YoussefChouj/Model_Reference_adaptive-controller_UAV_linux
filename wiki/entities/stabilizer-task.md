---
title: StabilizerTask
type: controller
tags: [pid, mrac, attitude-control, freertos, mixer]
created: 2026-04-13
updated: 2026-04-14
sources: [TASK/StabilizerTask.c, USER/main.c, Global_file/global_declare.h]
related_files: [TASK/StabilizerTask.c, BSP/pwm.c, BSP/pwm.h]
relations:
  - type: reads_from
    target: "[[IMU Update]]"
  - type: writes_to
    target: "[[Motor Mixer]]"
---

`StabilizerTask` is the 200 Hz attitude/altitude control pipeline that converts sensor feedback + RC/SDK references into four motor commands. The FreeRTOS task entry is `void Stabilizer_Task(void *pvParameters)` in `USER/main.c:177`, with period `pdMS_TO_TICKS(5)` at `USER/main.c:180`. That task calls `stabilizer_Task()` every cycle (`USER/main.c:189`), and `stabilizer_Task()` executes the fixed stage order:

1. `Check_Fly_Mode()` (`TASK/StabilizerTask.c:78`)  
2. `Update_Data()` (`TASK/StabilizerTask.c:80`)  
3. `Compute_Motor()` (`TASK/StabilizerTask.c:82`)  
4. `Update_Motor()` (`TASK/StabilizerTask.c:84`)

## Key Function Signatures

- `void stabilizer_Task(void)` (`TASK/StabilizerTask.c:76`)
- `void Update_Data(void)` (`TASK/StabilizerTask.c:95`)
- `void Compute_Motor(void)` (`TASK/StabilizerTask.c:237`)
- `void Update_Motor(void)` (`TASK/StabilizerTask.c:168`)
- `void Update_Des(unsigned char which_level)` (`TASK/StabilizerTask.c:361`)
- `float Constrain_Float(float amt, float low, float high)` (`TASK/StabilizerTask.c:491`)

## Inner Loop and MRAC Path

PID loops are layered by axis and rate:
- Angle loops: `Ctrler.pitchPID`, `Ctrler.rollPID`, `Ctrler.yawPID` (`TASK/StabilizerTask.c:270-275`)
- Rate loops: `Ctrler.gyroxPID`, `Ctrler.gyroyPID`, `Ctrler.gyrozPID` (`TASK/StabilizerTask.c:280-282`)
- Vertical and XY loops: `Ctrler.Z_posPID`, `Ctrler.Z_ratePID`, `Ctrler.locxPID`, `Ctrler.locyPID`, `Ctrler.locxsPID`, `Ctrler.locysPID` (`TASK/StabilizerTask.c:245-265`)

MRAC is invoked after nominal PID outputs are available: `MRAC_Control(&Ctrler)` at `TASK/StabilizerTask.c:286`. Injection behavior is compile-time gated by `ENABLE_MRAC_OUTPUT_INJECTION` (`TASK/StabilizerTask.c:293`):
- Enabled: `u_total = u_nom + u_ad * mrac_to_mixer` and NaN/Inf is forced to zero (`TASK/StabilizerTask.c:299-311`)
- Disabled: pure PID shadow mode (`TASK/StabilizerTask.c:312-319`)

## Virtual RC Gating and Safety

Effective stick readers (`eff_rc_thr/pit/rol/yaw`) choose between SBUS and host sticks using `sbus_lost` (`TASK/StabilizerTask.c:27-44`). The exact command acceptance condition is enforced in `send_data.c` as `if (sbus_lost == 1 && DroneStatus.FlyMode == FlyMode_SDK && idx < 4)` (`TASK/send_data.c:525`), and this task consumes those values through `virtual_rc_sticks[]`.

Motor output gating is in `Update_Motor()`:
- Only armed path runs when `DroneStatus.ARM_Status==Armed` (`TASK/StabilizerTask.c:170`)
- SDK mode checks altitude + throttle and may force `Set_IDLE_Motors()` (`TASK/StabilizerTask.c:173-186`)
- Any non-SDK or dangerous-stop branch sets zero motors and disarms (`TASK/StabilizerTask.c:188-197`)

## Motor Hand-off and Global Inputs

Mixer writes occur in `Compute_Motor()` as `mymotor.motor1..motor4` (`TASK/StabilizerTask.c:333-351`) and are pushed by `Set_PWM_Motors()` in `Update_Motor()`. Main globals read include:
- `imu_data` (from `API/imu_update.c`, declared as `_imu_st imu_data` in `API/imu_update.c:11`)
- `Ctrler`, `DroneStatus`, `Remoter`, `sbus_lost`, `virtual_rc_sticks`, `TWC` (declared through project headers including `Global_file/global_declare.h`)

Timing invariant: this control loop runs every 5 ms (`USER/main.c:180`), which matches the `0.005f` increments used in state derivatives inside this module (`TASK/StabilizerTask.c:107-147`).

## Edge Cases and Defensive Behavior

Several defensive branches are embedded directly in this control task:

- **Adaptive NaN containment**  
  Each MRAC correction term is validated with `isfinite` before injection (`TASK/StabilizerTask.c:303-306`). Invalid terms are zeroed, preventing propagation into motor outputs.

- **Throttle safety envelope from ground station limits**  
  `Throttle_out` is constrained using runtime `gs_throttle_min_pct` / `gs_throttle_max_pct` (`TASK/StabilizerTask.c:321-329`), which are set by host CMD `0x03` indices 8 and 9 (`TASK/send_data.c:548-552`).

- **TWC arrival observability**  
  Arrival condition is computed from Euclidean distance and exported via `TWC_arrived` (`TASK/StabilizerTask.c:373-381`), enabling host-side mission state UI without reading internal controller states.

## Cross-Module Contracts

Stabilizer correctness depends on these external contracts staying aligned:
- `virtual_rc_sticks[]` index ordering (`TASK/StabilizerTask.c:29`, `TASK/send_data.c:522-527`)
- Motor channel mapping in `pwm.h` (`BSP/pwm.h:8-11`)
- 5 ms loop period assumed by derivative and path-coupled computations (`USER/main.c:180`, `TASK/StabilizerTask.c:145`)

Any refactor touching one of these contracts should be mirrored in the other modules immediately to avoid sign inversions, authority loss, or unstable response.

## Evidence vs Inference

Evidence-backed:
- Task entry cadence, function call order, mixer equations, MRAC injection toggles, and gating branches are directly anchored in `USER/main.c` and `TASK/StabilizerTask.c`.
- Command-side virtual RC gate is directly anchored in `TASK/send_data.c`.

Inference-labeled:
- “Unstable response” and other failure outcomes are control-theory consequences inferred from sign/channel drift, not replay logs captured in this repository.

## See Also

- [[Control Loop Timing]]
- [[Motor Mixer]]
- [[Virtual RC Authority]]
- [[SDK Arming State Machine]]
