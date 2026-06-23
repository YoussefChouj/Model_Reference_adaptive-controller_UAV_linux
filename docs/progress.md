# Session Progress Log

## Sessions

### 2026-06-15 — Emergency Physical-Stick Takeover During Path Modes

- **Goal**: Fix the bug where the drone ignores physical RC stick movement (needed for emergency intervention) while executing a dashboard-armed path mode.
- **Completed**: Root-caused and fixed. Dashboard arm (CMD 0x0E) sets `GS_KeySDKflag=1` + authority=1, which permanently suppressed the rate-of-change physical-stick takeover in `RCInput_Update`. Ungated that takeover (now only `!sbus_lost`), cleared `GS_KeySDKflag` on takeover, and added authority gating to `AutoflyTask_PathArbitrate()` so all presets stop when authority drops (clean handoff to manual alt/position-hold). ch10 `DANGEROUS_STOP` hard kill left intact. Firmware rebuilt: 0 Errors, 0 Warnings.
- **Blocked**: Nothing. Verified by code trace only — no flight test. Reflash pending.
- **Changed**: `API/rc_input.c` (ungate takeover condition + clear `GS_KeySDKflag`), `TASK/AutoflyTask.c` (`#include "rc_input.h"` + authority-gated path arbitration), rebuilt `OBJ/JX_FLY.{axf,hex}`.
- **Next**: Reflash `OBJ/JX_FLY.hex`; flight-test fast stick deflection during a path run → confirm path stops + manual control resumes without motor cut. Optionally document in `wiki/concepts/virtual-rc-authority.md`.

### 2026-04-10 - VOFA Stream Isolation Fix

- **Goal**: Fix VOFA+ context contamination between Frame A (port 1347) and Frame B (port 1348) so each button loads its own independent channel names and tab layout.
- **Completed**: Rewrote `_open_plot` in `dashboard.py` to use a simple preset-copy approach (kill VOFA → copy stream preset → patch port → launch); created `presets/vofa/stream_a/` and `stream_b/` with correct config and tabviews files; 13 A channels and 75 B channels verified correct; syntax clean.
- **Blocked**: `vofa+.tabviews.json` files in `stream_a/` and `stream_b/` are placeholder copies — tabs are not yet organized per the checklist; agent prompt was generated for next step.
- **Changed**: `ground_station/gui/dashboard.py` (`_open_plot` rewritten, `_capture_vofa_stream_preset` added), `presets/vofa/stream_a/vofa+.config.json`, `presets/vofa/stream_a/vofa+.tabviews.json`, `presets/vofa/stream_b/vofa+.config.json`, `presets/vofa/stream_b/vofa+.tabviews.json`, `presets/vofa/README.md`.
- **Next**: Run the agent prompt (provided at end of session) to generate correct `vofa+.tabviews.json` for both streams, then test: click Frame A → verify 13 channels + 3 tabs; click Frame B → verify 75 channels + 10 tabs; no cross-contamination.

### 2026-05-25 — Full 5-Bug Fix (LAND + IDLE + TWC + Gesture + Ramp)

- **Goal**: Fix 5 confirmed flight bugs found after previous LAND/IDLE fixes: TWC.execute persistence causing re-arm climb, gesture detection using virtual sticks, arm gesture working in LAND mode, IDLE FB threshold too tight, LAND ramp causing free-fall bounce.
- **Completed**: All 5 bugs fixed. (A) `TWC.execute=0` + `sbus_flyup_trigger=0` added to disarm branch in `Update_Motor()`. (B) `Check_Stick_Motion()` now reads `Remoter.ThrCtrler/PitCtrler/RolCtrler/YawCtrler` directly (normalized `(raw-3000)/1000`) instead of `RCInput_Get()` which returns virtual=0 when authority=1. (C) Arm gesture guarded with `if (drone_mode != 2U)`. (D) IDLE FB threshold raised 0.3→0.5 m. (E) `LAND_THR_RAMP_STEP` reduced 1.5→0.5 (100 PWM/s, ~9.5 s ramp).
- **Blocked**: Requires Keil5 rebuild + reflash.
- **Changed**: `TASK/StabilizerTask.c` (3 edits: disarm branch, IDLE threshold, ramp step), `TASK/RemoterTask.c` (2 edits: gesture physical sticks, arm mode guard).
- **Next**: Rebuild + reflash. Flight test: arm with ch5 IDLE → IDLE motors → THR>0.2 flies; fly-up + disarm without LAND → re-arm still gets IDLE; LAND from 1m → slow smooth descent, no bounce; arm gesture with ch5 in LAND position → gesture ignored (must flip to IDLE first).

