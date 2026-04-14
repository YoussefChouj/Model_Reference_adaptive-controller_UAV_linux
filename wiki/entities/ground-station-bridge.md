---
title: Ground Station Bridge
type: entity
tags: [python, serial, udp, vofa, ground-station]
created: 2026-04-13
updated: 2026-04-14
sources: [ground_station/comm/serial_bridge.py]
related_files: [ground_station/comm/serial_bridge.py]
relations:
  - type: must_match
    target: "[[Ground-Station Binary Protocol]]"
---

`SerialBridge` is the host-side transport hub that decodes telemetry from STM32 and forwards it to VOFA, UDP mirror consumers, and command ingress queues.

## Class and Initialization

Primary class signature:
- `class SerialBridge` (`ground_station/comm/serial_bridge.py:140`)
- `def __init__(..., serial_port, baud_rate, vofa_host, vofa_port, vofa_port_a, vofa_port_b, ..., cmd_udp_port, ...)` (`ground_station/comm/serial_bridge.py:146-161`)

Important init bindings:
- Serial defaults from `load_config()` (`ground_station/comm/serial_bridge.py:162-186`)
- VOFA stream A/B ports (`ground_station/comm/serial_bridge.py:171-175`)
- Command UDP bind (`_cmd_udp_port`) (`ground_station/comm/serial_bridge.py:184-187`)
- Telemetry mirror destination (`telemetry_mirror_host/port`) (`ground_station/comm/serial_bridge.py:189-191`)

## Thread Model

`start()` launches up to 3 daemon threads:
- RX thread: `_rx_loop` (serial) or `_rx_loop_udp` (simulated) (`ground_station/comm/serial_bridge.py:262-284`)
- Command TX thread: `_cmd_loop` (`ground_station/comm/serial_bridge.py:273-275`)
- Local UDP command listener thread: `_cmd_udp_loop` (`ground_station/comm/serial_bridge.py:282-284`)

This separation avoids telemetry parsing stalls when user/UI command bursts occur.

## Receive Loop and Frame Dispatch

Sync detection for telemetry is `0xAA 0xBB` in `_rx_loop` (`ground_station/comm/serial_bridge.py:811-818`) and `_parse_and_handle_datagram` (`ground_station/comm/serial_bridge.py:743-744`). Header bytes are:
- `frame_type` (`0x01` / `0x02`)
- `LEN_hi`, `LEN_lo`
- `MAX_NUM_BASIS`

Dispatch condition is in `_handle_frame`:
- `frame_type == 0x01` -> `_unpack_frame_a` (`ground_station/comm/serial_bridge.py:601-603`)
- `frame_type == 0x02` -> `_unpack_frame_b` (`ground_station/comm/serial_bridge.py:603-604`)

## Command Send Path

Command frame packing is in `def _pack_command_frame(self, cmd)` (`ground_station/comm/serial_bridge.py:897`):
- Wire format: `[0xCC][0xDD][cmd_id][index][float32 LE][crc]` (`ground_station/comm/serial_bridge.py:912-916`)
- XOR CRC is computed over bytes 2..7 (`ground_station/comm/serial_bridge.py:914-915`)
- `_xor_crc8` implementation loops all passed bytes and XORs (`ground_station/comm/serial_bridge.py:122-132`)

## VOFA and Mirror Forwarding

Forwarding occurs after successful decode:
- `_emit_vofa_output(...)` selects port/format (`ground_station/comm/serial_bridge.py:343-356`)
- JustFloat payload and stream port mapping are emitted in `_emit_justfloat` (`ground_station/comm/serial_bridge.py:392-397`)
- JSON telemetry mirror to dashboard is emitted by `_mirror_telemetry_udp` to configured host/port (`ground_station/comm/serial_bridge.py:620-634`)

Data forwarded includes full Frame A/B decoded key-value sets (`_last_telemetry_a`, `_last_telemetry_b`).

## See Also

- [[Ground-Station Binary Protocol]]
- [[Dashboard]]
- [[VOFA Streaming]]
- [[Virtual RC Authority]]
