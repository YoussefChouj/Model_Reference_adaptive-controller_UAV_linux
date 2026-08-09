## MANDATORY: Knowledge Stack First

**Before ANY investigation — no exceptions:**

| Step | Command | When it answers your question — STOP here |
| --- | --- | --- |
| 1 | `ccc search "<query>"` | Exact code locations, symbol definitions |
| 2 | Read `graphify-out/GRAPH_REPORT.md` | System-wide dependencies, which files own what |
| 3 | Read `wiki/index.md` → navigate to entry | Architecture, design decisions, known gotchas |
| 4 | Read `docs/decisions.md` | Why something was built a certain way |

**Do NOT open Grep, Glob, or Read for exploration until steps 1–4 return nothing.**

After consulting the stack, unlock raw search for this session:

```
python .agent_scripts/knowledge_gate.py --unlock
```

> This is enforced by the PreToolUse hook. Grep/Glob calls will be blocked until you unlock.

---

## Session State

**Last Updated**: 2026-08-05
**Goal**: Gazebo retired; pivot to MuJoCo + the plant ladder. **Primary thesis claim = dense trajectory tracking**; airframe-invariant dimensionless priors are *instrumental* to it ([ADR-0014](docs/adr/0014-dimensionless-priors-and-declared-regressor-variants.md)). Design in [ADR-0012](docs/adr/0012-retire-gazebo-mujoco-plant-ladder.md) + [ADR-0013](docs/adr/0013-scenario-conditioned-adaptive-priors.md) + ADR-0014; terms in [docs/glossary.md](docs/glossary.md); specs 00–14 in [`.agent_contracts/prior_transfer/`](.agent_contracts/prior_transfer/README.md).

**Literature review LANDED 2026-08-06.** Three reports in [`docs/literature-review-findings/`](docs/literature-review-findings/); the operative summary with verified citations is [`SYNTHESIS.md`](docs/literature-review-findings/SYNTHESIS.md). **Read SYNTHESIS.md, not the raw reports** — reports 1 and 3 systematically over-report novelty and report 1 contains an outright error on σ-mod. Report 2 (Fable) is the reliable one; five of its load-bearing citations were verified against primary sources.

**Just did** (2026-08-06, all on disk, nothing staged in git):
- Wrote `docs/literature-review-findings/SYNTHESIS.md` — report ranking, verified-citation table, novelty ledger, the falsified list, benchmark anchors, and a §7 reading path for the held framing session.
- **Rewrote `prior-12` to integral CL.** Classical CL needs `ẋ` (angular acceleration); ICL (Parikh/Kamalapurkar/Dixon, IJACSP 2019) removes it. Added a pluggable stack-weighting seam (change 8) for `prior-14`.
- **`prior-11`**: `e_deadzone → 0` now **forbidden** (bursting); deadzone floored at `k·σ_noise`, `k∈[2,3]`, measured; projection stays on in both envelopes; new change 5 bounds `Γ` by the delay margin; new change 6 requires writing the heuristic-justification argument.
- **`prior-10`**: `Δs` promoted to headline variable (no quadrotor paper treats it as one); max error + transient error added; published anchors + lemniscate preset in constraints.
- **`prior-13`**: Phase B unheld; NeuroBEM + Blackbird are the backbone, UZH-FPV demoted pending an actuator-signal check.
- **New `prior-14-attention-stack-query`** (spec + journal) — attention vs uniform stack weighting as a controlled comparison, incl. a fair-baseline arm against SVM vs FIFO eviction. User chose "build it" over "park it".
- Corrected `wiki/concepts/attention-mechanism.md` — the TS/LPV "a proof route already exists" claim was overstated; needs frozen keys + bounded membership-function derivatives. Convex-hull result stands.
- Added **framing HOLD** headers to ADR-0013 and ADR-0014 (decisions stand; contribution claims held).

**BLOCKED ON — user decision, deliberately**: the **novelty framing** of ADR-0013/0014. User's words: *"since i did not have the chance to read the deep research reports and the cited papers, i feel the need to properly understand the fundamental things that form the basis for the framing of my thesis maybe during a separate grilling session."* **Do not rewrite the contribution claims until that session runs.** Reading path: SYNTHESIS.md §7 — Chowdhary ICRA 2013 first (does it port weights/stack, or only the baseline controller? the whole remaining contribution hinges on this), then Girard 2024, Neural-Fly, CDC 2010 + ICL, FAMLE.

