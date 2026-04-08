# Graph Report - .  (2026-04-08)

## Corpus Check
- 202 files · ~0 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1501 nodes · 2146 edges · 38 communities detected
- Extraction: 81% EXTRACTED · 19% INFERRED · 0% AMBIGUOUS · INFERRED: 407 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## God Nodes (most connected - your core abstractions)
1. `Dashboard` - 74 edges
2. `SerialBridge` - 38 edges
3. `FLASH_WaitForLastOperation()` - 17 edges
4. `FlightLogger` - 14 edges
5. `PathExecutor` - 12 edges
6. `Update_Des()` - 11 edges
7. `xTaskResumeAll()` - 10 edges
8. `TIM_ICInit()` - 9 edges
9. `UdpBridgeClient` - 9 edges
10. `vTaskSuspendAll()` - 8 edges

## Surprising Connections (you probably didn't know these)
- `UdpBridgeClient` --uses--> `SerialBridge`  [INFERRED]
  ground_station\gui\dashboard.py → ground_station\comm\serial_bridge.py
- `DebouncedSender` --uses--> `SerialBridge`  [INFERRED]
  ground_station\gui\dashboard.py → ground_station\comm\serial_bridge.py
- `Dashboard` --uses--> `SerialBridge`  [INFERRED]
  ground_station\gui\dashboard.py → ground_station\comm\serial_bridge.py
- `Send ground-station commands to a running `serial_bridge.py` process.` --uses--> `SerialBridge`  [INFERRED]
  ground_station\gui\dashboard.py → ground_station\comm\serial_bridge.py
- `Load a config.yaml that is only flat 'key: value' entries.     This matches how` --uses--> `SerialBridge`  [INFERRED]
  ground_station\gui\dashboard.py → ground_station\comm\serial_bridge.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.03
Nodes (54): AnoOF_DataAnl(), AnoOF_GetOneByte(), AutoflyTask(), AutoflyTask_PathArbitrate(), AutoflyTask_RunCircle(), AutoflyTask_RunSinusoid(), SDK_StateMachine_Init(), SDK_StateMachine_Loop() (+46 more)

### Community 1 - "Community 1"
Cohesion: 0.04
Nodes (20): Dashboard, DebouncedSender, dump_preset_yaml(), _format_inline_map(), load_preset_yaml(), main(), _parse_inline_map(), _parse_inline_value() (+12 more)

### Community 2 - "Community 2"
Cohesion: 0.03
Nodes (16): TI1_Config(), TI2_Config(), TI3_Config(), TI4_Config(), TIM_ETRClockMode1Config(), TIM_ETRClockMode2Config(), TIM_ETRConfig(), TIM_ICInit() (+8 more)

### Community 3 - "Community 3"
Cohesion: 0.03
Nodes (30): prvCheckDelayedList(), prvCheckPendingReadyList(), prvInitialiseCoRoutineLists(), vCoRoutineSchedule(), xCoRoutineCreate(), prvTestWaitCondition(), vEventGroupClearBitsCallback(), vEventGroupSetBitsCallback() (+22 more)

### Community 4 - "Community 4"
Cohesion: 0.04
Nodes (43): eTaskGetState(), prvAddCurrentTaskToDelayedList(), prvAddNewTaskToReadyList(), prvCheckTasksWaitingTermination(), prvDeleteTCB(), prvInitialiseNewTask(), prvInitialiseTaskLists(), prvListTasksWithinSingleList() (+35 more)

### Community 5 - "Community 5"
Cohesion: 0.05
Nodes (45): prvCopyDataFromQueue(), prvCopyDataToQueue(), prvInitialiseMutex(), prvInitialiseNewQueue(), prvIsQueueEmpty(), prvIsQueueFull(), prvNotifyQueueSetContainer(), prvUnlockQueue() (+37 more)

### Community 6 - "Community 6"
Cohesion: 0.03
Nodes (2): RCC_GetFlagStatus(), RCC_WaitForHSEStartUp()

### Community 7 - "Community 7"
Cohesion: 0.03
Nodes (0): 

### Community 8 - "Community 8"
Cohesion: 0.05
Nodes (18): RTC_Bcd2ToByte(), RTC_ByteToBcd2(), RTC_CoarseCalibCmd(), RTC_CoarseCalibConfig(), RTC_DeInit(), RTC_EnterInitMode(), RTC_ExitInitMode(), RTC_GetAlarm() (+10 more)

### Community 9 - "Community 9"
Cohesion: 0.04
Nodes (2): NVIC_SetPriority(), SysTick_Config()

### Community 10 - "Community 10"
Cohesion: 0.04
Nodes (0): 

