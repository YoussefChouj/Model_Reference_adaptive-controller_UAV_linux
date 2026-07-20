# Flight Log Analysis Framework - ADR-0007

## Status: Draft

## Context

We need a **state-of-the-art performance/stability analysis framework** for UAV flight logs that:
1. Analyzes flight logs to understand what happened
2. Tracks relationships between tuning controller parameters and performance metrics
3. Supports different frame types (quad, hex, custom configurations)
4. Specifically targets oscillation detection and stability analysis

## Flight Log Format

- **Structure**: Flat CSV with `t_s, frame, key, value` columns
- **Frame Types**: 
  - Frame A: High-frequency telemetry (100Hz, MRAC error signals, status)
  - Frame B: Lower-frequency telemetry (100Hz, full state including PID, MRAC weights)
- **Key Pattern**: Hierarchical dot notation (`mrac.pitch.e`, `pid.gyrox.Des`)
- **Typical Duration**: 100+ seconds of flight data
- **Sample Count**: ~44K lines

## Architecture

### Core Modules

```
flight_analysis/
├── core/
│   ├── loader.py          # Data loading with frame-type detection
│   ├── validator.py       # Data integrity checks
│   └── signals.py         # Signal processing primitives
├── stability/
│   ├── oscillation.py     # Oscillation detection
│   ├── damping.py         # Damping ratio estimation
│   └── margins.py         # Stability margin analysis
├── performance/
│   ├── tracking.py        # Tracking metrics (RMSE, MAE, peak)
│   ├── authority.py       # MRAC vs PID authority analysis
│   └── convergence.py     # Weight convergence analysis
├── correlation/
│   ├── param_map.py       # Controller parameter extraction
│   └── sensitivity.py     # Parameter-performance correlation
├── frames/
│   ├── base.py            # Frame base class
│   ├── quad.py            # Quadcopter configuration
│   ├── hex.py             # Hexacopter configuration
│   └── custom.py          # Custom frame support
├── diagnostics/
│   ├── alerts.py          # Expert-level alert generation
│   └── reports.py         # Markdown/HTML report generation
└── cli.py                 # Command-line interface
```

### Key Design Decisions

#### 1. Frame Type Abstraction

Each frame type defines:
- **Mixer scales**: Physical conversion from control output to motor command
- **Axis mapping**: Roll/pitch/yaw assignment to physical motors
- **Physical constants**: Mass, inertia, arm length
- **Expected dynamics**: Natural frequencies, damping targets

```python
class FrameConfig:
    MIXER_SCALES = {"pitch": 1170, "roll": 1170, "yaw": 1872, "z": 222}
    NUM_MOTORS = 4
    ARM_LENGTH = 0.1  # meters
    # ...
```

#### 2. Oscillation Detection Strategy

Oscillation detection uses multiple methods:
- **Spectral Analysis**: Dominant frequency extraction via Welch PSD
- **Zero-Crossing Rate**: Rate of sign changes in error signals
- **Autocorrelation**: Periodicity detection in control signals
- **Phase Margin Estimation**: From closed-loop step response

#### 3. Parameter-Performance Correlation

Controller parameters are extracted from firmware telemetry:
- **PID gains**: Kp, Ki, Kd for each axis
- **MRAC gamma**: Adaptation rates per basis function
- **Sigma-modification**: Leakage rates
- **Projection bounds**: Weight limits

Performance metrics computed:
- **RMSE**: Overall tracking accuracy
- **Overshoot**: Peak error relative to step input
- **Settling time**: Time to reach and stay within 2% band
- **Oscillation count**: Damped oscillation count after disturbance

## Test Strategy

### Slice 1: Data Loader
- Parse CSV with frame-type detection
- Handle missing keys gracefully
- Validate time monotonicity

### Slice 2: Oscillation Detection
- Synthetic sine wave detection
- Known oscillation frequency identification
- False positive suppression (valid maneuvers)

### Slice 3: Correlation Engine
- Parameter extraction from telemetry
- Sensitivity analysis output
- Performance ranking

### Slice 4: Frame Abstraction
- Quadcopter validation
- Custom frame registration
- Mixer scale adaptation

### Slice 5: Expert Diagnostics
- Alert generation from multiple sources
- Root cause classification
- Remediation suggestions

## Open Questions

1. **Frame identification**: Should frames be auto-detected or explicitly configured?
2. **Oscillation threshold**: What constitutes "oscillation" vs "aggressive maneuvering"?
3. **Correlation method**: Pearson correlation vs. causal inference for parameter impact?
4. **Report format**: Interactive HTML dashboard vs. static markdown?

## References

- Existing `analyze_flight_log.py` and `deep_analysis.py` as foundation
- MRAC telemetry structure from `API/mrac.c`
- PID structure from `API/pid.c`
