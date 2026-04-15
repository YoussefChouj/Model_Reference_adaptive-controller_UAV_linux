---
title: Architectural Decisions
type: source
tags: [decisions, architecture]
created: 2026-04-13
updated: 2026-04-14
sources: [docs/decisions.md]
---

Full digest of `docs/decisions.md` — the project's architectural decision log. Each decision includes the problem, alternatives considered, the chosen approach, rationale, affected files, and constraints created.

---

## Decision 1: Multi-rate FreeRTOS Task Partitioning

**Date**: 2026-04-12

**Problem**: The firmware must run sensing, control, autonomy, and telemetry at different cadences without starving critical loops.

**Options considered**:
- Single super-loop (cooperative, no RTOS)
- Interrupt-heavy design (most logic in ISRs)
- Dedicated periodic RTOS tasks (`vTaskDelayUntil`)

**Chosen**: Dedicated FreeRTOS tasks with fixed periods using `vTaskDelayUntil`.

| Task | Period | Function |
|:---|:---|:---|
| IMUSample | 1 ms (1 kHz) | `IMUSample_Task` — raw sensor read |
| IMU_DataDeal | 1 ms (1 kHz) | `IMU_DataDeal_Task` — Mahony fusion |
| Stabilizer | 5 ms (200 Hz) | `Stabilizer_Task` — PID + MRAC control |
| Autofly | 5 ms (200 Hz) | `Autofly_Task` — autonomous setpoints |
| Remoter | 10 ms (100 Hz) | `Remoter_Task` — RC input / SBUS loss |
| Send | 10 ms (100 Hz) | `Send_Task` — telemetry TX + command RX |
| SystemMonitor | 1000 ms (1 Hz) | `SystemMonitor_Task` — health check |

**Rationale**: Predictable loop timing and separation of responsibilities reduce coupling between fast control logic and slower communication paths. `vTaskDelayUntil` absorbs computation jitter to maintain fixed `dt` assumptions in the Mahony filter and MRAC controller.

**Files affected**: `USER/main.c`, `TASK/StabilizerTask.c`, `TASK/AutoflyTask.c`, `TASK/send_data.c`, `API/imu_update.c`

**Constraints created**:
- Task period constants and function-level `dt` assumptions must remain aligned: 1 ms IMU update must match `dt = 1e-3f` in `IMU_Update_Mahony()` (`USER/main.c:150`); 5 ms stabilizer must match `MRAC_DT = 0.005f` (`API/mrac.h:194`) and `const float dt = 0.005f` in path integrators (`TASK/AutoflyTask.c:31,59`)
- Changing any task period requires updating **all** dependent `dt` constants — see [[Control Loop Timing]]

**See also**: [[Multi-rate Task Partitioning]], [[FreeRTOS Primitives Used]]

---

## Decision 2: Lightweight Ground-Station Binary Protocol with XOR CRC

**Date**: 2026-04-12

**Problem**: Ground-station communication needs low overhead and simple parser logic on STM32.

**Options considered**:
- Text protocol (CSV/JSON) — easy to debug but high parsing cost on MCU
- Framed protocol with heavy CRC (CRC16/CRC32) — robust but computationally expensive
- Fixed sync bytes + compact binary payload + XOR checksum

**Chosen**: Sync-framed binary messages with XOR checksum.

**Frame structures**:

*Command frame (GS → Firmware)*:
```
[0xCC][0xDD][CMD_ID:u8][INDEX:u8][VALUE:f32 LE][CRC_XOR:u8]
```
CRC = XOR of bytes 2..7.

*Telemetry frame (Firmware → GS)*:
```
[0xAA][0xBB][frame_type:u8][LEN_hi:u8][LEN_lo:u8][MAX_NUM_BASIS:u8][payload...][CRC_XOR:u8]
```
CRC = XOR over `[frame_type, LEN_hi, LEN_lo, MAX_NUM_BASIS, payload...]`.

