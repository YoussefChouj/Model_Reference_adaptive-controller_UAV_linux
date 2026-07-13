# Trajectory tracking baseline + X/Y drift diagnosis (2026-06-14)

Source: 8 `flight_sinusoid_*.csv` logs in `ground_station/logs/`. Per-axis position
tracking computed from `pid.loc{x,y}.Des − .FB` (both in **cm**, see
[protocol contract]) over the window where `path.active_path_mode ≥ 1`.
Attitude RMSE (pitch/roll/yaw/z, in deg) comes from `deep_analysis.py` → `results/*.json`.

## Position tracking baseline (the trajectory metric)

| Run (ts) | Driven axis | Pos RMSE | Peak err | Amplitude vs commanded |
| --- | --- | --- | --- | --- |
| 1781275324 | locx | 13.0 cm | 18.5 cm | +50% (overshoot) |
| 1781275730 | locx | 42.7 cm | 68.1 cm | −9% (undershoot/lag) |
| 1781276093 | locx | 46.2 cm | 80.1 cm | −18% |
| 1781276599 | locx | 46.2 cm | 72.4 cm | −35% |
| 1781444507 | locx | 59.8 cm | 111.2 cm | −17% |
| **mean (driven locx)** | | **41.6 cm** | | |

Runs 287/304/311 drove neither X nor Y >2 cm → these were **Z-axis** sinusoids; their
12–17 cm "error" on the *static* X/Y axes is pure position hold wander (see drift below).
The overshoot-% metric is only meaningful on a driven axis (static axis amplitude ≈ 0
makes the ratio explode — ignore those numbers).

### Read of the baseline
- Horizontal trajectory tracking is **poor and degrading**: locx RMSE grows 13 → 60 cm
  across the session; later runs show **amplitude undershoot + phase lag** (negative
  "overshoot"), the signature of a position loop that can't keep up with the reference.
- This is exactly the case for the **waypoint-density** knob just added: a denser/slower
  reference should cut this lag-driven error; a sparse reference will expose it. The new
  Δs control lets you sweep this directly.
- Attitude (inner MRAC) RMSE is small (pitch ~2.4°, roll ~1.4°, z ~0.07 m) → the inner
  loop is healthy; the error budget is dominated by the **position layer**, not attitude.

## X/Y drift diagnosis

**Signature:** on axes the path did NOT command, position FB still wanders 12–18 cm RMSE
from a fixed Des within a single flight — consistent with the known optical-flow drift
(`ano_of.earth_x/y`, integrated from OF velocity).

**Root cause (why no controller "fixes" it):** the drift is a **measurement** error, not a
plant disturbance. `loc{x,y}.FB` is OF velocity integrated to position; a small constant
velocity bias `b` integrates into unbounded position error `b·t`. The position controller
faithfully drives the drone to hold the *corrupted* measurement, so it cannot reject an
error it cannot observe. Integral action makes it worse (chases the drift).

## Mitigation proposal (ranked)

