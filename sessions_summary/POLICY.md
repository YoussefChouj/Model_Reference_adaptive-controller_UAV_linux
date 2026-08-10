# Session State policy

This file is the contract between `CLAUDE.md` and `sessions_summary/`. It answers three questions:

1. What goes where?
2. When does content move from one to the other?
3. How do archives stay trustworthy?

Read it once when the dispatcher or planner loads context. Cite it (do not restate it) when the question comes up again.

---

## 1. Status taxonomy

Every work block in this repo carries exactly one of these statuses. The status lives in the `CLAUDE.md` Session State entry for the active session, and in the front-matter of the corresponding `sessions_summary/YYYY-MM-DD-<topic>.md` file.

### `active`

A goal is in progress. Open decisions exist. The agent working it is still discovering.

**In `CLAUDE.md`:** the full Session State block — goal, FC state, constraints, decisions, next action.
**In `sessions_summary/`:** a one-line pointer is enough. Detail lives in `CLAUDE.md` until status changes.

### `paused`

The goal is suspended waiting on an external event the operator controls — a flight, a hardware swap, an answer from the seller. The agent cannot make progress without that event.

**In `CLAUDE.md`:** one paragraph. State the goal, name the blocker, name the trigger that would resume it. Lose everything else. The blocker line is the load-bearing bit — a future agent must be able to read it and tell whether the trigger has fired.
**In `sessions_summary/`:** pointer + one-line outcome so far.

### `closed`

The goal is delivered. Acceptance criteria met against a real signal (flashed image, test pass, measured throughput, replay match). No open work.

**In `CLAUDE.md`:** pointer + one-line outcome. Detail is gone.
**In `sessions_summary/`:** the full detail file. This is where the measurements, gotchas, what-changed lists, and diagnostic sequences go.

### `superseded`

A newer session has invalidated the findings. Hardware was swapped. A protocol changed. A constraint was lifted.

**In `CLAUDE.md`:** not referenced. A `superseded` archive is never cited from a fresh agent's cold start; it is read only when the topic comes up directly.
**In `sessions_summary/`:** the full file remains, with a `## Supersession note` at the top naming the successor and the date.

---

## 2. The hybrid trigger — when to move content

The archive move fires on **either** of:

### Trigger A — status transition

The operator (or the agent acting on operator intent) declares the goal done. This is the normal path. The agent that detects acceptance writes the archive file in the same turn it edits `CLAUDE.md`.

Detection rules:

- A task with `state: done` in `.agent_contracts/ROADMAP.md`.
- The operator says "that's done", "shipped", "we're not touching that again", or equivalent.
- The current goal in `CLAUDE.md` Session State has no remaining "Open decisions" items.

When in doubt: ask. The cost of a wrong transition is low (the file is recoverable), the cost of *not* asking is a Session State that grows back to 30 KB.

### Trigger B — staleness cap (safety net)

A session with `Last Updated` older than **7 days** AND no commits to any file it referenced in the intervening period is **auto-paused** the next time an agent touches `CLAUDE.md`. Not deleted — compressed. The pointer remains; the detail moves to `sessions_summary/`.

The agent that does this appends a note to `journal.md` (if the session is task-driven) or to `sessions_summary/<file>.md` itself explaining the auto-pause and what would resume it.

The 7-day threshold is a default. Override per-session in the archive file's front-matter if a session has a known long pause (e.g. "waiting on seller reply, expect 30-day turnaround").

### Why both

Status transitions are how the *operator* drives the system. The staleness cap is how the *system* drives the operator when the operator forgets. Each fails in the other's absence:

- Status only: archives never get written; `CLAUDE.md` grows without bound.
- Staleness only: archives get written at random times; the operator loses the ability to say "I'm still working on that".

---

## 3. What goes where (decision table)

