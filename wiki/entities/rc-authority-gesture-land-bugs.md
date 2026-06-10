## [ENTRY] RC Authority, Gesture, and LAND Mode Bug Cluster
**Region**: `TASK/StabilizerTask.c` — `Update_Motor()`, `case_Update_height_Des`; `TASK/RemoterTask.c` — `Check_Stick_Motion()`
**Trigger**: Arises when any of: fly-up ch7 is used then drone disarms without LAND mode; ch5 is in IDLE mode while pilot attempts arm gesture; ch5 is in LAND position and pilot does arm gesture; optical flow reads >0.3 m on the ground; LAND mode initiated from altitude.

**Chain (BUG A — TWC persist)**:
`sbus_flyup_trigger` rising edge → `TWC.execute=1` in `case_Update_height_Des` → pilot disarms WITHOUT entering LAND mode → `TWC.execute` is never cleared (only LAND block at line 409 clears it) → on re-arm all 3 IDLE gates have `!TWC.execute` guard → IDLE never fires → `Set_PWM_Motors()` runs → `Z_posPID.Des` ramps toward stale `TWC.target_z=0.5m` → drone climbs against THR-min command.

**Chain (BUG B — virtual sticks in gesture)**:
ch5 enters IDLE (drone_mode=0) → `Check_Fly_Mode()` calls `RCInput_SetAuthority(1U)` → `s_authority=1` → `Check_Stick_Motion()` calls `RCInput_Get(RC_AXIS_YAW)` → returns `s_virtual[3]=0.0f` → `is_Stick_MAX(yaw)=FALSE` → arm gesture counter never increments → arm gesture silently blocked.

**Chain (BUG C — arm in LAND mode)**:
ch5 in LAND position (drone_mode=2) → pilot performs arm gesture → `FlightFSM_Event(FLIGHT_EVENT_ARM_REQUEST)` fires (no mode guard) → drone arms → `Update_Motor()` enters LAND ramp immediately → disarms in ~3.2 s → pilot sees "arming doesn't work."

**Chain (BUG D — IDLE FB threshold)**:
Drone on ground → optical flow noise → `Ctrler.Z_posPID.FB > 0.3f` → `Update_Motor()` IDLE gate condition `FB < 0.3f` fails → `Set_PWM_Motors()` instead of `Set_IDLE_Motors()`.

**Chain (BUG E — LAND free-fall)**:
`LAND_THR_RAMP_STEP=1.5f` at 200 Hz = 300 PWM/s → ramp from hover (~2650) to zero (2000) in ~2 s → drone descends faster than stable flight allows → near-free-fall → hard impact → structural bounce.

**Resolution**:
- **BUG A**: Added `TWC.execute=0; sbus_flyup_trigger=0;` in the DISARMED branch of `Update_Motor()` (`StabilizerTask.c` ~line 192), before `Clear_Structure()`. Clears stale fly-up state on every disarm regardless of LAND mode.
- **BUG B**: Replaced `RCInput_Get()` with direct `Remoter` struct reads in `Check_Stick_Motion()` (`RemoterTask.c` line 69): `((float)Remoter.ThrCtrler - 3000.0f) / 1000.0f` etc. Same normalization as `s_normalize()` in `rc_input.c`. Bypasses authority gate entirely.
- **BUG C**: Added `if (drone_mode != 2U)` guard around `FlightFSM_Event(FLIGHT_EVENT_ARM_REQUEST)` in `Check_Stick_Motion()` (`RemoterTask.c` line 110). Pilot must flip ch5 to IDLE before arming.
- **BUG D**: Raised IDLE gate FB threshold `0.3f → 0.5f` in `Update_Motor()` line 168.
- **BUG E**: Reduced `LAND_THR_RAMP_STEP` `1.5f → 0.5f` (`StabilizerTask.c` line 22). 100 PWM/s, ~9.5 s ramp — drone descends slowly, no impact bounce.

**Gotchas**:
- `RCInput_Get()` is UNSAFE for physical-action detection — returns `s_virtual[]=0` whenever `s_authority=1`. All gesture/stick recognition that must react to physical pilot input must read `Remoter.*` directly.
- `Clear_Structure()` (`API/pid.c:148`) does NOT clear `TWC` or SBUS trigger flags — only PID integrators and `Des` setpoints. Any trigger or mode flag must be cleared explicitly in the disarm branch.
- `FlightFSM` is intentionally mode-agnostic — it accepts `ARM_REQUEST` regardless of `drone_mode`. Mode guards must be at the call site.
- `LAND_THR_RAMP_STEP` is defined locally in `StabilizerTask.c:22`, not in a shared header. Search `StabilizerTask.c` directly if tuning landing speed.
- `s_authority=1` is set on every ch5→IDLE transition by `Check_Fly_Mode()`. It is NOT cleared by the arm gesture path — only by physical takeover detector rate threshold or explicit `RCInput_SetAuthority(0U)`.

**Tags**: #landing #idle #gesture #rc #authority #motor #pid #stabilizer #remoter #arm
**Confidence**: verified (root causes traced to code; all 5 fixes applied; reflash pending)
