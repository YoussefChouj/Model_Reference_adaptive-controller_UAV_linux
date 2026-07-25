# Knowledge Gate Enforcement — PreToolUse Hook Pattern

**Region**: Workflow & Recipes  
**Tags**: hooks, knowledge-stack, enforcement, claude-code, tooling

## Problem

Claude Code defaults to `Grep`/`Glob` raw file exploration even when a curated knowledge stack (CocoIndex, graphify graph, wiki) exists. The CLAUDE.md instructions were advisory — Claude ignored them under time pressure or for "quick" lookups.

Three layers of the stack, three roles:

| Layer | Tool | Best for |
|---|---|---|
| **ccc** | `ccc search "..."` | exact code locations, symbol defs, "where is X?" |
| **graphify** | `Read graphify-out/GRAPH_REPORT.md` | cross-file structure, god nodes, "who owns X?", "what depends on Y?" |
| **wiki** | `Read wiki/index.md` | design rationale, architecture, "why was X done this way?" |

A good agent consults **all three** in order and *attests* it before unlocking raw search. A bad agent reaches for `grep` immediately.

## Root Cause

The original PreToolUse hook exited `0` (allow) after printing a soft warning. Claude receives the warning as text but the tool call still proceeds. Exit 0 = tool runs regardless of what the hook prints.

## Fix: Exit Code 2 + Per-Layer Attestation

`exit 2` from a PreToolUse hook **blocks the tool call entirely**. Combined with mandatory per-layer `--touch` flags, the agent must demonstrate it consulted the right layer before unlocking raw search.

### Gate script: `.agent_scripts/knowledge_gate.py`

```python
# Two-state allow path:
#   1) state['unlocked'] is True         → exit 0 silently
#   2) all recommended layers are touched (per-classifier) → exit 0 silently
#
# Block path:
#   classifier finds the right layer(s) for the command,
#   agent has not touched them → exit 2 with a routing message
```

Commands exposed to the agent:

```
python .agent_scripts/knowledge_gate.py                       # gate (called by hook)
python .agent_scripts/knowledge_gate.py --touch <layer>       # record layer consulted
python .agent_scripts/knowledge_gate.py --unlock              # final unlock (requires all three layers touched)
python .agent_scripts/knowledge_gate.py --status              # show today's state
python .agent_scripts/knowledge_gate.py --reset               # clear state (debugging)
```

### Layer classifier

The gate inspects the Grep/Glob command and matches against layer-specific patterns:

| Layer | Patterns that trigger it |
|---|---|
| `ccc` | `snake_case_identifier`, `file.c:line`, "where is / find definition" |
| `graphify` | "cross-subsystem", "god node", "who owns", "what depends on", `GRAPH_REPORT.md` |
| `wiki` | "why was X", "rationale", "ADR-NNNN", "architecture", "trade-off" |

If no pattern matches, the gate tells the agent to consult all three layers.

### Attestation flow

```
1. Agent tries  `grep -n MRAC_What_lower_limit src/mrac.c`
2. Hook runs knowledge_gate.py → classifies as `ccc` → blocks (exit 2)
3. Agent runs `ccc search "MRAC_What_lower_limit"`
4. Agent runs `python .agent_scripts/knowledge_gate.py --touch ccc`
5. Agent retries grep → silent allow (cc layer was the only one needed and it's touched)
```

For a question that needs more than one layer:

```
1. Agent tries `grep -r "what depends on s_ekf" src/`
2. Gate classifies as `graphify` → blocks
3. Agent reads `graphify-out/GRAPH_REPORT.md`
4. Agent runs `python .agent_scripts/knowledge_gate.py --touch graphify`
5. Agent retries → silent allow
```

