#ifndef  __USART3_H__
#define  __USART3_H__

#include "stm32f4xx.h"
#include "main.h"

/* UART baud toward the long-range radio module (DevEBox 24RF_COM V1.0 on the drone,
 * USB_24RF Ver 3.1 dongle on the ground). MEASURED 2026-07-26, not guessed: the FC's
 * USART3->BRR was swept live over SWD while the ground dongle was captured at 115200.
 * At 115200 the JustFloat frames arrive intact -- 255/256 tails at exact 16-byte
 * stride, 1293 B/s = 80.8 frame/s, decoding to plausible attitude. At 9600/19200/
 * 38400/57600 the same capture yields zero tails and only mis-framed bytes.
 * So the module pair is configured for 115200 on both ends; at the previous 9600 the
 * drone-side unit never assembled a valid packet and transmitted nothing at all.
 *
 * Lives in the header (not usart3.c) because API/subscribe.c sizes its stream
 * link-budget guard from it. Raise this to match the module after reconfiguring
 * BOTH ends of the radio pair. */
#define USART3_BAUD                115200

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
