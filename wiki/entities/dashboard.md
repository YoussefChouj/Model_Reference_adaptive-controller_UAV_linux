---
title: Dashboard
type: entity
tags: [gui, ground-station, telemetry, commands]
created: 2026-04-14
updated: 2026-04-14
sources: [ground_station/gui/dashboard.py, ground_station/config.yaml]
related_files: [ground_station/gui/dashboard.py, ground_station/comm/serial_bridge.py, ground_station/config.yaml]
---

`Dashboard` is the operator GUI that sits above `SerialBridge` and acts as both telemetry consumer and command producer. Main class is `class Dashboard` (`ground_station/gui/dashboard.py:322`) with constructor `def __init__(self)` (`ground_station/gui/dashboard.py:323`).

## Class Structure and Roles

Key responsibilities are grouped in methods:
- Connection lifecycle: `_connect_on_launch`, `_try_remote_bridge`, `_start_bridge` (`ground_station/gui/dashboard.py:535,552,618`)
- UI build: `_build_gui` (`ground_station/gui/dashboard.py:2654`)
- Runtime refresh loop: `_frame` (`ground_station/gui/dashboard.py:668`)
- Command dispatch: `_send_cmd` (`ground_station/gui/dashboard.py:1039`)
- Telemetry listener: `_telemetry_listener` (`ground_station/gui/dashboard.py:400`)
- Flight logging: `_flight_log_start/_flight_log_stop` (`ground_station/gui/dashboard.py:2623,2633`)

## Config Loading

It reads config from `ground_station/config.yaml` through `load_config()` and lightweight YAML helpers. Consumed keys include:
- serial link: `serial_port`, `baud_rate` (`ground_station/config.yaml:1-2`)
- VOFA endpoints: `vofa_host`, `vofa_port_a`, `vofa_port_b`, `vofa_format`, `vofa_executable` (`ground_station/config.yaml:3,5-6,10-11`)
- command and telemetry UDP: `cmd_udp_port`, `telemetry_mirror_port` (`ground_station/config.yaml:17,19`)

## UI Layout and Panels

The main window builds:
- Left sidebar for connection, status (`ARM/FlyMode/SBUS/Bench`), flight mode buttons, STOP, VOFA shortcuts (`ground_station/gui/dashboard.py:2694-2773`)
- Tabbed right area: `Monitor`, `Virtual RC`, `PID Tuning`, `MRAC Tuning`, `Paths`, `Safety`, `Flight Log` (`ground_station/gui/dashboard.py:2777-2807`)

This layout is tightly coupled to command IDs and telemetry keys from [[Ground-Station Binary Protocol]].

## Telemetry Data Flow

There are two telemetry paths:
1. **Remote bridge mode**: UDP mirror listener thread reads JSON and updates `self._telem` (`ground_station/gui/dashboard.py:400-433`)
2. **Local bridge mode**: direct in-process pull via `self.bridge.get_telemetry_snapshot()` (`ground_station/gui/dashboard.py:442-450`)

In `_frame`, telemetry is refreshed and forwarded to logger:
- `self._flight_logger.log_snapshot("A", a)` and `"B"` (`ground_station/gui/dashboard.py:841-842`)

## Command Dispatch Path

User actions (buttons/sliders) eventually call `_send_cmd(cmd_id, index, value)` (`ground_station/gui/dashboard.py:1039`). `_send_cmd` routes to:
- UDP command client (`UdpBridgeClient`) when using remote bridge, or
- in-process `SerialBridge` command queue

Examples from UI:
- SDK mode button sends `CMD 0x04 idx 1` (`ground_station/gui/dashboard.py:2738-2743`)
- Dangerous stop button sends `CMD 0x04 idx 0` (`ground_station/gui/dashboard.py:2745-2750`)

The command path includes debounce/throttle behavior (`DebouncedSender` in this module) to avoid flooding serial link with slider noise. This matters for tunable parameters (PID/MRAC sliders) where high-frequency GUI events can otherwise saturate command queue depth on the MCU side.

## VOFA Integration

VOFA launching/selection is handled by `_open_plot(...)` (`ground_station/gui/dashboard.py:1996`) and sidebar shortcut buttons:
- Frame A workspace preset (`ground_station/gui/dashboard.py:2767`)
- Frame B workspace preset (`ground_station/gui/dashboard.py:2772`)

The dashboard also manages per-stream runtime contexts and executable discovery in VOFA helper methods (`ground_station/gui/dashboard.py:1334-1678` region).

## Safety-Relevant UI Behaviors

- STOP button is globally accessible in sidebar and wired to dangerous-stop command path (`ground_station/gui/dashboard.py:2754-2760`).
- Status indicators (`ARM`, `FlyMode`, `SBUS`, `Bench`) are refreshed from telemetry, not local UI assumptions, which reduces risk of stale-command optimism.
- Telemetry freshness checks gate some controls; if telemetry goes stale, UI indicates degraded link and avoids presenting stale state as valid control authority.

## Integration Boundaries

Dashboard is intentionally not the protocol source of truth:
- Binary framing and CRC are owned by [[Ground Station Bridge]]
- Dashboard sends semantic commands (`cmd_id/index/value`) and consumes decoded telemetry dictionaries
- File logging and deep analysis are delegated to [[FlightLogger]] and analysis scripts

Keeping this boundary clean is important when evolving protocol fields: bridge parser/packer can change while most GUI code remains stable.

## Evidence vs Inference

Evidence-backed:
- Class/method names, UI panels, command IDs from buttons, and telemetry listener paths are all anchored in `ground_station/gui/dashboard.py`.
- Config keys are anchored in `ground_station/config.yaml`.

Inference-labeled:
- Statements about operator risk reduction (“stale-command optimism” mitigation) are design-intent interpretations based on freshness/status code paths, not human-factors test results.

## See Also

- [[Ground Station Bridge]]
- [[Ground-Station Binary Protocol]]
- [[VOFA Streaming]]