### 2026-05-25 — LAND Spike Fix + IDLE Gate Repair

- **Goal**: Fix LAND mode motor spike at ~0.3 m altitude transition and fix IDLE mode never engaging after RC arm gesture.
- **Completed**: (1) Collapsed two-phase LAND into single-phase direct throttle ramp — snapshot capped at `Throttle_th` (2950) to prevent PID integrator windup inflation; `case_Update_height_Des` LAND block simplified to `Des = FB` immediately. (2) Replaced `RCInput_GetAuthority()` with `RCInput_Get(RC_AXIS_THR) < 0.2f` in three IDLE gate locations so IDLE fires on throttle position, not authority state.
- **Blocked**: Nothing — requires Keil5 rebuild + reflash before flight test.
- **Changed**: `TASK/StabilizerTask.c` — 5 edits: `Update_Motor` LAND branch (single-phase), `Update_Motor` IDLE gate, `case_Update_height_Des` LAND block, `case_Update_height_Des` IDLE gate, `case_Update_v_h_Des` IDLE gate.
- **Next**: Rebuild + reflash. Test LAND from 1 m (smooth ramp, no spike). Test IDLE: RC arm gesture → THR at center holds ground; push THR > 0.2 to fly.

### 2026-04-10 - Free Model Routing System

- **Goal**: Build a token-saving system that offloads subtasks to free OpenRouter models.
- **Completed**: Created 5 global skills (`/free`, `/free-review`, `/free-translate`, `/free-reason`, `/update-models`) and `~/.claude/openrouter_models.json` registry with 6 task types; ran live model discovery and ping-tested all primaries.
- **Blocked**: `qwen/qwen3-coder:free` and `z-ai/glm-4.5-air:free` hit provider-side 429 burst limits during testing; they remain as fallbacks and recover within minutes.
- **Changed**: `~/.claude/openrouter_models.json` (new), `~/.claude/skills/free*/SKILL.md` (5 new skills), `CLAUDE.md` (Free Model Routing section added).
- **Next**: Set `OPENROUTER_API_KEY` in environment; run `/free-review` on a real file to confirm end-to-end; run `/update-models` weekly to rotate deprecated models.

## 2026-06-16 — Finish sysid + inner-loop MRAC

- **Goal:** Complete the in-progress inner-loop MRAC + automated system-ID excitation work (ADR-0003/0004 Phase 1–4): audit/fix firmware, build the offline ID pipeline, close dashboard/protocol gaps.
- **Completed:** Firmware audit (3 parallel agents) — MRAC core, leakage, gyro_filter, P/R/Y bypass, FSM all verified clean. Fixed Z-axis silent no-op (now rejected in `SysID_Start`) and made `0x14` start self-reset the OF origin. Wrote `sysid_analysis.py` (Bode x/u & x/r, coherence gate, BW→ref_model_bw, J·ẋ+b·x=u). Added live FSM-state display (firmware 0x03 frame 90→91 B, GS_PROTO_VERSION 3→4, parsed + colour-coded in dashboard). Documented CMD 0x14; verified packing byte-for-byte.
- **Blocked/deferred:** Keil/ARMCC V5.06 build NOT run (no CLI toolchain here — verify in uVision). Deferred safety gates: battery-low / telemetry-stale / saturation aborts + hard ±0.7 m boundary (need threshold symbols). Full Z excitation wiring deferred.
- **Files changed:** `API/sysid.c`, `TASK/send_data.c`, `Global_file/global_declare.h`, `ground_station/comm/serial_bridge.py`, `ground_station/gui/dashboard.py`, `ground_station/scripts/sysid_analysis.py` (new), `CLAUDE.md`, `docs/progress.md`.
- **Next session:** Build in uVision; implement deferred SysID safety gates before any output-injection-ON flight; optionally amend ADR-0004 (100 Hz / PRECHECK / 0x0D drift); run first shadow-mode SysID capture and feed it to `sysid_analysis.py`.
