# 0004 - Automated System-Identification Excitation Module

* **Status:** Accepted
* **Date:** 2026-06-16

## Context and Problem Statement

The inner-loop reference-model bandwidth (`ref_model_bw`) and the rotational inertia (`J`) in
`API/mrac.c` are **guesses**. The runtime-selectable reference model (ADR-0003) and any principled
MRAC tuning need these **identified from flight data**. Manual RC excitation cannot produce clean,
repeatable, frequency-rich signals — only the chirp and multisine can, and they must be machine-
generated.

Constraints that shape the design:

* **Lab space ≈ 2×2×2 m.** A drifting pitch/roll sweep can cross that in one low-frequency swing.
* **Optical-flow position drifts ~50 cm** over a short flight — so any position-based geofence is
  only approximately trustworthy in a ±1 m cube.
* **Ground effect** begins ~0.10–0.15 m; the Z axis is altitude-limited and asymmetric (thrust can
  push up but not reverse).

We need an automated, safe, in-firmware excitation + high-rate capture, plus an offline ID pipeline.

## Options Considered

### Injection point
* **A — rate setpoint** (`gyro*.Des`): closed-loop excitation; controller keeps the vehicle stable;
  the open-loop plant `x/u` is recovered offline from the logged ID frame (`r, x, u_nom, u_ad`).
* B — actuator command (post rate-PID): direct open-loop plant ID, but uncommanded torque to motors.
* C — attitude setpoint: convolves outer+inner loops; wrong layer for inner-loop ID.

### Outer angle loop during injection
* Leave active — self-levels, but **fights low-frequency excitation** (contaminated low-freq Bode).
* **Bypass on the test axis only** — clean inner-loop excitation; other axes stay angle-stabilized.

### Excitation signal
* **Log chirp** (default) — intuitive, debuggable, you watch the rolloff; one frequency at a time.
* **Schroeder multisine** (optional) — flat spectrum, low crest factor, **shortest runs** (best for
  tight space / battery / bounded drift); needs a precomputed phase table.
* PRBS / steps — steps remain the **manual RC** complement (good for damping/time-constant).

### Drift containment in the cube
* RC dead-man only (manual) vs **automated geofence (green zone)**.
* Decisive realisation: horizontal translation falls **~1/f³** with excitation frequency, so a sweep
  **starting ≳0.8 Hz** barely translates while still covering the rolloff band (3–8 Hz) that sets
  `ref_model_bw`. High-frequency excitation is the *primary* drift control; the geofence is a backstop.

## Decision and Rationale

1. **Inject on the rate setpoint (A).** Safest on a free-flying vehicle; logging `u_nom`+`u_ad`+`x`
   lets us recover the open-loop plant `x/u` anyway, so we lose nothing relative to option B.
2. **Bypass the outer angle loop on the test axis only** (other axes angle-stabilized) for clean
   inner-loop frequency response; injection and bypass both applied at the cascade point
   `TASK/StabilizerTask.c` where `gyro*.Des` is written.
3. **Chirp default + multisine optional**, selectable per run; band starts ≳0.8 Hz (pitch/roll up to
   ~15 Hz; yaw ~6 Hz, authority-limited; Z small-amplitude, mid-altitude only). Ramp in/out (~1–2 s).
4. **Green zone (virtual test cube):** axis-aligned box anchored at the start point (OF origin reset
   on start). Excited axis drifts freely inside; **soft boundary ±0.5 m, hard ±0.7 m** (conservative
   vs the ~50 cm OF drift). High-frequency excitation keeps actual drift small; the geofence is a backstop.
5. **Safety state machine** (`IDLE → PRECHECK → RAMP_IN → RUNNING → RAMP_OUT → IDLE`, with
   `RUNNING → RECOVERY` on any abort trigger):
   * **PRECHECK gates:** armed · `FlyMode==SDK` · altitude ∈ [0.3, 1.5] m · inside green zone ·
     telemetry fresh · battery > warn · OF origin freshly reset.
   * **Abort triggers:** soft-boundary cross · |angle| > 30° · rate/actuator saturation sustained ·
     telemetry/OF stale · battery low · **RC dead-man (any stick → instant full pilot takeover)** ·
     manual abort (reuse CMD `0x0D`).
   * **Recovery:** kill excitation → re-engage outer loop on the test axis → **level + hold current
     position first, then gently re-center** only if comfortably inside bounds. Hard boundary /
     stale-OF escalates to controlled descent.
6. **Module + orchestration:** new `API/sysid.c`/`.h` ticked at 200 Hz from StabilizerTask. New
   **CMD `0x14`** `{axis, signal_type, f0, f1, amplitude, duration, start/abort}`. Start auto-resets
   the OF origin and auto-enables the high-rate ID frame (`0x0F` idx 11); finish/abort restores.
   New dashboard **"System ID" tab** + live FSM state.
7. **Offline analysis:** `ground_station/scripts/sysid_analysis.py` — `id.sample_counter` as time base;
   Bode of `x/u` and `x/r`; **coherence** quality gate; bandwidth → recommended `ref_model_bw`;
   regression `J·ẋ + b·x = u` → inertia/damping.

## Forward sequence (plan)

* **Phase 0 (done):** ID frame `0x03`, runtime reference-model selector `0x13`, battery indicator,
  data-grounded `e_sat`/`e_freeze`.
* **Phase 1:** gyro signal hygiene — anti-alias LPF (+ optional RPM-tracking dynamic notch).
* **Phase 2:** this excitation module (`sysid.c`, CMD `0x14`, dashboard tab); validate in shadow mode.
* **Phase 3:** SysID flights — chirp per axis (roll, pitch, yaw, Z-last) in the green zone.
* **Phase 4:** `sysid_analysis.py` → Bode, coherence, bandwidth, `J`. Set `ref_model_bw`, update `J`.
* **Phase 5:** validate the 1st/2nd-order reference model with the identified bandwidth.
* **Phase 6:** implement Pseudo-Control Hedging using the identified actuator model.
* **Phase 7:** translational observer / T265 VIO — for path-tracking thesis metrics *and* reliable
  tight-space geofencing.

## Files Affected (planned)

* `API/sysid.c`, `API/sysid.h` (new)
* `TASK/StabilizerTask.c` (injection + outer-loop bypass at the cascade), `TASK/send_data.c` (CMD `0x14`)
* `ground_station/gui/dashboard.py` (System ID tab), `ground_station/comm/serial_bridge.py` (CMD doc)
* `ground_station/scripts/sysid_analysis.py` (new)
* `CONTEXT.md`

## Constraints Created

* **Geofence reliability is bounded by OF drift (~50 cm).** Trustworthy tight-space geofencing
  requires drift-free position (T265 VIO, Phase 7).
* **`J` and torque effectiveness (`mrac_to_mixer`) are coupled** in flight data — the *lumped*
  input-output model is identifiable (sufficient for MRAC); physical `J` needs an independent
  effectiveness measurement.
* **Injection only when armed + SDK + inside the green zone + above ground-effect altitude.** The
  excited axis does not self-level; the RC dead-man is the final authority at all times.
