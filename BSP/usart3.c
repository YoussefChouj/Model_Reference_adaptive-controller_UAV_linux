#include "usart3.h"

#define USART3_RXDMA_LEN           22
#define USART3_RXMB_LEN            11

/* USART3_BAUD now lives in usart3.h -- API/subscribe.c needs it to size the
 * stream link-budget guard. */
__IO UCHAR8 UA3RxDMAbuf[USART3_RXDMA_LEN] = {0};
     UCHAR8 UA3RxMailbox[USART3_RXMB_LEN] = {0};
USART_RX_TypeDef USART3_Rcr = {USART3,DMA1_Stream1,UA3RxMailbox,UA3RxDMAbuf,USART3_RXMB_LEN,USART3_RXDMA_LEN,0,0,0};

 UCHAR8 Custom_DataBuf[68] = {0};

/* Long-range-module RX instrumentation. Non-static so livewatch can resolve them
 * by name over SWD. Read-only observation: nothing in the control path consumes
 * these yet, and no command parser is wired to USART3 (see wiki
 * concepts/uart-peripheral-map.md). Watch UA3RxFrameCnt while the ground station
 * transmits to determine empirically whether the module is bidirectional. */
volatile uint32_t UA3RxFrameCnt = 0U;   /* IDLE events that yielded >0 bytes */
volatile uint16_t UA3RxLastLen  = 0U;   /* byte count of the most recent burst */
 
