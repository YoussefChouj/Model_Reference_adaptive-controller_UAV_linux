# Graph Report - .  (2026-04-15)

## Corpus Check
- Large corpus: 297 files · ~512,566 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder, or use --no-semantic to run AST-only.

## Summary
- 2201 nodes · 3207 edges · 92 communities detected
- Extraction: 77% EXTRACTED · 23% INFERRED · 0% AMBIGUOUS · INFERRED: 725 edges (avg confidence: 0.56)
- Token cost: 0 input · 0 output

## God Nodes (most connected - your core abstractions)
1. `Dashboard` - 111 edges
2. `SerialBridge` - 43 edges
3. `StabilizerTask` - 39 edges
4. `AutoflyTask` - 24 edges
5. `Mahony Filter` - 21 edges
6. `Ground Station Dashboard` - 21 edges
7. `RemoterTask` - 20 edges
8. `FlightLogger` - 19 edges
9. `FLASH_WaitForLastOperation()` - 17 edges
10. `PID Controller` - 16 edges

## Surprising Connections (you probably didn't know these)
- `AutoflyTask PathArbitrate` --controls--> `TWC Path Family`  [INFERRED]
  TASK/AutoflyTask.c → wiki\concepts\path-arbitration.md
- `AutoflyTask PathArbitrate` --controls--> `Circle Path Family`  [INFERRED]
  TASK/AutoflyTask.c → wiki\concepts\path-arbitration.md
- `AutoflyTask PathArbitrate` --safety_critical_for--> `Single Active Path Arbitration`  [EXTRACTED]
  TASK/AutoflyTask.c → wiki\sources\architectural-decisions.md
- `Main Task` --gates--> `Persistence Task`  [INFERRED]
  USER/main.c → wiki\entities\flash-memory.md
- `USE_UNSTRUCTURED_UNCERTAINTY Flag` --must_match--> `Radial Basis Function (RBF) Basis`  [INFERRED]
  mrac.h → wiki\sources\adaptive-control-tutorial-notebook.md

## Communities

### Community 0 - "Community 0"
Cohesion: 0.02
Nodes (67): AnoOF_DataAnl(), AnoOF_GetOneByte(), bmi088_init(), BMI088_Read_Acc_Data(), BMI088_Read_Gyro_Data(), BMI088_Write_Acc_Data(), BMI088_Write_Gyro_Data(), Butterworth30HzLPF() (+59 more)

### Community 1 - "Community 1"
Cohesion: 0.02
Nodes (129): Kd_locx, Ki_locx, Kp_Z_pos, Kp_Z_rate, Kp_gyrox, Kp_locx, Kp_locxs, Kp_pitch (+121 more)

### Community 2 - "Community 2"
Cohesion: 0.03
Nodes (15): Dashboard, DebouncedSender, main(), Load a config.yaml that is only flat 'key: value' entries.     This matches how, Abort paths (0x0D) then dangerous stop (0x04), 50 ms apart., Single Z-rate PID (firmware axis index 6). CMD 0x01 index = 6*3 + gain., Resolve VOFA workspace path across legacy .vofa and newer .tabviews.json formats, Kill only the target stream's VOFA process, leaving the other stream alive. (+7 more)

### Community 3 - "Community 3"
Cohesion: 0.03
Nodes (44): prvCheckDelayedList(), prvCheckPendingReadyList(), prvInitialiseCoRoutineLists(), vCoRoutineSchedule(), xCoRoutineCreate(), prvTestWaitCondition(), vEventGroupClearBitsCallback(), vEventGroupSetBitsCallback() (+36 more)

### Community 4 - "Community 4"
Cohesion: 0.03
Nodes (115): Actuator, Actuator + mixer dynamics, Adaptive Control Term (UAD), Adaptive control u_ad, Adaptive Controller, Adaptive Law Update, Adaptive law ADP, Adaptive Control Output (u_ad) (+107 more)

### Community 5 - "Community 5"
Cohesion: 0.02
Nodes (2): RCC_GetFlagStatus(), RCC_WaitForHSEStartUp()

### Community 6 - "Community 6"
Cohesion: 0.03
Nodes (72): Analyze Flight Log Script, ARM Status, baud_rate, Bench Status, CMD 0x04 idx 0, CMD 0x04 idx 1, cmd_udp_port, Configuration YAML (+64 more)

### Community 7 - "Community 7"
Cohesion: 0.02
Nodes (2): CAN_GetITStatus(), CheckITStatus()

