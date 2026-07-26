---
name: parallel-implement
description: >
  UAV-pipeline parallel-implementer orchestration. Use when the conductor wants to split a
  single TASK_ID's spec into 2–N disjoint sub-scopes and dispatch one implementer per
  sub-scope in parallel, then serial-merge and review. Trades coherence risk for speed on
  the token-heavy implementer leg. Read by `uav-conductor` when the spec carries a
  `## Sub-scope manifest` section.
---

# Parallel-implementer protocol

You are the **uav-conductor** invoking the parallel-implementer protocol for one `TASK_ID`.
The implementer is the token-heavy leg of the pipeline; parallelising it shortens wall time
at the cost of more review surface and a higher chance of subtle contract conflicts.

The protocol is **opt-in**. The spec must carry a `## Sub-scope manifest` section naming the
sub-scopes; the conductor reads it. If the manifest is missing, the conductor falls back to
serial implementer (one sub-scope, the whole spec).

## When to use parallel mode

Use it when ALL of the following are true:

- The spec's `## Scope` lists ≥ 6 files OR the implementer's expected diff is ≥ 200 lines.
- The files split cleanly into disjoint subsets that don't reference each other's internals.
  Two implementers editing the same file is the failure mode this protocol does NOT handle.
- The cost of coherence risk (a missed cross-file contract) is bounded — i.e. the test
  suite catches the missed contract, not the reviewer alone.

Do NOT use it when:

- The spec is < 200 lines OR the scope is < 6 files — serial is faster end-to-end.
- The spec mandates a single-coherent change (e.g. one transport protocol that touches
  header + impl + tests cohesively). Splitting it forces one sub-scope to take the contract
  and another to depend on it — race condition.
- The repo is firmware (CURRENT SAFETY RULE). For firmware specs, the implementer must
  hold the whole change in one head. The risk of two implementers both editing
  `TASK/StabilizerTask.c` is not worth the speedup. **Default: serial for firmware.**

## Sub-scope manifest — the spec's contract

The planner writes a `## Sub-scope manifest` section in `spec.md` with this shape:

```markdown
## Sub-scope manifest

| Sub-scope | Owner files (may write) | Reads (no write) | Forbidden |
|-----------|--------------------------|------------------|-----------|
| `core`    | `transport.py`, `reader.py` | `manifest.py` | `cli.py`, `dashboard.py`, `tests/*` |
| `glue`    | `cli.py`, `dashboard.py` | `transport.py`, `reader.py` | `tests/*` |
| `tests`   | `tests/test_*.py` | all of the above | none |
```

The rules:

- **Owner files** are the only files this sub-scope's implementer may modify.
- **Reads** are files the implementer may read for context but must not edit.
- **Forbidden** are files the implementer must not even read (rare; usually the implementer
  can read everything but the planner can forbid specific files that would tempt scope creep).
- Each file in `## Scope` appears in **exactly one** sub-scope's owner column. The planner
  must NOT assign the same file to two sub-scopes.
- "Tests" is normally a separate sub-scope that runs **after** the others (see protocol).

## The protocol (conductor's marching orders)

```text
1. Plan + Spec     ← uav-planner            (single sub-scope manifest produced; same as serial)
2. Implement       ← N parallel implementers:
                     - core       (1 Task call)   — writes owner files; does NOT run tests
                     - glue       (1 Task call)   — writes owner files; does NOT run tests
                     - tests      (deferred to phase 2) — see step 3
3. Test implementer ← 1 implementer (1 Task call) — runs AFTER core and glue complete;
                      writes tests for the unioned diff; does NOT run tests
4. Conductor runs the full test suite ONCE (this is the only test run during parallel mode)
5. Review          ← uav-reviewer (single call) — reads the unioned diff
6. Adjudicate      ← conductor (you, in-line)
```

The two implementers in phase 2 are dispatched in **separate `Task` tool calls in the
same single message** — the `Task` tool runs subagents in parallel when the calls are
in the same message. Do NOT wait for one implementer to finish before dispatching the other.

## What to tell each parallel implementer

Each implementer's prompt must include:

```
You are the implementer for ONE sub-scope of TASK_ID=<id>. The whole spec lives at
.agent_contracts/<TASK_ID>/spec.md. The sub-scope manifest gives you:

  Owner files (you may write):
    - <file1>
    - <file2>
  Reads (you may read but MUST NOT write):
    - <file3>
    - <file4>

Hard rules specific to parallel mode:
  - DO NOT run tests. The conductor runs the suite once after all parallel implementers
    and the test implementer finish. Running tests now is wasted work AND may return
    false failures because the other sub-scope's writes haven't landed yet.
  - DO NOT write files outside your owner column. The other implementer is writing those
    concurrently; if you touch them, the LAST writer wins and the first writer's work
    is silently lost.
  - DO NOT make assumptions about the other sub-scope's behaviour beyond what the spec
    says. If the spec is ambiguous about how your sub-scope interacts with theirs, STOP
    and surface it in your journal entry as an "Open question for the conductor" — DO
    NOT pick a reading silently.
  - DO append a normal journal entry when done, naming the SUB-SCOPE in the header
    (e.g. "## [implementer-core] model-id — date"). The test implementer will append
    "## [implementer-tests] model-id — date" after they finish.
```

## What to tell the test implementer (phase 2)

The test implementer is dispatched AFTER both parallel implementers return. Their prompt:

```
You are the test implementer for TASK_ID=<id>. The two parallel implementers
(core, glue) have finished. Their work lives in:
  - <sub-scope A files>
  - <sub-scope B files>

Your owner files (you may write):
  - <test file 1>
  - <test file 2>

Hard rules:
  - You may read the parallel implementers' journal entries to learn what they
    implemented and how to test it.
  - DO NOT run tests. The conductor runs the suite once.
  - DO NOT modify non-test files. The behaviour is set; you only verify it.
  - DO append a journal entry when done, naming the SUB-SCOPE in the header
    (e.g. "## [implementer-tests] model-id — date").
```

## Serial merge discipline

The parallel-implementers write to disjoint file sets, so the merge is trivially the union
of their writes. The conductor:

1. **Tag the writes**: each implementer names the files they wrote in their journal entry.
   The conductor uses that to confirm the disjoint-set property held.
2. **Confirm no overlap**: if two implementers' journal entries both name the same file,
   the conductor STOPS. The second writer's journal entry wins; the first writer's work
   is lost. The conductor re-dispatches the lost implementer with: "Your previous work
   was overwritten by sub-scope X. Re-implement against the current state of the tree."
   This is a coherence miss; the planner should be flagged for the next time.
3. **Run the test suite ONCE**: `pytest -q <test paths from spec>` in the conductor's
   shell. The pre-condition is that the unioned diff is what the test implementer wrote
   against.
4. **If tests fail**, the conductor decides: was it a logic bug in core/glue (dispatch a
   repair implementer with the failure output), or a test that doesn't yet match the
   implementation (dispatch a test-implementer repair with the failure output)?

## Reviewer dispatch

The reviewer gets one prompt that:

- Reads the spec, the journal (all four entries: planner, core, glue, tests), and the
  unioned diff.
- Verifies the disjoint-set property held (no file edits from two sub-scopes).
- Reviews the unioned diff as a single coherent change, with extra attention to the
  seams between sub-scopes (the "Reads" files — did the core implementer make
  assumptions that the glue implementer doesn't honour?).

The reviewer does NOT need to know about parallelism. It reviews the unioned diff.

## Failure modes the protocol does NOT handle

- **Two implementers both editing the same file**: the protocol forbids this; if it
  happens, the second writer wins and the first writer's work is lost. The conductor
  detects this via the journal-tagged-writes check and re-dispatches the loser. This is
  a coherence miss; warn the user.
- **Implementer running tests in parallel mode**: forbidden in the prompt. If the
  implementer does it anyway, the conductor discards the test results (the test is
  running against a partial world) and re-runs the suite after the merge.
- **A sub-scope's work depends on a sibling sub-scope's internals** (not its interface):
  parallel mode cannot handle this. The planner must split by **interface**, not
  **implementation**, so each sub-scope reads the others' interfaces but writes only
  its own internals. If the planner can't find a clean split, fall back to serial
  implementer.

## When to fall back to serial

If any of the following is true, the conductor falls back to serial implementer
(one sub-scope, the whole spec):

- The spec's `## Sub-scope manifest` is missing.
- The spec is for **firmware** (any file under `USER/`, `TASK/`, `BSP/`, `API/`,
  `Global_file/`, `HARDWARE/`).
- The spec's `## Scope` is < 6 files OR the expected diff is < 200 lines.
- The sub-scope manifest assigns the same file to two sub-scopes.
- The user explicitly says "serial" or "no parallel".

The conductor's report says which path was taken and why.

## Surface to the user

At the end of the parallel run, the conductor reports:

- Which sub-scopes were dispatched.
- The model id of each sub-scope's journal entry (per the AGENTS.md "model collapse"
  rule, if all three + the reviewer are the same model family, flag it).
- The merge status (clean / overlap detected / overlap repaired).
- The test result (count, time).
- The reviewer's verdict.
- The wall time saved vs. serial (a rough estimate; useful for tuning the threshold).
