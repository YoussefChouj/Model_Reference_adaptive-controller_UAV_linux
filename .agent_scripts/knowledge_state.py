"""
Knowledge-state manifest — single source of truth for "is each layer fresh?".

Read/written by knowledge_gate.py (gate awareness) and by any tool that
finishes a knowledge-stack update (graphify, wiki, cocoindex). The manifest
lives at .agent_state/knowledge_manifest.json and is keyed by layer:

  ccc       — semantic search index (.cocoindex_code/target_sqlite.db)
  graphify  — graph + report + cache (graphify-out/)
  wiki      — wiki pages (wiki/concepts/, wiki/entities/, ...)

Each layer tracks:
  last_fresh       ISO-8601 timestamp of the last successful update
  last_commit      git HEAD hash at the time of that update (or 'unknown')
  last_commit_ts   ISO-8601 timestamp from `git log -1 --format=%cI`
  known_files      set of (relative_path, mtime) last seen at update time
                   used to detect drift on agent edits even without a commit

A layer is considered "stale" when EITHER:
  - HEAD has moved past last_commit (a commit landed after the update)
  - a file in known_files has been modified (mtime changed) after last_fresh

Functions:
  is_fresh(layer)              → bool
  is_stale(layer)              → bool  (inverse)
  freshness_summary()          → dict  (for --status display)
  mark_fresh(layer, **meta)    → record a successful update
  record_seen_files(layer,paths) → seed known_files on first update
  detect_drift()               → re-check all layers; updates 'stale' flags
"""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = ROOT / '.agent_state'
STATE_DIR.mkdir(exist_ok=True)
MANIFEST_PATH = STATE_DIR / 'knowledge_manifest.json'

LAYERS = ('ccc', 'graphify', 'wiki')

# File globs that, when touched, make a layer stale. Conservative: only
# paths that are LIKELY to affect a given layer.
LAYER_WATCH_GLOBS = {
    'ccc':       ['**/*'],                       # CocoIndex watches everything
    'graphify':  ['API/**', 'TASK/**', 'BSP/**', 'USER/**',
                  'docs/**', 'wiki/**', 'sim/**'],
    'wiki':      ['wiki/**', 'docs/**', 'API/**', 'TASK/**'],
}


# ---------------------------------------------------------------- data model

@dataclass
class LayerState:
    last_fresh: str | None = None       # ISO ts of last successful update
    last_commit: str = 'unknown'        # git HEAD hash at that time
    last_commit_ts: str | None = None
    known_files: dict = field(default_factory=dict)  # rel_path -> mtime float
    stale: bool = False                 # last-detected staleness

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> 'LayerState':
        return cls(
            last_fresh=d.get('last_fresh'),
            last_commit=d.get('last_commit', 'unknown'),
            last_commit_ts=d.get('last_commit_ts'),
            known_files=d.get('known_files', {}),
            stale=d.get('stale', False),
        )


# ---------------------------------------------------------------- manifest I/O

def _empty_manifest() -> dict:
    return {layer: LayerState().to_dict() for layer in LAYERS}


def load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        try:
            data = json.loads(MANIFEST_PATH.read_text())
            # ensure all layers exist (forward-compat)
            for layer in LAYERS:
                data.setdefault(layer, LayerState().to_dict())
            return data
        except Exception:
            pass
    return _empty_manifest()


def save_manifest(m: dict) -> None:
    MANIFEST_PATH.write_text(json.dumps(m, indent=2))


# ---------------------------------------------------------------- git helpers

