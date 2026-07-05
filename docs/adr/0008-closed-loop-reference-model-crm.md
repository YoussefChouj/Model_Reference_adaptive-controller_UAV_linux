# 0008 - Closed-loop reference model (CRM) with analytic 2x2 Lyapunov P

*   **Status:** Accepted (implemented in `sim/`, 2026-06-24; firmware port pending)
*   **Date:** 2026-06-24
*   **Extends:** ADR-0007 (2nd-order state-space matrix-P law) — CRM is a strict superset
*   **Depends on:** ADR-0006 (sim package), ADR-0007 (state-space drive)

## Context

ADR-0007 gave roll/pitch an *open-loop* reference model: `xm` evolves from the command
`r` alone (`ẋm = Am·xm + Bm·r`) and the adaptation drives `e = x − xm` to zero. With a
real plant/model mismatch the reference is "blind" to the plant, so the early tracking
error is large and excites a big adaptation transient (peaking) — visible in the sim as
high `max_abs_err`, large overshoot, and (for `disturbance_roll`) a never-settling error.

Modern (Lavretsky / Yucelen) MRAC closes this loop: the **closed-loop reference model
(CRM)** adds an observer-like feedback term `L·(x − xm)` so the reference is pulled
toward the plant, shrinking `e` and the transient it drives. This was the "highest-value
modern-MRAC step" flagged at the end of the 2026-06-24 architecture review, and the
`sim/loop.py` wiring seam was created to host it.

CRM changes the **error dynamics** from `Am` to `Am − L·C` (with `C = [1, 0]` selecting
the measured rate), so the Lyapunov `P` — and therefore the drive gains `(Pe, Pedot)` —
must be recomputed for the new matrix. That recomputation is the load-bearing decision.

## Decision

Adopt the full CRM `L = [l1; l2]` on the measured output error, with the Lyapunov `P`
computed from an **analytic closed form** for the general (non-companion) error matrix.
CRM rides on `ref_model_type == 2`; `L = [0; 0]` is the open-loop special case, so the
power-on default is byte-identical to ADR-0007.

### 1. Reference-model update (sim/firmware)

```
e_out = x − xm                                  // measured output error
acc   = wn²·(r − xm) − 2ζwn·xm_dot + l2·e_out
xm_dot += DT·acc
xm     += DT·(xm_dot + l1·e_out)
```

`l1 = l2 = 0` reduces exactly to the ADR-0007 semi-implicit-Euler open-loop update.

### 2. Analytic 2x2 Lyapunov P — *not* offline-pasted constants

The error matrix is `A = Am − L·C = [[−l1, 1], [−(wn²+l2), −2ζwn]]`. Solving
`Aᵀ P + P A = −diag(Q1, Q2)` for the only two entries the drive needs (`B = [0;1]`):

```
c     = 2ζwn
k     = wn² + l2
alpha = l1² + l1·c + k
Pedot (p22) = (Q1 + alpha·Q2) / (2·(alpha·c + l1·k))
Pe    (p12) = c·Pedot − Q2/2
```

This collapses to the ADR-0007 forms when `l1 = l2 = 0` (verified in code and tests).
It is computed **live** each tick — no matrix library, nothing to paste — preserving the
exact property ADR-0007 fought for. `scipy.linalg.solve_lyapunov` is retained only as the
**test oracle** (`test_crm.py`), not in the loop.

This was chosen over two rejected alternatives:

*   **Restricted `L = [0; l2]`** (keeps companion form, so ADR-0007 formulas work
    unchanged). Rejected: `l2` only shifts the effective stiffness `wn²→wn²+l2`; it cannot
    place the fast real observer pole that does the actual transient suppression. The L
    sweep confirmed empirically that `l1` dominates and `l2` contributes little — this
    option would have left almost all the benefit on the table.
*   **Full `L`, scipy P solved offline and pasted as constants.** Rejected: it
    re-introduces the sim↔firmware drift surface ADR-0007 deleted — every retune of `L`,
    `Q`, or `wn` would force a re-run of `compute_reference_model.py` and a re-paste. The
    analytic form fit in three lines, so "simpler sim math" was not a real advantage.

