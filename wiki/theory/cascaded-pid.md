# Cascaded PID Theory

> Explains the cascade control design principles behind the firmware's 4-level PID hierarchy, maps tuning rules to the specific gains in `API/pid.c`, and documents the anti-windup strategy.

**Sources**:
- K. J. Åström, R. M. Murray, *"Feedback Systems: An Introduction for Scientists and Engineers,"* Princeton Univ. Press, 2nd ed., 2021 — Ch. 11 (PID Control), Ch. 12 (Frequency Domain Design)
- S. Bouabdallah, P. Murrieri, R. Siegwart, *"PID vs LQ Control Techniques Applied to an Indoor Micro Quadrotor,"* IROS 2004 — quadrotor-specific cascade analysis
- G. V. Raffo, M. G. Ortega, F. R. Rubio, *"An Integral Predictive/Nonlinear H∞ Control Structure for a Quadrotor Helicopter,"* Automatica 46(1), 2010

**Related wiki**: [[PID Controller]], [[StabilizerTask]], [[Coordinate Conventions]], [[MRAC Theory]]

---

## 1. Why Cascade Control?

A quadrotor has a chain of dynamics from position to motor output:

```
Position → Velocity → Angle → Angular Rate → Motor Torque
```

Each level has different:
- **Bandwidth**: Angular rate responds in milliseconds, position in seconds
- **Sensor availability**: Gyro gives rate at 1 kHz, optical flow gives position at lower rates
- **Disturbance entry points**: Wind affects position; propeller vibrations affect rate

A single controller trying to go directly from position error to motor torque would need to handle all these timescales simultaneously — leading to high-order, fragile controllers.

**Cascade control** breaks this into nested loops, each handling one timescale:

```
                    ┌─────────────────────────────────────────────────────────────┐
                    │                    Outer loops (slow)                        │
                    │                                                             │
 Position ref ──►[Position PID]──►[Velocity PID]──►                              │
                                                    │                             │
                                              ┌─────▼──────┐                     │
                                              │ Angle PID   │  ◄── Middle loop   │
                                              └─────┬──────┘                     │
                                                    │                             │
                                              ┌─────▼──────┐                     │
                                              │  Rate PID   │  ◄── Inner loop    │
                                              └─────┬──────┘                     │
                                                    │                             │
                                              Motor Mixer                         │
                    └─────────────────────────────────────────────────────────────┘
```

Each inner loop "linearizes" the dynamics for the next outer loop: the rate loop makes the vehicle behave like a simple first-order angle system, the angle loop makes it behave like a first-order velocity system, and so on.

---

## 2. The Four Levels in This Firmware

All PID loops run in `Compute_Motor()` (`StabilizerTask.c:237–353`), called at 200 Hz from `Stabilizer_Task` (`main.c:186–193`).

### 2.1 Level 1: Position → Velocity (100 Hz effective)

**Loops**: `locxPID`, `locyPID` — computed at 100 Hz via the `cnt_loc` decimation counter (`StabilizerTask.c:252–265`)

**Input**: Position error in world frame (meters) from optical flow integration
**Output**: Velocity setpoint (cm/s) fed to velocity PID

```c
// StabilizerTask.c:256-257
ComputePID(&Ctrler.locxPID);
ComputePID(&Ctrler.locyPID);
```

**Gains** (`pid.c:22–23`):

| Parameter | locx | locy | Unit |
|:---|:---|:---|:---|
| Kp | 0.8 | 0.8 | (cm/s)/m |
| Ki | 0.01 | 0.01 | (cm/s)/(m·s) |
| Kd | 4.0 | 4.0 | (cm/s)/(m/s) |
| UMax | 300 | 300 | cm/s |

**World-to-body rotation**: The position PID uses specialized functions `ComputePID_locx` and `ComputePID_locy` (`pid.c:90–146`) that rotate the error from world frame to body frame before computing PID terms:

```c
// pid.c:94 — locx error in body frame
Ctrler.locxPID.E = (Ctrler.locxPID.Des - Ctrler.locxPID.FB) * Cos_Yaw
                 - (Ctrler.locyPID.Des - Ctrler.locyPID.FB) * Sin_Yaw;
```

```c
// pid.c:123 — locy error in body frame
Ctrler.locyPID.E = (Ctrler.locyPID.Des - Ctrler.locyPID.FB) * Cos_Yaw
                 + (Ctrler.locxPID.Des - Ctrler.locxPID.FB) * Sin_Yaw;
```

This rotation is necessary because position error is measured in the world (earth) frame, but the vehicle tilts in its body frame. Without rotation, a pure X-direction position error would require different pitch/roll corrections depending on the current yaw heading.

