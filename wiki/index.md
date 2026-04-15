# Knowledge Base Index

## Start Here

- [Agent & Developer Quick-Start Guide](quickstart.md) — First page for any new agent or developer
- [Project Overview](overview.md) — Architecture, task map, file map, subsystem guide

## Concepts

### Control & Estimation
- [Control Loop Timing](concepts/control-loop-timing.md) — dt/period coupling across IMU, control, and paths
- [MRAC Control Law](concepts/mrac-control-law.md) — Adaptive law structure, projection, and telemetry exposure
- [Coordinate Conventions](concepts/coordinate-conventions.md) — Sign conventions for motors, sticks, world frame, body frame
- [Adaptive Control Simulations](concepts/adaptive-control-simulations.md) — User-validated simulation notebook map and reuse workflow
- [Adaptive Simulation Theory-to-Code Deep Dive](concepts/adaptive-simulation-theory-to-code-deep-dive.md) — Equations, implementation pipeline, and debugging/tuning logic

### Safety & Authority
- [Virtual RC Authority](concepts/virtual-rc-authority.md) — SBUS-loss + SDK gating for host sticks
- [SDK Arming State Machine](concepts/sdk-arming-state-machine.md) — Arm/disarm transitions and mode guards
- [Path Arbitration](concepts/path-arbitration.md) — Single-active path invariant for TWC/sinusoid/circle

### Scheduling & Hardware
- [Multi-rate Task Partitioning](concepts/multi-rate-task-partitioning.md) — FreeRTOS task scheduling and shared-memory timing contracts
- [UART Peripheral Map](concepts/uart-peripheral-map.md) — All 6 UARTs: purpose, pins, baud, DMA, ISR
- [Interrupt Map](concepts/interrupt-map.md) — ISR dispatch table and data flow from interrupt to task context

### Communication
- [Ground-Station Binary Protocol](concepts/ground-station-binary-protocol.md) — Firmware/host binary frame format with XOR CRC
- [Config Reference](concepts/config-reference.md) — config.yaml keys explained
- [Autonomous Path Generation](concepts/autonomous-path-generation.md) — TWC, sinusoid, and circle trajectory generation

### Workflow & Recipes
- [Tuning Workflow](concepts/tuning-workflow.md) — Step-by-step PID/MRAC tuning via dashboard and VOFA
- [Adding a Command](concepts/adding-a-command.md) — End-to-end recipe for new CMD IDs
- [Common Pitfalls](concepts/common-pitfalls.md) — Troubleshooting guide for frequent issues

## Entities

### Firmware Tasks
- [StabilizerTask](entities/stabilizer-task.md) — 200 Hz PID/MRAC control pipeline and motor hand-off
- [AutoflyTask](entities/autofly-task.md) — 200 Hz autonomous setpoint generation and SDK mission flow
- [RemoterTask](entities/remoter-task.md) — 100 Hz RC input, SBUS loss, arming, fly mode
- [IMU Update](entities/imu-update.md) — 1 kHz Mahony fusion with PI drift correction

### Control & Actuation
- [PID Controller](entities/pid-controller.md) — PID algorithm, anti-windup, yaw wrapping, position rotation
- [Motor Mixer](entities/motor-mixer.md) — Mixer arithmetic to TIM3 CCR outputs
- [Timer & PWM Configuration](entities/timer-pwm-config.md) — TIM3 configuration and ESC output range

### Ground Station
- [Ground Station Bridge](entities/ground-station-bridge.md) — Serial decode/command/VOFA/UDP bridge
- [Dashboard](entities/dashboard.md) — GUI command/monitor orchestration layer
- [FlightLogger](entities/flight-logger.md) — CSV telemetry recording and analysis handoff
- [VOFA Streaming](entities/vofa-streaming.md) — Frame A/B telemetry streaming to VOFA+
- [Ground Station Tooling](entities/ground-station-tooling.md) — Analysis, diagnostics, and simulation scripts

### Data & Infrastructure
- [Data Dictionary](entities/data-dictionary.md) — All shared structs and globals (PIDTypeDef, CtrlerTypeDef, etc.)
- [Flash Memory](entities/flash-memory.md) — Current persistence status and flash integration gap

## Theory (External Knowledge → Code Mapping)

- [Mahony Filter Theory](theory/mahony-filter.md) — SO(3) complementary filter math → `imu_update.c` variables
- [MRAC Theory](theory/mrac-theory.md) — Adaptive control law, projection, basis functions → `mrac.h` / `mrac_math.c`
- [Cascaded PID Theory](theory/cascaded-pid.md) — 4-level cascade design rules, tuning order, anti-windup rationale
- [Yucelen Lectures Digest](theory/yucelen-lectures.md) — Key videos from "Lectures on Adaptive Control and Learning" with code cross-references

## Reference (Used-Subset Hardware/RTOS Docs)

- [STM32F4 Peripherals](reference/stm32f4-peripherals.md) — Only-used peripherals from RM0090: TIM3/TIM5, USART+DMA, SPI, NVIC
- [FreeRTOS Primitives Used](reference/freertos-used.md) — xTaskCreate, vTaskDelayUntil, critical sections — and what is deliberately NOT used

## Sources

- [Architectural Decisions](sources/architectural-decisions.md) — docs/decisions.md (2026-04-13)
- [Cross-Subsystem Interfaces](sources/cross-subsystem-interfaces.md) — docs/interfaces.md (2026-04-13)
- [Direct MRAC + FF + Projection Notebook](sources/direct-mrac-ff-projection-simulation-notebook.md) — External simulation notebook digest (2026-04-14)
- [Adaptive Control Tutorial Notebook](sources/adaptive-control-tutorial-notebook.md) — Progressive adaptive-control experiments (2026-04-14)
- [Adaptive Control Tutorial 2 Notebook](sources/adaptive-control-tutorial-2-notebook.md) — Beginner-to-derivative-free simulation set (2026-04-14)
