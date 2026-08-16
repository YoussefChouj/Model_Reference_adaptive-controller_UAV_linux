# ADR-0015 — Linux bridge-flash pipeline: chip-specific target + kernel hid claim

* **Status:** Accepted
* **Date:** 2026-08-16
* **Effective from:** commits `7c18346`, `1bd4d21`

## Context

The repository's Linux build pipeline flashes the STM32F407ZG FC over a
CMSIS-DAP probe — currently a wireless ATK-HS-V3 (Microchip 04d8:00df, USB-HID
+ CDC-ACM composite). Until 2026-08-16 the pipeline worked intermittently:
`pyocd flash` would exit 0 with "Erased 0 bytes (0 sectors), programmed 92336
bytes (0 pages)" but the FC kept running its prior firmware. Reads via
`livewatch` returned cached values, and `target_power` saw UART5 telemetry at
the right rate — yet on-chip flash was unreachable from the host.

Two independent bugs were silently breaking the path. Diagnosed by a sweep
that started from the research finding that pyocd issued "programmed 92336
bytes" without any flash sectors being erased:

1. **pyocd's `cortex_m` fallback target has no flash algorithm.** The fallback
   loader returns success without ever issuing the flash-algorithm routines
   over SWD. It exists to *acknowledge* the flash command, not to *execute*
   it. The STM32F4xx_DFP pack ships a real algorithm that pyocd wires in
   once it knows the chip name.

2. **`hid_mcp2200` claimed the bridge's HID interface.** The ATK-HS-V3's HID
   class descriptor matches `hid_mcp2200` by MISFITS-of-VID/PID heuristic,
   and Linux binds it there before pyocd's libusb path opens the device.
   Without the correct driver claim, the CMSIS-DAP HID-protocol commands
   are routed to a driver that doesn't speak CMSIS-DAP.

The diagnose-and-repair session is logged in
[`sessions_summary/2026-08-16-wireless-bridge-flash-dual-bug.md`](../../sessions_summary/2026-08-16-wireless-bridge-flash-dual-bug.md).

## Decision

The Linux flash pipeline pins all three of the following. Each fix on its
own is insufficient; both must be in place.

| Layer | Setting | Where |
|---|---|---|
| Python | `target_override=stm32f407zgtx` (chip-specific) | `ground_station/flashtool_linux/linux_flash.py` `_PROBE_CONFIG`; `pyocd.yaml` documents the choice. |
| Python | `cmsis_dap.deferred_transfers=0`, `cmsis_dap.limit_packets=1` | `pyocd.yaml` + `ground_station/flashtool_linux/linux_flash.py` + `ground_station/livewatch/transport.py`. Direct fix for pyocd issue #1257. |
| Kernel | `install hid_mcp2200 /bin/false`, then `modprobe -r hid_mcp2200` once per box | `/etc/modprobe.d/blacklist-hid-mcp2200.conf` (system) + `etc-modprobe-d/blacklist-hid-mcp2200.conf` (repo copy). |
| Host toolchain | `pyocd pack install stm32f407` (DFP) | Documented in `docs/lab-runbook.md` "Pipeline readiness". |

After all three are in place, flash is reliable:
`pyocd flash --target stm32f407zgtx firmware/build/JX_FLY.hex` reports
"Erased 131072 bytes (5 sectors), programmed 93184 bytes (91 pages)",
verified by reading `0x08000000` and confirming the vector table's first
word matches the new firmware's SP.

## Consequences

* **One-time per box** setup is now mandatory before the first lab session.
  The skill `lab-session` and the runbook `docs/lab-runbook.md` document
  the three lines.
* **`livewatch` keep using `target_override=cortex_m`.** The reader never
  issues flash commands; the fallback target suffices for DAP SWD reads
  and avoids the DFP-install dependency on the read-only side. The
  packet-reorder flags from `pyocd.yaml` are still required for fresh
  reads on a wireless bridge.
* **`tasks.py flash` has an intermittent IPSR=3 fault** on the ATK-HS-V3
  when the bridge uploads the flash algorithm to RAM. The documented
  escape hatch is the direct pyocd CLI on the same DFP-backed target.
  Both share the same `.hex`, same algorithm, same out-file — only the
  entry point differs.
* **Scope discipline unchanged.** `livewatch` is still strictly read-only
  (RAM reads cannot move the ARM flag). `tasks.py flash` still gates on
  `livewatch read DroneStatus.ARM_Status == DISARMED`.

## Open

* Re-introduce `tasks.py flash` reliability on the ATK-HS-V3 — root cause
  is pyocd-side and is tracked upstream.
* If a wired CMSIS-DAP becomes available, the wireless-bridge path is a
  fallback, not the primary. The runbook and the skill should make that
  explicit once both paths exist in the lab.