**Unblocked now — wave 1 is serial**: `prior-01` (retire Gazebo — **needs user approval twice**: before committing the dirty tree, and before deletion) → `prior-08` → `prior-11`. Prompts in [`.agent_contracts/prior_transfer/PROMPTS.md`](.agent_contracts/prior_transfer/PROMPTS.md). **`prior-14` has no prompt yet** — PROMPTS.md was not updated.

### Prior-transfer pivot (2026-08-05) — `/grill-with-docs` session

| # | Spec | Blocks on | Status |
|---|------|-----------|--------|
| 00 | `What_lower_limit` sign-constraint gate | — | ✅ done — slots 1–5 floored at 0 on **every** axis; slot 0 unlocked to `-What_limit[0]` on pitch/roll/yaw but **not z** (`mrac.c:353-355`) |
| 00b | Restore sim↔firmware `What_lower_limit` parity | 00 | ✅ done — `for_axis()` sets slot 0 = `-What_limit[0]` on pitch/roll/yaw, `[0.0]*6` on z; parity test added; 206 passed / 3 skipped. **Verdict: real but modest (2–3 % RMSE); `e_deadzone` is the dominant suppressor** |
| 01 | Retire Gazebo (2,049 LOC + 27 MB) | 00 | ⬜ needs user approval for commit **and** deletion |
| 02 | Transport-delay wrapper on 6-DOF plants | 01 | ⬜ mandatory before any 6-DOF prior learning (ADR-0006 D4) |
| 03 | `MujocoPlant` behind the `Plant` seam | 01 | ⬜ **authors** `sim/models/jx_fly.xml` from `CANONICAL_AIRFRAME` — the classmate's referral is the Menagerie Crazyflie 2.0 (33 g), a structural template only. Adds render + runtime randomisation |
| 04 | SysID calibration gate for simulated plants | 02, 03 | ⬜ re-scoped by ADR-0014 D2 — no longer a gate that blocks prior learning, now the service that **enables** transfer (`K` per plant is what gets divided out) |
| 05 | Prior factory + run logging | 00b, 08 | ⬜ starts on `IdentifiedPlant`; emits dimensionless `Θ̃`; owns relative scenario parameterisation (ADR-0014 D5) |
| 06 | Prior injection seam (3 channels) | 05 | ⬜ `sim/` only; mismatched-prior damage test promoted to `prior-09`'s precursor |
| 07 | `RigPlant` + rig SysID incl. missing Z axis | 00 | ⬜ Phase A only in-pipeline; B/C human operator |
| 08 | Declared basis dimensions + regressor variant registry | 01 | ⬜ wave 1, **additive only** — `Φ` bit-identical, golden-vector test unmodified. Blocks 05 |
| 09 | Cross-airframe prior invariance sweep | 03, 05, 06, 08 | ⬜ wave 4 |
| 10 | **Trajectory presets + `Δs` sweep** | 01 | ⬜ wave 2 — **carries the primary claim**. Run before 05 (shared `scenarios.py`) |
| 11 | Learning envelope vs deployment envelope | 00b | ⬜ wave 1 — `prior-00b` showed `e_deadzone` halts adaptation at ~0.2 s. Envelope, not bounds, limits learning |
| 12 | **Integral** CL (history stack + rank condition) | 08, 11 | ⬜ wave 3 — **unheld, rewritten to ICL 2026-08-06**. Classical CL needs `ẋ`; would pass in sim and fail on hardware |
| 13 | Offline prior fitting from real + public flight logs | 04, 08 | ⬜ wave 4 — **unheld**. NeuroBEM + Blackbird backbone; UZH-FPV demoted pending actuator check |
| 14 | Attention vs uniform stack weighting — controlled comparison | 12 | ⬜ wave 4 — highest novelty (all 3 reports found no precedent), least proven. **First thing cut under schedule pressure** |

**Thesis priority (settled 2026-08-05, confirmed by the review)**: **dense trajectory tracking is the primary claim**; airframe-invariant priors are instrumental to it. The review found `Δs` (waypoint spacing) is genuine white space *and* it sits on the primary claim — the priority survived contact with the literature.

