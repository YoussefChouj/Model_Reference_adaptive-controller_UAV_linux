---
title: Architectural Decisions
type: source
tags: [decisions, architecture]
created: 2026-04-13
updated: 2026-04-13
sources: [raw/notes/decisions.md]
---

Summary of docs/decisions.md — the project's architectural decision log.

## Decisions Covered

1. **Multi-rate FreeRTOS Task Partitioning** — Dedicated tasks with fixed periods (1kHz IMU, 200Hz control, 100Hz comms, 1Hz monitor). See [[Multi-rate Task Partitioning]].

2. **Lightweight Binary Protocol** — Sync-framed binary messages with XOR checksum for ground station communication. See [[Ground-Station Binary Protocol]].

3. **Virtual RC Gating** — CMD 0x06 virtual sticks only accepted when `sbus_lost == 1` and `FlyMode == FlyMode_SDK`. See [[Virtual RC Authority]].

4. **Single Active Path Arbitration** — `AutoflyTask_PathArbitrate` enforces one active path family at a time. See [[Path Arbitration]].
