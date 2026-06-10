## [ENTRY] LAND Ramp Spike and IDLE Authority Gate
**Region**: `TASK/StabilizerTask.c` — `Update_Motor()`, `case_Update_height_Des`, `case_Update_v_h_Des`
**Trigger**: Arises when testing LAND mode (ch5 high) near the ground (~0.3 m) or when the pilot arms via RC stick gesture and expects to fly manually in IDLE mode (ch5 mid/low).

**Chain (LAND spike)**:
Two-phase LAND design → Stage 1 runs Z PID with Des ramping toward 0 → Z rate PID integrator winds up against ground-effect aerodynamic cushion (natural lift increase below ~0.3 m) → Stage 2 triggers at FB < 0.3 m → `Throttle_out` snapshot is inflated by integrator → motors spike upward before ramp corrects → oscillation as motors wind down.

**Chain (IDLE gate)**:
IDLE gate used `RCInput_GetAuthority()` → after RC arm gesture (no GS involved), `s_authority = 0` → physical-RC takeover detector fired when pilot released gesture stick (rate-of-change of THR from −1.0 to 0.0 exceeded `RC_PHYSICAL_RATE_DELTA = 0.05/tick` after 100 ms grace) → authority never set by RC gesture path → all three IDLE gates permanently blocked → drone hovers or runs PID instead of holding ground idle.

**Resolution**:
- **LAND**: Collapsed two-phase to single-phase. `case_Update_height_Des` LAND block sets `Des = FB` immediately (Z PID error → 0, `Throttle_out ≈ Throttle_th ≈ 2950`). `Update_Motor` LAND branch starts direct throttle ramp at any altitude without waiting for 0.3 m; snapshot capped at `Throttle_th` so PID integrator windup cannot inflate ramp start.
- **IDLE**: Replaced `RCInput_GetAuthority()` with `RCInput_Get(RC_AXIS_THR) < 0.2f` in three locations (`Update_Motor` IDLE gate, `case_Update_height_Des` IDLE gate, `case_Update_v_h_Des` IDLE gate). THR at stick center (0.0) and GS virtual THR (−1.0) both satisfy < 0.2 → IDLE fires. Pilot pushes above 0.2 to escape IDLE and fly.

**Gotchas**:
- `RC_IDLE_THR_THRESHOLD = -0.85f` (defined in `API/rc_input.h`). The second IDLE check in `Update_Motor` (`FB < 0.3 m && THR < −0.85`) was **not** the bug — it only fires when throttle is nearly at minimum. Misleading when tracing IDLE failures.
- `Throttle_th` is declared `short` with default 2200 but set to 2950 every cycle in `Compute_Motor()`. Cast to `float` required in the cap comparison: `if (s_land_thr > (float)Throttle_th)`.
- Execution order matters: `Compute_Motor()` → `Update_Motor()` within `stabilizer_Task()`. The `Des = FB` freeze in `case_Update_height_Des` must happen first so `Throttle_out` is stable when `Update_Motor` snapshots it.
- The physical-RC takeover detector has a 100 ms grace period (`RC_AUTHORITY_GRACE_TICKS = 10` at 10 ms/tick) after authority is granted. This grace is irrelevant for arm-gesture arming because authority is never granted by that path.

**Tags**: #landing #idle #motor #pid #authority #rc #ground-effect #stabilizer
**Confidence**: verified (root cause traced to code; fix applied; reflash pending)
