---
title: Cross-Subsystem Interfaces
type: source
tags: [interfaces, contracts, protocols]
created: 2026-04-13
updated: 2026-04-13
sources: [raw/notes/interfaces.md]
---

Summary of docs/interfaces.md — defines the cross-subsystem contracts.

## Interfaces Covered

1. **IF-01: Command Frame** — Ground station to firmware (0xCC 0xDD). See [[Ground-Station Binary Protocol]].
2. **IF-02: Telemetry Frame** — Firmware to ground station (0xAA 0xBB). See [[Ground-Station Binary Protocol]].
3. **IF-03: Command Queue** — `GS_Cmd_t` ring buffer (depth 8, shared by UART4+UART5). See [[Ground Station Bridge]].
4. **IF-04: Motor Mapping** — `Compute_Motor` to TIM3 CCR registers. See [[Motor Mixer]].
5. **IF-05: Path Control State** — Shared path structs between send_data and AutoflyTask. See [[Path Arbitration]].
6. **IF-06: Timing Contract** — Task periods must match dt constants. See [[Control Loop Timing]].
