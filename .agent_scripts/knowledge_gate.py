"""
Knowledge-first gate for PreToolUse hook.

Exit 0  → allow the tool call
Exit 2  → block the tool call (route agent to the right knowledge layer)

A session is identified by today's date. Once Claude consults the
knowledge stack — and shows evidence of touching the layer(s) the gate
recommended — subsequent Grep/Glob calls in the same calendar day are
allowed through silently.

Layer model (route on each block):

  ccc       exact code locations, symbol defs, "where is X?"
            → ccc search  (e.g. "MRAC_What_lower_limit", "pid.c:ComputePID")
  graphify  cross-file structure, god nodes, "who owns X?", "what depends on Y?"
            → graphify-out/GRAPH_REPORT.md  (e.g. "community surrounding EKF")
  wiki      design rationale, architecture, "why was X done this way?"
            → wiki/index.md  (e.g. "ADR-0011", "EKF shadow-mode rationale")

The gate inspects the gate's own `command` (the Grep/Glob tool call) and
the agent's recent Read/Shell history to *recommend* which layer(s) to
consult. The agent must then call --touch ccc/--touch graphify/--touch wiki
to record evidence of consulting each layer before --unlock.

Usage:
  python knowledge_gate.py             # called by hook — gate or allow
  python knowledge_gate.py --touch <layer>     # record layer was consulted
  python knowledge_gate.py --freshen <layer>   # mark layer fresh after re-running its update (/graphify --update, /wiki ingest, ccc reindex)
  python knowledge_gate.py --unlock    # unlock raw search (requires all three layers touched)
  python knowledge_gate.py --status    # print current layer + freshness state
  python knowledge_gate.py --reset     # reset for the day (debugging)
"""
import sys
import os
import json
import re
from pathlib import Path
from datetime import date, datetime

ROOT      = Path(__file__).resolve().parent.parent
STATE_DIR = ROOT / '.agent_state'
STATE_DIR.mkdir(exist_ok=True)

STATE_FILE = STATE_DIR / f'ks_state_{date.today().isoformat()}.json'
# legacy single-flag file — kept on disk for backward compatibility / introspection
LEGACY_FLAG_FILE = STATE_DIR / f'ks_done_{date.today().isoformat()}'

LAYERS = ('ccc', 'graphify', 'wiki')

# Self-adaptive staleness awareness — consults knowledge_state.py.
# When a layer is stale (HEAD moved past last_commit, or known files drifted),
# the gate's block message pivots from "consult this layer" to
# "this layer is stale since commit X; re-run /graphify --update / /wiki ingest first".
_KNOWLEDGE_STATE_PATH = Path(__file__).resolve().parent
if str(_KNOWLEDGE_STATE_PATH) not in sys.path:
    sys.path.insert(0, str(_KNOWLEDGE_STATE_PATH))
try:
    from knowledge_state import is_stale, mark_fresh, freshness_summary, detect_drift  # noqa: E402
except Exception:
    # knowledge_state.py missing — degrade gracefully
    def is_stale(_layer: str) -> bool: return False
    def mark_fresh(_layer: str, **_kw) -> dict: return {}
    def freshness_summary() -> dict: return {}
    def detect_drift() -> dict: return {}


# ----- Layer classifier --------------------------------------------------

# Patterns that signal the right knowledge layer for the question.
# These are matched against the tool call's command / args. The agent
# doesn't always pass the question of course, but the patterns are loose
# enough to catch common signals (symbol hits, file path hints, etc.).
LAYER_HINTS = {
    'ccc': [
        # C identifiers / snake_case (e.g. MRAC_What_lower_limit, s_ekf.active)
        r'\b[A-Za-z_][A-Za-z0-9_]*_[A-Za-z0-9_]+\b',
        # file:line references (e.g. mrac.c:65, send_data.c:628)
        r'\b\w+\.(c|h|cpp|hpp|py|js|ts):[0-9]',
        # explicit "where is" / "find definition"
        r'\b(where is|find (the )?definition|locate)\b',
    ],
    'graphify': [
        # cross-file / cross-subsystem vocabulary
        r'\b(cross[- ]?subsystem|god ?node|community|bridge|coupling|hotspot|dependency)\b',
        # "what depends on / who owns"
        r'\b(depend(s|ency|encies|ent)?|who owns|what uses|impact (of|on))\b',
        # graph file references
        r'graphify[- ]?out/GRAPH_REPORT',
    ],
    'wiki': [
        # design rationale vocabulary
        r'\b(why (was|did|is|are)|rationale|decision|trade-?off|design(ed)?|ADR[- ]?[0-9]+)\b',
        # conceptual / architecture
        r'\b(architect(ure|ural)|concept|principle|invariant|contract|interface)\b',
        # wiki reference
        r'wiki/index\.md',
    ],
}


