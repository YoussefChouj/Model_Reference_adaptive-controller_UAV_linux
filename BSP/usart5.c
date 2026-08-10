#include "usart5.h"
#include "subscribe.h"   /* SUBSCRIBE_CMD / SUBSCRIBE_STREAM_CMD payload shapes */

/**
 * @module  usart5.c
 * @subsystem  comm
 * @depends  usart5.h, subscribe.h
 * @owns  UART5 DMA setup and UART5 ground-station command ingress
 * @caution  command frame parsing must stay byte-compatible with host serializer and UART4 ingress path
 */

//   rx pd2  
//   tx pc12

UCHAR8 UA5RxDMAbuf[USART5_RXDMA_LEN] = {0};
UCHAR8 UA5RxMailbox[USART5_RXMB_LEN] = {0};
/* UART5 extended-prefix (0xCC 0xDE) subscribe request staging buffer. File-scope:
 * Send_Task stack is 500 words / 2 kB; the largest legal request is
 * 6 (header) + 32 * 6 (tuples) + 1 (CRC) = 199 B, too big for any stack local.
 * `UA5RxSubscribeLen` is set by the IRQ-side parser when a complete 0xCC 0xDE
 * frame lands; Send_Task picks it up off the back of the UART5 DMA hand-off in
 * TASK/send_data.c. */
UCHAR8 UA5RxSubscribeBuf[USART5_SUBSCRIBE_RX_LEN] = {0};
uint16_t UA5RxSubscribeLen = 0U;
/* Set by the IRQ-side parser when a complete, CRC-valid 0xCC 0xDE subscribe
 * request lands. Cleared by Send_Task after the reply DMA completes (or by
 * the validator if the request is rejected with a 0x7F error reply). */
volatile uint8_t UA5RxSubscribePending = 0U;
USART_RX_TypeDef UART5_Rcr = {UART5,UART5_RX_STREAM,UA5RxMailbox,UA5RxDMAbuf,USART5_RXMB_LEN,USART5_RXDMA_LEN,0,0,0};

