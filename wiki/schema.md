---
title: Wiki Schema
type: schema
created: 2026-04-13
updated: 2026-04-13
---

# Wiki Conventions

## Page Types

Standard types from Karpathy Wiki:
- **concept** — Pattern, algorithm, or design principle
- **entity** — Component, module, service, or hardware element
- **source** — Summary of an ingested raw document
- **query** — Filed query result worth keeping
- **overview** — High-level synthesis

## Domain-Specific Entity Types (UAV/Control Systems)

- **controller** — PID, MRAC, LQR, SMC, or other control law
- **sensor** — IMU, barometer, GPS, optical flow
- **actuator** — Motor, servo, ESC
- **parameter** — Tunable constant with units (gains, limits, thresholds)
- **protocol** — UART, SPI, I2C, telemetry frame format
- **algorithm** — Named algorithm with complexity/tradeoffs

## Domain-Specific Relation Types

- **tunes** — A parameter tunes a controller
- **reads_from** — A module reads from a sensor or buffer
- **writes_to** — A module writes to an actuator or output
- **safety_critical_for** — A constraint is safety-critical for a component
- **must_match** — Two components must have matching layouts/formats

## Frontmatter Template

```yaml
---
title: Page Title
type: concept | entity | source | query | overview | controller | sensor | actuator | parameter | protocol | algorithm
tags: [tag1, tag2]
created: YYYY-MM-DD
updated: YYYY-MM-DD
sources: [raw/filename.md]
related_files: [src/path/file.c]
relations:
  - type: tunes | reads_from | writes_to | safety_critical_for | must_match
    target: "[[Target Page]]"
---
```

## Cross-References

Use `[[wikilinks]]` for page references. Use `file:line` for source code references.

## Knowledge Stack Query Priority

```
1. ccc search → exact code locations ("where is X?")
2. GRAPH_REPORT.md → system dependencies ("what depends on X?")
3. wiki/ → conceptual understanding ("why was X designed this way?")
4. docs/decisions.md → architectural choices ("what was decided about X?")
5. docs/interfaces.md → cross-subsystem contracts
6. .agent_memory/lessons.jsonl → past task learnings
```

If a wiki query doesn't have the answer, fall back to ccc search and GRAPH_REPORT.md.
