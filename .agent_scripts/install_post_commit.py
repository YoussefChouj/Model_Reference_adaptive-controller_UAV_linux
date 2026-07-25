"""
Install/uninstall the repo-local post-commit hook that fires the
self-adaptive knowledge loop after every commit.

Usage:
  python .agent_scripts/install_post_commit.py install
  python .agent_scripts/install_post_commit.py uninstall
  python .agent_scripts/install_post_commit.py status
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOK_SRC = ROOT / '.agent_hooks' / 'post-commit'
HOOK_DST = ROOT / '.git' / 'hooks' / 'post-commit'


def install() -> int:
    if not HOOK_SRC.exists():
        print(f'install_post_commit: missing source hook {HOOK_SRC}', file=sys.stderr)
        return 2
    HOOK_DST.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(HOOK_SRC, HOOK_DST)
    # Mark executable on POSIX; on Windows the file is invoked by git directly.
    try:
        os.chmod(HOOK_DST, 0o755)
    except Exception:
        pass
    print(f'install_post_commit: installed -> {HOOK_DST}')
    return 0


def uninstall() -> int:
    if HOOK_DST.exists():
        HOOK_DST.unlink()
        print(f'install_post_commit: removed {HOOK_DST}')
    else:
        print('install_post_commit: nothing to remove')
    return 0


def status() -> int:
    print(f'src: {HOOK_SRC}  exists={HOOK_SRC.exists()}')
    print(f'dst: {HOOK_DST}  exists={HOOK_DST.exists()}')
    return 0


def main(argv: list[str] | None = None) -> int:
    if not argv or argv[0] not in {'install', 'uninstall', 'status'}:
        print(__doc__)
        return 0
    return {'install': install, 'uninstall': uninstall, 'status': status}[argv[0]]()


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
