#ifndef  __USART3_H__
#define  __USART3_H__

#include "stm32f4xx.h"
#include "main.h"

/* UART baud toward the long-range radio module. HARDWARE REPLACED 2026-07-31: the
 * 24RF/nRF24L01 pair is gone; USART3 now drives a 2.4 GHz BLE serial module (Yuanxi),
 * configured to 921600 on BOTH ends with its Windows tool. The old 115200 figure and
 * the "no AT command can change the baud" conclusion belonged to the retired hardware.
 *
 * MEASURED 2026-07-31, not guessed: USART3->BRR was swept live over SWD while the
 * ground dongle was captured. Only at 921600 does the payload survive -- 218 distinct
 * byte values and the full 59-float test ramp verbatim; every lower rate collapses the
 * stream to 1-2 distinct byte values and zero tails.
 *
 * APB1 is 42 MHz, so 921600 is not exactly representable: BRR = 0x2E gives 913043 baud,
 * -0.93%. Well inside 8N1 tolerance (~2%) and confirmed working on the wire.
 *
 * Lives in the header (not usart3.c) because API/subscribe.c sizes its stream
 * link-budget guard from it. NOTE: that guard now permits ~18 kB/s, but the radio's
 * MEASURED air throughput is only ~4.7 kB/s -- the UART is no longer the binding
 * constraint, so the budget guard is optimistic. See USART3_TEST_FLOATS in
 * TASK/send_data.c. */
#define USART3_BAUD                921600

void USART3_Configuration(void);
extern UCHAR8 Custom_DataBuf[68];

/* Non-blocking DMA1_Stream3 hand-off for the 0x09 subscribe data stream.
 * Returns 1 if the transfer was armed, 0 if the previous one is still
 * draining (caller must then skip this frame rather than rebuild the buffer
 * underneath the DMA). Unlike Uart5_Subscribe_TxSend this never busy-waits:
 * Send_Task must not block on the radio. */
uint8_t Usart3_Stream_TxSend(const uint8_t* buf, uint16_t len);

/* 1 while DMA1_Stream3 still has bytes to push. */
uint8_t Usart3_Stream_Busy(void);
#endif