def git_head() -> tuple[str, str | None]:
    """Return (commit_hash, commit_iso_ts). 'unknown' if not a git repo."""
    try:
        h = subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'],
            cwd=str(ROOT), stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        return 'unknown', None
    try:
        ts = subprocess.check_output(
            ['git', 'log', '-1', '--format=%cI'],
            cwd=str(ROOT), stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        ts = None
    return h, ts or None


def git_changed_since(since_commit: str) -> list[str]:
    """Return list of changed file paths (relative) since since_commit.
    Empty list if since_commit is 'unknown' or git is unavailable."""
    if not since_commit or since_commit == 'unknown':
        return []
    try:
        out = subprocess.check_output(
            ['git', 'diff', '--name-only', f'{since_commit}..HEAD'],
            cwd=str(ROOT), stderr=subprocess.DEVNULL,
        ).decode()
        return [l.strip() for l in out.splitlines() if l.strip()]
    except Exception:
        return []


# ---------------------------------------------------------------- freshness

def _walk_watched(globs: list[str]) -> list[Path]:
    """Return all files under ROOT matching any glob in globs.
    Restricted to on-disk files only (skips .git, .agent_state, caches).

    Each glob may be a relative pattern like 'API/**' or 'docs/decisions.md'.
    pathlib's Path.glob('API/**') returns only the directory itself, not its
    contents — to enumerate files inside, the pattern must end in '/**/*'.
    We normalize trailing '/**' → '/**/*' and append '/*' to bare directory
    patterns like 'wiki'.
    """
    skip_dirs = {'.git', '.agent_state', 'graphify-out/cache',
                 '__pycache__', 'node_modules', '.cocoindex_code'}
    seen: set[Path] = set()
    for glob in globs:
        pattern = glob
        # Normalize directory-recursive patterns to actually match files.
        if pattern.endswith('/**'):
            pattern = pattern + '/*'
        elif pattern.endswith('/**/*') or '**/*' in pattern or '/*' in pattern:
            pass  # already explicit
        elif not any(ch in pattern for ch in ('*', '?', '[')):
            # bare directory like 'wiki' — recurse into its files
            pattern = pattern.rstrip('/') + '/**/*'
        for p in ROOT.glob(pattern):
            if not p.is_file():
                continue
            try:
                rel = p.relative_to(ROOT)
            except ValueError:
                continue
            if any(part in skip_dirs for part in rel.parts):
                continue
            seen.add(p)
    return sorted(seen)


def _snapshot_files(paths: Iterable[Path]) -> dict[str, float]:
    """rel_path -> mtime for the given paths."""
    out: dict[str, float] = {}
    for p in paths:
        try:
            rel = p.relative_to(ROOT).as_posix()
            out[rel] = p.stat().st_mtime
        except (ValueError, OSError):
            continue
    return out


def detect_drift() -> dict:
    """Re-check every layer against current HEAD + filesystem mtimes.
    Updates `stale` flags in the manifest and returns the new manifest."""
    m = load_manifest()
    head, head_ts = git_head()
    for layer in LAYERS:
        ls = LayerState.from_dict(m[layer])
        stale_reasons = []

        # Reason 1: HEAD has moved since last update
        if ls.last_commit != 'unknown' and ls.last_commit != head:
            changed = git_changed_since(ls.last_commit)
            if changed:
                stale_reasons.append(
                    f'{len(changed)} files changed since last update '
                    f'({ls.last_commit[:7]} → {head[:7]})'
                )

        # Reason 2: known files have been touched (mtime drift, even uncommitted)
        if ls.known_files:
            drifted = []
            for rel, old_mtime in ls.known_files.items():
                p = ROOT / rel
                if not p.exists():
                    drifted.append(f'{rel} (deleted)')
                    continue
                try:
                    if p.stat().st_mtime > old_mtime + 0.5:  # 0.5s slop
                        drifted.append(rel)
                except OSError:
                    drifted.append(f'{rel} (unreadable)')
            if drifted:
                stale_reasons.append(
                    f'{len(drifted)} known file(s) modified '
                    f'(uncommitted or external edit)'
                )

        ls.stale = bool(stale_reasons)
        m[layer] = ls.to_dict()
        # stash reasons in a transient field for the caller
        if stale_reasons:
            m[layer]['_reasons'] = stale_reasons
    save_manifest(m)
    return m


def is_stale(layer: str) -> bool:
    if layer not in LAYERS:
        return False
    return LayerState.from_dict(load_manifest()[layer]).stale


def is_fresh(layer: str) -> bool:
    return not is_stale(layer)


def freshness_summary() -> dict:
    """Return a human-friendly dict of the current state of all layers."""
    m = detect_drift()  # ensures flags are current
    out = {}
    for layer in LAYERS:
        ls = LayerState.from_dict(m[layer])
        out[layer] = {
            'last_fresh':     ls.last_fresh or 'never',
            'last_commit':    ls.last_commit,
            'stale':          ls.stale,
            'reasons':        m[layer].get('_reasons', []),
            'tracked_files':  len(ls.known_files),
        }
    return out


# ---------------------------------------------------------------- update hooks

def mark_fresh(layer: str, **meta) -> dict:
    """Record that `layer` was just updated. Resets stale flag, snapshots files.

    `meta` may include 'note' (free-text), 'token_cost' (int), etc.
    """
    if layer not in LAYERS:
        raise ValueError(f'unknown layer: {layer!r}')
    m = load_manifest()
    head, head_ts = git_head()
    paths = _walk_watched(LAYER_WATCH_GLOBS[layer])
    known = _snapshot_files(paths)
    ls = LayerState(
        last_fresh=datetime.now(timezone.utc).isoformat(timespec='seconds'),
        last_commit=head,
        last_commit_ts=head_ts,
        known_files=known,
        stale=False,
    )
    m[layer] = ls.to_dict()
    m[layer].update(meta)
    save_manifest(m)
    return m[layer]


def record_seen_files(layer: str, paths: Iterable[Path]) -> None:
    """Seed known_files for a layer without marking it fresh.
    Useful when an ingestion pass saw N files but the caller wants to defer
    the staleness-reset until later."""
    if layer not in LAYERS:
        return
    m = load_manifest()
    ls = LayerState.from_dict(m[layer])
    ls.known_files.update(_snapshot_files(paths))
    m[layer] = ls.to_dict()
    save_manifest(m)


# ---------------------------------------------------------------- CLI

def _print_summary(summary: dict) -> None:
    print(f"[knowledge-state] manifest: {MANIFEST_PATH.relative_to(ROOT)}")
    for layer, s in summary.items():
        flag = 'STALE' if s['stale'] else 'fresh'
        print(f"  {layer:<8} [{flag}] last_fresh={s['last_fresh']} "
              f"commit={s['last_commit'][:7]} tracked={s['tracked_files']}")
        for r in s['reasons']:
            print(f"           ↳ {r}")


def main(argv: list[str]) -> int:
    if '--status' in argv:
        _print_summary(freshness_summary())
        return 0
    if '--detect' in argv:
        # run detect_drift but only print the stale layers
        m = detect_drift()
        stale = [layer for layer, d in m.items() if d.get('stale')]
        print(f"stale layers: {stale or '∅'}")
        return 0
    # default: print help
    print(__doc__)
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main(sys.argv[1:]))