void UART5_Configuration(void)
{
		USART_InitTypeDef uart5;
		GPIO_InitTypeDef  GPIO_InitStructure;
		NVIC_InitTypeDef  nvic;
		DMA_InitTypeDef   DMA_InitStructure;

		RCC_AHB1PeriphClockCmd( RCC_AHB1Periph_DMA1,ENABLE);//ʹ��PC�˿�ʱ��
	  RCC_APB1PeriphClockCmd(RCC_APB1Periph_UART5, ENABLE); //����USART2ʱ��
    RCC_AHB1PeriphClockCmd(RCC_AHB1Periph_GPIOC, ENABLE);
    RCC_AHB1PeriphClockCmd(RCC_AHB1Periph_GPIOD, ENABLE);

		GPIO_PinAFConfig(GPIOC,GPIO_PinSource12,GPIO_AF_UART5); 
		GPIO_PinAFConfig(GPIOD,GPIO_PinSource2,GPIO_AF_UART5); 

    //����PC12��ΪUART5��Tx
    GPIO_InitStructure.GPIO_Pin = GPIO_Pin_12;
    GPIO_InitStructure.GPIO_Mode = GPIO_Mode_AF;
    GPIO_InitStructure.GPIO_Speed = GPIO_Speed_50MHz;
    GPIO_InitStructure.GPIO_OType = GPIO_OType_PP;
    GPIO_InitStructure.GPIO_PuPd = GPIO_PuPd_UP;
    GPIO_Init(GPIOC, &GPIO_InitStructure);
    //����PD2��ΪUART5��Rx
    GPIO_InitStructure.GPIO_Pin = GPIO_Pin_2;
    GPIO_InitStructure.GPIO_Mode = GPIO_Mode_AF;
    GPIO_InitStructure.GPIO_Speed = GPIO_Speed_50MHz;
    GPIO_InitStructure.GPIO_OType = GPIO_OType_OD;
    GPIO_InitStructure.GPIO_PuPd = GPIO_PuPd_NOPULL;
    GPIO_Init(GPIOD, &GPIO_InitStructure);


		nvic.NVIC_IRQChannel = UART5_IRQn;
		nvic.NVIC_IRQChannelPreemptionPriority = 2;//��ռ���ȼ�
		nvic.NVIC_IRQChannelSubPriority = 0;//�����ȼ�
		nvic.NVIC_IRQChannelCmd = ENABLE;//IRQͨ��ʹ�� 
		NVIC_Init(&nvic);//����ָ���Ĳ�����ʼ��VIC�Ĵ���

		uart5.USART_BaudRate = 115200;//������ (ground station)
		uart5.USART_WordLength = USART_WordLength_8b;//�ֳ�Ϊ8λ���ݸ�ʽ
		uart5.USART_StopBits = USART_StopBits_1;//һ��ֹͣλ
		uart5.USART_Parity = USART_Parity_No;//����żУ��λ
		uart5.USART_Mode = USART_Mode_Rx|USART_Mode_Tx;//������
		uart5.USART_HardwareFlowControl = USART_HardwareFlowControl_None;//��Ӳ������������
		USART_Init(UART5,&uart5);//��ʼ������

		USART_DMACmd(UART5,USART_DMAReq_Rx,ENABLE);
		USART_DMACmd(UART5,USART_DMAReq_Tx,ENABLE);
		USART_ITConfig(UART5,USART_IT_IDLE,ENABLE); //���������ж�

		USART_Cmd(UART5,ENABLE);//ʹ�ܴ���

		DMA_DeInit(DMA1_Stream0);
		DMA_InitStructure.DMA_Channel= DMA_Channel_4;//ͨ��
		DMA_InitStructure.DMA_PeripheralBaseAddr = (uint32_t)&(UART5->DR);//�����ַ
		DMA_InitStructure.DMA_Memory0BaseAddr = (uint32_t)UA5RxDMAbuf;//������4���յ�������ucRxData_DMA1_Stream2[]��ڴ����ַ
		DMA_InitStructure.DMA_DIR = DMA_DIR_PeripheralToMemory;//�������ݴ��䷽��
		DMA_InitStructure.DMA_BufferSize = USART5_RXDMA_LEN;//����DMAһ�δ����������Ĵ�С
		DMA_InitStructure.DMA_PeripheralInc = DMA_PeripheralInc_Disable;//���������ַ����
		DMA_InitStructure.DMA_MemoryInc = DMA_MemoryInc_Enable;	//�����ڴ��ַ����
		DMA_InitStructure.DMA_PeripheralDataSize = DMA_PeripheralDataSize_Byte;//������������ݳ���Ϊ�ֽڣ�8bits��
		DMA_InitStructure.DMA_MemoryDataSize = DMA_MemoryDataSize_Byte;//�����ڴ�����ݳ���Ϊ�ֽڣ�8bits��
		DMA_InitStructure.DMA_Mode = DMA_Mode_Circular;//DMA_Mode_Normal;////����DMAģʽΪѭ��ģʽ
		DMA_InitStructure.DMA_Priority = DMA_Priority_VeryHigh;//DMA_Priority_Medium;//����DMAͨ�������ȼ�Ϊ������ȼ�
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
		while( DMA_GetCmdStatus(DMA1_Stream7) == ENABLE );			//�ȴ�DMA������

		dma.DMA_Channel				=	DMA_Channel_4;
		dma.DMA_PeripheralBaseAddr	=	(uint32_t)&(UART5->DR);
		dma.DMA_Memory0BaseAddr		=	NULL;//����
		dma.DMA_DIR					=	DMA_DIR_MemoryToPeripheral;	//�ڴ浽����
		dma.DMA_BufferSize			=	NULL;//����
		dma.DMA_PeripheralInc		=	DMA_PeripheralInc_Disable;
		dma.DMA_MemoryInc			=	DMA_MemoryInc_Enable;
		dma.DMA_PeripheralDataSize	=	DMA_PeripheralDataSize_Byte;
		dma.DMA_MemoryDataSize		=	DMA_MemoryDataSize_Byte;
		dma.DMA_Mode				=	DMA_Mode_Normal;			//��������
		dma.DMA_Priority			=	DMA_Priority_VeryHigh;
		dma.DMA_FIFOMode			=	DMA_FIFOMode_Disable;
		dma.DMA_FIFOThreshold		=	DMA_FIFOThreshold_1QuarterFull;
		dma.DMA_MemoryBurst			=	DMA_MemoryBurst_Single;
		dma.DMA_PeripheralBurst		=	DMA_PeripheralBurst_Single;
		DMA_Init(DMA1_Stream7, &dma);
		DMA_Cmd(DMA1_Stream7, DISABLE);
}

typedef struct { uint8_t id; uint8_t index; float value; } GS_Cmd_t;
extern volatile GS_Cmd_t gs_cmd_queue[16];
extern volatile uint8_t gs_cmd_head;
extern volatile uint8_t gs_cmd_tail;
extern volatile uint32_t gs_cmd_drop_count;

