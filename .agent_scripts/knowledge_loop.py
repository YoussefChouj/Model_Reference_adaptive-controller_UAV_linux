"""
knowledge_loop — the no-human-in-the-loop orchestrator.

Single entry point that runs the deterministic part of the self-adaptive
knowledge refresh. The **LLM parts** are NOT performed by this script — they
are owned by the dedicated `uav-knowledge-writer` subagent
(see `.cursor/agents/uav-knowledge-writer.md`), which has its own model and
context and applies the rewrites itself.

This script only does the structural, deterministic work:

  0. Pre-flight    — load manifest, ensure .agent_state exists
  1. Trail flush   — read session trail(s), dedupe touched paths
  2. Drift detect  — re-evaluate stale flags in the manifest
  3. Annotate      — mark touched graph nodes with last_touched_session
  4. Recent change — append dated Recent change section to touched wiki pages
  5. Fresh stamp   — mark graphify + wiki + ccc fresh in the manifest
  6. Audit         — log everything to .agent_state/knowledge_loop_log.json

The actual LLM-driven graphify delta_update and wiki write-through happen
when the `uav-knowledge-writer` subagent (or the parent agent itself, mid-task)
calls:

  python .agent_scripts/knowledge_loop.py delta_update --paths <a,b,c>
  python .agent_scripts/knowledge_loop.py wiki_check     --paths <a,b,c>

These two subcommands return JSON prompts/instructions that the caller
runs through its own model.

Usage:
  python knowledge_loop.py                       # run with current session
  python knowledge_loop.py --session ID          # explicit session
  python knowledge_loop.py --dry-run             # show plan, do nothing
  python knowledge_loop.py status                # last loop run summary
  python knowledge_loop.py delta_update --paths a,b,c
  python knowledge_loop.py wiki_check     --paths a,b,c
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = ROOT / '.agent_state'
STATE_DIR.mkdir(exist_ok=True)

LOG_PATH = STATE_DIR / 'knowledge_loop_log.json'
SKIP_GLOBS = {'.git', '__pycache__', 'node_modules', '.agent_state',
              'graphify-out/cache', '.cocoindex_code', 'OBJ'}


# ------------------------------------------------------------------ helpers

def _imports():
    sys.path.insert(0, str(ROOT / '.agent_scripts'))
    import path_refresh as pr
    import trail
    import knowledge_state as ks
    return pr, trail, ks


def _normalize(p: str) -> str:
    return p.replace('\\', '/').lstrip('./')


def _should_skip(p: str) -> bool:
    return any(part in SKIP_GLOBS for part in p.split('/'))


def _dedupe_paths_from_trails(session_id: str | None) -> set[str]:
    paths: set[str] = set()
    pattern = f'trail_{session_id}.jsonl' if session_id else 'trail_*.jsonl'
    for tf in STATE_DIR.glob(pattern):
        with tf.open('r', encoding='utf-8') as f:
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
                    if p and not _should_skip(p):
                        paths.add(p)
    return paths


def _append_log(entry: dict) -> None:
    log = []
    if LOG_PATH.exists():
        try:
            log = json.loads(LOG_PATH.read_text())
        except Exception:
            log = []
    log.append(entry)
    LOG_PATH.write_text(json.dumps(log[-100:], indent=2))


# ------------------------------------------------------------------ main pipeline

def run(session: str | None = None, dry_run: bool = False) -> int:
    """Deterministic stages of the loop. No LLM calls."""
    pr, trail, ks = _imports()
    started = time.time()

    if session is None:
        session = trail._session_id()
    print(f'knowledge_loop: session={session}')

    touched_paths = _dedupe_paths_from_trails(session)
    print(f'knowledge_loop: {len(touched_paths)} unique touched paths')

    try:
        ks.detect_drift()
    except Exception as e:
        print(f'knowledge_loop: WARN detect_drift failed: {e}', file=sys.stderr)

    if dry_run:
        print(f'knowledge_loop: dry-run, would have processed '
              f'{len(touched_paths)} paths')
        return 0

    # Stage 3: annotate touched graph nodes
    annotated_count = 0
    try:
        graph = pr._read_graph()
        direct_ids = (pr._affected_graph_nodes(graph, touched_paths)
                      if graph else [])
        if graph and direct_ids:
            pr._annotate_graph(graph, direct_ids, session)
            pr._write_graph(graph)
            annotated_count = len(direct_ids)
            print(f'knowledge_loop: annotated {annotated_count} graph nodes')
        else:
            print('knowledge_loop: no graph nodes to annotate')
    except Exception as e:
        print(f'knowledge_loop: WARN annotate_graph: {e}', file=sys.stderr)

    # Stage 4: Recent change markers on touched wiki pages
    wiki_pages_flagged = 0
    try:
        concept_hits = pr._affected_concepts(touched_paths)
        for p, hits in concept_hits:
            pr._append_recent_change(p, hits)
        wiki_pages_flagged = len(concept_hits)
        if wiki_pages_flagged:
            print(f'knowledge_loop: appended Recent change to '
                  f'{wiki_pages_flagged} wiki pages')
    except Exception as e:
        print(f'knowledge_loop: WARN append_recent_change: {e}', file=sys.stderr)

    # Stage 5: fresh stamp
    try:
        for layer in ('graphify', 'wiki', 'ccc'):
            try:
                ks.mark_fresh(layer,
                              refreshed_paths=list(touched_paths),
                              session=session,
                              loop_ts=datetime.now(timezone.utc)
                                     .isoformat(timespec='seconds'))
            except Exception as e:
                print(f'knowledge_loop: WARN mark_fresh({layer}): {e}',
                      file=sys.stderr)
        print('knowledge_loop: marked graphify + wiki + ccc fresh')
    except Exception as e:
        print(f'knowledge_loop: WARN mark_fresh: {e}', file=sys.stderr)

    # Stage 6: audit
    elapsed = time.time() - started
    entry = {
        'ts':              datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'session':         session,
        'elapsed_s':       round(elapsed, 2),
        'touched_paths':   sorted(touched_paths),
        'annotated_nodes': annotated_count,
        'wiki_pages_flagged': wiki_pages_flagged,
    }
    _append_log(entry)
    print(f'knowledge_loop: done in {elapsed:.1f}s')
    return 0


def status() -> int:
    log = []
    if LOG_PATH.exists():
        try:
            log = json.loads(LOG_PATH.read_text())
        except Exception:
            log = []
    if not log:
        print('knowledge_loop: no runs recorded')
        return 0
    last = log[-1]
    print(f"last run: {last['ts']}  session={last['session']}  "
          f"elapsed={last['elapsed_s']}s")
    print(f"  touched paths: {len(last['touched_paths'])}")
    print(f"  annotated nodes: {last.get('annotated_nodes', '?')}")
    print(f"  wiki pages flagged: {last.get('wiki_pages_flagged', '?')}")
    return 0


# ------------------------------------------------------------------ LLM-driver helpers

def delta_update_cmd(paths: list[str]) -> int:
    """Build the prompt for the agent's own LLM to extract graph entities
    from the listed source files. Prints JSON instructions; the agent runs
    the LLM call itself and then calls merge_delta_into_graph(...).
    """
    pr, _, _ = _imports()
    out = []
    for rel in paths:
        p = ROOT / rel
        if not p.exists():
            print(f'  SKIP: {rel} (not found)', file=sys.stderr)
            continue
        if not rel.endswith(('.c', '.h', '.cpp', '.hpp', '.py', '.js', '.ts')):
            print(f'  SKIP: {rel} (not source)', file=sys.stderr)
            continue
        prompt = pr.delta_update_graph_from_text(rel, p.read_text(encoding='utf-8'))
        out.append(prompt)
    print(json.dumps(out, indent=2))
    return 0


def wiki_check_cmd(paths: list[str]) -> int:
    """Build prompts for the agent's own LLM to check whether rationale
    shifted on wiki concept pages affected by the listed files. Prints JSON
    instructions; the agent runs the LLM call itself and then calls
    autonomous_wiki_rewrite_from_verdict(...).
    """
    pr, _, _ = _imports()
    touched = {_normalize(p) for p in paths}
    out = []
    concept_hits = pr._affected_concepts(touched)
    for p, hits in concept_hits:
        prompt = pr.wiki_write_through_from_text(p, hits)
        out.append(prompt)
    print(json.dumps(out, indent=2))
    return 0


# ------------------------------------------------------------------ CLI

def main(argv: list[str] | None = None) -> int:
    argv = list(argv or sys.argv[1:])
    if argv and argv[0] in {'run', 'status', 'delta_update', 'wiki_check'}:
        cmd = argv[0]
        rest = argv[1:]
    else:
        cmd = 'run'
        rest = argv

    if cmd == 'status':
        return status()

    if cmd == 'delta_update':
        ap = argparse.ArgumentParser(prog='knowledge_loop.py delta_update')
        ap.add_argument('--paths', required=True,
                        help='comma-separated source files')
        args = ap.parse_args(rest)
        return delta_update_cmd([p.strip() for p in args.paths.split(',') if p.strip()])

    if cmd == 'wiki_check':
        ap = argparse.ArgumentParser(prog='knowledge_loop.py wiki_check')
        ap.add_argument('--paths', required=True,
                        help='comma-separated source files (used to find affected wiki pages)')
        args = ap.parse_args(rest)
        return wiki_check_cmd([p.strip() for p in args.paths.split(',') if p.strip()])

    # Default: `run`
    ap = argparse.ArgumentParser(prog='knowledge_loop.py run')
    ap.add_argument('--session', default=None)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args(rest)
    return run(session=args.session, dry_run=args.dry_run)


if __name__ == '__main__':
    sys.exit(main())
