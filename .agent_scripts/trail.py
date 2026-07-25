"""
Per-session trail recorder.

Records every Read/Write/Edit/NotebookEdit the agent performs into a
date+session-keyed JSONL file. This is the raw material the per-path
refresh step at session stop consumes.

Tools:
  python trail.py add <tool> <path> [--note "..."]    record one event
  python trail.py list [--session SESSION_ID]           list events
  python trail.py summary                              one-line summary of current session
  python trail.py clear --session SESSION_ID           wipe a session's trails
  python trail.py unique-files                         list unique paths touched this session

Session ID resolution:
  1. --session CLI flag (caller-supplied)
  2. $CLAUDE_SESSION_ID or $CURSOR_SESSION_ID env var
  3. today's date + a small hash of the parent PID (graceful fallback
     so the trail is robust even when no session ID is available)

The file is appended-only; rotation is by date.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = ROOT / '.agent_state'
STATE_DIR.mkdir(exist_ok=True)

TOOLS_OF_INTEREST = {'Write', 'Edit', 'MultiEdit', 'NotebookEdit', 'Read',
                     'Bash', 'Grep', 'Glob'}


# ------------------------------------------------------------------ session id

def _session_id() -> str:
    """Resolve the current session id.

    Priority: CLI flag > env var > date+pphash fallback.
    """
    # CLI flag handled by caller; this is the default path.
    for var in ('CLAUDE_SESSION_ID', 'CURSOR_SESSION_ID', 'AGENT_SESSION_ID'):
        v = os.environ.get(var)
        if v:
            return v.strip()
    # Fallback: today's date + a small hash of caller info
    ppid = os.getppid() if hasattr(os, 'getppid') else 0
    h = hashlib.sha256(f'{os.getpid()}-{ppid}-{os.environ.get("USERNAME", "")}'.encode()).hexdigest()[:8]
    return f'fallback-{datetime.now(timezone.utc).strftime("%Y%m%d")}-{h}'


def _trail_path(session_id: str) -> Path:
    safe = ''.join(c if c.isalnum() or c in '-_' else '_' for c in session_id)
    return STATE_DIR / f'trail_{safe}.jsonl'


# ------------------------------------------------------------------ CLI

def _record(session: str, tool: str, path: str, note: str = '') -> str:
    """Append one event; returns the normalized relative path."""
    # Normalize to a relative path under ROOT if possible
    try:
        rel = str(Path(path).resolve().relative_to(ROOT)).replace('\\', '/')
    except (ValueError, OSError):
        rel = path.replace('\\', '/')
    event = {
        'ts':      datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'session': session,
        'tool':    tool,
        'path':    rel,
        'note':    note or '',
    }
    trail = _trail_path(session)
    with trail.open('a', encoding='utf-8') as f:
        f.write(json.dumps(event, ensure_ascii=False) + '\n')
    return rel


def cmd_add(args: argparse.Namespace) -> int:
    session = args.session or _session_id()
    path = args.path
    if not path:
        print('trail.py: --path is required', file=sys.stderr)
        return 2
    rel = _record(session, args.tool, path, args.note)
    print(f'trail: {args.tool} {rel}  (session={session})')
    return 0


def cmd_hook(args: argparse.Namespace) -> int:
    """Record one event from a PostToolUse hook payload on stdin.

    Claude Code passes hooks a JSON object on stdin -- it does NOT substitute
    placeholders into the command string, which is why the previous
    `add __TOOL__ __FILE_PATH__` form failed on every single tool call.
    Relevant keys: session_id, tool_name, tool_input.{file_path,notebook_path}.

    Always exits 0. A trail recorder must never block or noisily fail the edit
    it is merely observing.
    """
    try:
        raw = sys.stdin.read()
    except Exception:
        return 0
    if not raw.strip():
        return 0
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return 0
    if not isinstance(payload, dict):
        return 0

    tool = str(payload.get('tool_name') or '')
    if tool not in TOOLS_OF_INTEREST:
        return 0
    tool_input = payload.get('tool_input')
    if not isinstance(tool_input, dict):
        return 0
    path = tool_input.get('file_path') or tool_input.get('notebook_path') or ''
    if not path:
        return 0

    session = args.session or payload.get('session_id') or _session_id()
    try:
        rel = _record(str(session), tool, str(path), args.note)
    except Exception as exc:  # disk full, permissions, race -- never propagate
        print(f'trail: skipped ({type(exc).__name__})', file=sys.stderr)
        return 0
    print(f'trail: {tool} {rel}')
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    session = args.session or _session_id()
    trail = _trail_path(session)
    if not trail.exists():
        print(f'(no trail for session {session})')
        return 0
    with trail.open('r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            print(f"{e['ts']}  {e['tool']:<8}  {e['path']}"
                  + (f"  [{e['note']}]" if e.get('note') else ''))
    return 0


def cmd_summary(args: argparse.Namespace) -> int:
    session = args.session or _session_id()
    trail = _trail_path(session)
    if not trail.exists():
        print(f'session={session}  events=0  files=0')
        return 0
    tools: dict[str, int] = {}
    files: set[str] = set()
    n = 0
    with trail.open('r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            n += 1
            tools[e['tool']] = tools.get(e['tool'], 0) + 1
            files.add(e['path'])
    print(f'session={session}  events={n}  unique_files={len(files)}')
    for tool, count in sorted(tools.items(), key=lambda kv: -kv[1]):
        print(f'  {tool:<10} {count}')
    return 0


def cmd_clear(args: argparse.Namespace) -> int:
    session = args.session or _session_id()
    trail = _trail_path(session)
    if trail.exists():
        trail.unlink()
        print(f'cleared trail {trail.name}')
    else:
        print(f'(no trail for session {session})')
    return 0


def cmd_unique_files(args: argparse.Namespace) -> int:
    """Print the unique set of paths touched this session, one per line.
    Used by path_refresh.py to know what to re-scan."""
    session = args.session or _session_id()
    trail = _trail_path(session)
    if not trail.exists():
        return 0
    files: set[str] = set()
    with trail.open('r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if e['tool'] in {'Read', 'Write', 'Edit', 'MultiEdit', 'NotebookEdit'}:
                files.add(e['path'])
    for f in sorted(files):
        print(f)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog='trail.py')
    p.add_argument('--session', help='override session id')
    sub = p.add_subparsers(dest='cmd', required=True)

    pa = sub.add_parser('add', help='record one event')
    pa.add_argument('tool', choices=sorted(TOOLS_OF_INTEREST))
    pa.add_argument('path')
    pa.add_argument('--note', default='')

    ph = sub.add_parser('hook',
                        help='record one event from a PostToolUse JSON payload on stdin')
    ph.add_argument('--note', default='')

    pl = sub.add_parser('list', help='list events')
    pu = sub.add_parser('summary', help='session summary')
    pc = sub.add_parser('clear', help='wipe a session trail')
    puf = sub.add_parser('unique-files',
                         help='print unique paths touched this session')

    args = p.parse_args(argv)
    if args.cmd == 'add':
        return cmd_add(args)
    if args.cmd == 'hook':
        return cmd_hook(args)
    if args.cmd == 'list':
        return cmd_list(args)
    if args.cmd == 'summary':
        return cmd_summary(args)
    if args.cmd == 'clear':
        return cmd_clear(args)
    if args.cmd == 'unique-files':
        return cmd_unique_files(args)
    return 1


if __name__ == '__main__':
    sys.exit(main())
