---
title: MRAC Control Law
type: concept
tags: [mrac, adaptive-control, lyapunov, flight-control]
created: 2026-04-14
updated: 2026-04-14
sources: [API/mrac.h, API/mrac_math.c, TASK/StabilizerTask.c, TASK/send_data.c]
related_files: [API/mrac.h, API/mrac_math.c, TASK/StabilizerTask.c, TASK/send_data.c]
---

This firmware implements a 4-axis MRAC augmentation layered on top of nominal PID loops. Runtime entry is `void MRAC_Control(const CtrlerTypeDef* current_state)` (`API/mrac.h:318`), called from `Compute_Motor()` after all PID outputs are computed (`TASK/StabilizerTask.c:284-287`). The execution model is “PID nominal + adaptive correction,” not adaptive-only control.

## Core Equations in Code Terms

Per-axis state is `MRAC_AxisState_t` with key fields `e`, `Phi[]`, `Theta[]`, `u_nom`, `u_ad`, `xm` (`API/mrac.h:246-272`). Config is `MRAC_AxisConfig_t` with `gamma[]`, `What_limit[]`, `What_tol[]`, `u_max`, `mrac_to_mixer`, and leak/filter terms (`API/mrac.h:210-233`).

The implemented Lyapunov-style adaptation structure is:
- error-driven update through `gamma[i]` (`API/mrac.h:203-211`)
- projection operator limiting update near bounds (`MRAC_Projection`, `API/mrac_math.c:18`)
- optional leakage/normalization flags (`API/mrac.h:53-56`)

Important strictness note: this page documents the adaptive law **structure and governing variables** from headers/utilities. The full axis update equation body resides in MRAC implementation sources not included in the audited snippet set, so equations here are intentionally described in code-variable form rather than retyped symbolic math to avoid over-claiming.

Projection logic is explicit:
- full update in safe interior (`API/mrac_math.c:23-25`)
- full update when gradient points back inward (`API/mrac_math.c:28-30`)
- hard stop at/over limit (`API/mrac_math.c:33-35`)
- linear fade in tolerance shell (`API/mrac_math.c:38-39`)

## Basis Functions and `MAX_NUM_BASIS`

Basis width is compile-time selected:
- `NUM_BASIS 4` (`API/mrac.h:73`)
- `MAX_NUM_BASIS` computed from structured/unstructured and control-regressor flags (`API/mrac.h:75-89`)

Default build path enables structured uncertainty with control-in-regressor (`API/mrac.h:46-47,59,75-81`), so basis includes physical terms and optional `un/v` channels. `MAX_NUM_BASIS` is exported into telemetry headers (`TASK/send_data.c:299,335`) so host decoders can parse variable-length payloads.

## Activation and Fallback

MRAC compute is always called in control loop (`TASK/StabilizerTask.c:286`), but motor injection is conditional:
- `ENABLE_MRAC_OUTPUT_INJECTION == 1`: add scaled `u_ad` to PID nominal (`TASK/StabilizerTask.c:293-311`)
- otherwise shadow mode, PID-only output to mixer (`TASK/StabilizerTask.c:312-319`)

NaN/Inf guards zero invalid adaptive outputs before mixing (`TASK/StabilizerTask.c:303-306`), ensuring fallback to stable nominal PID even if adaptive states diverge.

## Saturation / Projection

Weight saturation is handled by per-component bounds `What_limit[]` and tolerance shell `What_tol[]` (`API/mrac.h:216-223`). Projection can be globally toggled with `ENABLE_PROJECTION_OPERATOR` (`API/mrac.h:52`). There are additional safeguards (`e_deadzone`, `e_freeze`, `e_sat`, `k_e`) in config (`API/mrac.h:234-238`) for transient suppression and leakage shaping.

## Telemetry Exposure (Frame B)

Frame B exports adaptive internals for each axis:
- `Theta[i]` loop up to `MAX_NUM_BASIS` (`TASK/send_data.c:341-346`)
- `u_nom` and `xm` (`TASK/send_data.c:347-355`)
- Frame sizing uses `MAX_NUM_BASIS` in length formula (`TASK/send_data.c:330-331`)

This is consumed by host parser `_unpack_frame_b` that reconstructs `mrac.*.theta_i`, `u_nom`, and `xm` (`ground_station/comm/serial_bridge.py:559-566`).

## Evidence vs Inference

Evidence-backed:
- Basis sizing, projection utility, and telemetry packing are directly anchored in `API/mrac.h`, `API/mrac_math.c`, and `TASK/send_data.c`.
- Injection/fallback behavior is anchored in `TASK/StabilizerTask.c`.

Inference-labeled:
- “Lyapunov-style” terminology follows symbol naming and projection/leakage architecture; exact stability proof conditions are not reproduced here and should be tied to the original control derivation documents when needed for formal verification.

## See Also

- [[StabilizerTask]]
- [[Control Loop Timing]]
- [[Ground-Station Binary Protocol]]
- [[MRAC Theory]] — full theory-to-code mapping (adaptation law, projection, stability)
- [[Yucelen Lectures Digest]] — video lecture summaries with code cross-references
