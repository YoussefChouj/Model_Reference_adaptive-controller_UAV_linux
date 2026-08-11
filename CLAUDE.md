## MANDATORY: Knowledge Stack First

**Before ANY investigation — no exceptions:**

| Step | Command | When it answers your question — STOP here |
| --- | --- | --- |
| 1 | `ccc search "<query>"` | Exact code locations, symbol definitions |
| 2 | Read `graphify-out/GRAPH_REPORT.md` | System-wide dependencies, which files own what |
| 3 | Read `wiki/index.md` → navigate to entry | Architecture, design decisions, known gotchas |
| 4 | Read `docs/decisions.md` | Why something was built a certain way |
| 5 | **Apify MCP** | Looping, no local answer, current/post-cutoff data, YouTube, web docs |

**After steps 1–4 return nothing AND the agent is looping:** read `wiki/concepts/external-research-tools.md` and use Apify actors to get external data. This is the escape hatch.

**Do NOT open Grep, Glob, or Read for exploration until steps 1–4 return nothing.**

After consulting the stack, unlock raw search for this session:

```
python .agent_scripts/knowledge_gate.py --unlock
```

> This is enforced by the PreToolUse hook. Grep/Glob calls will be blocked until you unlock.

---

## Session State

**Last Updated**: 2026-08-11
**Goal**: Prior-transfer wave 1 serial pipeline: `prior-01` → `prior-08` → `prior-11`. Thesis framing held pending user reading session. **Primary claim = dense trajectory tracking**; airframe-invariant dimensionless priors are *instrumental* ([ADR-0014](docs/adr/0014-dimensionless-priors-and-declared-regressor-variants.md)). Terms in [docs/glossary.md](docs/glossary.md); specs in [`.agent_contracts/prior_transfer/`](.agent_contracts/prior_transfer/README.md).

**chore/agent-workflow-hardening MERGED 2026-08-11.** The branch brought in:
- MuJoCo + plant ladder (ADR-0012), scenario-conditioned priors (ADR-0013), dimensionless priors (ADR-0014)
- Literature review → [SYNTHESIS.md](docs/literature-review-findings/SYNTHESIS.md) (read this, not the raw reports)
- SIL gate, telemetry v2 subscriptions, MicoAir radio bringup, ground station overhaul
- All prior-transfer specs (00–14) with journals; 00 + 00b done, remainder unblocked per wave structure

### Active work — prior-transfer wave 1 (serial)

| # | Spec | Blocks on | Status |
|---|------|-----------|--------|
| 00 | `What_lower_limit` sign-constraint gate | — | ✅ done |
| 00b | Restore sim↔firmware parity | 00 | ✅ done — 2–3% RMSE improvement |
| 01 | Retire Gazebo (2,049 LOC + 27 MB) | 00 | ⬜ needs user approval for commit **and** deletion |
| 08 | Declared basis dimensions + regressor variant registry | 01 | ⬜ next |
| 11 | Learning envelope vs deployment envelope | 00b | ⬜ after 08 |
| 02 | Transport-delay wrapper on 6-DOF plants | 01 | ⬜ after 01 |
| 03 | `MujocoPlant` behind `Plant` seam | 01 | ⬜ after 01 |
| 04 | SysID calibration gate for simulated plants | 02, 03 | ⬜ wave 3 |
| 05 | Prior factory + run logging | 00b, 08 | ⬜ after 08 |
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
| External research | Apify MCP | `wiki/concepts/external-research-tools.md` — live web, YouTube, fact-check, escape from loops |

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