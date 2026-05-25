# Cross-Subsystem Interfaces

## IF-01: Ground-Station Command Frame (`0xCC 0xDD`)
- **Defines (writer):** `ground_station/comm/serial_bridge.py` in `_pack_command_frame`.
- **Consumes (reader):** `BSP/usart4.c` (`Handle_UART4_GroundStation_Command`), `BSP/usart5.c` (`Handle_UART5_GroundStation_Command`).
- **Byte layout:**
  - Byte 0: `0xCC`
  - Byte 1: `0xDD`
  - Byte 2: `CMD_ID` (`uint8`)
  - Byte 3: `INDEX` (`uint8`)
  - Bytes 4-7: `VALUE` (`float32`, little-endian)
  - Byte 8: `CRC8_XOR`
- **Sync constraints:** CRC is XOR of bytes 2..7 in both firmware and host.

## IF-02: Telemetry Frame (`0xAA 0xBB`)
- **Defines (writer):** `TASK/send_data.c` (`Send_Groundstation_Telemetry_UART4`).
- **Consumes (reader):** `ground_station/comm/serial_bridge.py` (`_rx_loop`, `_parse_and_handle_datagram`, `_handle_frame`).
- **Byte layout:**
  - Byte 0: `0xAA`
  - Byte 1: `0xBB`
  - Byte 2: `frame_type` (`0x01` or `0x02`)
  - Byte 3: payload length high byte
  - Byte 4: payload length low byte
  - Byte 5: `MAX_NUM_BASIS`
  - Bytes 6..(6+LEN-1): payload
  - Last byte: `CRC8_XOR`
- **Sync constraints:** CRC is XOR over `[frame_type, LEN_hi, LEN_lo, MAX_NUM_BASIS, payload...]`.
- **Notes:**
  - Frame A (`0x01`) payload length is fixed at 37 bytes.
  - Frame B (`0x02`) payload length is formula-based and depends on `MAX_NUM_BASIS`.

## IF-03: Ground-Station Command Queue (`GS_Cmd_t` ring buffer)
- **Defines (writer owner):** `BSP/usart4.c` defines `GS_Cmd_t`, `gs_cmd_queue[8]`, `gs_cmd_head`, `gs_cmd_tail`, `gs_cmd_drop_count`.
- **Consumes (reader):** `TASK/send_data.c` (`Process_GroundStation_Command`).
- **Field list:**
  - `id: uint8_t`
  - `index: uint8_t`
  - `value: float`
- **Sync constraints:**
  - Queue depth is exactly 8.
  - Full queue policy drops newest command and increments `gs_cmd_drop_count`.
  - UART4 and UART5 both enqueue into the same shared ring.

## IF-04: Mixer Output to Timer Compare Mapping
- **Defines (writer):** `TASK/StabilizerTask.c` (`Compute_Motor`) writes `mymotor.motor1..motor4`.
- **Consumes (reader):** `BSP/pwm.c` (`Set_PWM_Motors`) applies values through macros in `BSP/pwm.h`.
- **Field list / mapping:**
  - `mymotor.motor1` -> `M1` -> `TIM3->CCR1`
  - `mymotor.motor2` -> `M2` -> `TIM3->CCR3`
  - `mymotor.motor3` -> `M3` -> `TIM3->CCR4`
  - `mymotor.motor4` -> `M4` -> `TIM3->CCR2`
- **Sync constraints:** Mixer sign conventions in `Compute_Motor` and CCR mapping in `pwm.h` must be updated together.
- **Status:** Physical motor position labels are partially documented externally in `NOTE/` docs. [FILL]

## IF-05: Shared Path Control State
- **Defines (writer):** `TASK/send_data.c` updates `TWC`, `sinusoid_path`, `circle_path`, `GS_KeySDKflag` from command IDs `0x0A..0x0E`.
- **Consumes (reader):** `TASK/AutoflyTask.c` and `TASK/StabilizerTask.c`.
- **Field list:**
  - `SinusoidPath_t`: center_x, center_y, center_z, amplitude, frequency, duration, axis, active, t_elapsed
  - `CirclePath_t`: center_x, center_y, center_z, radius, angular_speed, duration, active, theta, t_elapsed
  - `TargetSet_WorldReal_Coordinate`: target_x, target_y, target_z, execute, set_yaw, plus world/real fields
