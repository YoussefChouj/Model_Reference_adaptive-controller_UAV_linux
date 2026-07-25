---
title: Common Pitfalls
type: concept
tags: [troubleshooting, debugging, faq]
created: 2026-04-14
updated: 2026-04-14
sources: [TASK/StabilizerTask.c, TASK/send_data.c, ground_station/comm/serial_bridge.py]
---

This page catalogs the most common problems encountered when working with this codebase, their root causes, and how to fix them. Check this page first before deep-diving into code.

## Motors Don't Spin

**Symptom**: Armed via dashboard but motors stay at zero PWM.

| Check | Expected | Fix |
|-------|----------|-----|
| RC mode switch (ch10) | Must be HIGH (>500) for ≥50 ms | Put physical RC mode switch in SDK position |
| `DroneStatus.FlyMode` | Must be `FlyMode_SDK (1)` | Telemetry `flymode` field; fix with RC mode switch |
| `DroneStatus.ARM_Status` | Must be `Armed (1)` | Click [SDK ARM REQ] or RC arm gesture |
| PC authority | Must be `1` after GS arm | Confirmed by [SDK ARM REQ]; check heartbeat not timed out |
| Throttle command | Must be above idle (> −0.85) | Raise throttle slider above minimum |
| SDK altitude gate | Near-ground + low throttle → idle only | Increase throttle or altitude |

The motor output path is layered: `Update_Motor()` checks armed → FlyMode → altitude/throttle → then `Set_PWM_Motors()` (`TASK/StabilizerTask.c:170-185`). Any failed gate routes to `Set_Zero_Motors()` or `Set_IDLE_Motors()`.

> **Note (2026-05-22):** `sbus_lost` is no longer required to be `1` for VRC to work. The physical RC must remain ON. Authority is controlled by CMD `0x0E` via the [SDK ARM REQ] button. See [[Virtual RC Authority]].

See [[SDK Arming State Machine]] for the full state diagram.

## No Telemetry in Dashboard / VOFA

**Symptom**: Dashboard shows stale or no data, VOFA traces are flat.

| Check | Fix |
|-------|-----|
| Serial port correct in `config.yaml`? | Set `serial_port: AUTO` and let the bridge probe — see [[Ground Station Bridge]] for the resolution flow. Otherwise verify `serial_port` matches your COM port |
| Bridge can't find dongle? | Run `python -m ground_station.comm.serial_bridge --scan-com` for a per-port probe report (desc, bytes, error) |
| Dongle stuck in Windows phantom state? | Run `ground_station\comm\Recover-AtkComPort.ps1 -AsSummary` for diagnosis + recovery instructions (Device Manager → Uninstall + "remove driver" + replug). Driver-level `pnputil` reset returns ACCESS DENIED for the phantom — see ADR-0007 |
| Baud rate match? | Must be `115200` on both sides |
| UART cable connected? | UART5 pins: PC12 (TX), PD2 (RX) |
| `DMA1_Stream7_IRQHandler` present? | If removed, UART5 TX hangs permanently |
| VOFA port collision? | Ensure `vofa_port_a/b` ≠ `cmd_udp_port` ≠ `telemetry_mirror_port` |
| VOFA format mismatch? | `vofa_format` in config must match VOFA+ connection protocol |

**Diagnostic tool**: Run `diag_telemetry_link.py` for frame-level statistics before launching full dashboard. See [[Ground Station Tooling]].

## Commands Are Ignored

**Symptom**: Dashboard sends commands but firmware doesn't respond.

| Check | Fix |
|-------|-----|
| CRC mismatch | Use `_pack_command_frame()`, don't hand-build frames |
| Command queue full on MCU | Reduce command rate; queue depth is 8 |
| Wrong UART | Commands accepted on both UART4 and UART5 |
| Virtual sticks gated | CMD `0x06` only works when `FlyMode_SDK` and `s_authority==1` (set by [SDK ARM REQ]) |

CRC coverage is bytes 2-7 (CMD_ID through VALUE), not including sync bytes. See [[Ground-Station Binary Protocol]].

