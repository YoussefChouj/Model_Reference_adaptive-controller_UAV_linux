---
name: git-worktree
description: >
  Use git worktrees to run multiple coding agents in parallel on one repo without
  collisions. Use when starting a task in a shared repo, when the user says "worktree",
  "parallel agents", or when agents keep overwriting each other's changes. Covers
  creating worktrees, making them complete, merging back, and cleanup.
disable-model-invocation: true
---

# Git Worktrees for Parallel Agents

## Detect where you are

```bash
[ "$(git rev-parse --path-format=absolute --git-dir)" = "$(git rev-parse --path-format=absolute --git-common-dir)" ] \
  && echo "primary checkout" || echo "worktree"
```

- **Primary checkout** → do NOT start editing here. Create a worktree, `cd` into it, do ALL task work there.
- **Worktree** → proceed with the task.

## The working model

- **One task = one worktree = one agent session.** Never let two agents share a working directory.
- **The primary checkout is the integration point.** It stays on the main branch and is used only to review, merge, and push. It is not a scratchpad.
- **Nothing auto-merges.** The human reviews each worktree's diff, then merges it into main, then deletes the worktree.
- **Worktree branches are local and short-lived.** Never push them unless the user explicitly asks.
- Merge one worktree at a time. Rebase a stale worktree onto main before merging if main moved.

## Creating and removing

```bash
git worktree add ../myrepo-task-x          # new worktree + branch
git worktree add ../fix-y -b fix-y main    # explicit branch off main
git worktree list                          # see all worktrees
git worktree remove ../myrepo-task-x       # delete when merged/abandoned
git worktree prune                         # clean up stale registrations
```

Note: a branch can only be checked out in ONE worktree at a time.

## Making the worktree complete

A fresh worktree contains ONLY tracked files. Everything gitignored is missing. Replicate:

1. **Env/secret files** — copy `.env`, `.env.local`, and similar from the primary checkout.
   Copy, never symlink (an agent editing a symlinked env file would corrupt the original).
2. **Dependencies** — run the install (`npm ci`, `uv sync`, etc.). Never symlink `node_modules`.
3. **Local databases and services** — pin identity so worktrees don't spawn duplicates fighting
   over the same port.
4. **Ports** — dev servers bind fixed ports. Either run one at a time across all worktrees,
   or make the port configurable per worktree.
5. **Generated files and caches** — rebuild in the worktree; build output is gitignored.
6. **Git hooks** — `core.hooksPath` and `.git/config` are shared across worktrees automatically.

## Merging back

```bash
# from the primary checkout, after reviewing the worktree's diff:
git merge --no-ff task-branch
git worktree remove ../myrepo-task-x
git branch -d task-branch
```

## Gotchas

- Gitignored files silently missing is the #1 failure — always bootstrap before the agent starts.
- Disk: each worktree duplicates the working files. Delete merged worktrees; don't hoard them.
- Long-lived worktrees rot. Rebase onto main or restart if a task stalls for days.
- Uncommitted work in a deleted worktree is gone. Commit early and often.
- One shared stash, one shared config, one shared refs — worktrees isolate files, not git state.
