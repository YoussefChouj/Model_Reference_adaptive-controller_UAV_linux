# Graph Report - .  (2026-04-13)

## Corpus Check
- Large corpus: 260 files · ~479,398 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder, or use --no-semantic to run AST-only.

## Summary
- 1890 nodes · 2700 edges · 84 communities detected
- Extraction: 76% EXTRACTED · 24% INFERRED · 0% AMBIGUOUS · INFERRED: 638 edges (avg confidence: 0.54)
- Token cost: 0 input · 0 output

## God Nodes (most connected - your core abstractions)
1. `Dashboard` - 111 edges
2. `SerialBridge` - 43 edges
3. `Stabilizer Task (200 Hz)` - 22 edges
4. `FlightLogger` - 19 edges
5. `Autofly Task (100 Hz)` - 19 edges
6. `FLASH_WaitForLastOperation()` - 17 edges
7. `main()` - 15 edges
8. `Virtual RC Gating by SBUS Loss and SDK Mode` - 15 edges
9. `Ground Station Binary Protocol with XOR CRC` - 15 edges
10. `Multi-rate FreeRTOS Task Partitioning` - 13 edges

## Surprising Connections (you probably didn't know these)
- `Virtual RC Authority` --reads_from--> `FlyMode`  [INFERRED]
  wiki\index.md → wiki\concepts\virtual-rc-authority.md
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
Cohesion: 0.03
Nodes (56): AnoOF_DataAnl(), AnoOF_GetOneByte(), AutoflyTask(), AutoflyTask_PathArbitrate(), AutoflyTask_RunCircle(), AutoflyTask_RunSinusoid(), SDK_StateMachine_Init(), SDK_StateMachine_Loop() (+48 more)

### Community 1 - "Community 1"
Cohesion: 0.03
Nodes (30): Dashboard, DebouncedSender, dump_preset_yaml(), _format_inline_map(), load_preset_yaml(), main(), _parse_inline_map(), _parse_inline_value() (+22 more)

### Community 2 - "Community 2"
Cohesion: 0.03
Nodes (30): prvCheckDelayedList(), prvCheckPendingReadyList(), prvInitialiseCoRoutineLists(), vCoRoutineSchedule(), xCoRoutineCreate(), prvTestWaitCondition(), vEventGroupClearBitsCallback(), vEventGroupSetBitsCallback() (+22 more)

### Community 3 - "Community 3"
Cohesion: 0.03
Nodes (95): Abort Logic, Attitude Estimation, Autofly Task (100 Hz), autoflytask_patharbitrange, AutoflyTask_PathArbitrate, Autonomous Path Generation, Circle, Circle Path Family (+87 more)

### Community 4 - "Community 4"
Cohesion: 0.03
Nodes (16): TI1_Config(), TI2_Config(), TI3_Config(), TI4_Config(), TIM_ETRClockMode1Config(), TIM_ETRClockMode2Config(), TIM_ETRConfig(), TIM_ICInit() (+8 more)

### Community 5 - "Community 5"
Cohesion: 0.02
Nodes (2): RCC_GetFlagStatus(), RCC_WaitForHSEStartUp()

### Community 6 - "Community 6"
Cohesion: 0.02
Nodes (0): 

### Community 7 - "Community 7"
Cohesion: 0.04
Nodes (43): eTaskGetState(), prvAddCurrentTaskToDelayedList(), prvAddNewTaskToReadyList(), prvCheckTasksWaitingTermination(), prvDeleteTCB(), prvInitialiseNewTask(), prvInitialiseTaskLists(), prvListTasksWithinSingleList() (+35 more)

### Community 8 - "Community 8"
Cohesion: 0.03
Nodes (67): Arming Logic, Command 0x06 Virtual Sticks, CMD_ID, Command ID 0x06 Virtual Stick Write, Command 0x06, Command Frame, Command Framing, Command ID (+59 more)

### Community 9 - "Community 9"
Cohesion: 0.05
Nodes (44): load_flight_data(), main(), plot_mrac_adaptive(), plot_tracking(), Read the flat t,frame,key,value format and rebuild into time series., _save(), analyze_weights(), build_json_record() (+36 more)

### Community 10 - "Community 10"
Cohesion: 0.05
Nodes (18): RTC_Bcd2ToByte(), RTC_ByteToBcd2(), RTC_CoarseCalibCmd(), RTC_CoarseCalibConfig(), RTC_DeInit(), RTC_EnterInitMode(), RTC_ExitInitMode(), RTC_GetAlarm() (+10 more)

### Community 11 - "Community 11"
Cohesion: 0.04
Nodes (2): NVIC_SetPriority(), SysTick_Config()

