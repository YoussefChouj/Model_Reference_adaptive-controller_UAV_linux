# Graph Report - .  (2026-05-25)

## Corpus Check
- Large corpus: 305 files · ~524,621 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder, or use --no-semantic to run AST-only.

## Summary
- 3396 nodes · 4836 edges · 178 communities detected
- Extraction: 76% EXTRACTED · 24% INFERRED · 0% AMBIGUOUS · INFERRED: 1152 edges (avg confidence: 0.64)
- Token cost: 0 input · 0 output

## God Nodes (most connected - your core abstractions)
1. `drone_control_guide` - 195 edges
2. `cross-subsystem-interfaces` - 92 edges
3. `Dashboard` - 90 edges
4. `freertos-used` - 89 edges
5. `stm32f4-peripherals` - 65 edges
6. `overview` - 53 edges
7. `common-pitfalls` - 51 edges
8. `Agent & Developer Quick-Start Guide` - 47 edges
9. `Knowledge Base Index` - 44 edges
10. `yucelen-lectures` - 44 edges

## Surprising Connections (you probably didn't know these)
- `stm32f4-peripherals` --references--> `bmi088_init`  [INFERRED]
  wiki\reference\stm32f4-peripherals.md → BSP/BSP.c
- `common-pitfalls` --references--> `Cos_Yaw`  [INFERRED]
  wiki\concepts\common-pitfalls.md → StabilizerTask.c
- `common-pitfalls` --references--> `Sin_Yaw`  [INFERRED]
  wiki\concepts\common-pitfalls.md → StabilizerTask.c
- `Set_Zero_Motors` --implements--> `Motor Mixer`  [INFERRED]
  BSP/pwm.c → wiki\log.md
- `drone_control_guide` --references--> `AutoflyTask_RunSinusoid`  [INFERRED]
  docs\drone_control_guide.md → TASK/AutoflyTask.c

## Communities

### Community 0 - "Community 0"
Cohesion: 0.01
Nodes (2): RCC_GetFlagStatus(), RCC_WaitForHSEStartUp()

### Community 1 - "Community 1"
Cohesion: 0.01
Nodes (238): _imu_st, algorithm.c, API/imu_update.c, API/mrac.h, AutoflyTask, TASK/AutoflyTask.c, AutoflyTask_RunCircle, AutoflyTask_RunSinusoid (+230 more)

### Community 2 - "Community 2"
Cohesion: 0.01
Nodes (237): apply_preset_payload, argparse, ARM_Delay_time, ARM_Status, armed, ARMED State, ARMING (implicit state), Sustained stick position (1.5s) for arming (+229 more)

### Community 3 - "Community 3"
Cohesion: 0.02
Nodes (61): CMD 0x04 idx 0, CMD 0x04 idx 1, baud_rate, cmd_udp_port, serial_port, telemetry_mirror_port, vofa_executable, vofa_format (+53 more)

### Community 4 - "Community 4"
Cohesion: 0.02
Nodes (69): AnoOF_DataAnl(), AnoOF_GetOneByte(), AutoflyTask(), AutoflyTask_PathArbitrate(), AutoflyTask_RunCircle(), AutoflyTask_RunSinusoid(), SDK_StateMachine_Init(), SDK_StateMachine_Loop() (+61 more)

### Community 5 - "Community 5"
Cohesion: 0.02
Nodes (160): Actuator dynamics, Mixer and actuator dynamics for realism, Adaptive-control experiment structure, Adaptive Control Simulations, Adaptive Control Simulations, Adaptive_Control_Tutorial_2.ipynb, Adaptive Control Tutorial 2 Notebook, Adaptive Control Tutorial Notebook (+152 more)

### Community 6 - "Community 6"
Cohesion: 0.02
Nodes (50): prvCheckDelayedList(), prvCheckPendingReadyList(), prvInitialiseCoRoutineLists(), vCoRoutineSchedule(), xCoRoutineCreate(), Drone Flight Control Program, embedded C, Embedded C Programming (+42 more)

### Community 7 - "Community 7"
Cohesion: 0.02
Nodes (116): active, amplitude, angular_speed, AutoflyTask_PathArbitrate(), AutoflyTask, AutoflyTask_PathArbitrate, AutoflyTask_RunCircle, AutoflyTask_RunSinusoid (+108 more)

### Community 8 - "Community 8"
Cohesion: 0.02
Nodes (116): ADC1, ADC1 Channel 4, Battery Voltage ADC, Black wire color, Bottom-left position, Bottom-right position, BSP/pwm.c, BSP/pwm.h (+108 more)

### Community 9 - "Community 9"
Cohesion: 0.03
Nodes (96): Adding a Command, Agent & Developer Quick-Start Guide, analyze_flight_log_py, Architectural Decisions, CMD 0x01 (PID Gain Update), CMD 0x02 (MRAC Gamma), CMD 0x03 (MRAC u_max, mrac_to_mixer), CMD 0x05 (MRAC What_limit) (+88 more)

### Community 10 - "Community 10"
Cohesion: 0.03
Nodes (16): TI1_Config(), TI2_Config(), TI3_Config(), TI4_Config(), TIM_ETRClockMode1Config(), TIM_ETRClockMode2Config(), TIM_ETRConfig(), TIM_ICInit() (+8 more)

