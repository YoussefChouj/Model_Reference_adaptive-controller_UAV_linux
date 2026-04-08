#include "usart3.h"

#define USART3_RXDMA_LEN           22
#define USART3_RXMB_LEN            11
__IO UCHAR8 UA3RxDMAbuf[USART3_RXDMA_LEN] = {0};
     UCHAR8 UA3RxMailbox[USART3_RXMB_LEN] = {0};
USART_RX_TypeDef USART3_Rcr = {USART3,DMA1_Stream1,UA3RxMailbox,UA3RxDMAbuf,USART3_RXMB_LEN,USART3_RXDMA_LEN,0,0,0};

 UCHAR8 Custom_DataBuf[68] = {0};
 
void USART3_Configuration(void)
{

    USART_InitTypeDef usart3;
    GPIO_InitTypeDef  gpio;
    NVIC_InitTypeDef  nvic;
	  DMA_InitTypeDef   DMA_InitStructure;

    RCC_AHB1PeriphClockCmd(RCC_AHB1Periph_GPIOC | RCC_AHB1Periph_DMA1,ENABLE);//使能PA端口时钟
    RCC_APB1PeriphClockCmd(RCC_APB1Periph_USART3,ENABLE);//使能USART2时钟
	

    GPIO_PinAFConfig(GPIOC,GPIO_PinSource10,GPIO_AF_USART3);
    GPIO_PinAFConfig(GPIOC,GPIO_PinSource11,GPIO_AF_USART3); 

	  gpio.GPIO_Pin = GPIO_Pin_10 | GPIO_Pin_11;
	  gpio.GPIO_Mode = GPIO_Mode_AF;//复用模式
    gpio.GPIO_OType = GPIO_OType_PP;//推挽输出
    gpio.GPIO_Speed = GPIO_Speed_100MHz;//IO口速度为100MHz
    gpio.GPIO_PuPd = GPIO_PuPd_NOPULL;
  	GPIO_Init(GPIOC,&gpio);//根据设定参数初始化GPIOA

	/*USART2接收空闲中断*/
    nvic.NVIC_IRQChannel = USART3_IRQn;
    nvic.NVIC_IRQChannelPreemptionPriority = 0;//抢占优先级
    nvic.NVIC_IRQChannelSubPriority = 1;//子优先级
    nvic.NVIC_IRQChannelCmd = ENABLE;//IRQ通道使能 
    NVIC_Init(&nvic);//根据指定的参数初始化VIC寄存器
	
	/*DMA发送完成中断*/
	  nvic.NVIC_IRQChannel = DMA1_Stream3_IRQn;
    nvic.NVIC_IRQChannelPreemptionPriority = 0;//抢占优先级
    nvic.NVIC_IRQChannelSubPriority = 7;//子优先级
    nvic.NVIC_IRQChannelCmd = ENABLE;//IRQ通道使能 
    NVIC_Init(&nvic);//根据指定的参数初始化VIC寄存器
    
		USART_DeInit(USART3);
    usart3.USART_BaudRate = 9600;//波特率
    usart3.USART_WordLength = USART_WordLength_8b;//字长为8位数据格式
    usart3.USART_StopBits = USART_StopBits_1;//一个停止位
    usart3.USART_Parity = USART_Parity_No;//无奇偶校验位
    usart3.USART_Mode = USART_Mode_Tx|USART_Mode_Rx;//收发模式
    usart3.USART_HardwareFlowControl = USART_HardwareFlowControl_None;//无硬件数据流控制
    USART_Init(USART3,&usart3);//初始化串口

    USART_ITConfig(USART3,USART_IT_IDLE,ENABLE);//使能串口空闲中断
	  USART_DMACmd(USART3,USART_DMAReq_Rx,ENABLE);
	  USART_DMACmd(USART3,USART_DMAReq_Tx,ENABLE);
	
    USART_Cmd(USART3,ENABLE);//使能串口
	//Rx
	  DMA_DeInit(DMA1_Stream1);
    DMA_InitStructure.DMA_Channel            = DMA_Channel_4;//外设地址
    DMA_InitStructure.DMA_PeripheralBaseAddr = (uint32_t)&(USART3->DR);//内存地址
    DMA_InitStructure.DMA_Memory0BaseAddr    = NULL;
    DMA_InitStructure.DMA_DIR                = DMA_DIR_PeripheralToMemory;//DMA传输为单向
    DMA_InitStructure.DMA_BufferSize         = USART3_RXDMA_LEN;//设置DMA在传输区的长度
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
    DMA_Init(DMA1_Stream1,&DMA_InitStructure);
	
	//Tx

	  DMA_DeInit(DMA1_Stream3);
    DMA_InitStructure.DMA_Channel            = DMA_Channel_4;               //外设地址
    DMA_InitStructure.DMA_PeripheralBaseAddr = (uint32_t)&(USART3->DR);
    DMA_InitStructure.DMA_Memory0BaseAddr    = NULL;
    DMA_InitStructure.DMA_DIR                = DMA_DIR_MemoryToPeripheral;  //DMA传输为单向
    DMA_InitStructure.DMA_BufferSize         = NULL;            //设置DMA在传输区的长度
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

    DMA_ITConfig(DMA1_Stream3,DMA_IT_TC,ENABLE);//发送中断使能
		
    DMA_Cmd(DMA1_Stream3,DISABLE);
}


//	//Rx
//	  DMA_DeInit(DMA1_Stream1);
//    DMA_InitStructure.DMA_Channel            = DMA_Channel_4;//外设地址
//    DMA_InitStructure.DMA_PeripheralBaseAddr = (uint32_t)&(USART3->DR);//内存地址
//    DMA_InitStructure.DMA_Memory0BaseAddr    = NULL;
//    DMA_InitStructure.DMA_DIR                = DMA_DIR_PeripheralToMemory;//DMA传输为单向
//    DMA_InitStructure.DMA_BufferSize         = NULL;//设置DMA在传输区的长度
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
//    DMA_InitStructure.DMA_Channel            = DMA_Channel_4;               //外设地址
//    DMA_InitStructure.DMA_PeripheralBaseAddr = (uint32_t)&(USART3->DR);
//    DMA_InitStructure.DMA_Memory0BaseAddr    = NULL;
//    DMA_InitStructure.DMA_DIR                = DMA_DIR_MemoryToPeripheral;  //DMA传输为单向
//    DMA_InitStructure.DMA_BufferSize         = NULL;            //设置DMA在传输区的长度
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
//		//DMA_Cmd(DMA1_Stream1,ENABLE);//先禁用，用不到

