---
name: lab-session
description: >
  Operates the agent side of a live lab session — drone powered, CMSIS-DAP probe
  attached, operator at the bench. Use when the user says "I have the drone
  powered on and the probe attached", "let's run live", "flash and test", or any
  variation that puts hardware in scope. Gates every write-path action on an
  explicit operator authorization sentence and on a four-step pre-flight that
  verifies probe, ELF, bridge freshness, and DISARMED state.
---

# Lab session — agent side

When the user puts the bench live, this skill governs what you may do. It is the
operator-facing document at `docs/lab-runbook.md` plus the always-on guard rail
at `.cursor/rules/lab-session.mdc`. Read both before any hardware-touching
action.

## Authorization gate

The user must give an explicit sentence of the form:

> "You are authorized to modify code, rebuild, flash, and live-probe the
> running firmware. The drone is disarmed, props are off, and the bench is
> safe. Proceed."

Without that sentence, stay offline. Read-only `livewatch read` is allowed once
`tasks.py doctor` is green. No flash, no mass-erase, no live reset, no probe
writes of any kind.

Once authorized, the user steps back. You decide what to do based on the task
at hand — bug-hunt loop, acceptance test, calibration sweep. Do not ask
permission for each rebuild; iterate freely until the user calls the loop done
or you have to surface a finding.

## Mandatory pre-flash sequence

Before `tasks.py flash`, run all four checks in order. Any failure → abort and
report; do not attempt a workaround.

```bash
# 1. Toolchain + probe enumerated
.venv/bin/python tasks.py doctor

# 2. ELF on disk matches the build actually flashed (catches stale ELF).
#    On Linux the ELF is firmware/build/JX_FLY.elf (CMake); Windows default
#    is OBJ/JX_FLY.axf (Keil). Pass --elf before the subcommand.
.venv/bin/python -m ground_station.livewatch --elf firmware/build/JX_FLY.elf verify

# 3. Bridge is fresh, not cached (USB-wired: usually passes immediately;
#    wireless: --samples 5 --delay-ms 20 --require-monotonic)
.venv/bin/python -m ground_station.livewatch --elf firmware/build/JX_FLY.elf \
    freshness s_ekf.x[3] --samples 5 --delay-ms 20 --require-monotonic

# 4. Drone is DISARMED
.venv/bin/python -m ground_station.livewatch --elf firmware/build/JX_FLY.elf \
    read DroneStatus.ARM_Status
```

ARM_Status must equal DISARMED. Any other value (ARMED, FAULT, INIT) is a hard
abort. The user disarms via RC; you do not bypass this check.

## One-time box setup

The first lab session on a fresh Linux box needs three kernel/Python prereqs
in place, otherwise flash silently no-ops:

```bash
# CMSIS Pack for the chip. Without this, pyocd uses a cortex_m fallback
# whose flash algorithm pretends to program and reports success without
# committing bytes to flash.
.venv/bin/python -m pyocd pack update
.venv/bin/python -m pyocd pack install stm32f407

# Bridge HID driver. The ATK-HS-V3 (Microchip 04d8:00df) ships a 2-channel
# CDC-ACM + HID device. Without an explicit modprobe block, Linux's
# hid_mcp2200 grabs the HID interface before pyocd can open it; writes are
# silently dropped.
sudo cp etc-modprobe-d/blacklist-hid-mcp2200.conf /etc/modprobe.d/
sudo modprobe -r hid_mcp2200
# Replug the bridge once. Verify the binding moved to hid-generic:
#   cat /sys/bus/hid/devices/0003:04D8:00DF.*/uevent | head -1
#   # -> DRIVER=hid-generic
```

Without both, `tasks.py flash` exits 0 but the FC keeps running its prior
firmware. Diagnose with:

```bash
.venv/bin/python -m pyocd list --targets | grep stm32f407     # DFP installed?
.venv/bin/python -m pyocd list                                  # probe seen?
cat /sys/bus/hid/devices/0003:04D8:00DF.*/uevent | head -1     # driver correct?
```

Root cause trace: `sessions_summary/2026-08-16-wireless-bridge-flash-dual-bug.md`.

