---
title: Direct MRAC + FF + Projection Notebook
type: source
tags: [mrac, projection-operator, barrier-function, quadrotor, simulation, multi-axis, performance-recovery, actuator-dynamics, l1-adaptive]
created: 2026-04-14
updated: 2026-06-20
sources:
  - "C:/Users/Acer/Desktop/Pich_yaw_roll_experimental_drone_setup/Drone_experiments_python_jypeter_code/Roll_Pitch_Yaw_Adaptive_Control_Direct_MRAC_FFcontroller_Projection_operator v2.ipynb"
---

60-cell full multi-axis simulation notebook. This is the integration environment where all techniques from the tutorial notebooks are combined into a realistic 3-axis (pitch/roll/yaw) quadrotor model with actuator dynamics, mixer math, and diagnostics. Treat all code cells as the most mature simulation baseline.

---

## Architecture overview

```mermaid
flowchart LR
    REF[Trajectory r(t)] --> RM[Reference model Am/Bm]
    RM --> ERR[Error e = x - xm]
    STATE[6D state x] --> ERR
    STATE --> REG[Regressor θ(x)]
    REG --> LAW[Adaptive weight update]
    ERR --> LAW
    CFG[Config flags] --> LAW
    PERF[PerfRec] --> LAW
    BAR[BarrierConfig] --> LAW
    LAW --> UAD[u_ad = -Ŵᵀθ]
    NOM[-K1x + K2r] --> SUM((+))
    UAD --> SUM
    SUM --> MIX[Mixer + actuator lag]
    MIX --> PLANT[6D state propagation]
    PLANT --> STATE
    STATE --> DIAG[Plots + diagnostics]
```

---

## State and weight structure

**State:** `x = [pitch, ṗitch, roll, ṙoll, yaw, ẏaw]ᵀ` (6×1)

**Adaptive weight vectors (per axis, independent):**
```
What_pitch = zeros(NUM_BASIS, 1)
What_roll  = zeros(NUM_BASIS, 1)
What_yaw   = zeros(NUM_BASIS, 1)
```

**Low-frequency filtered weights (parallel slow-timescale learners):**
```
Whatf_pitch = zeros(NUM_BASIS, 1)
Whatf_roll  = zeros(NUM_BASIS, 1)
Whatf_yaw   = zeros(NUM_BASIS, 1)
```

---

## Reference model design (Cells 0–7)

**Cell 0:** Guide for choosing `wn` (natural frequency) and `zeta` (damping ratio) for each axis. Quadrotor angles behave as 2nd-order systems — the reference model defines desired closed-loop dynamics.

**Cell 3:** Reference model state space:
```
wn, zeta → Am = [[0,1],[-wn²,-2*rn*wn]],  Bm = [[0],[wn²]]
```

**Cell 4:** Nominal controller design:
```
K1 = B⁺(A - Am)    (cancel open-loop A, impose Am)
K2 = B⁺Bm          (DC gain matching feedforward)
```

**Cells 5–7:** Stability analysis, root locus, pole-zero plots to verify nominal design before adding adaptation.

---

## Configuration flags (Cell 8)

```python
class Config:
    ADAPTATION_ON              = True   # Enable adaptive loop
    PERFORMANCE_RECOVERY_ON    = True   # L1-like recovery signal
    INCLUDE_CONTROL_IN_REGRESSOR = True # Adds un to θ to adapt for Λ uncertainty
    USE_LOW_FREQUENCY_LEARNING = True   # Two-timescale LF leakage
    USE_WEIGHT_NORMALIZATION   = True   # Divides gradient by (1 + θᵀθ)
    SIGMA_MODIFICATION         = False  # Standard σ-leakage (off when LFL is on)
    PROJECTION_OPERATOR        = True   # Linear smooth projection on weights
    Set_Theoretic_Barrier      = True/False  # Barrier-modified adaptation
```

**Key interaction:** `SIGMA_MODIFICATION` and `USE_LOW_FREQUENCY_LEARNING` are mutually exclusive in practice. LFL subsumes standard σ-modification (it uses `σ(Ŵ - Ŵf)` instead of `σŴ`).

---

## Adaptive parameters (Cell 9)

```python
DEADZONE_THRESHOLD = 0.05     # [°] — suppresses adaptation when error < 0.05°

MAX_ADAPTIVE_TORQUE = {       # [N·m] — 30% of physical maximum
    'pitch': 0.3 * U_MAX_PITCH_ROLL,
    'roll':  0.3 * U_MAX_PITCH_ROLL,
    'yaw':   0.3 * U_MAX_YAW
}

eps = {                        # [°] — set-theoretic error bounds
    'pitch': 0.5,
    'roll':  0.5,
    'yaw':   1.0
}
```

**Adaptation gain structure:** pitch/roll are fast axes (higher γ acceptable), yaw has lower control authority (lower γ to avoid saturation).