### Community 11 - "Community 11"
Cohesion: 0.03
Nodes (91): Adding a Command, Anti-Windup Strategy, API/, API/pid.c, API/pid.h, TASK/AutoflyTask.c, BSP.c, BSP/BSP.c / BSP.h (+83 more)

### Community 12 - "Community 12"
Cohesion: 0.03
Nodes (89): adc1_configuration, AnoOF_GetOneByte, anoof_getonebyte, bsp_spi_c, cmd queue, Command Ingress Latency Sensitivity, configmax_syscall_interrupt_priority, Decode_RX_Data_t265 (+81 more)

### Community 13 - "Community 13"
Cohesion: 0.04
Nodes (43): eTaskGetState(), prvAddCurrentTaskToDelayedList(), prvAddNewTaskToReadyList(), prvCheckTasksWaitingTermination(), prvDeleteTCB(), prvInitialiseNewTask(), prvInitialiseTaskLists(), prvListTasksWithinSingleList() (+35 more)

### Community 14 - "Community 14"
Cohesion: 0.05
Nodes (48): load_flight_data(), main(), plot_mrac_adaptive(), plot_tracking(), Read the flat t,frame,key,value format and rebuild into time series., _save(), analyze_weights(), build_json_record() (+40 more)

### Community 15 - "Community 15"
Cohesion: 0.04
Nodes (59): .agent_contracts/, .agent_reports/, ccc search, .agent_scripts/checker.py, Claude Code, /free, /free-graphify, /free-reason (+51 more)

### Community 16 - "Community 16"
Cohesion: 0.05
Nodes (18): RTC_Bcd2ToByte(), RTC_ByteToBcd2(), RTC_CoarseCalibCmd(), RTC_CoarseCalibConfig(), RTC_DeInit(), RTC_EnterInitMode(), RTC_ExitInitMode(), RTC_GetAlarm() (+10 more)

### Community 17 - "Community 17"
Cohesion: 0.04
Nodes (2): NVIC_SetPriority(), SysTick_Config()

### Community 18 - "Community 18"
Cohesion: 0.05
Nodes (29): FrameStats dataclass, pack_cmd_frame function, diag_telemetry_link.py — Telemetry Link Diagnostics, Rationale: standalone telemetry diagnosis without dashboard, xor_crc8 function, load_config(), _main_cli(), _parse_simple_yaml() (+21 more)

### Community 19 - "Community 19"
Cohesion: 0.04
Nodes (0): 

### Community 20 - "Community 20"
Cohesion: 0.07
Nodes (31): prvCopyDataFromQueue(), prvCopyDataToQueue(), prvInitialiseMutex(), prvInitialiseNewQueue(), prvIsQueueEmpty(), prvIsQueueFull(), prvNotifyQueueSetContainer(), prvUnlockQueue() (+23 more)

### Community 21 - "Community 21"
Cohesion: 0.05
Nodes (46): Ground Station Binary Protocol, Single Active Path Arbitration, Virtual RC Gating, Task period and dt constant alignment, Frame byte layout and CRC sync across firmware and host, Path activation flags mutual consistency, SBUS loss and FlyMode SDK dual condition for virtual stick acceptance, Multi-rate FreeRTOS Task Partitioning (+38 more)

### Community 22 - "Community 22"
Cohesion: 0.05
Nodes (44): Adaptive Control Simulations, Adaptive Simulation Theory-to-Code Deep Dive, Adding a Command, Autonomous Path Generation, Common Pitfalls, Config Reference, Control Loop Timing, Coordinate Conventions (+36 more)

### Community 23 - "Community 23"
Cohesion: 0.07
Nodes (17): FLASH_EraseAllBank1Sectors(), FLASH_EraseAllBank2Sectors(), FLASH_EraseAllSectors(), FLASH_EraseSector(), FLASH_GetStatus(), FLASH_OB_Launch(), FLASH_OB_PCROP1Config(), FLASH_OB_PCROPConfig() (+9 more)

### Community 24 - "Community 24"
Cohesion: 0.05
Nodes (0): 

### Community 25 - "Community 25"
Cohesion: 0.06
Nodes (0): 

### Community 26 - "Community 26"
Cohesion: 0.06
Nodes (0): 

### Community 27 - "Community 27"
Cohesion: 0.07
Nodes (0): 

### Community 28 - "Community 28"
Cohesion: 0.09
Nodes (31): Cache A stream context, Change cache bootstrap logic to use baselines, Add contamination guard to verify and auto-repair cache, Design target: Independent, persistent state per stream for port binding, tabs/layout, channel names, Add deterministic launch telemetry logging, _ensure_vofa_stream_context, Finding 1: Stream cache initialization cross-contaminating names, Finding 2: Stream inference uses only UDP local port, not channel schema identity (+23 more)

### Community 29 - "Community 29"
Cohesion: 0.07
Nodes (0): 

### Community 30 - "Community 30"
Cohesion: 0.1
Nodes (30): Capture A Config dashboard button, Capture B Config dashboard button, _capture_vofa_stream_preset function, Contamination Prevention Rationale: No contamination is possible, Dashboard auto-resolve file names behavior, Fast stream (Frame A, port 1347), Frame A Workspace dashboard button, Frame B Workspace dashboard button (+22 more)

