## [ENTRY] Emergency stick takeover during path modes

**Region**: `API/rc_input.c` (`RCInput_Update`), `TASK/AutoflyTask.c` (`AutoflyTask_PathArbitrate`)

**Trigger**: A path preset (sinusoid/circle/figure-8/TWC) is running after the drone was **armed from the dashboard** (CMD 0x0E), and the pilot tries to grab the physical RC sticks for an emergency manual intervention.

**Chain**: Dashboard arm (CMD 0x0E, `send_data.c:773`) sets `GS_KeySDKflag=1` AND `RCInput_SetAuthority(1)` → `RCInput_Update` rate-of-change takeover branch was gated `if (!GS_KeySDKflag && !s_heartbeat_active && !sbus_lost)`, so `GS_KeySDKflag=1` permanently suppressed it → meanwhile `authority=1` makes `RCInput_Get` return centered virtual sticks → physical sticks fully ignored for the entire SDK session; only the ch10 motor-cut (`DANGEROUS_STOP`) still worked. (Paths armed via SBUS **ch8** leave `GS_KeySDKflag=0`, so takeover still worked there — the bug was dashboard-specific.)

**Resolution**: (1) `RCInput_Update` takeover ungated to `if (!sbus_lost)` so the emergency override is always live during GS-controlled flight; `GS_KeySDKflag` is cleared on takeover. (2) `AutoflyTask_PathArbitrate` now stops **all** presets when `RCInput_GetAuthority()==0` (added `#include "rc_input.h"`), giving a clean handoff to manual alt/position-hold. ch10 `DANGEROUS_STOP` hard kill left untouched as the independent second emergency layer. Firmware rebuilt 0/0. Verified by code trace; needs reflash + flight test.

**Gotchas**:
- `GroundStation_AbortAllPaths()` (`send_data.c:473`) itself fires `DANGEROUS_STOP` (motor cut) — must NOT be reused for a *graceful* takeover.
- Firmware presets in `AutoflyTask.c` were gated only on `FlyMode==SDK`, never on authority — they keep writing `Ctrler.*PID.Des` even after authority drops, so they fight the pilot unless explicitly stopped.
- All legitimate path executions (GS arm and SBUS ch8) set `authority=1`, so gating presets on authority is a safe invariant.
- The takeover requires a valid SBUS link; if `sbus_lost`, physical readings are stale and takeover cannot engage (heartbeat watchdog + ch10 still apply).

**Tags**: #rc-authority #safety #autofly #path-mode #firmware

**Confidence**: simulated
