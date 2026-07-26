---
name: commit
description: >
  Commit the working tree in coherent, well-messaged commits using a single state-gathering
  round-trip. Use when the user says "commit", "commit the changes", "commit this", or hands
  over a finished piece of work to be recorded. Does not push.
---

# /commit

Git is fast here — measured: `status` 0.1 s, `push --dry-run` 3.4 s, the `post-commit`
knowledge-loop hook 5.5 s and properly backgrounded. **What makes committing feel slow is
agent round-trips**, not git. A careless run of this task costs a dozen tool calls: status,
ignore checks, four separate diff inspections, branch, commits, verification.

So the rule of this skill is: **gather everything in one call, decide offline, then commit.**
Target is 2–3 tool calls total.

## Phase 1 — one snapshot, one call

Run this verbatim. It emits every input the grouping decision needs:

```bash
cd "<repo root>" && \
echo "=== BRANCH ==="            && git branch --show-current && \
echo "=== AHEAD OF REMOTE ==="   && git --no-pager log --oneline @{u}.. 2>/dev/null | wc -l && \
echo "=== STATUS ==="            && git --no-pager status --porcelain && \
echo "=== DIFFSTAT (tracked) ===" && git --no-pager diff --stat && \
echo "=== STAGED ==="            && git --no-pager diff --cached --stat && \
echo "=== INVISIBLE (assume-unchanged/skip-worktree) ===" && git ls-files -v | grep -E "^[a-z]" && \
echo "=== RECENT STYLE ==="      && git --no-pager log --oneline -8
```

`--no-pager` on every read is mandatory. `core.pager` is `cat` in this repo, but that is
repo-local and does not follow a fresh clone or a worktree — a paged `git log` blocks until the
tool times out, which is the single most expensive mistake available here.

Read untracked directories with one `find`/`ls` if the status output leaves their contents
unclear. Do not inspect files one at a time.

## Phase 2 — group before writing anything

Never lump an entire mixed tree into one commit. Split by **concern**, not by file type:

- Work the user wrote vs. work you wrote in this session — different provenance, different
  commits.
- Feature / fix / chore boundaries.
- Anything the user did not ask about and you merely noticed — leave it unstaged and say so.

If the tree mixes their substantial work with your incidental changes, their work gets its own
commit with its own message. It is their history.

**Branch first if on the default branch** (`main` here). Then tell the user the exact
fast-forward command rather than deciding the merge for them:

```bash
git checkout main && git merge --ff-only <branch>
```

## Phase 3 — messages

Match the repo's existing style (`feat(scope):`, `fix(scope):`, `chore(scope):` — check the
`RECENT STYLE` block). Subject under ~72 chars, imperative.

The body explains **why**, and specifically *what was true that made this necessary* — the
measurement, the failure, the constraint. A body that restates the diff is worthless; the diff
is right there. Record what a reader six months from now cannot reconstruct.

End every message with:

```
Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
```

## Traps that have actually bitten here

**Heredoc, not here-string.** In the Bash tool use `git commit -F - <<'EOF' … EOF`. The
PowerShell form `-m @' … '@` is a *parser error's worth of silence* in Bash — it commits with
a literal `@` as the first character of the subject line. If you catch it, `--amend -F -` is
the fix; a follow-up commit cannot repair a subject.

**`&&` short-circuits on an ignored file.** `git add` returns non-zero if any path is covered
by `.gitignore`, so `git add X && git commit …` silently skips the commit and the log still
shows the previous SHA. Always print `git log --oneline -1` at the end and confirm the SHA
changed.

**`assume-unchanged` files are invisible.** `CLAUDE.md` and `docs/adr/0011-*.md` carry the `h`
flag, so git ignores all edits to them — including session-state updates. They will never
appear in `status` and never be committed. If the session edited one, say so explicitly rather
than letting the user believe it was recorded. Do not clear the bit unilaterally; it may be
deliberate churn suppression.

**Over-broad ignore patterns.** A bare `logs/` matches at *any* depth. Before adding an ignore
rule, test it both directions:

```bash
git check-ignore -v <file-that-must-be-ignored>     # expect a match
git check-ignore -v <file-that-must-stay-tracked>   # expect no match
```

Git also cannot re-include a file whose parent **directory** is excluded, so use file globs
(`some/dir/**/*.csv`) whenever any `!` negation follows.

## Hard rules

- **Never push.** Committing is local and reversible; pushing is outward-facing. Say the work
  is committed and let the user push, unless they explicitly asked for a push.
- Never `git add -A` blind. Stage the paths you decided on.
- Never amend or rebase a commit that is already on the remote.
- Never commit generated output, large binaries, or telemetry — see
  `ground_station/logs/README.md` for the storage policy.
- If the tree is clean, say so and stop. Do not invent a commit.
- Report the resulting SHAs and one line on what each covers.
