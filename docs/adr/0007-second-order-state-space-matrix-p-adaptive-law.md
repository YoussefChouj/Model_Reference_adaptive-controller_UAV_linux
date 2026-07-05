# 0007 - Second-order state-space matrix-P adaptive law

*   **Status:** Accepted (implemented in `API/mrac.c` + `sim/`, 2026-06-24)
*   **Date:** 2026-06-24
*   **Supersedes:** ADR-0003 scalar-`P` heuristic **for `ref_model_type == 2` only**; chosen instead of ADR-0005 §3 (augmented-error)
*   **Depends on:** ADR-0003 (inner-loop MRAC), ADR-0005 (identified ref models), ADR-0006 (sim package)

## Context

ADR-0003 used a single **scalar** Lyapunov gain `P = 1/(2·wn)` for *all* reference-model
types, and made it double as the adaptive-law gain (`grad = −e·P·Φ/denom`). For the
relative-degree-2 roll/pitch plants this is a heuristic: it ignores the second error
state (rate-derivative error `ė`) and the matrix structure of the true Lyapunov `P`
that solves `Amᵀ P + P Am = −Q`. ADR-0005 §3 flagged the same gap and proposed the
**augmented-error** (MIT/Narendra) fix — one filtered-regressor state per basis term —
but was never implemented.

Now that the reference model is well identified (`wn=44`, `ζ=0.8`) and the offline
solver (`ground_station/scripts/compute_reference_model.py`) reproduces the matrix `P`,
we revisit it. The user asked that the 2nd-order case use the **real matrix P**, not
the scalar `1/(2·wn)`. The matrix `P` is meaningless in the scalar law, so this
necessarily means adopting a **state-space** weight-update law for type 2.

## Decision

For `ref_model_type == 2` (roll/pitch) replace the scalar drive with the full
state-space Lyapunov drive; keep the scalar heuristic unchanged for passthrough (0)
and 1st-order (1, yaw — relative degree 1, already SPR).

### 1. The drive reduces to two scalars

With error vector `eᵥ = [e, ė]` (`e = x − xm`, `ė = ẋ − ẋm`) and adaptive-input
direction `B = [0; 1]`, the Lyapunov drive is

```
s = eᵥᵀ P B = e·p12 + ė·p22
```

so **only the 2nd column of P matters** — call it `(Pe, Pedot) = (p12, p22)`. For
diagonal `Q = diag(Q1, Q2)` and `Am = [[0,1],[−wn², −2ζwn]]` the closed form is

```
Pe    = Q1 / (2·wn²)
Pedot = (Q1/wn² + Q2) / (4·ζ·wn)
```

Firmware computes these **live** each tick from `(ref_model_bw, ref_model_zeta, ref_Q1,
ref_Q2)`, exactly as it computed the scalar `P` before — no matrix storage, no scipy.
The weight update is unified across laws: `grad[i] = −s·Φ[i]/denom`, only `s` differs.

### 2. Q is the gain knob (Q = I default)

`Q1` scales the rate-error channel; `Q1 = wn` makes `Pe = 1/(2·wn)`, recovering the old
scalar e-channel gain (a fair before/after point). `Q2` scales the derivative channel.
Power-on default is `Q = I` (`Q1=Q2=1`), matching the offline calculator default.

### 3. ė is a filtered finite difference (firmware **and** sim)

`ẋ` is the derivative of the gyro rate, so it is noisy on hardware. Both firmware
(`MRAC_UpdateAxis` step 2b) and sim (`adaptive_law.py`) form it identically:

```
raw_xdot = (x − x_prev)/DT
xdot_f  += DT·wc_edot·(raw_xdot − xdot_f)      // 1st-order LPF, wc_edot = 30 rad/s default
ė        = xdot_f − xm_dot
```

modelled the same lossy way in sim so the simulation predicts the hardware noise
penalty up front. `e` is tanh-saturated (via `PBe`) as before; `ė` is left to the LPF
bound in Phase 1 (no separate `e_sat_dot`). The filter runs every tick (kept warm in
deadzone/freeze).

### 4. Safety gating

The new path is reached **only** when `ref_model_type == 2`. Power-on default is
`DEFAULT_REF_MODEL_TYPE = 0` (passthrough), so default flight behaviour is **unchanged**
until the operator deliberately selects the 2nd-order model (CMD 0x13). Projection,
deadzone, hard-freeze, σ/e-mod, perf-recovery LPF all still apply.

## Consequences

*   **Pro:** roll/pitch now use a theoretically-grounded rel-deg-2 law (uses `ė`), with a
    single tunable `Q`. Sim (`sim/`, ADR-0006) is firmware-parity by construction —
    `test_state_space_law.py` pins the closed-form `P` against the scipy solver and the
    `Q1=wn` identity. Sweep B in `sim/experiments.py` shows `Q1`↑ improves tracking;
    `Q2`↑ destabilises (derivative-noise penalty), confirming the LPF-FD modelling choice.
*   **Con / watch:** `ė` injects gyro-derivative noise into adaptation — `wc_edot` and `Q2`
    must stay conservative; validate on the 2nd-order model in passthrough-sized `Q`
    before output-injection-ON flights. `P_lyap` (mrac.h) remains dead (unused) — left in
    place to avoid struct-layout churn.
*   **Not done:** per-axis `ref_model_type` (ADR-0005 §1) — still the global
    `mrac_flags.ref_model_type`. Augmented-error (ADR-0005 §3) is **not** pursued; this
    state-space law is the chosen rel-deg-2 mechanism instead.
*   **Weights still not persisted** across power cycle (pre-existing EEPROM gap).