### Community 12 - "Community 12"
Cohesion: 0.06
Nodes (24): DebouncedSender, send_ground_station_commands_to_a_running_serial_bridge_process, load_config(), _main_cli(), _parse_simple_yaml(), CRC8 in this project is an XOR checksum over bytes.     Matches the C code:, FireWater / CSV channel names: dots -> underscores (mrac.pitch.e -> mrac_pitch_e, Latest decoded Frame A / Frame B variables (thread-safe, for GUI + logging). (+16 more)

### Community 13 - "Community 13"
Cohesion: 0.04
Nodes (0): 

### Community 14 - "Community 14"
Cohesion: 0.07
Nodes (31): prvCopyDataFromQueue(), prvCopyDataToQueue(), prvInitialiseMutex(), prvInitialiseNewQueue(), prvIsQueueEmpty(), prvIsQueueFull(), prvNotifyQueueSetContainer(), prvUnlockQueue() (+23 more)

### Community 15 - "Community 15"
Cohesion: 0.07
Nodes (17): FLASH_EraseAllBank1Sectors(), FLASH_EraseAllBank2Sectors(), FLASH_EraseAllSectors(), FLASH_EraseSector(), FLASH_GetStatus(), FLASH_OB_Launch(), FLASH_OB_PCROP1Config(), FLASH_OB_PCROPConfig() (+9 more)

### Community 16 - "Community 16"
Cohesion: 0.05
Nodes (0): 

### Community 17 - "Community 17"
Cohesion: 0.06
Nodes (0): 

### Community 18 - "Community 18"
Cohesion: 0.06
Nodes (0): 

### Community 19 - "Community 19"
Cohesion: 0.07
Nodes (0): 

### Community 20 - "Community 20"
Cohesion: 0.07
Nodes (0): 

### Community 21 - "Community 21"
Cohesion: 0.07
Nodes (0): 

### Community 22 - "Community 22"
Cohesion: 0.07
Nodes (0): 

### Community 23 - "Community 23"
Cohesion: 0.08
Nodes (2): CAN_GetITStatus(), CheckITStatus()

### Community 24 - "Community 24"
Cohesion: 0.08
Nodes (0): 

### Community 25 - "Community 25"
Cohesion: 0.08
Nodes (0): 

### Community 26 - "Community 26"
Cohesion: 0.08
Nodes (0): 

### Community 27 - "Community 27"
Cohesion: 0.14
Nodes (14): prvCheckForValidListAndQueue(), prvGetNextExpireTime(), prvInitialiseNewTimer(), prvInsertTimerInActiveList(), prvProcessExpiredTimer(), prvProcessReceivedCommands(), prvProcessTimerOrBlockTask(), prvSampleTimeNow() (+6 more)

### Community 28 - "Community 28"
Cohesion: 0.11
Nodes (0): 

### Community 29 - "Community 29"
Cohesion: 0.11
Nodes (0): 

### Community 30 - "Community 30"
Cohesion: 0.15
Nodes (19): API/imu_update.c, BSP/pwm.c, BSP/usart4.c, BSP/usart5.c, ground_station/comm/serial_bridge.py, CRC8_XOR, Ground-Station Command Frame, CRC8_XOR (+11 more)

### Community 31 - "Community 31"
Cohesion: 0.15
Nodes (5): PathExecutor, PositionSourceError, Ground-station path follower: 10 Hz virtual stick commands (CMD 0x06).  Firmwa, Waypoint, RuntimeError

### Community 32 - "Community 32"
Cohesion: 0.13
Nodes (0): 

### Community 33 - "Community 33"
Cohesion: 0.14
Nodes (0): 

### Community 34 - "Community 34"
Cohesion: 0.17
Nodes (15): _capture_vofa_stream_preset function, ground_station/gui/dashboard.py, Frame A, Frame B, _open_plot function, OPENROUTER_API_KEY environment variable, ~/.claude/openrouter_models.json, presets/vofa/stream_a/vofa+.config.json (+7 more)

### Community 35 - "Community 35"
Cohesion: 0.26
Nodes (6): MRAC_Control(), MRAC_GenerateStructuredBasis(), MRAC_Init(), MRAC_ProjectGradient(), MRAC_Reset(), MRAC_UpdateAxis()

### Community 36 - "Community 36"
Cohesion: 0.2
Nodes (11): Ground-Station Binary Protocol, Multi-rate Task Partitioning, Path Arbitration, Virtual RC Authority, AutoflyTask, Ground Station Bridge, IMU Update, Motor Mixer (+3 more)

### Community 37 - "Community 37"
Cohesion: 0.44
Nodes (8): decode_stream(), FrameStats, main(), pack_cmd_frame(), print_port_list(), probe_udp_bridge(), run_serial_probe(), xor_crc8()

### Community 38 - "Community 38"
Cohesion: 0.25
Nodes (8): Control Loop Timing, Autofly Task, Ground Station Bridge, IMU Update, Motor Mixer, Stabilizer Task, Ingest Cross-Subsystem Interfaces 2026-04-13, Cross‑Subsystem Interfaces Source

### Community 39 - "Community 39"
Cohesion: 0.29
Nodes (7): agent_reports, checker.py, Claude Code, Copilot, Deterministic Checker, Free Model Routing, implementer.py

### Community 40 - "Community 40"
Cohesion: 0.43
Nodes (7): Ground Station Binary Protocol, Multi‑Rate Task Partitioning, Path Arbitration, Virtual RC Authority, Ingest Architectural Decisions 2026-04-13, Init 2026-04-13, Architectural Decisions Source

### Community 41 - "Community 41"
Cohesion: 0.6
Nodes (2): raw directory, README

### Community 42 - "Community 42"
Cohesion: 0.5
Nodes (4): Arming/Disarming, Dangerous Stop Behavior, RC Failover, Safety and Authority Management

### Community 43 - "Community 43"
Cohesion: 0.5
Nodes (4): Autonomous Path Behaviors, Circular Path, Sinusoidal Path, Target Point Path

### Community 44 - "Community 44"
Cohesion: 0.5
Nodes (4): Python Ground‑Station Communication Bridge, Serial Parsing, UDP Mirroring, VOFA Streaming

### Community 45 - "Community 45"
Cohesion: 0.5
Nodes (4): Actuator, Controller, Parameter, Sensor

### Community 46 - "Community 46"
Cohesion: 1.0
Nodes (2): count_packets(), main()

### Community 47 - "Community 47"
Cohesion: 0.67
Nodes (0): 

### Community 48 - "Community 48"
Cohesion: 0.67
Nodes (3): Control Loop Task, dt Constant, IF-06: Timing Contract

### Community 49 - "Community 49"
Cohesion: 1.0
Nodes (2): Model Registry, Rate Limits

### Community 50 - "Community 50"
Cohesion: 1.0
Nodes (2): Peripheral Integration, STM32F4 Embedded Firmware Architecture

### Community 51 - "Community 51"
Cohesion: 1.0
Nodes (2): Flight Control Task, FreeRTOS Multi-Rate Task Scheduling

### Community 52 - "Community 52"
Cohesion: 1.0
Nodes (0): 

### Community 53 - "Community 53"
Cohesion: 1.0
Nodes (0): 

### Community 54 - "Community 54"
Cohesion: 1.0
Nodes (1): Minimal summary: duration, numeric ranges for mrac.pitch.e, pid.z_rate FB.

### Community 55 - "Community 55"
Cohesion: 1.0
Nodes (1): Session State

### Community 56 - "Community 56"
Cohesion: 1.0
Nodes (1): 2026-04-11

### Community 57 - "Community 57"
Cohesion: 1.0
Nodes (1): Investigate and fix why the drone motors do not move when commanded via Virtual RC / Paths in SDK Mode

### Community 58 - "Community 58"
Cohesion: 1.0
Nodes (1): Graphify Knowledge Graph

### Community 59 - "Community 59"
Cohesion: 1.0
Nodes (1): Multi-Agent Workflow

### Community 60 - "Community 60"
Cohesion: 1.0
Nodes (1): log_lesson.py

### Community 61 - "Community 61"
Cohesion: 1.0
Nodes (1): lessons.jsonl

### Community 62 - "Community 62"
Cohesion: 1.0
Nodes (1): costs.jsonl

### Community 63 - "Community 63"
Cohesion: 1.0
Nodes (1): agent_contracts

### Community 64 - "Community 64"
Cohesion: 1.0
Nodes (1): Free Model Routing Skills

### Community 65 - "Community 65"
Cohesion: 1.0
Nodes (1): /free-translate skill

### Community 66 - "Community 66"
Cohesion: 1.0
Nodes (1): /free-reason skill

### Community 67 - "Community 67"
Cohesion: 1.0
Nodes (1): CMD_ID

### Community 68 - "Community 68"
Cohesion: 1.0
Nodes (1): INDEX

### Community 69 - "Community 69"
Cohesion: 1.0
Nodes (1): VALUE

### Community 70 - "Community 70"
Cohesion: 1.0
Nodes (1): frame_type

### Community 71 - "Community 71"
Cohesion: 1.0
Nodes (1): payload length

### Community 72 - "Community 72"
Cohesion: 1.0
Nodes (1): MAX_NUM_BASIS

### Community 73 - "Community 73"
Cohesion: 1.0
Nodes (1): CRC8_XOR

### Community 74 - "Community 74"
Cohesion: 1.0
Nodes (1): payload length

### Community 75 - "Community 75"
Cohesion: 1.0
Nodes (1): MAX_NUM_BASIS

### Community 76 - "Community 76"
Cohesion: 1.0
Nodes (1): 3000

### Community 77 - "Community 77"
Cohesion: 1.0
Nodes (1): Multi-Rate Task Partitioning

### Community 78 - "Community 78"
Cohesion: 1.0
Nodes (1): Ground Station Binary Protocol

### Community 79 - "Community 79"
Cohesion: 1.0
Nodes (1): Virtual RC Authority

### Community 80 - "Community 80"
Cohesion: 1.0
Nodes (1): Path Arbitration

### Community 81 - "Community 81"
Cohesion: 1.0
Nodes (1): Control Loop Timing

### Community 82 - "Community 82"
Cohesion: 1.0
Nodes (1): Protocol

### Community 83 - "Community 83"
Cohesion: 1.0
Nodes (1): FlyMode_SDK

## Ambiguous Edges - Review These
- `Monitor Task (1 Hz)` → `safety_limit`  [AMBIGUOUS]
  wiki\overview.md · relation: safety_critical_for

## Knowledge Gaps
- **175 isolated node(s):** `Synthetic UART4 telemetry generator for offline testing.  Sends Frame A / Fram`, `Same wire format as TASK/send_data.c: 16-bit LEN, then payload + XOR CRC8.`, `8 floats (sine, distinct Hz) + ARM + FlyMode + sbus_lost + TWC flags; LEN = 37.`, `MRAC: 4 axes * (N theta + u_nom + xm) + 12 PID * (FB, Des, U).     Theta: calle`, `Minimal YAML parser for simple "key: value" files (no nesting).     This avoids` (+170 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 49`** (2 nodes): `Model Registry`, `Rate Limits`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 50`** (2 nodes): `Peripheral Integration`, `STM32F4 Embedded Firmware Architecture`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 51`** (2 nodes): `Flight Control Task`, `FreeRTOS Multi-Rate Task Scheduling`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 52`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 53`** (1 nodes): `visualize_imu.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 54`** (1 nodes): `Minimal summary: duration, numeric ranges for mrac.pitch.e, pid.z_rate FB.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 55`** (1 nodes): `Session State`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 56`** (1 nodes): `2026-04-11`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 57`** (1 nodes): `Investigate and fix why the drone motors do not move when commanded via Virtual RC / Paths in SDK Mode`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 58`** (1 nodes): `Graphify Knowledge Graph`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 59`** (1 nodes): `Multi-Agent Workflow`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 60`** (1 nodes): `log_lesson.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 61`** (1 nodes): `lessons.jsonl`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 62`** (1 nodes): `costs.jsonl`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 63`** (1 nodes): `agent_contracts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 64`** (1 nodes): `Free Model Routing Skills`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 65`** (1 nodes): `/free-translate skill`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 66`** (1 nodes): `/free-reason skill`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 67`** (1 nodes): `CMD_ID`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 68`** (1 nodes): `INDEX`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 69`** (1 nodes): `VALUE`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 70`** (1 nodes): `frame_type`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 71`** (1 nodes): `payload length`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 72`** (1 nodes): `MAX_NUM_BASIS`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 73`** (1 nodes): `CRC8_XOR`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 74`** (1 nodes): `payload length`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 75`** (1 nodes): `MAX_NUM_BASIS`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 76`** (1 nodes): `3000`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 77`** (1 nodes): `Multi-Rate Task Partitioning`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 78`** (1 nodes): `Ground Station Binary Protocol`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 79`** (1 nodes): `Virtual RC Authority`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 80`** (1 nodes): `Path Arbitration`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 81`** (1 nodes): `Control Loop Timing`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 82`** (1 nodes): `Protocol`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 83`** (1 nodes): `FlyMode_SDK`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `Monitor Task (1 Hz)` and `safety_limit`?**
  _Edge tagged AMBIGUOUS (relation: safety_critical_for) - confidence is low._
- **Why does `Dashboard` connect `Community 1` to `Community 12`?**
  _High betweenness centrality (0.106) - this node is a cross-community bridge._
- **Why does `Virtual RC Authority` connect `Community 3` to `Community 0`, `Community 8`?**
  _High betweenness centrality (0.052) - this node is a cross-community bridge._
- **Why does `Stabilizer Task (200 Hz)` connect `Community 3` to `Community 0`, `Community 35`?**
  _High betweenness centrality (0.048) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `Dashboard` (e.g. with `SerialBridge` and `main()`) actually correct?**
  _`Dashboard` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 15 inferred relationships involving `SerialBridge` (e.g. with `start_bridge_in_background()` and `UdpBridgeClient`) actually correct?**
  _`SerialBridge` has 15 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `Stabilizer Task (200 Hz)` (e.g. with `Virtual RC Authority` and `imu_update.c`) actually correct?**
  _`Stabilizer Task (200 Hz)` has 11 INFERRED edges - model-reasoned connections that need verification._