/* Second DMA1_Stream7 turn for the 0x07 / 0x7F reply. Caller (API/subscribe.c
 * via Send_Task) is responsible for ensuring the live telemetry DMA has
 * completed; the existing pattern in Send_Groundstation_Telemetry_UART4 is
 * `while (DMA_GetCurrDataCounter(DMA1_Stream7));` followed by clearing the
 * stream-7 flags. Mirrors that exact sequence so the second turn does not
 * corrupt the live telemetry burst. */
void Uart5_Subscribe_TxSend(const uint8_t* buf, uint16_t len)
{
    if ((buf == 0) || (len == 0U)) {
        return;
    }
    while (DMA_GetCurrDataCounter(DMA1_Stream7));
    DMA_Cmd(DMA1_Stream7, DISABLE);
    while (DMA_GetCmdStatus(DMA1_Stream7) == ENABLE);
    DMA_ClearFlag(DMA1_Stream7, DMA_FLAG_TCIF7 | DMA_FLAG_HTIF7 | DMA_FLAG_TEIF7
                              | DMA_FLAG_DMEIF7 | DMA_FLAG_FEIF7);
    DMA1_Stream7->M0AR = (uint32_t)buf;
    DMA1_Stream7->NDTR = len;
    DMA_Cmd(DMA1_Stream7, ENABLE);
}

/* Transport-agnostic GS command-frame parser. Walks `mailbox[0..total)`, matching
 * the 0xCC 0xDD / 0xCC 0xDE grammar originally written for UART5 (BSP/usart5.c
 * Handle_UART5_GroundStation_Command) but parameterised so USART3 can call it
 * off its own IDLE without duplicating the parser.
 *
 * `allow_subscribe` selects the 0xCC 0xDE branch: only UART5 has the file-scope
 * subscribe staging buffer (UA5RxSubscribeBuf) and the reply DMA path the
 * subscribe handler arms off the back of Send_Task. USART3 callers must pass 0
 * so a 0xCC 0xDE byte sequence is consumed (offset advances) without touching
 * UART5-only state -- which would otherwise silently extend the reply path to
 * a transport that has no DMA wired for it.
 *
 * CONSTRAINT: 0xCC 0xDD frame layout and XOR CRC must match serial_bridge.py
 * `_pack_command_frame()` -- Format: [0xCC] [0xDD] [CMD_ID u8] [INDEX u8]
 * [VALUE float32 LE] [CRC8], total 9 B. */
