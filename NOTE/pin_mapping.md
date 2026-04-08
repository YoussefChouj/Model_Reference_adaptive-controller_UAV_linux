Pin mapping and annotated notes ！ STM32F407ZGT(x) project

Summary
- MCU (from your debug project): STM32F407ZGTx (Cortex-M4).
- This file explains where PWM outputs, timers, ADC (battery sense), SWD and serial ports are configured in the firmware and shows the MCU pins used.

Quick reference (what the firmware currently uses)
- Motor outputs (M1..M4): mapped to TIM3 channels (see `BSP/pwm.h` and `BSP/pwm.c`):
  - M1 (TIM3->CCR1) -> TIM3 CH1 -> PA6
  - M4 (TIM3->CCR2) -> TIM3 CH2 -> PA7
  - M2 (TIM3->CCR3) -> TIM3 CH3 -> PB0
  - M3 (TIM3->CCR4) -> TIM3 CH4 -> PB1
  - Note: `#define M1 TIM3->CCR1`, etc. are in `BSP/pwm.h`.

- Additional PWM groups present in firmware:
  - TIM2 channels (configured in `PWM_TIM2_Init`):
    - TIM2 CH1 -> PA5
    - TIM2 CH2 -> PB3
    - TIM2 CH3 -> PB10
    - TIM2 CH4 -> PB11
    - TIM2 is initialized and can be used for other PWMs/outputs (the code initializes them but M1..M4 currently point to TIM3 CCRs).
  - TIM4 channels (used for servos & beep in `PWM_TIM4_Init`):
    - TIM4 CH1 -> PB6
    - TIM4 CH2 -> PB7
    - TIM4 CH3 -> (used in code for beep; ensure pin mapped elsewhere if needed)
    - TIM4 configured for 50 Hz servo outputs (TIM4 prescaler/period set accordingly).

- ADC (battery sense):
  - `USER/ADC.c` configures ADC1 and selects `ADC_Channel_4` for the regular channel. On STM32F407, ADC_Channel_4 is typically on pin: PA4 (check your MCU package).
  - The code uses ADC1 and a regular channel config; see `USER/ADC.c` for details and `Voltage_Calculation` for conversion.

- SWD (programming/debug header):
  - SWCLK, SWDIO and 3.3V are referenced in `NOTE/pcb.txt` and are the standard SWD programming pins (PA13 = SWDIO, PA14 = SWCLK on STM32F4 devices). The notes show the SWD header location on the board.

- UARTs / Serial ports (where to find them):
  - The repo includes BSP/usart1.c .. usart6.c. Port-to-pin mappings depend on how each `usartX_Init` configures GPIO in those files ！ inspect each `BSP/usart*.c` to see the exact TX/RX pins. Example: a comment in `TASK/RemoterTask.c` mentions `PA10 (USART1_RX)`.

Where the mappings are defined in code (files to edit)
- Motor PWM mapping
  - `BSP/pwm.h` ！ contains defines for M1..M4 (maps to TIM3 CCR registers).
  - `BSP/pwm.c` ！ contains `PWM_TIM3_Init()`, `PWM_TIM2_Init()`, and `PWM_TIM4_Init()` which configure GPIO pins and AF mapping. To change pins, edit the GPIO_Pin / GPIO_PinSource lines and update AF (GPIO_AF_TIMx) and timer channel mapping.
    - Examples in `BSP/pwm.c`:
      - `GPIO_PinAFConfig ( GPIOA, GPIO_PinSource6, GPIO_AF_TIM3 );  //TIM3 CH1`  => PA6 TIM3 CH1
      - `GPIO_PinAFConfig ( GPIOB, GPIO_PinSource0, GPIO_AF_TIM3 );  //TIM3 CH3`  => PB0 TIM3 CH3

- Battery sense ADC
  - `USER/ADC.c` ！ `ADC_RegularChannelConfig(ADC1, ADC_Channel_4, 1, ...);` ！ change to another ADC channel if the hardware battery sense pin differs.

- UARTs and other peripheral pins
  - `BSP/usart1.c`, `BSP/usart2.c`, etc. ！ open these to see which GPIO pins are used for TX/RX. If you remap serial ports, edit the corresponding `GPIO_PinAFConfig` and `GPIO_Init` calls.

How to update the mapping safely
1. Decide new pins and verify the MCU supports that timer/channel on the chosen pin (consult STM32F407 datasheet / alternate function table). Many timers have multiple AF pin options but not every pin can be used for every channel.
2. Update `BSP/pwm.c`:
   - Change the GPIO pins used in the `GPIO_InitStructure.GPIO_Pin = ...` lines.
   - Change the `GPIO_PinAFConfig( ... GPIO_PinSourceX, GPIO_AF_TIMY );` lines to match the timer peripheral you want on that pin.
3. If you change which timer/channel is used for motors (i.e., you move M1..M4 from TIM3 to TIM2), update `BSP/pwm.h` so that `M1..M4` map to the correct `TIMx->CCRn` registers.
4. Rebuild and test with props removed; start with `Set_Zero_Motors()` or `Set_IDLE_Motors()` before applying throttle.

Motor numbering and rotation (from `NOTE/readme.txt`)
- Motor numbering used in notes:
  - 1 = top-right (motor 1) ！ rotation: white (CCW)
  - 2 = bottom-left ！ rotation: white (CCW)
  - 3 = top-left ！ rotation: black (CW)
  - 4 = bottom-right ！ rotation: black (CW)
- Confirm these match the wiring on your airframe. The firmware comments in `BSP/pwm.c` include sample assignments and rotation hints.

Helpful checks before changing pins
- Confirm the MCU package: `STM32F407ZGTx` has specific pin availability ！ use the STM32F407 datasheet and reference manual.
- Use Keil project `uvprojx` to ensure correct startup defines and that the code includes the correct peripheral libraries.
- After changing pins, check `GPIO_PinAFConfig` uses the right AF number for that pin & timer (GPIO_AF_TIM2/TIM3/TIM4 are used already in code).
