---
title: Flash Memory
type: entity
tags: [flash, persistence, bsp, storage]
created: 2026-04-14
updated: 2026-04-14
sources: [stm32_lib/stm32f4xx_flash.c, USER/main.c, TASK/send_data.c]
related_files: [stm32_lib/stm32f4xx_flash.c, USER/main.c, TASK/send_data.c]
---

Current project-level logic does **not** implement an application persistence pipeline for PID/MRAC/config data in internal flash. The STM32 standard peripheral flash driver exists in the repository (`stm32_lib/stm32f4xx_flash.c`), but no active firmware module calls erase/program APIs for control parameters.

## Evidence in Codebase

Search in project sources shows flash routines only in vendor library:
- `FLASH_Unlock`, `FLASH_EraseSector`, `FLASH_ProgramWord`, `FLASH_Lock` appear in `stm32_lib/stm32f4xx_flash.c` (for example declarations around `stm32_lib/stm32f4xx_flash.c:414,469,537`)
- No matching calls from `TASK/`, `USER/`, or `BSP/` control modules in current firmware path

Runtime task pipeline (`USER/main.c`) creates IMU/control/autofly/comm tasks but no persistence task (`USER/main.c:31-89`).

Ground-station command handler (`TASK/send_data.c:471`) updates gains and MRAC arrays in RAM directly, with no save-to-flash command branch (`0x01..0x0E` only).

## What Is Persisted Today

At present, effective persistence is configuration-at-compile-time and runtime RAM-only updates:
- PID and MRAC config updates are volatile (lost on reboot)
- Path parameters and safety limits are volatile globals
- No boot-time “load from NVM” function is invoked in `main()`/`BSP_Init()`

## Missing Write/Verify Pipeline

A full persistence implementation would normally include:
1. `FLASH_Unlock`
2. sector erase (`FLASH_EraseSector` / bank erase)
3. program words/halfwords
4. verify/readback
5. `FLASH_Lock`

Those primitives exist in vendor code, but project code does not call them in control paths. Therefore there is no wear-level policy, write throttling, sector rotation, or CRC-protected parameter block in current logic.

## Boot Read-Back Status

No read-back initialization from flash into control globals is present in startup sequence:
- `main()` only does `BSP_Init()` then starts scheduler (`USER/main.c:14-27`)
- `BSP_Init()` initializes peripherals and comm interfaces (`BSP/BSP.c:4-30`)

No parameter import step appears before control loops start.

## Practical Implication

All tuning performed via [[Ground-Station Binary Protocol]] (CMD `0x01`, `0x02`, `0x05`, `0x08`, `0x09`, etc.) is session-scoped. Power cycling the MCU restores compile-time defaults.

## See Also

- [[Multi-rate Task Partitioning]]
- [[Ground-Station Binary Protocol]]
