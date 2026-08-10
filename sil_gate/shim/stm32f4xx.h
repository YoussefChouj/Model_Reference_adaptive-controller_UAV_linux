/* ============================================================================
 * sil_gate/shim/stm32f4xx.h
 *
 * HOST-TEST STUB ONLY.
 *
 * This file is part of the Software-in-the-Loop gate (sil_gate/) and is
 * **NEVER compiled into firmware**. It exists so that API/ekf.c (and, later,
 * API/mrac.c) can be host-compiled by gcc on a developer laptop without pulling
 * in the real STM32 HAL.
 *
 * Widths are matched to the ARM ABI used by Keil ARMCC V5.06 (Cortex-M4F):
 *
 *   u8/u16/u32   = unsigned char / unsigned short / unsigned int
 *   s8/s16/s32   = signed   char / signed   short / signed   int
 *   uint8_t etc. = from <stdint.h> (always 8/16/32 on this ABI)
 *   _Bool        = 1 byte per C99 / ARMCC
 *
 * Nothing below this line is firmware code. Do not move this file under
 * API/ or Global_file/ — sil_gate/ is the only legal location.
 * ============================================================================
 */
#ifndef SIL_SHIM_STM32F4XX_H
#define SIL_SHIM_STM32F4XX_H

#include <stdint.h>
#include <stddef.h>

/* CMSIS-style fixed-width integer aliases (the real stm32f4xx.h provides these
 * from core_cm4.h, but the types they alias are the same ones <stdint.h>
 * guarantees under ARM ABI). No floating-point or hardware-register types are
 * reached by sil_gate target files (ekf.c, mrac.c), so we deliberately omit
 * them — see sil_gate/README.md for the seam definition. */
typedef int8_t   s8;
typedef int16_t  s16;
typedef int32_t  s32;
typedef uint8_t  u8;
typedef uint16_t u16;
typedef uint32_t u32;

typedef volatile uint8_t  vu8;
typedef volatile uint16_t vu16;
typedef volatile uint32_t vu32;

/* Hardware-register / peripheral types from the real stm32f4xx.h are NOT
 * reached by sil_gate. Any type here that gets referenced triggers a compile
 * failure and that is by design — keeps the shim honest. */

/* USART/DMA register types — referenced transitively by Global_file/robot_types.h
 * via USART_TypeDef* / DMA_Stream_TypeDef* pointers. We only need the pointer
 * types to be valid for the C compiler; the body of these structs is never
 * dereferenced by sil_gate targets because ekf.c / mrac.c never read them. */
struct _USART_TYPEDEF;
struct _DMA_STREAM_TYPEDEF;
typedef struct _USART_TYPEDEF     USART_TypeDef;
typedef struct _DMA_STREAM_TYPEDEF DMA_Stream_TypeDef;

/* GPIO register type — also pointer-only. */
struct _GPIO_TYPEDEF;
typedef struct _GPIO_TYPEDEF GPIO_TypeDef;

/* Bit-band / atomic primitives used by inline functions in robot_types.h
 * (GPIO_ReadInputDataBit etc.). We provide just enough so the inlines compile
 * when sil_gate compiles its target files; sil_gate never CALLS them, but the
 * preprocessor still parses the bodies. The bodies are stubbed so the gate
 * never accidentally invokes them. */
#define Bit_SET     ((uint8_t)1)
#define Bit_RESET   ((uint8_t)0)
#define GPIO_Pin_0  ((uint16_t)0x0001)
#define GPIO_Pin_1  ((uint16_t)0x0002)
#define GPIO_Pin_2  ((uint16_t)0x0004)
#define GPIO_Pin_3  ((uint16_t)0x0008)
#define GPIO_Pin_4  ((uint16_t)0x0010)
#define GPIO_Pin_5  ((uint16_t)0x0020)
#define GPIO_Pin_6  ((uint16_t)0x0040)
#define GPIO_Pin_7  ((uint16_t)0x0080)
#define GPIO_Pin_8  ((uint16_t)0x0100)
#define GPIO_Pin_9  ((uint16_t)0x0200)
#define GPIO_Pin_10 ((uint16_t)0x0400)
#define GPIO_Pin_11 ((uint16_t)0x0800)
#define GPIO_Pin_12 ((uint16_t)0x1000)
#define GPIO_Pin_13 ((uint16_t)0x2000)
#define GPIO_Pin_14 ((uint16_t)0x4000)
#define GPIO_Pin_15 ((uint16_t)0x8000)
#define GPIO_Pin_All ((uint16_t)0xFFFF)

#define GPIO_ReadInputDataBit(port, pin)  ((uint8_t)Bit_RESET)
#define GPIO_ReadInputData(port)          ((uint16_t)0)

/* Some files declare `__IO` as a volatile qualifier. Provide a no-op so the
 * preprocessor is happy. */
#ifndef __IO
#define __IO volatile
#endif

/* PRIMASK access intrinsics — same pattern used in BSP/usart3.c. The real
 * CMSIS `core_cmFunc.h` provides them on the ARM target. The shim provides
 * a no-op for the sil_gate host compile: the critical section is vacuous
 * (single-threaded test harness) but the API is callable, so MRAC's
 * #ifdef-guarded SetPrior/GetPrior compile and link. The sil_gate never
 * exercises a true race, so the no-op is a faithful semantic mapping for
 * the test purpose. */
#ifndef __get_PRIMASK
#define __get_PRIMASK()   (0U)
#endif
#ifndef __set_PRIMASK
#define __set_PRIMASK(v)  ((void)(v))
#endif
#ifndef __disable_irq
#define __disable_irq()   ((void)0)
#endif
#ifndef __enable_irq
#define __enable_irq()    ((void)0)
#endif

#endif /* SIL_SHIM_STM32F4XX_H */