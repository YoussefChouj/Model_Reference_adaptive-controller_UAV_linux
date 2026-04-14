---
title: Ground-Station Binary Protocol
type: protocol
tags: [uart, telemetry, crc, ground-station]
created: 2026-04-13
updated: 2026-04-14
sources: [TASK/send_data.c, BSP/usart4.c, BSP/usart5.c, ground_station/comm/serial_bridge.py]
related_files: [TASK/send_data.c, BSP/usart4.c, BSP/usart5.c, ground_station/comm/serial_bridge.py]
relations:
  - type: must_match
    target: "[[Ground Station Bridge]]"
---

This project uses a compact sync-framed binary protocol for telemetry (`0xAA 0xBB`) and commands (`0xCC 0xDD`). Parser and packer behavior must match exactly between firmware and host.

## Command Frame: `0xCC 0xDD`

| Byte | Field | Type |
|------|-------|------|
| 0 | Sync 0xCC | uint8 |
| 1 | Sync 0xDD | uint8 |
| 2 | CMD_ID | uint8 |
| 3 | INDEX | uint8 |
| 4-7 | VALUE | float32 LE |
| 8 | CRC8_XOR | uint8 |

Firmware decoding and queue write:
- UART4 ingress: `Handle_UART4_GroundStation_Command()` (`BSP/usart4.c:100`)
- UART5 ingress: `Handle_UART5_GroundStation_Command()` (`BSP/usart5.c:120`)
- CRC loop bounds: `for (i = 2; i < 8; i++) calc_crc ^= mailbox[i];` (`BSP/usart4.c:126-128`, `BSP/usart5.c:145-147`)

Host packing:
- `_pack_command_frame()` (`ground_station/comm/serial_bridge.py:897`)
- CRC over bytes `[2:]` (i.e., cmd_id/index/value bytes) (`ground_station/comm/serial_bridge.py:914-916`)

## Telemetry Frame: `0xAA 0xBB`

| Byte | Field | Type |
|------|-------|------|
| 0 | Sync 0xAA | uint8 |
| 1 | Sync 0xBB | uint8 |
| 2 | frame_type | uint8 (0x01 or 0x02) |
| 3-4 | payload length | uint16 BE |
| 5 | MAX_NUM_BASIS | uint8 |
| 6..N | payload | varies |
| N+1 | CRC8_XOR | uint8 |

Firmware sender is `Send_Groundstation_Telemetry_UART4()` (`TASK/send_data.c:281`).  
Frame A (`type=0x01`) payload is fixed 37 bytes (`TASK/send_data.c:295`).  
Frame B (`type=0x02`) payload length is computed from `MAX_NUM_BASIS`:

`payload_len = (4 * (MAX_NUM_BASIS + 2) + 36) * 4 + 22` (`TASK/send_data.c:330-331`)

CRC rule for telemetry is XOR over indices `2 .. len-1` before CRC append (`TASK/send_data.c:432-437`), mirrored on Python side in `_rx_loop` and `_parse_and_handle_datagram` (`ground_station/comm/serial_bridge.py:858-860`, `771-773`).

## Command IDs 0x01–0x10

Handled in `Process_GroundStation_Command()` (`TASK/send_data.c:471`):
- `0x01`: PID gain update (`TASK/send_data.c:481-501`)
- `0x02`: MRAC gamma[] (`TASK/send_data.c:503-519`)
- `0x03`: mixer scales, u_max, throttle min/max pct (`TASK/send_data.c:537-553`)
- `0x04`: flight mode / dangerous stop (`TASK/send_data.c:568-578`)
- `0x05`: MRAC What_limit[] (`TASK/send_data.c:503-519`)
- `0x06`: virtual sticks gated by SBUS+SDK (`TASK/send_data.c:522-528`)
- `0x07`: bench mode (`TASK/send_data.c:530-535`)
- `0x08`: MRAC What_tol[] (`TASK/send_data.c:503-519`)
- `0x09`: GS safety limits (`TASK/send_data.c:555-566`)
- `0x0A`: TWC target + execute (`TASK/send_data.c:580-595`)
- `0x0B`: sinusoid parameters (`TASK/send_data.c:597-626`)
- `0x0C`: circle parameters (`TASK/send_data.c:628-653`)
- `0x0D`: abort all paths (`TASK/send_data.c:655-660`)
- `0x0E`: GS SDK arm switch (`TASK/send_data.c:662-673`)
- `0x0F`, `0x10`: reserved/unimplemented in current firmware dispatcher.

## UART Channel and Baud

Ground-station telemetry TX uses UART5 DMA stream 7 (`TASK/send_data.c:441-448`, `BSP/usart5.c:92-111`) at `115200` baud (`BSP/usart5.c:55`). Command ingress is supported on both UART4 and UART5 at `115200` (`BSP/usart4.c:36`, `BSP/usart5.c:55`).

## Protocol Invariants (Must Not Drift)

The following are strict contracts between firmware and host:

1. **Endian contract for float payloads**  
   Command value bytes are interpreted as little-endian float on MCU (`BSP/usart4.c:112-120`, `BSP/usart5.c:131-139`) and packed little-endian on host (`struct.pack("<f", ...)`, `ground_station/comm/serial_bridge.py:910`).

2. **CRC coverage contract**  
   - Command CRC: bytes `[CMD_ID..VALUE]` only (indices 2..7), excluding sync (`BSP/usart4.c:126-128`, `ground_station/comm/serial_bridge.py:914-916`)  
   - Telemetry CRC: bytes from `frame_type` through last payload byte (`TASK/send_data.c:432-437`, `ground_station/comm/serial_bridge.py:858-860`)

3. **Length semantics**  
   `LEN` is payload length only, not full frame length. Host parser enforces exact expected payload sizes for frame types (`ground_station/comm/serial_bridge.py:831-840`, `751-758`).

4. **`MAX_NUM_BASIS` consistency**  
   Frame B parser computes expected float count from transmitted `MAX_NUM_BASIS`, so firmware and host must remain synchronized when MRAC basis compile-time options change (`TASK/send_data.c:330-335`, `ground_station/comm/serial_bridge.py:540-544`).

## Failure Behavior

Protocol corruption handling is intentionally drop-on-error:
- Wrong sync/header/len/CRC -> frame discarded without side effects (`ground_station/comm/serial_bridge.py:831-847,860-863`)
- Full command queue on MCU -> newest command dropped and counter incremented (`BSP/usart4.c:139-142`, `BSP/usart5.c:156-158`)

This design favors control-loop continuity over guaranteed command delivery; operators should expect occasional command loss under severe serial contention and resend idempotent commands when needed.

## See Also

- [[Ground Station Bridge]]
- [[Virtual RC Authority]]
- [[Dashboard]]
