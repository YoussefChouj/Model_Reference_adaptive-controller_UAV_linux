# Model Reference Adaptive Controller UAV — Linux build

Linux-native build pipeline for the STM32F407ZG adaptive-controller firmware.

This repository is the Linux mirror of
[YoussefChouj/Model_Reference_adaptive-controller_UAV](https://github.com/YoussefChouj/Model_Reference_adaptive-controller_UAV).
The source tree (API/, BSP/, TASK/, USER/, Global_file/, stm32_lib/, FreeRTOS/)
is shared with the Windows repo; only the **build pipeline** differs:

| | Windows (primary repo) | Linux (this repo) |
|---|---|---|
| **Toolchain** | Keil uVision + ARMCC V5.06 | arm-none-eabi-gcc 14.2 |
| **Build system** | `.uvprojx` | CMake (`firmware/CMakeLists.txt`) |
| **Output** | `OBJ/JX_FLY.axf` | `firmware/build/JX_FLY.{elf,hex,bin}` |
| **Flash tool** | Keil flash utility | pyocd (`ground_station/flashtool_linux`) |
| **Verify** | Keil `verify` | `tasks.py verify` → livewatch |

## Build

```bash
# One-time setup
sudo scripts/setup_linux_toolchain.sh

# Build firmware
.venv/bin/python tasks.py build

# Flash (CMSIS-DAP probe attached)
.venv/bin/python tasks.py flash

# Verify
.venv/bin/python tasks.py verify
```

## Layout

```
firmware/                    ARM GCC build pipeline
├── CMakeLists.txt           firmware-only CMake config
├── cmake/
│   ├── arm-none-eabi-gcc.toolchain.cmake
│   └── stm32f407zg.ld       linker script (FLASH/SRAM/CCM)
└── startup/
    ├── startup_stm32f40_41xxx.s  vector table + Reset_Handler (GAS syntax)
    └── newlib_stubs.c

ground_station/flashtool_linux/    pyocd wrapper (build + flash + verify)
├── __init__.py             enumerate_probes() helper
├── linux_build.py         cmake configure + build
├── linux_flash.py         pyocd flash + system_reset + checksum
├── linux_preflight.py     toolchain + probe checks
└── tests/                 offline regression tests

scripts/setup_linux_toolchain.sh    one-time apt + udev setup
docs/linux-pipeline-references.md   primary-source docs behind each decision
.github/workflows/firmware-linux.yml  GitHub Actions CI

firmware/, API/, BSP/, TASK/, USER/, Global_file/, stm32_lib/, FreeRTOS/   shared source
```

## Safety contract

The flash tool follows the same safety contract as `ground_station.livewatch`:

- `connect_mode=attach` — connect without halting the core.
- `resume_on_disconnect=False` — leave target state untouched on disconnect.
- `reset_type=system` — NVIC AIRCR.SYSRESETREQ (no halt).
- No memory-write API exposed.
- Flash path goes through `target.mass_erase()` + `board.program()` only.

See `docs/linux-pipeline-references.md` for the primary-source documentation
behind every non-obvious decision in this pipeline.

## CI

`.github/workflows/firmware-linux.yml` runs on every push to `main`:

1. `arm-none-eabi-gcc 14.2.Rel1` (cached via carlosperate/arm-none-eabi-gcc-action)
2. CMake configure + build
3. Vector table SP-word regression test
4. `ground_station/flashtool_linux/tests/`
5. `sim/tests/` (offline lanes)

Hardware-in-the-loop (`tasks.py flash`, `tasks.py verify` on a real board)
requires a self-hosted runner with the CMSIS-DAP probe attached.

## Syncing with the Windows repo

The Windows repo remains the source of truth. To pull the latest source:

```bash
git remote add windows git@github.com:YoussefChouj/Model_Reference_adaptive-controller_UAV.git
git fetch windows
git merge windows/main  # or rebase, as preferred
```

If the Windows repo lands a GCC-incompatible change (e.g., a Keil-specific
directive), port the fix here and back-port to the Windows repo as needed.