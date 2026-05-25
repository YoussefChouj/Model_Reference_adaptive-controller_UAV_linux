## Session State

**Last Updated**: 2026-05-23
**Goal**: TWC (Target Waypoint Command) full-stack debugging and safety hardening — all core issues resolved. Firmware requires rebuild + reflash for session 2026-05-23 changes.

### Task Breakdown

| # | Task | Status |
|---|------|--------|
| 1 | Investigate arming logic for Virtual RC / SDK mode | ✅ |
| 2 | Fix firmware to accept Virtual RC bounds for arming | ✅ |
| 3 | Fix firmware to automatically arm when SDK ARM REQ is held | ✅ |
| 4 | Fix UART burst coalescing (multi-frame parser, buffer 128B) | ✅ |
| 5 | Fix TWC_arrived mixed-unit bug (XY cm, Z m → ×0.01f) | ✅ |
| 6 | Fix dashboard XY unit display (÷100 cm→m) and send (×100 m→cm) | ✅ |
| 7 | Add Z setpoint rate limiter (0.005 m/cycle ≈ 0.5 m/s) | ✅ |
| 8 | Add two-phase TWC safe liftoff (0.5 m intermediate + 1 s wait) | ✅ |
| 9 | Add drone_mode SBUS ch5 (IDLE/FLY/LAND) | ✅ |
| 10 | Add SBUS ch8 rising-edge TWC trigger | ✅ |
| 11 | Update all codebase docs and memory | ✅ |

### Known Remaining Issues / Next Steps

- **Firmware must be rebuilt and reflashed** — changes from session 2026-05-23 (items 4-10) are in source but not yet in OBJ/. Rebuild in Keil5 and flash before testing.
- **Optical flow XY drift** — `locxPID.FB` and `locyPID.FB` drift ~50 cm over short flights. This is expected OF sensor behaviour, not a firmware bug. TWC_arrived threshold (0.15 m) accounts for some drift but a tighter threshold may miss.
- **ch5 / ch8 RC transmitter mapping** — must be physically assigned on transmitter. ch10 = kill switch (existing, unchanged).
- **MRAC adaptive weights lost on power cycle** — no EEPROM persistence yet. Future work.


---

## Free Model Routing
When a subtask does not require Claude-level reasoning, offload it to save tokens:
- /free [task] — general purpose free model routing
- /free-review — code review via free coder model
- /free-translate — Chinese↔English translation
- /free-reason — control theory / math analysis
- /update-models — refresh the model registry (run weekly)

Model registry: ~/.claude/openrouter_models.json (auto-updated)
Rate limits: 20 req/min, 1000 req/day (with $10+ OpenRouter credits)

---

## graphify

This project has a graphify knowledge graph at graphify-out/.

Rules:
- Before answering architecture or codebase questions, read graphify-out/GRAPH_REPORT.md for god nodes and community structure
- If graphify-out/wiki/index.md exists, navigate it instead of reading raw files
- After modifying code files in this session, run `python3 -c "from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))"` to keep the graph current

---

## Multi-Agent Workflow

This project uses a layered agent architecture:

- **Claude Code** (you): orchestrator, architect, final validator
- **Copilot**: execution layer with contract-based delegation to free models
- **Free OpenRouter models**: code generation only, no decision authority
- **Deterministic checker**: build/lint/test/scope gates, zero LLM cost

### Key files
- `.agent_scripts/implementer.py` — calls free models with task contracts
- `.agent_scripts/checker.py` — deterministic validation gates
- `.agent_scripts/log_lesson.py` — structured learning log
- `.agent_memory/lessons.jsonl` — accumulated project lessons (read before planning)
- `.agent_memory/costs.jsonl` — token/latency tracking per model call
- `.agent_contracts/` — task contracts (one per atomic task)
- `.agent_reports/` — checker gate reports

### When you receive a complex task
Use the `/orchestrator` skill to decompose and delegate.

### When verifying Copilot's work
Read: contract + checker report + changed files. Verify architectural intent is preserved.

---

## Coding Behavior Guidelines

Extracted from Karpathy's coding behavior principles (forrestchang/andrej-karpathy-skills).

### 1. Think Before Coding — Surface Confusion

Don't assume. Don't hide confusion.

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First

Minimum code that solves the problem. Nothing speculative.

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

### 3. Surgical Changes

Touch only what you must. Clean up only your own mess.

- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.
- Every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution

Define success criteria. Loop until verified.

Transform tasks into verifiable goals. For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
```

Strong success criteria allow independent looping. Weak criteria require constant clarification.

### 5. Manage the Context Window

- Read only the files you need for the current task.
- Don't re-read files you just wrote — the tool tracks state.
- Prefer targeted Grep/Glob over full directory reads.
- Summarize long outputs rather than quoting them wholesale.

---

## Knowledge Stack

| Layer | Tool | Query method |
|-------|------|-------------|
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
