# L1-NMPC grill session (2026-07-31)

> Moved verbatim out of CLAUDE.md on 2026-08-09 to cut per-turn
> context churn. CLAUDE.md keeps a compact index pointing here.

### Superseded this session — L1-NMPC grill (2026-07-31)


### L1-NMPC Grill Session (2026-07-31) — ACTIVE, nothing committed

**What was done**: fetched the missing PDF (`raw/papers/2026-07-21-Performance-Precision-and-Payloads-Adaptive-Nonlinear-MPC-for-Quadrotors.pdf`, 8 pp — the grab note had none), ingested to wiki, then a teaching session that produced real findings. `pypdf` installed to **scratchpad only** (`scratchpad/pylibs`, NOT `.venv`); extracted text at `scratchpad/l1nmpc.txt`.

**Wiki files created** (all committed to disk, untracked in git): `wiki/sources/l1-nmpc-adaptive-nonlinear-mpc-quadrotors.md`, `wiki/literature/arxiv-2109.04210.md`, `wiki/concepts/{l1-adaptive-control,matched-unmatched-uncertainty,indi-control}.md`; `wiki/index.md` + `wiki/log.md` updated; `sync_obsidian.py` run (72 pages).

**FINDING 1 — what the firmware actually has**:
- `ENABLE_PERFORMANCE_RECOVERY = 1` (`API/mrac.h:65`) → first-order LPF on `u_ad` at `omega_u`, `API/mrac.c:297-303`. **Compile-time only, no runtime gate — it has been live on every MRAC flight.** `omega_u = 30.0f` roll/pitch (`mrac.c:364,380`), `20.0f` yaw/Z (`mrac.c:398,415`).
- `mrac_flags.l1_filtering_on = 0` by default (`mrac.c:434`). It gates **`sigma_lf` low-frequency learning** (`mrac.c:260,274,285-287`), i.e. leakage toward `Whatf` (a `gam_f=16` rad/s ≈ 2.5 Hz filtered copy of `Theta`). `sigma_lf` 0.8 roll/pitch, 1.0 yaw.
- **LABEL BUG, UNFIXED**: `ground_station/gui/dashboard.py:3703` and `API/mrac.h:227` both describe `l1_filtering_on` as "low-pass filter on u_ad". **Wrong** — that flag never touches `u_ad`.

**FINDING 2 — `omega_u` is mis-set, and `docs/sysid_results.md` already proves it (no reflight needed)**:
- Measured June 2026: roll `G(s)=165/(s(1+s/19.8))·e^(−0.015s)`, lag pole **p = 19.8 rad/s**, T = 15 ms, VAF 98.7 %, **7 runs, <0.3 % spread**. Pitch p ≈ 16–18, T ≈ 12 ms, K ≈ 185. Yaw = **pure integrator K≈37/s, no pole, no delay, relative degree 1**.
- `omega_u = 30` sits **above** the plant's own pole (19.8) → the filter is **INERT, not dangerous** (earlier hypothesis of "too aggressive" was corrected against this data). Target `ω_co ≤ p/3…p/5` → **~4.0–6.6 rad/s for roll/pitch**. Phase lag at 30 rad/s = −82° (pole −56.6° + delay −25.8°); at 5 rad/s = −18.5°.
- **Yaw needs its own derivation** — no plant pole means no free filtering; do not copy roll's number.
- `p` and `T` are **mass-independent**; only `K` scales as `1/I`. → `omega_u` is settable at the desk from June data despite the battery/mass change.

**FINDING 3 — MPC readiness audit**. Has: mass 1.2961 kg, `Ixx/Iyy/Izz = 0.00839/0.00930/0.01485` (±8 %/±8 %/±3 %), arm 0.200 m, CG offset 0.0262 m, static thrust curve. T/W = **2.63** (paper's drone 4.5). Missing: `c_tau` (yaw drag-torque constant), thrust curves for motors 1–3 (`ground_station/logs/bench/thrust_20260729_191924.csv` is **motor_id=4 only**, 308 pts, CCR 2000–4000, 0–8.34 N, `vbat` 16.427→14.514 V = 12 % sag, `rpm` empty, `settle_s` 3.5–39.3 s = **load-cell settling, NOT motor dynamics**), `C_d` (derivable from existing flight logs via `m·g·tan(θ) = C_d·v`), Z-axis SysID (never wired, ADR-0004 #1).

**THESIS PIVOT (user-declared this session)**: abandoning NN-as-controller as unsafe. New direction = **the adaptive layer as a controller-agnostic augmentation**, demonstrated under the PID cascade *and* under an MPC. MPC's role changes from BC-data-generator to **baseline #2 in `sim/`** — never real-time, never ships to the STM32. This **contradicts memory `project_thesis`** (updated 2026-07-31). **`/distill-priorities` suggested but NOT yet run.**

**User's own research idea, worth preserving**: leakage-to-a-prior. Root cause of `Theta` wandering is **lack of persistent excitation** (`e→0` does NOT imply `Θ→Θ*`; Θ drifts on a manifold). Fix: replace the `Whatf` target at `mrac.c:274` with a stored `Θ_prior` identified under PE, giving cross-flight repeatability + weight persistence (closes the "weights lost on power cycle" gap).

**OPEN QUESTION posed to the user, UNANSWERED**: "Yaw has no plant pole and no delay — so what sets its `omega_u` ceiling?" My proposed answer: the **gyro noise floor**, measured props-off by `stream_log` PSD of `mrac_state.yaw.Phi[]`; floor = 3× densest trajectory's yaw-rate content from `sim/trajectories.py`. Asked whether the user instead thinks it should follow from yaw's 5×-weaker authority (`K≈37`).

**Agreed next sequence — steps 1–4 need NO drone**:
1. Set `omega_u` from p/T (roll/pitch ≈5 rad/s; yaw derived separately) — desk
2. Fix `sim/plant.py` torque path from measured thrust + inertia (kills `dF_roll_unit=0.005`, `tau=diff*r*0.25`, incoherent `_YAW_TORQUE_PER_UNIT`) — desk
3. Acceptance gate: sim must reproduce K≈165, p≈19.8 rad/s, T≈15 ms on roll and ≈37/s integrator on yaw — desk
4. Raise `gamma`, validate in sim — desk
5. Shadow-mode flight, confirm disturbance floor, **log `vbat`** (06-18 campaign had `id.vbat=0`) — FLIGHT
6. Enable `sigma_lf` — FLIGHT
7. Leakage-to-prior + weight persistence — later

**Housekeeping noted, not done**: `raw/papers/` holds 4 duplicate notes of arXiv 2109.04210 and 2 of GatedLinear (`2026-07-29-*` stub superseded by `2026-07-30-*`+PDF). GatedLinear remains **un-ingested**.