### 3. Tuning knob and safety gating

`L` is per-axis (`crm_l1`, `crm_l2`), default `0`. As with ADR-0007 the path is reached
only when `ref_model_type == 2`, and `DEFAULT_REF_MODEL_TYPE = 0` (passthrough), so
default flight behaviour is unchanged until the operator selects 2nd-order **and** sets a
nonzero `L`. Projection, deadzone, hard-freeze, σ/e-mod, perf-recovery LPF all still apply.

## Consequences

*   **Pro:** large, monotonic transient reduction in sim. Sweeping `l1` on the identified
    roll plant: `inertia_offset_roll` `max_abs_err` 0.326→0.122 and overshoot 37%→7% at
    `l1=80`; `disturbance_roll` RMSE 0.298→0.075 (~4×); `step_roll` overshoot 61%→10%. All
    stable. CRM also shrinks the `What_lower_limit=0` footprint indirectly by keeping `e`
    small. `sim/drive.py` needed **no** change — CRM is new `(Pe, Pedot)` values plus one
    reference-model term, not a new drive adapter.
*   **Con / watch:** CRM feeds the (noisy) measured rate into the reference model, and the
    classic Lavretsky concern is that a large `L` narrows the stability margin to
    *unmodelled high-frequency dynamics*. See the Validation note — that erosion did **not**
    appear for the identified-linear + pure-delay plant in this sim, so the binding limit
    here is numerical, not robustness. Re-test on Gazebo, where real actuator / HF dynamics
    exist, before treating large `L` as safe for an output-injection-ON flight.
*   **Not done:** firmware port (new `crm_l1`/`crm_l2` config fields + the `L` term in
    `MRAC_UpdateAxis`'s reference update + the generalized `Pe/Pedot`); deferred until the
    sim CRM is exercised on the 6-DOF/Gazebo plant. Per-axis `ref_model_type` (ADR-0005 §1)
    still global.

## Validation — transport-delay margin sweep (2026-06-24)

`sim/experiments.py` Sweep C (`_crm_delay_sweep`) ramps the roll plant's transport delay
for `l1 ∈ {0,20,40,80}`; an aggressive-adaptation cross-check (symmetric limits, deadzone
off, `Q1=10·wn`, inertia mismatch) was also run. Two findings, both captured as specs in
`test_crm.py`:

*   **The Lavretsky margin erosion was not reproduced — CRM *widened* the delay margin.**
    At every tested delay (up to 10× the 15 ms nominal) and in both the benign and the
    aggressive-adaptation regime, larger `l1` gave *lower* peak error / RMSE and *more*
    delay headroom, not less (critical delay 15→45 ms as `l1` 0→80; at 45 ms `max_abs_err`
    falls with `l1`). The "large L narrows the margin" sentence in the original Consequences
    was an a-priori guess; for the identified-linear + **pure-delay** plant it is wrong. The
    plant lacks the unmodelled higher-order / actuator dynamics where the continuous-time
    CRM tradeoff actually bites — hence the Gazebo re-test caveat above.
*   **The real hard limit on `l1` is numerical: the reference model's forward-Euler
    integration.** The `xm` update self-feedback coefficient is `(1 − l1·DT)`, so the
    recurrence is stable only for `l1·DT < 2`, i.e. `l1 < 2/DT` (≈ 400 at `DT = 5 ms`),
    *independent of plant delay* (`l1=300` fine, `l1=600` diverges at both 15 ms and 45 ms).
    The closed loop hides this — the PID / `What` clamps keep the plant rate bounded while
    `xm` itself blows up — so it must be guarded explicitly. **The firmware port must clamp
    `crm_l1` (and verify the `crm_l2` 2nd-order Euler bound) against `DT`**; this replaces
    the vaguer "stability-margin abort guard" idea. `l2` only shifts effective stiffness, so
    a per-axis `l1 ≤ ~0.4/DT` (comfortably inside the `2/DT` bound) is the recommended cap.
