"""
Knowledge-first gate for PreToolUse hook.

Exit 0  → allow the tool call (knowledge stack was consulted this session)
Exit 2  → block the tool call (show mandatory checklist to Claude)

A session is identified by today's date. Once Claude consults the
knowledge stack and calls this script with --unlock, subsequent
Grep/Glob calls in the same calendar day are allowed through silently.

Usage:
  python knowledge_gate.py           # called by hook — gate or allow
  python knowledge_gate.py --unlock  # called by Claude after ccc/wiki check
"""
import sys
import os
from pathlib import Path
from datetime import date

ROOT      = Path(__file__).resolve().parent.parent
FLAG_DIR  = ROOT / '.agent_state'
FLAG_FILE = FLAG_DIR / f'ks_done_{date.today().isoformat()}'

# --unlock mode: Claude has consulted the knowledge stack
if '--unlock' in sys.argv:
    FLAG_DIR.mkdir(exist_ok=True)
    FLAG_FILE.touch()
    print('[knowledge-gate] Unlocked. Grep/Glob now allowed for this session.')
    sys.exit(0)

# Allow mode: flag exists from earlier this session
if FLAG_FILE.exists():
    sys.exit(0)

# Block mode: knowledge stack not yet consulted
print("""
╔══════════════════════════════════════════════════════════════════╗
║  KNOWLEDGE GATE — Grep/Glob blocked until stack is consulted    ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  Run these IN ORDER before raw-searching:                        ║
║                                                                  ║
║  1. ccc search "<your query>"                                    ║
║     → Finds exact code locations (indexed, fast)                ║
║                                                                  ║
║  2. Read graphify-out/GRAPH_REPORT.md                           ║
║     → System dependencies, god nodes, community map             ║
║                                                                  ║
║  3. wiki/index.md  (for conceptual / design questions)          ║
║     → Architecture decisions, theory, known gotchas             ║
║                                                                  ║
║  4. docs/decisions.md  (for architectural choices)              ║
║                                                                  ║
║  After consulting the stack, unlock with:                        ║
║    python .agent_scripts/knowledge_gate.py --unlock             ║
║  Then re-run your Grep/Glob.                                     ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
""", file=sys.stderr)
sys.exit(2)