## Iterating inside an authorized loop

Once pre-flight is green and the user has authorized the loop, the typical
cycle is:

```
edit source
  ↓
.venv/bin/python tasks.py build
  ↓
.venv/bin/python -m ground_station.livewatch verify   # only if ELF changed
  ↓
.venv/bin/python tasks.py flash
  ↓
.venv/bin/python -m ground_station.livewatch read <sym> [more...]
  ↓
diagnose → next edit
```

Re-run only the steps that depend on what changed:

| Change | Re-run |
|---|---|
| C source under `API/`, `BSP/`, `TASK/`, `USER/`, `Global_file/`, `stm32_lib/`, `FreeRTOS/` | build + flash + verify + read |
| `firmware/startup/*.s` or `firmware/cmake/stm32f407zg.ld` | build + flash + verify (vector table SP must still be `0x2001d560`) |
| `firmware/CMakeLists.txt` | build (config regen) + flash + verify |
| `ground_station/**` Python | no flash — just re-run the tool |

`livewatch verify` is cheap (~hundreds of ms); run it after every flash rather
than guessing whether the build landed.

### Flash fallback when `tasks.py flash` glitches

On the ATK-HS-V3 wireless bridge, `tasks.py flash` can hit an "IPSR=3" fault
mid-flash while the bridge uploads the flash algorithm to RAM. The escape
hatch is the direct pyocd CLI, which uses the same DFP-backed target:

```bash
.venv/bin/python -m pyocd flash --target stm32f407zgtx firmware/build/JX_FLY.hex
```

This is the working path on the bench today. Re-attempt `tasks.py flash` only
if pyocd upstream lands a fix for the bridge algo-upload path.

## Wireless-bridge caveat

If the CMSIS-DAP is on a wireless link (J-Link WiFi, AIRLink, etc.):

- Run `freshness` at the start of every session.
- Re-run after any long pause.
- Re-run after any value that looks too clean.
- A passing freshness test does NOT guarantee every subsequent read is fresh —
  wireless bridges can drop only specific packets.

The Linux pipeline uses pyocd identically to the Windows one at the SWD wire
layer; wireless vs wired is a probe-hardware choice, not a software one. The
freshness probe is the only thing that catches bridge caching.

## End-of-session report

Before stopping, tell the user:

- what was changed in source (paths + commit SHA)
- what was flashed to the target (commit SHA + ELF sha256-16)
- whether the drone is still disarmed (re-read ARM_Status)
- where the new image lives (`firmware/build/JX_FLY.{elf,hex,bin}`)
- any open findings that need follow-up

The user disconnects battery and removes the probe. You do not.

## Forbidden actions even when authorized

Hardware-safety rules in `.cursor/rules/hardware-safety.mdc` are stricter than
this skill. Where they conflict, the safety rule wins. In particular you do
NOT:

- arm the vehicle
- spin motors
- bypass the DISARMED check under any pressure
- write to RAM, peripherals, or registers via livewatch (read-only path only)
- run `openocd`, `st-flash`, `st-util`, `JLink*`, or
  `ground_station.flashtool` (the Windows Keil wrapper) directly — only
  `tasks.py flash` and `livewatch` are permitted on the standard path.
- The exception is the ATK-HS-V3 flash fallback above:
  `pyocd flash --target stm32f407zgtx firmware/build/JX_FLY.hex`. The
  same DFP, the same .hex, the same flash algorithm — only the entry
  point differs. Use it as a documented escape hatch when
  `tasks.py flash` faults on the bridge's algo upload.
- modify `OBJ/`, `*.hex`, or `*.axf` — those are build outputs

## What this skill is NOT

- It is not the offline software workflow. Wiki work, sim runs, and CI do not
  load this skill.
- It is not the Windows/Keil workflow. The bench on Windows uses
  `OBJ/JX_FLY.axf` from Keil; the bench on Linux uses `firmware/build/JX_FLY.elf`
  from CMake. Same `livewatch` reads either way.
- It is not a substitute for `tasks.py doctor`. Doctor is always step 1.