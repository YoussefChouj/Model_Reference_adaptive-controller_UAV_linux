# UAV pipeline — agents index

Cursor GUI subagents that drive the implement and review legs of the five-leg pipeline. All
five legs can run from inside the Cursor Agents Window now — no Claude Code required.

| Subagent | Model | Read-only | Invocation | Behaviour |
|----------|-------|-----------|------------|-----------|
| `uav-conductor` | `claude-opus-5-high` | no | `/uav-conductor <TASK_ID>` | Orchestrates the full pipeline; delegates to planner + implementer + reviewer |
| `uav-planner` | `claude-opus-5-high` | no | `/uav-planner <TASK_ID>` | `.cursor/skills/planner/SKILL.md` — grilling conversation with the user, then writes spec.md |
| `uav-implementer` | `cursor-grok-4.5-high-fast` | no | `/uav-implementer <TASK_ID>` | `.cursor/skills/implement-spec/SKILL.md` |
| `uav-reviewer` | `gpt-5.6-sol-high` | **yes** | `/uav-reviewer <TASK_ID>` | `.cursor/skills/review-spec/SKILL.md` |

**`uav-conductor`** is the one-stop entry point. Type `/uav-conductor <TASK_ID>` in the
Agents Window and it chains planner → implementer → reviewer → adjudicate automatically via
the Task tool. No manual intervention between legs.

Use the individual subagents directly when you want to run a single leg only — e.g.
`/uav-planner` to think through a design without committing to implement yet, or
`/uav-reviewer` to re-review after a quick fix without re-running implement.

### Parallel mode (opt-in)

When the spec carries a `## Sub-scope manifest` section, the conductor can dispatch **two
implementers in parallel** instead of one serial implementer. The protocol is
`.cursor/skills/parallel-implement/SKILL.md`. Trade-off: ~1.5× speedup on the implementer
leg at the cost of higher review surface. **Firmware specs are serial by default** —
parallel mode is for ground_station / sim / docs specs only.

To opt in, the spec must include the sub-scope manifest. The conductor falls back to serial
automatically if the manifest is missing, if the spec is firmware, or if the scope is < 6
files / < 200 lines.

## Why three different families

The planner (Opus 5 High) and the reviewer (GPT-5.6 Sol High) are both on top-tier thinking
models but different families — independence between spec writing and review. The
implementer (Cursor Grok 4.5 High Fast) is the cheap-and-fast executor, deliberately chosen
to be cheap because that's the token-heavy leg. If all three journal entries show the same
model id, Cursor fell back to a compatible model on this plan — pause and tell the user
before adjudicating, since model-independence has collapsed.

## Why `readonly: true` on the reviewer

`readonly: true` blocks **state-changing** operations (file edits, destructive shell
commands) but **allows** reading files, running read-only commands (`git diff`, `git log`,
`ls`, `grep`), and appending to `.agent_contracts/<TASK_ID>/journal.md`. The journal is the
reviewer's reporting channel — it appends its findings as a markdown block, which is not a
"state change" in the readonly sense. If `readonly: true` were total, the reviewer's skill
file wouldn't work, since appending the journal entry is mandatory there.

## Pipeline sequence

1. **Plan + Spec** — `/uav-planner <TASK_ID>` (Agents Window) or skip if spec.md exists
2. **Implement** — `/uav-implementer <TASK_ID>` (Agents Window)
3. **Review** — `/uav-reviewer <TASK_ID>` (Agents Window, new tab)
4. **Adjudicate** — handled by `/uav-conductor` if you used it; otherwise human reads journal

Or one-shot:

```text
> /uav-conductor <TASK_ID>
```

Shared memory: `.agent_contracts/<TASK_ID>/{spec.md, journal.md}` — append-only.

Full pipeline guide: `.claude/skills/cursor-pipeline/SKILL.md`.
