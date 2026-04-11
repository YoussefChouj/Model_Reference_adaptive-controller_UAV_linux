#include "usart5.h"

//   rx pd2  
//   tx pc12

UCHAR8 UA5RxDMAbuf[USART5_RXDMA_LEN] = {0};
UCHAR8 UA5RxMailbox[USART5_RXMB_LEN] = {0};
USART_RX_TypeDef UART5_Rcr = {UART5,UART5_RX_STREAM,UA5RxMailbox,UA5RxDMAbuf,USART5_RXMB_LEN,USART5_RXDMA_LEN,0,0,0};

void UART5_Configuration(void)
{
		USART_InitTypeDef uart5;
		GPIO_InitTypeDef  GPIO_InitStructure;
		NVIC_InitTypeDef  nvic;
		DMA_InitTypeDef   DMA_InitStructure;

		RCC_AHB1PeriphClockCmd( RCC_AHB1Periph_DMA1,ENABLE);//使能PC端口时钟
	  RCC_APB1PeriphClockCmd(RCC_APB1Periph_UART5, ENABLE); //开启USART2时钟
    RCC_AHB1PeriphClockCmd(RCC_AHB1Periph_GPIOC, ENABLE);
    RCC_AHB1PeriphClockCmd(RCC_AHB1Periph_GPIOD, ENABLE);

		GPIO_PinAFConfig(GPIOC,GPIO_PinSource12,GPIO_AF_UART5); 
		GPIO_PinAFConfig(GPIOD,GPIO_PinSource2,GPIO_AF_UART5); 

    //配置PC12作为UART5　Tx
    GPIO_InitStructure.GPIO_Pin = GPIO_Pin_12;
    GPIO_InitStructure.GPIO_Mode = GPIO_Mode_AF;
    GPIO_InitStructure.GPIO_Speed = GPIO_Speed_50MHz;
    GPIO_InitStructure.GPIO_OType = GPIO_OType_PP;
    GPIO_InitStructure.GPIO_PuPd = GPIO_PuPd_UP;
    GPIO_Init(GPIOC, &GPIO_InitStructure);
    //配置PD2作为UART5　Rx
    GPIO_InitStructure.GPIO_Pin = GPIO_Pin_2;
    GPIO_InitStructure.GPIO_Mode = GPIO_Mode_AF;
    GPIO_InitStructure.GPIO_Speed = GPIO_Speed_50MHz;
    GPIO_InitStructure.GPIO_OType = GPIO_OType_OD;
    GPIO_InitStructure.GPIO_PuPd = GPIO_PuPd_NOPULL;
    GPIO_Init(GPIOD, &GPIO_InitStructure);


		nvic.NVIC_IRQChannel = UART5_IRQn;
		nvic.NVIC_IRQChannelPreemptionPriority = 2;//抢占优先级
		nvic.NVIC_IRQChannelSubPriority = 0;//子优先级
		nvic.NVIC_IRQChannelCmd = ENABLE;//IRQ通道使能 
		NVIC_Init(&nvic);//根据指定的参数初始化VIC寄存器

		uart5.USART_BaudRate = 115200;//波特率 (ground station)
		uart5.USART_WordLength = USART_WordLength_8b;//字长为8位数据格式
		uart5.USART_StopBits = USART_StopBits_1;//一个停止位
		uart5.USART_Parity = USART_Parity_No;//无奇偶校验位
		uart5.USART_Mode = USART_Mode_Rx|USART_Mode_Tx;//仅接收
		uart5.USART_HardwareFlowControl = USART_HardwareFlowControl_None;//无硬件数据流控制
		USART_Init(UART5,&uart5);//初始化串口

		USART_DMACmd(UART5,USART_DMAReq_Rx,ENABLE);
		USART_DMACmd(UART5,USART_DMAReq_Tx,ENABLE);
		USART_ITConfig(UART5,USART_IT_IDLE,ENABLE); //开启空闲中断

		USART_Cmd(UART5,ENABLE);//使能串口

		DMA_DeInit(DMA1_Stream0);
		DMA_InitStructure.DMA_Channel= DMA_Channel_4;//通道
		DMA_InitStructure.DMA_PeripheralBaseAddr = (uint32_t)&(UART5->DR);//外设地址
		DMA_InitStructure.DMA_Memory0BaseAddr = (uint32_t)UA5RxDMAbuf;//将串口4接收到的数据ucRxData_DMA1_Stream2[]里，内存基地址
		DMA_InitStructure.DMA_DIR = DMA_DIR_PeripheralToMemory;//设置数据传输方向
		DMA_InitStructure.DMA_BufferSize = USART5_RXDMA_LEN;//设置DMA一次传输数据量的大小
		DMA_InitStructure.DMA_PeripheralInc = DMA_PeripheralInc_Disable;//设置外设地址不变
		DMA_InitStructure.DMA_MemoryInc = DMA_MemoryInc_Enable;	//设置内存地址递增
		DMA_InitStructure.DMA_PeripheralDataSize = DMA_PeripheralDataSize_Byte;//设置外设的数据长度为字节（8bits）
		DMA_InitStructure.DMA_MemoryDataSize = DMA_MemoryDataSize_Byte;//设置内存的数据长度为字节（8bits）
		DMA_InitStructure.DMA_Mode = DMA_Mode_Circular;//DMA_Mode_Normal;////设置DMA模式为循环模式
		DMA_InitStructure.DMA_Priority = DMA_Priority_VeryHigh;//DMA_Priority_Medium;//设置DMA通道的优先级为最高优先级
		DMA_InitStructure.DMA_FIFOMode = DMA_FIFOMode_Disable;
		DMA_InitStructure.DMA_FIFOThreshold = DMA_FIFOThreshold_Full;
		DMA_InitStructure.DMA_MemoryBurst = DMA_MemoryBurst_Single;
		DMA_InitStructure.DMA_PeripheralBurst = DMA_PeripheralBurst_Single;
		DMA_Init(DMA1_Stream0,&DMA_InitStructure);

		//DMA_ITConfig(DMA1_Stream2,DMA_IT_TC,ENABLE);
		DMA_Cmd(DMA1_Stream0,ENABLE);

		/////////////////////////TX
		DMA_InitTypeDef		dma;
		DMA_DeInit(DMA1_Stream7);
		while( DMA_GetCmdStatus(DMA1_Stream7) == ENABLE );			//等待DMA可配置

		dma.DMA_Channel				=	DMA_Channel_4;
		dma.DMA_PeripheralBaseAddr	=	(uint32_t)&(UART5->DR);
		dma.DMA_Memory0BaseAddr		=	NULL;//暂无
		dma.DMA_DIR					=	DMA_DIR_MemoryToPeripheral;	//内存到外设
		dma.DMA_BufferSize			=	NULL;//暂无
		dma.DMA_PeripheralInc		=	DMA_PeripheralInc_Disable;
		dma.DMA_MemoryInc			=	DMA_MemoryInc_Enable;
		dma.DMA_PeripheralDataSize	=	DMA_PeripheralDataSize_Byte;
		dma.DMA_MemoryDataSize		=	DMA_MemoryDataSize_Byte;
		dma.DMA_Mode				=	DMA_Mode_Normal;			//正常发送
		dma.DMA_Priority			=	DMA_Priority_VeryHigh;
		dma.DMA_FIFOMode			=	DMA_FIFOMode_Disable;
		dma.DMA_FIFOThreshold		=	DMA_FIFOThreshold_1QuarterFull;
		dma.DMA_MemoryBurst			=	DMA_MemoryBurst_Single;
		dma.DMA_PeripheralBurst		=	DMA_PeripheralBurst_Single;
		DMA_Init(DMA1_Stream7, &dma);
		DMA_Cmd(DMA1_Stream7, DISABLE);
}

