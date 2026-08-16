# Lab session runbook — drone powered, probe attached

**This document is the operator/agent contract for live-bench work.** When you
(the operator) and an AI agent sit together at the bench with the drone powered
on and the CMSIS-DAP probe physically attached to your Linux box, this file
governs what the agent may do.

The agent is told: **read this file before touching hardware.**

---

## Pipeline readiness (one-time per Linux box)

Before you can flash from this machine, three kernel/Python prerequisites
must be present. **Skip this section on Windows; the Keil pipeline already
handles these.**

```bash
# 1. STM32F4xx_DFP pack — pyocd's cortex_m fallback target silently no-ops
#    on flash (writes succeed without committing bytes). The chip-specific
#    algorithm from this DFP is required for writes to actually land.
.venv/bin/python -m pyocd pack update
.venv/bin/python -m pyocd pack install stm32f407

# 2. Kernel: ATK-HS-V3's HID interface must not be claimed by hid_mcp2200.
#    Without this, the bridge enumerates but writes silently drop. The
#    install /bin/false rule is in etc-modprobe-d/blacklist-hid-mcp2200.conf.
sudo cp etc-modprobe-d/blacklist-hid-mcp2200.conf /etc/modprobe.d/
sudo modprobe -r hid_mcp2200
# Replug the bridge once so the new binding takes effect.
```

Verify each is in place:

```bash
.venv/bin/python -m pyocd list --targets | grep stm32f407    # DFP installed
cat /sys/bus/hid/devices/0003:04D8:00DF.*/uevent | head -1   # DRIVER=hid-generic
.venv/bin/python -m pyocd list                                # probe enumerated
```

Root cause + diagnostic trace: `sessions_summary/2026-08-16-wireless-bridge-flash-dual-bug.md`.

## Pre-flight (operator)

Before invoking the agent:

1. **Drone on the bench, props OFF, battery connected.**
2. **CMSIS-DAP probe plugged into a USB port on the Linux box.**
   Wireless bridges (ATK-HS-V3) need `livewatch freshness` runs before each
   write — see step 4. Wired CMSIS-DAP skips step 4 unless the operator has
   already seen stale reads.
3. **`tasks.py doctor` is green.** Toolchain present, probe enumerated.
4. **Drone ARM_STATUS = DISARMED.** Confirmed via livewatch before any write.
   Wireless-bridge staleness is caught by the freshness probe.

## Authorization gate (operator → agent)

Tell the agent explicitly:

> "You are authorized to modify code, rebuild, flash, and live-probe the
> running firmware. The drone is disarmed, props are off, and the bench is
> safe. Proceed."

Without that sentence, the agent **does not flash, mass-erase, or live-reset**.
Read-only `livewatch read` is allowed once `tasks.py doctor` is green.

Once authorized, the agent decides what to do based on the task at hand:

- Bug hunt: code → build → flash → live read → diagnose → fix → repeat.
- Acceptance test: live read → compare against the expected manifest.
- Calibration sweep: live log → compute → emit a config patch.

## Required verification steps before any flash

The agent MUST run these in order. Any failure → abort and report.

```bash
# 1. Probe + toolchain
.venv/bin/python tasks.py doctor

# 2. ELF on disk matches the build actually flashed (catches stale ELF)
#    On Linux, the image is firmware/build/JX_FLY.elf from CMake — pass it
#    with --elf. Windows uses OBJ/JX_FLY.axf from Keil (default).
.venv/bin/python -m ground_station.livewatch --elf firmware/build/JX_FLY.elf verify

# 3. Bridge is fresh, not stale (USB-wired: usually passes immediately;
#    wireless: re-run with --samples 5 --delay-ms 20 --require-monotonic)
.venv/bin/python -m ground_station.livewatch --elf firmware/build/JX_FLY.elf \
    freshness s_ekf.x[3] --samples 5 --delay-ms 20 --require-monotonic

# 4. Drone is DISARMED
.venv/bin/python -m ground_station.livewatch --elf firmware/build/JX_FLY.elf \
    read DroneStatus.ARM_Status
# Expected: ARM_Status = DISARMED (0). Any other value → ABORT.
```

If step 4 shows ARM_Status ≠ DISARMED, the agent does NOT flash. It tells the
operator "drone is armed; disarm via RC and re-run". The flash step is gated
on a DISARMED check; that gate is what the operator/agent contract means.

## Allowed actions once authorized

| Action | When |
|---|---|
| `tasks.py build` | Anytime (no hardware needed) |
| `livewatch read`, `watch`, `log` | After `freshness` passes |
| `livewatch verify` | After `freshness` passes |
| `tasks.py flash` (mass-erase + program) | After ARM_Status = DISARMED |
| `livewatch freshness` | Anytime — read-only |
| Telemetry/serial reads over UART5 | After freshness probe on UART5 |

The agent may freely decide how often to rebuild and re-flash as part of an
iterative debug loop. The agent may NOT:

- arm the vehicle
- spin motors
- bypass the DISARMED check
- write to RAM, peripherals, or registers via livewatch

## Wireless bridge mode (operator decision)

If the CMSIS-DAP is on a wireless link (J-Link WiFi, AIRLink, ATK-HS-V3),
the freshness probe is a hard requirement. Run it at the start of every
session and after any long pause.

A passing freshness test does not guarantee every subsequent read is fresh.
If you see values that look too clean / too perfect, run `freshness` again.
If it fails, pause and re-check the radio link.

### ATK-HS-V3 flash path (known-good)

On the ATK-HS-V3 (Microchip 04d8:00df), `tasks.py flash` can hit an
intermittent "IPSR=3" fault mid-flash while the bridge uploads the flash
algorithm to RAM. The agent's escape hatch is the direct pyocd CLI:

```bash
.venv/bin/python -m pyocd flash --target stm32f407zgtx firmware/build/JX_FLY.hex
```

This works reliably with the prerequisites above (DFP installed, mcp2200
blacklisted, target_override=stm32f407zgtx). Resume `tasks.py flash`
once pyocd upstream lands a fix for the bridge algo-upload path.

## End-of-session cleanup

The agent tells the operator:

- what was changed in source
- what was flashed to the target
- whether the drone is still disarmed (re-check ARM_Status)
- where the new firmware image lives (`firmware/build/JX_FLY.{elf,hex,bin}`)

The operator confirms battery disconnect and probe removal before walking away.

---

## What this file does NOT cover

- **Wiki ingestion / knowledge work** — does not require probe or drone.
- **Simulation runs (`sim/`)** — does not require probe or drone.
- **CI runs on GitHub Actions** — already gated; nothing to do here.

When the session is purely software, this runbook is irrelevant and the
agent follows the regular software-development rules.