To unlock for the rest of the day (so future grep's pass without re-classification):

```
1. Touch all three: --touch ccc && --touch graphify && --touch wiki
2. python .agent_scripts/knowledge_gate.py --unlock
3. Grep/Glob now allowed silently for the rest of today
```

The `--unlock` step is **hard to skip** — it refuses until all three layers have been touched at least once. This is the load-bearing step: it forces the agent to demonstrate it knows all three layers exist.

### Hook wiring: `.claude/settings.json`

```json
{
  "hooks": {
    "PreToolUse": [{
      "matcher": "Glob|Grep",
      "hooks": [{"type": "command", "command": "python .agent_scripts/knowledge_gate.py"}]
    }]
  },
  "permissions": {
    "allow": [
      "Bash(python .agent_scripts/knowledge_gate.py*)",
      "Bash(ccc search*)",
      "Bash(ccc status*)"
    ]
  }
}
```

The `Bash(ccc search*)` allow ensures the agent's first move (consulting the stack) is never blocked.

### State file: `.agent_state/ks_state_YYYY-MM-DD.json`

Persistent state per day, written as JSON:

```json
{
  "touched": {
    "ccc": 3, "ccc_ts": "2026-07-25T18:00:00",
    "graphify": 1, "graphify_ts": "...",
    "wiki": 2, "wiki_ts": "..."
  },
  "unlocked": true,
  "history": [ ...last 200 events... ]
}
```

The legacy `ks_done_YYYY-MM-DD` flag is also written on `--unlock` for any other tooling that still checks it.

## Gotchas

- The `--unlock` command requires ALL three layers touched — even if you only need ccc for the current question. This is the structural pressure that forces the agent to know the full stack.
- The `--touch` permission must NOT be in `settings.json` `allow` list, otherwise the agent can mass-touch all three without ever actually consulting the knowledge stack. The agent must call `ccc search` / `Read graphify-out/...` / `Read wiki/index.md` first; `--touch` only records that it did.
- The gate fires on Claude's OWN Glob/Grep calls, including exploratory ones during planning — this is intentional.
- The state is date-stamped not session-stamped — if you work past midnight the gate resets.
- The `--reset` flag is for debugging only; production agents should never need it.

## Cursor-Side Gate (separate)

The Cursor beforeShellExecution hook (`./.cursor/hooks/knowledge-gate.js`) is a **soft** ask — it returns `permission: "ask"` rather than blocking. It only fires on shell-level grep/rg/findstr, not on Cursor's `Grep` tool.

This is intentional: the hard block lives in Claude Code's PreToolUse because it has the correct matcher for `Glob|Grep`. The Cursor side is best-effort — if the agent ignores it, the strict Claude Code gate still catches the next session.

## Context Watch (Turn Counter)

A companion Stop hook in `.agent_scripts/context_watch.py` counts turns per day and warns at turn 10 (~50% context proxy) and turn 18 (~80%):

```python
COUNTER_F   = STATE_DIR / f'turns_{date.today().isoformat()}'
WARN_AT     = 10
CRITICAL_AT = 18
```

Combined with `"autoCompact": true` in `~/.claude/settings.json` (native auto-compact near ~85-90%), this gives three layers of context management.

## Custom Skills Not in the `/` Dropdown

Skills in `~/.claude/skills/` do **not** appear in the Claude Code command autocomplete. The dropdown only shows built-in commands (`/compact`, `/clear`, `/help`, etc.). Type the full skill name manually — `/skill-name` — and Claude will invoke it.

## Self-adaptive loop (no human in the loop)

The system runs itself. The `knowledge_loop.py` orchestrator ties everything together:

| Trigger | What runs |
|---|---|
| Every `Write|Edit|MultiEdit|NotebookEdit` | `trail.py add` records the path |
| Every Stop | `knowledge_loop.py run` (full pipeline: drift-detect, structural annotation, LLM delta_update, wiki write-through, fresh stamp) |
| SessionStart | `knowledge_loop.py run --no-llm` (cheap structural catch-up) |
| Git post-commit | same as Stop, fires in background |

The LLM stages (`delta_update_graph`, `autonomous_wiki_rewrite`) are off by default until `OPENROUTER_API_KEY` is set. Without the key, the loop falls back to **structural-only** mode: graph nodes get annotated, wiki pages get `## Recent change (YYYY-MM-DD)` markers, manifest is stamped fresh. The circuit breaker in `llm_call.py` opens after 3 consecutive failures and stays open for 5 minutes, so a flaky network cannot stall the loop.

When the LLM IS available, `autonomous_wiki_rewrite` will REPLACE wiki concept pages whose rationale has shifted. Every replacement is backed up to `.agent_state/wiki_backup/<date>/<page>.md` before the rewrite. To roll back: `cp .agent_state/wiki_backup/<date>/<page>.md wiki/concepts/<page>.md`.

### Install

```bash
# Optional: post-commit hook (already installed if you ran install_post_commit.py install)
python .agent_scripts/install_post_commit.py install

# Optional: enable LLM stages (set the API key)
export OPENROUTER_API_KEY=sk-or-v1-...

# Manual one-shot run
python .agent_scripts/knowledge_loop.py run
```

### Circuit breaker

`llm_call.py` keeps a rolling count of failures in `.agent_state/llm_circuit.json`. After 3 failures the circuit opens for 5 minutes; during that window, the loop skips LLM stages but continues structural updates. This means a bad API key or a rate-limited endpoint cannot block the agent.

### Auditing

- Every loop run is logged to `.agent_state/knowledge_loop_log.json` (last 100 entries).
- Every LLM call is logged to `.agent_state/llm_calls.jsonl`.
- Wiki rewrites are backed up to `.agent_state/wiki_backup/<date>/`.
- Graph.json gets a top-level `change_log` array recording every merge.
- The graph node `meta.last_touched_session` field tracks which session touched each node.
