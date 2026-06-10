---
title: SDK Arming State Machine
type: concept
tags: [arming, sdk, safety, flymode, flight-phase]
created: 2026-04-14
updated: 2026-05-27
sources: [TASK/RemoterTask.c, TASK/StabilizerTask.c, API/flight_fsm.h, API/flight_fsm.c]
related_files: [TASK/RemoterTask.c, TASK/StabilizerTask.c, API/flight_fsm.h, API/flight_fsm.c]
---

## Two Orthogonal State Variables

| Variable | Type | Owner | Purpose |
|---|---|---|---|
| `FlightState_t` (in `flight_fsm.c`) | DISARMED / ARMED / EMERGENCY | `flight_fsm.c` | Arm/disarm/emergency |
| `flight_phase` (in `flight_fsm.c`) | GROUND_IDLE / FLYING / LANDING / LANDED | RemoterTask + StabilizerTask | Sub-phase within ARMED |

`drone_mode` (old `uint8_t` global) has been removed. `flight_phase` replaces it with a proper FSM.

---

## FlightState Transitions

```
DISARMED → ARM_REQUEST  → ARMED
ARMED    → DISARM_REQUEST → DISARMED
ARMED    → DANGEROUS_STOP → EMERGENCY
EMERGENCY → RECOVER_SDK / DISARM_REQUEST → DISARMED
```

All transitions are under `taskENTER_CRITICAL()`. On any transition to DISARMED, `flight_phase` is automatically reset to `FLIGHT_PHASE_GROUND_IDLE`.

---

## FlightPhase Transitions

```
GROUND_IDLE → FLYING      : Z_posPID.FB > 0.2m (auto-detected in Update_Motor)
FLYING      → LANDING     : ch5 rising edge > 1300 (Check_Fly_Mode — ONLY from FLYING)
LANDING     → LANDED      : |Z_ratePID.FB| < 0.02 m/s for 50 ticks (0.25s at 200Hz)
                             OR ramp fully expired (s_land_thr ≤ 2000)
LANDED      → DISARMED    : auto FlightFSM_Event(DISARM_REQUEST) → resets to GROUND_IDLE
```

**ch5 in LAND position while GROUND_IDLE → ignored (Option A).** LAND only valid from FLYING.

---

## IDLE Motor Gate (Update_Motor)

```c
if (flight_phase == FLIGHT_PHASE_GROUND_IDLE &&
    !TWC.execute &&
    RCInput_Get(RC_AXIS_THR) < 0.2f)
    Set_IDLE_Motors();
else if (SDK_DelayWakeFlag == 1)
    Set_IDLE_Motors();
else
    Set_PWM_Motors();
```

No altitude threshold. The `GROUND_IDLE` state eliminates the threshold-noise class of bugs. Once in `FLYING`, `Set_PWM_Motors()` is always called regardless of THR — PID holds altitude.

---

## Authority Model

Authority is **NOT** set by ch5. Only three sources set authority:
- `CMD 0x0E` from GS → `RCInput_SetAuthority(1)` — VRC / policy mode
- `ch8 rising edge` (PATH_EXEC_CH) → `RCInput_SetAuthority(1)` — preset path
- Physical takeover detector (rate-of-change > RC_PHYSICAL_RATE_DELTA) → `RCInput_SetAuthority(0)`
- Heartbeat watchdog (500ms without CMD 0x06) → `RCInput_SetAuthority(0)`

**Physical takeover is always active**, including during policy execution. Moving any stick beyond the rate threshold immediately snaps authority back to 0.

---

## Arm Gesture

`Check_Stick_Motion()` reads physical `Remoter.*` directly (not `RCInput_Get`). No `drone_mode` or `flight_phase` guard on arm gesture — arming from any phase is safe because:
- ch5 LAND while GROUND_IDLE → LAND event ignored
- ch5 LAND while FLYING → LAND ramp starts, then LANDED auto-disarms

---

## LAND Ramp

- Step: `LAND_THR_RAMP_STEP = 0.5f` per tick at 200Hz = 100 PWM/s, ~9.5s from hover
- Snapshot capped at `Throttle_th` (2950) to prevent PID windup spike
- TWC.execute cleared on LANDING entry
- Terminates via LANDED detection (altitude rate) OR ramp expiry

---

**Confidence:** implemented (2026-05-27), reflash pending.
**Tags:** #arming #idle #land #authority #flight-phase #state-machine