### Community 11 - "Community 11"
Cohesion: 0.07
Nodes (21): load_config(), _main_cli(), _parse_simple_yaml(), CRC8 in this project is an XOR checksum over bytes.     Matches the C code:, FireWater / CSV channel names: dots -> underscores (mrac.pitch.e -> mrac_pitch_e, Latest decoded Frame A / Frame B variables (thread-safe, for GUI + logging)., Send one telemetry burst to VOFA+ according to config `vofa_format` and frame ty, VOFA+ JustFloat: little-endian float32 payload + frame tail bytes. (+13 more)

### Community 12 - "Community 12"
Cohesion: 0.07
Nodes (17): FLASH_EraseAllBank1Sectors(), FLASH_EraseAllBank2Sectors(), FLASH_EraseAllSectors(), FLASH_EraseSector(), FLASH_GetStatus(), FLASH_OB_Launch(), FLASH_OB_PCROP1Config(), FLASH_OB_PCROPConfig() (+9 more)

### Community 13 - "Community 13"
Cohesion: 0.05
Nodes (0): 

### Community 14 - "Community 14"
Cohesion: 0.06
Nodes (0): 

### Community 15 - "Community 15"
Cohesion: 0.06
Nodes (0): 

### Community 16 - "Community 16"
Cohesion: 0.07
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
Cohesion: 0.1
Nodes (11): build_frame_a(), build_frame_b(), _pack_telemetry_frame(), Synthetic UART4 telemetry generator for offline testing.  Sends Frame A / Fram, Same wire format as TASK/send_data.c: 16-bit LEN, then payload + XOR CRC8., 8 floats (sine, distinct Hz) + ARM + FlyMode + sbus_lost + TWC flags; LEN = 37., MRAC: 4 axes * (N theta + u_nom + xm) + 12 PID * (FB, Des, U).     Theta: calle, main() (+3 more)

### Community 21 - "Community 21"
Cohesion: 0.08
Nodes (0): 

### Community 22 - "Community 22"
Cohesion: 0.08
Nodes (2): CAN_GetITStatus(), CheckITStatus()

### Community 23 - "Community 23"
Cohesion: 0.08
Nodes (0): 

### Community 24 - "Community 24"
Cohesion: 0.08
Nodes (0): 

### Community 25 - "Community 25"
Cohesion: 0.11
Nodes (0): 

### Community 26 - "Community 26"
Cohesion: 0.11
Nodes (0): 

### Community 27 - "Community 27"
Cohesion: 0.11
Nodes (0): 

### Community 28 - "Community 28"
Cohesion: 0.12
Nodes (0): 

### Community 29 - "Community 29"
Cohesion: 0.15
Nodes (5): PathExecutor, PositionSourceError, Ground-station path follower: 10 Hz virtual stick commands (CMD 0x06).  Firmwa, Waypoint, RuntimeError

### Community 30 - "Community 30"
Cohesion: 0.13
Nodes (0): 

### Community 31 - "Community 31"
Cohesion: 0.14
Nodes (0): 

### Community 32 - "Community 32"
Cohesion: 0.26
Nodes (6): MRAC_Control(), MRAC_GenerateStructuredBasis(), MRAC_Init(), MRAC_ProjectGradient(), MRAC_Reset(), MRAC_UpdateAxis()

### Community 33 - "Community 33"
Cohesion: 0.25
Nodes (0): 

### Community 34 - "Community 34"
Cohesion: 0.6
Nodes (3): SetSysClock(), SystemInit(), SystemInit_ExtMemCtl()

### Community 35 - "Community 35"
Cohesion: 0.67
Nodes (0): 

### Community 36 - "Community 36"
Cohesion: 1.0
Nodes (0): 

### Community 37 - "Community 37"
Cohesion: 1.0
Nodes (1): Minimal summary: duration, numeric ranges for mrac.pitch.e, pid.z_rate FB.

## Knowledge Gaps
- **23 isolated node(s):** `Simple IMU CSV visualizer.  Input CSV expected columns (header optional): time`, `Synthetic UART4 telemetry generator for offline testing.  Sends Frame A / Fram`, `Same wire format as TASK/send_data.c: 16-bit LEN, then payload + XOR CRC8.`, `8 floats (sine, distinct Hz) + ARM + FlyMode + sbus_lost + TWC flags; LEN = 37.`, `MRAC: 4 axes * (N theta + u_nom + xm) + 12 PID * (FB, Des, U).     Theta: calle` (+18 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 36`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 37`** (1 nodes): `Minimal summary: duration, numeric ranges for mrac.pitch.e, pid.z_rate FB.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Dashboard` connect `Community 1` to `Community 11`?**
  _High betweenness centrality (0.093) - this node is a cross-community bridge._
- **Why does `SerialBridge` connect `Community 11` to `Community 1`?**
  _High betweenness centrality (0.061) - this node is a cross-community bridge._
- **Why does `UdpBridgeClient` connect `Community 1` to `Community 11`?**
  _High betweenness centrality (0.017) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `Dashboard` (e.g. with `main()` and `SerialBridge`) actually correct?**
  _`Dashboard` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `SerialBridge` (e.g. with `start_bridge_in_background()` and `UdpBridgeClient`) actually correct?**
  _`SerialBridge` has 10 INFERRED edges - model-reasoned connections that need verification._
- **Are the 16 inferred relationships involving `FLASH_WaitForLastOperation()` (e.g. with `FLASH_EraseSector()` and `FLASH_EraseAllSectors()`) actually correct?**
  _`FLASH_WaitForLastOperation()` has 16 INFERRED edges - model-reasoned connections that need verification._
- **Are the 9 inferred relationships involving `FlightLogger` (e.g. with `UdpBridgeClient` and `DebouncedSender`) actually correct?**
  _`FlightLogger` has 9 INFERRED edges - model-reasoned connections that need verification._