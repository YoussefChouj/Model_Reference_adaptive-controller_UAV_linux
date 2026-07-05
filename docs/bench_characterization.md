# Bench characterization — cheap DIY guide

Two cheap bench tests give the entire physical-parameter set the simulation/Gazebo  
digital twin needs, and fix the wrong constants in the notebooks (mass was 366 g in  
code, **really 988.5 g**). Neither needs the drone to fly.

| Test | Cost | Time | Produces |
| --- | --- | --- | --- |
| Bifilar pendulum | ~free | 1–2 h | Inertia tensor Ixx, Iyy, Izz + CG offset |
| Thrust stand | $0 (manual) → ~$20 (auto) | 1–3 h | Thrust & torque vs command; thrust vs voltage |

⚠️ **Safety (thrust stand):** a prop at full throttle can amputate. Bolt everything down,  
stand out of the prop plane, wear eye protection, use a current-limited supply or a  
charged-but-not-fresh pack, keep an arming kill switch in reach.

---

## 1\. Bifilar pendulum — inertia for ~free

**Idea:** hang the drone from **two parallel vertical strings** (fishing line) so the axis  
you want is vertical and passes through the CG. Twist a small angle, release, time the  
torsional oscillation. The period gives the moment of inertia.

**Formula:**

```
I = (m · g · d² · T²) / (16 · π² · L)
```

*   `m` = mass (0.9885 kg), `g` = 9.81, `d` = horizontal distance between the two strings \[m\],  
    `L` = string length \[m\], `T` = oscillation period \[s\].

**Procedure**

1.  **Find the CG first** (the missing guard offsets it): balance the drone on a thin edge  
    in two directions; the crossing point is the CG. Mark it.
2.  Attach two strings of **equal length** L, symmetric about the CG, separation d, so the  
    measured axis is **vertical** through the CG.
3.  Twist **small** (\<10–15°), release, and let it oscillate **20–30 cycles**.
4.  Repeat 3× per axis, average.
5.  Rotate the drone to put each axis vertical in turn (string pairs at motor centers,
    symmetric about the axis under test so the twist axis passes through the CG):
    *   **Izz (yaw):** drone level, props up — strings from two **diagonally opposite** motor centers.
    *   **Ixx (roll):** nose straight down (roll axis vertical) — strings from the two **rear** motors.
    *   **Iyy (pitch):** one side straight down (pitch axis vertical) — strings from the two motors of the **upper** side.

**Timing with the onboard gyro (no stopwatch, 2026-07-05):** the drone hangs powered
and DISARMED with the battery in (that *is* the flight configuration you want). The
gyro-rate feedbacks stream in **Frame B at 20 Hz regardless of arm state** — ample for
a ~0.5 Hz oscillation. Over the **wireless telemetry link** (a cable would damp the
swing), press the dashboard's **"Flight recording (20 Hz merged telemetry → CSV)"
Start**, twist–release, record 20–30 cycles, Stop. Then
`python ground_station/scripts/inertia_analysis.py <csv> --axis yaw --mass … --d … --L …`
extracts T (zero-crossing fit + FFT cross-check), the damping correction, and
I ± uncertainty, and warns if the off-axis gyros show the rig was swaying. **Zero
firmware changes needed.**

**Sizing the rig:** with m ≈ 0.99 kg and Izz ≈ 0.03 kg·m², **L ≈ 1.0–1.5 m** and
**d ≈ 0.4 m** (motor-to-motor) gives T ≈ 2 s — comfortable. Measure d and L to the
millimeter: they enter as d² and 1/L and dominate the error budget, not the gyro.

Expect Ixx ≈ Iyy (symmetric-ish), Izz a bit different. Sanity-check against the cuboid  
estimate `J = m/12·(w²+l²)` **recomputed with 988.5 g**, not 366 g.

---

## 2\. Thrust stand

### 2a. Manual version (kitchen scale, $0)

**Mount the motor blowing UPWARD, with the whole rig sitting on the scale.** Thrust pushes  
the rig up, so the scale reads **less**; thrust = (static weight) − (reading). Blowing _up_  
keeps prop-wash off the scale pan (blowing down corrupts the reading with airflow on the pan).

*   Drive the motor with the **built-in firmware Motor Bench mode** (ADR-0009): dashboard
    **"Motor Bench" tab** → pick the motor, step the CCR with the ± buttons (DISARMED-only;
    firmware dead-man stops it if the dashboard disconnects). CMD `0x16` drives one motor;
    telemetry frame `0x04` streams CCR + pack voltage at 100 Hz. (A **servo tester (~$5)** is
    the no-firmware fallback.) Use **fixed CCR steps** (e.g. 100 counts over 2000→4000), not
    percentage — even coverage of the nonlinear `T ∝ CCR²` curve gives a cleaner fit.
