# Linux build pipeline — authoritative references

This file collects the primary-source documentation behind each non-obvious
decision in `firmware/` and `ground_station/flashtool_linux/`. When in doubt,
check the source rather than guessing.

---

## 1. Cortex-M4 vector table layout

**Source**: ARM, *Cortex-M4 Devices Generic User Guide*, section 2.3.4 "Vector
table". Confirmed via charleskorn.com (2016-04-17), "A deeper look at the
STM32F4 project template: getting things started".

Key facts:
- The first word at offset 0 of the vector table is loaded into MSP on reset.
  It is the **stack pointer value**, not a label.
- Subsequent words are addresses of exception handlers.
- Layout is the same for every Cortex-M4 part — vendor startup code only
  differs in the IRQ names after the standard 16 system handlers.

**Our application**: vector table's first entry is `.word __StackTop`, where
`__StackTop` is defined in the linker script as a concrete address. A weak
`Default_Handler` (infinite loop) backs every external IRQ so an unexpected
interrupt does not jump to address 0.

---

## 2. GNU ld linker script memory regions

**Source**: GNU `ld` manual, *SECTIONS* / *MEMORY* / *PROVIDE*. Canonical
pattern for `__StackTop` + `__HeapBase`/`__HeapLimit` is the
`_user_heap_stack` block, followed by `.` to advance into stack space. The
`newlib` `_sbrk()` walks `_end..__HeapLimit`; the vector table's first word
points at `__StackTop` (the high water mark).

**Our application**: `firmware/cmake/stm32f407zg.ld` puts `.isr_vector`,
`.text`, `.rodata`, `.ARM.exidx` in FLASH. `.data` uses `> SRAM AT > FLASH`
to keep VMA in RAM and LMA in flash for the `Reset_Handler` copy loop.
`.bss` and `._user_heap_stack` go in SRAM with `(NOLOAD)`. `__StackTop` /
`__HeapBase` / `__HeapLimit` / `_estack` all live in this single section,
so no symbol is defined twice.

---

## 3. pyocd session options

**Source**: pyocd `docs/options.md` (main branch, July 2026). The four
options we depend on:

| Option | Value | Why |
|---|---|---|
| `connect_mode` | `attach` | Connect without halting the running core. Other modes (`halt`, `pre-reset`, `under-reset`) all halt. |
| `resume_on_disconnect` | `False` | Don't resume cores on disconnect; leave target state untouched. |
| `reset_type` | `system` | NVIC AIRCR.SYSRESETREQ. Pyocd's default already chooses `system`, but we set it explicitly so a future pyocd default change cannot quietly switch to `core`. |
| `target_override` | `cortex_m` | Fallback target when no CMSIS Pack is found for `stm32f407zg`. |

`target.system_reset()` is the no-halt reset path; `target.reset()` halts the
core. We use the former everywhere.

For the read-only path (`ground_station.livewatch`), `attach` +
`resume_on_disconnect=False` is also correct and is what livewatch's reader
uses. The flashtool_linux package follows the same contract.

---

## 4. arm-none-eabi-gcc for Cortex-M4F

**Source**: ARM, *Arm GNU Toolchain* downloads page. Tested versions:

- 14.2.Rel1 — built with and verified.
- 14.3.Rel1 / 15.2.Rel1 — also expected to work; the toolchain file is
  pinned only to the Cortex-M4F ISA (`-mcpu=cortex-m4 -mthumb
  -mfloat-abi=hard -mfpu=fpv4-sp-d16`).

**Caveats** (compared to Keil ARMCC V5.06):
- `__asm void func()` → `__attribute__((naked)) void func()` with
  `__asm volatile(...)` blocks.
- `NULL` casts on `uint32_t` DMA fields (already corrected in
  `BSP/usart3.c`, `BSP/usart4.c`, `BSP/usart5.c`).
- `--specs=nano.specs` is a linker-level option, not a compile option.

---

## 5. FreeRTOS GCC ARM_CM4F port

**Source**: FreeRTOS V9.0.0+ `FreeRTOS/Source/portable/GCC/ARM_CM4F/`. The
canonical upstream version is used. It pairs with
`FreeRTOS/portable/MemMang/heap_4.c` (selected by the `foreach` filter in
`firmware/CMakeLists.txt`).

The Keil RVDS port (`portable/RVDS/ARM_CM4F/`) is excluded by name in
`CMakeLists.txt`.

---

## 6. CI / pipeline

**Source**: GitHub Marketplace, `carlosperate/arm-none-eabi-gcc-action`.
Recommended workflow for the Linux mirror repo:

```yaml
- uses: carlosperate/arm-none-eabi-gcc-action@v1
  with:
    release: '14.2.Rel1'
```

Caches the toolchain between runs. Self-hosted runner required for any
hardware-in-the-loop step (probe must be physically attached).

---

## Cited URLs

- https://charleskorn.com/2016/04/17/a-deeper-look-at-the-stm32f4-project-template-getting-things-started/
- https://github.com/pyocd/pyOCD/blob/main/docs/options.md
- https://github.com/marketplace/actions/arm-none-eabi-gcc-gnu-arm-embedded-toolchain
- https://developer.arm.com/downloads/-/arm-gnu-toolchain-downloads

(Stored as local references; no live-link guarantee.)