### Community 31 - "Community 31"
Cohesion: 0.07
Nodes (0): 

### Community 32 - "Community 32"
Cohesion: 0.09
Nodes (28): .agent_memory/lessons.jsonl, ccc search, Concept (page type), file:line cross-reference, wikilinks cross-reference, docs/decisions.md, docs/interfaces.md, Actuator (UAV entity type) (+20 more)

### Community 33 - "Community 33"
Cohesion: 0.08
Nodes (2): CAN_GetITStatus(), CheckITStatus()

### Community 34 - "Community 34"
Cohesion: 0.08
Nodes (0): 

### Community 35 - "Community 35"
Cohesion: 0.08
Nodes (0): 

### Community 36 - "Community 36"
Cohesion: 0.08
Nodes (26): Complementary Filter, Mahony Filter, Board Support Package (BSP), IMU CSV Data, API/bmi088_driver.c, API/GPS.c, API/imu_update.c, API/pid.c (+18 more)

### Community 37 - "Community 37"
Cohesion: 0.08
Nodes (0): 

### Community 38 - "Community 38"
Cohesion: 0.1
Nodes (25): 115200 baud, Create Virtual Environment, CSV Format: timestamp,ax,ay,az,gx,gy,gz, FreeRTOS Kernel, IMU CSV File, IMU Sensor, Install Dependencies, SEGGER J-Link Programmer (+17 more)

### Community 39 - "Community 39"
Cohesion: 0.11
Nodes (0): 

### Community 40 - "Community 40"
Cohesion: 0.11
Nodes (0): 

### Community 41 - "Community 41"
Cohesion: 0.14
Nodes (7): PathExecutor, PositionSourceError, Ground-station path follower: 10 Hz virtual stick commands (CMD 0x06).  Firmwa, Return a normalised stick value in [-1.0, +1.0] for CMD 0x06., _stick_from_error(), Waypoint, RuntimeError

### Community 42 - "Community 42"
Cohesion: 0.12
Nodes (18): Autonomous path behaviors (target point, sinusoidal path, circular path), FreeRTOS multi-rate task scheduling for flight control, FreeRTOS multi-rate task scheduling for flight control, Ground-station binary protocol design (command and telemetry framing, CRC behavior), Ground-Station Command Handler, Ground-station binary protocol design (command and telemetry framing, CRC behavior), IMU sensor fusion (Mahony filter) and attitude estimation, IMU sensor fusion (Mahony filter) and attitude estimation (+10 more)

### Community 43 - "Community 43"
Cohesion: 0.12
Nodes (16): vofa_manual_setup_checklist, B Core Channel Groups (MAX\_NUM\_BASIS=6), B Rename Rules, Channel Rename Map (Frame A), Create Tabs, Create Tabs (Recommended), Final Validation, Frame A Workspace (+8 more)

### Community 44 - "Community 44"
Cohesion: 0.17
Nodes (15): cmd_udp_port, simulate_udp_port, telemetry_mirror_port, vofa_format, vofa_port_a, vofa_port_b, frame_simulator.py, ground_station/config.yaml (+7 more)

### Community 45 - "Community 45"
Cohesion: 0.19
Nodes (14): Co-routine Functionality, Compiler/Architecture Specific Directory, Core Kernel Components, croutine.c, FreeRTOS\readme.txt, FreeRTOS/Source, FreeRTOS/Source/Portable, Kernel (+6 more)

### Community 46 - "Community 46"
Cohesion: 0.22
Nodes (13): ARM Cortex-M7 Microcontrollers, Core Revision (r number, p number), /FreeRTOS/Source/portable/RVDS/ARM_CM4F, /FreeRTOS/Source/portable/RVDS/ARM_CM7/r0p1, Microcontroller Documentation, Minor Errata Workaround, If in doubt, use r0p1 port, FreeRTOS (+5 more)

### Community 47 - "Community 47"
Cohesion: 0.15
Nodes (13): Beginner Friendly Explanation, Bit Manipulation and Operators, Double Brackets Linking, Inline Tagging, Key Points Section, Line-by-Line Breakdown, Linking Principles, Note Title Format (+5 more)

### Community 48 - "Community 48"
Cohesion: 0.2
Nodes (10): Height Control, Ctrler.locxPID, Ctrler.locxsPID, Ctrler.locyPID, Ctrler.locysPID, Position-to-Velocity PID Level, Rationale: lower-rate loops decimated to 100 Hz because slower dynamics, Velocity-to-Angle PID Level (+2 more)

### Community 49 - "Community 49"
Cohesion: 0.44
Nodes (8): decode_stream(), FrameStats, main(), pack_cmd_frame(), print_port_list(), probe_udp_bridge(), run_serial_probe(), xor_crc8()

### Community 50 - "Community 50"
Cohesion: 0.22
Nodes (9): Ground, Pin 8 (TIM3 CH1), Pin 8 (TIM3 CH2), Pin 8 (TIM3 CH3), Pin 8 (TIM3 CH4), TIM3 CH1, TIM3 CH2, TIM3 CH3 (+1 more)