typedef struct { uint8_t id; uint8_t index; float value; } GS_Cmd_t;
extern volatile GS_Cmd_t gs_cmd_queue[8];
extern volatile uint8_t gs_cmd_head;
extern volatile uint8_t gs_cmd_tail;
extern volatile uint32_t gs_cmd_drop_count;

void Handle_UART5_GroundStation_Command(void)
{
	// Format: [0xCC] [0xDD] [CMD_ID: uint8] [INDEX: uint8] [VALUE: float32 LE] [CRC8]
	// Total frame length is 9 bytes.
	if (UA5RxMailbox[0] == 0xCC && UA5RxMailbox[1] == 0xDD)
	{
		uint8_t cmd_id = UA5RxMailbox[2];
		uint8_t index = UA5RxMailbox[3];

		union {
			float f;
			uint8_t b[4];
		} val;

		val.b[0] = UA5RxMailbox[4];
		val.b[1] = UA5RxMailbox[5];
		val.b[2] = UA5RxMailbox[6];
		val.b[3] = UA5RxMailbox[7];

		{
			uint8_t crc = UA5RxMailbox[8];
			uint8_t calc_crc = 0;
			int i;
			for (i = 2; i < 8; i++) {
				calc_crc ^= UA5RxMailbox[i];
			}

			if (calc_crc == crc) {
				uint8_t next_head = (uint8_t)((gs_cmd_head + 1U) % 8U);
				if (next_head != gs_cmd_tail) {
					gs_cmd_queue[gs_cmd_head].id = cmd_id;
					gs_cmd_queue[gs_cmd_head].index = index;
					gs_cmd_queue[gs_cmd_head].value = val.f;
					gs_cmd_head = next_head;
				} else {
					gs_cmd_drop_count++;
				}
			}
		}
	}
}
