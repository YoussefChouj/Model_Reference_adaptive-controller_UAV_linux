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

The system runs itself. The split is:

| Layer | Who runs it |
|---|---|
| Trail recording | `.claude/settings.json` `PostToolUse` hook → `trail.py add` |
| Structural annotation (graph nodes, wiki Recent change markers, fresh stamp) | `knowledge_loop.py run` |
| LLM-driven delta_update (graph re-extraction) | the **current agent** mid-task, OR the **`uav-knowledge-writer` subagent** for end-of-task rewrites |
| LLM-driven wiki write-through (rewrite concept pages whose rationale shifted) | same as above — agent or subagent, with its own model |

### Where the LLM lives

The LLM is **never** a third-party HTTP call (no OpenRouter, no external API).
Two options:

1. **Mid-task** — the agent that's currently working invokes:
   ```bash
   python .agent_scripts/knowledge_loop.py delta_update --paths "API/ekf.c,TASK/StabilizerTask.c"
   ```
   The script returns JSON prompts. The agent runs them through **its own model**,
   parses the JSON, and calls `path_refresh.merge_delta_into_graph(...)` directly.

2. **End-of-task** — the agent dispatches the dedicated `uav-knowledge-writer` subagent
   (`.cursor/agents/uav-knowledge-writer.md`, pinned to `cursor-grok-4.5-high`).
   That subagent has its own model + system prompt + read-only access to source files;
   it does the LLM call, parses the result, applies the rewrites (with backup), and
   appends to the audit log.

The agent that handles the loop is **the agent that's already running**, not a
new HTTP round-trip. The `uav-knowledge-writer` subagent exists for cases where
you want a focused, dedicated leg rather than letting the parent agent handle
it inline.

### `knowledge_loop.py` CLI

| Command | What it does |
|---|---|
| `python .agent_scripts/knowledge_loop.py run` | full structural pipeline (drift + annotate + Recent change + fresh stamp) |
| `python .agent_scripts/knowledge_loop.py status` | last loop run summary |
| `python .agent_scripts/knowledge_loop.py delta_update --paths a,b,c` | print JSON prompts for the calling agent's LLM to extract graph entities |
| `python .agent_scripts/knowledge_loop.py wiki_check --paths a,b,c` | print JSON prompts for the calling agent's LLM to check rationale shifts on affected wiki pages |

### Wiring

| Trigger | Hook | Mode |
|---|---|---|
| Every `Write|Edit|MultiEdit|NotebookEdit` | `PostToolUse` → `trail.py add` | records path |
| Every Stop | Stop → `knowledge_loop.py run` | structural pipeline |
| SessionStart | `SessionStart` → `knowledge_loop.py run` | structural catch-up |
| Git commit | `.git/hooks/post-commit` → `knowledge_loop.py run` (background) | structural catch-up |
| Manual | `python .agent_scripts/knowledge_loop.py run` | structural pipeline |

The LLM stages are NOT in the hook path. They happen when the working agent or
the `uav-knowledge-writer` subagent invokes `delta_update` / `wiki_check`. That
keeps the LLM model choice local to the agent doing the work.

### Install

```bash
# Optional: post-commit hook (already installed if you ran install_post_commit.py install)
python .agent_scripts/install_post_commit.py install

# Manual one-shot run
python .agent_scripts/knowledge_loop.py run
```

### Auditing

- Every loop run is logged to `.agent_state/knowledge_loop_log.json` (last 100 entries).
- Graph nodes get `meta.last_touched_session` and `meta.last_touched_at` fields.
- Wiki rewrites are backed up to `.agent_state/wiki_backup/<date>/`.
- Graph.json gets a top-level `change_log` array recording every merge.

### Hard constraints (all agent roles)

- **Never edit source code.** Only edit `graphify-out/`, `wiki/`, `.agent_state/`.
- **Never flash firmware, halt the core, or write to the target.**
- **Never bypass the backup step.** If `autonomous_wiki_rewrite_from_verdict` is broken, fix it first.
- **Never delete a wiki page.** Append `<!-- superseded by: ... -->` and link the replacement.

<!-- recent_change:2026-07-25 -->
## Recent change (2026-07-25)

Auto-flagged by path_refresh. Files affected in this session:
- `API/ekf.c`
- `TASK/StabilizerTask.c`

Run `/wiki ingest` or `python -m graphify --update` to verify rationale still holds. Remove this section if confirmed unchanged.