`Cos_Yaw` and `Sin_Yaw` are computed from the negative of `imu_data.yaw` in `Update_Data()` (`StabilizerTask.c:98–99`):

```c
Cos_Yaw_01 = cos(-imu_data.yaw * DEG2RAD);
Sin_Yaw_01 = sin(-imu_data.yaw * DEG2RAD);
```

### 2.2 Level 2: Velocity → Angle Setpoint (100 Hz effective)

**Loops**: `locxsPID`, `locysPID` — also at 100 Hz

**Input**: Velocity error in body frame (cm/s) from optical flow
**Output**: Acceleration command, converted to angle setpoint via `accel_to_lean_angles()` (`StabilizerTask.c:503–519`)

```c
// StabilizerTask.c:263-264
ComputePID(&Ctrler.locxsPID);
ComputePID(&Ctrler.locysPID);
```

**Gains** (`pid.c:24–25`):

| Parameter | locxs | locys | Unit |
|:---|:---|:---|:---|
| Kp | 3.0 | 3.0 | (°)/(cm/s) |
| Ki | 0 | 0 | — |
| Kd | 6.0 | 6.0 | (°)/(cm/s²) |
| UMax | 600 | 600 | acceleration units |

The velocity-to-angle conversion uses `accel_to_lean_angles()` which applies an atan-based mapping that accounts for the nonlinear relationship between tilt angle and horizontal acceleration:

```c
// StabilizerTask.c:513-514
*tar_pitch = Constrain_Float(
    fast_atan(acc_tar_forward * my_Cos_Roll / (GRAVITY_MSS*100)) * RAD2DEG,
    -lim_p, lim_p);
```

This includes cos(roll) and cos(pitch) compensation so that the pitch setpoint is correct even when the vehicle is already rolled (and vice versa).

### 2.3 Level 3: Angle → Rate Setpoint (200 Hz)

**Loops**: `pitchPID`, `rollPID`, `yawPID`

**Input**: Angle error in degrees
**Output**: Rate setpoint in °/s fed to the rate PID

```c
// StabilizerTask.c:270-274
ComputePID(&Ctrler.pitchPID);
ComputePID(&Ctrler.rollPID);
ComputeYawPID(&Ctrler.yawPID);  // Uses ±180° wrapping
```

**Gains** (`pid.c:6–8`):

| Parameter | pitch | roll | yaw |
|:---|:---|:---|:---|
| Kp | 3.0 | 3.0 | 6.0 |
| Ki | 0.1 | 0.1 | 0.04 |
| Kd | 8 | 8 | 0 |
| UMax | 200 | 200 | 120 |
| EMin | 3 | 3 | 2 |

The yaw loop uses `ComputeYawPID()` (`pid.c:58–86`) which wraps the error to ±180°:

```c
// pid.c:62-63
if(pPID->E >= 180) pPID->E -= 360;
if(pPID->E <= -180) pPID->E += 360;
```

This prevents the controller from commanding a 350° rotation when a -10° rotation would reach the same heading.

### 2.4 Level 4: Rate → Motor Torque (200 Hz)

**Loops**: `gyroxPID`, `gyroyPID`, `gyrozPID`

**Input**: Rate error in °/s
**Output**: Motor mixer command (dimensionless, maps to PWM)

```c
// StabilizerTask.c:280-282
ComputePID(&Ctrler.gyroxPID);
ComputePID(&Ctrler.gyroyPID);
ComputePID(&Ctrler.gyrozPID);
```

**Gains** (`pid.c:13–15`):

| Parameter | gyrox (roll rate) | gyroy (pitch rate) | gyroz (yaw rate) |
|:---|:---|:---|:---|
| Kp | 5 | 5 | 8.0 |
| Ki | 0.01 | 0.01 | 0.001 |
| Kd | 10 | 10 | 0.02 |
| UMax | 300 | 300 | 250 |
| EMin | 2 | 2 | 20 |

The rate PID outputs are combined in the motor mixer (`StabilizerTask.c:333–351`) with the throttle command and (optionally) MRAC adaptive corrections.

### 2.5 Height Control (100 Hz position, 200 Hz rate)

**Loops**: `Z_posPID` (altitude position) → `Z_ratePID` (vertical velocity)

**Gains** (`pid.c:17–18`):

| Parameter | Z_pos | Z_rate |
|:---|:---|:---|
| Kp | 0.7 | 400 |
| Ki | 0.005 | 0.435 |
| Kd | 0.1 | 0 |
| UMax | 1.0 | 300 |