---

## Performance recovery parameters (Cell 10)

```python
class PerfRec:
    LAMBDA = {'pitch': 100, 'roll': 100, 'yaw': 100}  # Recovery bandwidth
    USE_FILTERED = True
    TAU_V = {'pitch': 2.0, 'roll': 2.0, 'yaw': 1.5}  # v-signal filter [s]
```

**Theory:** Recovery signal `v` is generated from filtered state predictor error, then injected into both the control and the reference model. This is L1-adaptive-inspired: the reference model bends toward the actual state during large disturbances, reducing the effective tracking error seen by the adaptation law. `LAMBDA = 100` means the recovery bandwidth is 100 rad/s — fast enough to track typical attitude disturbances.

**Rule of thumb from Cell 10 comments:** `λ << min(|eig(Am)|) / Λ_max`. With LF filtering, the bandwidth can be pushed higher.

---

## Barrier function parameters (Cell 11)

```python
class BarrierConfig:
    E_MAX_PITCH = 15.0   # [°]
    E_MAX_ROLL  = 15.0   # [°]
    E_MAX_YAW   = 20.0   # [°]
    ACTIVATION_THRESHOLD = 0.75   # Barrier activates at 75% of E_MAX
    SMOOTHING = 0.01              # ε_s in log barrier denominator
```

**Logarithmic barrier (Cell 19):**
```python
def logarithmic_barrier(x, x_max, alpha=0.75, smoothing=0.01):
    activation_threshold = alpha * x_max
    if x <= activation_threshold:
        return 0.0
    return -log(x_max - x + smoothing)   # grows → ∞ as x → x_max
```

**Critical gotcha from Cell 19 docstring:** If `smoothing` is too large, the barrier can go negative (log of value >1). Typical safe range: `smoothing ∈ [0.005, 0.15]` where `smoothing ≈ 0.01 × x_max`.

**Two barrier approaches compared in Cell 20:**
1. **Logarithmic barrier** (component-wise on angle/rate): `φ(x) = -log(x_max - x + ε_s)`
2. **Prescribed performance barrier** (norm-based, from Tutorial 2 Cell 6): `φ'(e) = (ε - 0.5√(eᵀPe))/(ε - √(eᵀPe))²`

The notebook uses logarithmic for the multi-axis case because component-wise application is easier to tune per axis.

---

## Helper functions (Cell 12)

```python
def get_scheduled_gamma(t, gamma_final, tau):
    return gamma_final * (1 - exp(-t / tau))   # exponential ramp from 0 to gamma_final

def wrap_angle(angle_rad):
    return arctan2(sin(angle_rad), cos(angle_rad))   # yaw wrapping to [-π, π]

def Simple_rbf(x, c, width):
    return exp(-width * |x - c|²)   # per-state Gaussian

def Joint_rbf(x0, x1, c0, c1, width):
    return exp(-width * ((x0-c0)² + (x1-c1)²))   # joint 2D Gaussian
```

**Gamma scheduling:** Starting adaptation gain at 0 and ramping to `gamma_final` with time constant `tau` prevents the initial transient from driving large weight updates before the error has stabilized. Recommended `tau = 2–5 s` for flight conditions.

---

## Uncertainty model (Cell 13)

Three difficulty levels via `level='easy'/'medium'/'hard'`. Two modes:
- `use_structured=True`: physics-based uncertainty (aerodynamic cross-coupling, inertia mismatch)
- `use_structured=False`: RBF-parametrized uncertainty with random weight initialization

The uncertainty switches on partway through the simulation to allow the nominal controller to establish tracking first, then test adaptation performance.

---

## Initialization (Cell 14)

```
x  = zeros(6)     state [pitch, ṗ, roll, ṙ, yaw, ẏ]
xm = zeros(6)     reference model state
xr = zeros(6)     performance recovery reference model state

v         = zeros(3)    recovery signal per axis
v_filtered = zeros(3)   low-pass filtered v
f         = zeros(6)    state predictor filter
r_filtered = zeros(3)   filtered command
```

---

## Actuator dynamics (Cells 16–17)

**Cell 16** documents and fixes bugs in the mixer/actuator loop. Key facts:
- Forward mixer: `[F1, F2, F3, F4] = Mixer⁻¹ × [Thrust, τpitch, τroll, τyaw]`
- Actuator lag: 1st-order filter `ω̇_motor = (ω_cmd - ω_actual) / τ_motor`
- Inverse mixer: recovers applied torque from lagged motor speeds
- Bug fix documented: prior version had sign errors in the inverse mixer that caused simulation to diverge

**Realistic vs ideal mode:** toggled by `Config.ACTUATOR_DYNAMICS`. In ideal mode, commanded torque is applied directly. Realistic mode reveals that motor lag reduces effective adaptive bandwidth — `wn` of the reference model must be tuned lower to remain within what actuators can deliver.

