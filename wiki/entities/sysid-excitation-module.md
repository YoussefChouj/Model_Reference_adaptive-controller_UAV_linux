## [ENTRY] SysID excitation module and 0x03 ID frame

**Region**: `API/sysid.c` (+ `TASK/send_data.c`, `TASK/StabilizerTask.c`, GS `serial_bridge.py`/`dashboard.py`)

**Trigger**: Working on automated inner-loop system identification — excitation injection, the high-rate ID telemetry frame, the offline Bode/coherence pipeline, or anything that touches the 0x03 frame byte layout.

**Chain**: Dashboard System ID tab ([dashboard.py:2909](../../ground_station/gui/dashboard.py#L2909)) → CMD `0x14` idx 0–5 set params, idx 6 start/abort → handler [send_data.c ~824](../../TASK/send_data.c) calls `SysID_Start()` → FSM in [sysid.c](../../API/sysid.c) ticked from `SysID_Update()` → `SysID_IsAxisActive()`/`SysID_GetRateSetpoint()` override `gyro*.Des` at [StabilizerTask.c:305-311](../../TASK/StabilizerTask.c#L305-L311) (outer angle loop bypassed on the test axis only) → plant response logged in the 0x03 ID frame → offline `sysid_analysis.py` recovers `x/u` & `x/r` Bode.

**Resolution**: Feature completed/verified 2026-06-16.
- **FSM** `{IDLE=0, RAMP_IN=1, RUNNING=2, RAMP_OUT=3, RECOVERY=4}` in `sysid.c` — **no PRECHECK state** (gates run synchronously inside `SysID_Start`). `SysID_GetState()` at sysid.c:247.
- **0x03 ID frame = 91 bytes** (was 90): `u32 sample_counter | 4 axes×{r,x,u_nom,u_ad,xm} f32 | f32 vbat | u8 ARM | u8 FlyMode | u8 SysID-state`. Emitted at **100 Hz** (`frame_counter % 5` in [send_data.c:349](../../TASK/send_data.c#L349)). Parsed in [serial_bridge.py:644 `_unpack_frame_id`](../../ground_station/comm/serial_bridge.py#L644) as `id.*` keys incl. `id.sysid_state`; `GS_PROTO_VERSION=4`.
- **Offline pipeline**: [ground_station/scripts/sysid_analysis.py](../../ground_station/scripts/sysid_analysis.py) — Bode `x/u` & `x/r` (Welch/CSD), coherence gate, −3 dB BW → `ref_model_bw`, least-squares `J·ẋ+b·x=u`. Reads logs via `analyze_flight_log.load_flight_data` (long-form CSV `t_s,frame,key,value`).
- **Inner-loop MRAC** (ADR-0003) verified clean in [mrac.c](../../API/mrac.c): `P=1/(2·ω_ref)`, `grad=-P·B·e·Φ/denom`, leakage σ **not** divided by `denom` (`FIX_LEAKAGE_NORMALIZATION=1`), shadow-mode `mrac_flags.output_injection_on` defaults 0 in `MRAC_Init`.

**Gotchas**:
- **Z-axis SysID is rejected** in `SysID_Start` — there is no `Z_ratePID.Des` injection site (StabilizerTask only injects P/R/Y), so a Z run was a silent no-op (passed checks, computed a setpoint, moved nothing). Full Z wiring needs its own injection point + altitude/ground-effect aborts.
- **Frame-byte-count must stay consistent across 3 layers**: firmware `payload_len`, serial_bridge `len(payload)==91` check, and the unpacker offsets. Bump `GS_PROTO_VERSION` (firmware `global_declare.h` + `serial_bridge.py`) on any layout change.
- **ADR-0004 doc drift**: says 200 Hz (really 100 Hz), describes a PRECHECK state (none exists), says manual abort = CMD `0x0D` (actually `0x14` idx6).
- **Deferred safety gates**: `sysid_abort_condition()` lacks battery-low / telemetry-stale / saturation aborts — no `bat_warn`/`of_valid` symbols exist in firmware; and only the soft ±0.5 m green-zone boundary exists (no hard ±0.7 m descent). RC dead-man is the only backstop until added.
- `0x14` start self-resets the OF origin (mirrors the `0x10` handler) so it no longer depends on the GS sending `0x10` first.

**Tags**: #firmware #sysid #mrac #telemetry #protocol #ground-station
**Confidence**: verified
