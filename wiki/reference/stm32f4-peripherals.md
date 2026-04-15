# STM32F4 Peripherals Reference (Used Subset)

> Documents **only** the STM32F4 peripherals this firmware actually uses, with code anchors to the initialization and ISR handlers. This is not a mirror of RM0090 — it's a focused reference for understanding the hardware layer of this specific quadrotor.

**Canonical reference**: ST RM0090 Reference Manual rev. 19 — [st.com/resource/en/reference_manual/rm0090](https://www.st.com/resource/en/reference_manual/rm0090-stm32f405415-stm32f407417-stm32f427437-and-stm32f429439-advanced-armbased-32bit-mcus-stmicroelectronics.pdf) (1749 pages — do **not** copy into wiki; link only)

**Related wiki**: [[UART Peripheral Map]], [[Interrupt Map]], [[Timer & PWM Configuration]], [[Motor Mixer]]

---

## 1. Clock Tree Summary

The STM32F405/F407 in this project runs at 168 MHz core clock. The peripheral buses run at:

| Bus | Clock | Peripherals on this bus |
|:---|:---|:---|
| AHB1 | 168 MHz | GPIO, DMA1, DMA2 |
| APB1 | 42 MHz | TIM2, TIM3, TIM4, TIM5, USART2, USART3, UART4, UART5, SPI2 |
| APB2 | 84 MHz | USART1, USART6, ADC1, SPI1, TIM1 |

**Timer clock quirk**: When APB prescaler > 1 (which it is: AHB/APB1 = 168/42 = 4), the timer clocks run at **2× the APB frequency**:
- TIM2, TIM3, TIM4, TIM5 timer clock = **84 MHz** (not 42 MHz)
- This is why `pwm.c:60` uses prescaler = 42−1 to get 2 MHz, not prescaler = 21−1

---

## 2. TIM3 — Motor ESC PWM Output

**Purpose**: Generates 200 Hz PWM signals for the 4 motor ESCs.
**Init**: `PWM_TIM3_Init()` in `BSP/pwm.c:23–101`
**RM0090 section**: §18 (General-purpose timers TIM2 to TIM5)

### Configuration

| Parameter | Value | Code location | Derivation |
|:---|:---|:---|:---|
| Timer clock | 84 MHz | APB1 timer = 2 × 42 MHz | |
| Prescaler | 42 − 1 = 41 | `pwm.c:60` | 84 MHz / 42 = **2 MHz** tick rate |
| Period (ARR) | 10000 − 1 = 9999 | `pwm.c:59` | 2 MHz / 10000 = **200 Hz** PWM frequency |
| Resolution | 0.5 µs per count | | 1 / 2 MHz |
| PWM mode | PWM1 (OCxM = 110) | `pwm.c:67` | Output high when CNT < CCR |
| Counter mode | Up counting | `pwm.c:62` | |

### GPIO Mapping

| Channel | CCR register | GPIO | Pin | Macro | Motor |
|:---|:---|:---|:---|:---|:---|
| CH1 | TIM3->CCR1 | GPIOA | Pin 6 | `M1` | Motor 1 (top-left CW) |
| CH2 | TIM3->CCR2 | GPIOA | Pin 7 | `M4` | Motor 4 (top-right CCW) |
| CH3 | TIM3->CCR3 | GPIOB | Pin 0 | `M2` | Motor 2 (bottom-right CW) |
| CH4 | TIM3->CCR4 | GPIOB | Pin 1 | `M3` | Motor 3 (bottom-left CCW) |

GPIO AF config: `pwm.c:44–56`
Motor macros: `pwm.h:8–11`

**Critical note**: The macro mapping `M1=CCR1, M4=CCR2, M2=CCR3, M3=CCR4` is intentionally non-sequential. The channel-to-motor mapping was determined by PCB routing. Do not reorder without verifying the physical wiring.

### PWM Range

| Symbolic | CCR value | Pulse width | Meaning |
|:---|:---|:---|:---|
| `Motor_PWM_ZERO` | 2000 | 1000 µs | Motor stopped (ESC minimum) |
| `Motor_PWM_IDLE` | 2150 | 1075 µs | Motor spinning at idle (armed, no thrust) |
| `Motor_PWM_MAX` | 4000 | 2000 µs | Full throttle |

Defined in `pwm.h:13–15`. The ESC interprets 1000–2000 µs pulse width as 0–100% throttle, which maps to CCR values 2000–4000 at 0.5 µs resolution.

---

## 3. TIM5 — Microsecond Timestamp

**Purpose**: Free-running 32-bit counter for high-resolution time measurement.
**Init**: `TIM5_Configuration()` in `API/time_estimate.c:7–21`
**RM0090 section**: §18 (TIM5 is 32-bit capable)

### Configuration

| Parameter | Value | Derivation |
|:---|:---|:---|
| Timer clock | 84 MHz | APB1 timer |
| Prescaler | 84 − 1 = 83 | `time_estimate.c:3` → 84 MHz / 84 = **1 MHz** (1 µs ticks) |
| Period | 2³² − 1 = 4294967295 | `time_estimate.c:4` → wraps every ~4295 seconds (~72 minutes) |
| Counter mode | Up counting | `time_estimate.c:15` |

TIM5 is the only 32-bit general-purpose timer on STM32F405. Using the full 32-bit period means timestamps don't wrap for over an hour — long enough for any practical flight.

Reading `TIM5->CNT` gives current microsecond count. No interrupt needed.

---

## 4. TIM4 — Servo PWM Output

**Purpose**: 50 Hz PWM for pitch and roll camera servos + buzzer.
**Init**: `PWM_TIM4_Init()` in `BSP/pwm.c:194–251`

### Configuration

| Parameter | Value | Derivation |
|:---|:---|:---|
| Prescaler | 84 − 1 | 84 MHz / 84 = **1 MHz** (1 µs ticks) |
| Period | 20000 − 1 | 1 MHz / 20000 = **50 Hz** (standard servo) |

| Channel | GPIO | Function |
|:---|:---|:---|
| CH1 | PB6 | Roll servo |
| CH2 | PB7 | Pitch servo |
| CH3 | (internal) | Buzzer (via `SetBeep()`) |

Servo pulse mapping: 500–2500 µs → 0°–180° (standard hobby servo protocol). The `SetPitchAngle()` and `SetRollAngle()` functions (`pwm.c:260–268`) convert degrees to CCR values.

---

## 5. USART Peripherals — Async Serial + DMA

The firmware uses all 6 USART peripherals. Full mapping is in [[UART Peripheral Map]]; this section covers the hardware configuration patterns.

### 5.1 Common USART Configuration Pattern

Every USART in this firmware follows the same initialization sequence:
1. Enable GPIO clock (`RCC_AHB1PeriphClockCmd`)
2. Enable USART clock (`RCC_APBxPeriphClockCmd`)
3. Configure GPIO pins as AF (alternate function)
4. Connect GPIO to USART AF (`GPIO_PinAFConfig`)
5. Configure USART parameters (baud, word length, stop bits, parity)
6. Enable interrupts (RXNE for polled, IDLE for DMA-based)
7. For DMA: configure DMA stream/channel, enable circular mode

### 5.2 USART1 — SBUS Receiver (Special Configuration)

**Init**: `USART1_Configuration()` in `BSP/usart1.c:12–47`

SBUS uses **non-standard serial parameters** defined by the Futaba protocol:

| Parameter | Value | Why |
|:---|:---|:---|
| Baud rate | 100000 | SBUS protocol specification |
| Word length | 8 bits | |
| Stop bits | 2 | SBUS requires 2 stop bits |
| Parity | Even | SBUS requires even parity |
| Mode | RX only | No transmission needed |
| Interrupt | RXNE | Byte-by-byte processing via `DrvSbusGetOneByte()` |
| DMA | Not used | SBUS frame arrival is asynchronous |

NVIC priority: **Preemption = 0, Sub = 0** — highest possible. SBUS loss detection is time-critical for safety.

### 5.3 UART5 — Ground Station (DMA Configuration Example)

**Init**: `UART5_Configuration()` in `BSP/usart5.c:18–104`

| Parameter | Value |
|:---|:---|
| Baud rate | 115200 |
| Word length | 8 bits |
| Stop bits | 1 |
| Parity | None |
| DMA RX | DMA1_Stream0, Channel 4, circular mode |
| DMA TX | DMA1_Stream7, Channel 4 |
| Interrupt | IDLE (frame boundary detection) |
| NVIC priority | Preemption = 2, Sub = 0 |

### 5.4 DMA Stream/Channel Assignment

STM32F4 DMA uses a fixed mapping of peripherals to stream/channel combinations (RM0090 Table 42–43):

| Peripheral | Direction | DMA Controller | Stream | Channel |
|:---|:---|:---|:---|:---|
| USART2 TX | Memory → Peripheral | DMA1 | Stream 6 | Ch 4 |
| USART3 TX | Memory → Peripheral | DMA1 | Stream 3 | Ch 4 |
| UART4 RX | Peripheral → Memory | DMA1 | Stream 2 | Ch 4 |
| UART5 RX | Peripheral → Memory | DMA1 | Stream 0 | Ch 4 |
| UART5 TX | Memory → Peripheral | DMA1 | Stream 7 | Ch 4 |

**DMA circular mode** (used for RX streams): The DMA controller wraps around to the beginning of the buffer when it reaches the end, creating a ring buffer. The firmware uses the IDLE interrupt to detect frame boundaries, then computes how many bytes were received by reading `DMA_GetCurrDataCounter()` in `USART_Receive()` (`stm32f4xx_it.c:113–143`).

**DMA transfer complete interrupt** (used for TX): When a DMA TX transfer finishes, the TC interrupt fires and the ISR disables the DMA stream to prepare for the next transmission. This is critical — without the TC handler, the DMA stream remains active and can re-transmit stale data. See the `DMA1_Stream3_IRQHandler` warning in [[Interrupt Map]].

---

## 6. SPI — BMI088 IMU Communication

**Purpose**: Reads accelerometer and gyroscope data from the Bosch BMI088 6-axis IMU.
**Init**: `SPI_Configuration()` in `BSP/spi.c` (file not tracked in git; confirmed from linker map at `OBJ/JX_FLY.map:479–486`)
**Driver**: `bmi088_init()` called from `BSP/BSP.c:14`

The BMI088 datasheet specifies SPI Mode 3 (CPOL=1, CPHA=1) at up to 10 MHz. The SPI peripheral used is SPI2 (APB1, 42 MHz bus clock).

The SPI driver provides `spi2_read_write_byte()` for register-level read/write. The sensor data preparation function `Sensor_Data_Prepare()` is called at 1 kHz from `IMUSample_Task` (`main.c:167`).

---

## 7. NVIC Priority Model

**Configuration**: `NVIC_PriorityGroupConfig(NVIC_PriorityGroup_4)` in `BSP/BSP.c:6`

Group 4 means: **4 bits preemption priority, 0 bits sub-priority**. This gives 16 preemption levels (0 = highest, 15 = lowest) with no sub-priority distinction.

### Priority Assignment in This Firmware

| IRQ | Preemption | Handler | Justification |
|:---|:---|:---|:---|
| USART1 (SBUS) | 0 | `USART1_IRQHandler` | Highest — RC loss detection is safety-critical |
| UART4 (T265/GS) | 1–2 | `UART4_IRQHandler` | Navigation/command data |
| UART5 (GS) | 2 | `UART5_IRQHandler` | Ground station commands |
| DMA1_Stream3 (USART3 TX) | 3 | `DMA1_Stream3_IRQHandler` | TX completion |
| DMA1_Stream6 (USART2 TX) | 3 | `DMA1_Stream6_IRQHandler` | TX completion |
| DMA1_Stream7 (UART5 TX) | 3 | `DMA1_Stream7_IRQHandler` | TX completion |
| SysTick | 15 | FreeRTOS tick | Lowest — yields to all peripherals |

### Interaction with FreeRTOS

FreeRTOS on Cortex-M4 uses `configMAX_SYSCALL_INTERRUPT_PRIORITY` to define the boundary between:
- **Above max syscall priority** (lower numeric value): ISRs that must never call FreeRTOS API functions — they run with absolute priority
- **At or below max syscall priority**: ISRs that may call `FromISR()` API functions (e.g., `xTaskGetTickCountFromISR()`)

USART1 at priority 0 is above the FreeRTOS threshold. The `sbus_last_valid_tick` timestamp uses `xTaskGetTickCountFromISR()` (`BSP/usart1.c`), which technically requires the ISR to be at or below `configMAX_SYSCALL_INTERRUPT_PRIORITY`. This works if the FreeRTOS config sets the max syscall priority to 0 or if the tick reading is implemented without FreeRTOS critical sections.

---

## 8. ADC — Battery Voltage Monitor

**Purpose**: Reads battery voltage through a resistor divider.
**Init**: `ADC1_Configuration()` called from `BSP/BSP.c:10`
**Usage**: `Get_Voltage()` in `StabilizerTask.c:674–684`

The ADC reads a scaled voltage, and the firmware converts it back to actual battery voltage:

```c
real_voltage = (voltage / 2.85f) * 16.8f;
```

If `real_voltage < 15.0f` (low battery for 4S LiPo), the buzzer is activated via `SetBeep(1)`.

---

## 9. Evidence vs. Inference

### Verified from Code

- `NVIC_PriorityGroup_4` set at `BSP/BSP.c:6`
- TIM3 prescaler = 42−1, period = 10000−1 (`pwm.c:59–60`)
- TIM5 prescaler = 84−1, period = 2³²−1 (`time_estimate.c:3–4`)
- TIM4 prescaler = 84−1, period = 20000−1 (`pwm.c:219–220`)
- Motor PWM macros M1–M4 mapped to TIM3 CCR1–CCR4 (`pwm.h:8–11`)
- USART1 at 100000 baud, 8E2, RXNE interrupt, priority 0 (`usart1.c:37–45`)
- UART5 at 115200 baud, DMA1_Stream0_Ch4 circular, IDLE interrupt, priority 2 (`usart5.c:55–80`)
- SPI2 used for BMI088 (confirmed from linker map, `OBJ/JX_FLY.map:479–486`)
- DMA TC handlers for Stream3, Stream6, Stream7 (`stm32f4xx_it.c:56–63, 97–104, 341–348`)

### Inferred / Theoretical Context

- The "2× APB timer clock" rule comes from RM0090 §7.2 (RCC clocks) — not stated in firmware comments but confirmed by the prescaler math
- The claim about SPI Mode 3 for BMI088 comes from the BMI088 datasheet, not from the unavailable `spi.c` source
- NVIC priority levels for UART4 and DMA are approximate (some ISRs' exact priority values were not visible in the available source files)

---

## 10. Quick Reference Links

- **RM0090**: [STM32F405/415 Reference Manual](https://www.st.com/resource/en/reference_manual/rm0090-stm32f405415-stm32f407417-stm32f427437-and-stm32f429439-advanced-armbased-32bit-mcus-stmicroelectronics.pdf) — Chapter 18 (Timers), Chapter 30 (USART), Chapter 10 (DMA), Chapter 12 (ADC)
- **BMI088 datasheet**: [Bosch BMI088](https://www.bosch-sensortec.com/products/motion-sensors/imus/bmi088/) — SPI register map and timing
- **This codebase**: [[UART Peripheral Map]] for all 6 UARTs, [[Interrupt Map]] for ISR dispatch, [[Timer & PWM Configuration]] for TIM3 entity details
