#ifndef  __USART5_H__
#define  __USART5_H__

#include "stm32f4xx.h"
#include "main.h"

/*����5ͨ�Ż��峤��*/
#define UART5_RX_STREAM         DMA1_Stream0
#define UART5_TX_STREAM         DMA1_Stream7
#define USART5_RXDMA_LEN           128
#define USART5_RXMB_LEN            128

void UART5_Configuration(void);
void Handle_UART5_GroundStation_Command(void);
extern UCHAR8 UA5RxDMAbuf[USART5_RXDMA_LEN] ;
extern UCHAR8 UA5RxMailbox[USART5_RXMB_LEN] ;
extern USART_RX_TypeDef UART5_Rcr;
#endif