### Community 8 - "Community 8"
Cohesion: 0.03
Nodes (16): TI1_Config(), TI2_Config(), TI3_Config(), TI4_Config(), TIM_ETRClockMode1Config(), TIM_ETRClockMode2Config(), TIM_ETRConfig(), TIM_ICInit() (+8 more)

### Community 9 - "Community 9"
Cohesion: 0.04
Nodes (43): eTaskGetState(), prvAddCurrentTaskToDelayedList(), prvAddNewTaskToReadyList(), prvCheckTasksWaitingTermination(), prvDeleteTCB(), prvInitialiseNewTask(), prvInitialiseTaskLists(), prvListTasksWithinSingleList() (+35 more)

### Community 10 - "Community 10"
Cohesion: 0.03
Nodes (76): 115200 baud, CMD_ID, Command 0x06, Command Frame, Command ID 0x01, Command ID 0x02, CRC8_XOR (Command), CRC8_XOR (Telemetry) (+68 more)

### Community 11 - "Community 11"
Cohesion: 0.05
Nodes (18): RTC_Bcd2ToByte(), RTC_ByteToBcd2(), RTC_CoarseCalibCmd(), RTC_CoarseCalibConfig(), RTC_DeInit(), RTC_EnterInitMode(), RTC_ExitInitMode(), RTC_GetAlarm() (+10 more)

### Community 12 - "Community 12"
Cohesion: 0.04
Nodes (2): NVIC_SetPriority(), SysTick_Config()

### Community 13 - "Community 13"
Cohesion: 0.06
Nodes (40): load_flight_data(), main(), plot_mrac_adaptive(), plot_tracking(), Read the flat t,frame,key,value format and rebuild into time series., _save(), analyze_weights(), build_json_record() (+32 more)

### Community 14 - "Community 14"
Cohesion: 0.04
Nodes (0): 

### Community 15 - "Community 15"
Cohesion: 0.06
Nodes (50): ARMED, Check_Fly_Mode(), CMD 0x04, CMD 0x06, CMD 0x0E, Command 0x0E (Arm), Command 0x04 (Set SDK Mode), Command 0x06 (Throttle) (+42 more)

### Community 16 - "Community 16"
Cohesion: 0.07
Nodes (31): prvCopyDataFromQueue(), prvCopyDataToQueue(), prvInitialiseMutex(), prvInitialiseNewQueue(), prvIsQueueEmpty(), prvIsQueueFull(), prvNotifyQueueSetContainer(), prvUnlockQueue() (+23 more)

### Community 17 - "Community 17"
Cohesion: 0.07
Nodes (17): FLASH_EraseAllBank1Sectors(), FLASH_EraseAllBank2Sectors(), FLASH_EraseAllSectors(), FLASH_EraseSector(), FLASH_GetStatus(), FLASH_OB_Launch(), FLASH_OB_PCROP1Config(), FLASH_OB_PCROPConfig() (+9 more)

### Community 18 - "Community 18"
Cohesion: 0.05
Nodes (0): 

### Community 19 - "Community 19"
Cohesion: 0.06
Nodes (0): 

### Community 20 - "Community 20"
Cohesion: 0.06
Nodes (0): 

### Community 21 - "Community 21"
Cohesion: 0.07
Nodes (0): 

### Community 22 - "Community 22"
Cohesion: 0.07
Nodes (0): 

### Community 23 - "Community 23"
Cohesion: 0.07
Nodes (0): 

### Community 24 - "Community 24"
Cohesion: 0.09
Nodes (24): count_packets(), main(), decode_stream(), FrameStats, main(), pack_cmd_frame(), print_port_list(), probe_udp_bridge() (+16 more)

### Community 25 - "Community 25"
Cohesion: 0.16
Nodes (29): Accelerometer, Time Step (dt), ex, exInt, ey, eyInt, ez, ezInt (+21 more)

### Community 26 - "Community 26"
Cohesion: 0.07
Nodes (0): 

### Community 27 - "Community 27"
Cohesion: 0.08
Nodes (0): 

### Community 28 - "Community 28"
Cohesion: 0.08
Nodes (0): 

### Community 29 - "Community 29"
Cohesion: 0.08
Nodes (0): 

### Community 30 - "Community 30"
Cohesion: 0.11
Nodes (0): 

### Community 31 - "Community 31"
Cohesion: 0.11
Nodes (0): 

