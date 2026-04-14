---
title: VOFA Streaming
type: entity
tags: [vofa, udp, telemetry, visualization]
created: 2026-04-14
updated: 2026-04-14
sources: [ground_station/comm/serial_bridge.py, ground_station/gui/dashboard.py, ground_station/config.yaml]
related_files: [ground_station/comm/serial_bridge.py, ground_station/gui/dashboard.py, ground_station/config.yaml]
---

VOFA streaming is implemented in `SerialBridge` as an output stage after telemetry decode. It supports Frame A and Frame B streams on separate UDP ports and can emit either JustFloat binary or FireWater-like text modes.

## Protocol and Frame Formats

VOFA output mode is selected by config key `vofa_format` (`ground_station/config.yaml:10`), interpreted in `_emit_vofa_output` (`ground_station/comm/serial_bridge.py:343-356`).

Supported formats include:
- `justfloat` (default): little-endian float32 array + tail `00 00 80 7F` (`ground_station/comm/serial_bridge.py:392-397`)
- `firewater_single_line`
- `firewater_multiline`
- `firewater_header_csv`
(`ground_station/comm/serial_bridge.py:347-355`)

## Port and Stream Mapping

Configured endpoints:
- host: `vofa_host` (`ground_station/config.yaml:3`)
- Frame A stream port: `vofa_port_a` (`ground_station/config.yaml:5`)
- Frame B stream port: `vofa_port_b` (`ground_station/config.yaml:6`)

Bridge chooses destination per frame type in `_emit_vofa_output`:
- `frame_type == 0x01` -> `vofa_port_a`
- `frame_type == 0x02` -> `vofa_port_b`
(`ground_station/comm/serial_bridge.py:345`)

## Channel Mapping

Frame A unpack (`_unpack_frame_a`) maps 13 channels including:
- `mrac.pitch.e`, `mrac.pitch.u_ad`, ... `mrac.z.u_ad`
- `status.arm`, `status.flymode`, `status.sbus_lost`, `status.twc_execute`, `status.twc_arrived`
(`ground_station/comm/serial_bridge.py:455-469`)

Frame B unpack (`_unpack_frame_b`) maps dynamic MRAC weights (`theta_i` by `MAX_NUM_BASIS`), `u_nom`, `xm`, 12 PID loops (FB/Des/U), and path-state tail fields (`ground_station/comm/serial_bridge.py:558-596`).

Because Frame B channel count is basis-dependent, VOFA workspace presets must match current firmware `MAX_NUM_BASIS` or channels appear shifted/missing. The bridge mitigates this by carrying `max_num_basis` in state and validating frame lengths before unpack.

## Start/Stop Control

Streaming itself is effectively always-on while `SerialBridge` is running and receiving valid telemetry; there is no separate “CMD start VOFA” in firmware. Start/stop is therefore controlled by process lifecycle:
- `SerialBridge.start()` launches RX pipeline (`ground_station/comm/serial_bridge.py:246`)
- `SerialBridge.stop()` terminates threads/sockets (`ground_station/comm/serial_bridge.py:290`)

Dashboard-level VOFA app launch is independent and handled by `_open_plot(...)` (`ground_station/gui/dashboard.py:1996`) plus sidebar buttons (`ground_station/gui/dashboard.py:2767-2772`).

## Relationship to Dashboard

Dashboard can operate with local bridge or remote UDP bridge command mode, but VOFA streaming originates from bridge decode stage. The dashboard mostly orchestrates VOFA workspace opening and context files; channel data still comes from `SerialBridge` emissions.

## Common Misconfiguration Patterns

- **Port collision**: if command UDP and VOFA UDP share ports, commands or telemetry can appear “randomly dead.” Config keeps command port separate (`cmd_udp_port` vs VOFA ports in `ground_station/config.yaml:5-6,17`).
- **Mode mismatch**: VOFA set to FireWater while bridge emits JustFloat (or vice versa) yields unreadable traces; ensure `vofa_format` and VOFA receive mode agree.
- **Stale workspace labels**: if basis count or channel order changes, old workspace files can mislabel channels even when transport is correct.

## Evidence vs Inference

Evidence-backed:
- Output formats, packet construction, and stream-port routing are anchored in `ground_station/comm/serial_bridge.py`.
- Config defaults and ports are anchored in `ground_station/config.yaml`.

Inference-labeled:
- Misconfiguration symptom descriptions are operational heuristics derived from protocol and UI behavior, not from bundled incident logs.

## See Also

- [[Ground Station Bridge]]
- [[Dashboard]]
