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
| USART3 | **Long-range radio module** (TX only in practice) | PC10 | PC11 | 9600 | DMA1_Stream1 (configured, never enabled) | DMA1_Stream3 | `USART3_IRQHandler` (discards RX) |
| UART4 | T265 + GS command ingress | PA0 (TX) | PA1 (RX) | 115200 | DMA1_Stream2 | — | `UART4_IRQHandler` |
| UART5 | **Ground station link via wireless CMSIS-DAP VCP** — telemetry TX, GS commands, 0x07 subscribe | PC12 (TX) | PD2 (RX) | 115200 | DMA1_Stream0 | DMA1_Stream7 | `UART5_IRQHandler` |
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

## USART3 — Long-Range Radio Module

**Physical wiring (operator-confirmed 2026-07-26)**: PC10/PC11 go to the long-range
communication module. This port was previously mislabelled "Linux companion" here and
"sensor stream" in `CLAUDE.md`; both were wrong. The optical-flow sensor is USART2.

- **GPIO**: PC10 (TX), PC11 (RX), both `GPIO_AF_USART3` (`BSP/usart3.c:23-31`).
  No conflict with `pwm.c`, which uses **GPIOB** 3/10/11 (`BSP/pwm.c:135-144`).
- **Baud**: 9600 (`BSP/usart3.c:48`) — 100× slower than the UART5 ground-station link.
- **Mode**: `USART_Mode_Tx|USART_Mode_Rx` (`BSP/usart3.c:52`) — **RX is enabled in
  hardware**, IDLE interrupt on, `USART_DMAReq_Rx` on.
- **RX is dead in firmware anyway**: `USART3_IRQHandler` (`TASK/stm32f4xx_it.c:115-123`)
  clears the IDLE flag by reading SR then DR and *discards the byte* — no
  `USART_Receive(&USART3_Rcr)` call, no parser. `DMA1_Stream1` is configured
  (`BSP/usart3.c:62-78`) with `Memory0BaseAddr = NULL` and is **never enabled**
  (no `DMA_Cmd(DMA1_Stream1, ENABLE)` anywhere), so `UA3RxDMAbuf` is never filled.
  → Receiving on the long-range link needs firmware work; the pins can do it today.
- **DMA TX**: `DMA1_Stream3` (`TASK/stm32f4xx_it.c:142-149`) — TX completion handler.
  Comment warns this handler must not be deleted or the system hangs.
- **Called in**: `usart3_send()` (`TASK/send_data.c:318-358`) from `Send_Task`
  (`USER/main.c:230`). Payload is a 16-byte **VOFA+ JustFloat** frame: roll/pitch/yaw
  as 3 little-endian float32 + the `00 00 80 7F` JustFloat tail. That is the *only*
  thing the long-range link carries — the real Frame A/B telemetry goes out UART5.

### Two defects in `usart3_send()`

1. **DMA reads a dead stack frame.** `str_USART[16]` is a *local* array
   (`send_data.c:320`) whose address is handed to `DMA1_Stream3->M0AR`
   (`send_data.c:353`) before the function returns. The 16-byte transfer takes
   ~16.7 ms at 9600 baud, during which the stack slot is reused by other calls, so
   the radio transmits partly-corrupted floats. `send_data.h:19` declares
   `extern UCHAR8 str_USART[16]` but **no global definition exists** — the local
   shadows the intended buffer. Fix: make the buffer `static`.
2. **The busy-wait throttles the whole send loop.** `while(DMA_GetCurrDataCounter(
   DMA1_Stream3));` (`send_data.c:349`) blocks until the previous transfer drains.
   16 B × 10 bits ÷ 9600 baud = **16.7 ms**, so `Send_Task` cannot cycle faster than
   ~60 Hz even though it asks for 100 Hz. This is the measured cause of the 60 Hz
   ground-station telemetry ceiling and of EKF predict running at 60 Hz.

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

## UART5 — Ground Station Link (through the wireless CMSIS-DAP dongle)

**Physical wiring (operator-confirmed 2026-07-26)**: PC12/PD2 go to the **wireless
CMSIS-DAP probe** (ALIENTEK ATK-HS-V3), not to a long-range radio. That dongle is a
USB *composite* device — `USB\VID_04D8&PID_00DF\ATK_20190528` — exposing two
independent interfaces to the host:

| Dongle interface | Host sees | Used by |
| --- | --- | --- |
| CMSIS-DAP (SWD) | HID/WinUSB | [[Livewatch]] via pyOCD — live RAM reads |
| Virtual COM port (`&MI_00`) | `USB Serial Device (COMn)` | UART5 — telemetry, commands, 0x07 subscribe |

**Consequence: SWD livewatch and the UART5 0x07 subscribe path share one radio.**
They are not two independent links, so they contend for the same wireless bandwidth,
and losing the dongle loses both at once. The `ground_station` GUI presents them as
alternatives — `_LIVELOG_TRANSPORTS = ("Debugger (SWD)", "Long-range (UART5)")`
(`ground_station/gui/dashboard.py:2865`) — which is **doubly misleading**: UART5 is
not the long-range link, and the two options are one piece of hardware. The class
`Uart5LongRange` (`ground_station/livewatch/transport.py`) carries the same wrong name.

**COM-port identification on this machine** (`config.yaml: livewatch_uart5_port: COM6`
is correct, its comment is not):

- **COM6** = `VID:PID=04D8:00DF SER=ATK_20190528`, description `USB Serial Device` →
  the CMSIS-DAP VCP. **This is UART5** and the real ground-station link.
- **COM7** = `VID:PID=1A86:7523`, description `USB-SERIAL CH340` → the long-range
  module's receiver, i.e. **USART3** (9600 baud, attitude-only, TX only).

`resolve_serial_port` AUTO probes `com_scan` in order and takes the first port emitting
bytes, so it reaches COM6 before COM7 and works today. Two latent traps: (a) if the
dongle is absent or enumerates late, AUTO can select COM7 and decode the 9600-baud
JustFloat stream as 115200 Frame A garbage; (b) `com_match_hints` in `config.yaml` is
parsed as a bare string, not split on whitespace (`serial_bridge.py:116-117`), so
`list(...)` yields *individual characters* and the substring filter matches essentially
every port. The hint filter is therefore a no-op — harmless here only by accident.

- **Purpose**: Primary ground station link. Sends telemetry frames (`0xAA 0xBB`) and receives command frames (`0xCC 0xDD`)
- **GPIO**: PC12 (TX), PD2 (RX) (`BSP/usart5.c:30-46`)
- **Baud**: 115200 (`BSP/usart5.c:55`)
- **DMA RX**: DMA1_Stream0, circular mode (`BSP/usart5.c:68-88`)
- **DMA TX**: DMA1_Stream7 (`BSP/usart5.c:92-111`), used by `Send_Groundstation_Telemetry_UART4()` (despite the function name, telemetry is sent via UART5 DMA stream 7)
- **ISR**: `UART5_IRQHandler` (`TASK/stm32f4xx_it.c:321-339`)
  - On IDLE: `USART_Receive(&UART5_Rcr)` then `Handle_UART5_GroundStation_Command()`
- **TX completion**: `DMA1_Stream7_IRQHandler` (`TASK/stm32f4xx_it.c:341-348`)

## Measured link budget (2026-07-26, drone powered, both links attached)

Read-only serial probes, firmware as flashed before the `usart3_send()` fixes:

| Port | Result |
| --- | --- |
| **COM6** (UART5, CMSIS-DAP VCP) @115200 | **8569 B/s** = 86 kbps = **74 % of link capacity**. Clean `0xAA 0xBB` headers at 107/s: frame `0x01` ≈ 47 Hz, `0x06` ≈ 47 Hz, `0x02` ≈ 12.5 Hz. The 47 Hz confirms the `usart3_send()` busy-wait cap. |
| **COM7** (CH340) @2400…115200 | **No coherent data at any baud.** Zero JustFloat tails. Byte rate scales *linearly* with the baud selected (~20 % duty at every rate) — the signature of a floating RX line, not of a transmitter. Nothing is delivering long-range data to this host. |

**Consequence for moving telemetry to the long-range link:** the existing Frame A/B
stream is **8.6 kB/s**. USART3 at 9600 baud tops out at 960 B/s — **9× too slow**
before the radio's *air* rate is even considered, and air rate is typically well below
UART rate on this class of module. Frame A/B therefore **cannot** simply be re-pointed
at USART3. A selectable variable set with a selectable rate is not a convenience here,
it is the only thing that fits the link — see [[Ground-Station Binary Protocol]] and the
0x07 subscription contract, which already provides the variable-selection half.

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
- [[STM32F4 Peripherals Reference]] — USART async+DMA configuration and DMA stream/channel mapping
