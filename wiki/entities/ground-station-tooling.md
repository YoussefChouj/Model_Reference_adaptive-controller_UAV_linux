---
title: Ground Station Tooling
type: entity
tags: [analysis, diagnostics, scripts, ground-station]
created: 2026-04-14
updated: 2026-04-14
sources: [ground_station/scripts/deep_analysis.py, ground_station/scripts/experiment_db.py, ground_station/scripts/diag_telemetry_link.py, ground_station/comm/frame_simulator.py]
related_files: [ground_station/scripts/analyze_flight_log.py, ground_station/scripts/flight_logger.py]
---

The ground station includes several Python scripts beyond the core dashboard and serial bridge. This page catalogs each tool, its purpose, and how to use it.

## deep_analysis.py — Post-Flight Deep Analysis

**Location**: `ground_station/scripts/deep_analysis.py`  
**Dependencies**: numpy, scipy, matplotlib  
**Purpose**: Advanced frequency-domain and time-domain analysis of flight log data.

### Key Functions

- `get_data_array(data, axis, key)` (`deep_analysis.py:36`) — Fallback lookup helper for flat and dotted telemetry names
- `get_pid_array(data, loop, key)` (`deep_analysis.py:44`) — Same for PID telemetry

### What It Computes

Given a flight log CSV, this script produces:
- MRAC tracking error analysis per axis (RMSE, peak, settling time)
- Weight evolution convergence metrics (final weight norms, convergence rate)
- Phase relationship between reference model and actual output
- Frequency-domain analysis of control signals (FFT, power spectrum)
- Alert generation for critical conditions (weight saturation, error divergence)

### Physical Constants

Uses hardcoded mixer scales matching compile-time firmware config (`deep_analysis.py:23-27`):
```python
MIXER_PR = 1170.0    # pitch/roll mixer scale
MIXER_YAW = 1872.0   # yaw mixer scale
MIXER_Z = 222.0      # altitude mixer scale
MRAC_DT = 0.005      # 5 ms control dt
MAX_NUM_BASIS = 6     # basis function count
```

If firmware `mrac.h` compile-time constants change, these must be updated in sync.

### Usage

```bash
python -m ground_station.scripts.deep_analysis <path_to_flight_log.csv>
```

## experiment_db.py — Cross-Flight Experiment Ranking

**Location**: `ground_station/scripts/experiment_db.py`  
**Purpose**: Loads all analysis result JSONs from a directory and ranks experiments by configurable metrics.

### Usage

```bash
python -m ground_station.scripts.experiment_db --dir ground_station/results/ --sort composite_score --top 5
```

### Options

| Flag | Default | Meaning |
|------|---------|---------|
| `--dir` | `ground_station/results/` | Directory containing result JSONs |
| `--top` | all | Show top N results |
| `--sort` | `composite_score` | Sort field (e.g., `pitch.rmse`, `composite_score`) |
| `--format` | `table` | Output format: `table`, `json`, or `csv` |
| `--export` | false | Also write to file |

### Data Schema

Each result JSON is expected to contain:
- `experiment_id`, `timestamp`, `duration_s`, `rows_parsed`
- `scoreboard.<axis>.rmse`, `.rho_mean`, `.rho_p95`, `.phase_relationship`, `.alerts_critical`, `.alerts_warn`, `.weight_norm_final`

## diag_telemetry_link.py — Telemetry Link Diagnostics

**Location**: `ground_station/scripts/diag_telemetry_link.py`  
**Purpose**: Standalone link health probe that connects to the serial port (or UDP simulation) and reports frame statistics without requiring the full dashboard.

### Key Classes

- `FrameStats` dataclass (`diag_telemetry_link.py:26-38`) — counters for bytes, sync hits, CRC pass/fail, frame type distribution
- `xor_crc8(data)` (`diag_telemetry_link.py:41`) — CRC verification
- `pack_cmd_frame(cmd_id, index, value)` (`diag_telemetry_link.py:48`) — builds command frame for link testing

### What It Reports

- Total bytes received
- `0xAA` sync byte count vs `0xAA 0xBB` sync pair count (measures sync efficiency)
- Frame A and Frame B valid/CRC-fail/length-fail counts
- Last known ARM status, FlyMode, SBUS lost state
- First bytes dump for debugging garbled connections

### Usage

```bash
python -m ground_station.scripts.diag_telemetry_link [--port COM6] [--baud 115200] [--duration 10]
```

Useful when: dashboard shows no telemetry but you need to determine whether the issue is serial link, CRC, or parser.

## frame_simulator.py — Offline Frame Simulation

**Location**: `ground_station/comm/frame_simulator.py`  
**Purpose**: Generates synthetic telemetry frames and sends them via UDP, allowing dashboard and VOFA testing without physical hardware.

### Usage

```bash
python -m ground_station.comm.frame_simulator [--port 50007]
```

Configured UDP port should match `simulate_udp_port` in `config.yaml` (`ground_station/config.yaml:14`).

## check_vofa_udp.py — VOFA UDP Health Check

**Location**: `ground_station/scripts/check_vofa_udp.py`  
**Purpose**: Listens on VOFA ports and reports whether JustFloat packets are arriving and well-formed.

## show_frame_a_vofa_bytes.py — Raw Frame Inspection

**Location**: `ground_station/comm/show_frame_a_vofa_bytes.py`  
**Purpose**: Captures and hex-dumps raw Frame A VOFA UDP packets for protocol debugging.

## Relationship to Dashboard

```
Dashboard ──→ SerialBridge ──→ VOFA streams ──→ VOFA+
    │              │
    │              └─→ Telemetry mirror ──→ diag_telemetry_link.py
    │
    └─→ FlightLogger ──→ CSV ──→ deep_analysis.py ──→ result JSON
                                                          │
                                               experiment_db.py (ranking)
```

## See Also

- [[FlightLogger]] — CSV recording
- [[Dashboard]] — primary operator interface
- [[VOFA Streaming]] — VOFA protocol details
- [[Tuning Workflow]] — how these tools fit into tuning