**Novelty ledger after the review** (detail + citations in [SYNTHESIS.md](docs/literature-review-findings/SYNTHESIS.md) §3):
- **Prior art, not ours**: cross-vehicle adaptive transfer (Chowdhary/Wu/Cutler/How, ICRA 2013 — *concurrent learning*, flown at MIT RAVEN); dimensionless policy transfer as a mechanism (Girard, *Mathematics* 12(5):709, 2024); prior-library-with-runtime-selection (FAMLE, IROS 2020).
- **Still unclaimed**: dimensionless **MRAC weight vectors** via the `1/K` matching argument; the prior library realised **as a σ-mod attractor in MRAC weight space**; **attention over a CL history stack**; **`Δs` as an independent variable**; transferring a *populated* stack.
- **The interlock** (strongest available framing, to be tested in the held session): a stack recorded on plant A has `εⱼ` scaled by plant A, so transferring a stack is ill-posed *until* it is non-dimensionalised. The `Θ̃` work is the precondition for the transfer work, not a side quest.
- **Falsified**: "CL replaces σ-mod/e-mod/deadzone" (projection stays; deadzone stays, floored at the noise floor — bursting); RBF bases on this hardware (rank condition ⇒ 125 basis functions needs 125 independent points vs 6); the wiki's "TS/LPV proof route already exists" for attention.
- **Bars to clear**: Neural-Fly 2.9 cm still-air RMSE (42 % better than L1, 35 % than INDI); RAPTOR 0.19 m on a 5.5 s Crazyflie figure-8; Pereida/Schoellig **74 %** cross-quadrotor first-iteration reduction — if dimensionless transfer does not approach that, the invariance bonus becomes a (publishable) negative result.

**Note**: `docs/decisions.md` uses **date-titled** entries, never `ADR-NNNN` headings — a task created a collision that way on 2026-08-05.

**Standing constraints from this session**: a prior is dimensionless `Θ̃` (raw `Θ` + `(K, p, T)` stored alongside, never instead); plant tags are the rescaling key, not a transfer barrier; scenarios are parameterised relatively, never in absolute magnitudes; the regressor is a declared variant, not a fixture; never learn priors on a delay-free plant; numeric search is seeded deterministic code, never an LLM.

**Hard safety constraints — repeat verbatim across compaction**:
- `.cursor/rules/hardware-safety.mdc` (always-apply): no probe tooling, no flashing, no motor/arm-state code, EKF stays shadow-mode unless explicitly approved.
- `.cursor/cli.json` deny list: `pyocd`, `openocd`, `UV4`, `git push`, `git reset`, writes to `OBJ/`, `*.hex`. **Deny beats allow and beats `--force`.**
- **Never route a task through the pipeline if it requires touching the target board. Bench interaction stays with the human operator.** `prior-07` Phases B/C spin motors → human operator only, not a pipeline leg.
- `prior-01` must stop and ask the user **before committing** and **before deleting**. Git history is the only archive. Nothing has been committed or deleted yet.
- Specs 08–14 must not touch `API/`. Firmware is normative for integration; every firmware change lands in `sim/` first with a parity test (`mbd_workflow/README.md`, governing principle 1).

### ADR-0011 Session (2026-07-23) — closed

### ADR-0011 Session (2026-07-23)

| # | Task | Status |
|---|------|--------|
| 1 | Build fix: `USER/JX_FLY.uvprojx` — add `ekf.c` + `calib.c` to API file group | ✅ done → commit `3e1c828` |
| 2 | Build fix: `TASK/StabilizerTask.c` — remove `static` from `s_cal_trim`/`s_cal_hot` (extern needed by `send_data.c`) | ✅ done → commit `3e1c828` |
| 3 | Build green: uVision rebuild with 0 errors | ✅ done (69 warnings, all pre-existing) |
| 4 | v14 free-flight validation | pending → produce flight log with `of.lin_acc_x_mg` for EKF replay tool |
| 5 | EKF offline replay (`sim/tools/replay_ekf_flight.py`) against v14 flight log | pending |
| 6 | ADR-0011 build-fix log + ADR status update | ✅ done → docs/adr/ADR-0011-auto-imu-calibration.md |

