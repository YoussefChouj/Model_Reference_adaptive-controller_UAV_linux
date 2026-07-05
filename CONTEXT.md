# CONTEXT

Domain glossary for the FreeRTOS 6-DOF MRAC adaptive flight controller. Terms here are  
meaningful to a controls/embedded reviewer; implementation detail lives in the code.

## Control architecture

*   **MRAC inner loop** — Model Reference Adaptive Controller in `API/mrac.c`, runs per-axis  
    (pitch, roll, yaw, z) with adaptive weights `theta_0..theta_5`, nominal `u_nom` and  
    adaptive `u_ad`. Tracks the reference model state `xm`; tracking error `e`. This is the  
    layer that actually flies the setpoints.    *   **Reference Model:** 1st-order dynamic reference model for rates (`xm += dt * (Am * xm + Bm * r)`) to provide smooth, achievable targets. Bandwidth is tuned to 80-90% of the nominal PID closed-loop bandwidth.
    *   **Control Sign Convention:** Additive control efforts ($u_{total} = u_{nom} + u_{ad}$). Since rate-to-torque effectiveness $B > 0$, the update law gradient $\dot{\theta} = -\Gamma e P \Phi$ is mathematically correct and requires no sign-flip.*   **PID position/attitude loops** — `Ctrler.*PID` (locx, locy, z\_pos, pitch, roll, yaw,  
    gyrox/y/z). The path generator writes the **desired position** into  
    `Ctrler.locxPID.Des` / `locyPID.Des` / `Z_posPID.Des` / `yawPID.Des`.
*   **Path generator (firmware-side)** — `TASK/AutoflyTask.c`. THE trajectory engine. Each  
    preset advances at `dt = 0.005f` (200 Hz) and writes PID `.Des`. NOT the Python  
    `path_executor.py`.

## System identification (SysID) — inner-loop excitation

Planned module (design in progress; see ADR when written). Purpose: replace guessed inner-loop  
parameters with values **identified from flight data**.

*   **SysID excitation** — a firmware-generated test signal added to **one axis's rate setpoint**  
    (`gyro*.Des`). Closed-loop by design: the controller keeps stabilizing the vehicle, and the  
    plant model `x/u` is recovered offline from the high-rate ID frame (`r, x, u_nom, u_ad, xm`).  
    On the excited axis the **outer angle loop is bypassed** (clean inner-loop excitation); the  
    other axes stay angle-stabilized.
*   **Green zone (virtual test cube)** — an axis-aligned position box sized to the lab (~2×2×2 m)  
    and anchored at the drone's start point (OF origin reset before each run). The excited axis is  
    free to drift **inside** the zone; on a soft-boundary violation the outer loop re-engages, the  
    run aborts, and the drone returns to centre. **Backstop only** — primary drift control is  
    **high-frequency excitation** (translation falls ~1/f³, so a sweep starting ≳0.8 Hz barely  
    moves the vehicle while still capturing the rolloff band that sets `ref_model_bw`).  
    Caveat: geofence accuracy is limited by OF position drift (~50 cm); reliable tight-space  
    geofencing wants drift-free position (T265 VIO).
*   **Identified quantities** — inner-loop **bandwidth** (→ sets `ref_model_bw`) and effective  
    **inertia `J` / damping `b`** from `J·ẋ + b·x = u`. Note: from flight data alone `J` and torque  
    effectiveness (`mrac_to_mixer`) are coupled — the *lumped* input-output model is identifiable  
    (which is what MRAC needs); separating physical `J` needs an independent effectiveness measurement.

## Simulation package (`sim/`) — adaptive-control source of truth

Rebuild of the legacy notebooks (ADR-0006). One codebase, two scenarios: **hardware-param
derivation** (gains/P pasted into `mrac.c`) and **virtual simulation** (pluggable plant). The
controller and adaptive law are **plant-agnostic** — they never know if the plant behind the seam
is an identified linear model, a future 6-DOF model, or Gazebo.

*   **Plant boundary = the rate loop.** `plant.step(u_dict) -> state_dict`: torque/thrust (SI,
    `u_nom + u_ad`) in, **rate** out (`p,q,r,vz`). Outer position/attitude PID lives in `baseline.py`,
    never in the plant. `state_dict` is extensible so a later plant can return full 6-DOF state.
*   **Identified plant realisation** — `G(s)=K/(s(1+s/p))·e^{-sT}` as ZOH-discretized rational part
    + **integer delay ring buffer** (`N=round(T/dt)`). Roll/pitch = rel-degree-2 + delay; yaw = pure
    integrator `37/s`. Delay is load-bearing (caps learning aggressiveness) — never drop it.