def classify(cmd: str) -> list[str]:
    """Return the layers recommended for this command, in priority order."""
    if not cmd:
        return list(LAYERS)
    scores = {layer: 0 for layer in LAYERS}
    for layer, patterns in LAYER_HINTS.items():
        for pat in patterns:
            scores[layer] += len(re.findall(pat, cmd, flags=re.IGNORECASE))
    # If no signals matched at all, tell the agent to consult all three.
    if all(s == 0 for s in scores.values()):
        return list(LAYERS)
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    # Always recommend at least the top layer; if ties, include them.
    top_score = ranked[0][1]
    recommended = [layer for layer, score in ranked if score >= top_score * 0.5 and score > 0]
    return recommended or [ranked[0][0]]


# ----- State management --------------------------------------------------

def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {'touched': {}, 'unlocked': False, 'history': []}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


def append_history(state: dict, event: str, **fields) -> None:
    state['history'].append({
        'ts': datetime.now().isoformat(timespec='seconds'),
        'event': event,
        **fields,
    })
    # Cap history length to keep the file small
    state['history'] = state['history'][-200:]


# ----- CLI commands ------------------------------------------------------

def cmd_status() -> None:
    state = load_state()
    print(f"[knowledge-gate] date           : {date.today().isoformat()}")
    print(f"[knowledge-gate] state file     : {STATE_FILE.relative_to(ROOT)}")
    print(f"[knowledge-gate] unlocked       : {state.get('unlocked', False)}")
    for layer in LAYERS:
        touched = state.get('touched', {}).get(layer, 0)
        last_ts = state.get('touched', {}).get(f'{layer}_ts', 'never')
        stale_marker = ''
        try:
            if is_stale(layer):
                stale_marker = ' [STALE]'
        except Exception:
            pass
        print(f"[knowledge-gate] layer {layer:<8}: {touched} touch(es), last={last_ts}{stale_marker}")
    print(f"[knowledge-gate] history events : {len(state.get('history', []))}")
    # Append freshness summary from knowledge_state
    try:
        summary = freshness_summary()
        print('')
        print('[knowledge-state] freshness (HEAD vs last update):')
        for layer, s in summary.items():
            flag = 'STALE' if s['stale'] else 'fresh'
            print(f"  {layer:<8} [{flag}] last_fresh={s['last_fresh']} "
                  f"commit={s['last_commit'][:7]} tracked={s['tracked_files']}")
            for r in s['reasons']:
                print(f"           ↳ {r}")
    except Exception as e:
        print(f'[knowledge-state] unavailable: {e}')
    sys.exit(0)


def cmd_freshen(layer: str) -> None:
    """Mark a layer fresh in the manifest after the agent re-ran its update
    (e.g. /graphify --update, /wiki ingest, ccc daemon reindex).
    Also clears any same-day stale-block events in this gate's state."""
    if layer not in LAYERS:
        print(f"[knowledge-gate] unknown layer: {layer!r}. expected one of {LAYERS}", file=sys.stderr)
        sys.exit(2)
    try:
        meta = mark_fresh(layer)
    except Exception as e:
        print(f"[knowledge-gate] --freshen failed: {e}", file=sys.stderr)
        sys.exit(2)
    state = load_state()
    append_history(state, 'freshen', layer=layer,
                   last_fresh=meta.get('last_fresh'),
                   last_commit=meta.get('last_commit', 'unknown')[:7])
    save_state(state)
    print(f"[knowledge-gate] {layer} marked fresh at "
          f"{meta.get('last_fresh')} (HEAD {meta.get('last_commit', 'unknown')[:7]}, "
          f"tracked {len(meta.get('known_files', {}))} files)")
    print(f"[knowledge-gate] You may now --touch {layer} to record today's consultation.")
    sys.exit(0)