### Sim Rebuild Session (closed) — 2026-06-23

| # | Task | Status |
|---|------|--------|
| 1 | `/grill-with-docs` — package design, plant fidelity, regressor alignment, 6-DOF seam | ✅ done → ADR-0006 + CONTEXT.md |
| 2 | `/tdd` slice 1 — `plant.py` | ✅ done → 6 tests green (yaw integrator, roll ramp-slope=K, ZOH+N=3 delay, Plant seam, Gazebo stub) |
| 3 | `/tdd` slice 2 — `reference_model.py` | ✅ done → 7 tests green (firmware-parity Euler recurrence, scalar P=1/2wn, passthrough/1st/2nd, bumpless reset, for_axis factory) |
| 4 | `/tdd` slice 3 — `adaptive_law.py` + `regressor.py` | ✅ done → 17 tests green (regressor golden-vector parity mrac.c:65-91 + cross-coupling; adaptive law gradient/projection/freeze/deadzone/tanh-sat/perf-recovery LPF, lower-bound=0 firmware quirk, for_axis gains) |
| 5 | `/tdd` slice 4 — closed-loop wiring (`baseline.py` + `scenarios.py` + `run.py`) | ✅ done → 14 tests green (RatePID parity pid.c ComputePID incl EMin conditional-integ/clamps/u_nom÷mrac_to_mixer; closed-loop runner mrac.c:424-485 unit chain rad/s↔deg/s↔Nm; per-run artifacts ADR-0006 D7). 44 tests total. |
| 6 | `sim/README.md` + session-end distill | ✅ done → README (two scenarios, unit chain, findings); ADR-0006 D7 artifacts gitignored |

### Sysid Session (closed) — 2026-06-16

Audited firmware (MRAC/leakage/gyro_filter/bypass/FSM clean); fixed Z-axis no-op + OF self-reset; wrote `sysid_analysis.py`; added live FSM-state telemetry (0x03 frame 90→91 B, proto 3→4). See `docs/progress.md` / git history. Deferred: uVision build, SysID safety gates, full Z wiring.

### Known Remaining Issues (future work)

