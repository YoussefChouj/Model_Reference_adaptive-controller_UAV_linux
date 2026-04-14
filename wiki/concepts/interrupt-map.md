---
title: Interrupt Map
type: concept
tags: [isr, dma, interrupt, stm32]
created: 2026-04-14
updated: 2026-04-14
sources: [TASK/stm32f4xx_it.c]
related_files: [TASK/stm32f4xx_it.c, BSP/usart4.c, BSP/usart5.c]
---

All application-level ISRs are defined in `TASK/stm32f4xx_it.c`. This page catalogs every handler, its trigger condition, and the data flow from interrupt context into task context.

## ISR Table

| Handler | Trigger | Action | Line |
|---------|---------|--------|------|
| `USART1_IRQHandler` | USART1 RXNE (byte received) | `DrvSbusGetOneByte(com_data)` — SBUS decoder | `stm32f4xx_it.c:11` |
| `USART2_IRQHandler` | USART2 RXNE | `AnoOF_GetOneByte(com_data)` — optical flow parser | `stm32f4xx_it.c:32` |
| `DMA1_Stream6_IRQHandler` | DMA1 Stream6 TC (USART2 TX done) | Clear flag + disable DMA | `stm32f4xx_it.c:56` |
| `USART3_IRQHandler` | USART3 IDLE | Read SR+DR to clear flag | `stm32f4xx_it.c:70` |
| `DMA1_Stream3_IRQHandler` | DMA1 Stream3 TC (USART3 TX done) | Clear flag + disable DMA | `stm32f4xx_it.c:97` |
| `UART4_IRQHandler` | UART4 IDLE | `USART_Receive` → `Handle_UART4_GroundStation_Command` → `Decode_RX_Data_t265` | `stm32f4xx_it.c:152` |
| `UART5_IRQHandler` | UART5 IDLE | `USART_Receive` → `Handle_UART5_GroundStation_Command` | `stm32f4xx_it.c:321` |
| `DMA1_Stream7_IRQHandler` | DMA1 Stream7 TC (UART5 TX done) | Clear flag + disable DMA | `stm32f4xx_it.c:341` |
| `USART6_IRQHandler` | — | Empty body (GPS stub) | `stm32f4xx_it.c:360` |

## Data Flow: ISR → Task

### SBUS Path (USART1)
```
USART1_IRQHandler [ISR]
  → DrvSbusGetOneByte() [ISR context]
    → sbus_channel[]    [shared global, no lock]
    → sbus_last_valid_tick = xTaskGetTickCountFromISR()
      ↓
remoter_task() [100 Hz task context]
  → reads sbus_channel[], sbus_last_valid_tick
  → writes Remoter.*, sbus_lost
```

### Ground Station Command Path (UART4/UART5)
```
UART4_IRQHandler / UART5_IRQHandler [ISR]
  → USART_Receive(&UARTx_Rcr) [copies DMA buffer → mailbox]
  → Handle_UARTx_GroundStation_Command() [ISR context]
    → validates 0xCC 0xDD sync, CRC
    → pushes into cmd queue (ring buffer)
      ↓
Process_GroundStation_Command() [100 Hz task context in Send_Task]
  → pops from cmd queue
  → dispatches by CMD_ID → writes globals
```

### T265 Path (UART4 only)
```
UART4_IRQHandler [ISR]
  → USART_Receive(&UART4_Rcr)
  → Decode_RX_Data_t265() [ISR context]
    → validates 0xAA 0xAA sync
    → decodes float32 fields from mailbox
    → writes linux_data.* globals
```

## USART_Receive Helper

`USART_Receive(USART_RX_TypeDef*)` (`TASK/stm32f4xx_it.c:113-143`) extracts newly-arrived bytes from a DMA circular buffer into a fixed-size mailbox. It handles wrap-around when the DMA pointer crosses the buffer boundary. Returns byte count for this reception event.

This function runs in ISR context, so it must not block or allocate memory.

## NVIC Priority Assignments

| UART | Preemption Priority | Sub Priority | Source |
|------|-------------------|--------------|--------|
| UART4 | 0 | 0 | `BSP/usart4.c:31-33` |
| UART5 | 2 | 0 | `BSP/usart5.c:50-52` |

UART4 has the highest NVIC priority (0), which means T265 + GS command reception on UART4 preempts UART5 telemetry processing. This prioritization makes sense because command ingress is more latency-sensitive than telemetry output.

## Critical Warning: DMA1_Stream3_IRQHandler

The comment in source code explicitly warns: "this handler must not be deleted, otherwise the system will hang" (`TASK/stm32f4xx_it.c:97`). Even though the handler only clears a flag and disables DMA, removing it causes the DMA TC interrupt to remain pending, which blocks USART3 transmission indefinitely.

## See Also

- [[UART Peripheral Map]] — which UART does what
- [[Ground-Station Binary Protocol]] — frame format details
- [[RemoterTask]] — consumes SBUS ISR output
