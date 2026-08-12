/* STM32F407ZG startup — GNU ARM GCC (GAS syntax)
 *
 * Converted from: stm32_lib/startup_stm32f40_41xxx.s (Keil ARMASM, STMicroelectronics V1.4.0)
 * Mechanical translation:
 *   EQU       -> .equ
 *   AREA      -> .section
 *   DCD       -> .word
 *   PROC/ENDP -> removed (plain labels)
 *   EXPORT    -> .global
 *   IMPORT    -> .global (symbol defined in sys.c / system_stm32f4xx.c)
 *   B .       -> wfi + b .  (arm-none-eabi-as requires backward ref to be local)
 *   ALIGN     -> .balign 4
 *   SPACE     -> .space
 *
 * Stack:  1 KB  (matches startup_stm32f40_41xxx.s Stack_Size EQU 0x00000400)
 * Heap:   512 B (matches startup_stm32f40_41xxx.s Heap_Size  EQU 0x00000200)
 */

.syntax unified
.cpu cortex-m4
.fpu fpv4-sp-d16
.thumb

/* Stack and heap sizes — declared in linker script (firmware/cmake/stm32f407zg.ld).
 * The linker script owns __StackTop / __HeapBase / __HeapLimit and reserves
 * _stack_size / _heap_size bytes inside ._user_heap_stack. The vector table's
 * first entry points at __StackTop directly (the value the MCU loads into SP). */

/* ------------------------------------------------------------------
   Vector table
   ------------------------------------------------------------------ */
.section .isr_vector,"a",%progbits
.global __Vectors
.global __Vectors_End
.global __Vectors_Size

.type __Vectors, %object
.type __Vectors_End, %object
.size __Vectors, .-__Vectors

__Vectors:
    .word __StackTop                /* Top of Stack (value, not label)  */
    .word Reset_Handler             /* Reset Handler                   */
    .word NMI_Handler               /* NMI Handler                 */
    .word HardFault_Handler         /* Hard Fault Handler         */
    .word MemManage_Handler         /* MPU Fault Handler          */
    .word BusFault_Handler          /* Bus Fault Handler           */
    .word UsageFault_Handler        /* Usage Fault Handler        */
    .word 0                        /* Reserved                    */
    .word 0                        /* Reserved                    */
    .word 0                        /* Reserved                    */
    .word 0                        /* Reserved                    */
    .word SVC_Handler              /* SVCall Handler              */
    .word DebugMon_Handler          /* Debug Monitor Handler      */
    .word 0                        /* Reserved                    */
    .word PendSV_Handler           /* PendSV Handler             */
    .word SysTick_Handler          /* SysTick Handler            */

    /* External Interrupts */
    .word WWDG_IRQHandler
    .word PVD_IRQHandler
    .word TAMP_STAMP_IRQHandler
    .word RTC_WKUP_IRQHandler
    .word FLASH_IRQHandler
    .word RCC_IRQHandler
    .word EXTI0_IRQHandler
    .word EXTI1_IRQHandler
    .word EXTI2_IRQHandler
    .word EXTI3_IRQHandler
    .word EXTI4_IRQHandler
    .word DMA1_Stream0_IRQHandler
    .word DMA1_Stream1_IRQHandler
    .word DMA1_Stream2_IRQHandler
    .word DMA1_Stream3_IRQHandler
    .word DMA1_Stream4_IRQHandler
    .word DMA1_Stream5_IRQHandler
    .word DMA1_Stream6_IRQHandler
    .word ADC_IRQHandler
    .word CAN1_TX_IRQHandler
    .word CAN1_RX0_IRQHandler
    .word CAN1_RX1_IRQHandler
    .word CAN1_SCE_IRQHandler
    .word EXTI9_5_IRQHandler
    .word TIM1_BRK_TIM9_IRQHandler
    .word TIM1_UP_TIM10_IRQHandler
    .word TIM1_TRG_COM_TIM11_IRQHandler
    .word TIM1_CC_IRQHandler
    .word TIM2_IRQHandler
    .word TIM3_IRQHandler
    .word TIM4_IRQHandler
    .word I2C1_EV_IRQHandler
    .word I2C1_ER_IRQHandler
    .word I2C2_EV_IRQHandler
    .word I2C2_ER_IRQHandler
    .word SPI1_IRQHandler
    .word SPI2_IRQHandler
    .word USART1_IRQHandler
    .word USART2_IRQHandler
    .word USART3_IRQHandler
    .word EXTI15_10_IRQHandler
    .word RTC_Alarm_IRQHandler
    .word OTG_FS_WKUP_IRQHandler
    .word TIM8_BRK_TIM12_IRQHandler
    .word TIM8_UP_TIM13_IRQHandler
    .word TIM8_TRG_COM_TIM14_IRQHandler
    .word TIM8_CC_IRQHandler
    .word DMA1_Stream7_IRQHandler
    .word FSMC_IRQHandler
    .word SDIO_IRQHandler
    .word TIM5_IRQHandler
    .word SPI3_IRQHandler
    .word UART4_IRQHandler
    .word UART5_IRQHandler
    .word TIM6_DAC_IRQHandler
    .word TIM7_IRQHandler
    .word DMA2_Stream0_IRQHandler
    .word DMA2_Stream1_IRQHandler
    .word DMA2_Stream2_IRQHandler
    .word DMA2_Stream3_IRQHandler
    .word DMA2_Stream4_IRQHandler
    .word ETH_IRQHandler
    .word ETH_WKUP_IRQHandler
    .word CAN2_TX_IRQHandler
    .word CAN2_RX0_IRQHandler
    .word CAN2_RX1_IRQHandler
    .word CAN2_SCE_IRQHandler
    .word OTG_FS_IRQHandler
    .word DMA2_Stream5_IRQHandler
    .word DMA2_Stream6_IRQHandler
    .word DMA2_Stream7_IRQHandler
    .word USART6_IRQHandler
    .word I2C3_EV_IRQHandler
    .word I2C3_ER_IRQHandler
    .word OTG_HS_EP1_OUT_IRQHandler
    .word OTG_HS_EP1_IN_IRQHandler
    .word OTG_HS_WKUP_IRQHandler
    .word OTG_HS_IRQHandler
    .word DCMI_IRQHandler
    .word CRYP_IRQHandler
    .word HASH_RNG_IRQHandler
    .word FPU_IRQHandler