### Community 51 - "Community 51"
Cohesion: 0.29
Nodes (7): Configuration Reference, FreeRTOSConfig.h, FreeRTOS Configuration, Sensor Configuration, Task Configuration, TASK/, Tuning Parameters

### Community 52 - "Community 52"
Cohesion: 0.5
Nodes (2): Load a flat key: value YAML file (no nesting). Returns {} on missing/error., simple_yaml_kv_load()

### Community 53 - "Community 53"
Cohesion: 0.5
Nodes (4): Angle-to-Rate PID Level, Ctrler.pitchPID, Ctrler.rollPID, Ctrler.yawPID

### Community 54 - "Community 54"
Cohesion: 0.5
Nodes (4): Ctrler.gyroxPID, Ctrler.gyroyPID, Ctrler.gyrozPID, Rate-to-Motor Mixer PID Level

### Community 55 - "Community 55"
Cohesion: 0.5
Nodes (4): invSqrt (fast inverse square root function), quaternion normalization step, Trade off ~0.17% accuracy to avoid FPU sqrt+div pipeline stall at 1 kHz on Cortex-M4, Quaternion norm drifts from 1.0 due to numerical integration; re-normalization is mandatory every step to maintain valid rotation

### Community 56 - "Community 56"
Cohesion: 1.0
Nodes (2): count_packets(), main()

### Community 57 - "Community 57"
Cohesion: 0.67
Nodes (0): 

### Community 58 - "Community 58"
Cohesion: 0.67
Nodes (3): PID Controller, PWM Signals, Start with small gains; test in safe setup (props removed)

### Community 59 - "Community 59"
Cohesion: 0.67
Nodes (3): b_path_debug.tabviews.json, b_safety_debug.tabviews.json, Additional dashboard buttons

### Community 60 - "Community 60"
Cohesion: 0.67
Nodes (3): Telemetry Frame (0xAA 0xBB), Send_Groundstation_Telemetry_UART4 (send_data.c), Telemetry receiving functions in serial_bridge.py (_rx_loop, _parse_and_handle_datagram, _handle_frame)

### Community 61 - "Community 61"
Cohesion: 0.67
Nodes (2): matplotlib, numpy

### Community 62 - "Community 62"
Cohesion: 0.67
Nodes (3): accel_to_lean_angles, Accel to Lean Angle Mapping, Rationale: accounts for nonlinear relationship between tilt angle and horizontal acceleration

### Community 63 - "Community 63"
Cohesion: 0.67
Nodes (3): anti-windup, exInt, eyInt, ezInt (integral error accumulators), ∫ω_err dt (paper symbol)

### Community 64 - "Community 64"
Cohesion: 0.67
Nodes (3): Δt (paper symbol), dt (time step parameter), IMU_DataDeal_Task

### Community 65 - "Community 65"
Cohesion: 1.0
Nodes (2): UART Logging, Avoid heavy logging inside interrupts

### Community 66 - "Community 66"
Cohesion: 1.0
Nodes (2): FreeRTOS/Source/include, Header Files

### Community 67 - "Community 67"
Cohesion: 1.0
Nodes (2): FreeRTOS/Source/Portable/MemMang directory, Five Sample Memory Allocators

### Community 68 - "Community 68"
Cohesion: 1.0
Nodes (1): FreeRTOS/portable/RVDS

### Community 69 - "Community 69"
Cohesion: 1.0
Nodes (2): channel_reference.json, MAX_NUM_BASIS = 6 assumption

### Community 70 - "Community 70"
Cohesion: 1.0
Nodes (2): Pin 8 (TIM4 CH4), TIM4 CH4

### Community 71 - "Community 71"
Cohesion: 1.0
Nodes (2): Pin 8 (TIM4 CH1), TIM4 CH1

### Community 72 - "Community 72"
Cohesion: 1.0
Nodes (2): Pin 8 (TIM4 CH2), TIM4 CH2

### Community 73 - "Community 73"
Cohesion: 1.0
Nodes (2): Pin 8 (TIM4 CH3), TIM4 CH3

### Community 74 - "Community 74"
Cohesion: 1.0
Nodes (2): PA13 (SWDIO), SWDIO

### Community 75 - "Community 75"
Cohesion: 1.0
Nodes (2): PA14 (SWCLK), SWCLK

### Community 76 - "Community 76"
Cohesion: 1.0
Nodes (2): Beep, TIM4 CH3

### Community 77 - "Community 77"
Cohesion: 1.0
Nodes (2): Pin Mapping, NOTE/readme.txt

### Community 78 - "Community 78"
Cohesion: 1.0
Nodes (2): Power cable (BEC), Tail

### Community 79 - "Community 79"
Cohesion: 1.0
Nodes (2): Ground Truth Wiki Compilation Rationale, Raw Directory Immutability Decision

### Community 80 - "Community 80"
Cohesion: 1.0
Nodes (2): vofa_host, SerialBridge

### Community 81 - "Community 81"
Cohesion: 1.0
Nodes (2): vofa_executable, Dashboard._open_plot

### Community 82 - "Community 82"
Cohesion: 1.0
Nodes (2): vofa_manual_mode, Dashboard

