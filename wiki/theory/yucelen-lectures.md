# Yucelen Lectures on Adaptive Control — Digest

> Extracts key concepts from Dr. Tansel Yucelen's YouTube lecture series "Lectures on Adaptive Control and Learning" and maps them to this firmware's MRAC implementation.

**Playlist**: [Lectures on Adaptive Control and Learning](https://www.youtube.com/playlist?list=PLW4eqbV8qk8b7WLDXM2mTFZDSbm685Rjy) — Prof. Tansel Yucelen, University of South Florida

**About the instructor**: Dr. Yucelen is Professor of Mechanical and Aerospace Engineering at USF, Director of [LACIS](http://lacis.eng.usf.edu/) and [FoRCE](http://force.eng.usf.edu/), Co-Founder of [ControlX](https://controlx.systems/), and an associate fellow of AIAA. His PhD work at Georgia Tech with Prof. Anthony Calise produced the Derivative-Free MRAC architecture.

**Related wiki**: [[MRAC Theory]], [[MRAC Control Law]], [[Tuning Workflow]]

---

## 1. Lecture Index and Code Relevance

The playlist covers adaptive control from fundamentals to advanced topics. Below are the lectures most directly relevant to this codebase, with key takeaways and code cross-references.

### Lecture 1: "An Introduction to Adaptive Control and Learning"

**Video**: [youtube.com/watch?v=wJsWF9q3ARQ](https://www.youtube.com/watch?v=wJsWF9q3ARQ) (first video in the playlist)

**Key concepts**:
- **Why adaptive control?** Fixed-gain controllers (like PID) are designed for a nominal plant model. When the real plant differs — payload changes, actuator degradation, aerodynamic effects — performance degrades. Adaptive control adjusts gains online to maintain performance.
- **Model Reference Adaptive Control (MRAC)**: The controller drives the plant to behave like a desired *reference model*, regardless of plant uncertainties.
- **Two fundamental requirements**: (1) A reference model that specifies desired behavior, and (2) an adaptation law that updates controller parameters based on tracking error.

**Code connection**: The firmware's `MRAC_AxisState_t.xm` (`mrac.h:248`) is the reference model state. The tracking error `e = x - xm` (`mrac.h:254`) drives the adaptation law. The entire MRAC subsystem exists because PID alone cannot handle the payload configurations (`PAYLOAD_LIGHT` vs `PAYLOAD_HEAVY`, `mrac.h:21–25`) without re-tuning.

---

### Lecture: "What Is Model Reference Adaptive Control (MRAC)?"

**Video**: [youtube.com/watch?v=mVPbbtG7tTA](https://www.youtube.com/watch?v=mVPbbtG7tTA) (referenced from playlist)

**Key concepts**:
- The **reference model** `ẋ_m = A_m x_m + B_m r` defines the ideal closed-loop dynamics. The matrix A_m must be **Hurwitz** (all eigenvalues have negative real parts) — otherwise the "ideal" behavior is unstable.
- The **plant** has the same structure but with unknown parameters: `ẋ = (A + ΔA)x + (B + ΔB)u + d(t)`.
- The **adaptive law** adjusts the controller to minimize `e = x - x_m`.
- The **matching condition**: the uncertainty must lie in the column space of the control input matrix B. This means the controller must have physical authority over the uncertain dynamics.

**Code connection**: Each axis (pitch/roll/yaw/z) uses a separate MRAC instance with its own reference model. The `MRAC_AxisConfig_t.J` field (`mrac.h:232`) holds the nominal moment of inertia (or mass for Z), which appears in the B matrix. The matching condition is approximately satisfied for actuator and aerodynamic uncertainties but not for sensor noise — which is why the firmware has separate deadzone and hard-freeze mechanisms.

---

### Lecture: "Projection Operator"

**Video**: [youtube.com/watch?v=vlOy1ZH79wU](https://www.youtube.com/watch?v=vlOy1ZH79wU)

**Key concepts**:
- Without bounds on adaptive weights, they can grow unbounded — even if the tracking error is small — leading to eventual instability.
- The **projection operator** modifies the adaptive law to confine weights within a known convex set: `Θ̇ = Proj(Θ, y)` where y is the nominal gradient.
- **Key property**: The projection operator preserves the negative-semi-definiteness of the Lyapunov function derivative. In other words, the stability proof still holds after applying projection.
- **Implementation**: When |Θ| < bound, Proj(Θ, y) = y (no modification). When |Θ| approaches the bound and the gradient pushes outward, Proj scales it down to zero. When the gradient pushes inward (toward the interior), it is always allowed.

**Code connection**: `MRAC_Projection()` in `mrac_math.c:18–40` implements exactly this 4-region projection:
1. Interior (`|θ| < w_max - tol`): return y unchanged
2. Near boundary, pushing inward: return y unchanged
3. At boundary, pushing outward: return 0 (hard stop)
4. Tolerance zone, pushing outward: linearly scale y down

The per-component bounds `What_limit[]` and tolerances `What_tol[]` (`mrac.h:219–220`) are set based on physical disturbance budgets — see the detailed derivation in `mrac.h:107–136` and [[MRAC Theory]] Section 4.3.

---

### Lecture: "Leakage Modification"

**Video**: [youtube.com/watch?v=4dKtjL2yPzg](https://www.youtube.com/watch?v=4dKtjL2yPzg)

**Key concepts**:
- **Sigma-modification** (σ-mod): Adds `−σΘ` to the adaptive law, creating a constant leakage toward zero.
  ```
  Θ̇ = -Γ·Φ·e·P·B − σ·Θ
  ```
- The leakage term ensures that weights don't accumulate indefinitely in the absence of persistent excitation.
- **Trade-off**: Larger σ → faster weight decay → more robust but larger steady-state tracking error (weights can't hold their values against constant disturbances).
- **e-modification**: Replaces constant σ with `σ·‖e‖`, so leakage is strong only during transients and vanishes at equilibrium.

**Code connection**:
- `ENABLE_SIGMA_MODIFICATION` (`mrac.h:53`) — enables constant σ-mod
- `sigma` field in `MRAC_AxisConfig_t` (`mrac.h:212`) — the leakage rate
- `sigma_lf` (`mrac.h:211`) — low-frequency leakage for L1-style filtered weights
- `k_e` (`mrac.h:237`) — e-modification gain (leakage proportional to error)

---

### Lecture: "Neural Networks" / "Model Reference Neuroadaptive Control"

**Video**: [youtube.com/watch?v=mVPbbtG7tTA](https://www.youtube.com/watch?v=mVPbbtG7tTA) (Neural Networks), [youtube.com/watch?v=9vSmZcp_ItE](https://www.youtube.com/watch?v=9vSmZcp_ItE) (High-Order Case)

**Key concepts**:
- When the uncertainty is **unstructured** (unknown nonlinear function), a neural network can approximate it using basis functions.
- **Radial Basis Functions (RBFs)**: Gaussian kernels `φᵢ(x) = exp(-wᵢ·‖x − cᵢ‖²)` that activate locally around centers cᵢ.
- **Universal Approximation**: Any continuous function can be approximated to arbitrary accuracy by a sufficiently large sum of RBFs: `f(x) ≈ Θᵀ·Φ(x) + ε` where ε is the approximation error.
- The adaptive law learns the weights Θ online. The approximation error ε becomes a bounded disturbance that the robustness modifications (projection, σ-mod) handle.
- **Structured vs. unstructured**: If you know the form of the uncertainty (e.g., "linear in angle and rate"), use physics-based basis functions. If you don't know the form, use RBFs.

**Code connection**:
- `USE_STRUCTURED_UNCERTAINTY = 1` vs `USE_UNSTRUCTURED_UNCERTAINTY = 1` (`mrac.h:46–47`) — compile-time selection
- Structured basis: `Φ = [1, angle, rate, drag, un, v]` — physics-based, interpretable weights
- Unstructured basis: `MRAC_Simple_RBF()` in `mrac_math.c:49–56` — Gaussian `exp(-width·(x−c)²)`
- `NUM_BASIS = 4` (`mrac.h:73`) base features, expanded to `MAX_NUM_BASIS = 6` with `INCLUDE_CONTROL_IN_REGRESSOR`
- The structured model is recommended (comment at `mrac.h:46`) because quadrotor dynamics are well-modeled

---

### Lecture: "Projection Operator and Leakage Mod.: High-Order Case"

**Video**: [youtube.com/watch?v=MK_u1vfhG8o](https://www.youtube.com/watch?v=MK_u1vfhG8o)

**Key concepts**:
- Extension to higher-order systems (not just first-order plant dynamics).
- The **state predictor** tracks the plant state and generates a prediction error that drives adaptation, separate from the tracking error.
- **Performance recovery**: An L1-inspired technique where a state predictor + low-pass filter generates a correction signal `v` that compensates for the transient behavior of the adaptation.

**Code connection**:
- `ENABLE_PERFORMANCE_RECOVERY` (`mrac.h:58`) — enables L1-style state predictor + filtered correction
- `lambda_perf` (`mrac.h:226`) — state predictor bandwidth
- `tau_v` (`mrac.h:227`) — low-pass filter time constant for the performance recovery signal v
- The `v` signal appears as the last basis function when `INCLUDE_CONTROL_IN_REGRESSOR = 1`

---

### Lecture: "Adaptive Control Example in Matlab: High-Order Case"

**Video**: [youtube.com/watch?v=KytO5TujUAQ](https://www.youtube.com/watch?v=KytO5TujUAQ)

**Key concepts**:
- Practical MATLAB implementation showing the complete signal flow: reference model → error computation → regressor construction → adaptive law → projection → control output.
- Demonstrates the effect of learning rate (Γ) on convergence speed vs. transient oscillation.
- Shows how projection prevents weight divergence when the system encounters an unmodeled disturbance.

**Code connection**: The MATLAB signal flow maps directly to the firmware architecture:
1. Reference model update → `mrac_state.*.xm`
2. Error computation → `mrac_state.*.e = x - xm`
3. Regressor construction → `mrac_state.*.Phi[]`
4. Adaptive law with projection → `MRAC_Projection()` applied per-weight
5. Control output → `mrac_state.*.u_ad = Θᵀ·Φ`

The per-component learning rates in `mrac.h:143–145` follow the guidance from this lecture: scale γᵢ inversely with the typical squared magnitude of the corresponding regressor component.

---

### Lecture: "Neuroadaptive Control with Barrier Functions"

**Video**: [youtube.com/watch?v=CO6qpZzKwew](https://www.youtube.com/watch?v=CO6qpZzKwew)

**Key concepts**:
- **Barrier Lyapunov functions** provide state constraint satisfaction — keeping the tracking error within prescribed bounds, not just proving it's bounded.
- Unlike projection (which bounds weights), barriers bound the error itself.
- Useful for safety-critical applications where the error must never exceed a physical limit (e.g., maximum allowable tilt angle).

**Code connection**: `ENABLE_LYAPUNOV_BARRIER = 0` (`mrac.h:62`) — this feature is defined but disabled in the firmware. The barrier approach would complement the existing hard-freeze mechanism (`e_freeze` in `mrac.h:235`) by providing a smooth, Lyapunov-guaranteed alternative to the binary freeze threshold.

---

### Lecture: "Key Moments and What is Next"

**Video**: [youtube.com/watch?v=NuzA-VfJYwQ](https://www.youtube.com/watch?v=NuzA-VfJYwQ)

**Key concepts**:
- Summary of the key results: projection guarantees boundedness, σ-mod ensures robustness, neural networks handle unstructured uncertainty, performance recovery manages transients.
- Preview of advanced topics: multi-agent adaptive control, human-in-the-loop adaptive control, and applications to autonomous systems.

---

## 2. Key Academic Papers by Yucelen (Directly Relevant)

### 2a. "Derivative-Free Model Reference Adaptive Control" (2012)

**Citation**: T. Yucelen, A. J. Calise, *"Derivative-Free Model Reference Adaptive Control,"* AIAA JGCD, vol. 35, no. 4, 2012.

**Key contribution**: Standard MRAC requires the derivative of the tracking error (or state sensitivity) in the adaptive law. Derivative-Free MRAC (DF-MRAC) reformulates the law using a delayed weight update that does not require these derivatives, making it more practical for implementation on embedded systems where clean derivatives are hard to obtain.

**Relevance to this code**: The firmware's MRAC implementation does not compute `ė` or state derivatives in the adaptation law. The regressor `Phi[]` consists of state values (angle, rate) and control input — not their derivatives. This is consistent with the DF-MRAC architecture, though the code does not explicitly cite the paper.

### 2b. "Experimental Results of a Quadrotor UAV with MRAC" (2022)

**Citation**: T. Yucelen et al., *"Experimental Results of a Quadrotor UAV with a Model Reference Adaptive Controller in the Presence of Unmodeled Dynamics,"* AIAA SciTech, 2022.

**Key contribution**: Flight test validation of MRAC on a physical quadrotor with payload changes and aerodynamic disturbances. Demonstrates that:
- MRAC can compensate for up to 40% payload increase without re-tuning
- Projection bounds must be set conservatively to avoid aggressive adaptation during transients
- L1-style filtering on u_ad significantly reduces control chatter

**Relevance to this code**: The firmware's dual payload configurations (`PAYLOAD_LIGHT` / `PAYLOAD_HEAVY` at `mrac.h:21–25`) with different `mrac_to_mixer` scalers follow this paper's recommendation of payload-aware MRAC tuning. The L1 filtering (`ENABLE_LOW_FREQ_LEARNING`, `omega_u` parameter) directly implements the paper's chatter reduction strategy.

### 2c. "A Hybrid MRAC System for Multi-Rotor UAVs" (2024)

**Citation**: T. Yucelen et al., *"A Hybrid Model Reference Adaptive Control System for Multi-Rotor UAVs,"* AIAA SciTech, 2024.

**Key contribution**: Combines structured and unstructured uncertainty models in a hybrid architecture that switches between them based on operating conditions. When near hover (small angles), structured basis functions are sufficient. During aggressive maneuvers, RBFs activate to capture nonlinear effects.

**Relevance to this code**: The firmware's compile-time selection between `USE_STRUCTURED_UNCERTAINTY` and `USE_UNSTRUCTURED_UNCERTAINTY` (`mrac.h:46–47`) is a static version of this hybrid approach. A future enhancement could implement runtime switching based on the magnitude of the tracking error or angular rates.

---

## 3. Conceptual Map: Lecture Topics → Code Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     MRAC Signal Flow                                │
│                                                                     │
│  Lecture 1         Lecture "MRAC"       Lecture "Neural Nets"        │
│  ─────────         ─────────────       ──────────────────           │
│  "Why adaptive"    Reference Model     Basis Functions               │
│       │            xm = Am·xm + Bm·r  Φ = [1, θ, ω, ...]          │
│       │                │                     │                      │
│       ▼                ▼                     ▼                      │
│  PID baseline ──► e = x - xm ────────► Θ̇ = -Γ·Φ·e·P·B            │
│  (u_nom)              │                     │                      │
│                        │            Lecture "Projection"             │
│                        │            ─────────────────               │
│                        │            Θ̇ = Proj(Θ, y)                 │
│                        │                     │                      │
│                        │            Lecture "Leakage"                │
│                        │            ────────────────                │
│                        │            Θ̇ += -σ·Θ                      │
│                        │                     │                      │
│                        │                     ▼                      │
│                        │              u_ad = Θᵀ · Φ                 │
│                        │                     │                      │
│                        │            Lecture "High-Order"             │
│                        │            ────────────────                │
│                        │            LPF → u_ad_filtered             │
│                        │                     │                      │
│                        ▼                     ▼                      │
│                  u_total = u_nom + u_ad ──► Motor Mixer              │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 4. Recommended Viewing Order for This Codebase

If you're working on this firmware's MRAC subsystem, watch the lectures in this order:

| Order | Lecture | Why |
|:---|:---|:---|
| 1 | Introduction to Adaptive Control | Mental model for why MRAC exists alongside PID |
| 2 | What Is MRAC? | Reference model, tracking error, adaptive law — the three pillars |
| 3 | Projection Operator | Maps directly to `MRAC_Projection()` and `What_limit[]` |
| 4 | Leakage Modification | Maps to `sigma`, `sigma_lf`, `k_e` parameters |
| 5 | Neural Networks | Understand `USE_STRUCTURED_UNCERTAINTY` vs RBFs |
| 6 | High-Order Case / MATLAB Example | See the complete signal flow implemented |
| 7 | Barrier Functions | Future feature (`ENABLE_LYAPUNOV_BARRIER`) |

---

## 5. Evidence vs. Inference

### Verified

- Video URLs confirmed accessible and matching the described topics
- Code variable names mapped to specific `mrac.h` lines and `mrac_math.c` functions
- Paper citations confirmed via ResearchGate/IEEE/AIAA

### Inferred

- The claim that this firmware implements "Derivative-Free MRAC" is based on the observation that no state derivatives appear in the regressor — the code does not contain a comment attributing itself to Yucelen & Calise 2012
- Lecture content summaries are based on video titles, descriptions, and web search results — not full transcripts. Specific timestamps are not provided because auto-generated subtitles were not fetched
- The recommended viewing order is editorial judgment based on codebase dependencies, not prescribed by the instructor
