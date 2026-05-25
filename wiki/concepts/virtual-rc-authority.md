---
title: Virtual RC Authority
type: concept
tags: [safety, sdk-mode, arming, sbus]
created: 2026-04-13
updated: 2026-05-22 (bug fixes: throttle-jump on arm, motor-cut on ARM REQ OFF)
sources: [API/rc_input.c, API/rc_input.h, TASK/send_data.c, TASK/RemoterTask.c, Global_file/global_declare.h]
related_files: [API/rc_input.c, API/rc_input.h, TASK/send_data.c, TASK/RemoterTask.c]
relations:
  - type: safety_critical_for
    target: "[[StabilizerTask]]"
---

Virtual RC is an authority-layer: the PC takes control of all four stick axes when the GS arms via CMD `0x0E`. The physical RC remains ON as the hard kill switch at all times.

> **Design change (2026-05-22):** Authority now routes on `s_authority` flag (set by CMD `0x0E`), NOT on `sbus_lost`. The physical RC no longer needs to be turned off for VRC to work. `sbus_lost` is no longer relevant to VRC operation.

## Authority Routing — `RCInput_Get()`

`RCInput_Get()` (`API/rc_input.c:50`) selects the stick source based on `s_authority`:

```
s_authority == 1  →  virtual sticks from s_virtual[4]   (PC offboard)
s_authority == 0  →  physical RC via Remoter.* structs   (pilot mode)
```

The previous `sbus_lost`-based routing is removed. This allows the physical RC to remain connected and powered as an emergency fallback while the PC controls stick axes.

## How Authority is Set

CMD `0x0E` (`TASK/send_data.c:690-703`) is the sole authority switch:
- `idx=0, val≥0.5` → `FlightFSM_Event(ARM_REQUEST)` + `RCInput_SetAuthority(1)` — arms and grants authority.
- `idx=0, val<0.5`  → `RCInput_SetAuthority(0)` only — revokes authority, drone **stays ARMED**, physical RC resumes immediately. `FlightFSM_Event(DISARM_REQUEST)` is intentionally **not** called, because disarming mid-air cuts motors. The pilot must disarm on the ground via RC stick gesture (left-stick left+down).

`RCInput_SetAuthority(1)` now pre-sets `s_virtual[0] = -1.0f` (minimum throttle) before activating authority. This prevents a throttle jump when the PC takes over from physical RC (whose throttle is at minimum = -1.0f). Pitch/roll/yaw remain at 0.0f (centre is safe).

`RCInput_SetAuthority(0)` zeros all `s_virtual[]` so sticks centre immediately on handback (`API/rc_input.c:115-126`).

## CMD 0x06 Gate (Virtual Stick Injection)

`TASK/send_data.c:524-534`:
```c
if (DroneStatus.FlyMode == FlyMode_SDK && idx < 4)
    RCInput_SetVirtualStick((RC_Axis_t)idx, v);
```

`sbus_lost` is no longer in this gate. The PC can inject sticks while the RC is on, as long as FlyMode is SDK and `s_authority == 1` (which routes them through `RCInput_Get()`).

## Stick Vector Layout

- Ordering: `[thr, pit, rol, yaw]` — `RC_AXIS_THR=0, RC_AXIS_PITCH=1, RC_AXIS_ROLL=2, RC_AXIS_YAW=3`
- Range: normalised `[-1.0, +1.0]`, centre `0.0`

## Physical RC Takeover (any stick, any mode)

`RCInput_Update()` (`API/rc_input.c:152`) runs at 100 Hz (via RemoterTask). On every tick while `s_authority=1`, it reads the live physical RC sticks and compares them against a snapshot taken at the moment authority was granted:

```
if |live_stick − snapshot| > RC_PHYSICAL_TAKEOVER_DELTA (0.20)  →  s_authority = 0
```

All four axes are checked independently (thr, pitch, roll, yaw). The first axis to exceed the threshold wins. Authority is revoked immediately — within one 10 ms cycle — and `RCInput_Get()` switches to physical RC. The drone stays **ARMED and flying**; the pilot's sticks take over seamlessly without a motor cut.

The check is skipped if `sbus_lost = 1` (no valid SBUS data), preventing false triggers from stale Remoter values.

This override fires regardless of which mode is active (VRC slider, sinusoid path, circle path, TWC). Path executors keep sending virtual stick commands, but since `s_authority = 0`, they have no effect on the control loop. Click "Abort All / Return to RC" to stop paths cleanly after taking over.

To re-grant authority to the PC, click [SDK ARM REQ] again — the snapshot resets to the new stick positions.

## Heartbeat Watchdog

When `s_authority == 1`, `RCInput_Update()` also monitors for stale GS commands. If no `RCInput_SetVirtualStick` call arrives within `RC_HEARTBEAT_TIMEOUT_MS = 500 ms`, authority is revoked and all sticks centre. This returns control to the physical RC without cutting motors. The heartbeat check runs **after** the physical-takeover check.

## The Physical RC as Hard Kill Switch

The physical RC's mode switch (channel 10 / `sbus_channel[9]`) is wired directly to `Check_Fly_Mode()` (`TASK/RemoterTask.c:125`), which runs at 100 Hz independently of authority:

```
sbus_channel[9] > 500  →  FLIGHT_EVENT_RECOVER_SDK  →  FlyMode_SDK
sbus_channel[9] ≤ 500  →  FLIGHT_EVENT_DANGEROUS_STOP  →  FlyMode_DangerousStop (after 50 ms)
```

Because `RCInput_Get()` and all path CMDs gate on `FlyMode == FlyMode_SDK`, flipping the mode switch LOW kills all commanded output within one 10 ms task cycle. This is independent of `s_authority` and cannot be bypassed from the GS.

`sbus_channel` values are **held** after SBUS loss — the last decoded frame persists. So the initial SDK-position frame must come from a live RC before authority is taken; after that the RC can remain on or be briefly cycled without the mode switch dropping.

## Operational Flow (RC always on)

```
1. Physical RC ON, mode switch HIGH (>500)
   → Check_Fly_Mode fires RECOVER_SDK → FlyMode = SDK

2. GS clicks [SDK ARM REQ]  (CMD 0x0E idx=0 val=1.0)
   → s_authority = 1, FlightFSM → ARMED

3. GS sends CMD 0x06 slider updates
   → RCInput_SetVirtualStick() stores values
   → RCInput_Get() returns virtual sticks (s_authority=1)
   → Control loop follows PC commands

4. Emergency: RC mode switch → LOW
   → DANGEROUS_STOP → FlyMode = DangerousStop → motors cut
   → Completely independent of s_authority

5. GS clicks [ARM REQ OFF]  (CMD 0x0E idx=0 val=0.0)
   → s_authority = 0, sticks zeroed — drone stays ARMED
   → RCInput_Get() returns physical RC sticks immediately
   → Pilot lands normally, then disarms via RC stick gesture
```

## See Also

- [[Path Arbitration]]
- [[SDK Arming State Machine]]
- [[Ground-Station Binary Protocol]]
- [[StabilizerTask]]
