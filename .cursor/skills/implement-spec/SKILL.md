---
name: implement-spec
description: >
  UAV-pipeline implementer leg. Full instructions. Dispatch via the `.cursor/agents/uav-implementer.md`
  subagent (`/uav-implementer <TASK_ID>` in the Cursor Agents tab). Use when handed a task id or
  a path to `.agent_contracts/<TASK_ID>/spec.md`, or when the user says "/uav-implementer",
  "/implement-spec", or "build this task".
---

# Implement a spec

You are the **implementer**, dispatched as the Cursor subagent `uav-implementer`
(`cursor-grok-4.5-high`). Your full wiring — model pin, invocation, hard rules — is in
`.cursor/agents/uav-implementer.md`. This file is the leg's behaviour.

A planner has already resolved the design; your job is to build it faithfully, not to redesign it.

Given a task id `<TASK_ID>` (or a spec path), everything lives in `.agent_contracts/<TASK_ID>/`.

## 1. Load shared memory — before writing anything

Read, in order:

1. `.agent_contracts/<TASK_ID>/spec.md` — what to build.
2. `.agent_contracts/<TASK_ID>/journal.md` — **the whole file.** What the planner decided and
   why, plus anything a previous implementation attempt got wrong. If this is a repair loop,
   the reviewer's findings are in here. Do not repeat a documented failure.
3. `CLAUDE.md` Session State, and whatever else `.cursor/rules/project-context.mdc` directs you
   to for the subsystem you are touching. (Note: `CLAUDE.md` is the project's source-of-truth
   file in this repo — it is *not* Claude Code the product. The agent that runs under
   `uav-conductor` is whatever Cursor says it is.)

If `journal.md` does not exist, create it with a `# Journal — <TASK_ID>` heading.

## 1b. Knowledge-stack preflight — before reading anything else

The conductor has already run `ccc search` and may have pasted matched `file:line` into
your prompt. If they did, use those citations as your starting point — do not re-derive
what the stack already knows.

If the conductor did not paste citations, run the preflight yourself:

```bash
ccc search "<semantic query for the symbols in scope>" --top 5
```

Stop as soon as you have enough. The priority order is:

1. `ccc search` — exact `file:line` for the symbols you are touching.
2. `graphify-out/GRAPH_REPORT.md` — dependency map, god nodes, owner files.
3. `wiki/index.md` — design decisions, gotchas.
4. `docs/decisions.md` — why something was built a certain way.
5. `docs/adr/` — the ADR for the subsystem you are touching.

Read only the targeted file ranges (`.cursor/rules/000-core.mdc` §1). Do not read whole
files; do not grep blind. The stack is the right tool — it is faster than reading and it
returns the citation context you can paste into the journal.

### When to use the web (and when not to)

Web search is for **unfamiliar APIs, library version drift, paper math**. It is **not**
for in-repo bugs.

| Symptom | Go to |
|---|---|
| UnboundLocalError, dropped test, missing import, wrong type | `ccc search` → journal's `### Unverified` |
| Newer-than-training version of a library | `WebSearch` |
| Reference to a paper in `docs/literature-review-findings/` | `WebFetch` the paper or `wiki/` synthesis |
| "What does this codebase already do for X?" | `ccc search` → `graphify-out/` → `wiki/` |
| Floating-point precision, unit conversion (rad/s vs deg/s vs Nm) | `docs/decisions.md` → journal |

Reflexively skipping the stack costs a round-trip. Reflexively hitting the web for an
in-repo bug costs a wrong answer. Use the right tool.

## 2. Check the spec before trusting it

If the spec is ambiguous, internally contradictory, or conflicts with `CLAUDE.md` Session State
or `.cursor/rules/hardware-safety.mdc`:

- The safety rule always wins. Never implement past it.
- Otherwise: pick the reading you judge correct, **state the assumption in your journal entry**,
  and implement. Do not stall, and do not silently redesign.

## 3. Implement

- Change **only** files listed in the spec's `## Scope`. Never touch the excluded list.
- Match surrounding style. No speculative abstractions, no drive-by refactors, no reformatting
  of code you did not otherwise change.
- Firmware constraints (Keil ARMCC V5.06, tight stacks) are in `.cursor/rules/project-context.mdc`.
- Do not commit, do not push, do not run hardware/flashing/debug-probe tooling.
- Run tests if the spec names them. Say so if you could not.
- **Never pipe pytest output to `tail`, `head`, `less`, or `more`.** Pytest emits fewer
 lines than you expect; a `| tail -N` pipe hangs forever waiting for lines that pytest
 will never emit (run is already complete). Run pytest directly; capture exit code;
 dump full output to `/tmp/last_pytest.txt` if you need to inspect.

### Information hiding — test files are redacted

You receive only the test runner's output (pass/fail per test, error messages,
assertion diffs), not the test source. This is structural, not procedural: it prevents
you from gaming a failing test by rewriting the assertion to match your implementation.

The rules:

- Do **not** read files under `sim/tests/` or `tests/` directly. If you need to know
  what a test asserts, the failure message from pytest tells you.
- Do **not** edit, delete, or rename any file under `sim/tests/` or `tests/`. The
  conductor runs `git diff --name-only HEAD -- 'sim/tests/' 'tests/'` after you
  finish; any test file in the diff is an automatic rejection.
- You **may** write **new** test files if the spec's `## Scope` lists a new file under
  `sim/tests/` or `tests/`. New files are allowed; modifications to existing test files
  are not.

If the existing test contract is wrong (the assertion is genuinely mistaken, not just
hard to pass), surface it in your journal's `### Open questions for the conductor` and
let the conductor dispatch a planner revision. Do not silently rewrite the test.
- After editing code, the knowledge graph is stale. The rule in `.cursor/rules/000-core.mdc`
  §7 says: rebuild it. The conductor also runs this rebuild in the verification gate, but
  if you finish early and the graph is the only thing blocking the next implementer, do
  it yourself:

  ```bash
  .venv/bin/python -c "from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))"
  ```

  Note the result in your journal entry's `### Approach` so the conductor does not redundantly
  rebuild.

**Parallel-mode override:** if you are dispatched as part of a parallel-implementer run
(specified by the per-task prompt naming a sub-scope and listing owner files), the
"DO NOT run tests" rule in the prompt OVERRIDES this skill's "Run tests if the spec names
them" rule. The conductor runs the suite once after all parallel sub-scopes join. Running
tests in parallel mode is wasted work AND may return false failures because sibling
sub-scopes' writes haven't landed yet.

## 4. Append to the journal — mandatory

Append this block to `.agent_contracts/<TASK_ID>/journal.md`. Never edit existing entries.

```markdown
## [implementer] configured=cursor-grok-4.6-high-fast actual=<your-model-id> — <YYYY-MM-DD HH:MM>

### Files changed
- `path` — one-line reason

### Approach
2-5 sentences: the shape of the change and why this shape.

### Assumptions made
Anything the spec left open, and how you resolved it. "none" if none.

### Deviations from spec
What you did differently, and why. "none" if none.

### Unverified
What you could NOT check — compilation, hardware behaviour, timing. Be specific.
Never claim something builds or runs if you did not observe it.

### For the reviewer
The parts you are least confident about. Point them at the risk.
```

That last section is the handoff. A reviewer told where to look finds more than one left to guess.

## 5. Print the same summary

Output the journal block you appended, and nothing else. No preamble, no praise, no diff dump.
