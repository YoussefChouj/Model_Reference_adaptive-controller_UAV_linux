# Mahony Filter Theory

> Maps the Mahony 2008 nonlinear complementary filter to the firmware implementation in `API/imu_update.c`.

**Source paper**: R. Mahony, T. Hamel, J.-M. Pflimlin, *"Nonlinear Complementary Filters on the Special Orthogonal Group,"* IEEE Trans. Automatic Control, vol. 53, no. 5, pp. 1203–1217, June 2008.
DOI: [10.1109/TAC.2008.919528](https://doi.org/10.1109/TAC.2008.919528)

**Related wiki**: [[IMU Update]], [[Multi-rate Task Partitioning]], [[Data Dictionary]]

---

## 1. The Problem: Attitude from Noisy Sensors

A quadrotor needs its orientation (roll, pitch, yaw) at 1 kHz. It has two sensor sources:

| Sensor | Measures | Strength | Weakness |
|--------|----------|----------|----------|
| Gyroscope | Angular velocity ω | High bandwidth, low noise | Integrates drift (bias) |
| Accelerometer | Specific force (≈ gravity when hovering) | No drift | Noisy, corrupted by maneuvers |

The Mahony filter fuses these two sources using a **PI correction on the rotation group SO(3)**, producing a drift-free attitude estimate that responds quickly to angular changes.

---

## 2. The SO(3) Observer Structure

### 2.1 Core Idea

The filter maintains an estimated orientation as a **unit quaternion** q̂. Each timestep:

1. **Predict**: Propagate q̂ forward using gyroscope angular velocity ω
2. **Correct**: Compute the *attitude error* between where the accelerometer says "down" is vs. where the current estimate says "down" is
3. **Apply PI correction**: Feed this error back into the gyro integration as a proportional (Kp) and integral (Ki) correction

This is a nonlinear observer on SO(3), not a linearized Kalman filter. The key insight from Mahony's paper (Section III, Theorem 1) is that the cross-product between the measured gravity direction and the estimated gravity direction provides an error signal that is almost-globally asymptotically stable.

### 2.2 The Cross-Product Error

The estimated gravity vector in the body frame is extracted from the current quaternion as the third column of the rotation matrix R(q̂):

```
v̂_z = R(q̂)ᵀ · [0, 0, 1]ᵀ
```

This gives three components (the "estimated down" direction in body coordinates). The error between measured and estimated gravity is:

```
ω_err = a_normalized × v̂_z
```

where `a_normalized` is the accelerometer reading normalized to unit length. The cross product magnitude is proportional to sin(θ) where θ is the tilt error — for small angles this is approximately θ itself.

### 2.3 The PI Correction Law

The corrected gyroscope reading fed into quaternion propagation is:

```
ω_corrected = ω_raw + Kp · ω_err + Ki · ∫ω_err dt
```

- **Kp** (proportional): Controls how aggressively the filter corrects toward the accelerometer. Larger Kp = faster convergence but more accelerometer noise coupling.
- **Ki** (integral): Slowly estimates and removes gyroscope bias drift. Smaller Ki = slower bias convergence but less susceptibility to sustained accelerometer errors.

---

## 3. Mapping Paper to Code

### 3.1 Variable Correspondence

| Paper symbol | Code variable | File:Line | Description |
|:---|:---|:---|:---|
| q̂ = [q₀, q₁, q₂, q₃] | `q0, q1, q2, q3` | `imu_update.c:27–30` | Unit quaternion (scalar-first convention) |
| kₚ | `Kp = 0.5f` | `imu_update.c:20` | Proportional correction gain |
| kᵢ | `Ki = 0.001f` | `imu_update.c:21` | Integral correction gain (bias estimator) |
| ∫ω_err dt | `exInt, eyInt, ezInt` | `imu_update.c:23–25` | Accumulated integral error (gyro bias estimate) |
| ω_err | `ex, ey, ez` | `imu_update.c:47` | Cross-product attitude error |
| v̂_z (estimated down) | `vecxZ, vecyZ, veczZ` | `imu_update.c:50` | Third column of R(q̂), computed from quaternion |
| a_normalized | `nor_acc[X], nor_acc[Y], nor_acc[Z]` | `imu_update.c:46` | Normalized accelerometer |
| ω_raw | `Gyro_X_Real, Gyro_Y_Real, Gyro_Z_Real` | Globals from sensor driver | Raw gyroscope in rad/s |
| Δt | `dt` parameter (1e-3f) | `imu_update.c:43` | Task period, passed from `IMU_DataDeal_Task` |
| Δt/2 | `half_T` | `imu_update.c:53` | Half-step for quaternion integration |

### 3.2 Step-by-Step Code Walkthrough

**Step 1 — Normalize accelerometer** (`imu_update.c:63–73`)

The code skips correction entirely if all accelerometer axes read zero (degenerate case). Otherwise it normalizes to unit length using the fast inverse square root (`invSqrt`, line 33–42):

```c
normalise = invSqrt(nor_acc[X]*nor_acc[X] + nor_acc[Y]*nor_acc[Y] + nor_acc[Z]*nor_acc[Z]);
nor_acc[X] *= normalise;
nor_acc[Y] *= normalise;
nor_acc[Z] *= normalise;
```

The `invSqrt` function at line 33 uses the classic Quake III fast inverse square root (Newton's method, single iteration). This trades ~0.17% accuracy for avoiding the FPU `sqrt` + `div` pipeline stall — critical at 1 kHz on Cortex-M4.

**Step 2 — Cross-product error** (`imu_update.c:77–79`)

```c
ex = (nor_acc[Y] * veczZ - nor_acc[Z] * vecyZ);
ey = (nor_acc[Z] * vecxZ - nor_acc[X] * veczZ);
ez = (nor_acc[X] * vecyZ - nor_acc[Y] * vecxZ);
```

This is `ω_err = a_norm × v̂_z`, the cross product of the normalized accelerometer with the estimated gravity direction. The result is a 3-vector in body coordinates whose magnitude is approximately proportional to attitude error.

**Step 3 — Integral accumulation (bias estimator)** (`imu_update.c:82–84`)

```c
exInt += Ki * ex * dt;
eyInt += Ki * ey * dt;
ezInt += Ki * ez * dt;
```

This implements `∫ω_err dt` using forward Euler integration. The integral terms `exInt/eyInt/ezInt` slowly converge to the gyroscope bias, compensating for sensor imperfection. Note: there is **no anti-windup** on these integrals — if the accelerometer is persistently wrong (e.g., sustained maneuver), the integrals will accumulate error that takes time to unwind.

**Step 4 — PI correction applied to gyro** (`imu_update.c:87–89`)

```c
Gyro_X_Real += Kp * ex + exInt;
Gyro_Y_Real += Kp * ey + eyInt;
Gyro_Z_Real += Kp * ez + ezInt;
```

The raw gyro readings are **modified in-place** with the PI correction. After this line, `Gyro_X/Y/Z_Real` contains the corrected angular velocity that will drive quaternion propagation. This is the direct complementary filter form from Mahony's paper (Equation 46, Appendix B).

**Step 5 — Quaternion propagation** (`imu_update.c:93–109`)

The corrected angular velocity is converted to a half-angle rotation vector:

```c
delta_theta[0] = Gyro_X_Real * half_T;  // half_T = 0.5 * dt
delta_theta[1] = Gyro_Y_Real * half_T;
delta_theta[2] = Gyro_Z_Real * half_T;
```

Then the quaternion is updated using a **second-order expansion** (not the simple first-order form):

```c
// Second-order: Q(k+1) = ((1 - |δθ|²)I + δθ×) · Q(k)
q0 = q0Last*(1-delta_theta_s) - q1Last*delta_theta[0] - q2Last*delta_theta[1] - q3Last*delta_theta[2];
q1 = q1Last*(1-delta_theta_s) + q0Last*delta_theta[0] + q2Last*delta_theta[2] - q3Last*delta_theta[1];
q2 = q2Last*(1-delta_theta_s) + q0Last*delta_theta[1] - q1Last*delta_theta[2] + q3Last*delta_theta[0];
q3 = q3Last*(1-delta_theta_s) + q0Last*delta_theta[2] + q1Last*delta_theta[1] - q2Last*delta_theta[0];
```

where `delta_theta_s = δθ₀² + δθ₁² + δθ₂²`. The `(1 - |δθ|²)` factor is a second-order correction from the Cayley–Hamilton expansion of the matrix exponential, which gives better norm preservation than the first-order (commented out at lines 99–102). The commented-out first-order form is the standard `q += 0.5 * q ⊗ [0, ω·dt]` from many textbooks.

**Step 6 — Quaternion normalization** (`imu_update.c:112–116`)

```c
normalise = invSqrt(q0*q0 + q1*q1 + q2*q2 + q3*q3);
q0 *= normalise; q1 *= normalise; q2 *= normalise; q3 *= normalise;
```

This is **mandatory every step**. Numerical integration causes the quaternion norm to drift from 1.0. Without re-normalization, the quaternion ceases to represent a valid rotation after a few hundred steps. The second-order propagation reduces but does not eliminate this drift.

**Step 7 — Rotation matrix elements and Euler angles** (`imu_update.c:118–137`)

The code extracts specific elements of the rotation matrix R(q):

```c
R11 = q0s + q1s - q2s - q3s;   // R(1,1) — used for yaw via atan2
R21 = 2*(q1*q2 + q0*q3);       // R(2,1) — used for yaw via atan2

vecxZ = 2*(q1*q3 - q0*q2);     // R(3,1) — pitch via asin
vecyZ = 2*(q0*q1 + q2*q3);     // R(3,2) — roll via atan2
veczZ = q0s - q1s - q2s + q3s; // R(3,3) — roll via atan2
```

The `vecxZ/vecyZ/veczZ` components serve double duty: they are both the estimated gravity direction (fed back into Step 2 next iteration) and the rotation matrix elements used for Euler angle extraction:

```c
imu->pit = -asinf(vecxZ) * RAD2DEG;         // pitch = -asin(R31)
imu->rol = atan2f(vecyZ, veczZ) * RAD2DEG;  // roll = atan2(R32, R33)
imu->yaw = atan2f(R21, R11) * RAD2DEG;      // yaw = atan2(R21, R11)
```

The negative sign on pitch is a coordinate convention choice — see [[Coordinate Conventions]].

---

## 4. Gain Selection: Why Kp = 0.5, Ki = 0.001

### 4.1 Kp — Proportional Gain

Kp controls the **convergence bandwidth** of the attitude correction. With the cross-product error proportional to sin(θ) ≈ θ for small angles, the linearized correction dynamics are approximately first-order with time constant τ ≈ 1/Kp.

| Kp value | τ_convergence | Behavior |
|----------|:---:|---|
| 0.1 | ~10 s | Slow correction, minimal accel noise coupling |
| **0.5** | **~2 s** | **Moderate — balances speed vs. noise** |
| 2.0 | ~0.5 s | Fast correction, but accel vibrations directly affect attitude |

For a quadrotor experiencing vibration from propellers, Kp = 0.5 is a conservative choice that allows the gyro to dominate short-term attitude tracking while the accelerometer slowly pulls the estimate toward truth.

### 4.2 Ki — Integral Gain

Ki determines how fast the gyro bias estimate converges. The bias estimator time constant is approximately τ_bias ≈ 1/Ki.

| Ki value | τ_bias | Behavior |
|----------|:---:|---|
| 0.01 | ~100 s | Fast bias tracking, but susceptible to sustained maneuver artifacts |
| **0.001** | **~1000 s** | **Very slow — safe, robust to maneuvers** |
| 0.0001 | ~10000 s | Almost no bias tracking, gyro drift accumulates |

Ki = 0.001 is extremely conservative — it takes ~15 minutes for the bias estimate to fully converge. This is appropriate because gyro bias is a slowly-varying physical property (temperature drift), and aggressive Ki would cause the bias estimate to track maneuver-induced accelerometer errors as if they were bias.

### 4.3 The Ratio Matters

The ratio Kp/Ki ≈ 500 means the proportional correction dominates by a factor of 500x. The integral is essentially a very slow "trim" adjustment. If the drone is in sustained forward flight (accelerometer sees gravity + centripetal), the proportional term pulls the estimate wrong, but only by ~2°. The integral doesn't have time to accumulate significant error before the maneuver ends.

---

## 5. When the Filter Assumptions Break

The Mahony filter assumes the accelerometer measures **only gravity**. This assumption breaks under:

| Condition | Effect on Filter | Mitigation in This Code |
|-----------|-----------------|------------------------|
| **High vibration** (propeller harmonics) | Noisy Kp correction, jittery attitude | Kp = 0.5 limits coupling; `invSqrt` normalization rejects magnitude noise |
| **Sustained acceleration** (aggressive maneuver) | Pitch/roll error up to atan(a_maneuver / g) | Conservative Kp/Ki limits; error self-corrects when maneuver ends |
| **Free fall / zero-g** | Accelerometer reads zero; cross-product meaningless | Line 63: `if((Acc_X_Real != 0) || ...)` skips correction entirely |
| **Magnetic interference** | N/A — this filter does not use magnetometer | Yaw drifts over time (gyro-only for yaw); see [[Common Pitfalls]] |

**Critical limitation**: Because this implementation does not incorporate a magnetometer, the yaw angle relies entirely on gyroscope integration with no absolute reference. Yaw will drift over time, bounded only by the tiny Ki correction from any residual cross-coupling in the accelerometer error. For missions requiring heading hold, an external heading source (magnetometer, visual odometry, T265) must feed the yaw PID setpoint — see [[Coordinate Conventions]] and [[AutoflyTask]].

---

## 6. Evidence vs. Inference

### Verified from Code

- Kp = 0.5, Ki = 0.001 (exact values, `imu_update.c:20–21`)
- Second-order quaternion propagation with Cayley–Hamilton correction (`imu_update.c:106–109`)
- Fast inverse square root for normalization (`imu_update.c:33–42`)
- No magnetometer fusion (no mag-related code in the function)
- No anti-windup on integral terms (no clamping on `exInt/eyInt/ezInt`)
- `dt` passed as argument, called with `1e-3f` from `IMU_DataDeal_Task` (`main.c:150`)

### Inferred / Theoretical Context

- Time constant estimates (τ ≈ 1/Kp, τ_bias ≈ 1/Ki) are linearized approximations valid for small angles
- The claim that the second-order propagation is "Cayley–Hamilton" follows from the structure `(1 - |δθ|²)I + δθ×` matching the matrix exponential truncation, but the code comments just say "second order" (line 105)
- The sensor driver is `bmi088_init()` (called from `BSP/BSP.c:14`), not MPU6050 — the filter itself is driver-agnostic as it reads from globals `Acc_X/Y/Z_Real` and `Gyro_X/Y/Z_Real`

---

## 7. Further Reading

- **Original paper (full)**: Mahony et al. 2008, IEEE TAC vol. 53 no. 5 — Sections III (direct complementary filter) and Appendix B (quaternion form) are the most relevant
- **Practical tuning guide**: S. Madgwick, "An efficient orientation filter for inertial and inertial/magnetic sensor arrays," 2010 — compares Mahony vs. gradient descent approaches
- **This codebase**: [[IMU Update]] for the entity-level documentation of `imu_update.c`
