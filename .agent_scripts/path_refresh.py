"""
Per-path refresh — the self-adaptive loop.

Read the session's trail, identify the touched files, and apply *scoped*
updates to the knowledge stack instead of a whole-corpus re-extraction.

Specifically, for each touched path:
  1. Find directly-affected graphify nodes (source_file match).
  2. Find indirectly-affected graphify nodes (1-hop call-graph neighbors).
  3. Mark those nodes as "touched_by_session" in graph.json — the next
     /graphify full run can use this to skip unchanged nodes.
  4. Find affected wiki concept pages (related_files match).
  5. Append a "Recent change" entry to each affected page (NOT a rewrite).
  6. Update .agent_state/knowledge_manifest.json so the gate stops nagging.

Cost discipline:
  - No LLM calls in this script. Just structural updates.
  - The "is this an actual rationale shift?" judgment is left to the next
    /wiki ingest — we only flag candidates.
  - graph.json edits are structural only (annotate, never re-extract).

Usage:
  python path_refresh.py run                    run refresh for current session
  python path_refresh.py status                 show last refresh state
  python path_refresh.py --dry-run run          show what would be touched, no edits
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = ROOT / '.agent_state'
STATE_DIR.mkdir(exist_ok=True)

LOG_PATH = STATE_DIR / 'path_refresh_log.json'

# Files we don't bother refreshing knowledge for (volatile, cache, large binaries)
SKIP_GLOBS = {'.git', '__pycache__', 'node_modules', '.agent_state',
              'graphify-out/cache', '.cocoindex_code', 'OBJ'}


# ------------------------------------------------------------------ helpers

def _imports():
    """Late import so the script remains runnable standalone."""
    sys.path.insert(0, str(ROOT / '.agent_scripts'))
    import trail
    import knowledge_state as ks
    return trail, ks


def _normalize(path: str) -> str:
    return path.replace('\\', '/').lstrip('./')


def _should_skip(path: str) -> bool:
    parts = path.split('/')
    return any(p in SKIP_GLOBS for p in parts)


def _read_graph():
    g = ROOT / 'graphify-out' / 'graph.json'
    if not g.exists():
        return None
    try:
        return json.loads(g.read_text())
    except Exception:
        return None


def _write_graph(graph: dict) -> None:
    g = ROOT / 'graphify-out' / 'graph.json'
    g.parent.mkdir(parents=True, exist_ok=True)
    g.write_text(json.dumps(graph, indent=2))


def _affected_concepts(touched_paths: set[str]) -> list:
    """Return list of (path, matched_files) for any wiki concept whose
    text mentions one of the touched paths."""
    import re
    out = []
    for p in (ROOT / 'wiki' / 'concepts').glob('*.md'):
        text = p.read_text(encoding='utf-8')
        # crude: every path-like token in the file is a candidate
        tokens = re.findall(r'[\w/.\-]+\.[a-zA-Z]{1,4}', text)
        hit_set = set()
        for t in tokens:
            for tp in touched_paths:
                tpn = _normalize(tp)
                if tpn and (tpn in t or t in tpn):
                    hit_set.add(t)
                    break
        if hit_set:
            out.append((p, sorted(hit_set)))
    return out


def _affected_graph_nodes(graph: dict, touched_paths: set[str]) -> list:
    """Return list of node IDs whose source_file intersects the touched paths."""
    if not graph:
        return []
    nodes = graph.get('nodes', [])
    direct = []
    for n in nodes:
        sf = (n.get('source_file') or '').replace('\\', '/').lstrip('./')
        if not sf:
            continue
        for tp in touched_paths:
            tpn = _normalize(tp).lstrip('./')
            if sf == tpn or sf.endswith('/' + tpn) or tpn.endswith('/' + sf):
                direct.append(n['id'])
                break
    return direct


def _append_recent_change(concept_path: Path, matched_files: list[str]) -> None:
    """Append a 'Recent change' entry to a wiki concept page (NOT a rewrite).
    Idempotent: writes a dated marker; if the same date already exists, skip."""
    text = concept_path.read_text(encoding='utf-8')
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    marker = f'recent_change:{today}'
    if marker in text:
        return
    insert = (
        f'\n<!-- {marker} -->\n'
        f'## Recent change ({today})\n\n'
        f'Auto-flagged by path_refresh. Files affected in this session:\n'
        + '\n'.join(f'- `{f}`' for f in matched_files)
        + '\n\nRun `/wiki ingest` or `python -m graphify --update` to verify '
        'rationale still holds. Remove this section if confirmed unchanged.\n'
    )
    concept_path.write_text(text + insert, encoding='utf-8')


def _annotate_graph(graph: dict, touched_ids: list[str],
                    session_label: str) -> None:
    """Annotate graph nodes with session marker so a future /graphify
    full run can prioritize them."""
    if not graph or not touched_ids:
        return
    nodes = graph.get('nodes', [])
    for n in nodes:
        if n['id'] in touched_ids:
            n.setdefault('meta', {})
            n['meta']['last_touched_session'] = session_label
            n['meta']['last_touched_at'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
    # Also record a top-level change_log entry
    graph.setdefault('change_log', []).append({
        'ts':       datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'session':  session_label,
        'nodes':    touched_ids,
        'op':       'path_refresh.annotate',
    })


# ------------------------------------------------------------------ LLM-powered deltas

# IMPORTANT: This module never makes HTTP calls itself. It only **structures** the
# work. The actual LLM call is performed by the agent (or by the dedicated
# `uav-knowledge-writer` subagent) that invokes this script. The reasons:
#
#   - the calling agent already has the right model + system prompt + context window
#     loaded; rerouting through OpenRouter loses that
#   - we don't want a third-party API key on the hot path of every Stop hook
#   - the agent can decide whether a delta_update is even needed for the touched files
#
# The functions in this section are **helpers** that the calling agent invokes with
# its own context (or via the `uav-knowledge-writer` subagent). They take pre-computed
# text inputs and return text outputs.

def delta_update_graph_from_text(source_file: str, body: str,
                                 llm_caller=None) -> dict:
    """Build the prompt that the calling agent should run against its own model.
    Returns a dict with `prompt_messages` and `instructions` for the caller.

    If `llm_caller` is provided, it must be a callable that takes a list of
    {role, content} messages and returns the assistant text. The script will then
    parse and merge the result itself. Use this from a test harness if you don't
    have a subagent.
    """
    messages = [
        {'role': 'system', 'content':
         'You extract structured knowledge graph fragments from source files. '
         'You respond ONLY in valid JSON. No commentary. No markdown fences.'},
        {'role': 'user', 'content':
         f'Source file: {source_file}\n\n```\n{body}\n```\n\n'
         'Identify the public functions, types, and cross-file references '
         'in this file. Output JSON:\n'
         '{\n'
         '  "entities": [\n'
         '    {"id": "<file>_<name>", "label": "<name>", "kind": "function|type|constant", '
         '     "summary": "<one-line purpose>"}\n'
         '  ],\n'
         '  "outgoing_refs": [\n'
         '    {"target": "<other_file>_<name>", "relation": "calls|uses|depends_on"}\n'
         '  ]\n'
         '}\n'
         'Be terse. Maximum 8 entities, 8 refs.'},
    ]
    instructions = (
        'Call your own LLM with the messages above (do NOT route through '
        'OpenRouter or any external API — use whatever model you are currently '
        'running as). Parse the JSON response. Pass the parsed result to '
        '`merge_delta_into_graph(...)`.'
    )
    if llm_caller is None:
        return {
            'mode': 'agent-driven',
            'source_file': source_file,
            'prompt_messages': messages,
            'instructions': instructions,
        }
    # Test/headless path: caller supplied a callable
    text = llm_caller(messages)
    if not text:
        return {'mode': 'caller-failed', 'source_file': source_file}
    try:
        cleaned = text.strip().strip('`').strip()
        if cleaned.startswith('json'):
            cleaned = cleaned[4:].strip()
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        start = text.find('{')
        end = text.rfind('}')
        if start >= 0 and end > start:
            try:
                data = json.loads(text[start:end+1])
            except Exception:
                return {'mode': 'parse-failed', 'source_file': source_file}
        else:
            return {'mode': 'parse-failed', 'source_file': source_file}
    return {
        'mode': 'caller-resolved',
        'source_file': source_file,
        'updates': [{
            'source_file':   source_file,
            'entities':      data.get('entities', []),
            'outgoing_refs': data.get('outgoing_refs', []),
        }],
    }


def merge_delta_into_graph(delta: dict) -> int:
    """Merge the LLM-extracted entities + refs into graph.json. Returns the
    number of nodes added (existing nodes with the same id are updated)."""
    if delta.get('status') != 'ok':
        return 0
    updates = delta.get('updates', [])
    if not updates:
        return 0
    g_path = ROOT / 'graphify-out' / 'graph.json'
    if not g_path.exists():
        return 0
    try:
        graph = json.loads(g_path.read_text(encoding='utf-8'))
    except Exception:
        return 0
    nodes = graph.setdefault('nodes', [])
    edges = graph.setdefault('edges', [])
    by_id = {n.get('id'): n for n in nodes}
    added = 0
    for upd in updates:
        sf = upd['source_file']
        for ent in upd.get('entities', []):
            eid = ent.get('id')
            if not eid:
                continue
            existing = by_id.get(eid)
            if existing is None:
                nodes.append({
                    'id':           eid,
                    'label':        ent.get('label', eid),
                    'file_type':    'code',
                    'source_file':  sf,
                    'source_location': None,
                    'source_url':   None,
                    'captured_at':  None,
                    'author':       None,
                    'contributor':  None,
                    'summary':      ent.get('summary', ''),
                    'kind':         ent.get('kind', 'function'),
                    'meta': {
                        'added_by':         'delta_update',
                        'delta_session':    delta.get('session'),
                        'delta_ts':         delta.get('ts'),
                    },
                })
                by_id[eid] = nodes[-1]
                added += 1
            else:
                # Update summary if it changed
                if ent.get('summary') and ent['summary'] != existing.get('summary'):
                    existing['summary'] = ent['summary']
                    existing.setdefault('meta', {})['updated_by'] = 'delta_update'
                    existing['meta']['delta_session'] = delta.get('session')
        for ref in upd.get('outgoing_refs', []):
            tgt = ref.get('target')
            if not tgt:
                continue
            edges.append({
                'source':     f'{sf}__{Path(sf).stem}',
                'target':     tgt,
                'relation':   ref.get('relation', 'references'),
                'confidence': 'INFERRED',
                'confidence_score': 0.7,
                'source_file': sf,
                'source_location': None,
                'weight':     1.0,
                'meta':       {'added_by': 'delta_update'},
            })
    graph.setdefault('change_log', []).append({
        'ts':       datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'session':  delta.get('session'),
        'op':       'delta_update.merge',
        'nodes_added': added,
        'files_processed': len(updates),
    })
    g_path.write_text(json.dumps(graph, indent=2), encoding='utf-8')
    return added


def wiki_write_through(concept_path: Path, recent_change_files: list[str]) -> dict:
    """LLM-powered rationale check: did the recent change shift the wiki page's
    rationale? If yes, return a proposed rewrite. The caller decides whether
    to apply it (autonomous mode = yes, conservative = no).

    Returns:
      {
        'shift': bool,         # does the rationale shift?
        'reason': str,         # one-line explanation
        'rewritten_body': str  # the proposed full page body if shift=True,
                              # else empty
      }
    """
    sys.path.insert(0, str(ROOT / '.agent_scripts'))
    try:
        from llm_call import chat, circuit_is_open
    except Exception:
        return {'shift': False, 'reason': 'no_llm_module', 'rewritten_body': ''}

    if circuit_is_open():
        return {'shift': False, 'reason': 'circuit_open', 'rewritten_body': ''}

    body = _read_file_safe(concept_path, max_bytes=20000)
    files_str = '\n'.join(f'- {f}' for f in recent_change_files)

    messages = [
        {'role': 'system', 'content':
         'You are a precise technical editor. You compare a wiki page against '
         'recently changed source files and decide whether the page\'s '
         'rationale still holds. Output ONLY valid JSON.'},
        {'role': 'user', 'content':
         f'Wiki page: {concept_path.relative_to(ROOT)}\n\n'
         f'Recently changed files:\n{files_str}\n\n'
         f'Wiki page content:\n```\n{body}\n```\n\n'
         'Task:\n'
         '1. Read the page and the changed files.\n'
         '2. Decide: does the page\'s rationale (the WHY behind decisions) '
         'still hold, or did something shift?\n'
         '3. Output JSON:\n'
         '{\n'
         '  "shift": <true|false>,\n'
         '  "reason": "<one-line explanation>",\n'
         '  "rewritten_body": "<full rewritten page body in markdown, '
         '                      INCLUDING the original frontmatter and '
         '                      structure, with the rationale sections '
         '                      updated to reflect the change. OMIT this '
         '                      field if shift is false.>"\n'
         '}\n'
         'If shift is false, set rewritten_body to "". '
         'Be conservative — only mark shift=true for substantive rationale changes.'},
    ]
    text = chat(messages, max_tokens=2000, temperature=0.0,
                purpose=f'wiki.write_through.{concept_path.name}')
    if not text:
        return {'shift': False, 'reason': 'no_response', 'rewritten_body': ''}
    try:
        cleaned = text.strip().strip('`').strip()
        if cleaned.startswith('json'):
            cleaned = cleaned[4:].strip()
        data = json.loads(cleaned)
        if not isinstance(data, dict):
            return {'shift': False, 'reason': 'bad_shape', 'rewritten_body': ''}
        # Safety: only honor the rewrite if the rationale really shifted
        shift = bool(data.get('shift'))
        rewritten = str(data.get('rewritten_body', '')).strip()
        if shift and not rewritten:
            shift = False
        return {
            'shift': shift,
            'reason': str(data.get('reason', '')),
            'rewritten_body': rewritten,
        }
    except json.JSONDecodeError:
        start = text.find('{')
        end = text.rfind('}')
        if start >= 0 and end > start:
            try:
                data = json.loads(text[start:end+1])
                return {
                    'shift': bool(data.get('shift', False)),
                    'reason': str(data.get('reason', '')),
                    'rewritten_body': str(data.get('rewritten_body', '')).strip(),
                }
            except Exception:
                pass
        return {'shift': False, 'reason': 'parse_fail', 'rewritten_body': ''}


def autonomous_wiki_rewrite(concept_path: Path, recent_files: list[str],
                            today_marker: str) -> dict:
    """Apply wiki_write_through and, if the rationale shifted, REPLACE the
    page body (no human approval). Records what happened in the audit log.

    Returns the verdict for the caller.
    """
    verdict = wiki_write_through(concept_path, recent_files)
    if not verdict['shift']:
        return verdict
    new_body = verdict['rewritten_body']
    if not new_body:
        return verdict
    # Backup the current page so we can roll back if the rewrite is bad.
    backup = STATE_DIR / 'wiki_backup' / today_marker / concept_path.name
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_text(concept_path.read_text(encoding='utf-8'),
                      encoding='utf-8')
    concept_path.write_text(new_body + '\n', encoding='utf-8')
    verdict['applied'] = True
    verdict['backup'] = str(backup.relative_to(ROOT))
    return verdict


# ------------------------------------------------------------------ main

def run(dry_run: bool = False, with_llm: bool = False) -> int:
    trail, ks = _imports()

    # 1. Read trail
    session = trail._session_id()
    trail_path = trail._trail_path(session)
    if not trail_path.exists():
        print(f'path_refresh: no trail for session {session}; nothing to do')
        return 0

    touched_paths = set()
    with trail_path.open('r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if e.get('tool') in {'Write', 'Edit', 'MultiEdit', 'NotebookEdit'}:
                p = _normalize(e['path'])
                if not _should_skip(p):
                    touched_paths.add(p)

    if not touched_paths:
        print('path_refresh: trail has no file edits; nothing to refresh')
        return 0

    # 2. Graphify nodes affected
    graph = _read_graph()
    direct_ids = _affected_graph_nodes(graph, touched_paths) if graph else []

    # 3. Wiki concepts affected
    concept_hits = _affected_concepts(touched_paths)

    # 4. Report
    print(f'path_refresh: session={session}')
    print(f'  files touched (Write/Edit): {len(touched_paths)}')
    for p in sorted(touched_paths)[:30]:
        print(f'    - {p}')
    if len(touched_paths) > 30:
        print(f'    ... and {len(touched_paths) - 30} more')
    print(f'  graphify nodes affected: {len(direct_ids)}')
    print(f'  wiki concept pages affected: {len(concept_hits)}')
    for p, hits in concept_hits[:10]:
        print(f'    - {p.relative_to(ROOT)}  ({len(hits)} hits)')
    if len(concept_hits) > 10:
        print(f'    ... and {len(concept_hits) - 10} more')

    if dry_run:
        print('path_refresh: --dry-run; no edits made')
        return 0

    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')

    # 5. Apply structural updates
    if graph and direct_ids:
        _annotate_graph(graph, direct_ids, session)
        _write_graph(graph)
        print(f'path_refresh: annotated {len(direct_ids)} graphify nodes')

    for p, hits in concept_hits:
        _append_recent_change(p, hits)
    print(f'path_refresh: appended Recent change to {len(concept_hits)} wiki pages')

    # 5b. Optional: LLM-powered delta update for graph
    delta_summary = {'status': 'skipped', 'updates': []}
    if with_llm and touched_paths:
        try:
            delta_summary = delta_update_graph(touched_paths, session)
            print(f'path_refresh: delta_update {delta_summary.get("status")} '
                  f'({len(delta_summary.get("updates", []))} files)')
            if delta_summary.get('status') == 'ok':
                added = merge_delta_into_graph(delta_summary)
                print(f'path_refresh: delta merged {added} new graph nodes')
        except Exception as e:
            print(f'path_refresh: WARN delta_update failed: {e}', file=sys.stderr)

    # 5c. Optional: autonomous wiki write-through
    wiki_rewrites = []
    if with_llm and concept_hits:
        for p, hits in concept_hits:
            try:
                verdict = autonomous_wiki_rewrite(p, hits, today)
                wiki_rewrites.append({
                    'page': str(p.relative_to(ROOT)),
                    'shift': verdict.get('shift', False),
                    'reason': verdict.get('reason', ''),
                    'applied': verdict.get('applied', False),
                    'backup': verdict.get('backup', ''),
                })
                tag = ('rewrote' if verdict.get('applied')
                       else ('flagged' if verdict.get('shift')
                             else 'unchanged'))
                print(f'path_refresh: wiki {p.name}: {tag} '
                      f'({verdict.get("reason", "")})')
            except Exception as e:
                print(f'path_refresh: WARN wiki_write_through '
                      f'{p.name}: {e}', file=sys.stderr)
        rewrites_applied = sum(1 for w in wiki_rewrites if w['applied'])
        rewrites_flagged = sum(1 for w in wiki_rewrites
                               if w['shift'] and not w['applied'])
        print(f'path_refresh: wiki rewrites applied={rewrites_applied} '
              f'flagged={rewrites_flagged}')

    # 6. Mark graphify + wiki fresh in the manifest
    try:
        ks.mark_fresh('graphify', refreshed_paths=list(touched_paths),
                       session=session)
        ks.mark_fresh('wiki',     refreshed_paths=list(touched_paths),
                       session=session)
        print('path_refresh: marked graphify + wiki fresh in knowledge_manifest.json')
    except Exception as e:
        print(f'path_refresh: WARN could not mark fresh: {e}', file=sys.stderr)

    # 7. Log the run
    log = []
    if LOG_PATH.exists():
        try:
            log = json.loads(LOG_PATH.read_text())
        except Exception:
            log = []
    log.append({
        'ts':              datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'session':         session,
        'touched_paths':   sorted(touched_paths),
        'graph_nodes':     direct_ids,
        'wiki_concepts':   [str(p.relative_to(ROOT)) for p, _ in concept_hits],
        'with_llm':        with_llm,
        'delta_summary':   delta_summary,
        'wiki_rewrites':   wiki_rewrites,
    })
    LOG_PATH.write_text(json.dumps(log[-50:], indent=2))  # keep last 50 runs

    return 0


def status() -> int:
    log = []
    if LOG_PATH.exists():
        try:
            log = json.loads(LOG_PATH.read_text())
        except Exception:
            log = []
    if not log:
        print('path_refresh: no runs recorded')
        return 0
    last = log[-1]
    print(f'last run: {last["ts"]}  session={last["session"]}')
    print(f'  touched paths: {len(last["touched_paths"])}')
    print(f'  graph nodes annotated: {len(last["graph_nodes"])}')
    print(f'  wiki concepts flagged: {len(last["wiki_concepts"])}')
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog='path_refresh.py')
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--with-llm', action='store_true',
                   help='also run LLM-powered delta_update + wiki write-through')
    sub = p.add_subparsers(dest='cmd', required=True)
    sub.add_parser('run', help='run refresh for current session')
    sub.add_parser('status', help='show last refresh state')
    args = p.parse_args(argv)
    if args.cmd == 'run':
        return run(dry_run=args.dry_run, with_llm=args.with_llm)
    if args.cmd == 'status':
        return status()
    return 1


if __name__ == '__main__':
    sys.exit(main())
