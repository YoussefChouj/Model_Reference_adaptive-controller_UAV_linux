# Flight Analysis Report

**Generated:** 2026-07-20 18:23:57
**Duration:** 100.9 seconds
**Samples:** 44,620

---

## Executive Summary

**Overall Status:** CAUTION (score: 73/100)

⚠️ **Oscillation detected on:** yaw, z

## Per-Axis Analysis

| Axis | Oscillation | Frequency (Hz) | Damping | Phase Margin | RMSE |
|------|-------------|-----------------|---------|--------------|------|
| PITCH | ✅ No | 14.1 | 0.16 | 30° | 3.4932 |
| ROLL | ✅ No | 16.0 | 0.12 | 30° | 3.2224 |
| YAW | ⚠️ Yes | 0.4 | 0.16 | - | 23.6069 |
| Z | ⚠️ Yes | 0.4 | 0.11 | 30° | - |

## Detailed Findings

### Alerts

- **[CRITICAL]** PITCH: Phase margin is low (30.0°) (LOW_PHASE_MARGIN)
- **[WARNING]** PITCH: High tracking error (RMSE=3.493) (POOR_TRACKING)
- **[CRITICAL]** ROLL: Phase margin is low (30.0°) (LOW_PHASE_MARGIN)
- **[WARNING]** ROLL: High tracking error (RMSE=3.222) (POOR_TRACKING)
- **[INFO]** YAW: Controller actively compensating for oscillation (CONTROLLER_REACTING)
- **[WARNING]** YAW: High tracking error (RMSE=23.607) (POOR_TRACKING)
- **[INFO]** Z: Controller actively compensating for oscillation (CONTROLLER_REACTING)
- **[CRITICAL]** Z: Phase margin is low (30.0°) (LOW_PHASE_MARGIN)

## Recommendations

1. PITCH: Reduce proportional gain
2. PITCH: Increase derivative action
3. PITCH: Increase controller gains
4. PITCH: Check for disturbances or wind
5. ROLL: Reduce proportional gain
6. ROLL: Increase derivative action
7. ROLL: Increase controller gains
8. ROLL: Check for disturbances or wind
9. YAW: Increase controller gains
10. YAW: Check for disturbances or wind

---

## Technical Details

### Data Quality

- Signals recorded: 92
- Total samples: 44,620
- Estimated sample rate: 442.2 Hz
- Maximum gap: 221 ms
