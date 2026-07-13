# Map: Uncertainty-aware MRAC & KF data quality

Label: wayfinder:map
Created: 2026-07-10

## Destination

A locked, literature-grounded **thesis experiment spec** covering (a) offline KF/smoothing to raise SysID flight-data quality and (b) an uncertainty-aware adaptation mechanism for the MRAC layer — each with a citable stability argument (must-have gate), a sim-first test plan, and a flag-gated firmware path whose first real-drone target is **MRAC mode 0 (passthrough)**. Implementation happens after the map, via /tdd.

## Notes

- Domain: STM32F4 quadrotor firmware (`mrac.c`, `pid.c`, `imu_update.c`), firmware-parity `sim/` package (44 tests green), `sysid_analysis.py` offline pipeline.
- Standing rules: every firmware addition behind a flag, **default OFF = today's behaviour**; sim ON-vs-OFF before flying; stability proof required for any mechanism the spec selects.
- Real-drone sequencing (user, 2026-07-10): mode 0 passthrough first; 1st/2nd-order reference-model modes wait until physical modeling (actuator dynamics, lift-force-to-PWM curve, moment of inertia — torque stand already built) improves on the closed-loop SysID done so far.
- Model-fidelity caveat (user): sim is encouraged for pre-real-test flexibility, but pending modeling may limit how informative sim A/Bs are — the map must weigh this explicitly.
- Skills to consult per session: `ccc search` first (knowledge gate), `/free-reason` for math/stability derivations, `control-teaching/` records 0004+ for the learner's KF thread, `wiki/theory/` MRAC pages.
- Key sources so far: Labbe (KF/smoothing, ch. 13), Ioannou & Sun ch. 4 (least-squares adaptive laws), Mahony 2008. See `control-teaching/RESOURCES.md` estimation section.
- Sequencing (user, 2026-07-10): the online-KF build (ticket 08) comes **first** and is a learning-driven, `/grill-with-docs`-style interactive effort — teach each filter stage until understood, then implement it. Adaptation-theory grilling (03/04) only starts after 08 resolves. Sim before firmware throughout.

## Decisions so far

<!-- one line per closed ticket: gist + link -->

- [Online KF in firmware — value assessment](issues/02-online-kf-value-assessment.md) — user decided (2026-07-10): pursue the online KF; build it step-by-step interactively with Mahony-matched Q/R (steady-state gain equivalence, not copied Kp/Ki) → spawned [Online KF — step-by-step interactive design & build](issues/08-online-kf-stepwise-build.md). Adaptation-theory work (tickets 03/04) waits until the KF build finishes.

## Not yet specified

- **Autonomous scenario detection / multi-mode "belief systems"** — the drone classifying its own operating regime (from state-dependent signals) and switching between designer-set or sim-learned trade-off modes; stability via switched-systems arguments (common Lyapunov / dwell time, MMAC literature). Stays fog until a single-mode uncertainty-aware mechanism is chosen and evaluated — the switching question is only sharp once we know what is being switched.
- **Per-weight covariance priors: designer-set vs learned from sim results** — depends on which mechanism is chosen (matrix Γ vs RLS-P) and on sim fidelity findings.
- **Firmware flag design & injection points** for the chosen mechanism (which `mrac.c` lines, telemetry additions) — specifiable only after the mechanism decision.
- **1st/2nd-order reference-model experiments** — gated on the pending physical modeling (actuator dynamics, thrust-PWM curve, inertia); becomes ticketable when those measurements land.

## Out of scope

- **Replacing the attitude estimator (Mahony) or SINS observer** — MISSION.md fence; the online-KF ticket assesses *adding* estimation value (e.g., for OF drift / data quality), not rewriting what flies the drone today.
- **Executing the experiments** — this map ends at the spec; implementation and flights are a follow-on effort (/tdd + flight campaign).
