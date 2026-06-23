# Handoff prompt — Sim rebuild (Phase 1)

> Paste the block below into a **fresh** Claude Code session. It is written to be
> self-contained, to follow the project's `/grill-with-docs` then `/tdd` skills,
> and to double as a guided re-learning of the adaptive-control intuition.

---

## PROMPT TO PASTE

I want to rebuild my MRAC simulation from scratch into a clean, modular, test-driven
Python package. The current simulation lives in several large Jupyter notebooks that
neither I nor an agent can navigate or modify safely, and I have lost much of the
intuition I had when I wrote them. This rebuild is also my review: **teach me as we
go — be Socratic, make me justify each modelling choice, and do not let me hand-wave.**

**Run `/grill-with-docs` first**, then drive the build with **`/tdd`** (red-green-refactor,
test-first). Do not write simulation code before we have agreed the design and written
the failing test for the slice.

### Objective
A single `sim/` package that is the one source of truth for adaptive-control behavior,
usable in **two** scenarios from the same code:
1. **Hardware param derivation** — produce reference-model matrices, Lyapunov P, and
   PID/LQR gains that get pasted into `API/mrac.c` (firmware parity is a hard requirement).
2. **Virtual simulation** — pluggable plant so the same controller runs against the
   identified linear models *and* against a higher-fidelity 6-DOF model (Gazebo or other)
   later. The controller/adaptive-law code must not know which plant it is driving.

### Non-negotiable grounding facts (verify, don't assume)
- **Identified plants (docs/sysid_results.md, SysID 2026-06-18):**
  - Roll & pitch: relative-degree-2, 2nd-order reference model, closed-loop BW
    **wn ≈ 44.1 rad/s, zeta ≈ 0.8**, plant `K/(s(1+s/p))·e^-sT` (K~165–185, pole ~2.6–3.2 Hz, delay ~12–15 ms).
  - Yaw: **pure integrator K ≈ 37 (rel-degree 1)** → 1st-order reference model. Its
    closed-loop BW is NOT yet trustworthy (the old reading was a pre-emphasis artifact);
    treat as provisional until a clean 0.05–4 Hz, no-pre-emphasis re-fly is analyzed.
  - Z axis: not identified, deferred.
- **Measured mass = 988.5 g with battery** (NOT the notebooks' 366 g — that is 2.7× wrong
  and invalidates the cuboid inertia, 23 % hover throttle, and 4.3:1 thrust-to-weight).
  One pitch side is missing a ~68 g motor guard → model as a CG/bias offset.
- **SysID gives lumped gain K = effectiveness/J, not physical inertia.** For true inertia a
  bifilar pendulum test is needed — see `docs/bench_characterization.md` (cheap DIY bifilar +
  thrust-stand guide; produces Ixx/Iyy/Izz, CG, thrust&torque-vs-command, thrust-vs-voltage).
- **Reference-model + Lyapunov-P calculator already exists:**
  `ground_station/scripts/compute_reference_model.py` — Mode A (pure MRAC, pick wn/zeta or bw)
  and Mode B (PID-augmented: Am=Ar built from plant + PID gains, exactly notebook Cells 2–4).
  Reuse it; do not reinvent the Lyapunov solve.

### Read these before proposing a design (knowledge stack)
1. `ccc search` for any symbol before grepping (project rule; unlock gate if needed).
2. `docs/sysid_results.md` — the identified models (canonical).
3. `wiki/concepts/adaptive-control-simulations.md` and its deep-dive companion.
4. `wiki/sources/pid-mrac-notebook.md` — has the full Ar/Br/Ba/P + cascaded LQR machinery
   and a Cell-by-Cell map; this is the richest existing reference.
5. `wiki/sources/direct-mrac-ff-projection-simulation-notebook.md`,
   `adaptive-control-tutorial-notebook.md`, `adaptive-control-tutorial-2-notebook.md`.
6. `wiki/theory/mrac-theory.md`, `wiki/theory/yucelen-lectures.md`.
7. `API/mrac.c` / `API/mrac.h` — the firmware the sim must stay in parity with
   (per-axis configs, flags, regressor `[bias, θ, ω, ...]`, projection, σ/e-mod, perf-recovery).
8. `API/pid.c` — current cascaded gains (yaw rate Kp=8; pitch/roll rate Kp=5; outer Kp 3/3/6).

### Theoretical target (my thesis direction — keep the architecture open to it)
Validate **Yucelen / Lavretsky–Wise state-space MRAC** (full state, matrix Lyapunov,
no augmented error) against the *identified* models, then extend to **dense trajectory
following**, then optionally a **NN adaptive layer** trained in this sim that replaces
`Ŵᵀφ`. The package must make swapping the adaptive law (classical → σ-mod → e-mod →
DF-MRAC → set-theoretic → NN) a one-file change.

### Proposed package shape (challenge it during grilling)
```
sim/
  plant.py            # identified linear models + a 6-DOF stub; common Plant interface
  reference_model.py  # thin wrapper over compute_reference_model.py (Am, Bm, P)
  baseline.py         # cascaded PID (gains from pid.c) / LQR / pole-placement
  adaptive_law.py     # Yucelen variants behind one interface; mirrors mrac.c structure
  regressor.py        # Phi(x) — must match the firmware regressor exactly
  scenarios.py        # step, disturbance, mass-offset, dense trajectory
  run.py              # wire plant+baseline+adaptive+scenario, log, plot
tests/                # /tdd lives here; one failing test per slice before code
```

### Definition of done for Phase 1
- Each module has tests written first; `pytest` green.
- The sim reproduces a known notebook result (pick one, e.g. PID-MRAC Cell 19 disturbance
  rejection) within tolerance — proves parity with the trusted old code.
- Running the identified roll/pitch/yaw models through the matching reference model shows
  stable tracking and bounded weights.
- `/grill-with-docs` has updated `CONTEXT.md` / an ADR with the design decisions and the
  corrected physical params (mass 988.5 g, per-axis relative degree, sim↔firmware parity rule).
- A short README in `sim/` explains the two run scenarios (hardware-param vs virtual).

Start by running `/grill-with-docs` on this plan. Grill me on: which plant fidelity we
need first, whether the baseline stays cascaded-PID or moves to single-loop LQR, how the
sim regressor will be kept byte-for-byte aligned with `mrac.c`, and how the 6-DOF/Gazebo
seam should be drawn so the controller code never depends on it.
```

---

## What Phase 0 (this session) already produced — inputs the new session inherits
- `ground_station/scripts/compute_reference_model.py` — verified: numeric P == closed-form
  to 1e-13, SPD; Mode A (2nd/1st order) and Mode B (PID-augmented Ar/Br/Ba/P) both working.
- Corrected mass 988.5 g recorded; pitch guard asymmetry noted.
- Open follow-ups parked for Phase 1: trustworthy yaw closed-loop BW (re-fly 0.05–4 Hz,
  pre-emphasis OFF), and ADR-0005 (per-axis ref-model type + real P into `mrac.c`).
