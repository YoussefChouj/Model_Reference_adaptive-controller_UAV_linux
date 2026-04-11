## Session State

**Last Updated**: 2026-04-11
**Goal**: Investigate and fix why the drone motors do not move when commanded via Virtual RC / Paths in SDK Mode.

### Task Breakdown

| # | Task | Status |
|---|------|--------|
| 1 | Investigate arming logic for Virtual RC / SDK mode | ✅ |
| 2 | Fix firmware to accept Virtual RC bounds for arming | ✅ |
| 3 | Fix firmware to automatically arm when SDK ARM REQ is held | ✅ |
| 4 | Explain to the user how to correctly take off in SDK mode | 🔄 |


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
