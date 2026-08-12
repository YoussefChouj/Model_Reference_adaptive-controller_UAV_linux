/* STM32F407ZG linker script
 *
 * Memory layout from Keil .uvprojx:
 *   FLASH : ORIGIN = 0x08000000, LENGTH = 1 MB
 *   SRAM  : ORIGIN = 0x20000000, LENGTH = 192 KB
 *   CCM   : ORIGIN = 0x10000000, LENGTH = 64 KB
 *
 * Keil scatter equivalent:
 *   IROM1 = 0x08000000 0x00100000  (1 MB flash)
 *   IRAM1 = 0x20000000 0x00030000  (192 KB SRAM)
 *   IRAM2 = 0x10000000 0x00010000  (64 KB CCM)
 */

ENTRY(Reset_Handler)

/* Stack and heap sizes from startup_stm32f40_41xxx.s */
_stack_size = 0x400;   /* 1 KB — matches Keil Stack_Size EQU */
_heap_size  = 0x200;    /* 512 B — matches Keil Heap_Size  EQU */

MEMORY
{
    FLASH (rx)  : ORIGIN = 0x08000000, LENGTH = 1M
    SRAM (rwx)  : ORIGIN = 0x20000000, LENGTH = 192K
    CCM  (rwx)  : ORIGIN = 0x10000000, LENGTH = 64K
}

SECTIONS
{
    /* Vector table must sit at 0x08000000 (flash start) */
    .isr_vector :
    {
        . = ALIGN(4);
        KEEP(*(.isr_vector))
        . = ALIGN(4);
    } > FLASH

    .text :
    {
        . = ALIGN(4);
        *(.text)
        *(.text*)
        *(.glue_7)         /* ARM/Thumb call glue */
        *(.glue_7t)
        *(.eh_frame)
        KEEP(*(.init))
        KEEP(*(.fini))
        . = ALIGN(4);
        _etext = .;
    } > FLASH

    .rodata :
    {
        . = ALIGN(4);
        *(.rodata)
        *(.rodata*)
        . = ALIGN(4);
    } > FLASH

    /* ARM exception handlers — must be in SRAM for hardware faults */
    .ARM.exidx :
    {
        *(.ARM.exidx*)
        *(.arm.exidx*)
    } > FLASH
    /* Cortex-M4 has no unwind tables; exidx is empty in practice.
     * Keil puts this in IRAM1 by convention; FLASH is correct and saves RAM. */

    .ccm :
    {
        . = ALIGN(4);
        *(.ccm)
        *(.ccm*)
        . = ALIGN(4);
    } > CCM

    /* Initialised data: VMA in SRAM, LMA in FLASH. Reset_Handler copies. */
    .data :
    {
        . = ALIGN(4);
        _sdata = .;
        *(.data)
        *(.data*)
        . = ALIGN(4);
        _edata = .;
    } > SRAM AT > FLASH
    _sdata_load = LOADADDR(.data);

    .bss :
    {
        . = ALIGN(4);
        _sbss = .;
        __bss_start__ = _sbss;
        *(.bss)
        *(.bss*)
        *(COMMON)
        . = ALIGN(4);
        _ebss = .;
        __bss_end__ = _ebss;
    } > SRAM

    /* Heap + stack reservation. Stack grows down from __StackTop.
     * Reset_Handler reads __StackTop into MSP via the vector table.
     * newlib _sbrk() walks _end..__HeapLimit. */
    ._user_heap_stack (NOLOAD) :
    {
        . = ALIGN(8);
        _end = .;
        __end = .;
        end = .;
        __HeapBase = .;
        _heap_start = .;
        . = . + _heap_size;
        . = ALIGN(8);
        __HeapLimit = .;
        _heap_end = .;
        . = . + _stack_size;
        . = ALIGN(8);
        __StackTop = .;
        __StackLimit = __StackTop - _stack_size;
        _estack = __StackTop;
    } > SRAM

    /DISCARD/ :
    {
        libc.a (*)
        libm.a (*)
        libgcc.a (*)
    }
}
