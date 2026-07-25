# Diagnose

Diagnose a hard bug or regression methodically — do NOT guess-and-patch.

1. Restate the symptom precisely and define what "fixed" looks like (a verifiable signal).
2. Knowledge-stack first: `ccc search` the relevant subsystem, read `graphify-out/GRAPH_REPORT.md` for owners/dependents, check `wiki/` for known gotchas.
3. Form 2–3 concrete hypotheses. Rank them by likelihood. State them to me.
4. For the top hypothesis, identify the **minimal evidence** that would confirm or refute it (a log line, a value, a replay result). Gather that evidence before writing any fix.
5. Only after the root cause is confirmed, propose the smallest fix. Confirm with me before editing.
