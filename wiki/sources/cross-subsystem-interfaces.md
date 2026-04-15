---
title: Cross-Subsystem Interfaces
type: source
tags: [interfaces, contracts, protocols]
created: 2026-04-13
updated: 2026-04-14
sources: [docs/interfaces.md]
---

Full digest of `docs/interfaces.md` — the project's cross-subsystem interface contracts. Each interface defines its writer, reader(s), byte/field layout, and sync constraints that must hold for the system to function correctly.

---

## IF-01: Ground-Station Command Frame (`0xCC 0xDD`)

**Writer**: `ground_station/comm/serial_bridge.py` — `_pack_command_frame`
**Readers**: `BSP/usart4.c` (`Handle_UART4_GroundStation_Command`), `BSP/usart5.c` (`Handle_UART5_GroundStation_Command`)

**Byte layout** (9 bytes total):

| Byte | Field | Type | Notes |
|:---|:---|:---|:---|
| 0 | Sync 0 | `0xCC` | Fixed |
| 1 | Sync 1 | `0xDD` | Fixed |
| 2 | `CMD_ID` | `uint8` | Command opcode |
| 3 | `INDEX` | `uint8` | Sub-index (axis, channel, etc.) |
| 4–7 | `VALUE` | `float32 LE` | Payload value |
| 8 | `CRC8_XOR` | `uint8` | XOR of bytes 2..7 |

**Command ID map (selected)**:

| CMD | Purpose |
|:---|:---|
| `0x01` | Set Kp for axis |
| `0x02` | Set Ki for axis |
| `0x05` | Set MRAC learning rate (`gamma`) |
| `0x06` | Write virtual RC stick (`[thr, pit, rol, yaw]`) |
| `0x08` | Set MRAC weight limit |
| `0x09` | Set MRAC weight tolerance |
| `0x0A` | TWC waypoint + execute |
| `0x0B` | Configure sinusoid path |
| `0x0C` | Configure circle path |
| `0x0D` | Global abort all paths |
| `0x0E` | SDK ARM request (hold-to-arm) |

**Sync constraints**:
- CRC must be XOR of exactly bytes `[CMD_ID, INDEX, VALUE_b0, VALUE_b1, VALUE_b2, VALUE_b3]`
- Firmware drops frames where CRC does not match
- Both UART4 and UART5 use the same frame format and push into the same `GS_Cmd_t` ring buffer (IF-03)

**See also**: [[Ground-Station Binary Protocol]], [[Ground Station Bridge]]

---

## IF-02: Telemetry Frame (`0xAA 0xBB`)

**Writer**: `TASK/send_data.c` — `Send_Groundstation_Telemetry_UART4`
**Readers**: `ground_station/comm/serial_bridge.py` — `_rx_loop`, `_parse_and_handle_datagram`, `_handle_frame`

**Frame header** (6 bytes before payload):

| Byte | Field | Type | Notes |
|:---|:---|:---|:---|
| 0 | Sync 0 | `0xAA` | Fixed |
| 1 | Sync 1 | `0xBB` | Fixed |
| 2 | `frame_type` | `uint8` | `0x01` = Frame A, `0x02` = Frame B |
| 3 | `LEN_hi` | `uint8` | Payload length high byte |
| 4 | `LEN_lo` | `uint8` | Payload length low byte |
| 5 | `MAX_NUM_BASIS` | `uint8` | MRAC basis count (affects Frame B size) |
| 6..N | payload | `bytes` | Frame-type dependent |
| N+1 | `CRC8_XOR` | `uint8` | XOR of `[frame_type, LEN_hi, LEN_lo, MAX_NUM_BASIS, payload...]` |

**Frame A (`0x01`)** — fixed 37-byte payload, 100 Hz nominal:
- MRAC error and adaptive output per axis (`mrac.pitch.e`, `mrac.pitch.u_ad`, etc.)
- Status flags: `arm`, `flymode`, `sbus_lost`, `twc_execute`, `twc_arrived`

