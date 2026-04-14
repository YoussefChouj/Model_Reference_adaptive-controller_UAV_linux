#!/usr/bin/env python3
"""
Sync wiki/ directory to Obsidian vault after wiki ingest/lint operations.

Usage:
    python3 scripts/sync_obsidian.py
    python3 scripts/sync_obsidian.py --dry-run
"""

import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
WIKI_DIR = PROJECT_ROOT / "wiki"
OBSIDIAN_VAULT = Path(r"C:\Users\Acer\OneDrive\Obsidian_vaults\OpenClaw_Brain")
OBSIDIAN_WIKI = OBSIDIAN_VAULT / "wiki"

DRY_RUN = "--dry-run" in sys.argv


def sync():
    if not WIKI_DIR.exists():
        print(f"[sync_obsidian] wiki/ not found at {WIKI_DIR}")
        sys.exit(1)

    if not OBSIDIAN_VAULT.exists():
        print(f"[sync_obsidian] Obsidian vault not found at {OBSIDIAN_VAULT}")
        print("  Skipping sync — vault may be on a different machine or drive.")
        return

    if DRY_RUN:
        print(f"[sync_obsidian] DRY RUN — would copy {WIKI_DIR} → {OBSIDIAN_WIKI}")
        for f in sorted(WIKI_DIR.rglob("*.md")):
            print(f"  {f.relative_to(WIKI_DIR)}")
        return

    if OBSIDIAN_WIKI.exists():
        shutil.rmtree(OBSIDIAN_WIKI)

    shutil.copytree(WIKI_DIR, OBSIDIAN_WIKI)

    files = list(OBSIDIAN_WIKI.rglob("*.md"))
    print(f"[sync_obsidian] Synced {len(files)} wiki pages -> {OBSIDIAN_WIKI}")


if __name__ == "__main__":
    sync()
