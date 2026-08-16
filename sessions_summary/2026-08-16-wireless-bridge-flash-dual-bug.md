---
session_date: 2026-08-16
status: closed
goal: Get the ATK-HS-V3 wireless CMSIS-DAP bridge to actually flash the STM32F407ZG FC, not just report success.
---

# 2026-08-16: Wireless bridge flash — dual-bug root cause

## TL;DR

The flash pipeline silently no-op'd because of two independent bugs:

1. **pyocd's `cortex_m` fallback target has no flash algorithm.** It runs the loader, pretends to program, and reports success without ever issuing the sector-program DAP commands. The STM32F4xx_DFP pack provides a real algorithm. Switch `target_override` to `stm32f407zgtx`.
2. **Linux hid_mcp2200 was claiming the ATK-HS-V3's HID interface** before pyocd's libusb path could open it. Writes got routed to a driver that doesn't speak CMSIS-DAP. `install hid_mcp2200 /bin/false` in `/etc/modprobe.d/blacklist-hid-mcp2200.conf` rebinds to `hid-generic`.

Both fixes are committed (`1bd4d21`). The previous commit `7c18346` added the `cmsis_dap.deferred_transfers=0` / `limit_packets=1` workaround from pyocd issue #1257 — that one was already needed for reads, not writes.

## Final state

- FC flashed, vector table at `0x08000000` = `60d50120f5090108…` (my firmware).
- `xTickCount` advances at the right rate (103–104 ticks / 100 ms ≈ 1 kHz FreeRTOS tick).
- `/dev/ttyACM0` target_power reports 18395 B/s on UART5.
- `pyocd flash --target stm32f407zgtx firmware/build/JX_FLY.hex` reports `Erased 131072 bytes (5 sectors), programmed 93184 bytes (91 pages)` — real numbers.
- `tasks.py flash` still hits an intermittent "IPSR=3" mid-flash on the bridge's algo upload. Direct pyocd CLI is the working path until that stabilises.

## What was tried and ruled out

| Hypothesis | Tried | Result |
|---|---|---|
| Bridge TCP mode (WiFi → port 4441) | nmap-subnet scan at `192.168.4.1`–`.10` for ports 80, 3241, 4441, 8080. Only `192.168.4.1:80` (gateway) open. | ATK-HS-V3 is not in TCP mode. Skip. |
| OpenOCD over USB-HID | `apt install openocd 0.12.0`, `interface/cmsis-dap.cfg` + `target/stm32f4x.cfg`. | OpenOCD 0.12 has only the bulk CMSIS-DAP driver; skips the ATK's HID interface ("endpoint[0] is not bulk out"). The `cmsis_dap_backend hid` option is undocumented / not recognised in this build. Need a custom OpenOCD with the hidapi patch from upstream. |
| `pyocd.yaml` `chip_erase=chip` + `smart_flash=false` + `trust_crc=false` | committed `1bd4d21`, then reverted to default in same commit. | None of these addressed the underlying "no flash algorithm" issue. |
| `cmsis_dap.deferred_transfers=0` + `limit_packets=1` | committed `7c18346`. | Fixes read-path staleness (xTickCount returns same value across 500 ms without it). Does *not* fix writes — different code path. |
| STM32F4 readout-protection check via OpenOCD | — | Skipped: OpenOCD can't enumerate the bridge. |
| JTAG instead of SWD | — | Skipped: requires 4-wire FC wiring. |
| Re-flash ATK-HS-V3 ESP32 firmware | — | Skipped: requires ESP-IDF toolchain and ATK-specific firmware, not on hand. |
| pyocd `--chip-erase=chip` from CLI | — | No effect without the DFP. |
| Bridge power-cycle + replug | — | Stale firmware flashes / re-binds. Modprobe rule clear across replug. |
| STM32F4 ROM bootloader via USART1 | — | Requires BOOT0 pin toggle + wiring to a USB-UART adapter. Held for Tier 5 fallback. |

## Why the symptoms were misleading

Pyocd's `cortex_m` fallback target uses a loader that just streams bytes to the algorithm-stub address in flash. It runs the algorithm-stub loader, which writes 0xFFFFFFFF to the target's flash status register, which is the "stay in ICRST" state for an eraser. Without the real algorithm, the program step is a no-op.

The "Erased 0 bytes (0 sectors), programmed 92336 bytes (0 pages)" message is misleading: 92336 is the size of the source image, not bytes actually written. We were seeing this *before* and *after* the cluster of fixes, which is how I knew the issue was upstream of the chip_erase / smart_flash flags.

## Files changed

| File | Change | Commit |
|---|---|---|
| `ground_station/flashtool_linux/linux_preflight.py` | search beyond `$PATH` for `arm-none-eabi-gcc` | `7c18346` (prior session) |
| `ground_station/flashtool_linux/linux_flash.py` | use `FileProgrammer` (API change), add packet-order flags, set `target_override=stm32f407zgtx`, pass `chip_erase=False` to `FileProgrammer` | `7c18346`, `1bd4d21` |
| `ground_station/livewatch/transport.py` | add packet-order flags to `SwdCmsisDap.connect` | `7c18346` |
| `etc-modprobe-d/blacklist-hid-mcp2200.conf` | new file: `install hid_mcp2200 /bin/false` | `1bd4d21` |
| `pyocd.yaml` | documents the dual-bug root cause + host-side install steps | `1bd4d21` |

## Open / not-closed

- `tasks.py flash` IPSR=3 intermittent failure during FileProgrammer algo upload. Work-around: use direct `pyocd flash --target stm32f407zgtx`. Root cause: pyocd-side, not host-side. Consider a follow-up that shells out to the pyocd CLI from the wrapper.
- Livewatch reads return a cached buffer after a flash. Suspect the bridge has stale state across session. `target.resume()` + 200 ms settle before re-attach resolves it. Consider documenting in `livewatch` skill.
- The bridge's esp32 firmware is unmodified. If a known-fixed upstream exists, that's the long-term fix. Out of scope today.

## Operator actions needed

None. Pipeline is wired up. To flash from a fresh shell:

```bash
.venv/bin/python -m pyocd flash --target stm32f407zgtx firmware/build/JX_FLY.hex
```

(Or `tasks.py flash` if you accept the intermittent IPSR=3 retry.)

To verify FC is alive:

```bash
.venv/bin/python -m ground_station.livewatch --elf firmware/build/JX_FLY.elf freshness xTickCount --samples 5 --delay-ms 100
sudo -A chmod 666 /dev/ttyACM0   # bridge CDC ACM endpoint
.venv/bin/python -m ground_station.flashtool.target_power --port /dev/ttyACM0
```