**Frame B (`0x02`)** — variable payload, 20 Hz nominal:
- MRAC adaptive weights (`Theta[i]` for `i = 0..MAX_NUM_BASIS-1`) per axis
- `u_nom`, `xm` per axis
- 12 PID loop states (Feedback / Desired / Output per loop)
- Path-state tail fields

**Sync constraints**:
- Frame A payload is exactly 37 bytes regardless of configuration
- Frame B payload length = `f(MAX_NUM_BASIS)` — host and firmware must agree on `MAX_NUM_BASIS` or Frame B unpacking produces shifted/missing channels
- CRC covers header bytes 2–5 + full payload; a CRC mismatch causes host to discard the frame silently

**See also**: [[Ground-Station Binary Protocol]], [[VOFA Streaming]]

---

## IF-03: Ground-Station Command Queue (`GS_Cmd_t` ring buffer)

**Owner / writer**: `BSP/usart4.c` defines the ring buffer; `BSP/usart4.c` and `BSP/usart5.c` ISR handlers enqueue
**Reader**: `TASK/send_data.c` — `Process_GroundStation_Command()`

**Type definition**:
```c
typedef struct {
    uint8_t id;
    uint8_t index;
    float   value;
} GS_Cmd_t;
```

**Ring buffer globals** (defined in `BSP/usart4.c`):
- `GS_Cmd_t gs_cmd_queue[8]` — depth-8 ring
- `uint8_t gs_cmd_head`, `gs_cmd_tail`
- `uint32_t gs_cmd_drop_count` — saturation counter

**Sync constraints**:
- Queue depth is exactly 8; if `head == (tail+1) % 8` the queue is full — newest command is dropped and `gs_cmd_drop_count` incremented
- Both UART4 and UART5 ISRs enqueue into the same shared ring — no per-channel priority
- `Process_GroundStation_Command()` processes one entry per call; at 100 Hz task rate this gives max throughput of 100 commands/s before backpressure
- No mutex protects the ring: ISR enqueue and task dequeue rely on the write-first / read-after pattern and the fixed 8-slot depth

**See also**: [[Ground-Station Binary Protocol]], [[Virtual RC Authority]]

---

## IF-04: Mixer Output → Timer Compare Mapping

**Writer**: `TASK/StabilizerTask.c` — `Compute_Motor()` fills `mymotor.motor1..motor4`
**Reader**: `BSP/pwm.c` — `Set_PWM_Motors()` reads `mymotor` and writes CCR registers via macros in `BSP/pwm.h`

**Field mapping**:

| `Compute_Motor` output | Macro | Hardware register | Physical meaning |
|:---|:---|:---|:---|
| `mymotor.motor1` | `M1` | `TIM3->CCR1` | Motor 1 ESC PWM |
| `mymotor.motor2` | `M2` | `TIM3->CCR3` | Motor 2 ESC PWM |
| `mymotor.motor3` | `M3` | `TIM3->CCR4` | Motor 3 ESC PWM |
| `mymotor.motor4` | `M4` | `TIM3->CCR2` | Motor 4 ESC PWM |

Note: `M4` maps to `CCR2` and `M2` maps to `CCR3` — macro names are intentionally non-sequential relative to CCR channel numbers.

**PWM range**:
- `Motor_PWM_ZERO = 2000` (disarmed / stopped)
- `Motor_PWM_IDLE = 2150` (minimum spin threshold)
- `Motor_PWM_MAX  = 4000` (full throttle)

`Set_PWM_Motors()` applies `value_limit(motorN, Motor_PWM_ZERO, Motor_PWM_MAX)` per channel before writing CCRs (`BSP/pwm.c:274-284`).

**Sync constraints**:
- Mixer sign conventions in `Compute_Motor` and CCR macro assignments in `pwm.h` must be updated together; a sign flip on any motor without updating the mixing matrix produces rotation-reversal failure at runtime
- PWM range constants must be validated against the specific ESC model in use; mismatched range causes either no spin or full-throttle surprise on arm