void USART3_Configuration(void)
{

    USART_InitTypeDef usart3;
    GPIO_InitTypeDef  gpio;
    NVIC_InitTypeDef  nvic;
	  DMA_InitTypeDef   DMA_InitStructure;

    RCC_AHB1PeriphClockCmd(RCC_AHB1Periph_GPIOC | RCC_AHB1Periph_DMA1,ENABLE);//ʹ��PA�˿�ʱ��
    RCC_APB1PeriphClockCmd(RCC_APB1Periph_USART3,ENABLE);//ʹ��USART2ʱ��
	

    GPIO_PinAFConfig(GPIOC,GPIO_PinSource10,GPIO_AF_USART3);
    GPIO_PinAFConfig(GPIOC,GPIO_PinSource11,GPIO_AF_USART3); 

	  gpio.GPIO_Pin = GPIO_Pin_10 | GPIO_Pin_11;
	  gpio.GPIO_Mode = GPIO_Mode_AF;//����ģʽ
    gpio.GPIO_OType = GPIO_OType_PP;//�������
    gpio.GPIO_Speed = GPIO_Speed_100MHz;//IO���ٶ�Ϊ100MHz
    gpio.GPIO_PuPd = GPIO_PuPd_NOPULL;
  	GPIO_Init(GPIOC,&gpio);//�����趨������ʼ��GPIOA

	/*USART2���տ����ж�*/
    nvic.NVIC_IRQChannel = USART3_IRQn;
    nvic.NVIC_IRQChannelPreemptionPriority = 0;//��ռ���ȼ�
    nvic.NVIC_IRQChannelSubPriority = 1;//�����ȼ�
    nvic.NVIC_IRQChannelCmd = ENABLE;//IRQͨ��ʹ�� 
    NVIC_Init(&nvic);//����ָ���Ĳ�����ʼ��VIC�Ĵ���
	
	/*DMA��������ж�*/
	  nvic.NVIC_IRQChannel = DMA1_Stream3_IRQn;
    nvic.NVIC_IRQChannelPreemptionPriority = 0;//��ռ���ȼ�
    nvic.NVIC_IRQChannelSubPriority = 7;//�����ȼ�
    nvic.NVIC_IRQChannelCmd = ENABLE;//IRQͨ��ʹ�� 
    NVIC_Init(&nvic);//����ָ���Ĳ�����ʼ��VIC�Ĵ���
    
		USART_DeInit(USART3);
    usart3.USART_BaudRate = USART3_BAUD;//������
    usart3.USART_WordLength = USART_WordLength_8b;//�ֳ�Ϊ8λ���ݸ�ʽ
    usart3.USART_StopBits = USART_StopBits_1;//һ��ֹͣλ
    usart3.USART_Parity = USART_Parity_No;//����żУ��λ
    usart3.USART_Mode = USART_Mode_Tx|USART_Mode_Rx;//�շ�ģʽ
    usart3.USART_HardwareFlowControl = USART_HardwareFlowControl_None;//��Ӳ������������
    USART_Init(USART3,&usart3);//��ʼ������

    USART_ITConfig(USART3,USART_IT_IDLE,ENABLE);//ʹ�ܴ��ڿ����ж�
	  USART_DMACmd(USART3,USART_DMAReq_Rx,ENABLE);
	  USART_DMACmd(USART3,USART_DMAReq_Tx,ENABLE);
	
    USART_Cmd(USART3,ENABLE);//ʹ�ܴ���
	//Rx
	  DMA_DeInit(DMA1_Stream1);
    DMA_InitStructure.DMA_Channel            = DMA_Channel_4;//�����ַ
    DMA_InitStructure.DMA_PeripheralBaseAddr = (uint32_t)&(USART3->DR);//�ڴ��ַ
    DMA_InitStructure.DMA_Memory0BaseAddr    = NULL;
    DMA_InitStructure.DMA_DIR                = DMA_DIR_PeripheralToMemory;//DMA����Ϊ����
    DMA_InitStructure.DMA_BufferSize         = USART3_RXDMA_LEN;//����DMA�ڴ������ĳ���
    DMA_InitStructure.DMA_PeripheralInc      = DMA_PeripheralInc_Disable;
    DMA_InitStructure.DMA_MemoryInc          = DMA_MemoryInc_Enable;
    DMA_InitStructure.DMA_PeripheralDataSize = DMA_PeripheralDataSize_Byte;
    DMA_InitStructure.DMA_MemoryDataSize     = DMA_MemoryDataSize_Byte;
    DMA_InitStructure.DMA_Mode               = DMA_Mode_Circular;
    DMA_InitStructure.DMA_Priority           = DMA_Priority_VeryHigh;
    DMA_InitStructure.DMA_FIFOMode           = DMA_FIFOMode_Disable;
    DMA_InitStructure.DMA_FIFOThreshold      = DMA_FIFOThreshold_Full;
    DMA_InitStructure.DMA_MemoryBurst        = DMA_MemoryBurst_Single;
    DMA_InitStructure.DMA_PeripheralBurst    = DMA_PeripheralBurst_Single;
    /* Overrides the Memory0BaseAddr = NULL set above. The RX stream had no
     * destination address AND was never enabled, so UA3RxDMAbuf was always
     * empty and every byte the long-range module sent was lost. Mirrors the
     * working UART5 RX setup (BSP/usart5.c:84,100). */
    DMA_InitStructure.DMA_Memory0BaseAddr    = (uint32_t)UA3RxDMAbuf;
    DMA_Init(DMA1_Stream1,&DMA_InitStructure);
    DMA_Cmd(DMA1_Stream1,ENABLE);

	//Tx

	  DMA_DeInit(DMA1_Stream3);
    DMA_InitStructure.DMA_Channel            = DMA_Channel_4;               //�����ַ
    DMA_InitStructure.DMA_PeripheralBaseAddr = (uint32_t)&(USART3->DR);
    DMA_InitStructure.DMA_Memory0BaseAddr    = NULL;
    DMA_InitStructure.DMA_DIR                = DMA_DIR_MemoryToPeripheral;  //DMA����Ϊ����
    DMA_InitStructure.DMA_BufferSize         = NULL;            //����DMA�ڴ������ĳ���
    DMA_InitStructure.DMA_PeripheralInc      = DMA_PeripheralInc_Disable;
    DMA_InitStructure.DMA_MemoryInc          = DMA_MemoryInc_Enable;
    DMA_InitStructure.DMA_PeripheralDataSize = DMA_PeripheralDataSize_Byte;
    DMA_InitStructure.DMA_MemoryDataSize     = DMA_MemoryDataSize_Byte;
    DMA_InitStructure.DMA_Mode               = DMA_Mode_Normal;//
    DMA_InitStructure.DMA_Priority           = DMA_Priority_VeryHigh;
    DMA_InitStructure.DMA_FIFOMode           = DMA_FIFOMode_Disable;
    DMA_InitStructure.DMA_FIFOThreshold      = DMA_FIFOThreshold_Full;
    DMA_InitStructure.DMA_MemoryBurst        = DMA_MemoryBurst_Single;
    DMA_InitStructure.DMA_PeripheralBurst    = DMA_PeripheralBurst_Single;
    DMA_Init(DMA1_Stream3,&DMA_InitStructure);

    DMA_ITConfig(DMA1_Stream3,DMA_IT_TC,ENABLE);//�����ж�ʹ��
		
    DMA_Cmd(DMA1_Stream3,DISABLE);
}


