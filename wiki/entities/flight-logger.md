---
title: FlightLogger
type: entity
tags: [logging, csv, analysis, ground-station]
created: 2026-04-14
updated: 2026-04-14
sources: [ground_station/scripts/flight_logger.py, ground_station/gui/dashboard.py, ground_station/scripts/analyze_flight_log.py]
related_files: [ground_station/scripts/flight_logger.py, ground_station/gui/dashboard.py, ground_station/scripts/analyze_flight_log.py]
---

`FlightLogger` is the dashboard-integrated telemetry recorder that stores per-frame key/value streams to CSV for post-flight analysis. Core class is `class FlightLogger` in `ground_station/scripts/flight_logger.py:12`.

## Class and Method Signatures

- `def start(self, filename: Path) -> None` (`ground_station/scripts/flight_logger.py:20`)
- `def log_snapshot(self, frame: str, data: Dict[str, float]) -> None` (`ground_station/scripts/flight_logger.py:30`)
- `def stop(self) -> None` (`ground_station/scripts/flight_logger.py:38`)
- `@staticmethod def analyze(filename: Path) -> Dict[str, Any]` (`ground_station/scripts/flight_logger.py:56`)

Dashboard integration points:
- logger object instantiated at `ground_station/gui/dashboard.py:362`
- logging invoked in UI frame loop (`ground_station/gui/dashboard.py:841-842`)
- recording start/stop handlers (`ground_station/gui/dashboard.py:2623,2633`)

## What Is Logged and at What Rate

Logged content is “latest telemetry snapshot” from both decoded frame families:
- Frame A snapshot keys under label `"A"`
- Frame B snapshot keys under label `"B"`

Each call to `log_snapshot` writes all keys in sorted order (`ground_station/scripts/flight_logger.py:34-36`). Actual sampling rate depends on dashboard frame/update cadence plus telemetry freshness, but source telemetry nominally arrives at 100 Hz (Frame A) and 20 Hz (Frame B) from firmware.

## Storage Format

File format is flat CSV with schema:
- header row: `t_s,frame,key,value` (`ground_station/scripts/flight_logger.py:26`)
- one row per metric per snapshot (`ground_station/scripts/flight_logger.py:35`)

Filename convention from dashboard:
- `logs/flight_<unix_timestamp>.csv` (`ground_station/gui/dashboard.py:2629`)

Path-memory helper logs are separate (`path_<timestamp>.csv`) and only contain desired XY traces (`ground_station/gui/dashboard.py:2645-2650`).

## Post-Flight Analysis Path

Two analysis layers exist:
1. Lightweight static method `FlightLogger.analyze` computes basic summary stats (`ground_station/scripts/flight_logger.py:56-87`)
2. Full plotting script `analyze_flight_log.py` loads CSV and renders tracking + MRAC figures:
   - `load_flight_data(...)` (`ground_station/scripts/analyze_flight_log.py:8`)
   - `plot_tracking(...)` (`ground_station/scripts/analyze_flight_log.py:39`)
   - `plot_mrac_adaptive(...)` (`ground_station/scripts/analyze_flight_log.py:80`)

Dashboard “stop recording” workflow chains into these scripts via subprocess in the diagnostics flow (`ground_station/gui/dashboard.py:2580-2614`).

## Process Model

`FlightLogger` runs in the dashboard process (not a separate daemon). It is event-driven from UI frame updates and can be started/stopped by button callbacks (`ground_station/gui/dashboard.py:2499-2500`). This keeps logging synchronized with what the operator sees in the GUI telemetry state.

## Evidence vs Inference

Evidence-backed:
- CSV schema, write loops, filename conventions, and analysis script entry points are all anchored in logger/dashboard/scripts files.

Inference-labeled:
- Any “effective logging rate” interpretation depends on runtime UI loop timing and telemetry freshness in the specific deployment; this page documents nominal behavior, not guaranteed sample-period bounds.

## See Also

- [[Ground Station Bridge]]
- [[Dashboard]]
- [[Ground-Station Binary Protocol]]
