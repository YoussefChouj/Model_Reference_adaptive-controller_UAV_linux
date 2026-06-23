# 0003 - Inner-Loop MRAC Architecture and Gap Resolutions

* **Status:** Accepted
* **Date:** 2026-06-15

## Context and Problem Statement

The physics-based simulations (Jupyter notebooks) demonstrated that a Model Reference Adaptive Controller (MRAC) effectively mitigates nonlinear uncertainties and disturbances. However, porting the mathematical theory directly to bare-metal embedded C (FreeRTOS STM32) without adjusting for physical hardware realities predictably results in instability. 

We needed to formally structure the MRAC implementation in `API/mrac.c` and `API/mrac.h` to address the gap between continuous-time simulation and discrete actuator-limited reality.

Specifically, we needed to resolve:
1. Translating abrupt step commands to the inner loop without causing error spikes and weight windup.
2. Preventing integration windup when the motors saturate.
3. Preventing weight drift caused by high-frequency gyroscope measurement noise via proper normalization of leakage terms.
4. Protecting the ESCs and motors from high-frequency adaptive control chatter.

## Options Considered

### Reference Model Design
* **Option A:** Direct passthrough (`xm = r`). Simpler, but causes massive $e$ spikes on step inputs, forcing violent weight updates.
* **Option B:** 1st-Order Dynamic Reference Model ($\dot{x}_m = -A_m x_m + B_m r$). Smooths the trajectory and gives the target closed-loop system a definable bandwidth.

### Noise Drift Mitigation
* **Option A:** Pure deadzone. Ignore errors below a noise threshold. (Already implemented, but insufficient for large continuous noise).
* **Option B:** $\sigma$-modification (Leakage). Mathematically guarantees weight stability, but standard division by the regressor norm `denom` ($1 + \Phi^T \Phi$) causes leakage to drop to zero when signals diverge.

### Actuator Protection
* **Option A:** Unfiltered direct injection ($u_{total} = u_{nom} + \hat{\theta}^T \Phi$). Computationally cheap, but passes adaptation chatter directly to the motors.
* **Option B:** Performance Recovery (L1 low-pass filter). Decouples fast adaptation from actuator bandwidth.

## Decision and Rationale

We iteratively modified the source implementation to reflect the hardware-safe MRAC architecture:

1. **Adopted Option B (1st-Order Reference Model):** Enabled via `#define ENABLE_DYNAMIC_REF_MODEL 1`. The reference bandwidth ($A_m = \omega_{ref}$) is tuned slightly below the nominal PID bandwidth, preventing the adaptive layer from chasing physically impossible targets. The Lyapunov scalar is simply $P = \frac{1}{2 \omega_{ref}}$.

   > **Side-effect (recorded 2026-06-16):** `P` is not only the Lyapunov constant — it multiplies the gradient (`grad = -PBe·P·Φ/denom`). Switching from the passthrough era (`P = 1`) to `P = 1/(2·ω_ref)` cuts the effective adaptation gain by `2·ω_ref` (≈100× pitch/roll, 60× yaw, 40× z) **with the `gamma[]` values unchanged**. This is conservative/safe (it de-tunes the dual-integrator resonance that caused the historical 3DOF-rig oscillation) but was not deliberate. To restore prior learning aggressiveness with the model active, scale `gamma[]` by ≈`2·ω_ref`; do **not** re-inflate `P`.
2. **Fixed Leakage Normalization:** Enabled via `#define FIX_LEAKAGE_NORMALIZATION 1`. We removed the `/ denom` from both $\sigma_{lf}$ and $\sigma_{eff}$ in `mrac.c` step 5. Normalization is now strictly applied to the gradient itself resulting in $\dot{\theta} = \Gamma \cdot \text{Proj}(-e \Phi P B / denom) - \sigma \theta$. This ensures the "mathematical spring" remains active even during chaotic maneuvers.
3. **Confirmed Additive Sign Convention:** Documented in `CONTEXT.md` that $u_{total} = u_{nom} + u_{ad}$. Because $B > 0$ for quadcopter rate controllers, the gradient law $\dot{\theta} = -\Gamma e P \Phi$ remains strictly valid.
4. **Confirmed Projection Operator for Saturation:** Decided to rely on the existing `MRAC_ProjectGradient` function bounding individual weights rather than back-calculating true actuation limits via Pseudo-Control Hedging, due to the difficulty of accurate real-time inverse mixing.
5. **Adopted Option B (Performance Recovery):** Enabled via `#define ENABLE_PERFORMANCE_RECOVERY 1` in `mrac.h` and implemented a discrete low-pass filter $\dot{u}_{ad} = \omega_u ( \hat{\theta}^T \Phi - u_{ad} )$ at the end of the `MRAC_UpdateAxis` function.

   > **Clarification (recorded 2026-06-16):** this is a plain 1st-order output low-pass on `u_ad`, **not** a full L1 reference/state predictor — `lambda_perf` and `tau_v` remain unused. Behaviour is benign (anti-chatter, ~5 Hz, `DT·ω_u`≈0.15, stable) but should not be reasoned about as L1 performance recovery.

6. **Runtime shadow-mode gate (added 2026-06-16):** `ENABLE_MRAC_OUTPUT_INJECTION` stays `1` (the injection path is compiled in), but a new runtime flag `mrac_flags.output_injection_on` (CMD 0x0F idx 10, dashboard checkbox) gates whether `u_ad` actually reaches the motors. It **defaults to 0 (shadow)** in `MRAC_Init` so the first flight after any MRAC change logs `e`/`xm`/`u_ad` with the motors on pure PID; the operator flips it ON live once telemetry confirms `u_ad` is bounded and sane.

## Files Affected
* `CONTEXT.md`
* `API/mrac.h`
* `API/mrac.c`

## Constraints Created
* **Sensor Handling:** The MRAC sits exclusively in the inner rate loop responding to Gyro data. Outer-loop sensor drift (e.g., Optical Flow translation drift) MUST be handled by a dedicated sensor observer/fusion layer, NOT by the MRAC.
* **Sign Mixing:** The nominal PID values and MRAC `u_ad` values MUST be added together downstream, not subtracted.


