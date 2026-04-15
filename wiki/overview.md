---
title: Project Overview
type: overview
tags: [uav, freertos, stm32, mrac, pid, architecture]
created: 2026-04-13
updated: 2026-04-14
---

# 6-DOF Quadcopter Flight Controller

This is a FreeRTOS-based flight controller for a quadcopter built on STM32F4, with PID attitude control augmented by a 4-axis MRAC (Model Reference Adaptive Control) layer. A Python ground station communicates over UART using a custom binary protocol, with real-time visualization through VOFA+.

## System Architecture

```
┌─────────────────────────────────────────────────┐
│                    STM32F4 MCU                   │
│                                                  │
│  ┌──────────┐  ┌──────────────┐  ┌───────────┐  │
│  │ IMU      │  │ Stabilizer   │  │ Autofly   │  │
│  │ 1 kHz    │→ │ 200 Hz       │← │ 200 Hz    │  │
│  │ Mahony   │  │ PID + MRAC   │  │ Paths     │  │
│  └──────────┘  └──────┬───────┘  └───────────┘  │
│                       │                          │
│                  ┌────▼────┐                     │
│                  │ Motor   │  ┌──────────┐       │
│                  │ Mixer   │  │ Send     │       │
│                  │ TIM3    │  │ 100 Hz   │       │
│                  └─────────┘  │ Telemetry│       │
│                               │ + Cmds   │       │
│                               └────┬─────┘       │
│  ┌──────────┐  ┌──────────┐        │             │
│  │ Remoter  │  │ Monitor  │        │             │
│  │ 100 Hz   │  │ 1 Hz     │        │             │
│  │ RC+SBUS  │  │ Health   │        │             │
│  └──────────┘  └──────────┘        │             │
└─────────────────────────────────── ┼ ─────────────┘
                                    │ UART5 (115200)
                    ┌───────────────▼───────────────┐
                    │     Python Ground Station      │
                    │  ┌──────────┐ ┌────────────┐  │
                    │  │ Serial   │ │ Dashboard  │  │
                    │  │ Bridge   │→│ GUI        │  │
                    │  └──┬──┬───┘  └────────────┘  │
                    │     │  │                      │
                    │     │  └→ VOFA+ (UDP)         │
                    │     └──→ Flight Logger (CSV)  │
                    └──────────────────────────────┘
```

## Task Structure

All tasks are created in `start_task()` (`USER/main.c:31-89`) and use `vTaskDelayUntil` for deterministic scheduling:

| Task | Rate | Period | Role | Key File |
|------|------|--------|------|----------|
| `IMUSample_Task` | 1 kHz | 1 ms | Raw sensor reading (BMI088 SPI) | `USER/main.c:160-171` |
| `IMU_DataDeal_Task` | 1 kHz | 1 ms | Mahony attitude filter | `USER/main.c:141-153` → [[IMU Update]] |
| `Stabilizer_Task` | 200 Hz | 5 ms | PID + MRAC control + motor output | `USER/main.c:177-193` → [[StabilizerTask]] |
| `Autofly_Task` | 200 Hz | 5 ms | Path generation (TWC, sinusoid, circle) | `USER/main.c:217-228` → [[AutoflyTask]] |
| `Remoter_Task` | 100 Hz | 10 ms | RC input, SBUS loss, arming, fly mode | `USER/main.c:200-211` → [[RemoterTask]] |
| `Send_Task` | 100 Hz | 10 ms | Telemetry TX + command RX dispatch | `USER/main.c:117-132` |
| `SystemMonitor_Task` | 1 Hz | 1000 ms | Watchdog, FPS counters | `USER/main.c:100-111` |

See [[Multi-rate Task Partitioning]] for scheduling details and [[Control Loop Timing]] for dt contracts.

## Control Pipeline

The control pipeline executes every 5 ms in `stabilizer_Task()` (`TASK/StabilizerTask.c:76`):

