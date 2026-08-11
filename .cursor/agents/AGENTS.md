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
Agents Window and it chains planner → implementer → verify → review → adjudicate
automatically via the Task tool. No manual intervention between legs. Full instructions
are in `.cursor/skills/uav-conductor/SKILL.md`.

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

**Wrong family is also a failure.** If the implementer returns as anything other than
`cursor-grok-4.5-high-fast`, or the reviewer returns as anything other than `gpt-5.6-sol-high`,
the conductor stops and tells the user. The conductor runs the verification gate in
parallel — it can catch the bug before the reviewer is even called. The user decides
whether to re-dispatch with the correct model or accept the substitution.

### Journal entry convention — `configured_model` + `actual_model`

Every journal entry header now carries two model ids. The first is what the conductor
configured for that leg (from `.cursor/agents/<name>.md` frontmatter). The second is what
Cursor actually dispatched. They should match; if they don't, the entry is the audit
trail of a fallback.

```markdown
## [implementer] configured=cursor-grok-4.5-high-fast actual=cursor-grok-4.5-high-fast — 2026-08-12 10:30
## [reviewer]    configured=gpt-5.6-sol-high          actual=gpt-5.6-sol-high          — 2026-08-12 10:45
```

**Why both fields:** Cursor can override the configured model via the Task tool's `model`
parameter, or fall back to a compatible model if the configured one is blocked. The
override is silent; the audit needs both sides of the contract.

The conductor's adjudication step (leg 5) runs an automated check: for every journal
entry, `actual_model` must match `configured_model`. If not, the conductor surfaces the
mismatch to the user before writing the verdict. The user can re-dispatch with the
correct model, or explicitly accept the substitution with a one-line note in the
adjudication entry.

### The hard rule that backs this

`.cursor/rules/subagent-model-pinning.mdc` is the always-on rule that enforces the
configured-model discipline at dispatch time. The rule covers the built-in `explore`,
`bash`, and `browser` subagents too — they get their configured model by default and the
orchestrator must not silently override.

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
3. **Verify** — conductor runs the test suite + graph rebuild (NOT delegated)
4. **Review** — `/uav-reviewer <TASK_ID>` (Agents Window, new tab)
5. **Adjudicate** — conductor reads the journal and writes the verdict
6. **Digest** — main agent writes `sessions_summary/YYYY-MM-DD-digest.md` on completion
7. **Validate** — operator reviews the digest; decides next goal or next session

The digest is the handoff between implementation and operator review. See `sessions_summary/POLICY.md` §Digest protocol for template and meaning of `operator_review` field.

Or one-shot:

```text
> /uav-conductor <TASK_ID>
```

Shared memory: `.agent_contracts/<TASK_ID>/{spec.md, journal.md}` — append-only.

Full pipeline guide: `.claude/skills/cursor-pipeline/SKILL.md`.