The Z position PID runs at 100 Hz (decimated via `cnt_h`, `StabilizerTask.c:243–247`), while Z rate runs at the full 200 Hz.

---

## 3. Cascade Design Rules and How This Code Follows Them

### Rule 1: Inner Loops Must Be 5–10× Faster Than Outer Loops

The bandwidth separation principle ensures that each inner loop has "settled" before the outer loop's next sample. Without this, the outer loop sees a plant that is still responding to the previous command, causing oscillation.

| Loop | Effective rate | Bandwidth ratio to next inner |
|:---|:---|:---|
| Position (locx/locy) | 100 Hz | ~1:1 with velocity (same rate) |
| Velocity (locxs/locys) | 100 Hz | ~1:2 with angle (200 Hz) |
| Angle (pitch/roll/yaw) | 200 Hz | ~1:1 with rate (same rate) |
| Rate (gyrox/gyroy/gyroz) | 200 Hz | Inner-most |

**Observation**: The 100 Hz → 200 Hz → 200 Hz frequency hierarchy gives only a 2:1 ratio between position/velocity and angle/rate loops, which is tighter than the textbook 5–10× recommendation. In practice this works because (a) the position PID has relatively gentle gains (Kp = 0.8) that don't excite the angle loop's bandwidth, and (b) the derivative terms in the angle PID (Kd = 8) provide phase lead that compensates for the reduced frequency separation.

### Rule 2: Tune Inner Loops First, Then Outer

The tuning sequence must proceed from innermost to outermost:

1. **Rate PID** (gyrox/gyroy/gyroz) — tune Kp/Kd first with integral off, then add Ki for steady-state
2. **Angle PID** (pitch/roll) — tune Kp/Kd assuming rate loop tracks perfectly
3. **Yaw PID** — tune separately (different dynamics, no coupling to position)
4. **Height PID** (Z_pos → Z_rate) — requires working attitude control
5. **Velocity PID** (locxs/locys) — requires working height hold
6. **Position PID** (locx/locy) — requires working velocity control

This ordering matters because each outer loop assumes the inner loop is a well-behaved "virtual actuator." If you change the rate PID gains, every outer loop's effective plant changes, potentially requiring re-tuning. See [[Tuning Workflow]] for the practical procedure.

### Rule 3: Inner Loops Reject Disturbances Before Outer Loops See Them

A gust hitting the propellers creates an angular rate disturbance. The rate PID rejects it within a few milliseconds (200 Hz, Kp = 5). The angle PID never sees more than a small transient deviation. The position PID sees even less.

This disturbance rejection cascade is the primary engineering reason for cascade structure. A single loop from position to motor would need extremely high bandwidth to reject rate-level disturbances, which is impractical with position sensor latency.

---

## 4. Anti-Windup Strategy

### 4.1 The Problem

PID integrators accumulate error over time to eliminate steady-state offset. But when the output is saturated (e.g., motor at maximum), the integral keeps growing even though increasing the output has no effect. When the saturation condition ends, the accumulated integral causes a large overshoot — "integrator windup."

### 4.2 This Code's Approach: Integral Separation + Per-Term Clamping

The anti-windup in `ComputePID()` (`pid.c:32–54`) uses two mechanisms:

**Mechanism 1 — Integral separation** (`pid.c:36–40`):

```c
if(((pPID->U <= pPID->UMax && pPID->E > 0) || 
    (pPID->U >= -pPID->UMax && pPID->E < 0))
    && ABS(pPID->E) < pPID->EMin)
{
    pPID->SumE += pPID->E;
}
```

The integral only accumulates when two conditions are met:
1. **Output is not saturated** in the same direction as the error — if U is at +UMax and E is positive, adding more integral won't help
2. **Error is below EMin** — this "integral separation" threshold prevents the integral from engaging during large transients. Only when the error is small (near steady state) does the integral activate to eliminate the remaining offset.