### Community 32 - "Community 32"
Cohesion: 0.12
Nodes (20): Decode_RX_Data_t265, DrvSbusGetOneByte, Handle_UART4_GroundStation_Command, Handle_UART5_GroundStation_Command, Process_GroundStation_Command, USART_Receive, cmd_queue (ring buffer), linux_data.* (+12 more)

### Community 33 - "Community 33"
Cohesion: 0.12
Nodes (0): 

### Community 34 - "Community 34"
Cohesion: 0.15
Nodes (5): PathExecutor, PositionSourceError, Ground-station path follower: 10 Hz virtual stick commands (CMD 0x06).  Firmwa, Waypoint, RuntimeError

### Community 35 - "Community 35"
Cohesion: 0.13
Nodes (0): 

### Community 36 - "Community 36"
Cohesion: 0.14
Nodes (15): CMD ID 0x0F, Command 0x0F, Dashboard UI, Process_GroundStation_Command(), Index 0, Index 1, my_new_param_a, my_new_param_b (+7 more)

### Community 37 - "Community 37"
Cohesion: 0.18
Nodes (15): Motor Actuator, Cascaded PID Controller, Inner Loop Error, Outer Loop Error, Inner PID Loop, Kd (Inner), Kd (Outer), Ki (Inner) (+7 more)

### Community 38 - "Community 38"
Cohesion: 0.15
Nodes (13): Clear_Structure Function, ComputePID Function, ComputePID_locx Function, ComputePID_locy Function, ComputeYawPID Function, Kd Gain, Ki Gain, Kp Gain (+5 more)

### Community 39 - "Community 39"
Cohesion: 0.18
Nodes (12): Control Loop Timing, Ground-Station Binary Protocol, Multi-rate Task Partitioning, Path Arbitration, Virtual RC Authority, AutoflyTask, Ground Station Bridge, IMU Update (+4 more)

### Community 40 - "Community 40"
Cohesion: 0.25
Nodes (0): 

### Community 41 - "Community 41"
Cohesion: 0.25
Nodes (8): Barrier Function, Derivative-Free Adaptive Controller, Integral Nominal Adaptive Controller, Low-Frequency-Learning Adaptive Controller, PID-Style Adaptive Controller, Set-Theoretic Neuro-Adaptive Controller, Simulation Time Step (dt), Uncertainty Switch Logic

### Community 42 - "Community 42"
Cohesion: 0.5
Nodes (5): TIM5_Configuration, safety_limit_timestamp_wrap, SPI1 (BMI088 IMU), IMU Read Task, TIM5

### Community 43 - "Community 43"
Cohesion: 0.5
Nodes (4): DMA1_Stream3_IRQHandler, UART4 NVIC Priority (0,0), UART5 NVIC Priority (2,0), DMA1_Stream3_IRQHandler Safety

### Community 44 - "Community 44"
Cohesion: 0.83
Nodes (4): PWM_TIM4_Init, GPIOB Pin6 (Roll Servo), GPIOB Pin7 (Pitch Servo), TIM4

### Community 45 - "Community 45"
Cohesion: 0.5
Nodes (4): APB1 Clock Enable for TIM3, PWM_TIM3_Init Function, TIM Period (10000-1), TIM Prescaler (42-1)

### Community 46 - "Community 46"
Cohesion: 0.67
Nodes (0): 

### Community 47 - "Community 47"
Cohesion: 0.67
Nodes (3): GPS Module, USART6, usart6_irq_handler

### Community 48 - "Community 48"
Cohesion: 1.0
Nodes (2): Command ID, MRAC_UpdateAxis

### Community 49 - "Community 49"
Cohesion: 1.0
Nodes (2): cmd_host, dashboard._send_cmd

### Community 50 - "Community 50"
Cohesion: 1.0
Nodes (2): AnoOF_GetOneByte, USART2_IRQHandler

### Community 51 - "Community 51"
Cohesion: 1.0
Nodes (2): autoflytask_patharbitrange, Sinusoid Path Family

### Community 52 - "Community 52"
Cohesion: 1.0
Nodes (2): serial_bridge._rx_loop_udp, simulate_udp_port

### Community 53 - "Community 53"
Cohesion: 1.0
Nodes (0): 

### Community 54 - "Community 54"
Cohesion: 1.0
Nodes (0): 

### Community 55 - "Community 55"
Cohesion: 1.0
Nodes (1): Minimal summary: duration, numeric ranges for mrac.pitch.e, pid.z_rate FB.

### Community 56 - "Community 56"
Cohesion: 1.0
Nodes (1): Multi-Rate Task Partitioning

