# FreeRTOS STM32 6-DOF Drone Control Guide

**Project:** `FreeRTOS---Six Degrees of Freedom Initial Code - International Student`  
**Date produced:** 2026-04-08  
**Audience:** Lab students flying or bench-testing the drone for the first time.

> ⚠️ **WARNING: This drone uses real motors and propellers. Never arm with props installed unless you have cleared the flight area, have a spotter, and are fully confident in the disarm procedure. When in doubt, remove propellers before testing any electrical or software change.**

---

## Table of Contents

1.  [Part 1 — Keil µVision Manual Debug Session](#part-1--keil-vision-manual-debug-session)
2.  [Part 2 — Custom GUI (dashboard.py)](#part-2--custom-gui-dashboardpy)
3.  [Part 3 — Keil to GUI Transition Handoff](#part-3--keil-to-gui-transition-handoff)
4.  [Appendix A — Frame Format Reference](#appendix-a--frame-format-reference)
5.  [Appendix B — CMD ID Quick Reference](#appendix-b--cmd-id-quick-reference)
6.  [Appendix C — Key Variable Map](#appendix-c--key-variable-map)

---

## Part 1 — Keil µVision Manual Debug Session

### 1.1 Prerequisites

**Hardware required:**

*   STM32F4-based flight controller (the project targets STM32F4xx, see `BSP/BSP.c:6` NVIC group config).
*   ST-Link V2 or equivalent JTAG/SWD debugger connected to the SWD header.
*   USB-to-UART dongle wired to UART4 (PA0 = TX, PA1 = RX, 115200 8N1) for telemetry monitoring. Configured in `BSP/usart4.c:36`.
*   5V supply or LiPo with props **removed** for initial sessions.

**Software required:**

*   Keil MDK-ARM µVision 5 (tested; MDK 5.36 or newer recommended).
*   STM32F4xx device pack (installed via Pack Installer).
*   ST-Link USB driver.
*   (Optional) A serial terminal (PuTTY / CoolTerm) set to 115200 8N1 to watch raw telemetry on UART4.

### 1.2 Opening the Project

Open the Keil project file:

```
USER/JX_FLY.uvprojx
```

All source files are already in the µVision project groups. Do not move or rename files—the project uses relative paths.

### 1.3 Build, Flash, and Start Debug

| Step | Action | Keil shortcut |
| --- | --- | --- |
| 1 | Build all | F7 |
| 2 | Flash to target | F8 (or Download button) |
| 3 | Start debug session | Ctrl+F5 |
| 4 | Run firmware | F5 |

After pressing F5, all FreeRTOS tasks start. The scheduler is launched by `vTaskStartScheduler()` at `USER/main.c:17`. The task creation order and stack sizes are defined in `start_task()` at `USER/main.c:22-83`.

**Task summary (all created at startup):**

| Task name | Rate | Key work |
| --- | --- | --- |
| `SystemMonitor_Task` | 1 Hz | `SystemErrorDetect()` |
| `IMUSample_Task` | 1000 Hz | `Sensor_Data_Prepare()` |
| `IMU_DataDeal_Task` | 1000 Hz | `IMU_Update_Mahony()` |
| `Stabilizer_Task` | 200 Hz | `stabilizer_Task()` — PID + MRAC + motors |
| `Remoter_Task` | 100 Hz | `remoter_task()` — SBUS decoding + arm logic |
| `Autofly_Task` | 200 Hz | `AutoflyTask()` — path following |
| `Send_Task` | 100 Hz | Telemetry TX + ground station CMD RX |

### 1.4 Recommended Watch Window Variables

Add these to the µVision Watch window for live inspection during a debug session. All names are exact C identifiers.

**Flight status:**

| Watch expression | Source | Meaning |
| --- | --- | --- |
| `DroneStatus.ARM_Status` | `Global_file/robot_types.h:72` | 0 = DisArmed, 1 = Armed |
| `DroneStatus.FlyMode` | `Global_file/robot_types.h:73` | 0 = DangerousStop, 1 = SDK |
| `sbus_lost` | `Global_file/global_declare.h:135` | 1 = no SBUS signal (triggers SDK / virtual RC mode) |
| `sbus_last_valid_tick` | `Global_file/global_declare.h:136` | FreeRTOS tick of last valid SBUS packet |
| `GS_KeySDKflag` | `Global_file/global_declare.h:182` | Ground station parallel SDK trigger |
| `bench_mode_active` | `Global_file/global_declare.h:138` | 1 = throttle capped at 20% |

**Virtual RC sticks (used when** `**sbus_lost == 1**`**):**

| Watch expression | Index meaning | Normal value |
| --- | --- | --- |
| `virtual_rc_sticks[0]` | Throttle | 3000 (center/off) |
| `virtual_rc_sticks[1]` | Pitch | 3000 |
| `virtual_rc_sticks[2]` | Roll | 3000 |
| `virtual_rc_sticks[3]` | Yaw | 3000 |

Stick range: 2000 (min) to 4000 (max), center 3000. Defined in `TASK/StabilizerTask.c:21-35` via `eff_rc_*()` helpers.

**RC physical channels (if SBUS receiver is connected):**

| Watch expression | Meaning |
| --- | --- |
| `Remoter.ThrCtrler` | Physical throttle stick value (PWM units) |
| `Remoter.PitCtrler` | Physical pitch stick |
| `Remoter.RolCtrler` | Physical roll stick |
| `Remoter.YawCtrler` | Physical yaw stick |

Set in `TASK/RemoterTask.c:36-39`.

**Arm/disarm counters:**

| Watch expression | Meaning |
| --- | --- |
| `StickMotion.LeftStick_RightDown_cnt` | ARM hold counter (must reach 150) |
| `StickMotion.LeftStick_LeftDown_cnt` | DISARM hold counter (must reach 50) |

**PID outputs (inner loop):**

| Watch expression | Meaning |
| --- | --- |
| `Ctrler.gyroxPID.U` | Roll rate PID output |
| `Ctrler.gyroyPID.U` | Pitch rate PID output |
| `Ctrler.gyrozPID.U` | Yaw rate PID output |
| `Ctrler.Z_ratePID.U` | Altitude rate PID output |
| `Ctrler.pitchPID.U` | Pitch angle PID output |
| `Ctrler.rollPID.U` | Roll angle PID output |

**Motor outputs:**

| Watch expression | Meaning |
| --- | --- |
| `mymotor.motor1` | Motor 1 PWM command |
| `mymotor.motor2` | Motor 2 PWM command |
| `mymotor.motor3` | Motor 3 PWM command |
| `mymotor.motor4` | Motor 4 PWM command |

**IMU data:**

| Watch expression | Meaning |
| --- | --- |
| `imu_data.pit` | Pitch angle (degrees) |
| `imu_data.rol` | Roll angle (degrees) |
| `imu_data.yaw` | Yaw angle (degrees) |

**MRAC state:**

| Watch expression | Meaning |
| --- | --- |
| `mrac_state.pitch.e` | Pitch MRAC tracking error |
| `mrac_state.pitch.u_ad` | Pitch MRAC adaptive output |
| `mrac_state.roll.e` | Roll MRAC tracking error |
| `mrac_state.z_rate.e` | Z-rate MRAC tracking error |

### 1.5 How `sbus_lost` Triggers SDK Mode

`sbus_lost` is the primary gate that switches the flight controller from physical RC to virtual RC (computer) control.

**Where it is set:** `TASK/RemoterTask.c:43-54`

```c
// runs every 10 ms inside remoter_task()
if (sbus_last_valid_tick == 0U) {
    if (now > pdMS_TO_TICKS(500)) {
        sbus_lost = 1U;            // No SBUS ever received → lost after 500 ms
    }
} else {
    if ((now - sbus_last_valid_tick) > pdMS_TO_TICKS(500)) {
        sbus_lost = 1U;            // Last SBUS packet >500 ms ago → lost
    } else {
        sbus_lost = 0U;
    }
}
```

**Where it is read:** `TASK/StabilizerTask.c:21-35` inside `eff_rc_thr()`, `eff_rc_pit()`, `eff_rc_rol()`, `eff_rc_yaw()`. When `sbus_lost == 1`, these functions return `virtual_rc_sticks[n]` instead of physical `Remoter.*Ctrler` values.

**What this means for Keil bench testing:**

*   If you power on the board with **no SBUS receiver connected**, `sbus_lost` automatically becomes `1` after 500 ms.
*   The firmware then reads `virtual_rc_sticks[]` for all stick inputs.
*   You can inject stick values directly in the Watch window.

### 1.6 FlyMode Enum Values

Defined in `Global_file/global_declare.h:29-30`:

```c
#define FlyMode_DangerousStop   0
#define FlyMode_SDK             1
```

`FlyMode_DangerousStop` sets motors to zero and immediately disarms (`TASK/StabilizerTask.c:179-183`). `FlyMode_SDK` is normal operational mode. The mode is set by `Check_Fly_Mode()` in `TASK/RemoterTask.c:115-138`:

```c
void Check_Fly_Mode(void)
{
    // ...
    if (sbus_channel[4] == 200)  // physical kill switch
        DangerousStop_cnt++;
    else
        DangerousStop_cnt = 0;

    if (DangerousStop_cnt > 10)   // 50 ms
        DroneStatus.FlyMode = FlyMode_DangerousStop;
    else
        DroneStatus.FlyMode = FlyMode_SDK;
}
```

> ⚠️ **WARNING:** `**FlyMode_DangerousStop**` **(value 0) triggers immediate motor shutdown AND disarm. The firmware also writes** `**DisArmed**` **to** `**DroneStatus.ARM_Status**` **in** `**TASK/StabilizerTask.c:182**`**. If you inject** `**DroneStatus.FlyMode = 0**` **in the Watch window while armed and airborne, the drone will fall.**

### 1.7 Step-by-Step ARM Procedure (Physical RC)

ARM is gated by a stick gesture held for 150 × 10 ms = **1.5 seconds**.

Defined in `Global_file/global_declare.h:32`:

```c
#define ARM_Delay_time  150   // 150 calls × 10 ms = 1.5 seconds
```

**ARM gesture:** Left stick to **bottom-right** (Throttle MIN, Yaw MAX).

```
Condition:   is_Stick_MIN(Remoter.ThrCtrler)  &&  is_Stick_MAX(Remoter.YawCtrler)
Counter:     StickMotion.LeftStick_RightDown_cnt
Threshold:   >= ARM_Delay_time (150)
Effect:      DroneStatus.ARM_Status = Armed (1)
```

Source: `TASK/RemoterTask.c:63-64, 98-103`.

Stick threshold macros (`TASK/RemoterTask.c:57-59`):

```c
#define is_Stick_MAX(value)  ( value>3900 && value<4100 )  // ~4000
#define is_Stick_MIN(value)  ( value>1900 && value<2100 )  // ~2000
#define is_Stick_MID(value)  ( value>2900 && value<3100 )  // ~3000
```

**DISARM gesture:** Left stick to **bottom-left** (Throttle MIN, Yaw MIN), held 50 × 10 ms = **0.5 seconds**.

```c
#define DISARM_Delay_time  50  // 50 * 20ms = 1s (comment in code says 20ms; actual is 10ms = 0.5s)
```

Source: `Global_file/global_declare.h:33`, `TASK/RemoterTask.c:67-68, 104-108`.

### 1.8 ARM Procedure via Watch Window (No Physical RC)

When `sbus_lost == 1` (no RC connected), you can arm the drone purely from the Keil Watch window:

**Step 1** — Verify `sbus_lost` is 1 (automatic after 500 ms power-on with no SBUS).

**Step 2** — Set virtual sticks to the ARM gesture:

```
virtual_rc_sticks[0] = 2000.0   (Throttle MIN)
virtual_rc_sticks[3] = 4000.0   (Yaw MAX)
```

**Step 3** — Wait 1.5 seconds. Monitor `StickMotion.LeftStick_RightDown_cnt` climbing to 150.

**Step 4** — `DroneStatus.ARM_Status` becomes 1 (Armed).

**Step 5** — Immediately return sticks to center:

```
virtual_rc_sticks[0] = 3000.0
virtual_rc_sticks[3] = 3000.0
```

**Step 6** — Verify `DroneStatus.FlyMode == 1` (FlyMode\_SDK).

> ⚠️ **WARNING: After ARM, the firmware enters the motor control path. With props installed, motors will spin. Keep throttle (virtual\_rc\_sticks\[0\]) at or below 3000 (center) until intentionally flying. A value above ~3050 will spin motors noticeably.**

Alternatively, you can inject ARM directly (bypasses stick hold):

```
DroneStatus.ARM_Status = 1
DroneStatus.FlyMode = 1
```

Use this only for bench testing with no props.

### 1.9 MRAC Shadow vs Active Mode

The firmware supports two build configurations controlled by the preprocessor flag `ENABLE_MRAC_OUTPUT_INJECTION` in `TASK/StabilizerTask.c:284`:

```c
#if ENABLE_MRAC_OUTPUT_INJECTION == 1
    // MRAC adaptive signals are added to motor mixer
    Throttle_out = Ctrler.Z_ratePID.U + Throttle_th + (mrac_state.z_rate.u_ad * mrac_config_z.mrac_to_mixer);
    ...
#else
    // Shadow mode: MRAC runs but motors only see PID
    Throttle_out = Ctrler.Z_ratePID.U + Throttle_th;
    ...
#endif
```

Check which mode is compiled. In shadow mode, `mrac_state.*.u_ad` is computed but not injected — safe for initial flights.

The `l1_filtering_on` flag is part of `mrac_flags` (a `MRAC_FeatureFlags_t` struct in `API/mrac.c:14`). To see the current flag state, add `mrac_flags.l1_filtering_on` to the Watch window.

### 1.10 What to Observe in UART4 Telemetry Output

UART4 (PA0 TX, PA1 RX, 115200 8N1) carries the ground station frame stream. This is the same port that `serial_bridge.py` reads.

Two frame types are multiplexed. Frame rate:

*   **Frame A** (ID `0x01`): 80 Hz (every `frame_counter % 5 != 0` iteration). Source: `TASK/send_data.c:283`.
*   **Frame B** (ID `0x02`): 20 Hz (every 5th iteration). Source: `TASK/send_data.c:316`.

Each frame starts with sync bytes `0xAA 0xBB`. See Appendix A for the complete frame layout.

In a raw terminal at 115200 you will see binary data. Use the tool `ground_station/comm/show_frame_a_vofa_bytes.py` to decode Frame A manually, or let `serial_bridge.py` do the decoding.

**Frame A quick sanity check:** After a few seconds of running firmware you should see `Buf_Telemetry_UART4[0] == 0xAA` and `Buf_Telemetry_UART4[1] == 0xBB`. In the Watch window watch `Buf_Telemetry_UART4` as an array. Byte \[2\] should alternate 0x01 and 0x02.

### 1.11 Recommended Breakpoints for Initial Verification

| File | Line | Function | Purpose |
| --- | --- | --- | --- |
| `TASK/StabilizerTask.c` | 67 | `stabilizer_Task()` | Confirm 200 Hz control loop entry |
| `TASK/StabilizerTask.c` | 159 | `Update_Motor()` | Inspect motor outputs pre-PWM |
| `TASK/RemoterTask.c` | 99 | `Check_Stick_Motion()` | Confirm ARM counter incrementing |
| `TASK/RemoterTask.c` | 100 | `DroneStatus.ARM_Status = Armed` | Hit when ARM gesture completes |
| `TASK/send_data.c` | 460 | `Process_GroundStation_Command()` | Confirm CMD reception |
| `TASK/send_data.c` | 512 | virtual stick injection | Confirm CMD 0x06 is being applied |
| `BSP/usart4.c` | 129 | CRC check passes | Confirm valid commands arriving from PC |

Set these as conditional breakpoints only during initial verification; leave them disabled during normal flight.

### 1.12 Safety: Disarm Procedure and Emergency Stop

**Normal disarm via Watch window:**

```
DroneStatus.ARM_Status = 0   (DisArmed)
```

This is equivalent to the stick gesture but instant.

**Force dangerous stop (cuts motors immediately):**

```
DroneStatus.FlyMode = 0   (FlyMode_DangerousStop)
```

This triggers `Set_Zero_Motors()` and also sets `DroneStatus.ARM_Status = DisArmed` via `TASK/StabilizerTask.c:182`.

**Firmware self-protection:** `Update_Motor()` at `TASK/StabilizerTask.c:159-196` calls `Set_Zero_Motors()` whenever `ARM_Status == DisArmed`. Motors receive zero PWM. Confirmed: the SDK mode altitude guard at line 166 also calls `Set_IDLE_Motors()` when altitude (`Ctrler.Z_posPID.FB`) is below 0.3 m and throttle is below 2150.

### 1.13 Gotchas Specific to This Codebase

`**FlyMode**` **enum value 0 is DangerousStop, NOT "idle".** Never write `DroneStatus.FlyMode = 0` thinking you are putting the drone in a safe idle. It cuts motors and disarms immediately.

`**sbus_last_valid_tick**` **must be 0 or stale before** `**sbus_lost**` **activates.** If you plug in a SBUS receiver mid-session, `sbus_lost` clears to 0 within 500 ms and `virtual_rc_sticks` stop being used. Your Watch-window injected values are silently ignored.

`**ARM_Delay_time = 150**` **counts** at the `remoter_task()` rate of 100 Hz, making the ARM hold time 1.5 seconds. The comment in the code says "20ms" but `remoter_task()` runs at 10 ms intervals (`USER/main.c:186`).

**MRAC** `**mrac_to_mixer**` **defaults to 0 in uninitialized configs.** If `mrac_config_pitch.mrac_to_mixer == 0.0`, MRAC output is multiplied to zero regardless of active mode. This is intentional for bringing up the system step-by-step, but can be confusing.

**Throttle base offset** `**Throttle_th = 2800**` is hardcoded at `TASK/StabilizerTask.c:282`. This represents the hover throttle estimation. If you spin up motors without a proper hover throttle, tune this value first.

`**bench_mode_active**` **caps throttle.** When set to 1, `eff_rc_thr()` at `TASK/StabilizerTask.c:22-30` caps the effective throttle at `2000 + 0.2 × 2000 = 2400`. This is the bench test safety feature.

**UART4 TX uses** `**DMA1_Stream4**` (`BSP/usart4.c:73`). If you halt the MCU mid-DMA transfer, the DMA controller may stall. Resume the MCU before re-stopping if you observe a stuck DMA.

---

## Part 2 — Custom GUI (dashboard.py)

### 2.1 Prerequisites

**Python version:** 3.9 or newer (f-strings, `from __future__ import annotations`, `dataclasses` used throughout).

**Required packages** (exact imports from `ground_station/gui/dashboard.py:1-13` and `ground_station/comm/serial_bridge.py:1-12`):

```
pip install dearpygui pyserial
```

Core imports:

*   `dearpygui.dearpygui as dpg` — GUI framework (`dashboard.py:19`)
*   `serial` (pyserial) — UART communication (`serial_bridge.py:14`)
*   Standard library: `socket`, `threading`, `struct`, `json`, `csv`, `time`, `math`, `pathlib`, `queue`, `subprocess`, `argparse`, `re`, `shutil`

Optional (for file dialogs inside the GUI):

*   `tkinter` — used in `_browse_and_load_preset()` and `_browse_vofa_executable()` (`dashboard.py:1104, 1174`)

**VOFA+** (optional, for plotting): A third-party serial/UDP data visualizer. The dashboard can launch VOFA+ workspace files via the sidebar buttons if `vofa_executable` is set in `config.yaml`.

### 2.2 Configuration (`ground_station/config.yaml`)

The config file is at `ground_station/config.yaml`. It is a flat key:value YAML file (no nesting). Parsed by `load_config()` in `ground_station/comm/serial_bridge.py:82-119`.

**All fields with defaults:**

| Key | Default | Description |
| --- | --- | --- |
| `serial_port` | `COM3` | COM port for UART4 wireless link |
| `baud_rate` | `115200` | Must match firmware (`BSP/usart4.c:36`) |
| `vofa_host` | `127.0.0.1` | VOFA+ UDP host |
| `vofa_port_a` | `1347` | VOFA+ Frame A channel (100 Hz MRAC errors) |
| `vofa_port_b` | `1348` | VOFA+ Frame B channel (20 Hz full state) |
| `vofa_format` | `justfloat` | VOFA+ protocol: `justfloat`, `firewater_single_line`, `firewater_header_csv`, `firewater_multiline` |
| `simulate_udp_port` | `50007` | UDP port for `frame_simulator.py` input |
| `cmd_udp_port` | `1349` | Dashboard → serial\_bridge command channel |
| `telemetry_mirror_port` | `1350` | serial\_bridge → dashboard telemetry mirror |
| `vofa_executable` | (none) | Full path to VOFA+ executable |
| `cmd_host` | `127.0.0.1` | Host for command channel |

**Current repo config** (`ground_station/config.yaml`):

```
serial_port: COM6
baud_rate: 115200
vofa_host: 127.0.0.1
vofa_port_a: 1347
vofa_port_b: 1348
vofa_format: justfloat
simulate_udp_port: 50007
cmd_host: 127.0.0.1
cmd_udp_port: 1349
telemetry_mirror_port: 1350
```

Change `serial_port` to match the COM port your wireless UART dongle appears on.

### 2.3 Launch Command

From the project root directory:

```
# Hardware mode (real drone connected on COM6):
python ground_station/gui/dashboard.py

# Simulation mode (no hardware, use frame_simulator.py for synthetic telemetry):
# Terminal 1: start the bridge in simulate mode
python -m ground_station.comm.serial_bridge --simulate
# Terminal 2: start the simulator
python -m ground_station.comm.frame_simulator
# Terminal 3: start the dashboard
python ground_station/gui/dashboard.py
```

**Expected startup output (hardware mode):** The dashboard window "UAV Dashboard" opens. The left sidebar shows "Disconnect" if the bridge auto-connected, or "Connect" if the port was not available. The status indicators show "ARM: ?" until the first telemetry frame arrives.

**Startup auto-connect behavior:** `_connect_on_launch()` at `dashboard.py:457` first tries to ping a running `serial_bridge.py` via UDP on `cmd_udp_port`. If that fails, it starts a local `SerialBridge` object (`SerialBridge.start()` at `serial_bridge.py:246`). Then `_load_default_preset_if_exists()` loads `ground_station/presets/default.yaml` if present.

### 2.4 GUI Layout Overview

The window "UAV Dashboard" (`dashboard.py:1598`) is 1400×860 pixels and contains:

**Left sidebar (200 px wide):**

*   COM port dropdown (`com_selector`), baud dropdown (`baud_selector`), Connect/Disconnect button (`conn_button`)
*   Status: `ARM: ?/ON/OFF` (color coded), `FlyMode`, `SBUS`, `Bench` indicators
*   **STOP** button (red, large) — emergency stop (`stop_button`, calls `_emergency_stop()`)
*   VOFA+ workspace shortcut buttons: MRAC Errors, Adaptive Weights, PID Loops, Full Telemetry

**Main content area — tab bar:**

| Tab | Tag | Purpose |
| --- | --- | --- |
| Monitor | `tab_monitor` | Live progress bars for MRAC e/u\_ad + PID FB/Des/U text |
| Virtual RC | `tab_vrc` | SDK mode button, throttle/pitch/roll/yaw sliders, bench mode toggle |
| PID Tuning | `tab_pid` | Sub-tabs: Pitch / Roll / Yaw / Z (Kp/Ki/Kd sliders per axis) |
| MRAC Tuning | `tab_mrac` | Sub-tabs: Pitch / Roll / Yaw / Z (gamma, What\_limit, What\_tol sliders) |
| Paths | `tab_paths` | TWC/Sinusoid/Circle path inputs + 2D XY canvas |
| Safety | `tab_safety` | Expert mode toggle, speed/angle limits, safety profiles |
| Flight Log | `tab_flog` | Start/stop flight CSV recording, path memory |

**Bottom bar (all tabs):** Preset load combo + Browse + Save Preset button.

**Footer text** (`mon_footer`): Live single-line summary of `sbus_lost`, ARM, FlyMode, bench state.

### 2.5 Serial Connection Verification Steps

1.  Set `serial_port` in `config.yaml` to your COM port.
2.  Launch `dashboard.py`.
3.  If the sidebar shows "Disconnect", the bridge connected. If "Connect", click Connect.
4.  Watch the `ARM: ?` indicator in the sidebar. Once it changes to `ARM: OFF` or `ARM: ON`, telemetry is flowing.
5.  Check the `mon_footer` text at the bottom — it shows `sbus_lost`, ARM, FlyMode.
6.  If no telemetry after 3 seconds: confirm baud (115200), confirm the UART4 PA0/PA1 wiring, and try the `--test-com` diagnostic: `python -m ground_station.comm.serial_bridge --test-com` (tests COM6/COM4/COM5 for 3 seconds each and prints byte counts, `serial_bridge.py:972`).

### 2.6 SDK Mode Activation

**Button location:** Virtual RC tab → "SDK MODE" button (tag `vrc_sdk_btn`).

**What it sends:** CMD 0x04, index 1, value 0.0 (`dashboard.py:1207, 1257`):

```python
self._send_cmd(0x04, 1, 0.0)   # dashboard.py:1207
```

**Firmware handler** (`TASK/send_data.c:557-562`):

```c
else if (id == 0x04) {
    if (idx == 1) {
        DroneStatus.FlyMode = FlyMode_SDK;   // value 1
    }
}
```

The button is **disabled by default** and only enables when connected (`dashboard.py:576`).

> ⚠️ **WARNING: SDK mode does not arm the motors. You must arm separately (see Section 2.7). Pressing SDK MODE only sets** `**DroneStatus.FlyMode = 1**`**. Without ARM, motors stay at zero.**

### 2.7 Arm Sequence via GUI

The GUI does not have a dedicated ARM button. Arming is done by injecting the stick gesture via the virtual RC sliders or by the firmware's physical RC stick hold.

**GUI arm procedure (assumes** `**sbus_lost == 1**` **and** `**FlyMode_SDK**`**):**

1.  Confirm the sidebar shows "SBUS: GS" (meaning `sbus_lost == 1`).
2.  Click "SDK MODE" to ensure `FlyMode = SDK`.
3.  In the Virtual RC tab, set sliders:
    *   **Throttle** slider (`vrc_thr_slider`): drag to **2000** (minimum — left end)
    *   **Yaw** slider (`vrc_yaw_slider`): drag to **4000** (maximum — right end)
4.  Hold for **1.5 seconds** (150 × 10 ms at `ARM_Delay_time = 150`). The `DroneStatus.ARM_Status` will change.
5.  The sidebar ARM indicator flips from "ARM: OFF" (red) to "ARM: ON" (green).
6.  Return Throttle to center (3000) and Yaw to center (3000) immediately after ARM.

Each slider change sends CMD 0x06 (`dashboard.py:1211`):

```python
def _on_vrc_slider(self, sender, app_data, user_data):
    idx = int(user_data)
    self._send_cmd(0x06, idx, float(app_data))
```

Firmware applies it only when `sbus_lost == 1 && FlyMode == FlyMode_SDK && idx < 4` (`TASK/send_data.c:512-515`).

> ⚠️ **WARNING: The Virtual RC sliders are disabled (grayed out) when** `**sbus_lost == 0**` **(physical RC active). If a physical RC receiver is connected and sending valid SBUS, the GUI sliders have no effect on the drone.**

### 2.8 RC Virtual Stick Control

**Slider tags and index mapping:**

| Slider tag | user\_data index | Maps to | Range | Center |
| --- | --- | --- | --- | --- |
| `vrc_thr_slider` | 0 | `virtual_rc_sticks[0]` = Throttle | 2000–4000 | 3000 |
| `vrc_pit_slider` | 1 | `virtual_rc_sticks[1]` = Pitch | 2000–4000 | 3000 |
| `vrc_rol_slider` | 2 | `virtual_rc_sticks[2]` = Roll | 2000–4000 | 3000 |
| `vrc_yaw_slider` | 3 | `virtual_rc_sticks[3]` = Yaw | 2000–4000 | 3000 |

Defined in `dashboard.py:1261-1302`. Constants from `dashboard.py:90-96`.

**Bench mode checkbox** (`vrc_bench_cb`): When ticked, sends CMD 0x07 index 0 value 1.0, which sets `bench_mode_active = 1` in firmware (`TASK/send_data.c:519-522`). The throttle slider maximum drops to 2400 (`BENCH_THR_MAX = 2000 + 0.2 × 2000 = 2400`, `dashboard.py:96`). Firmware enforces the same cap in `eff_rc_thr()` (`TASK/StabilizerTask.c:22-30`).

### 2.9 Live PID Tuning Workflow

**Tab:** PID Tuning → sub-tabs Pitch / Roll / Yaw / Z.

Each sub-tab has outer PID (angle loop) and inner PID (rate loop) sliders for Kp, Ki, Kd. The Z sub-tab has only inner (Z\_ratePID).

**How it works:** Each slider callback calls `_debounced_pid_gain()` → `_debouncer.call()` (50 ms debounce, `dashboard.py:335`) → `_send_cmd(0x01, index, value)`.

**Debounce:** 50 ms (`DebouncedSender(delay_s=0.05)` at `dashboard.py:335`). Slider changes within 50 ms are coalesced — only the last value in any 50 ms window is sent. This prevents flooding the STM32 command queue.

**CMD 0x01 index encoding** (`dashboard.py:887`, `TASK/send_data.c:471-488`):

```
index = axis_firmware_idx * 3 + gain_idx
axis:  pitch=0, roll=1, yaw=2, gyrox=3, gyroy=4, gyroz=5, Z_rate=6
gain:  Kp=0, Ki=1, Kd=2
```

Example: To update pitch outer Kp, `index = 0*3+0 = 0`. To update gyroz Kd, `index = 5*3+2 = 17`.

**Verifying a PID update landed:** In Keil Watch window, inspect `Ctrler.pitchPID.Kp` (or whichever axis/gain) immediately after moving the slider.

### 2.10 Live MRAC Tuning Workflow

**Tab:** MRAC Tuning → sub-tabs Pitch / Roll / Yaw / Z.

Each sub-tab has sliders for:

*   **Gamma** (`gamma[0..MAX_NUM_BASIS-1]`): Learning rate per basis function. Higher = faster adaptation, potentially less stable.
*   **What\_limit** (`What_limit[0..MAX_NUM_BASIS-1]`): Upper bound on each adaptive weight.
*   **What\_tol** (`What_tol[0..MAX_NUM_BASIS-1]`): Projection tolerance band (dead-band near limit).

Sliders for basis indices >= `MAX_NUM_BASIS` are hidden automatically (`_update_mrac_visibility()` at `dashboard.py:850`).

**CMD assignments** (`TASK/send_data.c:492-508`, `dashboard.py:898-910`):

| CMD ID | Sets | Physical effect |
| --- | --- | --- |
| `0x02` | `mrac_config_[axis].gamma[elem]` | Adaptation speed for one basis |
| `0x05` | `mrac_config_[axis].What_limit[elem]` | Authority cap on one adaptive weight |
| `0x08` | `mrac_config_[axis].What_tol[elem]` | Tolerance band before hard projection |

**Index encoding** for all three CMDs (`dashboard.py:900`):

```
index = ((axis_cfg_idx & 0x0F) << 4) | (elem & 0x0F)
axis:  pitch=0, roll=1, yaw=2, z=3
elem:  0..MAX_NUM_BASIS-1
```

**Physical meaning:**

*   CMD `0x02` (gamma): Increases gamma → MRAC adapts faster to disturbances (e.g., motor fault, wind gust). Too high → oscillation.
*   CMD `0x05` (What\_limit): Reduces What\_limit → caps maximum corrective authority MRAC can claim. Reduces drift risk.
*   CMD `0x08` (What\_tol): Sets the soft boundary band. Zero tolerance = hard clip. Small positive = smooth saturation before hard limit.

**Mixer tab** (inside Safety tab, expert mode): CMD `0x03` sets `mrac_to_mixer` (MRAC output scaling into PWM mixer) and `u_max` (per-axis saturation). Source: `TASK/send_data.c:525-540`.

### 2.11 Preset Save/Load Workflow

**Preset files live at:** `ground_station/presets/*.yaml`

**Format** (per-axis, inline maps):

```
pitch:
  outer_pid: {Kp: 2.0, Ki: 0.0, Kd: 0.5}
  inner_pid: {Kp: 8.0, Ki: 0.1, Kd: 0.2}
  mrac: {gamma: [1.5, 0.2, 0.05, 0.05, 0.1, 0.1, 0.0, 0.0], What_limit: [0.15, 0.05, ...], What_tol: [...]}
  mixer: {MRAC_TO_MIXER: 500.0, U_MAX: 10.0}
roll:
  ...
yaw:
  ...
z:
  inner_pid: {Kp: 5.0, Ki: 0.0, Kd: 0.1}
  mrac: {...}
  mixer: {...}
```

Z axis has no `outer_pid` because there is no separate Z angle loop — only `Z_ratePID`. Source: `dashboard.py:1061`.

**Save a preset:**

1.  Tune sliders to desired values.
2.  Click "Save Preset" (bottom bar) → modal opens.
3.  Enter a filename (alphanumeric, underscores). File will be `ground_station/presets/<name>.yaml`.
4.  Click Save.

**Load a preset:**

*   Use the "Load preset:" combo at the bottom bar to pick any file in `presets/`.
*   Or click "Browse…" to open a file picker.
*   The `default.yaml` preset is auto-loaded on startup if it exists (`dashboard.py:975-985`).

**Important:** Loading a preset immediately pushes all gain values to the firmware via CMD 0x01, 0x02, 0x05, 0x08, 0x03. The `_loading_preset` flag (`dashboard.py:333`) suppresses debounced sends during load to prevent the slider callbacks from firing; instead `_apply_preset_payload()` calls `_send_cmd()` once all sliders are set.

### 2.12 Autonomous Paths

**Tab:** Paths

All path commands require:

*   `FlyMode_SDK` (send SDK mode first via Virtual RC tab)
*   A position source selected in the "Position source" combo (`combo_pos_source`)
*   Available sources: `Optical Flow` (real hardware), `Simulation` (PathExecutor integrates its own position), `SLAM`/`GPS` (disabled — "coming soon")

The path buttons are disabled until a valid position source is selected (`_paths_refresh_ui()` at `dashboard.py:669`).

#### TWC (Target World Coordinate — Point to Point)

*   Inputs: `twc_tx` (target x), `twc_ty` (target y), `twc_tz` (target z), `twc_yaw` (yaw deg)
*   Button: "Execute TWC" (`btn_path_twc_exec`)
*   Sends CMDs `0x0A` index 0–4 (`dashboard.py:797-801`):
*   Arrival detected when `|position - target| < 0.15 m` (`TASK/StabilizerTask.c:359`). `TWC_arrived` flag in Frame A telemetry.

#### Sinusoid Path

*   Inputs: center (cx/cy/cz), amplitude (m), freq (Hz), duration (s), axis (0=X, 1=Y, 2=Z)
*   Button: "Execute sinusoid" (`btn_path_sin_exec`)
*   Sends CMDs `0x0B` index 0–7 (`dashboard.py:815-822`)
*   Runs inside firmware `AutoflyTask_RunSinusoid()` (referenced in Community 0 graph nodes)

#### Circle Path

*   Inputs: center (cx/cy/cz), radius (m), omega (rad/s), duration (s)
*   Button: "Execute circle" (`btn_path_circ_exec`)
*   Sends CMDs `0x0C` index 0–6 (`dashboard.py:835-841`)

#### Aborting Any Path

*   **STOP button** (sidebar): calls `_emergency_stop()` at `dashboard.py:874`. Sends `0x0D idx=0` (abort all paths) then 50 ms later `0x04 idx=0` (DangerousStop). Sets `DroneStatus.FlyMode = FlyMode_DangerousStop` in firmware (`TASK/send_data.c:447-458`).
*   **Spacebar** is also bound to the emergency stop (`dashboard.py:1610`).
*   **CMD 0x0D idx=0** alone aborts all paths and neutral sticks but without DangerousStop.

> ⚠️ **WARNING: Path commands only work when** `**FlyMode_SDK == 1**`**. If the drone loses SDK mode for any reason (physical kill switch on SBUS channel 4, or** `**DangerousStop_cnt > 10**`**), all path following stops immediately.**

### 2.13 Telemetry Monitoring

#### Frame A (100 Hz) — VOFA+ port 1347

VOFA+ JustFloat channel map (13 channels when `vofa_format = justfloat`):

| VOFA+ Ch | Name | C source |
| --- | --- | --- |
| I0 | `mrac.pitch.e` | `mrac_state.pitch.e` |
| I1 | `mrac.pitch.u_ad` | `mrac_state.pitch.u_ad` |
| I2 | `mrac.roll.e` | `mrac_state.roll.e` |
| I3 | `mrac.roll.u_ad` | `mrac_state.roll.u_ad` |
| I4 | `mrac.yaw.e` | `mrac_state.yaw.e` |
| I5 | `mrac.yaw.u_ad` | `mrac_state.yaw.u_ad` |
| I6 | `mrac.z.e` | `mrac_state.z_rate.e` |
| I7 | `mrac.z.u_ad` | `mrac_state.z_rate.u_ad` |
| I8 | `status.arm` | `DroneStatus.ARM_Status` |
| I9 | `status.flymode` | `DroneStatus.FlyMode` |
| I10 | `status.sbus_lost` | `sbus_lost` |
| I11 | `status.twc_execute` | `TWC.execute` |
| I12 | `status.twc_arrived` | `TWC_arrived` |

Source: `ground_station/comm/serial_bridge.py:399-469`.

#### Frame B (20 Hz) — VOFA+ port 1348

First `4 × (MAX_NUM_BASIS + 2)` channels are MRAC weights; then 12 × 3 PID channels (FB/Des/U per loop); then path state. Full map in `serial_bridge.py:471-596`.

Key Frame B channels for flight debugging:

| Name pattern | Meaning |
| --- | --- |
| `mrac.pitch.theta_0..N` | Adaptive weights for pitch |
| `pid.pitch.FB` / `.Des` / `.U` | Pitch outer PID |
| `pid.gyrox.FB` / `.Des` / `.U` | Pitch inner (gyro rate) PID |
| `pid.z_rate.FB` / `.Des` / `.U` | Altitude rate PID |
| `pid.locx.FB` / `.Des` | Optical flow X position |
| `path.active_path_mode` | 0=none, 1=TWC, 2=sinusoid, 3=circle |

#### VOFA+ Integration

1.  Install and open VOFA+. Set "Connection type" to UDP, port 1347 for Frame A (JustFloat protocol).
2.  Add second UDP connection on port 1348 for Frame B.
3.  The sidebar VOFA+ shortcut buttons ("MRAC Errors", "Adaptive Weights", etc.) open `.vofa` workspace files from `ground_station/presets/vofa/`. Set the `vofa_executable` path in `config.yaml`.

### 2.14 Flight Logging

**Tab:** Flight Log

*   **"Start recording"** button (`btn_log_start`): Creates `ground_station/logs/flight_<unix_timestamp>.csv` and begins logging. Source: `dashboard.py:1542-1549`.
*   **"Stop"** button (`btn_log_stop`): Closes the file and prints row count + file size. Source: `dashboard.py:1551-1553`.

**Logging rate:** 20 Hz (sampled in `_frame()` every 50 ms, `dashboard.py:659`). Both Frame A and Frame B snapshots are logged per sample.

**CSV format** (`ground_station/scripts/flight_logger.py:26`):

```
t_s, frame, key, value
0.0500, A, mrac.pitch.e, 0.01234567
0.0500, A, status.arm, 1.0
0.0500, B, pid.pitch.FB, -2.3456
...
```

**Post-flight analysis:**

```python
from ground_station.scripts.flight_logger import FlightLogger
from pathlib import Path
result = FlightLogger.analyze(Path("ground_station/logs/flight_12345.csv"))
# Returns: {duration, pitch_e_min, pitch_e_max, ...}
```

**Path memory:** "Record path" button samples `pid.locx.Des` and `pid.locy.Des` at 10 Hz and saves to `logs/path_<timestamp>.csv`.

### 2.15 Gotchas Specific to GUI Usage

**VOFA+ JustFloat requires a fixed channel count.** If `MAX_NUM_BASIS` changes in firmware, the channel count in Frame B changes and VOFA+ will misalign. The GUI hides extra MRAC sliders but VOFA+ does not automatically re-subscribe. Restart VOFA+ connections if `MAX_NUM_BASIS` changes.

**Dashboard tries a remote bridge first.** At startup, `_try_remote_bridge()` at `dashboard.py:474` pings `cmd_udp_port` (1349). If a stale `serial_bridge.py` process from a previous session is still running in the background, the dashboard may connect to it instead of your fresh hardware. Kill any background bridge processes before re-launching.

**CMD 0x06 virtual stick injection has two guards.** Firmware rejects it if EITHER `sbus_lost != 1` OR `FlyMode != FlyMode_SDK` (`TASK/send_data.c:513`). Moving the GUI sliders while SBUS is active does nothing — but no error is shown.

**Preset loading pushes gains immediately.** Opening a preset replaces all live firmware PID and MRAC values. Do not load an untested preset while the drone is armed.

**Emergency stop sends two CMDs.** `_emergency_stop()` first sends `0x0D idx=0` (path abort), then 50 ms later `0x04 idx=0` (DangerousStop). If the 50 ms timer thread is interrupted (process kill), only the first CMD reaches the firmware. Always verify the drone actually disarmed after E-stop.

**The "SDK MODE" button uses debounce.** `_sdk_button()` at `dashboard.py:1206` routes through `_debouncer.call(...)` with key `"flymode_sdk"`. If you click it twice rapidly, only one CMD is sent.

**Paths tab buttons are disabled until position source != "None".** Even if the firmware is in SDK mode and armed, the buttons will not respond until you select "Optical Flow" or "Simulation" in the combo.

---

## Part 3 — Keil to GUI Transition Handoff

### 3.1 When to Transition

**Complete in Keil first:**

*   `sbus_lost` confirmed to be `1` automatically (no SBUS receiver plugged in)
*   `DroneStatus.FlyMode == 1` (FlyMode\_SDK) confirmed in Watch window
*   ARM/disarm cycle verified at least once via Watch window stick injection
*   Motor spin-up confirmed safe (props off, `bench_mode_active = 1` recommended)
*   `virtual_rc_sticks[]` changes in Watch window produce visible motor PWM changes in `mymotor.motor*`
*   UART4 telemetry confirmed: raw bytes visible or `Buf_Telemetry_UART4[0] == 0xAA`

**What GUI adds over Keil:**

*   Live PID slider tuning without pausing firmware
*   MRAC weight monitoring (progress bars update at 5 Hz via telemetry)
*   Preset management
*   Structured arm/disarm via slider gestures
*   Path execution (TWC, sinusoid, circle)
*   CSV flight logging
*   VOFA+ workspace shortcuts

### 3.2 Stopping Keil Debug Without Rebooting Firmware

You **cannot coexist** — see Section 3.3. The recommended procedure:

1.  In Keil: set `DroneStatus.ARM_Status = 0` (DisArmed) if armed.
2.  In Keil: press the **Stop Debug Session** button (Ctrl+F5, or Debug menu → Stop Debugging).
3.  The MCU continues running (it is not reset by stopping the debugger, only by a hard reset or power cycle). The firmware carries on from where it was.
4.  The ST-Link releases the SWD bus but the MCU is live.

> ⚠️ **WARNING: Stopping the Keil debugger does NOT reset or halt the STM32. If the drone was armed when you stopped the debug session, it remains armed. Always disarm before exiting the debugger.**

### 3.3 Serial Port Acquisition — Can Keil and `serial_bridge.py` Coexist?

**No, they cannot share UART4 simultaneously.**

UART4 (the ground station telemetry port) is a hardware UART peripheral. Only one software process can hold a COM port open at a time.

Keil's debug session uses the SWD interface (ST-Link), **not** UART4. If you are not actively receiving UART4 data inside Keil (e.g., no UARTView window open), the COM port is free for `serial_bridge.py`.

**Conflict scenario:** If you opened a UART terminal (CoolTerm, PuTTY, or Keil's own UART window) on the UART4 COM port during debugging, it must be closed before `serial_bridge.py` can open it.

**Safe transition steps:**

1.  Close any serial terminal viewing UART4 data.
2.  Stop Keil debug session (Ctrl+F5). SWD is released; UART4 COM port was never held by Keil's debugger itself.
3.  Launch `serial_bridge.py` (or the dashboard, which auto-starts it in-process).

### 3.4 Step-by-Step Handoff Checklist

Follow these steps in order each time you transition from Keil to GUI:

```
[ ] 1. In Keil Watch window: set DroneStatus.ARM_Status = 0  (disarm for safety)
[ ] 2. In Keil: confirm mymotor.motor1-4 read ~2000 (idle) or 0 (motors off)
[ ] 3. In Keil: press Stop Debug (Ctrl+F5). MCU stays live.
[ ] 4. Close any serial terminal open on the UART4 COM port.
[ ] 5. Edit ground_station/config.yaml: confirm serial_port matches the UART4 dongle.
[ ] 6. Launch: python ground_station/gui/dashboard.py
[ ] 7. Sidebar should show "Disconnect" within 2 seconds if auto-connect succeeds.
[ ] 8. Wait for ARM indicator to change from "ARM: ?" to "ARM: OFF".
[ ] 9. Verify mon_footer shows: sbus_lost=1 | ARM=OFF | FlyMode: SDK | bench=OFF
[ ] 10. Load a preset (or leave at firmware defaults — Keil-set gains survive the transition).
[ ] 11. Proceed with GUI workflow (Section 2.7 onward).
```

### 3.5 Verifying GUI Has Correct Telemetry After Transition

After connecting, check the following in the Monitor tab progress bars and the mon\_footer status line:

| Check | Expected value | Source channel |
| --- | --- | --- |
| `status.arm` | 0.0 (off) | Frame A `status.arm` |
| `status.flymode` | 1.0 (SDK) | Frame A `status.flymode` |
| `status.sbus_lost` | 1.0 (lost) | Frame A `status.sbus_lost` |
| `mrac.pitch.e` | Small value near 0 (idle) | Frame A I0 |
| Sidebar SBUS text | "SBUS: GS" | Derived from `status.sbus_lost` |
| Sidebar ARM text | "ARM: OFF" (red) | Derived from `status.arm` |
| Footer | \`sbus\_lost=1 | ARM=OFF |

If `status.flymode` shows 0 (DangerousStop) after connecting: the MCU was left in DangerousStop. Click SDK MODE on the Virtual RC tab to recover.

If `status.sbus_lost` shows 0 (RC active): a physical SBUS receiver is connected and sending valid data. The virtual RC sliders will be locked/grayed. This is safe — you can still use the PID tuning and monitoring tabs, but RC stick commands must come from the physical transmitter.

**Telemetry path after transition:**

```
STM32 UART4 TX (100 Hz)
  → USB-UART dongle
    → Windows COM port (e.g. COM6)
      → serial_bridge.py SerialBridge._rx_loop()
        → _handle_frame() → _unpack_frame_a() / _unpack_frame_b()
          → _last_telemetry_a / _last_telemetry_b (thread-safe dict)
          → _mirror_telemetry_udp() → UDP 127.0.0.1:1350
            → Dashboard._telemetry_listener() → self._telem
              → _frame() → ARM/FlyMode/sbus_lost indicators, Monitor tab, footer
```

If you started `serial_bridge.py` as an external process and the dashboard connects to it as a remote bridge, the path is the same except the `serial_bridge.py` is in a separate process and the dashboard only uses the UDP mirror (no direct `get_telemetry_snapshot()` call).

---

## Appendix A — Frame Format Reference

### Telemetry (STM32 → PC) — `0xAA 0xBB`

```
[0xAA] [0xBB] [frame_type] [LEN_hi] [LEN_lo] [MAX_NUM_BASIS] [payload…] [CRC8_XOR]
```

*   Sync: `0xAA 0xBB` (`TASK/send_data.c:280-281`)
*   `frame_type`: `0x01` = Frame A (80 Hz), `0x02` = Frame B (20 Hz)
*   `LEN`: 16-bit big-endian payload length
*   `MAX_NUM_BASIS`: current MRAC basis count (firmware compile-time constant)
*   `CRC8`: XOR over bytes from `frame_type` through end of payload (bytes index 2..len-1)

**Frame A payload (LEN=37):**

*   8 floats (32 bytes): pitch.e, pitch.u\_ad, roll.e, roll.u\_ad, yaw.e, yaw.u\_ad, z.e, z.u\_ad
*   5 uint8 (5 bytes): ARM\_Status, FlyMode, sbus\_lost, TWC.execute, TWC\_arrived

**Frame B payload size:** `4 × (MAX_NUM_BASIS + 2) × 4 + 36 × 4 + 22` bytes.

### Command (PC → STM32) — `0xCC 0xDD`

```
[0xCC] [0xDD] [CMD_ID] [INDEX] [VALUE float32 LE] [CRC8_XOR]
```

*   Total: 9 bytes
*   Sync: `0xCC 0xDD` (`BSP/usart4.c:106`, `ground_station/comm/serial_bridge.py:143-144`)
*   `CRC8`: XOR over bytes 2–7 (CMD\_ID, INDEX, 4 bytes of VALUE)

Parsed by `Handle_UART4_GroundStation_Command()` at `BSP/usart4.c:99` and queued into `gs_cmd_queue[8]`. Dispatched by `Process_GroundStation_Command()` at `TASK/send_data.c:460`.

---

## Appendix B — CMD ID Quick Reference

| CMD ID | Name | Index | Value | Firmware handler (send\_data.c) |
| --- | --- | --- | --- | --- |
| `0x01` | PID gain | `axis*3 + gain` (0..20) | gain value | Line 472 |
| `0x02` | MRAC gamma | \`(axis\<\<4) | elem\` | learning rate |
| `0x03` | Mixer/saturation | 0–3 = mrac\_to\_mixer, 4–7 = u\_max, 8 = thr\_min, 9 = thr\_max | float | Line 526 |
| `0x04` | Flight mode | 0 = DangerousStop+abort, 1 = SDK | ignored / ignored | Line 557 |
| `0x05` | MRAC What\_limit | \`(axis\<\<4) | elem\` | weight upper bound |
| `0x06` | Virtual RC sticks | 0=thr 1=pit 2=rol 3=yaw | PWM 2000–4000 | Line 512 |
| `0x07` | Bench mode | 0 | ≥0.5 = on | Line 519 |
| `0x08` | MRAC What\_tol | \`(axis\<\<4) | elem\` | tolerance band |
| `0x09` | GS safety limits | 0=horiz\_mps 1=vert\_mps 2=pitch\_deg 3=roll\_deg | float | Line 544 |
| `0x0A` | TWC target | 0=x 1=y 2=z 3=yaw 4=execute | float / 1.0 | Line 566 |
| `0x0B` | Sinusoid path | 0–7 (center,amp,freq,dur,axis,active) | float | Line 583 |
| `0x0C` | Circle path | 0–6 (center,r,omega,dur,active) | float | Line 614 |
| `0x0D` | Abort all paths | 0 | 1.0 | Line 641 |
| `0x0E` | GS\_KeySDKflag | 0 | 1=enable 0=disable | Line 648 |

---

## Appendix C — Key Variable Map

| C variable | File:line | Type | Description |
| --- | --- | --- | --- |
| `DroneStatus.ARM_Status` | `Global_file/robot_types.h:72` | `uint8` | 0=DisArmed, 1=Armed |
| `DroneStatus.FlyMode` | `Global_file/robot_types.h:73` | `uint8` | 0=DangerousStop, 1=SDK |
| `sbus_lost` | `Global_file/global_declare.h:135` | `volatile uint8_t` | 1 = SBUS signal absent >500 ms |
| `sbus_last_valid_tick` | `Global_file/global_declare.h:136` | `volatile uint32_t` | FreeRTOS tick of last valid SBUS |
| `virtual_rc_sticks[4]` | `Global_file/global_declare.h:137` | `float[4]` | \[thr, pit, rol, yaw\], 2000–4000 |
| `bench_mode_active` | `Global_file/global_declare.h:138` | `volatile uint8_t` | 1 = throttle capped at 20% |
| `GS_KeySDKflag` | `Global_file/global_declare.h:182` | `volatile uint8_t` | SDK parallel mission trigger |
| `TWC.execute` | `TASK/StabilizerTask.c:17` | `uint8` (in struct) | 1 = TWC point targeting active |
| `TWC_arrived` | `Global_file/global_declare.h:149` | `volatile uint8_t` | 1 = within 0.15 m of TWC target |
| `ARM_Delay_time` | `Global_file/global_declare.h:32` | `#define` | 150 (counts at 100 Hz = 1.5 s) |
| `DISARM_Delay_time` | `Global_file/global_declare.h:33` | `#define` | 50 (counts at 100 Hz = 0.5 s) |
| `FlyMode_SDK` | `Global_file/global_declare.h:30` | `#define` | 1 |
| `FlyMode_DangerousStop` | `Global_file/global_declare.h:29` | `#define` | 0 |
| `mrac_state` | `API/mrac.c:13` | `MRAC_State_t` | All 4-axis MRAC runtime state |
| `mrac_config_pitch` | `API/mrac.c:17` | `MRAC_AxisConfig_t` | Pitch MRAC parameters |
| `Ctrler` | `Global_file/robot_types.h:34` | `CtrlerTypeDef` | All PID loop struct |
| `mymotor.motor1..4` | (motor output struct) | `float` | Motor PWM commands |
| `Throttle_th` | `TASK/StabilizerTask.c:8` | `short` | Hover throttle offset (2800) |
| `Buf_Telemetry_UART4` | `TASK/send_data.c:271` | `UCHAR8[512]` | UART4 telemetry TX buffer |
| `gs_cmd_queue[8]` | `BSP/usart4.c:96` | `GS_Cmd_t[8]` | Received command ring buffer |
| `sinusoid_path` | `Global_file/global_declare.h:164` | `SinusoidPath_t` | Sinusoidal path parameters |
| `circle_path` | `Global_file/global_declare.h:179` | `CirclePath_t` | Circle path parameters |

```
0x0A idx=0 → TWC.target_x
0x0A idx=1 → TWC.target_y
0x0A idx=2 → TWC.target_z
0x0A idx=3 → TWC.set_yaw
0x0A idx=4 = 1.0 → TWC.execute = 1 (start)
```