# Flight telemetry — storage policy

Telemetry is **write-once bulk data**: a run is recorded, analysed, and never edited again.
Git is the wrong store for it — it versions every byte forever, and 191 tracked runs had grown
to **467 MB working tree / ~157 MiB packed**, which is the entire weight of this repository.

So telemetry is ignored by default and only *cited* runs are tracked.

## What is tracked

The 18 files referenced by `docs/`, `wiki/`, `sim/`, `flight_analysis/`, or ground-station
code — the evidence base for the ADRs and the analysis pipeline. Removing them would break
reproducibility of published results, so they stay in git despite the size (~80 MB).

They are re-included by explicit `!` negations at the bottom of `.gitignore`.

## What is not tracked

The other 173 runs (~386 MB) — routine flights that nothing cites. They are **still on disk**;
`git rm --cached` only stopped tracking them. `ARCHIVE_MANIFEST.csv` records path, size, and
date for every one, so the set is reconstructible even if the files move.

History was deliberately **not** rewritten: the blobs remain in past commits and the remote is
unchanged in size. Purging them would rewrite every commit SHA and break the hashes cited in
the ADRs and wiki — a cost already paid once (see the pre-filter-repo backup bundle). Since
`git push` measures at ~3 s, the size is not currently hurting anything that a rewrite would
fix. Untracking alone stops future growth and keeps `git worktree add` cheap, which is what
actually mattered.

## Adding a new run

New telemetry is ignored automatically — nothing to do, it just stays local.

**When a run becomes evidence** (you cite it in an ADR, a wiki page, or an analysis script),
promote it:

```bash
# 1. add the negation to .gitignore, next to the others
echo '!ground_station/logs/flight_<id>.csv' >> .gitignore
# 2. track it
git add .gitignore ground_station/logs/flight_<id>.csv
```

The `-f` shortcut (`git add -f <file>`) also works, but prefer the negation — it documents
*why* the file is tracked and survives someone regenerating the ignore rules.

## Archiving to a GitHub Release

Releases are the right home for write-once data: permanent URLs, no history bloat, no LFS
quota. Bundle and upload the untracked set:

```bash
tar -czf flight-logs-archive-$(date +%Y%m%d).tar.gz -T <(tail -n +2 ARCHIVE_MANIFEST.csv | cut -d, -f1)
gh release create logs-$(date +%Y%m%d) flight-logs-archive-*.tar.gz \
    --title "Flight log archive" --notes "173 uncited runs, see ARCHIVE_MANIFEST.csv"
```

Run this yourself — it publishes data to a public remote, so it is a deliberate act, not
something an agent should do on your behalf.

## Gotcha

The ignore rules use **file globs** (`ground_station/logs/**/*.csv`), never a bare directory.
Git cannot re-include a file whose parent directory is excluded, so `ground_station/logs/`
would make every `!` negation below it silently inoperative — the cited runs would drop out of
tracking with no error.
