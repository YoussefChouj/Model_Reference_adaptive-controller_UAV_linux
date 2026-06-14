## [ENTRY] LAND Mode — Pure PID Descent Design

**Region**: `TASK/StabilizerTask.c` — `Update_Motor()`, `case_Update_height_Des`, `case_Update_v_h_Des`
**Trigger**: Arises when testing LAND mode (ch5 high). Prior throttle-ramp approach caused upward spike at entry, bounces at touchdown, and unreliable LANDED detection.

**Final Architecture (pure PID — ArduPilot/PX4 style)**:

Landing is split across three places, each with one responsibility:

1. **`case_Update_height_Des` (LANDING branch)**: Ramps `Z_posPID.Des` down at `LAND_DES_STEP = 0.0015 m/tick` (0.30 m/s at 200 Hz). On entry, snaps `Des = min(Des, FB)` so a setpoint above current altitude cannot pull the drone upward (case A fix). Clamps Des at 0.0f floor.

2. **`case_Update_v_h_Des` (LANDING branch)**: Forces `Z_ratePID.Des = Z_posPID.U` — THR stick is blocked from overriding the PID cascade during landing.

3. **`Update_Motor()` (LANDING branch)**: Calls `Set_PWM_Motors()` — PID drives motors directly, no throttle ramp. During descent the integrator winds negative so `Throttle_out` is already below hover at touchdown. Touchdown detection: `|Z_ratePID.FB| < 0.02 m/s` for 50 ticks (0.25 s) AND `Z_posPID.FB < 0.15 m`. Rate is ≈0.30 m/s during descent and drops to ~0 only on contact, so detection is reliable. Safety net: forced disarm after `LAND_MAX_TICKS = 2000` (10 s).

4. **`Update_Motor()` else branch**: Changed `else` → `else if (FLYING)` so LANDED state does not accidentally call `Set_PWM_Motors()` with a stale high `Throttle_out` (case C micro-jump fix).

**Why not throttle ramp**:
- Ramp start was inflated by PID integrator → upward spike at entry (case A).
- Below-0.20 m fast-ramp still caused bounces because residual thrust was wrong.
- Rate-based LANDED detection was unreliable: drone was hovering at 0 m/s before ramp reached minimum → false fires when not at ground, or slow detection.
- PID descent naturally produces: (a) nonzero rate during flight → reliable touchdown signal; (b) negative integrator at ground → `Throttle_out` below hover when LANDED fires → no spike.

**Gotchas**:
- `case_Update_height_Des` runs at 200 Hz (before `cnt_h` check); `LAND_DES_STEP = 0.0015 m/tick` gives exactly 0.30 m/s.
- `LAND_MAX_TICKS = 2000` is the safety net; normal landings complete via rate detection well before 10 s.
- The LANDED state in `case_Update_height_Des` sets `Des = 0.0f` and is only a one-tick holdover while disarm completes (FlightFSM_Event is synchronous via taskENTER_CRITICAL).
- The physical-RC takeover detector has a 100 ms grace period (`RC_AUTHORITY_GRACE_TICKS = 10` at 10 ms/tick) after authority is granted. This is irrelevant for arm-gesture arming because authority is never granted by that path.

**Tags**: #landing #motor #pid #ground-effect #stabilizer #casea #casec
**Confidence**: verified (all root causes traced to code; fix implemented; reflash pending)
