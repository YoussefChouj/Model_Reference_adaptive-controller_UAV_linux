"""
Extract assistant text turns from a Claude Code session JSONL file.
Produces a clean plain-text file suitable as input to distill-trace.

Usage:
  python extract_history.py                       # latest session, print to stdout
  python extract_history.py --session <uuid>      # specific session
  python extract_history.py --out <path>          # write to file instead of stdout
  python extract_history.py --list                # list available sessions
  python extract_history.py --include-tools       # also include key tool results (Read paths, ccc search queries)
"""
import argparse, json, re, sys
from pathlib import Path
from datetime import datetime

PROJECTS_DIR = Path.home() / '.claude' / 'projects'


def cwd_slug(cwd: Path) -> str:
    """Reproduce Claude Code's project directory naming: each non-alnum char → '-'."""
    return re.sub(r'[^a-zA-Z0-9]', '-', str(cwd))


def find_project_dir(cwd: Path) -> Path:
    slug = cwd_slug(cwd)
    candidate = PROJECTS_DIR / slug
    if candidate.exists():
        return candidate
    # Fallback: search for partial match (handles minor path variation)
    matches = [d for d in PROJECTS_DIR.iterdir() if d.is_dir() and d.name in slug or slug in d.name]
    if matches:
        return sorted(matches, key=lambda d: len(d.name), reverse=True)[0]
    raise FileNotFoundError(
        f'No Claude project directory found for {cwd}\n'
        f'Expected: {candidate}\n'
        f'Available: {[d.name for d in PROJECTS_DIR.iterdir() if d.is_dir()][:5]}'
    )


def list_sessions(project_dir: Path) -> list[Path]:
    return sorted(project_dir.glob('*.jsonl'), key=lambda p: p.stat().st_mtime, reverse=True)


def extract(session_path: Path, include_tools: bool = False) -> str:
    lines_out = []
    lines_out.append(f'# Session: {session_path.stem}')
    lines_out.append(f'# Extracted: {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    lines_out.append('')

    # Claude Code JSONL format: each line is an envelope with 'type' (user/assistant/system/attachment)
    # and 'message' containing the actual {role, content} object.
    turn = 0
    for raw in session_path.read_text(encoding='utf-8', errors='replace').splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            envelope = json.loads(raw)
        except json.JSONDecodeError:
            continue

        if not isinstance(envelope, dict):
            continue

        obj_type = envelope.get('type', '')
        msg = envelope.get('message', {}) if isinstance(envelope.get('message'), dict) else {}
        content = msg.get('content', envelope.get('content', ''))

        if obj_type == 'assistant':
            turn += 1
            text_blocks = []
            if isinstance(content, str):
                text_blocks = [content]
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get('type') == 'text':
                        text_blocks.append(block['text'])
                    # skip 'thinking' blocks — internal reasoning, not useful for distillation

            text = '\n'.join(text_blocks).strip()
            if text:
                lines_out.append(f'--- Turn {turn} [assistant] ---')
                lines_out.append(text)
                lines_out.append('')

        elif obj_type == 'user' and include_tools:
            # User turns contain tool results as content blocks
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get('type') == 'tool_result':
                        for inner in block.get('content', []):
                            if isinstance(inner, dict) and inner.get('type') == 'text':
                                snippet = inner['text'][:300].replace('\n', ' ')
                                lines_out.append(f'  [tool-result snippet] {snippet}')
                lines_out.append('')

    return '\n'.join(lines_out)


def main():
    parser = argparse.ArgumentParser(description='Extract Claude session history for distill-trace')
    parser.add_argument('--session', help='Session UUID (default: most recent)')
    parser.add_argument('--out', help='Output file path (default: stdout)')
    parser.add_argument('--list', action='store_true', help='List available sessions')
    parser.add_argument('--include-tools', action='store_true', help='Include tool result snippets')
    parser.add_argument('--cwd', help='Project working directory (default: current dir)')
    args = parser.parse_args()

    cwd = Path(args.cwd) if args.cwd else Path.cwd()

    try:
        project_dir = find_project_dir(cwd)
    except FileNotFoundError as e:
        print(f'ERROR: {e}', file=sys.stderr)
        sys.exit(1)

    sessions = list_sessions(project_dir)
    if not sessions:
        print('No session files found.', file=sys.stderr)
        sys.exit(1)

    if args.list:
        print(f'Project: {project_dir}')
        for s in sessions:
            mtime = datetime.fromtimestamp(s.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
            size_kb = s.stat().st_size // 1024
            print(f'  {mtime}  {size_kb:>6} KB  {s.stem}')
        return

    if args.session:
        matches = [s for s in sessions if s.stem.startswith(args.session)]
        if not matches:
            print(f'ERROR: No session matching "{args.session}"', file=sys.stderr)
            sys.exit(1)
        session_path = matches[0]
    else:
        session_path = sessions[0]

    print(f'Extracting: {session_path.name} ({session_path.stat().st_size // 1024} KB)', file=sys.stderr)
    text = extract(session_path, include_tools=args.include_tools)

    if args.out:
        Path(args.out).write_text(text, encoding='utf-8')
        print(f'Written to: {args.out}', file=sys.stderr)
    else:
        print(text)


if __name__ == '__main__':
    main()
