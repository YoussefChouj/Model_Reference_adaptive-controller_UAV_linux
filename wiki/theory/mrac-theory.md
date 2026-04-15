# MRAC Theory

> Maps Model Reference Adaptive Control theory to the firmware implementation in `API/mrac.h`, `API/mrac_math.c`, and `TASK/StabilizerTask.c`.

**Primary sources**:
- T. Yucelen, A. J. Calise, *"Derivative-Free Model Reference Adaptive Control,"* AIAA J. Guidance, Control, and Dynamics, vol. 35, no. 4, pp. 1124–1132, 2012. DOI: [10.2514/1.56158](https://doi.org/10.2514/1.56158)
- E. Lavretsky, K. Wise, *"Robust and Adaptive Control with Aerospace Applications,"* Springer, 2013 — Ch. 9–11 for standard MRAC, Ch. 12 for projection.
- T. Yucelen et al., *"Experimental Results of a Quadrotor UAV with a Model Reference Adaptive Controller,"* AIAA SciTech, 2022 — directly relevant to this use case.
- T. Yucelen et al., *"A Hybrid Model Reference Adaptive Control System for Multi-Rotor UAVs,"* AIAA SciTech, 2024.

**Related wiki**: [[MRAC Control Law]], [[StabilizerTask]], [[PID Controller]], [[Data Dictionary]]

---

## 1. What MRAC Does and Why It's Here

The PID controllers in this firmware (see [[PID Controller]]) are tuned for a *nominal* plant: known mass, known inertia, no wind, no payload shift. When the actual plant differs — heavier payload, motor degradation, aerodynamic drag, CG offset — PID gains are no longer optimal and performance degrades.

MRAC augments the PID baseline by **learning the mismatch online** and generating an adaptive correction signal `u_ad` that compensates for the difference between the assumed and actual plant dynamics. The total control is:

```
u_total = u_nom (from PID) + u_ad (from MRAC)
```

The key guarantee: under certain conditions (matched uncertainty, bounded disturbances), the tracking error between the plant and a reference model converges to a bounded neighborhood of zero, regardless of the specific plant parameters.

---

## 2. The Standard MRAC Architecture

### 2.1 Reference Model

For each controlled axis (pitch rate, roll rate, yaw rate, z rate), a first-order reference model defines the *desired* closed-loop behavior:

```
ẋ_m = A_m · x_m + B_m · r
```

where:
- `x_m` is the reference state (desired rate trajectory)
- `r` is the reference command (from the outer PID loop)
- `A_m` is Hurwitz (stable) — determines how fast the reference model responds
- `B_m` scales the command input

In this codebase, the reference model is implemented as a simple first-order low-pass of the PID rate command. The `MRAC_AxisConfig_t` struct has `ref_model_bw` (`mrac.h:240`) reserved for configuring the bandwidth, though the current implementation uses a simplified form.

**Code mapping**: `mrac_state.pitch.xm` (`mrac.h:248`) holds the reference model state for the pitch axis.

### 2.2 Tracking Error

The tracking error between the actual plant and reference model drives all adaptation:

```
e = x - x_m
```

**Code mapping**: `mrac_state.pitch.e` (`mrac.h:254`) — computed each cycle as the difference between measured gyro rate and reference state.

### 2.3 The Adaptive Law

The core of MRAC is the weight update that learns the plant-model mismatch. In the standard formulation:

```
Θ̇ = -Γ · Φ(x) · eᵀ · P · B
```

where:
- **Θ** (Theta) = adaptive weight vector — the "learned" parameters
- **Γ** (Gamma) = learning rate matrix (positive definite, diagonal in this implementation)
- **Φ(x)** = regressor (basis function) vector — features of the current state
- **e** = tracking error
- **P** = Lyapunov matrix (solution to `A_mᵀP + PA_m = -Q`)
- **B** = control effectiveness matrix

For the scalar (SISO) case used per-axis in this code, this simplifies to:

```
Θ̇ᵢ = -γᵢ · Φᵢ(x) · e · P · B
```

### 2.4 Adaptive Control Output

The adaptive signal is the inner product of learned weights and basis functions:

```
u_ad = Θᵀ · Φ(x)
```

**Code mapping**: `mrac_state.pitch.u_ad` (`mrac.h:268`) — the scalar output injected into the motor mixer at `StabilizerTask.c:299–302`.

---

## 3. Mapping Theory to Code Variables

### 3.1 Per-Axis State (`MRAC_AxisState_t`, `mrac.h:246–272`)

| Theory symbol | Code field | Type | Description |
|:---|:---|:---|:---|
| x_m | `xm` | float | Reference model state |
| x | `x` | float | Actual plant state (measured rate) |
| e = x − x_m | `e` | float | Tracking error |
| Φ(x) | `Phi[MAX_NUM_BASIS]` | float[] | Regressor/basis function vector |
| Θ | `Theta[MAX_NUM_BASIS]` | float[] | Adaptive weight vector |
| Θ_f (filtered) | `Whatf[MAX_NUM_BASIS]` | float[] | Low-frequency filtered weights (L1-style) |
| u_nom | `u_nom` | float | Nominal control from PID |
| u_ad | `u_ad` | float | Adaptive correction output |
| u_def | `u_def` | float | Saturation deficit for pseudo control hedging |

### 3.2 Per-Axis Configuration (`MRAC_AxisConfig_t`, `mrac.h:198–243`)

| Theory symbol | Code field | Description |
|:---|:---|:---|
| Γ (diagonal) | `gamma[MAX_NUM_BASIS]` | Per-weight learning rates |
| σ_lf | `sigma_lf` | Low-frequency leakage coefficient |
| σ | `sigma` | Sigma-modification leakage |
| ω_u | `omega_u` | L1-style low-pass cutoff for u_ad |
| W_max | `What_limit[MAX_NUM_BASIS]` | Per-component projection bounds |
| W_tol | `What_tol[MAX_NUM_BASIS]` | Soft boundary tolerance (smooth projection zone) |
| λ_perf | `lambda_perf` | State predictor bandwidth (performance recovery) |
| τ_v | `tau_v` | Low-pass time constant for performance recovery signal |
| u_max | `u_max` | Maximum control torque/force |
| J | `J` | Moment of inertia (rotational) or mass (Z axis) |
| P | `P_lyap` | Lyapunov matrix scalar (default 1.0) |

### 3.3 Feature Flags (`MRAC_FeatureFlags_t`, `mrac.h:282–293`)

| Flag | Purpose | Theory connection |
|:---|:---|:---|
| `adaptation_on` | Master switch | Freeze all weight updates |
| `projection_on` | Weight bounding | Enables the projection operator (Section 4) |
| `deadzone_on` | Gradient deadzone | Stops learning when error is below noise floor |
| `hard_freeze_on` | Safety freeze | Zeros u_ad when error exceeds `e_freeze` threshold |
| `tanh_saturation_on` | Soft saturation | Applies tanh to PBe signal for gradient smoothness |
| `e_modification_on` | e-modification | Extra leakage proportional to |e| |
| `l1_filtering_on` | L1 low-pass | Filters u_ad to reject high-frequency transients |

---

## 4. The Projection Operator

### 4.1 Why Projection Is Necessary

Without bounds, the adaptive weights Θ can grow without limit — especially if the regressor Φ is persistently excited in one direction (e.g., constant wind disturbance). Unbounded weights lead to large u_ad signals that can destabilize the system.

The projection operator modifies the adaptive law so that Θ stays within a known safe region, while preserving the Lyapunov stability proof. From Lavretsky & Wise (2013, Ch. 12):

```
Θ̇ = Proj(Θ, -Γ · Φ · e · P · B)
```

where Proj(Θ, y) equals y when Θ is far from the boundary, gradually attenuates y as Θ approaches the boundary, and equals 0 (or allows only inward motion) when Θ is at the boundary.

### 4.2 Implementation in `mrac_math.c:18–40`

```c
float MRAC_Projection(float theta, float y, float w_max, float tol)
{
    float abs_theta = fabsf(theta);
    
    // Region 1: Well inside bounds — return y unchanged
    if (abs_theta <= (w_max - tol)) {
        return y;
    }
    
    // Region 2: At boundary but pushing inward — allow full learning
    if ((theta > 0.0f && y < 0.0f) || (theta < 0.0f && y > 0.0f)) {
        return y;
    }
    
    // Region 3: Outside boundary pushing outward — hard stop
    if (abs_theta >= w_max) {
        return 0.0f;
    }
    
    // Region 4: In tolerance zone pushing outward — smooth scale-down
    float scale = (w_max - abs_theta) / tol;
    return y * scale;
}
```

This implements a smooth, convex projection operator with four regions:

```
    ← ALLOW →  ← SCALE →  ← STOP →
    |          |          |
    0    w_max-tol    w_max    |theta|
```

The tolerance zone (`tol`) prevents discontinuous jumps in the control signal. The `What_tol` arrays in `mrac.h:149–151` are set to 20% of `What_limit`, giving a smooth transition region.

### 4.3 Physical Meaning of Projection Bounds

The comments in `mrac.h:107–136` provide detailed physical derivations for each bound. The key idea: `What_limit[i]` is set so that the maximum adaptive torque from component i does not exceed what the actuators can physically produce.

For pitch/roll (from `mrac.h:112–123`):

| Basis component | What_limit | Max torque contribution | Physical meaning |
|:---|:---|:---|:---|
| bias (i=0) | 0.50 | 0.50 Nm | CG offset up to 14mm |
| angle (i=1) | 1.00 | 0.524 Nm at 30° | Spring stiffness error up to 1.0 Nm/rad |
| rate (i=2) | 0.10 | 0.105 Nm | Damping error ΔB ≤ 0.10 Nm/(rad/s) |
| drag (i=3) | 0.05 | 0.052 Nm | Nonlinear drag error |
| un/LOE (i=4) | 0.80 | Up to 80% LOE recovery | Motor loss-of-effectiveness |
| v/perf (i=5) | 0.20 | Performance recovery ≤ 20% of v | L1 state predictor correction |

---

## 5. Regressor Types: Structured vs. Unstructured

The firmware supports two uncertainty models, selected at compile time (`mrac.h:46–47`):

### 5.1 Structured Uncertainty (`USE_STRUCTURED_UNCERTAINTY = 1`, default)

The regressor Φ uses physics-based features that directly correspond to known dynamic effects:

```
Φ = [1, angle, rate, drag_term, u_nom, v]
```

where:
- `1` = constant bias (handles gravity offsets, CG errors)
- `angle` = attitude angle (handles restoring torque errors)
- `rate` = angular rate (handles damping coefficient errors)
- `drag_term` = nonlinear drag (handles aerodynamic uncertainty)
- `u_nom` = nominal control input (handles actuator effectiveness errors / LOE)
- `v` = performance recovery signal (L1-style correction)

With `INCLUDE_CONTROL_IN_REGRESSOR = 1`, `MAX_NUM_BASIS = 6` (`mrac.h:78`). Without, `MAX_NUM_BASIS = 4`.

### 5.2 Unstructured Uncertainty (`USE_UNSTRUCTURED_UNCERTAINTY = 1`)

Uses Radial Basis Functions (RBFs) — Gaussian kernels centered at different operating points:

```
Φᵢ(x) = exp(-width · (x - cᵢ)²)
```

Implemented in `mrac_math.c:49–56`:

```c
float MRAC_Simple_RBF(float x, float c, float width)
{
    float dist_sq = (x - c) * (x - c);
    return expf(-width * dist_sq);
}
```

RBFs can approximate arbitrary nonlinear functions (universal approximation), but at higher computational cost and with less interpretable weights. The structured model is recommended (`mrac.h:46`) because the quadrotor dynamics are well-understood and the basis functions have clear physical meaning.

---

## 6. Learning Rate Selection

The per-component learning rates `gamma[i]` (`mrac.h:210`) are set according to:

```
γᵢ = γ_base / (typical |θᵢ|²)
```

This compensates for the fact that different regressors have different magnitudes. Without this normalization, the basis function with the largest typical value would dominate learning.

From `mrac.h:203–209`:

| Component | Typical |θ| | γ value (pitch) | Rationale |
|:---|:---|:---|:---|
| bias | 1.0 | 0.50 | θ² = 1.0, needs least gain |
| angle | ~0.15 rad | 3.30 | θ² = 0.023, needs 44x more gain |
| rate | ~0.5 rad/s | 1.00 | θ² = 0.25 |
| drag | ~0.25 | 2.00 | θ² = 0.063 |

When `ENABLE_WEIGHT_NORMALIZATION = 1` (`mrac.h:54`), the adaptive law additionally normalizes by `(1 + ‖Φ‖²)` to prevent large regressor signals from causing weight jumps. The norm-squared is computed by `MRAC_VectorNormSquare()` in `mrac_math.c:64–73`.

---

## 7. Robustness Modifications

The firmware layers multiple robustness modifications on top of the basic adaptive law. Each addresses a specific failure mode:

### 7.1 Sigma-Modification (`ENABLE_SIGMA_MODIFICATION`, `mrac.h:53`)

Adds a leakage term that slowly pulls weights toward zero:

```
Θ̇ᵢ = -γᵢ · Φᵢ · e · P · B  -  σ · Θᵢ
```

This prevents weight drift when the system is in steady state (e ≈ 0) and the adaptation law has no driving signal. Without it, weights can "remember" transient disturbances long after they've passed. Controlled by `sigma` in `MRAC_AxisConfig_t` (`mrac.h:212`).

### 7.2 e-Modification (`ENABLE_DEADZONE`, `mrac.h:63` / `k_e` in config)

Adds leakage proportional to the tracking error magnitude:

```
Θ̇ᵢ += -k_e · |e| · Θᵢ
```

When the error is large (transient, not a steady disturbance), this accelerates weight decay. When e is small (near equilibrium), the extra leakage vanishes.

### 7.3 Deadzone (`ENABLE_DEADZONE`, `mrac.h:63`)

Stops learning entirely when |e| falls below a noise-floor threshold `e_deadzone` (`mrac.h:234`). Without this, sensor noise constantly drives small weight updates that accumulate into drift.

### 7.4 Hard Freeze (`e_freeze` in `MRAC_AxisConfig_t`, `mrac.h:235`)

When |e| exceeds `e_freeze`, both u_ad and weight updates are zeroed. This is a safety mechanism: if the tracking error is so large that the adaptive controller is clearly not helping (e.g., during arming transient, propeller strike), it's safer to fall back to PID-only control.

### 7.5 L1-Style Filtering (`ENABLE_LOW_FREQ_LEARNING`, `mrac.h:55`)

Instead of injecting raw u_ad into the control loop, the adaptive signal is passed through a low-pass filter:

```
u_ad_filtered = LPF(u_ad, ω_u)
```

This is inspired by L1 adaptive control (Hovakimyan & Cao, 2010). The filter removes high-frequency transients from the adaptive signal, preventing the controller from reacting to fast disturbances that the adaptation bandwidth cannot accurately track. Controlled by `omega_u` and `gam_f` in `MRAC_AxisConfig_t` (`mrac.h:213–214`).

### 7.6 Pseudo Control Hedging (`ENABLE_PSEUDO_CONTROL_HEDGING`, `mrac.h:64`)

When the total control command exceeds the actuator limits (mixer saturation), the excess `u_def = u_cmd - u_actual` is fed back to the reference model to prevent the adaptive law from "seeing" an error caused by saturation rather than model mismatch. This prevents adaptation windup. Tracked in `u_def` (`mrac.h:271`).

---

## 8. Control Flow in StabilizerTask

The MRAC controller is invoked after all PID loops complete, in `Compute_Motor()` (`StabilizerTask.c:286`):

```c
MRAC_Control(&Ctrler);
```

The adaptive outputs are injected into the motor mixer at `StabilizerTask.c:293–311`:

```c
float mrac_z     = mrac_state.z_rate.u_ad * mrac_config_z.mrac_to_mixer;
float mrac_roll  = mrac_state.roll.u_ad  * mrac_config_roll.mrac_to_mixer;
float mrac_pitch = mrac_state.pitch.u_ad * mrac_config_pitch.mrac_to_mixer;
float mrac_yaw   = mrac_state.yaw.u_ad   * mrac_config_yaw.mrac_to_mixer;
```

The `mrac_to_mixer` scaling factors (`mrac.h:30–41`) convert from physical units (Nm or N) to PWM mixer units. These are payload-dependent:

| Payload | PR scaler | Yaw scaler | Z scaler |
|:---|:---|:---|:---|
| PAYLOAD_LIGHT (~0.5 kg) | 1170.0 | 1872.0 | 222.0 |
| PAYLOAD_HEAVY (~1.5 kg) | 286.0 | 458.0 | 54.0 |

A NaN/Inf guard (`StabilizerTask.c:303–306`) protects against diverged weights — if any `u_ad * scaler` is not finite, it falls back to 0.0f so PID always reaches the motors.

The `ENABLE_MRAC_OUTPUT_INJECTION` flag (`mrac.h:51`) provides a "shadow mode" where MRAC computes and learns but sends zero to the mixer, useful for offline weight observation before committing to closed-loop injection.

---

## 9. Stability: What Guarantees Bounded Error?

The Lyapunov stability argument for MRAC (Lavretsky & Wise, Ch. 9) requires:

1. **A_m is Hurwitz**: The reference model is stable → guaranteed by design
2. **Matching condition**: The uncertainty lies in the range of the control input → approximately true for actuator and aero modeling errors, not true for sensor noise
3. **Bounded Θ**: The projection operator keeps weights finite → enforced by `MRAC_Projection()`
4. **Persistent excitation (for convergence)**: The regressor Φ must be sufficiently rich → depends on flight profile; hovering provides poor PE

Under these conditions, the tracking error e(t) converges to a bounded residual set. The size of this set depends on:
- Projection bounds (tighter bounds → smaller residual, but less disturbance rejection capacity)
- Sigma-modification strength (more leakage → larger residual, but more robustness)
- Noise floor (deadzone threshold determines minimum residual)

**Important caveat**: Lyapunov stability guarantees bounded signals but does **not** guarantee good transient performance. The various robustness modifications (L1 filtering, PCH, hard freeze) are engineering additions to manage transient behavior that pure theory does not address.

---

## 10. Evidence vs. Inference

### Verified from Code

- Four MRAC axes: pitch, roll, yaw, z_rate (`mrac.h:96–101`)
- Structured uncertainty with 4 or 6 basis functions depending on `INCLUDE_CONTROL_IN_REGRESSOR` (`mrac.h:73–89`)
- Projection operator implementation with 4 regions (`mrac_math.c:18–40`)
- RBF implementation: Gaussian kernel (`mrac_math.c:49–56`)
- Vector norm-squared for normalization (`mrac_math.c:64–73`)
- Shadow mode via `ENABLE_MRAC_OUTPUT_INJECTION` (`mrac.h:51`)
- NaN guard on mixer injection (`StabilizerTask.c:303–306`)
- `MRAC_Control` is called from `Compute_Motor()` after all PID loops (`StabilizerTask.c:286`)
- Detailed projection limit derivations in `mrac.h:107–136`
- Per-component gamma rationale in `mrac.h:203–209`

### Inferred / Theoretical Context

- The adaptation law `Θ̇ = -Γ·Φ·e·P·B` is the standard direct MRAC form; the exact discrete-time implementation is not visible (function body of `MRAC_Control()` is not yet implemented in the repository)
- The reference to "derivative-free" MRAC (Yucelen & Calise 2012) is based on the architectural choices (no explicit state derivative in the regressor), but the code does not contain a comment attributing it to that paper
- The L1-style filtering is inspired by Hovakimyan & Cao's L1 adaptive control, but this is a hybrid MRAC/L1 approach rather than a pure L1 controller
- Stability guarantees assume the matching condition holds and the uncertainty is within the projection bounds — these are modeling assumptions, not code-verifiable facts

---

## 11. Further Reading

- **Standard MRAC**: Lavretsky & Wise, *Robust and Adaptive Control with Aerospace Applications*, Springer 2013 — Chapters 9–12
- **Derivative-Free MRAC**: Yucelen & Calise, JGCD 2012 — the no-ideal-weights formulation
- **L1 Adaptive Control**: Hovakimyan & Cao, *L1 Adaptive Control Theory*, SIAM 2010 — explains the low-pass filtering philosophy
- **This codebase**: [[MRAC Control Law]] for the entity-level documentation, [[Yucelen Lectures]] for video digests
- **Tuning**: [[Tuning Workflow]] for practical gain adjustment procedures
