# 1. Trajectory presets are generated firmware-side, not in the ground station

Date: 2026-06-14
Status: Accepted

## Context

The drone has two code paths that can command position:

1. **Firmware path generator** (`TASK/AutoflyTask.c`) — circle / sinusoid / TWC presets
   that write the position setpoint `Ctrler.loc{x,y}PID.Des` directly at 200 Hz. The MRAC
   inner loop tracks those setpoints. All existing flight logs were produced this way.
2. **Ground-station `path_executor.py`** — a Python outer loop that sends virtual sticks
   (CMD 0x06) at 10 Hz over serial, active only in SDK / sbus-lost mode. Its `_loop_body`
   is a stubbed placeholder; it appears legacy.

When adding a new figure-8 (lemniscate) preset, plus a shared waypoint-density control, we
had to choose which path owns trajectory generation.

## Decision

New trajectory presets (figure-8) and the shared waypoint-density quantizer are implemented
**firmware-side**, mirroring circle/sinusoid: a `*_path` struct in `global_declare.h`, a
`AutoflyTask_Run*` generator writing PID `.Des`, arbitration in
`AutoflyTask_PathArbitrate`, an idx-mapped CMD in `send_data.c`, and an `active_path_mode`
telemetry code. The ground station only sends parameters + start/stop.

## Consequences

- **Positive:** every preset is tracked by the same MRAC inner loop at 200 Hz, so tracking
  results across modes are directly comparable — essential for the thesis. No 10 Hz serial
  outer loop in the control path. Waypoint density (reference quantization) can be applied
  uniformly to all modes from one place.
- **Negative:** each change requires a Keil rebuild + reflash; iteration is slower than
  editing Python. Trajectory math lives on an MCU (`float`, no easy logging mid-derivation).
- **Follow-up:** `path_executor.py` is now confirmed legacy for preset flights; leave it
  untouched but do not extend it.

## Alternatives considered

- **Implement figure-8 in `path_executor.py` (no reflash).** Rejected: it drives the
  separate CMD-0x06 virtual-stick path, so its tracking would not be comparable to the
  circle/sinusoid logs and would bypass the MRAC setpoint interface under study.
