#ifndef __RPM_H__
#define __RPM_H__

#include "stm32f4xx.h"

/**
 * @module  rpm.h
 * @subsystem  drivers
 * @depends  stm32f4xx.h, misc.h (NVIC), syscfg.h (SYSCFG_EXTILineConfig)
 * @owns  RPM measurement via EXTI rising-edge + DWT cycle counter (ADR-0010).
 *        Replaces the never-used TIM2 PWM init that previously owned PA5/PB3/PB10/PB11.
 * @caution  ISR context only — RPM_EdgeISR must NOT use floats or FreeRTOS API.
 *           Per-channel state is `volatile` so the ISR can write and the bench
 *           frame builder (called from Send_Groundstation_Telemetry_UART4, normal
 *           task context) can read.
 */

/* Number of sensor channels wired on the bench.  Channel index is the
 * physical pin on the 3-pin header type, NOT the motor number — pairing is
 * decided by which header carries the one bench sensor. */
#define RPM_NUM_CH            4U

/* Reflective marks per prop: 2 (one per blade underside, sensor under the disc). */
#define RPM_PULSES_PER_REV    2U

/* Channel-to-pin mapping.  Grouped per channel so one channel can be remapped
 * in a single place.  PA5 caveat: NOT 5V-tolerant (ADC/DAC-class); see ADR-0010
 * for the bench 10k series resistor when the header rail is 5 V. */
#define RPM_CH0_GPIO_PORT     GPIOA
#define RPM_CH0_GPIO_PIN      GPIO_Pin_5
#define RPM_CH0_GPIO_PINSRC   GPIO_PinSource5
#define RPM_CH0_EXTI_PORT     EXTI_PortSourceGPIOA
#define RPM_CH0_EXTI_LINE     EXTI_Line5

#define RPM_CH1_GPIO_PORT     GPIOB
#define RPM_CH1_GPIO_PIN      GPIO_Pin_3
#define RPM_CH1_GPIO_PINSRC   GPIO_PinSource3
#define RPM_CH1_EXTI_PORT     EXTI_PortSourceGPIOB
#define RPM_CH1_EXTI_LINE     EXTI_Line3

#define RPM_CH2_GPIO_PORT     GPIOB
#define RPM_CH2_GPIO_PIN      GPIO_Pin_10
#define RPM_CH2_GPIO_PINSRC   GPIO_PinSource10
#define RPM_CH2_EXTI_PORT     EXTI_PortSourceGPIOB
#define RPM_CH2_EXTI_LINE     EXTI_Line10

#define RPM_CH3_GPIO_PORT     GPIOB
#define RPM_CH3_GPIO_PIN      GPIO_Pin_11
#define RPM_CH3_GPIO_PINSRC   GPIO_PinSource11
#define RPM_CH3_EXTI_PORT     EXTI_PortSourceGPIOB
#define RPM_CH3_EXTI_LINE     EXTI_Line11

/* Staleness timeout: 0.5 s of no full-revolution edges => RPM = 0. */
#define RPM_TIMEOUT_CYCLES    (SystemCoreClock / 2U)

/* Glitch reject: discard revolution periods shorter than the period of 20000 RPM.
 * At 168 MHz: (168e6 / 20000) * 60 = 8400 * 60 = 504000 cycles.
 * NOTE: divide-first then multiply — SystemCoreClock * 60U overflows u32 above ~71.6 MHz. */
#define RPM_MIN_PERIOD_CYCLES ((SystemCoreClock / 20000U) * 60U)

/* Ring buffer depth for per-revolution periods (averaged for noise rejection). */
#define RPM_RING_DEPTH        4U

void     RPM_Init(void);
void     RPM_EdgeISR(uint8_t ch);   /* called from EXTI handlers; ch 0..RPM_NUM_CH-1 */
uint16_t RPM_Get(uint8_t ch);       /* averaged RPM, 0 if stopped or stale */

#endif