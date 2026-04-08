#include "usart4.h"

_linux_data_st linux_data;
yolo_data linux_yolo_data;
//PA0  TX
//PA1  RX
UCHAR8 UA4RxDMAbuf[UART4_RXDMA_LEN] = {0};
UCHAR8 UA4RxMailbox[UART4_RXMB_LEN] = {0};
USART_RX_TypeDef UART4_Rcr = {UART4,UART4_RX_STREAM,UA4RxMailbox,UA4RxDMAbuf,UART4_RXMB_LEN,UART4_RXDMA_LEN,0,0,0};
void UART4_Configuration(void)  
{
	USART_InitTypeDef uart4;
	GPIO_InitTypeDef  gpio;
	NVIC_InitTypeDef  nvic;
	DMA_InitTypeDef   DMA_InitStructure;

	RCC_AHB1PeriphClockCmd(RCC_AHB1Periph_GPIOA | RCC_AHB1Periph_DMA1,ENABLE);//使能PC端口时钟
	RCC_APB1PeriphClockCmd(RCC_APB1Periph_UART4,ENABLE);//使能UART4时钟

	GPIO_PinAFConfig(GPIOA,GPIO_PinSource0,GPIO_AF_UART4); 
	GPIO_PinAFConfig(GPIOA,GPIO_PinSource1,GPIO_AF_UART4); 

	gpio.GPIO_Pin = GPIO_Pin_0|GPIO_Pin_1;
	gpio.GPIO_Mode = GPIO_Mode_AF;//复用模式
	gpio.GPIO_OType = GPIO_OType_PP;//推挽输出
	gpio.GPIO_Speed = GPIO_Speed_100MHz;//IO口速度为50MHz
	gpio.GPIO_PuPd = GPIO_PuPd_UP;//上拉
	GPIO_Init(GPIOA,&gpio);//根据设定参数初始化GPIOC

	nvic.NVIC_IRQChannel = UART4_IRQn;
	nvic.NVIC_IRQChannelPreemptionPriority = 0;//抢占优先级
	nvic.NVIC_IRQChannelSubPriority = 0;//子优先级
	nvic.NVIC_IRQChannelCmd = ENABLE;//IRQ通道使能 
	NVIC_Init(&nvic);//根据指定的参数初始化VIC寄存器

	uart4.USART_BaudRate = 115200;//波特率
	uart4.USART_WordLength = USART_WordLength_8b;//字长为8位数据格式
	uart4.USART_StopBits = USART_StopBits_1;//一个停止位
	uart4.USART_Parity = USART_Parity_No;//无奇偶校验位
	uart4.USART_Mode = USART_Mode_Rx|USART_Mode_Tx;//仅接收
	uart4.USART_HardwareFlowControl = USART_HardwareFlowControl_None;//无硬件数据流控制
	USART_Init(UART4,&uart4);//初始化串口

	USART_DMACmd(UART4,USART_DMAReq_Rx,ENABLE);
	USART_DMACmd(UART4,USART_DMAReq_Tx,ENABLE);
	USART_ITConfig(UART4,USART_IT_IDLE,ENABLE); //开启空闲中断

	USART_Cmd(UART4,ENABLE);//使能串口

	DMA_DeInit(DMA1_Stream2);
	DMA_InitStructure.DMA_Channel= DMA_Channel_4;//通道
	DMA_InitStructure.DMA_PeripheralBaseAddr = (uint32_t)&(UART4->DR);//外设地址
	DMA_InitStructure.DMA_Memory0BaseAddr = (uint32_t)UA4RxDMAbuf;//将串口4接收到的数据ucRxData_DMA1_Stream2[]里，内存基地址
	DMA_InitStructure.DMA_DIR = DMA_DIR_PeripheralToMemory;//设置数据传输方向
	DMA_InitStructure.DMA_BufferSize = UART4_RXDMA_LEN;//设置DMA一次传输数据量的大小
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
	DMA_Init(DMA1_Stream2,&DMA_InitStructure);

	//DMA_ITConfig(DMA1_Stream2,DMA_IT_TC,ENABLE);
	DMA_Cmd(DMA1_Stream2,ENABLE);

	/////////////////////////TX
	DMA_InitTypeDef		dma;
	DMA_DeInit(DMA1_Stream4);
	while( DMA_GetCmdStatus(DMA1_Stream4) == ENABLE );			//等待DMA可配置

	dma.DMA_Channel				=	DMA_Channel_4;
	dma.DMA_PeripheralBaseAddr	=	(uint32_t)&(UART4->DR);
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
	DMA_Init(DMA1_Stream4, &dma);
	DMA_Cmd(DMA1_Stream4, DISABLE);
}

typedef struct { uint8_t id; uint8_t index; float value; } GS_Cmd_t;
volatile GS_Cmd_t gs_cmd_queue[8];
volatile uint8_t gs_cmd_head = 0, gs_cmd_tail = 0;

void Handle_UART4_GroundStation_Command(void)
{
    // The DMA mailbox has the latest data.
    // Format: [0xCC] [0xDD] [CMD_ID: uint8] [INDEX: uint8] [VALUE: float32 LE] [CRC8]
    // Total 9 bytes.
    
    // For 9 bytes, we only care if the first bytes match
    if (UA4RxMailbox[0] == 0xCC && UA4RxMailbox[1] == 0xDD)
    {
        uint8_t cmd_id = UA4RxMailbox[2];
        uint8_t index = UA4RxMailbox[3];
        
        union {
            float f;
            uint8_t b[4];
        } val;
        
        val.b[0] = UA4RxMailbox[4];
        val.b[1] = UA4RxMailbox[5];
        val.b[2] = UA4RxMailbox[6];
        val.b[3] = UA4RxMailbox[7];
        
        uint8_t crc = UA4RxMailbox[8];
        uint8_t calc_crc = 0;
        int i;
        
        for (i = 2; i < 8; i++) {
            calc_crc ^= UA4RxMailbox[i];
        }
        
        if (calc_crc == crc) {
            gs_cmd_queue[gs_cmd_head].id = cmd_id;
            gs_cmd_queue[gs_cmd_head].index = index;
            gs_cmd_queue[gs_cmd_head].value = val.f;
            
            // Advance head (mod 8)
            gs_cmd_head = (gs_cmd_head + 1) % 8;
        }
    }
}
