"""
knowledge_loop — the no-human-in-the-loop orchestrator.

Single entry point that runs the full self-adaptive knowledge refresh in
one pass. Designed to be called:

  - from the Claude Code Stop hook  (`python .agent_scripts/knowledge_loop.py`)
  - from the git post-commit hook  (same command)
  - from session-start              (catches up missed work)
  - from cron / systemd timer       (if no agent runtime is around)
  - manually                        (`python .agent_scripts/knowledge_loop.py run`)

The orchestrator runs these stages in order. Each stage is self-contained
and fails soft — a stage that fails never blocks the rest of the loop.

  0. Pre-flight    — check git, load manifest, ensure .agent_state exists
  1. Trail flush   — read session trail(s), dedupe touched paths
  2. Drift detect  — re-evaluate stale flags in the manifest
  3. delta_update  — LLM re-extraction on touched code files → graph.json
  4. Wiki rewrite  — LLM rationale check on touched concept pages → rewrite
  5. Fresh stamp   — mark all layers fresh in the manifest
  6. Audit         — log everything to .agent_state/knowledge_loop_log.json

A circuit breaker (in llm_call.py) opens after 3 consecutive LLM failures;
while open, stages 3+4 are skipped but everything else still runs.

Usage:
  python knowledge_loop.py                  # run with default session
  python knowledge_loop.py --session ID     # explicit session id
  python knowledge_loop.py --dry-run        # show plan, do nothing
  python knowledge_loop.py --no-llm         # structural-only (no LLM calls)
  python knowledge_loop.py --status         # last loop run summary
"""
from __future__ import annotations

import argparse
import json
import os
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
    """Read every trail file and union the touched paths. If session_id is
    provided, only that session; otherwise all sessions."""
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


# ------------------------------------------------------------------ main

