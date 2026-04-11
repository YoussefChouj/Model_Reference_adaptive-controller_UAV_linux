# Graph Report - .  (2026-04-11)

## Corpus Check
- Large corpus: 236 files · ~472,329 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder, or use --no-semantic to run AST-only.

## Summary
- 1922 nodes · 2673 edges · 98 communities detected
- Extraction: 79% EXTRACTED · 21% INFERRED · 0% AMBIGUOUS · INFERRED: 568 edges (avg confidence: 0.52)
- Token cost: 0 input · 0 output

## God Nodes (most connected - your core abstractions)
1. `Dashboard` - 111 edges
2. `SerialBridge` - 43 edges
3. `FlightLogger` - 19 edges
4. `FLASH_WaitForLastOperation()` - 17 edges
5. `main()` - 15 edges
6. `VOFA Context Switch Audit (A/B Buttons)` - 15 edges
7. `GETTING STARTED Guide` - 13 edges
8. `TIM3` - 13 edges
9. `PathExecutor` - 12 edges
10. `_simple_yaml_kv_load()` - 11 edges

## Surprising Connections (you probably didn't know these)
- `Blink/heartbeat FreeRTOS task` --controls--> `BSP/pwm.c`  [INFERRED]
  UAV_TUTORIAL.md → GETTING_STARTED.md
- `UdpBridgeClient` --uses--> `SerialBridge`  [INFERRED]
  ground_station\gui\dashboard.py → ground_station\comm\serial_bridge.py
- `DebouncedSender` --uses--> `SerialBridge`  [INFERRED]
  ground_station\gui\dashboard.py → ground_station\comm\serial_bridge.py
- `Dashboard` --uses--> `SerialBridge`  [INFERRED]
  ground_station\gui\dashboard.py → ground_station\comm\serial_bridge.py
- `Send ground-station commands to a running `serial_bridge.py` process.` --uses--> `SerialBridge`  [INFERRED]
  ground_station\gui\dashboard.py → ground_station\comm\serial_bridge.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.02
Nodes (60): AnoOF_DataAnl(), AnoOF_GetOneByte(), AutoflyTask(), AutoflyTask_PathArbitrate(), AutoflyTask_RunCircle(), AutoflyTask_RunSinusoid(), SDK_StateMachine_Init(), SDK_StateMachine_Loop() (+52 more)

### Community 1 - "Community 1"
Cohesion: 0.03
Nodes (30): Dashboard, DebouncedSender, dump_preset_yaml(), _format_inline_map(), load_preset_yaml(), main(), _parse_inline_map(), _parse_inline_value() (+22 more)

### Community 2 - "Community 2"
Cohesion: 0.03
Nodes (39): api, Blink/heartbeat FreeRTOS task, prvCheckDelayedList(), prvCheckPendingReadyList(), prvInitialiseCoRoutineLists(), vCoRoutineSchedule(), xCoRoutineCreate(), Embedded C (+31 more)

### Community 3 - "Community 3"
Cohesion: 0.03
Nodes (16): TI1_Config(), TI2_Config(), TI3_Config(), TI4_Config(), TIM_ETRClockMode1Config(), TIM_ETRClockMode2Config(), TIM_ETRConfig(), TIM_ICInit() (+8 more)

### Community 4 - "Community 4"
Cohesion: 0.03
Nodes (2): RCC_GetFlagStatus(), RCC_WaitForHSEStartUp()

### Community 5 - "Community 5"
Cohesion: 0.04
Nodes (43): eTaskGetState(), prvAddCurrentTaskToDelayedList(), prvAddNewTaskToReadyList(), prvCheckTasksWaitingTermination(), prvDeleteTCB(), prvInitialiseNewTask(), prvInitialiseTaskLists(), prvListTasksWithinSingleList() (+35 more)

### Community 6 - "Community 6"
Cohesion: 0.03
Nodes (0): 

### Community 7 - "Community 7"
Cohesion: 0.05
Nodes (45): load_flight_data(), main(), plot_mrac_adaptive(), plot_tracking(), Read the flat t,frame,key,value format and rebuild into time series., _save(), analyze_weights(), build_json_record() (+37 more)