---

## Tuning guide (Cell 17)

Diagnostic symptom table from the notebook:

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| High-freq oscillation in angle/rate | γ too high | Reduce γ or add normalization |
| Slow tracking | γ too low, wn too low | Increase γ, increase wn |
| Steady-state drift | σ too low, projection too loose | Increase σ or tighten projection bounds |
| Control saturation | Uncertainty too large, authority limits too tight | Widen MAX_ADAPTIVE_TORQUE or reduce uncertainty level |
| Weight runaway | No projection or leakage | Enable PROJECTION_OPERATOR |
| NaN/Inf | Barrier smoothing too small, or error exceeds E_MAX | Increase smoothing or widen E_MAX |

---

## Barrier function theory cell (Cell 18)

Full Lyapunov-barrier derivation in markdown:

**Standard MRAC Lyapunov function:**
```
V = eᵀPe + W̃ᵀΓ⁻¹W̃
```

**Barrier-augmented:**
```
Vb = eᵀPe + W̃ᵀΓ⁻¹W̃ + φ(e)
```
where `φ(e)` is the log barrier. The barrier gradient `∇φ` is injected additively into the weight update, modifying the Lyapunov descent condition to prevent constraint violations.

**Key insight from Cell 18:** The barrier does not replace the MRAC law — it *shapes* the adaptation direction near the constraint boundary. Far from the boundary `(||e|| << ε)`, standard MRAC behavior is recovered exactly.

---

## Firmware cross-references

| Notebook parameter | Firmware location | Variable name |
|-------------------|-------------------|---------------|
| `Config.ADAPTATION_ON` | [API/mrac.c](../../API/mrac.c) | `mrac_enabled` flag |
| `Config.PROJECTION_OPERATOR` | [API/mrac.c](../../API/mrac.c) | `mrac_projection_scalar()` |
| `Config.USE_LOW_FREQUENCY_LEARNING` | [API/mrac.c](../../API/mrac.c) | LF leakage update block |
| `Config.PERFORMANCE_RECOVERY_ON` | [API/mrac.c](../../API/mrac.c) | `v_signal`, `f_filter` |
| `DEADZONE_THRESHOLD` | [API/mrac.h](../../API/mrac.h) | `MRAC_DEADZONE` |
| `MAX_ADAPTIVE_TORQUE` | [API/mrac.h](../../API/mrac.h) | `MRAC_MAX_UA_*` |
| `PerfRec.LAMBDA` | [API/mrac.c](../../API/mrac.c) | `perf_rec_lambda` |
| `BarrierConfig.E_MAX_*` | not yet in firmware | (future work) |
| `get_scheduled_gamma()` | not yet in firmware | (future work — gamma ramp) |

**Contradiction to flag:** Firmware does not yet implement gamma scheduling (ramp from 0). The firmware initializes adaptation gain at full value from power-on. This produces larger initial weight transients on first arm. The notebook's gamma scheduling is the recommended approach for firmware too.

---

## High-value gotchas

1. **Projection + sigma ordering:** Apply projection to the gradient vector first, then add sigma leakage. Reversing the order (sigma first, then project) can clip the leakage term and cause drift.

2. **Weight normalization:** `Γ_eff = Γ/(1 + θᵀθ)` prevents gradient explosion when regressor norm is large (e.g., during large attitude errors). Without it, high `γ` + large excitation causes oscillation.

3. **INCLUDE_CONTROL_IN_REGRESSOR:** Including `un` in θ allows adapting for input gain uncertainty `Λ ≠ 1`. If the true `Λ` is known, omit this — it unnecessarily couples the nominal and adaptive channels.

4. **Barrier smoothing is critical:** `smoothing = 0.01` works for `E_MAX = 15°`. Scaling rule: `smoothing ≈ 0.001 × E_MAX`. Too large → barrier goes negative. Too small → numerical overflow near boundary.

5. **Actuator dynamics change optimal gains:** Nominal gains designed for ideal plant are suboptimal with motor lag. Expect to reduce `wn` by ~20–30% when enabling actuator dynamics.

---

## Recommended use pattern for agents

1. Read Cells 8–11 to understand all configuration flags before modifying.
2. Use Cell 17 symptom table to diagnose problems before tuning.
3. Run with `Config.ACTUATOR_DYNAMICS = False` first to validate adaptive law, then enable for realism.
4. Enable barrier (`Set_Theoretic_Barrier = True`) only after verifying nominal tracking is clean — it interacts strongly with gain settings.

## Related pages

- [[Adaptive Control Tutorial Notebook]]
- [[Adaptive Control Tutorial 2 Notebook]]
- [[Adaptive Control Simulations]]
- [[Adaptive Simulation Theory-to-Code Deep Dive]]
- [[MRAC Theory]]
- [[MRAC Control Law]]
- [[Motor Mixer]]
- [[Timer & PWM Configuration]]
