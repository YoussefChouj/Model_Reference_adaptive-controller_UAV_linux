---
name: goal-loop
description: >
  Explain and write effective instructions for the `/goal` feature — the persistent
  self-checking agent loop (plan → act → test → review → iterate) available in
  Claude Code and Cursor agents. Use when the user mentions `/goal`, "goal loop",
  wants to kick off a long-running autonomous run, asks how to write a goal prompt,
  or wants a one-paragraph goal instruction drafted.
---

# Agent `/goal` Loop

## What `/goal` is

`/goal` is a slash command that turns an agent prompt into a **persistent agent** looping
`plan → act → test → review → iterate` until a stop condition is met, the user pauses,
or the token budget runs out.

Key difference from a normal prompt: when a turn ends but the goal isn't met, the agent
**auto-continues** instead of waiting for input.

**Lifecycle states:** `pursuing`, `paused`, `achieved`, `unmet`, `budget-limited`.

**Not:** a budget command, a safety boundary, "run forever", or a replacement for `/plan`.

## Requirements

- An agent with the `/goal` feature — Claude Code and Cursor Agents support it
- The goal must have a **verifiable stop condition**

## The 5-part contract (every goal needs this)

1. **Objective** — one sentence, one concrete outcome.
2. **Read first** — files/PLAN.md/issue the agent should load before starting.
3. **Constraints** — what must NOT change (public API, files, libs, conventions).
4. **Validation command** — the exact shell command that proves progress (`pytest -q`, etc.).
5. **Stop condition** — verifiable: "Stop when X passes" OR "when further changes need human/input."

## Writing a goal (emit only the contract body)

```
**Objective:** <one-sentence objective>
**Read first:** <files/PLAN.md/issue>
**Constraints:** <what not to change, libs, conventions>
**Validate:** `<exact command>` after each change
**Stop when:** <verifiable condition>, OR when further changes require human/product input
```

## Examples

Migration:
```
**Objective:** Migrate this project from Pydantic v1 to v2.
**Read first:** pyproject.toml, src/, tests/
**Constraints:** no public API changes; keep imports backwards-compatible; no new deps
**Validate:** `pytest -q`
**Stop when:** full suite passes with zero deprecation warnings, OR when a change requires architecture decisions
```

Coverage lift:
```
**Objective:** Raise coverage in src/auth/ from ~38% to ≥75%.
**Read first:** src/auth/, tests/auth/, AGENTS.md
**Constraints:** no new deps; mirror existing test style; do not modify production code unless strictly required
**Validate:** `pytest --cov=src/auth --cov-report=term-missing`
**Stop when:** coverage ≥75% AND all tests pass, OR when uncovered code needs design changes
```

## Rules

- **One objective, one stop condition.** Not a backlog.
- **Forbid reward-hacking:** "Do not delete, skip, weaken, or narrow tests to make the goal pass."
- **Forbid scope creep:** "Do not refactor unrelated code. Do not add dependencies."
- **Documentation is mandatory:** every goal must include a single sentence committing to concise, targeted docs.
- Tell the agent when to pause: "If, pause and ask before proceeding."
- Short, vague goals burn tokens. Define "done" precisely.
- **4,000-char limit** on the objective. If longer, put detail in a file and make the goal point to it.

## Meta-prompting trick (highest-leverage)

Ask a second agent session to: (1) inspect the codebase, (2) surface hidden assumptions/constraints,
(3) emit a structured `/goal` block. Paste that into the agent. Order-of-magnitude better runs.

## Controlling a running goal

| Command | Effect |
|---|---|
| `/goal` (alone) | Status: current checkpoint, what's verified, what remains, blockers |
| `/goal pause` | Freeze |
| `/goal resume` | Unfreeze |
| `/goal clear` | Kill the goal |
| `/goal ` | Replace the current goal |

## Mental model

`/goal` is a **contract enforcer with a verification loop**, not a "run forever" button.
The shift: stop writing prompts, start writing **specifications with stop conditions**.
