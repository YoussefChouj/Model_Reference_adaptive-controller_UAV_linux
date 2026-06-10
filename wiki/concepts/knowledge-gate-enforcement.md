# Knowledge Gate Enforcement — PreToolUse Hook Pattern

**Region**: Workflow & Recipes  
**Tags**: hooks, knowledge-stack, enforcement, claude-code, tooling

## Problem

Claude Code defaults to `Grep`/`Glob` raw file exploration even when a curated knowledge stack (CocoIndex, graphify graph, wiki) exists. The CLAUDE.md instructions were advisory — Claude ignored them under time pressure or for "quick" lookups.

## Root Cause

The old PreToolUse hook exited `0` (allow) after printing a soft warning. Claude receives the warning as text but the tool call still proceeds. Exit 0 = tool runs regardless of what the hook prints.

## Fix: Exit Code 2 = Hard Block

`exit 2` from a PreToolUse hook **blocks the tool call entirely**. Claude receives a "tool blocked" message it must address before continuing. Combined with a mandatory header at the top of CLAUDE.md, this creates two enforcing layers:

1. **Structural** — hook blocks Grep/Glob at the OS level
2. **Instructional** — CLAUDE.md mandatory header with explicit `STOP` language

### Gate script: `.agent_scripts/knowledge_gate.py`

```python
FLAG_FILE = FLAG_DIR / f'ks_done_{date.today().isoformat()}'

if '--unlock' in sys.argv:
    FLAG_DIR.mkdir(exist_ok=True)
    FLAG_FILE.touch()
    sys.exit(0)          # allow future calls

if FLAG_FILE.exists():
    sys.exit(0)          # already unlocked this session

# print banner to stderr, then:
sys.exit(2)              # BLOCK the tool call
```

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
    "allow": ["Bash(python .agent_scripts/knowledge_gate.py*)"]
  }
}
```

### Unlock after consulting the stack

```powershell
python .agent_scripts/knowledge_gate.py --unlock
```

This creates a date-stamped flag file (`.agent_state/ks_done_YYYY-MM-DD`) that expires at midnight, so the gate resets each new session.

## Gotchas

- The `--unlock` permission must be in `settings.json` `allow` list — otherwise the unlock command itself gets blocked
- The gate fires on Claude's OWN Glob/Grep calls, including exploratory ones during planning — this is intentional
- Reset the gate after testing: `Remove-Item -Force ".agent_state\ks_done_$(Get-Date -Format yyyy-MM-dd)"`
- The flag is date-stamped not session-stamped — if you work past midnight the gate resets

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