| Kind of content | Lives in |
|---|---|
| **Current goal** (one line) | `CLAUDE.md` Session State (always, for any non-trivial session) |
| **FC live state** (powered, disarmed, running `Code=N`, etc.) | `CLAUDE.md` while session is `active`; archive file's first paragraph once moved |
| **Active constraints** that override older docs | `CLAUDE.md` Session State (these are the rules; they don't move) |
| **Hard constraints** (flashing, livewatch policy, etc.) | `.cursor/rules/hardware-safety.mdc` (always — they don't move) |
| **Open decisions** the user owes | `CLAUDE.md` Session State under `Open decisions` |
| **Next-action order** | `CLAUDE.md` Session State while `active`; `sessions_summary/<file>.md` "Next action" section once `paused`/`closed` |
| **Measurements** (ladder tables, iso-rate, etc.) | `sessions_summary/<file>.md` always — they are session-specific data |
| **Diagnostic sequences** ("do not re-derive") | `sessions_summary/<file>.md` always — they exist only because a past session paid the cost |
| **Gotchas hit for real** | `sessions_summary/<file>.md` always, AND `wiki/concepts/common-pitfalls.md` if reusable beyond the session |
| **Uncommitted work inventory** | `git status` covers this; do not write it down |
| **Harness inventory** (`scratchpad/*.py`) | `sessions_summary/harnesses.md` — cross-cutting |
| **Codebase facts** (firmware quirks, stack sizes, etc.) | `wiki/` concept pages, not Session State |
| **Architectural decisions** | `docs/decisions.md` and `docs/adr/` |

---

## 4. Rot protocol — keeping archives trustworthy

Archives go stale. The radio gets replaced. The protocol version bumps. A bug fix invalidates a measurement. The agent's job is to detect this *when it matters*, not maintain a permanent freshness guarantee.

### Detection — lazy on-read

When an agent opens an archive file, before relying on its contents, it checks:

1. **Date.** How old is the file? If `<Updated>` is more than 30 days ago, the agent reads with extra skepticism and treats the file as evidence of *what was true then*, not *what is true now*.
2. **Drift.** Did the cited files / symbols still exist and still mean what the archive says? Specifically:
   - For each `file:line` citation, verify the symbol exists. `ccc search` or a targeted Read suffices.
   - For each measurement, verify the test/firmware state is reachable. `livewatch read` for runtime facts; `tests/test_<name>.py` for ground-station facts.
3. **Supersession.** Does a newer archive's `Superseded by` chain point at this one? If yes, follow the chain.

### Update — append-only

Drift detection never edits the archive's body. Append a `## Drift` section to the bottom with:

- Date of detection.
- What was checked.
- What drifted.
- Verdict: `conclusion still valid` OR `conclusion invalidated, see <newer file>`.

The original measurements stay. They are evidence of *what was true then*. Deleting them would lose the diagnostic value.

### When to write a `Superseded` note

A new session invalidates the *finding* (not just the data freshness) when:

- Hardware changed in a way that changes the answer (radio swap, sensor swap).
- A protocol or wire contract changed.
- A constraint was deliberately lifted (e.g. "EKF stays in shadow mode" → "EKF now wired to position loop").

Mechanical drift (the file moved, the function was renamed, the test now lives elsewhere) does NOT supersede the finding. It only needs the `Drift` section.

### What the agent does NOT do

- Re-validate every archive on cold start. Too expensive, and the cold-start path doesn't read them anyway.
- Auto-delete archives older than N days. Disk is cheap; history is what makes the system debuggable.
- Update archives it isn't currently relying on. The rot protocol triggers on *open*, not on *tick*.

---

## 5. How a fresh agent uses this policy

A fresh agent in a fresh session reads, in order:

1. `CLAUDE.md` — Session State. Gets the active goal and pointer to the current archive.
2. `sessions_summary/README.md` — confirms the convention.
3. **If and only if** the active goal touches the current archive's topic, read the archive.

That is the whole cold-start contract. Everything else is on-demand.

A fresh agent that finds itself needing an older archive (closed-session question) opens it, applies the rot protocol, and either trusts the data or follows the supersession chain.

---

## 6. Worked example — applying this in practice

Suppose today's `CLAUDE.md` Session State points at `sessions_summary/2026-08-09-micoair-summary.md` and that file documents the MicoAir WiFi Link TX ring rework (status: `active`, because the in-flight re-measure is still pending).

**Scenario A — operator flies the drone and the re-measure passes.**

- Status transition: `active` → `closed`.
- Move: the next agent edits `CLAUDE.md` to compress the Session State to a one-line pointer + outcome. The full detail already lives in `sessions_summary/2026-08-09-micoair-summary.md` — no file move needed; just the status flip in the file's front-matter.

**Scenario B — operator decides to swap the radio module.**

- The hardware-change event invalidates the MicoAir measurements but not the methodology (the iso-rate ladder technique still applies to the new radio).
- The new session's archive supersedes `2026-08-09-micoair-summary.md` for the *measurements* but cites it for the *technique*.
- The original file gets a `## Supersession note` section at the top naming the new file. Original measurements stay.

**Scenario C — two weeks pass with no flight.**

- Trigger B fires. Agent compresses the Session State to `paused` status, names the blocker as "in-flight re-measure pending", names the trigger as "next bench session with the drone airborne".
- The full detail stays in the archive; `CLAUDE.md` no longer carries it.

---

## 7. What this policy does NOT cover

- **Task-driven work** (`.agent_contracts/<TASK_ID>/`). That has its own journal and spec; the dispatcher's `ROADMAP.md` is the source of truth for state. The archive here is for *sessions*, not *tasks*.
- **Wiki concept pages**. Those have their own lifecycle (drop in `raw/`, run `/wiki ingest`). Different scale, different rules.
- **Decision records** (`docs/decisions.md`, `docs/adr/`). Those are append-only by definition; nothing in this policy supersedes them.

Cite this file when the question comes up. Do not re-derive it.