*   **Sim↔firmware parity rule (HARD).** Sim controller step `dt = 0.005 s` (= `MRAC_DT`, 200 Hz) so
    every gain/flag pastes from `mrac.c` with no rescaling. The **regressor `Phi` is hand-ported from
    `MRAC_GenerateStructuredBasis` (`mrac.c:65-91`) and pinned by a golden-vector test** — if the
    firmware formula drifts, the test fails. Active flag combo: `STRUCTURED + INCLUDE_CONTROL` ⇒
    6 basis terms `[bias, x, x·tanh x, cross_coupling, u_nom, xm]`.
*   **Adaptive coupling, not dynamic coupling.** Plant axes are independent SISO, but regressors are
    cross-coupled: `cross_pitch = roll_rate·yaw_rate`, `cross_roll = pitch_rate·yaw_rate`
    (`mrac.c:445-446`). The run-loop must read **all** plant rates, compute cross terms, *then* build
    each axis regressor — ordering is a parity requirement.
*   **Reference-model default diverges from firmware on purpose.** Firmware ships `ref_model_type=0`
    (passthrough); the sim defaults to the **identified per-axis types** (2nd-order roll/pitch, 1st-order
    yaw, ADR-0005) because validating those is the point. Passthrough stays available as a baseline.
*   **Per-run artifacts** — `sim/runs/<ts>_<scenario>/{plots/, report.md, data.csv, metrics.json}`.
*   **Frame** — canonical **NED** (firmware); ENU adapter only at the Gazebo seam. **Gazebo** is a
    reserved `NotImplementedError` stub in Phase 1; bring-up is a later Linux-partition session.

## Trajectory presets (firmware-generated)

Run only when `DroneStatus.FlyMode == FlyMode_SDK`. Mutually exclusive via  
`AutoflyTask_PathArbitrate()`. Streamed as `path.active_path_mode`:

| Mode | active\_path\_mode | Start CMD | Curve |
| --- | --- | --- | --- |
| **TWC** (point-to-point) | 1 | 0x0A | go-to single target (target\_x/y/z, set\_yaw, execute) |
| **Sinusoid** | 2 | 0x0B | single-axis sine: `center + amplitude·sin(2π·freq·t)` on axis 0=X/1=Y/2=Z |
| **Circle** | 3 | 0x0C | `center + radius·(cos θ, sin θ)`, θ advances by `angular_speed·dt`; yaw follows θ |
| **Figure-8** (planned) | 4 | 0x11 (planned) | lemniscate, selectable Bernoulli (∞) vs Gerono (vertical 8) |

Path CMDs are idx-mapped floats (one param per index); activation index sets `.active=1`  
inside `taskENTER_CRITICAL()` and zeroes `t_elapsed`. Abort: CMD 0x0D  
(`GroundStation_AbortAllPaths`).

Used CMD IDs: 0x0A TWC · 0x0B sinusoid · 0x0C circle · 0x0D abort · 0x0E SDK arm ·  
0x0F MRAC flags · 0x10 OF-origin reset · **0x11 figure-8 (new)** ·  
**0x12 waypoint spacing (new)**.

## Waypoint density (reference quantization) — shared across all path modes

*   **waypoint\_spacing Δs** (shared global; set by CMD 0x12 idx 0). Firmware unit is the  
    loc-PID unit (**cm** for x/y); the dashboard presents metres and sends `Δs·100`.  
    Default is **5 cm** (firmware `waypoint_spacing = 5.0f`, GUI field `0.05`).  
    `Δs = 0` ⇒ continuous reference (maximally dense). The accumulator scales the z delta  
    by ×100 (m→cm) so `Δs` (cm) is uniform across all axes, including Z-axis sinusoid.
*   Mechanism (mode-agnostic): each 200 Hz tick a mode computes its _continuous_ parametric  
    target. A shared accumulator sums the Euclidean distance the continuous target moved  
    since the last commit; when `accum ≥ Δs`, the current continuous target is committed to  
    `Ctrler.loc{x,y}PID.Des` and the accumulator resets. Between commits `Des` is held.
*   This realises **time-based stepping at the path's nominal speed** (the reference moves at  
    the path speed, so arc-length and time advance together) — NOT arrival-based gating on  
    the drone's measured position. Density (Δs) and traversal speed stay independent knobs,  
    which is the point for thesis tracking-performance comparisons: denser ⇒ smoother,  
    sparser ⇒ a staircase reference that stresses the MRAC.

## Position feedback & known sensor behaviour

