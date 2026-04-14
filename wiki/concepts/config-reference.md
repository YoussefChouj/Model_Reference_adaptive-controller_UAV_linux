---
title: Config Reference
type: concept
tags: [config, yaml, ground-station, setup]
created: 2026-04-14
updated: 2026-04-14
sources: [ground_station/config.yaml, ground_station/comm/serial_bridge.py, ground_station/gui/dashboard.py]
---

All ground station runtime configuration lives in `ground_station/config.yaml`. This page documents every key, its default, and where it's consumed.

## Serial Connection

| Key | Default | Type | Consumed By | Purpose |
|-----|---------|------|-------------|---------|
| `serial_port` | `COM6` | string | `SerialBridge.__init__` | Serial port for MCU connection |
| `baud_rate` | `115200` | int | `SerialBridge.__init__` | Must match firmware UART config |

Both consumed via `load_config()` in `serial_bridge.py`. Firmware UART4 and UART5 both use 115200 (`BSP/usart4.c:36`, `BSP/usart5.c:55`).

## VOFA+ Visualization

| Key | Default | Type | Consumed By | Purpose |
|-----|---------|------|-------------|---------|
| `vofa_host` | `127.0.0.1` | string | `SerialBridge` | VOFA+ UDP target host |
| `vofa_port_a` | `1347` | int | `SerialBridge._emit_vofa_output` | Frame A JustFloat stream port |
| `vofa_port_b` | `1348` | int | `SerialBridge._emit_vofa_output` | Frame B JustFloat stream port |
| `vofa_format` | `justfloat` | string | `SerialBridge._emit_vofa_output` | Output format: `justfloat`, `firewater_single_line`, `firewater_multiline`, `firewater_header_csv` |
| `vofa_executable` | (path) | string | `Dashboard._open_plot` | Absolute path to VOFA+ executable |
| `vofa_manual_mode` | `1` | int | `Dashboard` | If 1, don't auto-overwrite VOFA workspace files |

**Critical**: `vofa_port_a` and `vofa_port_b` must not collide with `cmd_udp_port` or `telemetry_mirror_port`. Port collision causes commands or telemetry to be "randomly dead."

**VOFA format must match**: If bridge emits `justfloat` but VOFA+ is set to FireWater (or vice versa), traces will be unreadable. Ensure `vofa_format` in config matches the VOFA+ connection protocol setting.

## Command Channel

| Key | Default | Type | Consumed By | Purpose |
|-----|---------|------|-------------|---------|
| `cmd_host` | `127.0.0.1` | string | `Dashboard._send_cmd` | Command UDP target |
| `cmd_udp_port` | `1349` | int | `SerialBridge._cmd_udp_loop` | UDP port for command ingress |

Commands can be sent from dashboard (in-process) or from external scripts via UDP to this port.

## Telemetry Mirror

| Key | Default | Type | Consumed By | Purpose |
|-----|---------|------|-------------|---------|
| `telemetry_mirror_port` | `1350` | int | `SerialBridge._mirror_telemetry_udp` | JSON telemetry mirror for dashboard remote mode |

When dashboard runs in remote mode (separate process from bridge), it receives decoded telemetry as JSON datagrams on this port.

## Simulation

| Key | Default | Type | Consumed By | Purpose |
|-----|---------|------|-------------|---------|
| `simulate_udp_port` | `50007` | int | `SerialBridge._rx_loop_udp` | UDP port for simulated telemetry input (from `frame_simulator.py`) |

Used when testing without physical hardware. Set dashboard to UDP simulation mode and point `frame_simulator.py` at this port.

## Port Allocation Summary

```
1347  ← VOFA Frame A (bridge → VOFA+)
1348  ← VOFA Frame B (bridge → VOFA+)
1349  ← Command UDP  (dashboard/scripts → bridge)
1350  ← Telemetry mirror (bridge → dashboard remote)
50007 ← Simulation input (frame_simulator → bridge)
```

All ports must be unique. If running multiple drone instances, offset all ports.

## Loading Mechanism

`load_config()` in `serial_bridge.py` reads `ground_station/config.yaml` using PyYAML. Missing keys fall back to hardcoded defaults in the `__init__` signature of `SerialBridge`.

## See Also

- [[Ground Station Bridge]] — how config is consumed
- [[Dashboard]] — UI that reads config
- [[VOFA Streaming]] — VOFA protocol details
- [[Agent & Developer Quick-Start Guide]] — setup instructions