### Community 57 - "Community 57"
Cohesion: 1.0
Nodes (1): Ground Station Binary Protocol

### Community 58 - "Community 58"
Cohesion: 1.0
Nodes (1): Virtual RC Authority

### Community 59 - "Community 59"
Cohesion: 1.0
Nodes (1): Path Arbitration

### Community 60 - "Community 60"
Cohesion: 1.0
Nodes (1): Control Loop Timing

### Community 61 - "Community 61"
Cohesion: 1.0
Nodes (1): Protocol

### Community 62 - "Community 62"
Cohesion: 1.0
Nodes (1): FlyMode_SDK

### Community 63 - "Community 63"
Cohesion: 1.0
Nodes (1): GPS Stub

### Community 64 - "Community 64"
Cohesion: 1.0
Nodes (1): SBUS Receiver

### Community 65 - "Community 65"
Cohesion: 1.0
Nodes (1): xm (reference model state)

### Community 66 - "Community 66"
Cohesion: 1.0
Nodes (1): Ctrler

### Community 67 - "Community 67"
Cohesion: 1.0
Nodes (1): Ctrler.Z_posPID (Altitude PID)

### Community 68 - "Community 68"
Cohesion: 1.0
Nodes (1): USART6_IRQHandler

### Community 69 - "Community 69"
Cohesion: 1.0
Nodes (1): PID Loop

### Community 70 - "Community 70"
Cohesion: 1.0
Nodes (1): e_deadzone

### Community 71 - "Community 71"
Cohesion: 1.0
Nodes (1): e_freeze

### Community 72 - "Community 72"
Cohesion: 1.0
Nodes (1): e_sat

### Community 73 - "Community 73"
Cohesion: 1.0
Nodes (1): k_e

### Community 74 - "Community 74"
Cohesion: 1.0
Nodes (1): NUM_BASIS

### Community 75 - "Community 75"
Cohesion: 1.0
Nodes (1): gyroxPID

### Community 76 - "Community 76"
Cohesion: 1.0
Nodes (1): gyroyPID

### Community 77 - "Community 77"
Cohesion: 1.0
Nodes (1): gyrozPID

### Community 78 - "Community 78"
Cohesion: 1.0
Nodes (1): pitchPID

### Community 79 - "Community 79"
Cohesion: 1.0
Nodes (1): rollPID

### Community 80 - "Community 80"
Cohesion: 1.0
Nodes (1): yawPID

### Community 81 - "Community 81"
Cohesion: 1.0
Nodes (1): Z_ratePID

### Community 82 - "Community 82"
Cohesion: 1.0
Nodes (1): Z_posPID

### Community 83 - "Community 83"
Cohesion: 1.0
Nodes (1): locxPID

### Community 84 - "Community 84"
Cohesion: 1.0
Nodes (1): locyPID

### Community 85 - "Community 85"
Cohesion: 1.0
Nodes (1): USART6_IRQHandler

### Community 86 - "Community 86"
Cohesion: 1.0
Nodes (1): STM32F4 Peripherals Reference (Used Subset)

### Community 87 - "Community 87"
Cohesion: 1.0
Nodes (1): DMA1_Stream2_Channel4

### Community 88 - "Community 88"
Cohesion: 1.0
Nodes (1): DMA1_Stream6_Channel4

### Community 89 - "Community 89"
Cohesion: 1.0
Nodes (1): DMA1_Stream3_Channel4

### Community 90 - "Community 90"
Cohesion: 1.0
Nodes (1): Data Dictionary

### Community 91 - "Community 91"
Cohesion: 1.0
Nodes (1): TIM3 Timer

## Ambiguous Edges - Review These
- `Monitor` → `safety_limit`  [AMBIGUOUS]
  wiki\overview.md · relation: safety_critical_for
- `sbus_lost` → `CMD 0x06`  [AMBIGUOUS]
  wiki\concepts\common-pitfalls.md · relation: gates
- `gamma (adaptation gain)` → `CMD 0x02`  [AMBIGUOUS]
  wiki\concepts\common-pitfalls.md · relation: controls
- `DroneStatus.FlyMode` → `CMD 0x06`  [AMBIGUOUS]
  wiki\concepts\common-pitfalls.md · relation: gates
- `CMD 0x06` → `SDK altitude gate`  [AMBIGUOUS]
  wiki\concepts\common-pitfalls.md · relation: gates
- `mrac_to_mixer` → `CMD 0x03`  [AMBIGUOUS]
  wiki\concepts\common-pitfalls.md · relation: controls