The `EMin` values are configured per-loop:
- Rate loops: EMin = 2°/s (integral only engages within ±2°/s of setpoint)
- Angle loops: EMin = 3° (integral only within ±3° of target)
- Yaw rate: EMin = 20°/s (very wide, reflecting yaw's slower dynamics)

**Mechanism 2 — Per-term clamping** (`pid.c:41–52`):

```c
value_limit(pPID->SumE, -pPID->SumEMax, pPID->SumEMax);  // Integral accumulator
pPID->Ui = pPID->Ki * pPID->SumE;
value_limit(pPID->Ui, -pPID->UiMax, pPID->UiMax);         // Integral output
pPID->Up = pPID->Kp * pPID->E;
value_limit(pPID->Up, -pPID->UpMax, pPID->UpMax);         // Proportional output
pPID->Ud = pPID->Kd * (pPID->E - pPID->PreE);
value_limit(pPID->Ud, -pPID->UdMax, pPID->UdMax);         // Derivative output
pPID->U = pPID->Up + pPID->Ui + pPID->Ud;
value_limit(pPID->U, -pPID->UMax, pPID->UMax);            // Total output
```

Four independent clamps:
1. `SumEMax` — limits the integral accumulator itself (prevents runaway integration)
2. `UiMax` — limits the integral contribution to output
3. `UpMax` — limits the proportional contribution
4. `UdMax` — limits the derivative contribution (prevents derivative kick on step changes)
5. `UMax` — final total output clamp

This is more conservative than textbook back-calculation anti-windup, but simpler to implement and tune. The per-term clamping ensures that no single PID term can dominate the output.

### 4.3 Integral Reset on Disarm

When the drone is disarmed, `Clear_Structure()` (`pid.c:148–167`) zeros all integral accumulators:

```c
Ctrler.pitchPID.SumE = 0;
Ctrler.rollPID.SumE = 0;
// ... all axes
```

It also resets position setpoints to current position (`locxPID.Des = locxPID.FB`), preventing a position jump on the next arm.

---

## 5. Body-to-World Rotation in Position Control

### The Problem

The position PID computes errors in the world (earth) frame, but the vehicle must tilt in its body frame to move. If the vehicle is yawed 90°, a world-X position error requires a body-Y (roll) correction, not a body-X (pitch) correction.

### The Solution

The error rotation in `ComputePID_locx/locy` (`pid.c:90–146`) applies a yaw rotation matrix:

```
[e_body_x]   [cos(-ψ)  -sin(-ψ)] [e_world_x]
[e_body_y] = [sin(-ψ)   cos(-ψ)] [e_world_y]
```

where ψ is the current yaw angle. The negative sign in `cos(-yaw)` / `sin(-yaw)` (`StabilizerTask.c:98–99`) transforms from world to body frame.

Similarly, the velocity-to-angle conversion at `StabilizerTask.c:450–451` applies the same rotation:

```c
des_pitch = (Ctrler.locysPID.U) * Cos_Yaw_01 + (Ctrler.locxsPID.U) * Sin_Yaw_01;
des_roll  = (Ctrler.locxsPID.U) * Cos_Yaw_01 - (Ctrler.locysPID.U) * Sin_Yaw_01;
```

This ensures that the vehicle always corrects position errors by tilting in the correct direction regardless of its current heading.

---

## 6. Evidence vs. Inference

### Verified from Code

- 4-level cascade: position → velocity → angle → rate, all in `Compute_Motor()` (`StabilizerTask.c:237–353`)
- Position/velocity loops decimated to 100 Hz via `cnt_loc` and `cnt_h` counters (`StabilizerTask.c:243, 252`)
- All PID gain values from `pid.c:3–28`
- Integral separation condition at `pid.c:36–40` with EMin threshold
- Four levels of clamping: SumE, Ui, Up, Ud, U (`pid.c:41–52`)
- Yaw wrapping ±180° in `ComputeYawPID` (`pid.c:62–63`)
- World-to-body rotation in `ComputePID_locx/locy` (`pid.c:94, 123`)
- `Clear_Structure()` zeros all integrals and resets position setpoints (`pid.c:148–167`)
- `accel_to_lean_angles()` converts velocity PID output to angle setpoint with cos compensation (`StabilizerTask.c:503–519`)

### Inferred / Theoretical Context

- The "5–10× bandwidth separation rule" is a standard cascade design heuristic (Åström & Murray, Ch. 11); this firmware's 2:1 ratio is tighter than typical recommendations
- The integral separation technique is commonly used in Chinese quadrotor control literature and flight controller firmware (e.g., ANO FC)
- The assertion that derivative terms compensate for reduced frequency separation is a linearized analysis argument

---

## 7. Further Reading

- **Cascade PID for quadrotors**: Bouabdallah et al. 2004 (IROS) — experimental comparison of PID vs. LQ on a quadrotor
- **Anti-windup survey**: L. Zaccarian, A. R. Teel, *"Modern Anti-Windup Synthesis,"* Princeton Univ. Press, 2011
- **This codebase**: [[PID Controller]] for function-level docs, [[Tuning Workflow]] for practical procedures
- **Adaptive augmentation**: [[MRAC Theory]] for how MRAC compensates for cascade PID limitations