**Rationale**: XOR checksum plus fixed-byte framing is cheap on MCU (single loop, no table lookup) and straightforward to validate in both firmware (`TASK/send_data.c`) and Python bridge (`ground_station/comm/serial_bridge.py:122-132`).

**Files affected**: `TASK/send_data.c`, `BSP/usart4.c`, `BSP/usart5.c`, `ground_station/comm/serial_bridge.py`

**Constraints created**:
- Command and telemetry byte layouts and CRC coverage rules must match exactly across firmware and host parser — any field reorder or addition requires synchronized updates on both sides
- Frame A payload is fixed 37 bytes; Frame B payload length is formula-based (`MAX_NUM_BASIS`-dependent)

**See also**: [[Ground-Station Binary Protocol]], [[Ground Station Bridge]]

---

## Decision 3: Virtual RC Gating by SBUS Loss and SDK Mode

**Date**: 2026-04-12

**Problem**: Host commands must not override active physical RC control in normal operation.

**Options considered**:
- Always accept virtual sticks (no physical RC override protection)
- Separate mode with no SBUS dependency (mode switch only)
- Gate virtual sticks by SBUS loss **and** SDK mode

**Chosen**: Accept CMD `0x06` virtual stick writes only when `sbus_lost == 1` AND `DroneStatus.FlyMode == FlyMode_SDK`.

**Exact gate condition** (`TASK/send_data.c:525`):
```c
if (sbus_lost == 1 && DroneStatus.FlyMode == FlyMode_SDK && idx < 4)
```

**Rationale**: Protects against mixed-authority control conflicts. Physical RC is primary authority when available. SDK mode requirement ensures the operator has explicitly chosen software control. The dual condition means a SBUS cable fault alone does not give host full control unless the mode was already SDK.

**Files affected**: `TASK/send_data.c`, `TASK/StabilizerTask.c`, `Global_file/global_declare.h`, `BSP/usart4.c`, `BSP/usart5.c`

**Constraints created**:
- Stick vector ordering `[thr, pit, rol, yaw]` becomes a cross-module contract (`TASK/StabilizerTask.c:29`)
- Neutral stick value `3000.0f` used in all `eff_*_ch_valid()` checks (`TASK/StabilizerTask.c:49,56,63,70`)
- SBUS loss timeout = 500 ms (`TASK/RemoterTask.c:43-52`)

**See also**: [[Virtual RC Authority]], [[SDK Arming State Machine]]

---

## Decision 4: Single Active Path Arbitration

**Date**: 2026-04-12

**Problem**: Multiple path generators (TWC waypoint, sinusoid, circle) can conflict if enabled simultaneously, producing contradictory setpoints.

**Options considered**:
- Run all path modes concurrently (summed or last-writer-wins setpoints)
- Last-writer-wins behavior (no explicit arbitration)
- Explicit arbitration enforcing at most one active path family per cycle

**Chosen**: `AutoflyTask_PathArbitrate()` enforces one active path family at a time with a fixed priority ordering.

**Priority order** (`TASK/AutoflyTask.c:17-26`):
```
sinusoid > circle > TWC
```

**Deactivation on conflict**: when sinusoid is active, circle and TWC are cleared; when circle is active, sinusoid and TWC are cleared.

**Rationale**: Prevents contradictory setpoint writers. Single active path simplifies safety reasoning — any abort command (`CMD 0x0D`, `TASK/send_data.c:655-660`) has a deterministic effect. Priority ordering is not physically meaningful but provides a reproducible tie-break.

**Files affected**: `TASK/AutoflyTask.c`, `TASK/send_data.c`, `Global_file/global_declare.h`

**Constraints created**:
- Path activation flags (`sinusoid_path.active`, `circle_path.active`, `TWC.execute`) must be mutually consistent after every `AutoflyTask_PathArbitrate()` call
- Abort logic (`GroundStation_AbortAllPaths()`) must clear **all** path-active state atomically to be effective
- Priority order is a safety invariant — changing it changes which path "wins" during simultaneous activation

**See also**: [[Path Arbitration]], [[AutoflyTask]], [[Autonomous Path Generation]]
