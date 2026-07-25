---
name: cursor-pipeline
description: >
  Four-leg model-routing workflow running entirely inside Cursor Agents. Use when the user says
  "run the pipeline", "cursor pipeline", "implement via uav-implementer", or hands over a spec to
  be built. The four subagents (uav-conductor, uav-planner, uav-implementer, uav-reviewer) are
  registered globally in ~/.cursor/agents/ and ~/.cursor/skills/. See those files for authoritative
  wiring.
---

# Cursor Pipeline — reference (local project)

This file is the **local project reference copy**. The authoritative files live in:

- Agents: `~/.cursor/agents/` — all four subagent `.md` files
- Skills: `~/.cursor/skills/` — `implement-spec/SKILL.md`, `review-spec/SKILL.md`,
  `cursor-pipeline/SKILL.md`

This local copy exists so Claude Code (if still used as a secondary orchestrator) and other
project-level tools can reference the pipeline without requiring global access.

## Quick reference

| Leg | Subagent | Model | Read-only |
|-----|----------|-------|-----------|
| Plan + Spec | `uav-planner` | `claude-opus-5-high` | no |
| Implement | `uav-implementer` | `cursor-grok-4.5-high` | no |
| Review | `uav-reviewer` | `gpt-5.6-sol-high` | **yes** |
| Adjudicate | `uav-conductor` | `claude-opus-5-high` | no |

**One-shot:** `/uav-conductor <TASK_ID>` in the Cursor Agents Window.

For full details (preconditions, hard rules, safety, known blockers), read the authoritative
global skill at `~/.cursor/skills/cursor-pipeline/SKILL.md`.

## Task memory

Tasks live in `.agent_contracts/<TASK_ID>/`:

| File | Written by | Read by |
|------|------------|---------|
| `spec.md` | planner (`uav-planner`) | implementer, reviewer |
| `journal.md` | all roles, **append-only** | all roles |
