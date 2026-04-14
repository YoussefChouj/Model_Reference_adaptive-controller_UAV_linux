---
title: UART Peripheral Map
type: protocol
tags: [uart, usart, dma, hardware, bsp]
created: 2026-04-14
updated: 2026-04-14
sources: [BSP/usart4.c, BSP/usart5.c, BSP/usart6.c, BSP/BSP.h, TASK/stm32f4xx_it.c]
related_files: [BSP/usart4.c, BSP/usart5.c, BSP/usart6.c, TASK/stm32f4xx_it.c]
---

This page maps every UART peripheral to its purpose, GPIO pins, baud rate, DMA stream, and ISR handler. Any agent modifying serial communication should check this page first to avoid port conflicts.

## Peripheral Summary

| UART | Purpose | TX Pin | RX Pin | Baud | DMA RX | DMA TX | ISR |
|------|---------|--------|--------|------|--------|--------|-----|
| USART1 | SBUS RC receiver | — | PA10 | 100000 (SBUS) | — | — | `USART1_IRQHandler` (byte-by-byte) |
| USART2 | Optical flow sensor | — | — | — | DMA1_Stream6 (TX) | — | `USART2_IRQHandler` |
| USART3 | Linux companion TX | — | — | — | DMA1_Stream3 (TX) | — | `USART3_IRQHandler` |
| UART4 | T265 + GS command ingress | PA0 (TX) | PA1 (RX) | 115200 | DMA1_Stream2 | — | `UART4_IRQHandler` |
| UART5 | Ground station telemetry TX + GS command ingress | PC12 (TX) | PD2 (RX) | 115200 | DMA1_Stream0 | DMA1_Stream7 | `UART5_IRQHandler` |
| USART6 | GPS (stub, empty init) | — | — | — | — | — | `USART6_IRQHandler` (empty) |

## USART1 — SBUS Receiver

- **Purpose**: Receives SBUS protocol frames from the RC receiver
- **RX interrupt**: `USART1_IRQHandler` (`TASK/stm32f4xx_it.c:11-25`) receives one byte at a time and feeds `DrvSbusGetOneByte(com_data)` to the SBUS decoder
- **Output**: `sbus_channel[]` array, `sbus_last_valid_tick` timestamp
- **No DMA**: Byte-by-byte RXNE interrupt, appropriate for inverted-UART SBUS protocol
- **Consumed by**: [[RemoterTask]] for channel scaling and loss detection

## USART2 — Optical Flow (ANO)

- **Purpose**: Receives optical flow data from ANO-compatible sensor
- **RX interrupt**: `USART2_IRQHandler` (`TASK/stm32f4xx_it.c:32-49`) calls `AnoOF_GetOneByte(com_data)` for protocol parsing
- **DMA TX**: `DMA1_Stream6` (`TASK/stm32f4xx_it.c:56-63`) for outbound data
- **Consumed by**: Position estimation in stabilizer velocity loops

## USART3 — Linux Companion

- **Purpose**: Communication with onboard Linux computer (send telemetry, receive commands)
- **ISR**: `USART3_IRQHandler` (`TASK/stm32f4xx_it.c:70-78`) handles IDLE interrupt for RX
- **DMA TX**: `DMA1_Stream3` (`TASK/stm32f4xx_it.c:97-104`) — TX completion handler. Comment warns this handler must not be deleted or the system hangs.
- **Called in**: `usart3_send()` invoked by `Send_Task` at 100 Hz (`USER/main.c:129`)

## UART4 — T265 Tracking Camera + Ground Station Commands

- **Purpose**: Dual-use port. Receives T265 position data (44-byte frames with `0xAA 0xAA` sync) AND ground station command frames (`0xCC 0xDD` sync)
- **GPIO**: PA0 (TX), PA1 (RX) (`BSP/usart4.c:20-28`)
- **Baud**: 115200 (`BSP/usart4.c:36`)
- **DMA RX**: DMA1_Stream2, Channel 4, circular mode (`BSP/usart4.c:50-60`)
- **ISR**: `UART4_IRQHandler` (`TASK/stm32f4xx_it.c:152-171`)
  - On IDLE: calls `USART_Receive(&UART4_Rcr)` to extract bytes
  - Then dispatches to `Handle_UART4_GroundStation_Command()` for `0xCC 0xDD` frames
  - Then dispatches to `Decode_RX_Data_t265()` for `0xAA 0xAA` T265 frames
- **Consumed by**: T265 data → `_linux_data_st linux_data` struct; GS commands → `Process_GroundStation_Command()`

## UART5 — Ground Station Telemetry + Commands

- **Purpose**: Primary ground station link. Sends telemetry frames (`0xAA 0xBB`) and receives command frames (`0xCC 0xDD`)
- **GPIO**: PC12 (TX), PD2 (RX) (`BSP/usart5.c:30-46`)
- **Baud**: 115200 (`BSP/usart5.c:55`)
- **DMA RX**: DMA1_Stream0, circular mode (`BSP/usart5.c:68-88`)
- **DMA TX**: DMA1_Stream7 (`BSP/usart5.c:92-111`), used by `Send_Groundstation_Telemetry_UART4()` (despite the function name, telemetry is sent via UART5 DMA stream 7)
- **ISR**: `UART5_IRQHandler` (`TASK/stm32f4xx_it.c:321-339`)
  - On IDLE: `USART_Receive(&UART5_Rcr)` then `Handle_UART5_GroundStation_Command()`
- **TX completion**: `DMA1_Stream7_IRQHandler` (`TASK/stm32f4xx_it.c:341-348`)

## USART6 — GPS (Stub)

- **Purpose**: Reserved for GPS module
- **Status**: Empty init file (`BSP/usart6.c:1`) and empty ISR (`TASK/stm32f4xx_it.c:360-363`)
- **Not operational** in current firmware

## DMA Stream Allocation

| DMA | Stream | Channel | UART | Direction |
|-----|--------|---------|------|-----------|
| DMA1 | Stream0 | Ch4 | UART5 | RX |
| DMA1 | Stream2 | Ch4 | UART4 | RX |
| DMA1 | Stream3 | — | USART3 | TX |
| DMA1 | Stream6 | — | USART2 | TX |
| DMA1 | Stream7 | Ch4 | UART5 | TX |

All DMA RX streams use circular mode for continuous reception without CPU intervention. The `USART_Receive()` helper (`TASK/stm32f4xx_it.c:113-143`) extracts new bytes from the DMA circular buffer on each IDLE interrupt.

## Common Pitfall: Telemetry Function Naming

`Send_Groundstation_Telemetry_UART4()` in `TASK/send_data.c` is misleadingly named — it actually sends via **UART5** DMA Stream 7 (`TASK/send_data.c:441-448`). The function name is a legacy artifact. Do not "fix" this by routing to UART4; that would conflict with T265 data.

## See Also

- [[Ground-Station Binary Protocol]] — frame formats
- [[Interrupt Map]] — ISR dispatch details
- [[Ground Station Bridge]] — Python-side serial handling