- `What_limit[]` → `cmd_0x05`  [AMBIGUOUS]
  wiki\concepts\common-pitfalls.md · relation: controls

## Knowledge Gaps
- **274 isolated node(s):** `Synthetic UART4 telemetry generator for offline testing.  Sends Frame A / Fram`, `Same wire format as TASK/send_data.c: 16-bit LEN, then payload + XOR CRC8.`, `8 floats (sine, distinct Hz) + ARM + FlyMode + sbus_lost + TWC flags; LEN = 37.`, `MRAC: 4 axes * (N theta + u_nom + xm) + 12 PID * (FB, Des, U).     Theta: calle`, `Minimal YAML parser for simple "key: value" files (no nesting).     This avoids` (+269 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 48`** (2 nodes): `Command ID`, `MRAC_UpdateAxis`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 49`** (2 nodes): `cmd_host`, `dashboard._send_cmd`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 50`** (2 nodes): `AnoOF_GetOneByte`, `USART2_IRQHandler`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 51`** (2 nodes): `autoflytask_patharbitrange`, `Sinusoid Path Family`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 52`** (2 nodes): `serial_bridge._rx_loop_udp`, `simulate_udp_port`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 53`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 54`** (1 nodes): `visualize_imu.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 55`** (1 nodes): `Minimal summary: duration, numeric ranges for mrac.pitch.e, pid.z_rate FB.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 56`** (1 nodes): `Multi-Rate Task Partitioning`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 57`** (1 nodes): `Ground Station Binary Protocol`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 58`** (1 nodes): `Virtual RC Authority`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 59`** (1 nodes): `Path Arbitration`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 60`** (1 nodes): `Control Loop Timing`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 61`** (1 nodes): `Protocol`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 62`** (1 nodes): `FlyMode_SDK`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 63`** (1 nodes): `GPS Stub`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 64`** (1 nodes): `SBUS Receiver`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 65`** (1 nodes): `xm (reference model state)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 66`** (1 nodes): `Ctrler`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 67`** (1 nodes): `Ctrler.Z_posPID (Altitude PID)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 68`** (1 nodes): `USART6_IRQHandler`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 69`** (1 nodes): `PID Loop`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 70`** (1 nodes): `e_deadzone`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 71`** (1 nodes): `e_freeze`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 72`** (1 nodes): `e_sat`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 73`** (1 nodes): `k_e`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 74`** (1 nodes): `NUM_BASIS`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 75`** (1 nodes): `gyroxPID`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 76`** (1 nodes): `gyroyPID`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 77`** (1 nodes): `gyrozPID`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 78`** (1 nodes): `pitchPID`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 79`** (1 nodes): `rollPID`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 80`** (1 nodes): `yawPID`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 81`** (1 nodes): `Z_ratePID`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 82`** (1 nodes): `Z_posPID`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 83`** (1 nodes): `locxPID`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 84`** (1 nodes): `locyPID`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 85`** (1 nodes): `USART6_IRQHandler`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 86`** (1 nodes): `STM32F4 Peripherals Reference (Used Subset)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 87`** (1 nodes): `DMA1_Stream2_Channel4`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 88`** (1 nodes): `DMA1_Stream6_Channel4`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 89`** (1 nodes): `DMA1_Stream3_Channel4`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 90`** (1 nodes): `Data Dictionary`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 91`** (1 nodes): `TIM3 Timer`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `Monitor` and `safety_limit`?**
  _Edge tagged AMBIGUOUS (relation: safety_critical_for) - confidence is low._
- **What is the exact relationship between `sbus_lost` and `CMD 0x06`?**
  _Edge tagged AMBIGUOUS (relation: gates) - confidence is low._
- **What is the exact relationship between `gamma (adaptation gain)` and `CMD 0x02`?**
  _Edge tagged AMBIGUOUS (relation: controls) - confidence is low._
- **What is the exact relationship between `DroneStatus.FlyMode` and `CMD 0x06`?**
  _Edge tagged AMBIGUOUS (relation: gates) - confidence is low._
- **What is the exact relationship between `CMD 0x06` and `SDK altitude gate`?**
  _Edge tagged AMBIGUOUS (relation: gates) - confidence is low._
- **What is the exact relationship between `mrac_to_mixer` and `CMD 0x03`?**
  _Edge tagged AMBIGUOUS (relation: controls) - confidence is low._
- **What is the exact relationship between `What_limit[]` and `cmd_0x05`?**
  _Edge tagged AMBIGUOUS (relation: controls) - confidence is low._