def cmd_reset() -> None:
    if STATE_FILE.exists():
        STATE_FILE.unlink()
    if LEGACY_FLAG_FILE.exists():
        LEGACY_FLAG_FILE.unlink()
    print('[knowledge-gate] state reset for today.')
    sys.exit(0)


def cmd_touch(layer: str) -> None:
    if layer not in LAYERS:
        print(f"[knowledge-gate] unknown layer: {layer!r}. expected one of {LAYERS}", file=sys.stderr)
        sys.exit(2)
    state = load_state()
    state.setdefault('touched', {})
    state['touched'][layer] = state['touched'].get(layer, 0) + 1
    state['touched'][f'{layer}_ts'] = datetime.now().isoformat(timespec='seconds')
    append_history(state, 'touch', layer=layer)
    save_state(state)
    print(f"[knowledge-gate] {layer} touched ({state['touched'][layer]}x). "
          f"Run --unlock after all recommended layers are touched.")
    sys.exit(0)


def cmd_unlock() -> None:
    state = load_state()
    # Determine which layers the agent has touched at least once.
    touched = state.get('touched', {})
    have = {layer for layer in LAYERS if touched.get(layer, 0) > 0}
    missing = set(LAYERS) - have
    if missing:
        # Block unlock. Tell the agent which layers are still outstanding.
        print(f"""
╔══════════════════════════════════════════════════════════════════╗
║  KNOWLEDGE GATE — unlock refused                                ║
╠══════════════════════════════════════════════════════════════════╣
║  You have not touched all three knowledge layers today.         ║
║                                                                  ║
║  Touched so far: {sorted(have) or '∅'}
║  Still missing: {sorted(missing)}
║                                                                  ║
║  For each missing layer, record you consulted it:               ║
║    python .agent_scripts/knowledge_gate.py --touch <layer>      ║
║                                                                  ║
║  Layer cheat-sheet:                                              ║
║    ccc        →  ccc search "..."   (exact code locations)       ║
║    graphify   →  Read graphify-out/GRAPH_REPORT.md              ║
║                                                                ║
║    wiki       →  Read wiki/index.md (or relevant ADR)            ║
║                                                                  ║
║  After all three are touched, retry --unlock.                    ║
╚══════════════════════════════════════════════════════════════════╝
""", file=sys.stderr)
        sys.exit(2)
    # All three layers touched — unlock.
    state['unlocked'] = True
    append_history(state, 'unlock')
    save_state(state)
    # Maintain the legacy flag file for any other tooling that still checks it.
    LEGACY_FLAG_FILE.touch()
    print('[knowledge-gate] Unlocked. All three layers touched today. Grep/Glob now allowed.')
    sys.exit(0)


# ----- Gate (default run) ------------------------------------------------

