#!/usr/bin/env python3
"""Pull server-generated thesis-relevant paper briefings into this repo.

The OpenClaw server writes on-demand PDF summaries (from the !grab command /
📥 reaction) to ~/notes/Literature/summaries/ on the box. This copies them into
wiki/literature/ so they are git-tracked and picked up by Obsidian sync.

Run locally:  python scripts/pull_summaries.py
The files are world-readable, so a plain scp as root works (no sudo needed).
"""
import subprocess
import sys
from pathlib import Path

SERVER = "root@204.168.167.145"
REMOTE = "/home/openclaw/notes/Literature/summaries"
DEST = Path(__file__).resolve().parent.parent / "wiki" / "literature"


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    # scp expands the remote glob via the remote shell; -p preserves mtimes.
    cmd = f'scp -p "{SERVER}:{REMOTE}/*.md" "{DEST}"'
    print(f"[pull] {cmd}")
    r = subprocess.run(cmd, shell=True)
    if r.returncode != 0:
        print("[pull] scp failed (no summaries yet, or SSH/host issue).", file=sys.stderr)
        return r.returncode
    files = sorted(p.name for p in DEST.glob("*.md"))
    print(f"[pull] {len(files)} summary file(s) in {DEST}:")
    for f in files:
        print(f"        {f}")
    print("[pull] review, then `git add wiki/literature && git commit`.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