## VOFA Channels Are Shifted / Garbled

**Symptom**: VOFA shows data but channel labels don't match values.

**Root cause**: Frame B channel count depends on `MAX_NUM_BASIS` at compile time (`API/mrac.h:75-89`). If firmware is recompiled with different basis count but VOFA workspace presets aren't updated, channels shift.

**Fix**: Regenerate VOFA workspace presets or manually re-map channels. The bridge carries `max_num_basis` in state for host-side validation.

## Yaw Drifts Continuously

**Symptom**: Yaw angle increases/decreases steadily even with no stick input.

| Cause | Check | Fix |
|-------|-------|-----|
| Mahony Ki too low | `Ki = 0.001f` (`API/imu_update.c:21`) | Increase Ki or check accelerometer normalization |
| Magnetometer not used | Mahony filter in this codebase is accel-only; no magnetometer correction | Accept drift as inherent limitation |
| IMU dt mismatch | `1e-3f` must match 1 ms task period | Verify `pdMS_TO_TICKS(1)` in `USER/main.c:144` |

See [[IMU Update]] and [[Control Loop Timing]].

## Gain Changes Disappear After Reboot

**Symptom**: Tuned PID/MRAC gains revert to defaults on power cycle.

**Root cause**: All runtime parameter updates are RAM-only. No flash persistence is implemented. See [[Flash Memory]].

**Workaround**: Record good gains manually, then update compile-time defaults in source code and reflash.

## Position Controller Spirals

**Symptom**: X/Y position tracking goes unstable or spirals outward.

| Cause | Check | Fix |
|-------|-------|-----|
| Yaw sign wrong | Position PID uses `Cos_Yaw`/`Sin_Yaw` rotation | Verify `imu_data.yaw` sign convention matches [[Coordinate Conventions]] |
| Optical flow stale | `USART2_task_cnt` not incrementing | Check optical flow sensor connection |
| Position gains too aggressive | `locxPID.Kp` or `locyPID.Kp` too high | Reduce outer position gains |

## MRAC Output Causes Oscillation

**Symptom**: Flight becomes unstable when MRAC injection is enabled.

| Cause | Fix |
|-------|-----|
| `mrac_to_mixer` too large | Reduce CMD `0x03 idx 0-3` values |
| `gamma[]` too aggressive | Reduce adaptation rates via CMD `0x02` |
| `What_limit[]` too loose | Tighten weight bounds via CMD `0x05` |
| NaN in weights | Check `isfinite` guard is active (`TASK/StabilizerTask.c:303-306`) |

See [[MRAC Control Law]] and [[Tuning Workflow]].

## Build Fails in Keil

| Error | Fix |
|-------|-----|
| Missing `robot_types.h` | File is at `Global_file/robot_types.h`; check include paths |
| Missing `bmi088_driver.h` | BMI088 driver headers must be in include path |
| `MRAC_Init` undefined | Ensure `API/mrac.h` and MRAC source files are added to project |

## Naming Confusions

| Misleading Name | Actual Behavior |
|----------------|-----------------|
| `Send_Groundstation_Telemetry_UART4()` | Actually sends via **UART5** DMA Stream 7 |
| `M4` motor macro | Maps to TIM3 **CH2** (PA7), not CH4 |
| `DisArmed = 0` / `Armed = 1` | Chinese comments say 解锁 (unlock) for armed and 上锁 (lock) for disarmed — opposite intuition |

## See Also

- [[Agent & Developer Quick-Start Guide]] — setup flow
- [[SDK Arming State Machine]] — arming troubleshooting
- [[UART Peripheral Map]] — serial connection reference
- [[Ground Station Tooling]] — diagnostic scripts

<!-- recent_change:2026-07-25 -->
## Recent change (2026-07-25)

Auto-flagged by path_refresh. Files affected in this session:
- `API/imu_update.c`
- `TASK/StabilizerTask.c`

Run `/wiki ingest` or `python -m graphify --update` to verify rationale still holds. Remove this section if confirmed unchanged.
