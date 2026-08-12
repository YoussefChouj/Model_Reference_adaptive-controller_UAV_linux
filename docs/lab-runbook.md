# Lab session runbook — drone powered, probe attached

**This document is the operator/agent contract for live-bench work.** When you
(the operator) and an AI agent sit together at the bench with the drone powered
on and the CMSIS-DAP probe physically attached to your Linux box, this file
governs what the agent may do.

The agent is told: **read this file before touching hardware.**

---

## Pre-flight (operator)

Before invoking the agent:

1. **Drone on the bench, props OFF, battery connected.**
2. **CMSIS-DAP probe plugged into a USB port on the Linux box.**
   Wireless bridges are NOT supported without first running `livewatch freshness`
   — see step 4.
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
.venv/bin/python -m ground_station.livewatch verify

# 3. Bridge is fresh, not stale (USB-wired: usually passes immediately;
#    wireless: re-run with --samples 5 --delay-ms 20 --require-monotonic)
.venv/bin/python -m ground_station.livewatch freshness s_ekf.x[3] \
    --samples 5 --delay-ms 20 --require-monotonic

# 4. Drone is DISARMED
.venv/bin/python -m ground_station.livewatch read DroneStatus.ARM_Status
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

If the CMSIS-DAP is on a wireless link (J-Link WiFi, AIRLink, etc.), the
freshness probe is a hard requirement. Run it at the start of every session
and after any long pause.

A passing freshness test does not guarantee every subsequent read is fresh.
If you see values that look too clean / too perfect, run `freshness` again.
If it fails, pause and re-check the radio link.

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