def run(session: str | None = None, dry_run: bool = False,
        no_llm: bool = False) -> int:
    pr, trail, ks = _imports()
    started = time.time()

    # 0. Pre-flight
    if session is None:
        session = trail._session_id()
    print(f'knowledge_loop: session={session}')

    touched_paths = _dedupe_paths_from_trails(session)
    print(f'knowledge_loop: {len(touched_paths)} unique touched paths')

    # Detect drift up front (refreshes stale flags)
    try:
        ks.detect_drift()
    except Exception as e:
        print(f'knowledge_loop: WARN detect_drift failed: {e}', file=sys.stderr)

    if dry_run:
        print(f'knowledge_loop: dry-run, would have processed {len(touched_paths)} paths')
        return 0

    # 3+4. delta_update + wiki rewrite (if LLM allowed)
    delta_summary = {'status': 'skipped'}
    wiki_rewrites = []

    if no_llm:
        print('knowledge_loop: --no-llm, skipping LLM stages')
    else:
        # Check circuit breaker
        try:
            from llm_call import circuit_is_open
            if circuit_is_open():
                print('knowledge_loop: LLM circuit open, skipping LLM stages')
                no_llm = True
        except Exception as e:
            print(f'knowledge_loop: WARN llm_call import: {e}', file=sys.stderr)
            no_llm = True

    if not no_llm and touched_paths:
        # Stage 3: graphify delta_update
        try:
            delta_summary = pr.delta_update_graph(touched_paths, session)
            print(f'knowledge_loop: delta_update {delta_summary.get("status")} '
                  f'({len(delta_summary.get("updates", []))} files)')
            if delta_summary.get('status') == 'ok':
                added = pr.merge_delta_into_graph(delta_summary)
                print(f'knowledge_loop: delta merged {added} new graph nodes')
        except Exception as e:
            print(f'knowledge_loop: WARN delta_update: {e}', file=sys.stderr)

        # Stage 4: wiki write-through
        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        if touched_paths:
            concept_hits = pr._affected_concepts(touched_paths)
            for p, hits in concept_hits:
                try:
                    verdict = pr.autonomous_wiki_rewrite(p, hits, today)
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
                    print(f'knowledge_loop: wiki {p.name}: {tag} '
                          f'({verdict.get("reason", "")})')
                except Exception as e:
                    print(f'knowledge_loop: WARN wiki {p.name}: {e}',
                          file=sys.stderr)

    # Stage 2.5: structural annotation (always runs, even in --no-llm mode)
    # This is the cheap, deterministic part: mark graph nodes as touched,
    # append Recent change to wiki pages.
    try:
        graph = pr._read_graph()
        direct_ids = pr._affected_graph_nodes(graph, touched_paths) if graph else []
        if graph and direct_ids:
            pr._annotate_graph(graph, direct_ids, session)
            pr._write_graph(graph)
            print(f'knowledge_loop: annotated {len(direct_ids)} graph nodes')
        else:
            print(f'knowledge_loop: no graph nodes to annotate '
                  f'(graph nodes with matching source_file=0)')
    except Exception as e:
        print(f'knowledge_loop: WARN annotate_graph: {e}', file=sys.stderr)

    try:
        concept_hits_for_marker = pr._affected_concepts(touched_paths)
        for p, hits in concept_hits_for_marker:
            pr._append_recent_change(p, hits)
        if concept_hits_for_marker:
            print(f'knowledge_loop: appended Recent change to '
                  f'{len(concept_hits_for_marker)} wiki pages')
    except Exception as e:
        print(f'knowledge_loop: WARN append_recent_change: {e}', file=sys.stderr)

    # 5. Mark all layers fresh in the manifest
    try:
        for layer in ('graphify', 'wiki', 'ccc'):
            try:
                ks.mark_fresh(layer,
                              refreshed_paths=list(touched_paths),
                              session=session,
                              loop_ts=datetime.now(timezone.utc).isoformat(timespec='seconds'))
            except Exception as e:
                print(f'knowledge_loop: WARN mark_fresh({layer}): {e}',
                      file=sys.stderr)
        print('knowledge_loop: marked graphify + wiki + ccc fresh')
    except Exception as e:
        print(f'knowledge_loop: WARN mark_fresh: {e}', file=sys.stderr)

    # 6. Audit log
    elapsed = time.time() - started
    entry = {
        'ts':              datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'session':         session,
        'elapsed_s':       round(elapsed, 2),
        'touched_paths':   sorted(touched_paths),
        'delta_summary':   delta_summary,
        'wiki_rewrites':   wiki_rewrites,
        'no_llm':          no_llm,
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
    print(f"  delta: {last['delta_summary'].get('status', '?')}")
    rewrites_applied = sum(1 for w in last['wiki_rewrites'] if w.get('applied'))
    rewrites_flagged = sum(1 for w in last['wiki_rewrites']
                           if w.get('shift') and not w.get('applied'))
    print(f"  wiki rewrites: applied={rewrites_applied} flagged={rewrites_flagged}")
    print(f"  no_llm: {last.get('no_llm', False)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    # Handle the bare case (no subcommand) — default to `run`
    argv = list(argv or sys.argv[1:])
    if argv and argv[0] in {'run', 'status'}:
        cmd = argv[0]
        rest = argv[1:]
    else:
        cmd = 'run'
        rest = argv

    p = argparse.ArgumentParser(prog='knowledge_loop.py')
    p.add_argument('--session', default=None)
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--no-llm',  action='store_true',
                   help='skip LLM-powered stages (structural only)')
    sub = p.add_subparsers(dest='cmd', required=False)
    sub.add_parser('run',    help='run the loop')
    sub.add_parser('status', help='last loop run summary')

    args = p.parse_args(rest)
    args.cmd = cmd
    if args.cmd == 'status':
        return status()
    return run(session=args.session, dry_run=args.dry_run, no_llm=args.no_llm)


if __name__ == '__main__':
    sys.exit(main())