def gate(cmd: str) -> int:
    """Return 0 to allow, 2 to block."""
    state = load_state()
    if state.get('unlocked'):
        return 0
    recommended = classify(cmd)
    recommended_str = ', '.join(recommended) if recommended else '(none)'
    touched = state.get('touched', {})
    have = {layer for layer in LAYERS if touched.get(layer, 0) > 0}
    missing = [layer for layer in recommended if layer not in have]

    # Self-adaptive: if any *recommended* layer is STALE (HEAD moved past
    # last_commit, or known files drifted), the agent must refresh it before
    # the touch counts. We split `missing` into:
    #   stale_missing — recommended layers that are touched today but stale
    #   pure_missing  — recommended layers not touched at all today
    # Both block, but the message and remediation differ.
    stale_recommended = []
    fresh_reasons = {}  # layer -> list[str]
    try:
        summary = freshness_summary()
        for layer in recommended:
            s = summary.get(layer, {})
            if s.get('stale'):
                stale_recommended.append(layer)
                fresh_reasons[layer] = s.get('reasons', [])
    except Exception:
        # knowledge_state not available / not in a git repo — skip
        pass

    if not missing and not stale_recommended:
        # All recommended layers touched AND fresh — silent allow.
        return 0

    # Block. Compose the message differently for stale vs unconsulted.
    layer_help = {
        'ccc': (
            'ccc search "<your query>"',
            'Exact code locations, symbol defs, file:line.      '
            'Indexed, fast. Returns ranked snippets in `Source: ...line N`.',
            'ccc daemon reindex (auto on file change)',
        ),
        'graphify': (
            'Read graphify-out/GRAPH_REPORT.md',
            'Cross-file structure, god nodes, community map,    '
            'who-owns-what. Use when the question is about deps/coupling.',
            '/graphify --update  (or full /graphify <path>)',
        ),
        'wiki': (
            'Read wiki/index.md (or relevant ADR)',
            'Design rationale, architecture, trade-offs,        '
            'known gotchas. Use when the question is "why" / "how was X decided?".',
            '/wiki ingest  (re-runs INGEST on raw/)',
        ),
    }
    layer_lines = []
    for layer in recommended:
        line, blurb, refresh_cmd = layer_help[layer]
        if layer in stale_recommended:
            tag = '! stale'
            layer_lines.append(
                f'  [{tag:<9}] {layer:<8}  {line}\n'
                f'                  {blurb}\n'
                f'                  DRIFT: {", ".join(fresh_reasons.get(layer, []))}\n'
                f'                  Refresh with: {refresh_cmd}'
            )
        elif layer in have:
            tag = '✓ touched'
            layer_lines.append(f'  [{tag:<9}] {layer:<8}  {line}\n                  {blurb}')
        else:
            tag = '○ needed'
            layer_lines.append(f'  [{tag:<9}] {layer:<8}  {line}\n                  {blurb}')
    block = f"""
╔══════════════════════════════════════════════════════════════════╗
║  KNOWLEDGE GATE — Grep/Glob blocked                              ║
╠══════════════════════════════════════════════════════════════════╣
║  Before raw-searching, consult the layer(s) this question needs: ║
║                                                                  ║
║  Recommended: {recommended_str}
║  Touched     : {sorted(have) or '∅'}
║  Stale       : {stale_recommended or '∅'}
║  Still need  : {[l for l in missing if l not in stale_recommended]}
║                                                                  ║
{chr(10).join(layer_lines)}
║                                                                  ║
║  For unconsulted layers, record after reading:                  ║
║    python .agent_scripts/knowledge_gate.py --touch <layer>      ║
║                                                                  ║
║  For stale layers, run the refresh command shown above, then:    ║
║    python .agent_scripts/knowledge_state.py --status            ║
║    python .agent_scripts/knowledge_gate.py --touch <layer>      ║
║                                                                  ║
║  When all three layers are touched AND fresh, unlock with:       ║
║    python .agent_scripts/knowledge_gate.py --unlock             ║
║  Then re-run your Grep/Glob.                                    ║
║                                                                  ║
║  Exceptions:                                                     ║
║    --status  show today's layer + freshness state               ║
║    --reset   clear today's state (debugging)                     ║
╚══════════════════════════════════════════════════════════════════╝
"""
    sys.stderr.write(block)
    append_history(state, 'block', cmd=cmd[:200], recommended=recommended,
                   missing=missing, stale=stale_recommended)
    save_state(state)
    return 2


def main() -> None:
    args = sys.argv[1:]
    if '--unlock' in args:
        cmd_unlock()
    if '--reset' in args:
        cmd_reset()
    if '--status' in args:
        cmd_status()
    if '--touch' in args:
        try:
            idx = args.index('--touch')
            layer = args[idx + 1]
        except (IndexError, ValueError):
            print('[knowledge-gate] --touch requires a layer argument: ccc | graphify | wiki', file=sys.stderr)
            sys.exit(2)
        cmd_touch(layer)
    if '--freshen' in args:
        try:
            idx = args.index('--freshen')
            layer = args[idx + 1]
        except (IndexError, ValueError):
            print('[knowledge-gate] --freshen requires a layer argument: ccc | graphify | wiki', file=sys.stderr)
            sys.exit(2)
        cmd_freshen(layer)
    # Default: gate on the tool call command from stdin (PreToolUse hook contract).
    raw = sys.stdin.read() if not sys.stdin.isatty() else ''
    cmd = ''
    if raw:
        try:
            cmd = str(json.loads(raw).get('command', '') or '')
        except Exception:
            cmd = raw
    sys.exit(gate(cmd))


if __name__ == '__main__':
    main()