*   At each step, let the reading settle, then **Log point** → one (CCR, thrust, voltage) row
    in `logs/bench/thrust_<ts>.csv`. ~20 points = your curve. Sweep **up and down** (hysteresis).
*   **RPM (ADR-0010):** TCRT5000 reflective module plugged into a spare TIM2 3-pin header
    (use PB3/PB10/PB11 — avoid the PA5 header until its rail voltage is verified ≤3.3 V or a
    10k series resistor is added), sensor looking **up at the blade roots from below**, one
    reflective mark on each blade underside at the same radius. Tune the module trimpot so a
    bare blade reads LOW and only tape reads HIGH (verify by hand-spinning, watching the module
    LED, before powering the motor). Frame 0x04 then streams live RPM and each Log-point row
    gains `rpm` and the `T_est = k·ω²` estimate from measured ω → model-vs-scale error per point.
*   Thrust in grams × 0.00981 = newtons (the dashboard computes `thrust_N` and the
    `T = k·ω²` estimate for you if you fill the propeller `k, a, b` fields).

**Battery-voltage caveat (important):** thrust at a given command **drops as the pack**  
**discharges**. So either (a) do the whole sweep **fast on a freshly-charged pack and note the**  
**voltage**, or (b) repeat the sweep at full / mid / low pack and record voltage each time to  
get thrust-vs-voltage. Since you have **no voltage sensing on the drone**, measure pack  
voltage with a **multimeter or a cheap battery alarm/checker** at the start and end of each  
sweep and log it by hand.

### 2b. Auto-logging DIY stand (~$15–25, the RCBenchmark poor-man's clone)

Build this if you want clean, repeatable curves without hand-logging.

**Parts**

| Part | ~Cost | Role |
| --- | --- | --- |
| Load cell (1–5 kg) + **HX711** 24-bit amp | $5 | digital thrust |
| **ESP32** dev board | $5 | drives ESC throttle + reads sensors + logs (SD/WiFi/serial) |
| Voltage divider (2 resistors, e.g. 30k/7.5k for 4S) | ~$0 | pack voltage on an ADC pin |
| **ACS758** (50 A) hall sensor _or_ INA226 + shunt | $3–4 | current (**optional**, see below) |
| Servo tester | $5 | only if not letting the ESP32 generate the throttle signal |
| Frame: scrap wood / 3D print / alu extrusion | ~$0 | motor on an arm → force into load cell |

**Wiring/architecture**

*   ESP32 generates the throttle signal to the ESC (PWM/oneshot/DShot — PWM via `Servo` lib is  
    simplest), **scripts an automatic sweep** (ramp 0→100 % in steps, dwell ~2 s each).
*   At each step it samples HX711 (thrust), the divider (V), and optionally current, with a  
    timestamp, and writes a CSV line. → automatic thrust-vs-command **and** thrust-vs-voltage.
*   Calibrate: HX711 with known weights (set scale factor); divider against a multimeter.

**Do you need current?** For _control/Gazebo fidelity_, **no** — you need thrust & torque vs  
command, and thrust vs voltage. Current only buys you **thrust-to-power / efficiency**, which  
is endurance modelling, not control. Build the thrust+voltage stand first; add the current  
sensor later only if you start caring about flight time. (Note: drone motor current can hit  
20–40 A, so a small INA219 (3 A max) is **not** enough — use ACS758/INA226-with-shunt.)

### 2c. Getting _torque_ (for yaw K and the mixer constant)

Thrust alone gives roll/pitch authority. For **yaw drag-torque** (your K≈37) you need torque:  
mount the motor on an **arm of known length r** offset from the load cell, so the reaction  
acts as a moment → `torque = measured_force × r`. Or measure reaction torque by mounting the  
whole motor on a pivot with the load cell at a known radius. One extra geometry, same rig.

---

## What these feed

| Output | Fixes / fills | Used by |
| --- | --- | --- |
| Ixx, Iyy, Izz, CG | notebook cuboid guess (with 988.5 g) | sim plant, Gazebo `<inertia>` |
| Thrust vs command | bogus `TORQUE_TO_PWM2` / hover throttle | mixer, Gazebo motor plugin (Ct) |
| Torque vs command | yaw authority, validates K≈37 | Gazebo (Cq), mixer |
| Thrust vs voltage | battery-sag disturbance model | MRAC robustness scenarios |

All of this is **off the flight critical path** — do it on the bench whenever, in parallel  
with the sim rebuild. See [sim\_rebuild\_handoff.md](sim_rebuild_handoff.md).