__Vectors_End:

.equ __Vectors_Size, __Vectors_End - __Vectors
.size __Vectors, .-__Vectors

/* ------------------------------------------------------------------
   Reset handler
   ------------------------------------------------------------------ */
.section .text.Reset_Handler
.weak Reset_Handler
.type Reset_Handler, %function

Reset_Handler:
    /* Copy .data from flash to SRAM */
    ldr r0, =_sdata
    ldr r1, =_edata
    ldr r2, =_sdata_load
    movs r3, #0
    cmp r0, r1
    beq .L_copy_data_done
.L_copy_data_loop:
    ldr r3, [r2], #4
    str r3, [r0], #4
    cmp r0, r1
    blt .L_copy_data_loop
.L_copy_data_done:

    /* Zero .bss */
    ldr r2, =__bss_start__
    ldr r3, =__bss_end__
    movs r4, #0
    cmp r2, r3
    beq .L_zero_bss_done
.L_zero_bss_loop:
    str r4, [r2], #4
    cmp r2, r3
    blt .L_zero_bss_loop
.L_zero_bss_done:

    /* FPU context init — enable FPU access in CPACR */
    ldr r0, =0xE000ED88
    ldr r1, [r0]
    orr r1, r1, #(0xF << 20)
    str r1, [r0]
    dsb
    isb

    /* Call SystemInit then __libc_init_array (provides __main equivalent) */
    bl SystemInit
    bl __libc_init_array
    bl main
    b .

.size Reset_Handler, .-Reset_Handler

/* ------------------------------------------------------------------
   Weak exception handlers — infinite loop (default)
   ------------------------------------------------------------------ */
.macro weak_handler name
.weak \name
.type \name, %function
\name:
    b .
.size \name, .-\name
.endm

weak_handler NMI_Handler
weak_handler HardFault_Handler
weak_handler MemManage_Handler
weak_handler BusFault_Handler
weak_handler UsageFault_Handler
weak_handler SVC_Handler
weak_handler DebugMon_Handler
weak_handler PendSV_Handler
weak_handler SysTick_Handler

