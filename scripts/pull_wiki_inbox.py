#!/usr/bin/env python3
"""
Pull grabbed-paper notes + PDFs from the OpenClaw server's wiki_inbox into
raw/papers/, then report which papers are still awaiting wiki ingestion.

Runs automatically at session start (Claude Code SessionStart hook and the
Cursor project rule both call it), and can be run by hand:

    python scripts/pull_wiki_inbox.py            # pull + report
    python scripts/pull_wiki_inbox.py --report   # report only, no network

Requires `Host openclaw` in ~/.ssh/config (HostName 204.168.167.145, User root).
Always exits 0 — a dead network must never block a session from starting.
"""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PAPERS_DIR = PROJECT_ROOT / "raw" / "papers"
WIKI_DIR = PROJECT_ROOT / "wiki"
REMOTE = "openclaw"
REMOTE_INBOX = "/home/openclaw/workspace/wiki_inbox"
SSH_OPTS = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=8"]


def _remote_listing():
    """Return {filename: size} for notes + PDFs in the server inbox, or None."""
    try:
        out = subprocess.run(
            ["ssh", *SSH_OPTS, REMOTE,
             f"find {REMOTE_INBOX} -maxdepth 1 "
             r"\( -name '*.md' -o -name '*.pdf' \) -printf '%s %f\n'"],
            capture_output=True, text=True, timeout=30)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if out.returncode != 0:
        return None
    files = {}
    for line in out.stdout.splitlines():
        size, _, name = line.partition(" ")
        if name:
            files[name] = int(size)
    return files


def pull():
    """Copy any inbox file that is missing locally or differs in size."""
    remote = _remote_listing()
    if remote is None:
        print("[wiki-inbox] server unreachable — skipping pull (report is local-only)")
        return []
    PAPERS_DIR.mkdir(parents=True, exist_ok=True)
    wanted = [n for n, size in remote.items()
              if not (PAPERS_DIR / n).exists()
              or (PAPERS_DIR / n).stat().st_size != size]
    for name in wanted:
        r = subprocess.run(
            ["scp", *SSH_OPTS, f"{REMOTE}:{REMOTE_INBOX}/{name}",
             str(PAPERS_DIR / name)],
            capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            print(f"[wiki-inbox] FAILED to pull {name}: {r.stderr.strip()}")
    return wanted


def _source_url(note_path):
    """The `- url: ...` line a grab note carries, if any."""
    for line in note_path.read_text(encoding="utf-8", errors="replace").splitlines()[:20]:
        if line.startswith("- url:"):
            return line.split(":", 1)[1].strip()
    return ""


def pending_ingestion():
    """Notes in raw/papers/ that no wiki page references yet.

    Matched by filename OR source URL — the server re-exports the same paper
    under a new date when feedback arrives again, so filename alone would
    keep reporting already-ingested papers as pending.
    """
    if not PAPERS_DIR.is_dir():
        return []
    wiki_text = "\n".join(
        p.read_text(encoding="utf-8", errors="replace")
        for p in WIKI_DIR.rglob("*.md")) if WIKI_DIR.is_dir() else ""
    # Same paper, later date: the server re-exports on each new 📥. Keep one
    # entry per source URL — the newest, since only later grabs carry the PDF.
    best = {}
    for note in sorted(PAPERS_DIR.glob("*.md")):
        if note.name in wiki_text:
            continue
        url = _source_url(note)
        if url and url in wiki_text:
            continue
        best[url or note.name] = note.name
    return sorted(best.values())


def main():
    pulled = [] if "--report" in sys.argv else pull()
    for name in pulled:
        print(f"[wiki-inbox] pulled {name}")
    pending = pending_ingestion()
    if pending:
        print(f"[wiki-inbox] {len(pending)} grabbed paper(s) AWAITING WIKI INGESTION:")
        for name in pending:
            pdf = (PAPERS_DIR / name).with_suffix(".pdf")
            tag = "  [+PDF]" if pdf.exists() else ""
            print(f"  - raw/papers/{name}{tag}")
        print("[wiki-inbox] offer the user: ingest now (/wiki) or a "
              "learning session (/grill-paper)")
    else:
        print("[wiki-inbox] no papers pending ingestion")


if __name__ == "__main__":
    main()
    sys.exit(0)
