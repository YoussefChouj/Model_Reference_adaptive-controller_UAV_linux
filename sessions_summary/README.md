# sessions_summary/

Point-in-time archive of past sessions. Each file is a **CLOSED** or **PAUSED** work block — measurements, conclusions, and context that mattered on the day but do not need to be in every fresh agent's cold-start context.

## Lifecycle

`CLAUDE.md` Session State is short. Findings live here. The decision rules are in [`POLICY.md`](POLICY.md); the always-on summary is in [`.cursor/rules/session-lifecycle.mdc`](../.cursor/rules/session-lifecycle.mdc). Read those once; cite, do not restate.

Status taxonomy: `active` (in `CLAUDE.md`) / `paused` / `closed` / `superseded`. Triggers:

- **Status transition** — agent working the session writes the archive in the same turn it compresses `CLAUDE.md`.
- **Staleness cap** — `Last Updated` > 7 days with no commits to referenced files auto-pauses the session on next `CLAUDE.md` touch.

## When to read these files

- The user or another agent asks about a closed session's findings ("what did ticket-10 actually measure?", "what was that attention-mechanism session?").
- A current task is rooted in a closed session ("why was the radio replaced?", "why is `What_lower_limit = 0`?").
- Debugging a regression that touches archived territory.

## When NOT to read these files

- A fresh session is starting with a new goal. The active constraints and pointer to the most recent session live in `CLAUDE.md` Session State — read those first.
- A task is rooted in the **current** session. Read the most recent `sessions_summary/YYYY-MM-DD-*.md` file only if `CLAUDE.md`'s pointer is not enough.

## Rot protocol — when an archive is opened

Before trusting the contents:

1. Check `Updated:` date. > 30 days: read with extra skepticism.
2. Verify cited `file:line` references still resolve (`ccc search` or targeted Read).
3. Follow any `Superseded by` chain in the front-matter.

Drift detected → append a `## Drift` section. Never edit the body.

## Index

| File | Session | Status | Outcome | Supersedes |
|---|---|---|---|---|
| [`2026-07-31-ticket10-radio.md`](2026-07-31-ticket10-radio.md) | Ticket-10 radio capacity | closed | BLE module max clean = 4170 B/s, packet-SIZE limited. | (replaced by MicoAir) |
| [`2026-08-02-teaching.md`](2026-08-02-teaching.md) | `/grilling` attention-mechanism teaching | closed | Wiki concepts written. 2 open `mrac.c` defects surfaced. | nothing |
| [`2026-08-09-micoair-summary.md`](2026-08-09-micoair-summary.md) | MicoAir WiFi Link + TX ring rework | **active** (in `CLAUDE.md`) | 90363 B/s = 98.8 % of UART wire, 0.00 % loss. Bandwidth problem closed. | ticket-10 BLE capacity |
| [`operator-decisions.md`](operator-decisions.md) | (cross-cutting) | active | Operator decisions: in-flight re-measure, architecture choices, bench setup. | n/a |
| [`harnesses.md`](harnesses.md) | (cross-cutting) | active | Inventory of `scratchpad/*.py` measurement scripts. | n/a |
| [`POLICY.md`](POLICY.md) | (cross-cutting) | n/a | Lifecycle decision rules. | n/a |

## Naming convention

`YYYY-MM-DD-<short-topic>.md`. Date is the **session's** date (UTC+8), not the file's write date. Topic is hyphenated, lowercase, descriptive enough that an agent scanning the directory can pick the right file without opening each.

If a session is reopened later, append `-v2` / `-v3` rather than overwriting the original — version history of a session's conclusions is itself useful.

## Front-matter each archive carries

```markdown
---
session: YYYY-MM-DD-<topic>
status: active | paused | closed | superseded
updated: YYYY-MM-DD
superseded_by: <file or null>
supersedes: <file or null>
---
```

The `Status:` line in `CLAUDE.md` Session State and the `status:` front-matter in the archive must agree. If they disagree, the archive's front-matter wins — it is closer to the data.

## What does NOT go here

- **Active constraints** — those live in `CLAUDE.md` Session State (the load-bearing rules).
- **Hard architectural decisions** — `docs/decisions.md` and `docs/adr/`.
- **Codebase facts** — `wiki/` concepts and `GRAPH_REPORT.md`.
- **Open tasks** — `.agent_contracts/ROADMAP.md`.
- **Per-task journals** — `.agent_contracts/<TASK_ID>/journal.md`.

If something is **still relevant to current work**, it belongs in one of those places, not here.