---
title: SDK Arming State Machine
type: concept
tags: [arming, sdk, safety, flymode]
created: 2026-04-14
updated: 2026-04-14
sources: [TASK/RemoterTask.c, TASK/send_data.c, TASK/StabilizerTask.c, TASK/AutoflyTask.c]
related_files: [TASK/RemoterTask.c, TASK/send_data.c, TASK/StabilizerTask.c, TASK/AutoflyTask.c]
---

The firmware uses a hybrid arming flow: stick-based arming logic remains active, but ground station can assert arming intent via command `0x0E` in SDK workflows. The practical state progression is `DISARMED -> ARMED` with mode guards and forced-disarm exits; there is no standalone enum for ARMING state, but counters/flags implement equivalent timing transitions.

## Inputs and Transition Signals

Primary arm signals:
- Stick gesture detector `Check_Stick_Motion()` (`TASK/RemoterTask.c:61`)
- GS arm request `CMD 0x0E` (`TASK/send_data.c:662-673`)
- SDK mission trigger flags (`GS_KeySDKflag`, `KeySDKflag`) (`TASK/send_data.c:666`, `TASK/AutoflyTask.c:119,126`)

Threshold timing constants:
- `ARM_Delay_time 150` and `DISARM_Delay_time 50` (`Global_file/global_declare.h:32-33`)
- At 100 Hz remoter task (`USER/main.c:203`), arm hold is ~1.5 s and disarm hold is ~0.5 s.

## State Interpretation

- **DISARMED**: `DroneStatus.ARM_Status = DisArmed` (`Global_file/global_declare.h:34`)
- **ARMING** (implicit): stick counter rising toward threshold (`TASK/RemoterTask.c:68-70,103`)
- **ARMED**: set by stick threshold or CMD `0x0E` (`TASK/RemoterTask.c:105`, `TASK/send_data.c:667`)
- **FORCED DISARM**: dangerous-stop or invalid mode branches clear motors and set disarmed (`TASK/StabilizerTask.c:188-197`)

## Motor Enable Sequence

Arming status alone does not guarantee full motor PWM. `Update_Motor()` applies layered guards:
- Must be armed (`TASK/StabilizerTask.c:170`)
- Must be in `FlyMode_SDK` to reach PWM branch (`TASK/StabilizerTask.c:173`)
- Near-ground + low-throttle uses `Set_IDLE_Motors()` instead of full PWM (`TASK/StabilizerTask.c:175-178`)
- `SDK_DelayWakeFlag` also holds idle (`TASK/StabilizerTask.c:179-182`)

Only after these guards pass does `Set_PWM_Motors()` run (`TASK/StabilizerTask.c:185`).

## Disarm Conditions

Disarm is triggered by:
- Left-down stick hold (`TASK/RemoterTask.c:72-74,109-113`)
- Ground station arm clear (`CMD 0x0E` value 0) (`TASK/send_data.c:668-671`)
- Dangerous stop mode or non-SDK branch in `Update_Motor` (`TASK/StabilizerTask.c:188-197`)
- Land-complete in SDK state machine (`TASK/AutoflyTask.c:258-264`)

SBUS regain does not forcibly disarm by itself; it revokes virtual-stick authority via `sbus_lost` transitions, which can indirectly alter mission/arming behavior.

## FlyMode Coupling

Arming is functionally useful only in `FlyMode_SDK` (`Global_file/global_declare.h:30`) because motor update path rejects other modes and forces zero/disarm (`TASK/StabilizerTask.c:193-197`). `Check_Fly_Mode()` currently maps channel-based dangerous-stop vs SDK (`TASK/RemoterTask.c:120-143`), so FlyMode acts as a hard gate around arming outputs.

## Operational Transition Table

Observed transition behavior from code:

- `DISARMED -> ARMED`  
  Trigger A: right-down stick hold reaches `ARM_Delay_time` (`TASK/RemoterTask.c:68-70,103-106`)  
  Trigger B: GS command `0x0E idx0 val!=0` sets armed immediately (`TASK/send_data.c:664-667`)

- `ARMED -> DISARMED`  
  Trigger A: left-down stick hold reaches `DISARM_Delay_time` (`TASK/RemoterTask.c:72-74,109-112`)  
  Trigger B: GS command `0x0E idx0 val==0` — revokes authority only (drone stays ARMED); pilot disarms via RC gesture  
  Trigger C: Dangerous stop / non-SDK path in motor updater (`TASK/StabilizerTask.c:188-197`)  
  Trigger D: SDK land completion (`TASK/AutoflyTask.c:258-264`)

## Physical RC Prerequisite

`Check_Fly_Mode()` reads `sbus_channel[9]` at 100 Hz. If the RC mode switch is never HIGH, `DangerousStop_cnt` immediately exceeds 10 → `DANGEROUS_STOP` fires continuously → FSM never leaves EMERGENCY → FlyMode_DangerousStop always.

**The physical RC mode switch must be HIGH before arming.** Once a valid SBUS frame with channel[9] > 500 has been decoded, the value is held in `sbus_channel[9]` even if SBUS is later lost, so a brief SBUS dropout does not kill the mode.

## Authority Handover on Arm

CMD `0x0E` arm (`send_data.c:694-695`) calls both `FlightFSM_Event(ARM_REQUEST)` and `RCInput_SetAuthority(1)`. After this:
- Physical RC sticks are suspended from the control loop
- PC sliders (CMD `0x06`) are accepted and routed by `RCInput_Get()`
- RC mode switch still works as hard kill (operates on FlyMode, not authority)

CMD `0x0E` disarm (`send_data.c:698-701`) calls `RCInput_SetAuthority(0)` only. Physical RC resumes immediately; drone stays ARMED so the pilot can land safely. `FlightFSM_Event(DISARM_REQUEST)` is NOT sent — calling it mid-air cuts motors.

## Ambiguities Worth Tracking

Two implementation details can surprise operators:

1. **No explicit hold-time on GS arm request**  
   GS arm command is immediate (`send_data.c:694`), unlike stick arming which is delay-gated at `ARM_Delay_time = 150` cycles.

2. **Arm and mode are split authorities**  
   Arming can be set while mode later flips to dangerous stop via RC channel (`TASK/RemoterTask.c:125-143`), causing immediate zero/disarm on next motor update cycle. This is intentional: RC kill switch overrides everything.

3. **Authority is not cleared by DANGEROUS_STOP**  
   If the RC mode switch is flipped LOW (kill) then back HIGH, the FSM recovers to DISARMED but `s_authority` remains 1 until the GS clicks [ARM REQ OFF] or re-sends CMD `0x0E val=0`. Motors stay stopped (FSM DISARMED) but a new SDK ARM REQ restores full VRC without needing to reset authority.

## See Also

- [[Virtual RC Authority]]
- [[StabilizerTask]]
- [[Motor Mixer]]