### Community 83 - "Community 83"
Cohesion: 1.0
Nodes (2): cmd_host, Dashboard._send_cmd

### Community 84 - "Community 84"
Cohesion: 1.0
Nodes (2): Shared globals are intentional for low latency; timing consistency relies on periodic tasks, Shared Globals Without Mutexes for Low Latency

### Community 85 - "Community 85"
Cohesion: 1.0
Nodes (2): Flash API Functions, STM32 Standard Peripheral Flash Driver

### Community 86 - "Community 86"
Cohesion: 1.0
Nodes (2): Boot Sequence, Compile-Time Default Parameters

### Community 87 - "Community 87"
Cohesion: 1.0
Nodes (2): Kp (proportional gain), kₚ (paper symbol)

### Community 88 - "Community 88"
Cohesion: 1.0
Nodes (2): ex, ey, ez (cross-product attitude error), ω_err (paper symbol)

### Community 89 - "Community 89"
Cohesion: 1.0
Nodes (2): ω_raw (paper symbol), Gyro_X_Real, Gyro_Y_Real, Gyro_Z_Real (raw gyroscope)

### Community 90 - "Community 90"
Cohesion: 1.0
Nodes (2): Second-order correction from Cayley-Hamilton expansion provides better norm preservation than first-order, second-order quaternion propagation

### Community 91 - "Community 91"
Cohesion: 1.0
Nodes (2): Ki (integral gain), kᵢ (paper symbol)

### Community 92 - "Community 92"
Cohesion: 1.0
Nodes (2): vecxZ, vecyZ, veczZ (estimated down vector), v̂_z (paper symbol)

### Community 93 - "Community 93"
Cohesion: 1.0
Nodes (2): a_normalized (paper symbol), nor_acc[X], nor_acc[Y], nor_acc[Z] (normalized accelerometer)

### Community 94 - "Community 94"
Cohesion: 1.0
Nodes (0): 

### Community 95 - "Community 95"
Cohesion: 1.0
Nodes (1): Minimal summary: duration, numeric ranges for mrac.pitch.e, pid.z_rate FB.

### Community 96 - "Community 96"
Cohesion: 1.0
Nodes (1): Global_file/global_declare.h/c

### Community 97 - "Community 97"
Cohesion: 1.0
Nodes (1): USER/JX_FLY.uvprojx

### Community 98 - "Community 98"
Cohesion: 1.0
Nodes (1): keilkilll.bat

### Community 99 - "Community 99"
Cohesion: 1.0
Nodes (1): BSP\Note.md

### Community 100 - "Community 100"
Cohesion: 1.0
Nodes (1): Architectural Decisions

### Community 101 - "Community 101"
Cohesion: 1.0
Nodes (1): _sync_system_context_to_stream_cache

### Community 102 - "Community 102"
Cohesion: 1.0
Nodes (1): _stage_stream_cache_to_system_context

### Community 103 - "Community 103"
Cohesion: 1.0
Nodes (1): _apply_vofa_channel_labels

### Community 104 - "Community 104"
Cohesion: 1.0
Nodes (1): _terminate_vofa_instances

### Community 105 - "Community 105"
Cohesion: 1.0
Nodes (1): Cache B stream context

### Community 106 - "Community 106"
Cohesion: 1.0
Nodes (1): vofa_manual_mode config

### Community 107 - "Community 107"
Cohesion: 1.0
Nodes (1): VOFA Application

### Community 108 - "Community 108"
Cohesion: 1.0
Nodes (1): Ground Station Dashboard

### Community 109 - "Community 109"
Cohesion: 1.0
Nodes (1): Dashboard sidebar wiring

### Community 110 - "Community 110"
Cohesion: 1.0
Nodes (1): SWCLK pin

### Community 111 - "Community 111"
Cohesion: 1.0
Nodes (1): SWDIO pin

### Community 112 - "Community 112"
Cohesion: 1.0
Nodes (1): 3.3V power

### Community 113 - "Community 113"
Cohesion: 1.0
Nodes (1): R (left header)

### Community 114 - "Community 114"
Cohesion: 1.0
Nodes (1): T (left header)

### Community 115 - "Community 115"
Cohesion: 1.0
Nodes (1): 5 (left header)

### Community 116 - "Community 116"
Cohesion: 1.0
Nodes (1): TIM4

### Community 117 - "Community 117"
Cohesion: 1.0
Nodes (1): TIM3

### Community 118 - "Community 118"
Cohesion: 1.0
Nodes (1): TIM2

### Community 119 - "Community 119"
Cohesion: 1.0
Nodes (1): TIM2 CH1

### Community 120 - "Community 120"
Cohesion: 1.0
Nodes (1): TIM2 CH2

### Community 121 - "Community 121"
Cohesion: 1.0
Nodes (1): TIM2 CH3

### Community 122 - "Community 122"
Cohesion: 1.0
Nodes (1): TIM2 CH4

### Community 123 - "Community 123"
Cohesion: 1.0
Nodes (1): Pin 5 (TIM2 area)

### Community 124 - "Community 124"
Cohesion: 1.0
Nodes (1): BATT(ADC)

### Community 125 - "Community 125"
Cohesion: 1.0
Nodes (1): STM32F407ZGTx