//	//Rx
//	  DMA_DeInit(DMA1_Stream1);
//    DMA_InitStructure.DMA_Channel            = DMA_Channel_4;//�����ַ
//    DMA_InitStructure.DMA_PeripheralBaseAddr = (uint32_t)&(USART3->DR);//�ڴ��ַ
//    DMA_InitStructure.DMA_Memory0BaseAddr    = NULL;
//    DMA_InitStructure.DMA_DIR                = DMA_DIR_PeripheralToMemory;//DMA����Ϊ����
//    DMA_InitStructure.DMA_BufferSize         = NULL;//����DMA�ڴ������ĳ���
//    DMA_InitStructure.DMA_PeripheralInc      = DMA_PeripheralInc_Disable;
//    DMA_InitStructure.DMA_MemoryInc          = DMA_MemoryInc_Enable;
//    DMA_InitStructure.DMA_PeripheralDataSize = DMA_PeripheralDataSize_Byte;
//    DMA_InitStructure.DMA_MemoryDataSize     = DMA_MemoryDataSize_Byte;
//    DMA_InitStructure.DMA_Mode               = DMA_Mode_Circular;
//    DMA_InitStructure.DMA_Priority           = DMA_Priority_VeryHigh;
//    DMA_InitStructure.DMA_FIFOMode           = DMA_FIFOMode_Disable;
//    DMA_InitStructure.DMA_FIFOThreshold      = DMA_FIFOThreshold_Full;
//    DMA_InitStructure.DMA_MemoryBurst        = DMA_MemoryBurst_Single;
//    DMA_InitStructure.DMA_PeripheralBurst    = DMA_PeripheralBurst_Single;
//    DMA_Init(DMA1_Stream1,&DMA_InitStructure);
//	
//	//Tx
//		DMA_InitTypeDef		dma;
//	  DMA_DeInit(DMA1_Stream3);
//    DMA_InitStructure.DMA_Channel            = DMA_Channel_4;               //�����ַ
//    DMA_InitStructure.DMA_PeripheralBaseAddr = (uint32_t)&(USART3->DR);
//    DMA_InitStructure.DMA_Memory0BaseAddr    = NULL;
//    DMA_InitStructure.DMA_DIR                = DMA_DIR_MemoryToPeripheral;  //DMA����Ϊ����
//    DMA_InitStructure.DMA_BufferSize         = NULL;            //����DMA�ڴ������ĳ���
//    DMA_InitStructure.DMA_PeripheralInc      = DMA_PeripheralInc_Disable;
//    DMA_InitStructure.DMA_MemoryInc          = DMA_MemoryInc_Enable;
//    DMA_InitStructure.DMA_PeripheralDataSize = DMA_PeripheralDataSize_Byte;
//    DMA_InitStructure.DMA_MemoryDataSize     = DMA_MemoryDataSize_Byte;
//    DMA_InitStructure.DMA_Mode               = DMA_Mode_Normal;
//    DMA_InitStructure.DMA_Priority           = DMA_Priority_VeryHigh;
//    DMA_InitStructure.DMA_FIFOMode           = DMA_FIFOMode_Disable;
//    DMA_InitStructure.DMA_FIFOThreshold      = DMA_FIFOThreshold_Full;
//    DMA_InitStructure.DMA_MemoryBurst        = DMA_MemoryBurst_Single;
//    DMA_InitStructure.DMA_PeripheralBurst    = DMA_PeripheralBurst_Single;
//    DMA_Init(DMA1_Stream3,&DMA_InitStructure);

//    //DMA_ITConfig(DMA1_Stream3,DMA_IT_TC,ENABLE);
//		DMA_Init(DMA1_Stream3, &dma);
//		//DMA_ITConfig(DMA1_Stream1,DMA_IT_TC,ENABLE);
//    DMA_Cmd(DMA1_Stream3,DISABLE);
//		//DMA_Cmd(DMA1_Stream1,ENABLE);//�Ƚ��ã��ò���



/* ---- 0x09 subscribe data stream (API/subscribe.c) -----------------------
 * Shares DMA1_Stream3 with usart3_send(). Only one of them may drive the
 * stream at a time; Subscribe_StreamOwnsUsart3() is what stands usart3_send()
 * down while a subscription is running.
 *
 * Deliberately skip-if-busy rather than wait-if-busy. The busy-wait this file
 * used to contain is exactly what pinned Send_Task to 60 Hz (16 B at 9600 baud
 * = 16.7 ms of blocking per cycle); at a 1 kB frame the same pattern would
 * block for ~89 ms at 115200 and stall the whole telemetry task. A skipped
 * frame costs one sequence number, which the host can see and count. */
uint8_t Usart3_Stream_Busy(void)
{
    return (DMA_GetCurrDataCounter(DMA1_Stream3) != 0U) ? 1U : 0U;
}

uint8_t Usart3_Stream_TxSend(const uint8_t* buf, uint16_t len)
{
    if ((buf == 0) || (len == 0U))
    {
        return 0U;
    }
    if (DMA_GetCurrDataCounter(DMA1_Stream3) != 0U)
    {
        return 0U;                    /* previous frame still draining */
    }
    DMA_Cmd(DMA1_Stream3, DISABLE);
    while (DMA_GetCmdStatus(DMA1_Stream3) == ENABLE);
    /* Clear HTIF3/FEIF3 as well as TCIF3. The legacy path clears only TCIF3,
     * which leaves the other flags latched in LISR forever. */
    DMA_ClearFlag(DMA1_Stream3, DMA_FLAG_TCIF3 | DMA_FLAG_HTIF3 | DMA_FLAG_TEIF3
                              | DMA_FLAG_DMEIF3 | DMA_FLAG_FEIF3);
    DMA1_Stream3->M0AR = (uint32_t)buf;
    DMA1_Stream3->NDTR = len;
    DMA_Cmd(DMA1_Stream3, ENABLE);
    return 1U;
}
