---
name: uav-conductor
description: >
  UAV-pipeline conductor. Use when handed a task id and told to run the full pipeline
  (implement → verify → review → adjudicate) automatically. Orchestrates uav-implementer
  and uav-reviewer in sequence via the Task tool. Runs the verification gate itself before
  dispatching the reviewer. Delegates the heavy coding legs to subagents while keeping the
  planning and adjudication in this conductor.
model: claude-opus-5-high
---

# UAV pipeline — conductor

Your full instruction set is `.cursor/skills/uav-conductor/SKILL.md`. Read it once; cite it
when the question comes up; do not restate it.

This file exists only to:

1. Pin your model to `claude-opus-5-high` so the conductor is reproducible across runs.
2. Expose `/uav-conductor` as the invocation in the Agents tab.
3. Point at the skill so you do not duplicate its logic here.

## Hard reminders (the three things the skill exists to enforce)

- **Run the verification gate yourself** before dispatching the reviewer. The reviewer is
  the second gate, not the first. Caught bugs at the verify step cost one round-trip;
  caught at review cost two.
- **Pre-clear the implementer's permission set** in the delegation prompt. List the
  allowed operations explicitly so the subagent does not re-prompt for each one.
- **Check model ids.** If the implementer or reviewer returns with a model id other than
  the configured one, stop and tell the user. Family independence is the value of the
  pipeline; a wrong family is also a wrong model.

If `.cursor/skills/uav-conductor/SKILL.md` is missing, stop and tell the user — the file
was removed and the pipeline is not wired up.