### Community 126 - "Community 126"
Cohesion: 1.0
Nodes (1): PWM generation

### Community 127 - "Community 127"
Cohesion: 1.0
Nodes (1): pointers

### Community 128 - "Community 128"
Cohesion: 1.0
Nodes (1): structs

### Community 129 - "Community 129"
Cohesion: 1.0
Nodes (1): hardware registers

### Community 130 - "Community 130"
Cohesion: 1.0
Nodes (1): interrupts

### Community 131 - "Community 131"
Cohesion: 1.0
Nodes (1): bit manipulation

### Community 132 - "Community 132"
Cohesion: 1.0
Nodes (1): Index

### Community 133 - "Community 133"
Cohesion: 1.0
Nodes (1): Project Overview

### Community 134 - "Community 134"
Cohesion: 1.0
Nodes (1): CMD ID 0x10

### Community 135 - "Community 135"
Cohesion: 1.0
Nodes (1): Config Reference

### Community 136 - "Community 136"
Cohesion: 1.0
Nodes (1): ground_station/gui/dashboard.py

### Community 137 - "Community 137"
Cohesion: 1.0
Nodes (1): com_data

### Community 138 - "Community 138"
Cohesion: 1.0
Nodes (1): TWC

### Community 139 - "Community 139"
Cohesion: 1.0
Nodes (1): PIDTypeDef

### Community 140 - "Community 140"
Cohesion: 1.0
Nodes (1): StickMotionTypeDef

### Community 141 - "Community 141"
Cohesion: 1.0
Nodes (1): USART_RX_TypeDef

### Community 142 - "Community 142"
Cohesion: 1.0
Nodes (1): check_vofa_udp.py — VOFA UDP Health Check

### Community 143 - "Community 143"
Cohesion: 1.0
Nodes (1): show_frame_a_vofa_bytes.py — Raw Frame Inspection

### Community 144 - "Community 144"
Cohesion: 1.0
Nodes (1): invSqrt

### Community 145 - "Community 145"
Cohesion: 1.0
Nodes (1): Motor_PWM_IDLE

### Community 146 - "Community 146"
Cohesion: 1.0
Nodes (1): Global_file/global_declare.h

### Community 147 - "Community 147"
Cohesion: 1.0
Nodes (1): TASK/StabilizerTask.c

### Community 148 - "Community 148"
Cohesion: 1.0
Nodes (1): API/mrac.h

### Community 149 - "Community 149"
Cohesion: 1.0
Nodes (1): Stabilizer_Task

### Community 150 - "Community 150"
Cohesion: 1.0
Nodes (1): Cos_Yaw_01

### Community 151 - "Community 151"
Cohesion: 1.0
Nodes (1): Sin_Yaw_01

### Community 152 - "Community 152"
Cohesion: 1.0
Nodes (1): imu_data.yaw

### Community 153 - "Community 153"
Cohesion: 1.0
Nodes (1): GRAVITY_MSS

### Community 154 - "Community 154"
Cohesion: 1.0
Nodes (1): cnt_loc

### Community 155 - "Community 155"
Cohesion: 1.0
Nodes (1): cnt_h

### Community 156 - "Community 156"
Cohesion: 1.0
Nodes (1): Anti-Windup Strategy

### Community 157 - "Community 157"
Cohesion: 1.0
Nodes (1): half_T (half time step)

### Community 158 - "Community 158"
Cohesion: 1.0
Nodes (1): delta_theta (half-angle rotation vector)

### Community 159 - "Community 159"
Cohesion: 1.0
Nodes (1): commented-out first-order propagation

### Community 160 - "Community 160"
Cohesion: 1.0
Nodes (1): rotation matrix elements

### Community 161 - "Community 161"
Cohesion: 1.0
Nodes (1): Euler angles

### Community 162 - "Community 162"
Cohesion: 1.0
Nodes (1): SO(3) observer

### Community 163 - "Community 163"
Cohesion: 1.0
Nodes (1): PI correction law

### Community 164 - "Community 164"
Cohesion: 1.0
Nodes (1): cross-product error (attitude error)

### Community 165 - "Community 165"
Cohesion: 1.0
Nodes (1): unit quaternion

### Community 166 - "Community 166"
Cohesion: 1.0
Nodes (1): rotation matrix R(q̂)