/* External interrupt weak aliases */
weak_handler WWDG_IRQHandler
weak_handler PVD_IRQHandler
weak_handler TAMP_STAMP_IRQHandler
weak_handler RTC_WKUP_IRQHandler
weak_handler FLASH_IRQHandler
weak_handler RCC_IRQHandler
weak_handler EXTI0_IRQHandler
weak_handler EXTI1_IRQHandler
weak_handler EXTI2_IRQHandler
weak_handler EXTI3_IRQHandler
weak_handler EXTI4_IRQHandler
weak_handler DMA1_Stream0_IRQHandler
weak_handler DMA1_Stream1_IRQHandler
weak_handler DMA1_Stream2_IRQHandler
weak_handler DMA1_Stream3_IRQHandler
weak_handler DMA1_Stream4_IRQHandler
weak_handler DMA1_Stream5_IRQHandler
weak_handler DMA1_Stream6_IRQHandler
weak_handler ADC_IRQHandler
weak_handler CAN1_TX_IRQHandler
weak_handler CAN1_RX0_IRQHandler
weak_handler CAN1_RX1_IRQHandler
weak_handler CAN1_SCE_IRQHandler
weak_handler EXTI9_5_IRQHandler
weak_handler TIM1_BRK_TIM9_IRQHandler
weak_handler TIM1_UP_TIM10_IRQHandler
weak_handler TIM1_TRG_COM_TIM11_IRQHandler
weak_handler TIM1_CC_IRQHandler
weak_handler TIM2_IRQHandler
weak_handler TIM3_IRQHandler
weak_handler TIM4_IRQHandler
weak_handler I2C1_EV_IRQHandler
weak_handler I2C1_ER_IRQHandler
weak_handler I2C2_EV_IRQHandler
weak_handler I2C2_ER_IRQHandler
weak_handler SPI1_IRQHandler
weak_handler SPI2_IRQHandler
weak_handler USART1_IRQHandler
weak_handler USART2_IRQHandler
weak_handler USART3_IRQHandler
weak_handler EXTI15_10_IRQHandler
weak_handler RTC_Alarm_IRQHandler
weak_handler OTG_FS_WKUP_IRQHandler
weak_handler TIM8_BRK_TIM12_IRQHandler
weak_handler TIM8_UP_TIM13_IRQHandler
weak_handler TIM8_TRG_COM_TIM14_IRQHandler
weak_handler TIM8_CC_IRQHandler
weak_handler DMA1_Stream7_IRQHandler
weak_handler FSMC_IRQHandler
weak_handler SDIO_IRQHandler
weak_handler TIM5_IRQHandler
weak_handler SPI3_IRQHandler
weak_handler UART4_IRQHandler
weak_handler UART5_IRQHandler
weak_handler TIM6_DAC_IRQHandler
weak_handler TIM7_IRQHandler
weak_handler DMA2_Stream0_IRQHandler
weak_handler DMA2_Stream1_IRQHandler
weak_handler DMA2_Stream2_IRQHandler
weak_handler DMA2_Stream3_IRQHandler
weak_handler DMA2_Stream4_IRQHandler
weak_handler ETH_IRQHandler
weak_handler ETH_WKUP_IRQHandler
weak_handler CAN2_TX_IRQHandler
weak_handler CAN2_RX0_IRQHandler
weak_handler CAN2_RX1_IRQHandler
weak_handler CAN2_SCE_IRQHandler
weak_handler OTG_FS_IRQHandler
weak_handler DMA2_Stream5_IRQHandler
weak_handler DMA2_Stream6_IRQHandler
weak_handler DMA2_Stream7_IRQHandler
weak_handler USART6_IRQHandler
weak_handler I2C3_EV_IRQHandler
weak_handler I2C3_ER_IRQHandler
weak_handler OTG_HS_EP1_OUT_IRQHandler
weak_handler OTG_HS_EP1_IN_IRQHandler
weak_handler OTG_HS_WKUP_IRQHandler
weak_handler OTG_HS_IRQHandler
weak_handler DCMI_IRQHandler
weak_handler CRYP_IRQHandler
weak_handler HASH_RNG_IRQHandler
weak_handler FPU_IRQHandler

/* ------------------------------------------------------------------
   User-provided overrides (weak aliases)
   ------------------------------------------------------------------ */
.weak Default_Handler
.type Default_Handler, %function
Default_Handler:
    b .
.size Default_Handler, .-Default_Handler

/* ------------------------------------------------------------------
   no __user_initial_stackheap under GCC/newlib (the two-region memory
   scheme is a Keil/ARMCC macro. GCC's nano.specs calls __libc_init_array
   which handles the C runtime setup.)
   ------------------------------------------------------------------ */