### Community 8 - "Community 8"
Cohesion: 0.05
Nodes (18): RTC_Bcd2ToByte(), RTC_ByteToBcd2(), RTC_CoarseCalibCmd(), RTC_CoarseCalibConfig(), RTC_DeInit(), RTC_EnterInitMode(), RTC_ExitInitMode(), RTC_GetAlarm() (+10 more)

### Community 9 - "Community 9"
Cohesion: 0.04
Nodes (2): NVIC_SetPriority(), SysTick_Config()

### Community 10 - "Community 10"
Cohesion: 0.05
Nodes (54): API/bmi088_driver.c, API/imu_update.c, API/pid.c, BATT(AD), BSP/pwm.c, File BSP/pwm.h, CH1, CH2 (+46 more)

### Community 11 - "Community 11"
Cohesion: 0.04
Nodes (0): 

### Community 12 - "Community 12"
Cohesion: 0.07
Nodes (21): load_config(), _main_cli(), _parse_simple_yaml(), CRC8 in this project is an XOR checksum over bytes.     Matches the C code:, FireWater / CSV channel names: dots -> underscores (mrac.pitch.e -> mrac_pitch_e, Latest decoded Frame A / Frame B variables (thread-safe, for GUI + logging)., Send one telemetry burst to VOFA+ according to config `vofa_format` and frame ty, VOFA+ JustFloat: little-endian float32 payload + frame tail bytes. (+13 more)

### Community 13 - "Community 13"
Cohesion: 0.07
Nodes (31): prvCopyDataFromQueue(), prvCopyDataToQueue(), prvInitialiseMutex(), prvInitialiseNewQueue(), prvIsQueueEmpty(), prvIsQueueFull(), prvNotifyQueueSetContainer(), prvUnlockQueue() (+23 more)

### Community 14 - "Community 14"
Cohesion: 0.07
Nodes (17): FLASH_EraseAllBank1Sectors(), FLASH_EraseAllBank2Sectors(), FLASH_EraseAllSectors(), FLASH_EraseSector(), FLASH_GetStatus(), FLASH_OB_Launch(), FLASH_OB_PCROP1Config(), FLASH_OB_PCROPConfig() (+9 more)

### Community 15 - "Community 15"
Cohesion: 0.05
Nodes (0): 

### Community 16 - "Community 16"
Cohesion: 0.06
Nodes (0): 

### Community 17 - "Community 17"
Cohesion: 0.07
Nodes (0): 

### Community 18 - "Community 18"
Cohesion: 0.07
Nodes (0): 

### Community 19 - "Community 19"
Cohesion: 0.07
Nodes (0): 

### Community 20 - "Community 20"
Cohesion: 0.07
Nodes (0): 

### Community 21 - "Community 21"
Cohesion: 0.08
Nodes (2): CAN_GetITStatus(), CheckITStatus()

### Community 22 - "Community 22"
Cohesion: 0.08
Nodes (0): 

### Community 23 - "Community 23"
Cohesion: 0.08
Nodes (0): 

### Community 24 - "Community 24"
Cohesion: 0.08
Nodes (0): 

### Community 25 - "Community 25"
Cohesion: 0.14
Nodes (14): prvCheckForValidListAndQueue(), prvGetNextExpireTime(), prvInitialiseNewTimer(), prvInsertTimerInActiveList(), prvProcessExpiredTimer(), prvProcessReceivedCommands(), prvProcessTimerOrBlockTask(), prvSampleTimeNow() (+6 more)

### Community 26 - "Community 26"
Cohesion: 0.11
Nodes (22): settings_ctx (global channel name state), baseline_a.config.json, baseline_b.config.json, VOFA Context Switch Audit (A/B Buttons), ground_station/gui/dashboard.py, presets/vofa/stream_a/vofa+.config.json, presets/vofa/stream_a/vofa+.tabviews.json, presets/vofa/stream_b/vofa+.config.json (+14 more)

### Community 27 - "Community 27"
Cohesion: 0.11
Nodes (0): 

### Community 28 - "Community 28"
Cohesion: 0.11
Nodes (0): 

### Community 29 - "Community 29"
Cohesion: 0.11
Nodes (0): 

### Community 30 - "Community 30"
Cohesion: 0.11
Nodes (0): 

### Community 31 - "Community 31"
Cohesion: 0.15
Nodes (5): PathExecutor, PositionSourceError, Ground-station path follower: 10 Hz virtual stick commands (CMD 0x06).  Firmwa, Waypoint, RuntimeError

### Community 32 - "Community 32"
Cohesion: 0.12
Nodes (0): 

### Community 33 - "Community 33"
Cohesion: 0.13
Nodes (0): 

### Community 34 - "Community 34"
Cohesion: 0.14
Nodes (16): cw_ccw_ccw, cw_ccw_cw, Motor 1 (Top - Right), Motor 2 (Bottom - Left), Motor 3 (Top - Left), Motor 4 (Bottom - Right), Firmware TIM3 CCR mapping note (BSP/pwm.h, BSP/pwm.c), Motor numbering and rotation note (NOTE/readme.txt) (+8 more)

### Community 35 - "Community 35"
Cohesion: 0.14
Nodes (0): 

### Community 36 - "Community 36"
Cohesion: 0.18
Nodes (13): Autofly_Task, Check_Fly_Mode(), DroneStatus, FlyMode enum, FlyMode_DangerousStop, FlyMode_SDK, FreeRTOS STM32 6-DOF Drone Control Guide, IMU_DataDeal_Task (+5 more)

### Community 37 - "Community 37"
Cohesion: 0.26
Nodes (6): MRAC_Control(), MRAC_GenerateStructuredBasis(), MRAC_Init(), MRAC_ProjectGradient(), MRAC_Reset(), MRAC_UpdateAxis()

### Community 38 - "Community 38"
Cohesion: 0.22
Nodes (11): Connection 1 (fast / 100 Hz), Connection 2 (slow / 20 Hz), JUSTFLOAT CHANNEL MAP - Frame A (100 Hz), JUSTFLOAT CHANNEL MAP - Frame B (20 Hz), mrac_pitch_e, mrac_pitch_theta_0, path.active_path_mode, Simulate UDP port (+3 more)

### Community 39 - "Community 39"
Cohesion: 0.24
Nodes (10): Core Kernel Components, croutine.c, FreeRTOS/Source directory, FreeRTOS/Source/include directory, list.c, FreeRTOS/Source/Portable/MemMang Directory, queue.c, real time kernel port (+2 more)

### Community 40 - "Community 40"
Cohesion: 0.29
Nodes (10): channel_reference.json, Dashboard button "Frame A Workspace", Dashboard button "Frame B Workspace", MAX_NUM_BASIS = 6, stream_a folder, stream_b folder, vofa+.config.json (Stream A), vofa+.config.json (Stream B) (+2 more)

### Community 41 - "Community 41"
Cohesion: 0.44
Nodes (8): decode_stream(), FrameStats, main(), pack_cmd_frame(), print_port_list(), probe_udp_bridge(), run_serial_probe(), xor_crc8()

### Community 42 - "Community 42"
Cohesion: 0.25
Nodes (0): 

### Community 43 - "Community 43"
Cohesion: 0.22
Nodes (9): API/, BSP/, FreeRTOS/, Global_file/, ground_station/, OBJ/, TASK/, USER/ (+1 more)

### Community 44 - "Community 44"
Cohesion: 0.22
Nodes (9): ~/.claude/openrouter_models.json, qwen/qwen3-coder:free, z-ai/glm-4.5-air:free, 2026-04-10 - Free Model Routing System, /free, /free-reason, /free-review, /free-translate (+1 more)

### Community 45 - "Community 45"
Cohesion: 0.28
Nodes (6): ImageMagick, Inkscape, motor_pin_map.png, motor_pin_map.svg, NOTE/README.md, UAV_TUTORIAL.md

### Community 46 - "Community 46"
Cohesion: 0.31
Nodes (9): Beginner-Friendly Explanation, Bit Manipulation & Operators, Key Points Section, Line-by-Line Breakdown, Note Title Format, Obsidian Links, Related Files, USER\Prompt.txt (+1 more)

### Community 47 - "Community 47"
Cohesion: 0.29
Nodes (8): Black, White, Counter‑clockwise (CCW), Clockwise (CW), Motor 1 (top-right), Motor 2 (bottom-left), Motor 3 (top-left), Motor 4 (bottom-right)

### Community 48 - "Community 48"
Cohesion: 0.29
Nodes (7): /free, /free-reason, /free-review, /free-translate, /update-models, Free Model Routing, ~/.claude/openrouter_models.json

### Community 49 - "Community 49"
Cohesion: 0.29
Nodes (3): BSP/BSP.c, Exercise 2 – Heartbeat task (FreeRTOS), vHeartbeatTask

### Community 50 - "Community 50"
Cohesion: 0.29
Nodes (7): Pin PA13 (SWDIO), Pin PA14 (SWCLK), PA13, PA14, SWCLK, SWDIO, 3.3V

### Community 51 - "Community 51"
Cohesion: 0.38
Nodes (7): fast_stream_strategy, full.tabviews.json, mrac_errors.tabviews.json, pid_all.tabviews.json, professional_preset_wiring, slow_stream_strategy, weights.tabviews.json

### Community 52 - "Community 52"
Cohesion: 0.4
Nodes (6): FreeRTOS ARM Cortex-M4F port, ARM Cortex-M7 core, ARM Cortex-M7 core revision r0p1, FreeRTOS ARM Cortex-M7 r0p1 port, /FreeRTOS/Source/portable/RVDS/ARM_CM4F, /FreeRTOS/Source/portable/RVDS/ARM_CM7/r0p1

### Community 53 - "Community 53"
Cohesion: 0.4
Nodes (5): graphify-out/GRAPH_REPORT.md, graphify-out/, graphify, python3 -c "from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))", graphify-out/wiki/index.md

### Community 54 - "Community 54"
Cohesion: 0.4
Nodes (5): Keil µVision, FreeRTOS, C/C++, Project Stack, UAV / Six Degrees of Freedom

### Community 55 - "Community 55"
Cohesion: 0.4
Nodes (5): Keil MDK-ARM µVision 5, FreeRTOS---Six Degrees of Freedom Initial Code - International Student, ST-Link V2 debugger, STM32F4-based flight controller, USB-to-UART dongle

### Community 56 - "Community 56"
Cohesion: 0.4
Nodes (5): Frame A Workspace, Frame B Workspace, Verify protocol = JustFloat, Verify UDP local port = 1347, Verify UDP local port = 1348

### Community 57 - "Community 57"
Cohesion: 0.6
Nodes (5): FreeRTOS/Source/Portable/[compiler]/[architecture] Directory, compiler, FreeRTOS/Source/Portable/[compiler] Directory, FreeRTOS/Source/Portable directory, microcontroller

### Community 58 - "Community 58"
Cohesion: 0.5
Nodes (4): calibration values, gains, Tuning Parameters, UAV control parameters

### Community 59 - "Community 59"
Cohesion: 0.5
Nodes (4): I0, channel_i2, Tab: A MRAC Error, mrac_pitch_e

### Community 60 - "Community 60"
Cohesion: 1.0
Nodes (2): count_packets(), main()

### Community 61 - "Community 61"
Cohesion: 0.67
Nodes (0): 

### Community 62 - "Community 62"
Cohesion: 0.67
Nodes (3): Exercise 1 – Build tools check, python --version, USER/JX_FLY.uvprojx

### Community 63 - "Community 63"
Cohesion: 0.67
Nodes (3): UART, Exercise 3 – IMU CSV logger, PuTTY

### Community 64 - "Community 64"
Cohesion: 0.67
Nodes (3): PID control, Exercise 5 – Simple PID control test, Global_file/algorithm.c

### Community 65 - "Community 65"
Cohesion: 0.67
Nodes (3): I7, Tab: B Tracking, mrac_yaw_xm

### Community 66 - "Community 66"
Cohesion: 0.67
Nodes (3): ADC1, Pin PA4, File USER/ADC.c

### Community 67 - "Community 67"
Cohesion: 0.67
Nodes (3): matplotlib, numpy, tutorial\requirements.txt

### Community 68 - "Community 68"
Cohesion: 0.67
Nodes (3): File BSP/usart1.c, pa10, File TASK/RemoterTask.c

### Community 69 - "Community 69"
Cohesion: 1.0
Nodes (2): API/GPS.c, GPS Sensor

### Community 70 - "Community 70"
Cohesion: 1.0
Nodes (2): FreeRTOS Configuration, FreeRTOSConfig.h

### Community 71 - "Community 71"
Cohesion: 1.0
Nodes (2): Task Configuration, TASK/ directory

### Community 72 - "Community 72"
Cohesion: 1.0
Nodes (2): Close all VOFA windows, Pre-Setup

### Community 73 - "Community 73"
Cohesion: 1.0
Nodes (2): "Capture A Config" button, _capture_vofa_stream_preset("a")

### Community 74 - "Community 74"
Cohesion: 1.0
Nodes (2): "Capture B Config" button, _capture_vofa_stream_preset("b")

### Community 75 - "Community 75"
Cohesion: 1.0
Nodes (2): BEC at the tail, Power cable at the tail

### Community 76 - "Community 76"
Cohesion: 1.0
Nodes (2): PB6, TIM4 CH1

### Community 77 - "Community 77"
Cohesion: 1.0
Nodes (2): PB7, TIM4 CH2

### Community 78 - "Community 78"
Cohesion: 1.0
Nodes (2): ADC1 CH4, PA4

### Community 79 - "Community 79"
Cohesion: 1.0
Nodes (2): Serial Terminal (PuTTY/Tera Term), uart_logging

### Community 80 - "Community 80"
Cohesion: 1.0
Nodes (2): rationale_for, tutorial_visualizer

### Community 81 - "Community 81"
Cohesion: 1.0
Nodes (2): channel_i8, Tab: A Status

### Community 82 - "Community 82"
Cohesion: 1.0
Nodes (2): channel_i31, var_mrac_z_xm

### Community 83 - "Community 83"
Cohesion: 1.0
Nodes (2): channel_i1, Tab: A MRAC Adaptive

### Community 84 - "Community 84"
Cohesion: 1.0
Nodes (2): File BSP/usart2.c, pa2

### Community 85 - "Community 85"
Cohesion: 1.0
Nodes (0): 

### Community 86 - "Community 86"
Cohesion: 1.0
Nodes (1): Minimal summary: duration, numeric ranges for mrac.pitch.e, pid.z_rate FB.

### Community 87 - "Community 87"
Cohesion: 1.0
Nodes (1): Session State

### Community 88 - "Community 88"
Cohesion: 1.0
Nodes (1): BSP/spi.c

### Community 89 - "Community 89"
Cohesion: 1.0
Nodes (1): BSP/usart.c

### Community 90 - "Community 90"
Cohesion: 1.0
Nodes (1): Global_file/global_declare.h

### Community 91 - "Community 91"
Cohesion: 1.0
Nodes (1): Global_file/global_declare.c

### Community 92 - "Community 92"
Cohesion: 1.0
Nodes (1): FreeRTOS kernel sources

### Community 93 - "Community 93"
Cohesion: 1.0
Nodes (1): Architecture Overview

### Community 94 - "Community 94"
Cohesion: 1.0
Nodes (1): Configuration Reference

### Community 95 - "Community 95"
Cohesion: 1.0
Nodes (0): 

### Community 96 - "Community 96"
Cohesion: 1.0
Nodes (1): STM32F407ZGTx MCU

### Community 97 - "Community 97"
Cohesion: 1.0
Nodes (1): Flight Controller (STM32F407ZGTx)

## Knowledge Gaps
- **191 isolated node(s):** `Simple IMU CSV visualizer.  Input CSV expected columns (header optional): time`, `Synthetic UART4 telemetry generator for offline testing.  Sends Frame A / Fram`, `Same wire format as TASK/send_data.c: 16-bit LEN, then payload + XOR CRC8.`, `8 floats (sine, distinct Hz) + ARM + FlyMode + sbus_lost + TWC flags; LEN = 37.`, `MRAC: 4 axes * (N theta + u_nom + xm) + 12 PID * (FB, Des, U).     Theta: calle` (+186 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 69`** (2 nodes): `API/GPS.c`, `GPS Sensor`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 70`** (2 nodes): `FreeRTOS Configuration`, `FreeRTOSConfig.h`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 71`** (2 nodes): `Task Configuration`, `TASK/ directory`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 72`** (2 nodes): `Close all VOFA windows`, `Pre-Setup`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 73`** (2 nodes): `"Capture A Config" button`, `_capture_vofa_stream_preset("a")`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 74`** (2 nodes): `"Capture B Config" button`, `_capture_vofa_stream_preset("b")`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 75`** (2 nodes): `BEC at the tail`, `Power cable at the tail`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 76`** (2 nodes): `PB6`, `TIM4 CH1`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 77`** (2 nodes): `PB7`, `TIM4 CH2`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 78`** (2 nodes): `ADC1 CH4`, `PA4`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 79`** (2 nodes): `Serial Terminal (PuTTY/Tera Term)`, `uart_logging`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 80`** (2 nodes): `rationale_for`, `tutorial_visualizer`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 81`** (2 nodes): `channel_i8`, `Tab: A Status`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 82`** (2 nodes): `channel_i31`, `var_mrac_z_xm`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 83`** (2 nodes): `channel_i1`, `Tab: A MRAC Adaptive`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 84`** (2 nodes): `File BSP/usart2.c`, `pa2`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 85`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 86`** (1 nodes): `Minimal summary: duration, numeric ranges for mrac.pitch.e, pid.z_rate FB.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 87`** (1 nodes): `Session State`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 88`** (1 nodes): `BSP/spi.c`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 89`** (1 nodes): `BSP/usart.c`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 90`** (1 nodes): `Global_file/global_declare.h`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 91`** (1 nodes): `Global_file/global_declare.c`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 92`** (1 nodes): `FreeRTOS kernel sources`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 93`** (1 nodes): `Architecture Overview`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 94`** (1 nodes): `Configuration Reference`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 95`** (1 nodes): `channel_map.txt`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 96`** (1 nodes): `STM32F407ZGTx MCU`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 97`** (1 nodes): `Flight Controller (STM32F407ZGTx)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Dashboard` connect `Community 1` to `Community 12`?**
  _High betweenness centrality (0.093) - this node is a cross-community bridge._
- **Why does `SerialBridge` connect `Community 12` to `Community 1`?**
  _High betweenness centrality (0.034) - this node is a cross-community bridge._
- **Why does `BSP/pwm.c` connect `Community 10` to `Community 2`?**
  _High betweenness centrality (0.023) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `Dashboard` (e.g. with `SerialBridge` and `main()`) actually correct?**
  _`Dashboard` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 15 inferred relationships involving `SerialBridge` (e.g. with `start_bridge_in_background()` and `UdpBridgeClient`) actually correct?**
  _`SerialBridge` has 15 INFERRED edges - model-reasoned connections that need verification._
- **Are the 14 inferred relationships involving `FlightLogger` (e.g. with `UdpBridgeClient` and `DebouncedSender`) actually correct?**
  _`FlightLogger` has 14 INFERRED edges - model-reasoned connections that need verification._
- **Are the 16 inferred relationships involving `FLASH_WaitForLastOperation()` (e.g. with `FLASH_EraseSector()` and `FLASH_EraseAllSectors()`) actually correct?**
  _`FLASH_WaitForLastOperation()` has 16 INFERRED edges - model-reasoned connections that need verification._