### Community 167 - "Community 167"
Cohesion: 1.0
Nodes (1): fast inverse square root (Newton's method)

### Community 168 - "Community 168"
Cohesion: 1.0
Nodes (1): Cayley-Hamilton expansion

### Community 169 - "Community 169"
Cohesion: 1.0
Nodes (1): gyroscope bias estimator

### Community 170 - "Community 170"
Cohesion: 1.0
Nodes (1): quaternion re-normalization

### Community 171 - "Community 171"
Cohesion: 1.0
Nodes (0): 

### Community 172 - "Community 172"
Cohesion: 1.0
Nodes (0): 

### Community 173 - "Community 173"
Cohesion: 1.0
Nodes (1): Note

### Community 174 - "Community 174"
Cohesion: 1.0
Nodes (1): Adaptive Control Simulations

### Community 175 - "Community 175"
Cohesion: 1.0
Nodes (1): Cascaded PID Theory

### Community 176 - "Community 176"
Cohesion: 1.0
Nodes (1): Config Reference

### Community 177 - "Community 177"
Cohesion: 1.0
Nodes (1): MRAC Theory

## Ambiguous Edges - Review These
- `IMU Sensor` → `PID`  [AMBIGUOUS]
  UAV_EXERCISES.md · relation: safety_critical_for

## Knowledge Gaps
- **928 isolated node(s):** `Simple IMU CSV visualizer.  Input CSV expected columns (header optional): time`, `Synthetic UART4 telemetry generator for offline testing.  Sends Frame A / Fram`, `Same wire format as TASK/send_data.c: 16-bit LEN, then payload + XOR CRC8.`, `8 floats (sine, distinct Hz) + ARM + FlyMode + sbus_lost + TWC flags + proto_ver`, `MRAC: 4 axes * (N theta + u_nom + xm) + 12 PID * (FB, Des, U).     Theta: calle` (+923 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 65`** (2 nodes): `UART Logging`, `Avoid heavy logging inside interrupts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 66`** (2 nodes): `FreeRTOS/Source/include`, `Header Files`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 67`** (2 nodes): `FreeRTOS/Source/Portable/MemMang directory`, `Five Sample Memory Allocators`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 68`** (2 nodes): `FreeRTOS/portable/RVDS`, `See-also-the-RVDS-directory.txt`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 69`** (2 nodes): `channel_reference.json`, `MAX_NUM_BASIS = 6 assumption`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 70`** (2 nodes): `Pin 8 (TIM4 CH4)`, `TIM4 CH4`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 71`** (2 nodes): `Pin 8 (TIM4 CH1)`, `TIM4 CH1`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 72`** (2 nodes): `Pin 8 (TIM4 CH2)`, `TIM4 CH2`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 73`** (2 nodes): `Pin 8 (TIM4 CH3)`, `TIM4 CH3`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 74`** (2 nodes): `PA13 (SWDIO)`, `SWDIO`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 75`** (2 nodes): `PA14 (SWCLK)`, `SWCLK`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 76`** (2 nodes): `Beep`, `TIM4 CH3`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 77`** (2 nodes): `Pin Mapping`, `NOTE/readme.txt`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 78`** (2 nodes): `Power cable (BEC)`, `Tail`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 79`** (2 nodes): `Ground Truth Wiki Compilation Rationale`, `Raw Directory Immutability Decision`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 80`** (2 nodes): `vofa_host`, `SerialBridge`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 81`** (2 nodes): `vofa_executable`, `Dashboard._open_plot`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 82`** (2 nodes): `vofa_manual_mode`, `Dashboard`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 83`** (2 nodes): `cmd_host`, `Dashboard._send_cmd`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 84`** (2 nodes): `Shared globals are intentional for low latency; timing consistency relies on periodic tasks`, `Shared Globals Without Mutexes for Low Latency`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 85`** (2 nodes): `Flash API Functions`, `STM32 Standard Peripheral Flash Driver`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 86`** (2 nodes): `Boot Sequence`, `Compile-Time Default Parameters`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 87`** (2 nodes): `Kp (proportional gain)`, `kₚ (paper symbol)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 88`** (2 nodes): `ex, ey, ez (cross-product attitude error)`, `ω_err (paper symbol)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 89`** (2 nodes): `ω_raw (paper symbol)`, `Gyro_X_Real, Gyro_Y_Real, Gyro_Z_Real (raw gyroscope)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 90`** (2 nodes): `Second-order correction from Cayley-Hamilton expansion provides better norm preservation than first-order`, `second-order quaternion propagation`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 91`** (2 nodes): `Ki (integral gain)`, `kᵢ (paper symbol)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 92`** (2 nodes): `vecxZ, vecyZ, veczZ (estimated down vector)`, `v̂_z (paper symbol)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 93`** (2 nodes): `a_normalized (paper symbol)`, `nor_acc[X], nor_acc[Y], nor_acc[Z] (normalized accelerometer)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 94`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 95`** (1 nodes): `Minimal summary: duration, numeric ranges for mrac.pitch.e, pid.z_rate FB.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 96`** (1 nodes): `Global_file/global_declare.h/c`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 97`** (1 nodes): `USER/JX_FLY.uvprojx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 98`** (1 nodes): `keilkilll.bat`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 99`** (1 nodes): `BSP\Note.md`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 100`** (1 nodes): `Architectural Decisions`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 101`** (1 nodes): `_sync_system_context_to_stream_cache`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 102`** (1 nodes): `_stage_stream_cache_to_system_context`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 103`** (1 nodes): `_apply_vofa_channel_labels`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 104`** (1 nodes): `_terminate_vofa_instances`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 105`** (1 nodes): `Cache B stream context`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 106`** (1 nodes): `vofa_manual_mode config`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 107`** (1 nodes): `VOFA Application`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 108`** (1 nodes): `Ground Station Dashboard`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 109`** (1 nodes): `Dashboard sidebar wiring`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 110`** (1 nodes): `SWCLK pin`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 111`** (1 nodes): `SWDIO pin`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 112`** (1 nodes): `3.3V power`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 113`** (1 nodes): `R (left header)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 114`** (1 nodes): `T (left header)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 115`** (1 nodes): `5 (left header)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 116`** (1 nodes): `TIM4`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 117`** (1 nodes): `TIM3`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 118`** (1 nodes): `TIM2`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 119`** (1 nodes): `TIM2 CH1`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 120`** (1 nodes): `TIM2 CH2`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 121`** (1 nodes): `TIM2 CH3`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 122`** (1 nodes): `TIM2 CH4`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 123`** (1 nodes): `Pin 5 (TIM2 area)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 124`** (1 nodes): `BATT(ADC)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 125`** (1 nodes): `STM32F407ZGTx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 126`** (1 nodes): `PWM generation`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 127`** (1 nodes): `pointers`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 128`** (1 nodes): `structs`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 129`** (1 nodes): `hardware registers`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 130`** (1 nodes): `interrupts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 131`** (1 nodes): `bit manipulation`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 132`** (1 nodes): `Index`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 133`** (1 nodes): `Project Overview`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 134`** (1 nodes): `CMD ID 0x10`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 135`** (1 nodes): `Config Reference`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 136`** (1 nodes): `ground_station/gui/dashboard.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 137`** (1 nodes): `com_data`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 138`** (1 nodes): `TWC`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 139`** (1 nodes): `PIDTypeDef`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 140`** (1 nodes): `StickMotionTypeDef`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 141`** (1 nodes): `USART_RX_TypeDef`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 142`** (1 nodes): `check_vofa_udp.py — VOFA UDP Health Check`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 143`** (1 nodes): `show_frame_a_vofa_bytes.py — Raw Frame Inspection`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 144`** (1 nodes): `invSqrt`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 145`** (1 nodes): `Motor_PWM_IDLE`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 146`** (1 nodes): `Global_file/global_declare.h`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 147`** (1 nodes): `TASK/StabilizerTask.c`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 148`** (1 nodes): `API/mrac.h`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 149`** (1 nodes): `Stabilizer_Task`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 150`** (1 nodes): `Cos_Yaw_01`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 151`** (1 nodes): `Sin_Yaw_01`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 152`** (1 nodes): `imu_data.yaw`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 153`** (1 nodes): `GRAVITY_MSS`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 154`** (1 nodes): `cnt_loc`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 155`** (1 nodes): `cnt_h`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 156`** (1 nodes): `Anti-Windup Strategy`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 157`** (1 nodes): `half_T (half time step)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 158`** (1 nodes): `delta_theta (half-angle rotation vector)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 159`** (1 nodes): `commented-out first-order propagation`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 160`** (1 nodes): `rotation matrix elements`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 161`** (1 nodes): `Euler angles`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 162`** (1 nodes): `SO(3) observer`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 163`** (1 nodes): `PI correction law`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 164`** (1 nodes): `cross-product error (attitude error)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 165`** (1 nodes): `unit quaternion`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 166`** (1 nodes): `rotation matrix R(q̂)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 167`** (1 nodes): `fast inverse square root (Newton's method)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 168`** (1 nodes): `Cayley-Hamilton expansion`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 169`** (1 nodes): `gyroscope bias estimator`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 170`** (1 nodes): `quaternion re-normalization`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 171`** (1 nodes): `Note.txt`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 172`** (1 nodes): `channel_map.txt`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 173`** (1 nodes): `Note`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 174`** (1 nodes): `Adaptive Control Simulations`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 175`** (1 nodes): `Cascaded PID Theory`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 176`** (1 nodes): `Config Reference`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 177`** (1 nodes): `MRAC Theory`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `IMU Sensor` and `PID`?**
  _Edge tagged AMBIGUOUS (relation: safety_critical_for) - confidence is low._
- **Why does `drone_control_guide` connect `Community 2` to `Community 1`, `Community 4`, `Community 5`, `Community 7`, `Community 8`, `Community 9`, `Community 43`, `Community 44`, `Community 12`, `Community 20`?**
  _High betweenness centrality (0.139) - this node is a cross-community bridge._
- **Why does `overview` connect `Community 1` to `Community 2`, `Community 3`, `Community 4`, `Community 5`, `Community 7`, `Community 8`, `Community 9`, `Community 11`, `Community 12`?**
  _High betweenness centrality (0.095) - this node is a cross-community bridge._
- **Why does `cross-subsystem-interfaces` connect `Community 7` to `Community 32`, `Community 1`, `Community 2`, `Community 4`, `Community 5`, `Community 8`, `Community 9`, `Community 12`?**
  _High betweenness centrality (0.065) - this node is a cross-community bridge._
- **Are the 138 inferred relationships involving `drone_control_guide` (e.g. with `vtaskstartscheduler` and `Start RTOS Task`) actually correct?**
  _`drone_control_guide` has 138 INFERRED edges - model-reasoned connections that need verification._
- **Are the 61 inferred relationships involving `cross-subsystem-interfaces` (e.g. with `_pack_command_frame` and `Handle_UART4_GroundStation_Command`) actually correct?**
  _`cross-subsystem-interfaces` has 61 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `Dashboard` (e.g. with `SerialBridge` and `main()`) actually correct?**
  _`Dashboard` has 4 INFERRED edges - model-reasoned connections that need verification._