#ifndef  __USART5_H__
#define  __USART5_H__

#include "stm32f4xx.h"
#include "main.h"

/*串口5通信缓冲长度*/
#define UART5_RX_STREAM         DMA1_Stream0
#define UART5_TX_STREAM         DMA1_Stream7
#define USART5_RXDMA_LEN           56
#define USART5_RXMB_LEN            28

void UART5_Configuration(void);
extern UCHAR8 UA5RxDMAbuf[USART5_RXDMA_LEN] ;
extern UCHAR8 UA5RxMailbox[USART5_RXMB_LEN] ;
extern USART_RX_TypeDef UART5_Rcr;
#endif
