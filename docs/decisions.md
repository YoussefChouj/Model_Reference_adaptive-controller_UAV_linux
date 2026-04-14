# Architectural Decisions

## 2026-04-12: Multi-rate FreeRTOS Task Partitioning
- **Problem:** The firmware must run sensing, control, autonomy, and telemetry at different cadences without starving critical loops.
- **Options considered:** Single super-loop; interrupt-heavy design; dedicated periodic RTOS tasks.
- **Chosen:** Dedicated FreeRTOS tasks with fixed periods using `vTaskDelayUntil` (1000 Hz IMU sample/update, 200 Hz stabilizer/autofly, 100 Hz remoter/send, 1 Hz monitor).
- **Rationale:** Predictable loop timing and separation of responsibilities reduce coupling between fast control logic and slower communication paths. [VERIFY]
- **Files affected:** `USER/main.c`, `TASK/StabilizerTask.c`, `TASK/AutoflyTask.c`, `TASK/send_data.c`, `API/imu_update.c`.
- **Constraints created:** Task period constants and function-level `dt` assumptions must remain aligned (for example, 1 ms IMU update and 5 ms autopilot path integration).

## 2026-04-12: Lightweight Ground-Station Binary Protocol with XOR CRC
- **Problem:** Ground-station communication needs low overhead and simple parser logic on STM32.
- **Options considered:** Text protocol (CSV/JSON), framed protocol with heavy CRC, fixed sync + compact binary payload.
- **Chosen:** Sync-framed binary messages with XOR checksum.
- **Rationale:** XOR checksum plus fixed-byte framing is cheap on MCU and straightforward to validate in both firmware and Python bridge.
- **Files affected:** `TASK/send_data.c`, `BSP/usart4.c`, `BSP/usart5.c`, `ground_station/comm/serial_bridge.py`.
- **Constraints created:** Command and telemetry byte layouts and CRC coverage rules must match exactly across firmware and host parser.

## 2026-04-12: Virtual RC Gating by SBUS Loss and SDK Mode
- **Problem:** Host commands must not override active physical RC control in normal operation.
- **Options considered:** Always accept virtual sticks; separate mode with no SBUS dependency; gate virtual sticks by SBUS loss and SDK mode.
- **Chosen:** Accept CMD `0x06` virtual stick writes only when `sbus_lost == 1` and `FlyMode == FlyMode_SDK`.
- **Rationale:** Protects against mixed-authority control conflicts and keeps physical RC as primary authority when available. [VERIFY]
- **Files affected:** `TASK/send_data.c`, `TASK/StabilizerTask.c`, `Global_file/global_declare.h`, `BSP/usart4.c`, `BSP/usart5.c`.
- **Constraints created:** Stick vector ordering (`[thr, pit, rol, yaw]`) and neutral value (`3000`) become cross-module contracts.

## 2026-04-12: Single Active Path Arbitration
- **Problem:** Multiple path generators (TWC, sinusoid, circle) can conflict if enabled simultaneously.
- **Options considered:** Run all path modes concurrently; last-writer-wins behavior; explicit arbitration to keep one active mode.
- **Chosen:** `AutoflyTask_PathArbitrate` enforces one active path family at a time.
- **Rationale:** Prevents contradictory setpoint writers and simplifies safety reasoning for autonomous behavior.
- **Files affected:** `TASK/AutoflyTask.c`, `TASK/send_data.c`, `Global_file/global_declare.h`.
- **Constraints created:** Path activation flags must be mutually consistent, and abort logic must clear all path-active state.