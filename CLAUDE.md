## Knowledge Stack (protocol)

`.cursor/rules/knowledge-stack.mdc` — query priority and tool guide.

---

## Session State

**Last Updated**: 2026-08-12
**Goal**: Prior-transfer wave 1 serial pipeline: `prior-01` → `prior-08` → `prior-11` → `prior-05`. Thesis framing held pending user reading session. **Primary claim = dense trajectory tracking**; airframe-invariant dimensionless priors are *instrumental* ([ADR-0014](docs/adr/0014-dimensionless-priors-and-declared-regressor-variants.md)). Terms in [docs/glossary.md](docs/glossary.md); specs in [`.agent_contracts/prior_transfer/`](.agent_contracts/prior_transfer/README.md).

**chore/agent-workflow-hardening MERGED 2026-08-11.** The branch brought in:

- MuJoCo + plant ladder (ADR-0012), scenario-conditioned priors (ADR-0013), dimensionless priors (ADR-0014)
- Literature review → [SYNTHESIS.md](docs/literature-review-findings/SYNTHESIS.md) (read this, not the raw reports)
- SIL gate, telemetry v2 subscriptions, MicoAir radio bringup, ground station overhaul
- All prior-transfer specs (00–14) with journals; 00 + 00b done, remainder unblocked per wave structure

**Workflow-hardening sub-session 2026-08-12** (this session, uncommitted on `main`):

- `.cursor/rules/subagent-model-pinning.mdc` (new, always-on) — forbids `model:` override on Task tool; surfaces Cursor fallbacks instead of absorbing them.
- `.cursor/skills/uav-conductor/SKILL.md` (new, 306 lines) — full conductor playbook. Was referenced in `AGENTS.md` but did not exist. Adds: knowledge-stack preflight, pre-cleared permissions in delegation, four-check verification gate (test SHA, suite, scope, graph rebuild), test-source redaction, `tests/` excluded list.
- `.cursor/agents/uav-conductor.md` — rewritten 250→35 lines; model pin + pointer at the skill.
- `.cursor/agents/AGENTS.md` — `configured_model` + `actual_model` journal convention; pipeline sequence now has verify leg between implement and review.
- `.cursor/skills/implement-spec/SKILL.md` — added §1b knowledge-stack preflight, when-to-use-web table, test-source redaction section.
- `.cursor/skills/review-spec/SKILL.md` — both model ids in header template.

**Net effect on the next pipeline call:**
- Implementer dispatches on configured model, or stops and tells user.
- Implementer sees test output only, not test source — cannot game assertions.
- Conductor's gate runs `git diff --name-only HEAD -- 'sim/tests/' 'tests/'`; any test file in diff = automatic rejection.
- Journal entries now carry configured + actual model ids for audit.

**`sim/` architecture review 2026-08-12** (this session, uncommitted):

`.agent_contracts/sim-arch-2026-08-12/` — five specs from the deep-modules pass:

