"""
Stop-hook context watcher.
Counts turns per session (date-stamped file) and warns at WARN_AT and CRITICAL_AT turns.
These are heuristic proxies for context depth — not exact percentages.
"""
from pathlib import Path
from datetime import date
import sys

ROOT        = Path(__file__).resolve().parent.parent
STATE_DIR   = ROOT / '.agent_state'
COUNTER_F   = STATE_DIR / f'turns_{date.today().isoformat()}'
WARN_AT     = 10   # ~50% — suggest /compact
CRITICAL_AT = 18   # ~80% — strong warning

STATE_DIR.mkdir(exist_ok=True)
count = int(COUNTER_F.read_text().strip()) if COUNTER_F.exists() else 0
count += 1
COUNTER_F.write_text(str(count))

if count == WARN_AT:
    print(f"""
┌─────────────────────────────────────────────────────┐
│  CONTEXT WATCH  ·  Turn {count:>2}  ·  ~50% depth        │
│  Consider running /compact before the next task.    │
│  Current session will degrade in quality past ~20t. │
└─────────────────────────────────────────────────────┘""")
elif count == CRITICAL_AT:
    print(f"""
╔═════════════════════════════════════════════════════╗
║  CONTEXT WATCH  ·  Turn {count:>2}  ·  NEAR LIMIT          ║
║  Run /compact NOW or quality will drop sharply.     ║
╚═════════════════════════════════════════════════════╝""")
elif count > CRITICAL_AT and (count - CRITICAL_AT) % 3 == 0:
    print(f'[context-watch] Turn {count} — past safe limit. Run /compact.')