- **Sync constraints:**
  - Path parameters are interpreted at a 5 ms control cadence in `AutoflyTask` (`dt = 0.005f`).
  - Path arbitration ensures only one active path family at a time.
- **Coordinate unit contract (updated 2026-05-23):**
  - `TWC.target_x`, `TWC.target_y` are in **cm** — written as-is from CMD 0x0A idx 0/1; consumed by `locxPID` / `locyPID` (both cm).
  - `TWC.target_z` is in **metres** — consumed by `Z_posPID` (metres).
  - `TWC_arrived` distance check in `StabilizerTask.c` converts XY to metres (×0.01f) before Euclidean distance. Threshold: 0.15 m.
  - Ground station must send `user_x * 100.0` and `user_y * 100.0` for CMD 0x0A idx 0/1.

## IF-06: Control-Loop Timing Contract
- **Defines (writer):** `USER/main.c` task schedule and explicit call arguments.
- **Consumes (reader):** `API/imu_update.c` and control/autonomy tasks.
- **Field list:**
  - IMU update task period: 1 ms
  - Mahony call argument: `dt = 1e-3f`
  - Stabilizer/autofly task period: 5 ms
- **Sync constraints:** If task periods change, the corresponding `dt` constants and filter/controller assumptions must be updated to match.

## IF-07: drone_mode Global — Flight Mode Switch
- **Defines (writer):** `TASK/RemoterTask.c` (`Check_Fly_Mode`) writes `drone_mode` from SBUS ch5 each 10 ms cycle.
- **Consumes (reader):** `TASK/StabilizerTask.c` (`case_Update_height_Des`).
- **Values:**
  - `0` = IDLE — freeze Z_posPID.Des at current FB, suppress TWC execute.
  - `1` = FLY — normal operation, rate-limited TWC execute allowed.
  - `2` = LAND — ramp Z_posPID.Des to 0 at 0.003 m/cycle; auto-disarm when Z_FB < 0.1 m and Z_Des ≤ 0.05 m.
- **Sync constraints:** `drone_mode` is `volatile uint8_t`. Single-byte write is atomic on Cortex-M4; no critical section needed. SBUS ch5 thresholds: `< 300` = IDLE, `300-700` = FLY, `> 700` = LAND.

## IF-08: sbus_twc_trigger Flag — SBUS Ch8 TWC Trigger
- **Defines (writer):** `TASK/RemoterTask.c` (`Check_Fly_Mode`) sets `sbus_twc_trigger = 1U` on `TWC_EXEC_CH > 500` rising edge. Also auto-arms and grants RC authority if disarmed.
- **Consumes (reader):** `TASK/StabilizerTask.c` — reads flag, sets `TWC.execute = 1U`, clears flag to 0U.
- **Sync constraints:** Flag is `volatile uint8_t`, cleared by StabilizerTask within one 5 ms cycle. Producer (RemoterTask) must not re-set the flag until it has been cleared; the rising-edge detection (`ch8_prev`) prevents re-triggering.

## IF-09: SBUS Channel Assignments
- **Defines (writer):** RC transmitter hardware + `BSP/usart1.c` SBUS decoder writes `sbus_channel[]`.
- **Consumes (readers):** `TASK/RemoterTask.c`, `TASK/RemoterTask.h`.
- **Channel map (0-indexed, raw 0-2000 range):**

| Index | Macro | Function |
|-------|-------|----------|
| 0 | `ROLL_CH` | Aileron / roll stick |
| 1 | `PITCH_CH` | Elevator / pitch stick |
| 2 | `THR_CH` | Throttle |
| 3 | `YAW_CH` | Rudder / yaw stick |
| 4 | `MODE_CH` | 3-pos flight mode switch (ch5) |
| 7 | `TWC_EXEC_CH` | Momentary TWC trigger (ch8) |
| 9 | kill switch | ch10: ≤500 → DANGEROUS_STOP (unconditional) |

- **Sync constraints:** ch10 kill switch check is independent of `drone_mode` and `s_authority`. It always fires regardless of SDK state.