*   **Optical flow XY drift** — `locxPID.FB` / `locyPID.FB` drift ~50 cm over short flights; expected OF sensor behaviour.
*   **MRAC adaptive weights lost on power cycle** — no EEPROM persistence yet. Future work.
*   **SysID deferred safety gates (ADR-0004 #2/#3)** — `sysid_abort_condition()` still lacks battery-low, telemetry/OF-stale, and sustained-saturation aborts (no clean `bat_warn`/`of_valid` symbols exist — needs thresholds defined first). Green-zone **hard** boundary (±0.7 m → controlled descent) not implemented; only the soft ±0.5 m → RECOVERY exists. RC dead-man remains final authority. Do before output-injection-ON SysID flights.
*   **SysID Z-axis not wired** — `SYSID_AXIS_Z` is rejected in `SysID_Start`; full Z excitation needs a `Z_ratePID.Des` injection site + its own altitude/ground-effect abort guards (ADR-0004 #1).
*   **ADR-0004 doc drift** — dec.7 says 200 Hz (firmware emits the 0x03 ID frame at 100 Hz); no separate `PRECHECK` FSM state (gates run synchronously in `SysID_Start`); manual abort is CMD `0x14` idx6, not `0x0D`. Functionally fine; amend ADR when convenient.

---

## Free Model Routing

When a subtask does not require Claude-level reasoning, offload it to save tokens:

*   /free \[task\] — general purpose free model routing
*   /free-review — code review via free coder model
*   /free-translate — Chinese↔English translation
*   /free-reason — control theory / math analysis
*   /update-models — refresh the model registry (run weekly)

Model registry: ~/.claude/openrouter\_models.json (auto-updated)  
Rate limits: 20 req/min, 1000 req/day (with $10+ OpenRouter credits)

---

## graphify

This project has a graphify knowledge graph at graphify-out/.

Rules:

*   Before answering architecture or codebase questions, read graphify-out/GRAPH\_REPORT.md for god nodes and community structure
*   If graphify-out/wiki/index.md exists, navigate it instead of reading raw files
*   After modifying code files in this session, run `python3 -c "from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))"` to keep the graph current

---

## Multi-Agent Workflow

This project uses a layered agent architecture:

*   **Claude Code** (you): orchestrator, architect, final validator
*   **Copilot**: execution layer with contract-based delegation to free models
*   **Free OpenRouter models**: code generation only, no decision authority
*   **Deterministic checker**: build/lint/test/scope gates, zero LLM cost

### Key files

*   `.agent_scripts/implementer.py` — calls free models with task contracts
*   `.agent_scripts/checker.py` — deterministic validation gates
*   `.agent_scripts/log_lesson.py` — structured learning log
*   `.agent_memory/lessons.jsonl` — accumulated project lessons (read before planning)
*   `.agent_memory/costs.jsonl` — token/latency tracking per model call
*   `.agent_contracts/` — task contracts (one per atomic task)
*   `.agent_reports/` — checker gate reports

### When you receive a complex task

Use the `/orchestrator` skill to decompose and delegate.

### When verifying Copilot's work

Read: contract + checker report + changed files. Verify architectural intent is preserved.

---

## Coding Behavior Guidelines

Extracted from Karpathy's coding behavior principles (forrestchang/andrej-karpathy-skills).

### 1\. Think Before Coding — Surface Confusion

Don't assume. Don't hide confusion.

Before implementing:

*   State your assumptions explicitly. If uncertain, ask.
*   If multiple interpretations exist, present them — don't pick silently.
*   If a simpler approach exists, say so. Push back when warranted.
*   If something is unclear, stop. Name what's confusing. Ask.

### 2\. Simplicity First

Minimum code that solves the problem. Nothing speculative.

*   No features beyond what was asked.
*   No abstractions for single-use code.
*   No "flexibility" or "configurability" that wasn't requested.
*   No error handling for impossible scenarios.
*   If you write 200 lines and it could be 50, rewrite it.

### 3\. Surgical Changes

Touch only what you must. Clean up only your own mess.

*   Don't "improve" adjacent code, comments, or formatting.
*   Don't refactor things that aren't broken.
*   Match existing style, even if you'd do it differently.
*   If you notice unrelated dead code, mention it — don't delete it.
*   Every changed line should trace directly to the user's request.

### 4\. Goal-Driven Execution

Define success criteria. Loop until verified.

Transform tasks into verifiable goals. For multi-step tasks, state a brief plan:

```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
```

Strong success criteria allow independent looping. Weak criteria require constant clarification.

### 5\. Manage the Context Window

*   Read only the files you need for the current task.
*   Don't re-read files you just wrote — the tool tracks state.
*   Prefer targeted Grep/Glob over full directory reads.
*   Summarize long outputs rather than quoting them wholesale.

---

## Knowledge Stack

| Layer | Tool | Query method |
| --- | --- | --- |
| Code search | CocoIndex | `ccc search "query"` |
| Code graph | Graphify | Read `graphify-out/GRAPH_REPORT.md` |
| Knowledge wiki | LLM Wiki | `/wiki` or read `wiki/index.md` |
| Project wiki | Project Wiki | `/project-wiki` for architecture questions |
| Decisions | decisions.md | Read `docs/decisions.md` |
| Interfaces | interfaces.md | Read `docs/interfaces.md` |
| Lessons | lessons.jsonl | Read `.agent_memory/lessons.jsonl` |

### Query priority

```
1. ccc search      → exact code locations ("where is X?")
2. GRAPH_REPORT.md → system dependencies ("what depends on X?")
3. wiki/           → conceptual understanding ("why was X designed this way?")
4. docs/decisions.md → architectural choices ("what was decided about X?")
5. docs/interfaces.md → cross-subsystem contracts
6. .agent_memory/lessons.jsonl → past task learnings
```

### Adding knowledge

Drop sources in `raw/`, then run `/wiki` to ingest.

### After wiki updates

Run `/free-graphify` to re-index wiki pages in the knowledge graph.  
Sync to Obsidian: `python3 scripts/sync_obsidian.py`

---

## Wiki

This project has an LLM wiki at `wiki/`. Consult `wiki/index.md` for questions about concepts, architecture, and design decisions. Keep the wiki updated when knowledge evolves.