1. **Check_Fly_Mode** → determine SDK/DangerousStop mode
2. **Update_Data** → read IMU angles, compute derived quantities (Cos_Yaw, Sin_Yaw, velocities)
3. **Compute_Motor** → cascaded PID loops (position → velocity → angle → rate), then MRAC augmentation, then motor mixing
4. **Update_Motor** → arming/mode guards → `Set_PWM_Motors()` or safety fallback

See [[StabilizerTask]] for full details.

## Communication Architecture

**Firmware → Host**: Telemetry frames with `0xAA 0xBB` sync, XOR CRC, two frame types (A: status/MRAC, B: PID/weights). Sent via UART5 DMA at 100 Hz.

**Host → Firmware**: Command frames with `0xCC 0xDD` sync, 9 bytes each. CMD IDs `0x01`-`0x0E` cover PID gains, MRAC params, flight mode, virtual sticks, paths, and safety limits.

See [[Ground-Station Binary Protocol]] for frame format and [[UART Peripheral Map]] for hardware wiring.

## Key Subsystems and Their Wiki Pages

### Firmware Core
- [[StabilizerTask]] — the heart of the control system
- [[PID Controller]] — algorithm and anti-windup
- [[MRAC Control Law]] — adaptive augmentation
- [[IMU Update]] — Mahony attitude estimation
- [[Motor Mixer]] — PWM generation
- [[AutoflyTask]] — autonomous paths
- [[RemoterTask]] — RC input and mode management

### Safety & Authority
- [[Virtual RC Authority]] — SBUS loss gating
- [[SDK Arming State Machine]] — arm/disarm transitions
- [[Path Arbitration]] — single-active path invariant

### Hardware Layer
- [[UART Peripheral Map]] — all 6 UART peripherals
- [[Interrupt Map]] — ISR dispatch table
- [[Timer & PWM Configuration]] — TIM3 motor PWM
- [[Coordinate Conventions]] — sign and frame definitions

### Ground Station
- [[Ground Station Bridge]] — serial decode/command/VOFA
- [[Dashboard]] — operator GUI
- [[VOFA Streaming]] — real-time visualization
- [[FlightLogger]] — CSV recording
- [[Ground Station Tooling]] — analysis scripts

### Data & Config
- [[Data Dictionary]] — shared structs and globals
- [[Config Reference]] — config.yaml keys
- [[Flash Memory]] — persistence status (currently none)

### Workflow
- [[Agent & Developer Quick-Start Guide]] — start here
- [[Tuning Workflow]] — how to tune PID/MRAC
- [[Adding a Command]] — recipe for new CMD IDs
- [[Common Pitfalls]] — troubleshooting

## Key Decisions

See [sources/architectural-decisions.md](sources/architectural-decisions.md) for the full decision log:
1. Multi-rate FreeRTOS tasks with `vTaskDelayUntil`
2. Lightweight binary protocol with XOR CRC
3. Virtual RC gating by SBUS loss + SDK mode
4. Single active path arbitration

## File Map

```
USER/main.c          → Entry point, task creation, scheduler start
TASK/StabilizerTask.c → Control pipeline (PID+MRAC+mixer)
TASK/AutoflyTask.c   → Autonomous path generators
TASK/send_data.c     → Telemetry packing + command dispatch
TASK/RemoterTask.c   → RC input + arming + mode
TASK/stm32f4xx_it.c  → All interrupt handlers
API/imu_update.c     → Mahony attitude filter
API/pid.c            → PID compute functions
API/mrac.h           → MRAC config, state, and types
API/mrac_math.c      → MRAC projection and math helpers
BSP/pwm.c            → TIM3 PWM motor output
BSP/usart4.c         → UART4 (T265 + GS commands)
BSP/usart5.c         → UART5 (GS telemetry + commands)
BSP/BSP.c            → Hardware init aggregator
Global_file/robot_types.h    → All shared struct definitions
Global_file/global_declare.h → Extern globals, macros, constants
ground_station/comm/serial_bridge.py → Host-side protocol handler
ground_station/gui/dashboard.py      → Operator GUI
ground_station/config.yaml           → Runtime configuration
```
