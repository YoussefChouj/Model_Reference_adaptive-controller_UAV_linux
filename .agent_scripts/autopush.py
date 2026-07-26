"""Push already-made commits to origin so a dead laptop cannot cost you work.

Deliberately conservative. It only ever pushes commits you made yourself:

  - never commits anything, never stages, never touches the working tree or index
  - never force-pushes, never rewrites, never deletes a remote branch
  - pushes the CURRENT branch to a remote branch of the same name, nothing else
  - no-op when there is nothing ahead, so it is safe to run on a timer

It does NOT protect uncommitted work -- that was a deliberate choice. When it finds
uncommitted changes it says so in the log, because that work is still only on one disk.

Stdlib only, so it runs under any Python on PATH.

    python .agent_scripts/autopush.py           # push if needed
    python .agent_scripts/autopush.py --dry-run # show what it would do
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path

TIMEOUT = 120  # a hung push must not wedge a git hook or a scheduled task


def git(*args: str, cwd: Path) -> tuple[int, str]:
    p = subprocess.run(
        ["git", "--no-pager", *args],
        cwd=cwd, capture_output=True, text=True, timeout=TIMEOUT,
    )
    return p.returncode, (p.stdout + p.stderr).strip()


def log(root: Path, msg: str) -> None:
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}"
    print(line)
    logfile = root / ".agent_state" / "autopush.log"
    logfile.parent.mkdir(parents=True, exist_ok=True)
    with logfile.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def main() -> int:
    dry = "--dry-run" in sys.argv

    rc, root_s = git("rev-parse", "--show-toplevel", cwd=Path.cwd())
    if rc != 0:
        print("not a git repository")
        return 1
    root = Path(root_s)

    # Mid-rebase/merge/bisect: HEAD is not a branch tip the user means to publish.
    gitdir = root / ".git"
    for marker in ("rebase-merge", "rebase-apply", "MERGE_HEAD", "BISECT_LOG", "CHERRY_PICK_HEAD"):
        if (gitdir / marker).exists():
            log(root, f"SKIP  operation in progress ({marker})")
            return 0

    rc, branch = git("rev-parse", "--abbrev-ref", "HEAD", cwd=root)
    if rc != 0 or branch == "HEAD":
        log(root, "SKIP  detached HEAD")
        return 0

    # Reported, never acted on -- see the module docstring.
    _, dirty = git("status", "--porcelain", cwd=root)
    dirty_n = len([ln for ln in dirty.splitlines() if ln.strip()])

    rc, _ = git("rev-parse", "--abbrev-ref", f"{branch}@{{u}}", cwd=root)
    has_upstream = rc == 0

    warn = f"  [WARNING: {dirty_n} uncommitted file(s), NOT backed up]" if dirty_n else ""

    if has_upstream:
        rc, ahead = git("rev-list", "--count", "@{u}..HEAD", cwd=root)
        if rc == 0 and ahead == "0":
            log(root, f"ok    {branch}: nothing to push{warn}")
            return 0
        what = f"{ahead} commit(s)"
    else:
        what = "new branch (no upstream yet)"

    if dry:
        log(root, f"DRY   would push {branch}: {what}{warn}")
        return 0

    push_args = ["push", "--set-upstream", "origin", branch] if not has_upstream \
        else ["push", "origin", branch]
    try:
        rc, out = git(*push_args, cwd=root)
    except subprocess.TimeoutExpired:
        log(root, f"FAIL  {branch}: push timed out after {TIMEOUT}s (offline?)")
        return 1

    if rc == 0:
        log(root, f"ok    pushed {branch}: {what}{warn}")
        return 0

    # Most common cause is the remote having moved on; a pull is the user's call, not ours.
    log(root, f"FAIL  {branch}: {out.splitlines()[-1] if out else 'push failed'}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