**See also**: [[Motor Mixer]], [[Timer & PWM Configuration]], [[STM32F4 Peripherals Reference]]

---

## IF-05: Shared Path Control State

**Writer**: `TASK/send_data.c` — updates `TWC`, `sinusoid_path`, `circle_path`, `GS_KeySDKflag` from CMD `0x0A..0x0E`
**Readers**: `TASK/AutoflyTask.c` (path execution), `TASK/StabilizerTask.c` (TWC setpoint consumption in `Update_Des`)

**Struct field lists**:

*`SinusoidPath_t`*:
- `center_x`, `center_y`, `center_z` — offset origin
- `amplitude`, `frequency` — sinusoid parameters
- `duration` — auto-stop time (seconds)
- `axis` — 0=X, 1=Y, 2=Z routing
- `active` — gate flag (read by `AutoflyTask_PathArbitrate`)
- `t_elapsed` — internal integrator state

*`CirclePath_t`*:
- `center_x`, `center_y`, `center_z` — circle center
- `radius`, `angular_speed` — geometry
- `duration` — auto-stop time
- `active` — gate flag
- `theta`, `t_elapsed` — internal integrator states

*`TargetSet_WorldReal_Coordinate` (TWC)*:
- `target_x`, `target_y`, `target_z` — world-frame XYZ setpoints
- `execute` — gate flag (`!= 0` means active)
- `set_yaw` — yaw override value
- Plus world/real fields for position reference

**Sync constraints**:
- Path parameters are consumed at 5 ms cadence in `AutoflyTask` (`const float dt = 0.005f` at `TASK/AutoflyTask.c:31,59`) — if path command rate exceeds this, intermediate values are overwritten without being executed
- `AutoflyTask_PathArbitrate()` enforces mutual exclusion each cycle: at most one of `sinusoid_path.active`, `circle_path.active`, `TWC.execute != 0` is true after arbitration
- Abort command (`CMD 0x0D`) must clear all three gate flags simultaneously to have full effect — partial clears leave a path silently active

**See also**: [[Path Arbitration]], [[AutoflyTask]], [[Autonomous Path Generation]]

---

## IF-06: Control-Loop Timing Contract

**Writer**: `USER/main.c` — task periods declared via `pdMS_TO_TICKS()` and explicit `dt` arguments
**Readers**: `API/imu_update.c` (Mahony filter), all control and autonomy tasks

**Period and `dt` table**:

| Task / Module | Period (ms) | Declared `dt` | Location |
|:---|:---|:---|:---|
| `IMU_DataDeal_Task` | 1 | `1e-3f` arg to `IMU_Update_Mahony` | `USER/main.c:150` |
| Mahony `half_T` | — | `0.5f * dt` | `API/imu_update.c:53` |
| `Stabilizer_Task` | 5 | `0.005f` in derivative terms | `TASK/StabilizerTask.c:107-147` |
| `Autofly_Task` | 5 | `0.005f` in path integrators | `TASK/AutoflyTask.c:31,59` |
| MRAC controller | 5 | `MRAC_DT = 0.005f` | `API/mrac.h:194` |

**Sync constraints**:
- If any task period changes in `USER/main.c`, **all** dependent `dt` constants in the table above must be updated to match — they are not auto-derived
- Mahony PI gains (`Kp`, `Ki`) and MRAC learning rates (`gamma[]`) are tuned for these specific periods; period changes require re-tuning
- Path integrators `theta += angular_speed * dt` and `t_elapsed += dt` (`TASK/AutoflyTask.c:42-43,70-74`) assume `dt` is exact; jitter accumulates as phase error over long trajectories

**See also**: [[Control Loop Timing]], [[Multi-rate Task Partitioning]], [[IMU Update]], [[FreeRTOS Primitives Used]]
