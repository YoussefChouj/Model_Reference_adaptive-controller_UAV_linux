"""flashtool_linux — Linux-native build + flash for STM32F407ZG via arm-none-eabi-gcc + pyocd.

Agent loop on Linux (no Windows, no Keil):

    cmake -B firmware/build -S firmware
    cmake --build firmware/build
    python -m ground_station.flashtool_linux flash firmware/build/JX_FLY.hex
    python -m ground_station.livewatch verify

Safety model (mirrors ground_station/livewatch):
  - Read-only probe path: livewatch.reader (SwdCmsisDap, attach mode, no reset)
  - Write path: this package (flash/reset only, no memory-write API)

Components:
  - linux_flash  — pyocd Session wrapper: flash(), reset(), checksum_elf()
  - linux_preflight — Linux preflight: probe enumerability, toolchain presence
  - linux_build   — CMake configure + build via subprocess
"""
from __future__ import annotations


def enumerate_probes() -> list[dict]:
    """Return a list of {uid, description, board_name} for every CMSIS-DAP probe.

    Never opens a session. Returns [] if pyocd is not installed or no probe is
    plugged in. The single source of truth for probe enumeration; both
    linux_flash.probe_info() and linux_preflight.cmsis_dap_present() call this.
    """
    try:
        from pyocd.probe.cmsis_dap_probe import CMSISDAPProbe
    except Exception:
        return []
    out: list[dict] = []
    try:
        for p in CMSISDAPProbe.get_all_connected_probes():
            out.append({
                "uid": getattr(p, "unique_id", "") or "",
                "description": getattr(p, "description", "") or "",
                "board_name": getattr(p, "board_name", "") or "",
            })
    except Exception:
        pass
    return out