1. **(Implemented 2026-07-12, `StabilizerTask.c:46-143`.)** OF velocity-bias calibration.
   `of2_dx_fix`/`of2_dy_fix` are averaged over a settled window and the result is
   subtracted from the raw signal before it feeds `DISTANCE_X/Y` and `earth_x/y`
   (`locx/locyPID.FB`). `loc{x,y}s.FB` (raw telemetry velocity, driven by `of2_dx/of2_dy`
   — not the `_fix` variant that's actually integrated) is left uncalibrated on purpose,
   so it stays useful as a live diagnostic of the raw bias magnitude.

   **v1 (arm-edge-triggered, 2s fixed window) — did not work.** First attempt started a
   2 s average immediately on the DisArmed→Armed edge. Bench-retested same day
   (`flight_1783833738.csv`, rigid mount @ 0.81–0.82 m, 266 s): `locx.FB` drift was
   +5.2 to +5.6 cm/s — essentially unchanged from the pre-fix baseline (+5.4 to +6.5 cm/s,
   `flight_1783831920.csv`). Root cause: arming (stick gesture) happens *before* the
   drone is physically settled into position — the fixed 2 s window closes while it's
   still being placed/held, so it calibrates against placement motion, not the true
   stationary bias.

   **v2 (gyro-quiescence-gated, one-shot per arm) — partial improvement, confirmed
   insufficient alone.** Waits for `OF_BIAS_STILL_TICKS` (0.5 s) of gyro rate below
   `OF_BIAS_STILL_THRESH_RADPS` (~3 deg/s), then averages `of2_dx_fix`/`of2_dy_fix` for
   `OF_BIAS_CAL_TICKS` (2.0 s), freezing the result until next arm. Bench-retested
   2026-07-12 with the drone actually armed this time (`flight_1783834592.csv`, rigid
   mount @ ~0.83 m, 326 s): `locx.FB` drift dropped from the pre-fix +5.4 to +6.5 cm/s
   down to +3.0 to +4.5 cm/s — real, roughly 40% reduction, confirming the calibration
   mechanism itself works. But the drift rate *climbs* across the session (+3.15 → +4.49
   cm/s over 5 segments), matching the same slow thermal-drift trend seen in
   `flight_1783831920.csv` (~13% bias change over 13 min) — a single arm-time snapshot
   can't track bias that keeps creeping afterward.

   **v3 (quiescence-gated, periodic refresh) — current.** Same quiescence gate, but also
   requires pitch/roll RC sticks centered (`!RCInput_IsActive(RC_AXIS_PITCH/ROLL)`) —
   this ties calibration to the exact moments `case_Update_loc_Des` already latches
   `locxPID.Des = locxPID.FB` (position hold assuming the drone is holding still,
   `StabilizerTask.c` ~line 629), and avoids folding a real constant-velocity manual
   translation into the bias estimate. Critically, completing a window no longer freezes
   the bias — it goes back to waiting, so **every time the pilot releases the sticks to
   hover** (not just at arm) the bias gets refreshed, tracking thermal drift throughout a
   flight instead of only at t=0. Motivation: manual-stick-only flight isn't a viable
   long-term workaround since position hold is the default whenever sticks are centered
   (not an opt-in mode) — this closes that gap so position hold can eventually be trusted
   without requiring the pilot to keep the sticks deflected the whole flight. **Not yet
   bench- or flight-validated.**

   Bench-characterized bias (rigid mount, fixed 0.83 m, 2026-07-12,
   `flight_1783831920.csv`): ~12–14 raw units on X, ~2–3 on Y, std 0.3–0.6 (tight/repeatable
   once hand-tremor is removed as a confound — see `flight_1783831067.csv` vs
   `flight_1783831920.csv` comparison). Sign and magnitude are yaw/orientation-dependent
   (X/Y bias flipped sign vs. the earlier hand-held test), which is expected since the OF
   velocity bias is measured in body/sensor frame before the yaw rotation into earth frame —
   another reason to recalibrate per-arm rather than hardcode a constant.
2. **Periodic / event origin re-zero.** CMD `0x10` already re-zeros the OF origin; expose a
   "re-zero before run" toggle in the path panel so each trajectory starts from a clean
   origin. Bounds accumulated drift per run; does not fix in-run drift.
3. **Absolute-reference fusion (future).** Fuse OF with GPS/SLAM/UWB for an un-drifting
   position. Currently blocked — `path_executor` reports SLAM/GPS "not available yet".

**Battery → overshoot:** un-analysable from these logs (no Vbat pre-v3). Now instrumented
as `status.vbat` (proto v3). After reflash + a few runs, correlate `status.vbat` against
locx peak error / undershoot; if overshoot tracks Vbat sag, re-enable the disabled Vbat→
throttle feedforward at `StabilizerTask.c:310` as the test mitigation.

## OF sensor interface facts (verified 2026-07-12)

Traced during a `/grill-with-docs` session to settle exactly what the OF module computes
on its own vs. what firmware does, and whether the two attitude estimates on the vehicle
(main FC vs. OF module) are coupled in any way.

**Protocol / data tiers received from the OF module** (`API/Ano_OF.c:109-180`, frame ID
`0x51`, sub-type at `data+4`):
- sub-type `0`: `of0_dx`/`of0_dy` — raw, uncompensated single-byte flow counts.
- sub-type `1`: `of1_dx`/`of1_dy` (`s16`) — height-fused (scaled by altitude) flow velocity.
- sub-type `2`: `of2_dx`/`of2_dy` (`s16`) plus `of2_dx_fix`/`of2_dy_fix` (`s16`) — INS-fused
  (tilt-compensated) flow velocity, and `intergral_x`/`intergral_y` (`s16`) — the module's
  own onboard-integrated position.
- Separately, frame `0x01` carries the module's own onboard accel/gyro
  (`acc_data_x/y/z`, `gyr_data_x/y/z`) and frame `0x04` carries the module's own
  quaternion (`Ano_OF.c:162-179`).

**`of2_dx_fix`/`of2_dy_fix` are body-frame velocities, tilt-compensated only.** The "_fix"
compensates for pitch/roll-induced apparent flow (a tilted downward camera sees apparent
ground motion even when stationary); it says nothing about yaw, since a straight-down
camera doesn't need yaw to be tilt-corrected. Firmware then rotates this body-frame vector
into `earth_x`/`earth_y` using `Cos_Yaw_01`/`Sin_Yaw_01`, which come from `imu_data.yaw` —
**the main FC's own Mahony-filtered yaw estimate**, not the OF module's
(`StabilizerTask.c:104-105,169-171`).

**Firmware never transmits to the OF module — confirmed, not assumed.** Checked the full
RX/TX path for USART2 (the OF module's UART, `BSP/usart2.c`):
- `USART_Mode_Tx | USART_Mode_Rx` is set at the hardware level (`usart2.c:36`), but only
  `USART_IT_RXNE` is ever enabled (`usart2.c:39`) — no TX interrupt is configured.
- A `DMA1_Stream6_IRQHandler` stub exists in `stm32f4xx_it.c:57-64` (comment: "USART2 send-
  complete interrupt") but is never armed — no `DMA_Init`/`DMA_Cmd(DMA1_Stream6, ENABLE)`
  call exists anywhere in the app.
- No call to `USART_SendData(USART2, ...)` exists anywhere in the repo.
- **Conclusion:** the OF module never receives FC attitude data. Its own tilt-compensation
  and quaternion are computed **entirely from its own onboard IMU**, fully independent of
  and unsynchronized with the main FC's attitude filter. There are two separate, uncoupled
  attitude estimates on the vehicle; firmware only ever trusts the main FC's for the
  body→earth rotation of OF velocity.
- **Implication:** any yaw error in the main FC's estimate leaks directly into `earth_x/y`
  position error, independent of and in addition to the OF velocity bias tracked above —
  not yet investigated as a contributor to observed drift.

**`intergral_x`/`intergral_y` (the module's own onboard position integral) are parsed but
never used.** Firmware discards them and re-integrates `of2_dx_fix`/`of2_dy_fix` itself
into `DISTANCE_X`/`DISTANCE_Y`/`earth_x`/`earth_y` (`StabilizerTask.c:165-171`). No
documented reason found for this choice (plausible: the module's integral is body-frame
only, or resets/wraps in a way firmware doesn't trust) — flagged as an open question, not
yet resolved.

## Roadmap: IMU+OF fusion to replace v3 bias correction (planned 2026-07-12)

Decided during the `/grill-with-docs` session above. Goal: replace the v3 stillness-gated
bias subtraction with a proper filter that fuses the FC's own IMU accel with the OF velocity,
estimating the velocity/accel bias *continuously* instead of only during stillness windows.
A Kalman filter with state `[velocity, accel_bias]` makes the v3 machinery obsolete.

**Two hard prerequisites** (surfaced in the interview):
1. **Gravity-removed body-frame linear accel is not exposed.** `Acc_X/Y/Z_Real` (mg, body
   frame, gravity-included) exist from the BMI088; the gravity direction in body frame
   `(vecxZ, vecyZ, veczZ)` is computed inside `IMU_Update_Mahony` (`imu_update.c:127-129`)
   but is a function-local static, never exported. Fusion needs
   `linear_acc_x = Acc_X_Real - G*vecxZ`, `linear_acc_y = Acc_Y_Real - G*vecyZ`. Do fusion
   in **body frame** (before the yaw rotation), matching where `of2_dx_fix` lives.
2. **`of2_dx_fix`→m/s scale factor is unknown** (same unknown as Q1: nobody knows the
   sensor's pixel/velocity→m/s scale). A filter can't blend accel (m/s) with OF (unknown
   units) until this scale `X` is measured. There is **no absolute XY reference on the
   vehicle** (that's the root of the drift), so `X` can only be found with an **external
   physical measurement** — a known-distance translation. `execute-TWC` cannot supply it:
   TWC feedback *is* the OF integral (`StabilizerTask.c:524,532`), so it's a ruler measuring
   itself (`X` cancels). Height matters too: OF velocity is height-scaled; log `of_alt_cm`
   to test whether `X` is constant across heights or the sensor's internal height-comp is
   imperfect.

**Execution order (raw logging both times; filter tuned offline, flown last):**
1. ✅ **DONE (2026-07-12) — `0x05` telemetry frame implemented** (below). Firmware serializer in
   `send_data.c` (gated by `mrac_flags.of_frame_on`, CMD `0x0F` idx 12), 200 Hz path in `main.c`,
   `GS_PROTO_VERSION` 8→9, host parser `_unpack_frame_of` in `serial_bridge.py`, and a frame
   selector in the dashboard Flight Log tab ("OF Calibration (0x05)"). No filter yet.
2. **Scenario 1 — hand-held ±1 m X/Y slides**, textured floor, bench height, props off/armed.
   Log raw signals. Derive `X`, check accel noise floor, confirm sign/frame conventions.
3. **Tune both filters offline in Python** (replay Scenario-1 log; same approach as `sim/`).
4. **Scenario 2 — free flight + execute-TWC translations**, logging the *same* raw `0x05`
   frame. Drone flies on the existing v3 estimate (known-safe); captures flight-condition
   vibration/propwash the bench can't. Still no onboard filter.
5. **Re-tune/validate both filters offline** against the Scenario-2 flight log; compare
   complementary vs Kalman (drift reduction, lag, vibration robustness).
6. **Only then flash the winning filter behind a flag** to drive `locxPID.FB`.
Principle: never fly an unvalidated filter — raw logging both scenarios, filter offline
first, onboard last.

### `0x05` calibration/fusion frame — locked layout (~42 B, streams @200 Hz)

UART4 ground-station link is 115200 baud → ~57 B/frame ceiling at 200 Hz (really bounded by
the blocking DMA-TX busy-wait fitting the 5 ms slot; the `0x03` ID frame proved 36 B @200 Hz).
Modelled on the `0x03` pattern: a new frame type gated by a CMD-toggled flag that replaces
Frame A/B while active, so normal telemetry stays lean. Bumps `GS_PROTO_VERSION`; needs a
dashboard parser.

```
[0..5]   header (sync, type=0x05, LEN16, MAX_NUM_BASIS)
[6..7]   sample_counter      u16     (dt base + dropped-frame detection)
[8..11]  of2_dx_fix, of2_dy_fix   s16x2  (integrated signal -> scale X)
[12..15] of2_dx, of2_dy           s16x2  (raw velocity, cross-check; first to cut if TX overruns)
[16..19] Acc_X_Real, Acc_Y_Real   s16x2  (mg; gravity-INCLUDED body accel)
[20..23] Lin_Acc_X_body, Lin_Acc_Y_body  s16x2  (mg; gravity-REMOVED body accel, fusion input)
[24..29] yaw, pit, rol            s16x3  (0.01 deg; body->earth rotation + gravity removal)
[30..33] s_of_bias_x, s_of_bias_y s16x2  (firmware v3 bias; validate + Kalman baseline)
[34..35] of_alt_cm               u16     (cm; test height-dependence of X)
[36..43] earth_x, earth_y        floatx2 (raw*s accumulator; *0.0124 -> m. verify integ vs offline)
[44]     of_quality              u8
[45]     CRC8   (payload 39 B; proto v10)
```
Fallback if the Send task overruns the 5 ms slot: drop raw `of2_dx`/`of2_dy` — they're the most
redundant since `of2_dx_fix` is what's integrated.

**Scale X derived (Scenario 1, 2026-07-12, `flight_1783845799.csv`):** 18 clean single-axis
~92 cm slides give **X = 0.0124 ± 0.0009 m per raw·s (7 %)**. 1 raw `of2_dx_fix` ≈ 0.0124 m/s;
firmware `earth_x` unit ≈ 1.24 cm. **X is ~height-invariant over alt 60–145 cm** → the ANO module
height-compensates internally; `of2_dx_fix` is a true fixed-unit velocity (no `of_alt_cm` scaling
needed in fusion). Still-bias on ground: dx_fix +0.22, dy_fix +2.41 raw. Circle (r≈92 cm) could NOT
cross-check X — the 16 s loop drifted open (~261 raw·s net) in the unaided integral, itself proof
the fusion filter is needed. `s_of_bias_x/y` stayed 0 (v3 estimator only fires armed) → needs an
armed hover (Scenario 2) to validate v3 bias. Prereq #1 (gravity-removed accel) DONE — now streamed
as `Lin_Acc_X/Y_body`, so Scenario 2 captures the complete fusion dataset in one flight.

[protocol contract]: ../CONTEXT.md