- `00-summary.md` — verdict; two of six CLAUDE.md candidates were stale (no `axis_priors` ever existed; `recorder.py`/`run.py` schema duplication was overstated); three real issues + one missing-symbols gap.
- `01-prior-05-factory-recovery.md` — `prior-05` is **half-landed**: commit on `main` declares the schema but does not implement `PriorFactory`, `PriorLibrary`, `to_dimensionless`/`from_dimensionless`, `ConvergenceResult`, `TargetConstraints`, `FEATURE_SERIES_COLUMNS`. Verified by `grep -rn`. **Blocks `prior-06`, `prior-09`, `prior-12`.**
- `02-run-decompose.md` — `sim/run.py` `run()` does four jobs (loop + log + calibrator + artifact). Add `sim/artifact.py` (`RunArtifactWriter`) and `sim/calibrator_step.py` (`CalibratorStep`). Adds `theta_seed` branch to `AdaptiveLaw` so `_seeded_deploy` in `experiments.py` can be deleted.
- `03-experiments-split.md` — split the five sweep families into `sim/sweeps/*.py`; add `sim/sweep_runner.py` for structured JSON+Markdown output (today's sweeps go to stdout only — not citable).
- `04-manifest-consolidate.md` — schema lives in two places (`sim/manifest.py` and `sim/run.py:_report`). Single `ManifestPayload` dataclass in `sim/manifest_schema.py`. Bump version `"1.0"` → `"1.1"`.
- `05-plant-seam-leak.md` — `MujocoPlant.is_available()` duplicates `MujocoBridge.is_available()`. Add abstract `is_available()` to `Plant` ABC.

Recommended wave order: `02` → `04` → `01` → `05` (parallel worktree) → `03`. Total 4–6 h agent work.

**Apify MCP auth resolved this session** (per user). All paths through `user-apify` are live; `RAG Web Browser` and `search-actors` are reachable without further setup.

**Pending (deliberately not done):**
- User-scope Cursor rule via `cursor_dialog` — blocked by Privacy Mode. Project-scope `.cursor/rules/` version is in place.
- prior-05 status on the table below is now stale; per the review above, **the symbols it promised are not in the codebase**. Spec `01-prior-05-factory-recovery` must land before `prior-06`/`prior-09`/`prior-12`.

**Not committed:** all changes sit on working tree. Open question for user: commit on `workflow/conductor-skill-v1` branch, or push straight to `main`? Uncommitted changes do not break `prior-11` work; separate concern.

### Active work — prior-transfer wave 1 (serial)

| # | Spec | Blocks on | Status |
|---|------|-----------|--------|
| 00 | `What_lower_limit` sign-constraint gate | — | ✅ done |
| 00b | Restore sim↔firmware parity | 00 | ✅ done — 2–3% RMSE improvement |
| 01 | Retire Gazebo (2,049 LOC + 27 MB) | 00 | ✅ done |
| 08 | Declared basis dimensions + regressor variant registry | 01 | ✅ done — 2026-08-11 |
| 11 | Learning envelope vs deployment envelope | 00b | ✅ done — 2026-08-11 |
| 02 | Transport-delay wrapper on 6-DOF plants | 01 | ⬜ after 01 |
| 03 | `MujocoPlant` behind `Plant` seam | 01 | ⬜ after 01 |
| 04 | SysID calibration gate for simulated plants | 02, 03 | ⬜ wave 3 |
| 05 | Prior factory + run logging | 00b, 08, 11 | ⚠️ half-landed — see spec `01-prior-05-factory-recovery` |
| 06 | Prior injection seam (3 channels) | 05 | ⬜ after 05 |
| 07 | `RigPlant` + rig SysID incl. Z axis | 00 | ⬜ Phase A in-pipeline; B/C human operator |
| 09 | Cross-airframe prior invariance sweep | 03, 05, 06, 08 | ⬜ wave 4 |
| 10 | Trajectory presets + `Δs` sweep | 01 | ⬜ wave 2 — **carries primary claim** |
| 12 | Integral CL (history stack + rank condition) | 08, 11 | ⬜ wave 3 |
| 13 | Offline prior fitting from real + public logs | 04, 08 | ⬜ wave 4 |
| 14 | Attention vs uniform stack weighting | 12 | ⬜ wave 4 — **first cut under schedule pressure** |

**Novelty ledger** (detail + citations in [SYNTHESIS.md](docs/literature-review-findings/SYNTHESIS.md) §3):

- **Prior art**: Chowdhary ICRA 2013 (concurrent learning), Girard 2024 (dimensionless transfer), FAMLE IROS 2020
- **Still yours**: dimensionless MRAC weight vectors via `1/K` matching; prior library as σ-mod attractor; attention over CL history stack; `Δs` as independent variable; transferring a populated stack
- **Falsified**: CL replaces σ-mod/deadzone; RBF bases on this hardware; TS/LPV proof route for attention

**BLOCKED — user decision, deliberately**: contribution claims in ADR-0013/0014. User needs to read SYNTHESIS.md §7 → Chowdhary ICRA 2013 first, then Girard 2024, Neural-Fly, CDC 2010+ICL, FAMLE before the framing session.

**Standing constraints**: prior = dimensionless `Θ̃`; plant tags are the rescaling key; scenarios parameterised relatively; regressor is a declared variant; never learn on a delay-free plant.

**Hard safety constraints**:
- No probe tooling, no flashing, no motor/arm-state code; EKF stays shadow-mode
- `prior-01` must ask user before committing **and** before deleting
- Specs 08–14 must not touch `API/`; every firmware change lands in `sim/` first with a parity test

### Closed sessions

| Session | Closed |
|---------|--------|
| ADR-0011 Phase 3+4 EKF build fix | 2026-07-23 |
| Sim rebuild (TDD plant/reference/adaptive/run) | 2026-06-23 |
| Sysid session (firmware audit, Z-axis deferred) | 2026-06-16 |

### Known Remaining Issues

- **Optical flow XY drift** — `locxPID.FB` / `locyPID.FB` drift ~50 cm over short flights; expected OF sensor behaviour.
- **MRAC adaptive weights lost on power cycle** — no EEPROM persistence yet. Future work.
- **SysID deferred safety gates (ADR-0004 #2/#3)** — `sysid_abort_condition()` still lacks battery-low, telemetry/OF-stale, and sustained-saturation aborts (no clean `bat_warn`/`of_valid` symbols exist — needs thresholds defined first). Green-zone **hard** boundary (±0.7 m → controlled descent) not implemented; only the soft ±0.5 m → RECOVERY exists. RC dead-man remains final authority. Do before output-injection-ON SysID flights.
- **SysID Z-axis not wired** — `SYSID_AXIS_Z` is rejected in `SysID_Start`; full Z excitation needs a `Z_ratePID.Des` injection site + its own altitude/ground-effect abort guards (ADR-0004 #1).
- **ADR-0004 doc drift** — dec.7 says 200 Hz (firmware emits the 0x03 ID frame at 100 Hz); no separate `PRECHECK` FSM state (gates run synchronously in `SysID_Start`); manual abort is CMD `0x14` idx6, not `0x0D`. Functionally fine; amend ADR when convenient.

---

## Workflow altitude

Pick the right entry point for the task:

| Command | Use when |
|---------|----------|
| `/dispatcher` | Main session: what to build, which lane, flight-test queue |
| `/wayfinder` | One effort too big for a single spec; charts a map, one ticket per session |
| `/uav-planner` | One task → `spec.md`. **Interactive** — grills you first. Never delegated. |
| `/uav-conductor` | Implement → review → adjudicate, unattended, from an existing spec |

Pipeline reference: `.cursor/agents/AGENTS.md`.

---

## On-demand skills (invoke by `name:` in frontmatter)

| Skill | Use when |
|-------|----------|
| `goal-loop` | Write a `/goal` contract for long autonomous runs with verifiable stop conditions |
| `decisions` | After large changes: what decisions are you unsure about? |
| `next-decision` | Work through open decisions one at a time (forward-looking) |
| `setup-help` | Guide the user through any multi-step setup, one step at a time |
| `git-worktree` | Spawn a parallel agent on this repo without file collisions |
| `anti-sleep` | Keep the Linux workstation awake during long runs |

Skills live in `~/.cursor/skills/` (global) and `.claude/skills/` (also for Claude Code).

---

## After editing code

```
python -c "from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))"
```

Full knowledge graph protocol: `.cursor/rules/knowledge-stack.mdc`.

---

## Session digest

On session end: write `sessions_summary/YYYY-MM-DD-digest.md`. Template: `sessions_summary/POLICY.md` §Digest protocol.