static void ParseGsCommandFrames(const uint8_t* mailbox, uint16_t total,
                                  uint8_t allow_subscribe)
{
	uint16_t offset = 0;
	while (offset + 9U <= total)
	{
		if (allow_subscribe != 0U &&
		    mailbox[offset] == 0xCC && mailbox[offset + 1U] == 0xDE)
		{
			// Extended-prefix subscribe request: variable payload, run-length encoded.
			// Header layout (offsets inside mailbox):
			//   +0  0xCC (SYNC_HI)
			//   +1  0xDE (SYNC_LO)
			//   +2  CMD (0x20)
			//   +3  LEN_HI
			//   +4  LEN_LO
			//   +5  MAX_NUM_BASIS (tuple count)
			//   +6 .. +6+LEN-1  payload tuples (each 6 B)
			//   +6+LEN         CRC8 XOR
			// Minimum frame is 7 B (zero tuples: 6 header + 0 payload + 1 CRC).
			uint8_t  sub_cmd = mailbox[offset + 2U];
			uint16_t len_hi = mailbox[offset + 3U];
			uint16_t len_lo = mailbox[offset + 4U];
			uint16_t payload_len = (uint16_t)((len_hi << 8) | len_lo);
			uint8_t  len_ok;
			// Reject malformed frames early: total in mailbox must cover header + payload + 1 CRC.
			// Two commands share the 0xCC 0xDE prefix and differ in payload shape:
			//   0x20 one-shot read   payload = N * 6   (address LE32 + size LE16)
			//   0x21 stream subscribe payload = 2 + N * 8 (divider, transport, then
			//                                             address LE32 + size LE16 + count LE16)
			// Anything else is not a frame we own; skip a byte and resync.
			if (sub_cmd == SUBSCRIBE_STREAM_CMD)
			{
				// 0x21 payload = 3 config bytes (divider, transport, slot) + N * 8.
				len_ok = ((payload_len >= 3U) && (((payload_len - 3U) % 8U) == 0U)) ? 1U : 0U;
			}
			else if (sub_cmd == SUBSCRIBE_CMD)
			{
				len_ok = ((payload_len % 6U) == 0U) ? 1U : 0U;
			}
			else
			{
				len_ok = 0U;
			}
			if ((len_ok == 0U) ||
			    payload_len > (USART5_SUBSCRIBE_RX_LEN - 7U))
			{
				offset += 1U;
				continue;
			}
			uint16_t frame_len = (uint16_t)(6U + payload_len + 1U);
			if (offset + frame_len > total)
			{
				// Truncated: stop walking, leave the partial frame for the next IDLE.
				break;
			}
			// Verify CMD byte and CRC8 XOR over [CMD, LEN_HI, LEN_LO, MAX_NUM_BASIS, payload...].
			uint8_t calc_crc = 0;
			uint16_t i;
			for (i = 2U; i < (uint16_t)(frame_len - 1U); i++)
			{
				calc_crc ^= mailbox[offset + i];
			}
			uint8_t crc = mailbox[offset + frame_len - 1U];
			if (calc_crc == crc)
			{
				// Stage the validated frame for Send_Task. Copy into the file-scope
				// UA5RxSubscribeBuf (NOT a stack local — Send_Task = 500 words / 2 kB).
				// The IRQ path does NOT arm the reply DMA; that happens off the back
				// of the live-telemetry DMA hand-off in TASK/send_data.c, so the
				// reply observes the same UART5 timing contract as A/B telemetry.
				// If a previous reply is still pending (i.e. Send_Task hasn't picked
				// it up yet), drop the new request silently — protects against a
				// runaway host that re-sends faster than 60 Hz Send_Task cadence.
				if (UA5RxSubscribePending == 0U)
				{
					for (i = 0U; i < frame_len; i++)
					{
						UA5RxSubscribeBuf[i] = mailbox[offset + i];
					}
					UA5RxSubscribeLen = frame_len;
					UA5RxSubscribePending = 1U;
				}
			}
			offset = (uint16_t)(offset + frame_len);
		}
		else if (mailbox[offset] == 0xCC && mailbox[offset + 1U] == 0xDD)
		{
			uint8_t cmd_id = mailbox[offset + 2U];
			uint8_t index  = mailbox[offset + 3U];

			union {
				float f;
				uint8_t b[4];
			} val;

			val.b[0] = mailbox[offset + 4U];
			val.b[1] = mailbox[offset + 5U];
			val.b[2] = mailbox[offset + 6U];
			val.b[3] = mailbox[offset + 7U];

			uint8_t crc = mailbox[offset + 8U];
			uint8_t calc_crc = 0;
			int i;
			for (i = 2; i < 8; i++) {
				calc_crc ^= mailbox[offset + (uint16_t)i];
			}

			if (calc_crc == crc) {
				uint8_t next_head = (uint8_t)((gs_cmd_head + 1U) % 16U);
				if (next_head != gs_cmd_tail) {
					gs_cmd_queue[gs_cmd_head].id    = cmd_id;
					gs_cmd_queue[gs_cmd_head].index = index;
					gs_cmd_queue[gs_cmd_head].value = val.f;
					gs_cmd_head = next_head;
				} else {
					gs_cmd_drop_count++;
				}
			}
			offset += 9U;
		}
		else
		{
			offset += 1U;
		}
	}
}

/* UART5 ingress wrapper. Source of truth for the 0xCC 0xDE subscribe path --
 * only UART5 has the staging buffer (UA5RxSubscribeBuf) and the reply DMA
 * (DMA1_Stream7) the subscribe handler arms off the back of Send_Task. */
void Handle_UART5_GroundStation_Command(void)
{
	// ARCH: Queue storage ownership is in BSP/usart4.c; this function is an additional ingress source.
	// WHY loop: the PC serial bridge coalesces multiple rapid writes into one OS-level burst.
	// IDLE fires once for the whole burst; parsing only mailbox[0..8] silently drops every
	// frame after the first (e.g. the execute flag sent last in a TWC sequence).
	ParseGsCommandFrames(UA5RxMailbox, UART5_Rcr.rxSize, 1U);
}

/* USART3 ingress wrapper. Exported (BSP/usart5.h) for USART3_IRQHandler in
 * TASK/stm32f4xx_it.c. Reads UA3RxMailbox via the parameter so the parser has
 * no UART5-specific state in its body.
 *
 * Subscribe (0xCC 0xDE) is rejected by the parser when allow_subscribe=0 -- a
 * 0xCC 0xDE byte sequence on the radio link is consumed (offset advances past
 * it) without touching UART5-only state, so a malformed subscribe cannot reach
 * a transport that has no reply DMA wired. The dashboard command set (every
 * CMD_ID 0x01..0x18) is 0xCC 0xDD, so this is the entire functional surface
 * the radio needs today; the 0xCC 0xDE subscribe path stays UART5-only. */
void Handle_USART3_GroundStation_Command(const uint8_t* mailbox, uint16_t total)
{
	ParseGsCommandFrames(mailbox, total, 0U);
}