*   **locx.FB / locy.FB** — horizontal position feedback from **optical flow**. Known to  
    **drift ~50 cm** over a short flight (expected OF behaviour). Primary error source for  
    X/Y trajectory tracking. `locxs`/`locys` are the velocity (rate) sub-loops.
*   **z\_pos.FB** — height feedback (TF-Mini / rangefinder).
*   **Tracking error** = `pid.loc{x,y}.Des − pid.loc{x,y}.FB`; both are logged, so per-axis  
    RMSE/overshoot is computable from existing CSVs.

## Battery

*   **real\_voltage** — battery voltage, sampled by `Get_Voltage()` (ADC1 ch4) in  
    `TASK/StabilizerTask.c`; scaled to a 4S pack (`/2.85·16.8`). As of proto v3 (2026-06-14)  
    it is appended to the Frame B tail and parsed as `**status.vbat**`, so it now lands in the  
    flight CSV logs and battery↔tracking correlation is analysable.
*   MRAC uses `current_vbatt` inside `MRAC_InverseMixer` (thrust ∝ (pwm·vbatt)²).
*   A static Vbat→throttle feedforward exists but is **commented out**  
    (`StabilizerTask.c:310`).

## Ground station

*   **Flight log** — `ground_station/logs/flight_<label>_<ts>.csv`, long format  
    `t_s,frame,key,value`. Auto-saved when recording stops; analysis writes plots to  
    `Analysis_plots/` and a JSON report to `ground_station/results/<stem>.json`.
*   **path\_executor.py** — separate virtual-stick path (CMD 0x06, SDK/sbus-lost only) with a  
    stubbed `_loop_body`; appears legacy. Not the engine behind the logged preset runs.

## Analysis & evaluation pipeline

Three **distinct stages** produce three **distinct artifacts** — the word "summary" was overloaded  
across all three, so the canonical names are fixed here:

*   **Per-run analysis** (stage 1, automatic). Runs every time a preset finishes/aborts. Two scripts:  
    `analyze_flight_log.py` (tracking + MRAC PNGs) and `deep_analysis.py` (metrics engine).  
    Emits per run, in `Analysis_plots/<stem>_analysis_<ts>/`:
    *   **`summary.md`** — the run header (mode + **real GUI params**). Enriched to carry the  
        headline scorecard + the *What-Happened verdict*.
    *   **`report.md`** — the full per-axis deep report (scoreboard, alerts, plots).
    *   **`<stem>.json`** in `ground_station/results/` — the machine record consumed by the  
        `analyze-results` skill. Schema is **append-only** (never break `scoreboard`/`diagnostics`).
*   **Champion store** (stage 2). `ground_station/champions/<mode>/` retains the **best run per  
    (mode × tuning-config)** — keyed by a hash of the ranking-relevant params/gammas, so a new  
    tuning never erases a prior champion. Holds `best_overall.json`, `leaderboard.json` (top-N),  
    and `by_config/cfg_<hash>.json`. Updated incrementally after each run.
*   **Global analysis** (stage 3). `Analysis_plots/_global/` — cross-run leaderboard + per-mode  
    trend (this run vs previous vs champion) + delta narrative. Auto-appended cheaply per run;  
    full rebuild on demand via `global_analysis.py`.

### Evaluation vocabulary (canonical metric terms)

*   **Position-tracking RMSE** — RMSE of `pid.loc{x,y}.Des − .FB` (cm) / `z_pos` (m). The primary  
    path-performance signal. *Was previously unanalysed — deep\_analysis only scored attitude loops.*
*   **Cross-track error** — perpendicular distance from the flown XY point to the **closed-form  
    ideal curve** (circle/lemniscate/sine). Measures *shape fidelity*, decoupled from waypoint  
    quantization (`Δs`). Distinct from Des−FB tracking error.
*   **Along-track lag** — tangential displacement along the ideal curve; isolates *running behind  
    the reference* (timing/phase) from *wrong shape* (cross-track).
*   **TWC settling** — for point-to-point (mode 1): rise time, settling time (±band), overshoot,  
    steady-state error. Continuous-path modes use RMSE/cross-track instead.
*   **Champion** — the health-gated best run for a (mode × tuning-config). A run with any  
    **CRITICAL** alert is **ineligible** regardless of RMSE.
*   **What-Happened verdict** — rule-based plain-language interpretation of the scorecard at the  
    top of `summary.md`/`report.md`. The pipeline's primary purpose is *understanding a run*,  
    not just scoring it.
*   **Real params vs snapshot** — `deep_analysis.snapshot_firmware_params()` is currently  
    **hardcoded/static**; the true per-run params live in the GUI's `_auto_log_params` and must be  
    forwarded so champion records key on real tunings, not a fake snapshot.