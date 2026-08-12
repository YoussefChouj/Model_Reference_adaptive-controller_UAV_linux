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
  - linux_flash  — pyocd Session wrapper: flash(), reset(), verify()
  - linux_preflight — Linux preflight: probe enumerability, toolchain presence
  - linux_build   — CMake configure + build via subprocess
"""
