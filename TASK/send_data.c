#include "send_data.h"
#include "mrac.h"
#include "pid.h"
#include "robot_types.h"
#include "global_declare.h"

_linux_flag stm32_to_linux_flag;
/*************************************************************************
函 数 名：void ANO_Report_UserData1(void)
函数功能：无线串口发数任务
备    注：PA10(USART1_RX)
*************************************************************************/
void ANO_Report_UserData1(void)  //串口5
{
	Get_Voltage();
	float senddata[16];

	senddata[0] =	 real_voltage ;
  senddata[1] =  Ctrler.Z_ratePID.U ; 
	senddata[2] =  Ctrler.locxPID.FB;    
	senddata[3] =  Ctrler.locyPID.FB ;
  senddata[4] =  Ctrler.Z_posPID.FB ; 
	senddata[5] =  imu_data.pit; 
	senddata[6] =  1;  
	senddata[7] =  8 ;  
	senddata[8] =  9;  
	senddata[9] = 10 ;  
	senddata[10]=  11 ;
	senddata[11] = 12;
	senddata[12] = 13 ;
	senddata[13] = 14;
	senddata[14] = 15;
	senddata[15] = 16 ;

	Custom_DataBuf[0]= BYTE0(senddata[0]) ;//   
	Custom_DataBuf[1]= BYTE1(senddata[0]) ;//   
	Custom_DataBuf[2]= BYTE2(senddata[0]) ;//    
	Custom_DataBuf[3]= BYTE3(senddata[0]) ;// 
	
	Custom_DataBuf[4]= BYTE0(senddata[1]) ;//    
	Custom_DataBuf[5]= BYTE1(senddata[1]) ;//    
	Custom_DataBuf[6]= BYTE2(senddata[1]) ;//   
	Custom_DataBuf[7]= BYTE3(senddata[1]) ;//  
	
	Custom_DataBuf[8]= BYTE0(senddata[2]) ;//    
	Custom_DataBuf[9]= BYTE1(senddata[2]) ;//    
	Custom_DataBuf[10]= BYTE2(senddata[2]) ;//    
	Custom_DataBuf[11]= BYTE3(senddata[2]) ;//   
	
	Custom_DataBuf[12]= BYTE0(senddata[3]) ;//   
	Custom_DataBuf[13]= BYTE1(senddata[3]) ;//   
	Custom_DataBuf[14]= BYTE2(senddata[3]) ;//    
	Custom_DataBuf[15]= BYTE3(senddata[3]) ;//  
	
	Custom_DataBuf[16]= BYTE0(senddata[4]) ;//   
	Custom_DataBuf[17]= BYTE1(senddata[4]) ;//   
	Custom_DataBuf[18]= BYTE2(senddata[4]) ;//    
	Custom_DataBuf[19]= BYTE3(senddata[4]) ;//  
	
	Custom_DataBuf[20]= BYTE0(senddata[5]) ;//   
	Custom_DataBuf[21]= BYTE1(senddata[5]) ;//   
	Custom_DataBuf[22]= BYTE2(senddata[5]) ;//    
	Custom_DataBuf[23]= BYTE3(senddata[5]) ;//  
	
	Custom_DataBuf[24]= BYTE0(senddata[6]) ;//   
	Custom_DataBuf[25]= BYTE1(senddata[6]) ;//   
	Custom_DataBuf[26]= BYTE2(senddata[6]) ;//    
	Custom_DataBuf[27]= BYTE3(senddata[6]) ;//  
	
	Custom_DataBuf[28]= BYTE0(senddata[7]) ;//   
	Custom_DataBuf[29]= BYTE1(senddata[7]) ;//   
	Custom_DataBuf[30]= BYTE2(senddata[7]) ;//    
	Custom_DataBuf[31]= BYTE3(senddata[7]) ;//  
	
	Custom_DataBuf[32]= BYTE0(senddata[8]) ;//   
	Custom_DataBuf[33]= BYTE1(senddata[8]) ;//   
	Custom_DataBuf[34]= BYTE2(senddata[8]) ;//    
	Custom_DataBuf[35]= BYTE3(senddata[8]) ;// 
	
	Custom_DataBuf[36]= BYTE0(senddata[9]) ;//   
	Custom_DataBuf[37]= BYTE1(senddata[9]) ;//   
	Custom_DataBuf[38]= BYTE2(senddata[9]) ;//    
	Custom_DataBuf[39]= BYTE3(senddata[9]) ;// 
	
	Custom_DataBuf[40]= BYTE0(senddata[10]) ;//   
	Custom_DataBuf[41]= BYTE1(senddata[10]) ;//   
	Custom_DataBuf[42]= BYTE2(senddata[10]) ;//    
	Custom_DataBuf[43]= BYTE3(senddata[10]) ;// 
	
	Custom_DataBuf[44]= BYTE0(senddata[11]) ;//   
	Custom_DataBuf[45]= BYTE1(senddata[11]) ;//   
	Custom_DataBuf[46]= BYTE2(senddata[11]) ;//    
	Custom_DataBuf[47]= BYTE3(senddata[11]) ;// 
	
	Custom_DataBuf[48]= BYTE0(senddata[12]) ;//   
	Custom_DataBuf[49]= BYTE1(senddata[12]) ;//   
	Custom_DataBuf[50]= BYTE2(senddata[12]) ;//    
	Custom_DataBuf[51]= BYTE3(senddata[12]) ;// 
	
	Custom_DataBuf[52]= BYTE0(senddata[13]) ;//   
	Custom_DataBuf[53]= BYTE1(senddata[13]) ;//   
	Custom_DataBuf[54]= BYTE2(senddata[13]) ;//    
	Custom_DataBuf[55]= BYTE3(senddata[13]) ;// 
	
	Custom_DataBuf[56]= BYTE0(senddata[14]) ;//   
	Custom_DataBuf[57]= BYTE1(senddata[14]) ;//   
	Custom_DataBuf[58]= BYTE2(senddata[14]) ;//    
	Custom_DataBuf[59]= BYTE3(senddata[14]) ;// 
	
	Custom_DataBuf[60]= BYTE0(senddata[15]) ;//   
	Custom_DataBuf[61]= BYTE1(senddata[15]) ;//   
	Custom_DataBuf[62]= BYTE2(senddata[15]) ;//    
	Custom_DataBuf[63]= BYTE3(senddata[15]) ;// 
	
	Custom_DataBuf[64]=  0x00 ;//    
	Custom_DataBuf[65]=  0x00 ;//  
	Custom_DataBuf[66]=  0x80 ;//    
	Custom_DataBuf[67]=  0x7f ;// 
	
	/*--------------------------开启DMA发送---------------------------*/
	
  while(DMA_GetCurrDataCounter(DMA1_Stream7));		   //等之前的发完
  DMA_ClearITPendingBit(DMA1_Stream7, DMA_IT_TCIF7); //开启DMA_Mode_Normal,即便没有使用完成中断也要软件清除，否则只发一次
    
  DMA_Cmd(DMA1_Stream7, DISABLE);				             //设置当前计数值前先禁用DMA
  DMA1_Stream7->M0AR = (uint32_t)&Custom_DataBuf;  //设置当前待发数据基地址:Memory0 tARget
  DMA1_Stream7->NDTR = 68;     //设置当前待发的数据的数量:Number of Data units to be TRansferred
  DMA_Cmd(DMA1_Stream7, ENABLE);		
                                        //开启DMA传输 
                                        //开启DMA传输 		
}

UCHAR8 DataBuf_to_linux[52] = {0}; 
void send_to_linux(void)    //串口4
{
	float senddata[13];

	//senddata[0]  做为帧头
	senddata[1] = real_voltage;
	senddata[2] = Ctrler.Z_ratePID.U; 
	senddata[3] =	3; 
  senddata[4] = 4; 
	senddata[5] = 5;
	
	senddata[6] = 6;
	senddata[7] = 7;
	senddata[8] = 8; 
	senddata[9] = 9; 
	senddata[10]= 10; 
	senddata[11]= 11;   //预留
	senddata[12]= 12;   //预留

	DataBuf_to_linux[0]= 0xAA ;  
	DataBuf_to_linux[1]= 0xAA ; 
	DataBuf_to_linux[2]= 0x00 ; 
	DataBuf_to_linux[3]= 0x00 ;
	
	DataBuf_to_linux[4]= BYTE0(senddata[1]) ;//    
	DataBuf_to_linux[5]= BYTE1(senddata[1]) ;//    
	DataBuf_to_linux[6]= BYTE2(senddata[1]) ;//   
	DataBuf_to_linux[7]= BYTE3(senddata[1]) ;//  
	
	DataBuf_to_linux[8]= BYTE0(senddata[2]) ;//    
	DataBuf_to_linux[9]= BYTE1(senddata[2]) ;//    
	DataBuf_to_linux[10]= BYTE2(senddata[2]) ;//    
	DataBuf_to_linux[11]= BYTE3(senddata[2]) ;//   
	
	DataBuf_to_linux[12]= BYTE0(senddata[3]) ;//   
	DataBuf_to_linux[13]= BYTE1(senddata[3]) ;//   
	DataBuf_to_linux[14]= BYTE2(senddata[3]) ;//    
	DataBuf_to_linux[15]= BYTE3(senddata[3]) ;//  
	
	DataBuf_to_linux[16]= BYTE0(senddata[4]) ;//   
	DataBuf_to_linux[17]= BYTE1(senddata[4]) ;//   
	DataBuf_to_linux[18]= BYTE2(senddata[4]) ;//    
	DataBuf_to_linux[19]= BYTE3(senddata[4]) ;//  
	
	DataBuf_to_linux[20]= BYTE0(senddata[5]) ;//   
	DataBuf_to_linux[21]= BYTE1(senddata[5]) ;//   
	DataBuf_to_linux[22]= BYTE2(senddata[5]) ;//    
	DataBuf_to_linux[23]= BYTE3(senddata[5]) ;//  
	
	DataBuf_to_linux[24]= BYTE0(senddata[6]) ;//   
	DataBuf_to_linux[25]= BYTE1(senddata[6]) ;//   
	DataBuf_to_linux[26]= BYTE2(senddata[6]) ;//    
	DataBuf_to_linux[27]= BYTE3(senddata[6]) ;//  
	
	DataBuf_to_linux[28]= BYTE0(senddata[7]) ;//   
	DataBuf_to_linux[29]= BYTE1(senddata[7]) ;//   
	DataBuf_to_linux[30]= BYTE2(senddata[7]) ;//    
	DataBuf_to_linux[31]= BYTE3(senddata[7]) ;//  
	
	DataBuf_to_linux[32]= BYTE0(senddata[8]) ;//   
	DataBuf_to_linux[33]= BYTE1(senddata[8]) ;//   
	DataBuf_to_linux[34]= BYTE2(senddata[8]) ;//    
	DataBuf_to_linux[35]= BYTE3(senddata[8]) ;// 
	
	DataBuf_to_linux[36]= BYTE0(senddata[9]) ;//   
	DataBuf_to_linux[37]= BYTE1(senddata[9]) ;//   
	DataBuf_to_linux[38]= BYTE2(senddata[9]) ;//    
	DataBuf_to_linux[39]= BYTE3(senddata[9]) ;// 
	
	DataBuf_to_linux[40]= BYTE0(senddata[10]) ;//    
	DataBuf_to_linux[41]= BYTE1(senddata[10]) ;//  
	DataBuf_to_linux[42]= BYTE2(senddata[10]) ;//    
	DataBuf_to_linux[43]= BYTE3(senddata[10]) ;// 
	
	DataBuf_to_linux[44]= BYTE0(senddata[11]) ;//    
	DataBuf_to_linux[45]= BYTE1(senddata[11]) ;//  
	DataBuf_to_linux[46]= BYTE2(senddata[11]) ;//    
	DataBuf_to_linux[47]= BYTE3(senddata[11]) ;// 
	
	DataBuf_to_linux[48]= BYTE0(senddata[12]) ;//    
	DataBuf_to_linux[49]= BYTE1(senddata[12]) ;//  
	DataBuf_to_linux[50]= BYTE2(senddata[12]) ;//    
	DataBuf_to_linux[51]= BYTE3(senddata[12]) ;// 
	
  while(DMA_GetCurrDataCounter(DMA1_Stream4));		   //等之前的发完
  DMA_ClearITPendingBit(DMA1_Stream4, DMA_IT_TCIF4); //开启DMA_Mode_Normal,即便没有使用完成中断也要软件清除，否则只发一次
    
  DMA_Cmd(DMA1_Stream4, DISABLE);				             //设置当前计数值前先禁用DMA
  DMA1_Stream4->M0AR = (uint32_t)&DataBuf_to_linux;  //设置当前待发数据基地址:Memory0 tARget
  DMA1_Stream4->NDTR = 52;     //设置当前待发的数据的数量:Number of Data units to be TRansferred
  DMA_Cmd(DMA1_Stream4, ENABLE);		
                                        //开启DMA传输 		

}
void usart3_send(void)
{
	UCHAR8 str_USART[16];
	float angles[3] ;
	angles[0] = imu_data.rol;
	angles[1] = imu_data.pit;
	angles[2] = imu_data.yaw;
	//angles[0] = 0;
	//angles[1] = 0;
  //angles[2] = 0;
	str_USART[0] = BYTE0(angles[0]);
	str_USART[1] = BYTE1(angles[0]);
	str_USART[2] = BYTE2(angles[0]);
	str_USART[3] = BYTE3(angles[0]);

	str_USART[4] = BYTE0(angles[1]);
	str_USART[5] = BYTE1(angles[1]);
	str_USART[6] = BYTE2(angles[1]);
	str_USART[7] = BYTE3(angles[1]);	
	
	str_USART[8] = BYTE0(angles[2]);
	str_USART[9] = BYTE1(angles[2]);
	str_USART[10] = BYTE2(angles[2]);
	str_USART[11] = BYTE3(angles[2]);	
	
	str_USART[12] = 0x00;
	str_USART[13] = 0x00;
	str_USART[14] = 0x80;
	str_USART[15] = 0x7f;
	
	
  while(DMA_GetCurrDataCounter(DMA1_Stream3));		   //等之前的发完
  DMA_ClearITPendingBit(DMA1_Stream3, DMA_IT_TCIF3); //开启DMA_Mode_Normal,即便没有使用完成中断也要软件清除，否则只发一次
    
  DMA_Cmd(DMA1_Stream3, DISABLE);				             //设置当前计数值前先禁用DMA
  DMA1_Stream3->M0AR = (uint32_t)&str_USART;  //设置当前待发数据基地址:Memory0 tARget
  DMA1_Stream3->NDTR =16;     //设置当前待发的数据的数量:Number of Data units to be TRansferred
  DMA_Cmd(DMA1_Stream3, ENABLE);		
                                        //开启DMA传输 
                                        //开启DMA传输 		
}

/* Max frame: 6-byte header + payload + 1 CRC; Frame B payload up to ~326 bytes @ MAX_NUM_BASIS=8 */
UCHAR8 Buf_Telemetry_UART4[512] = {0};

void Send_Groundstation_Telemetry_UART4(void)
{
    static uint8_t frame_counter = 0;
    uint16_t len = 0;
    uint8_t crc = 0;
    int i;
    
    Buf_Telemetry_UART4[0] = 0xAA;
    Buf_Telemetry_UART4[1] = 0xBB;
    
    if (frame_counter % 5 != 0) // 100Hz Frame A 
    {
        // FRAME A — header: [type][LEN_hi][LEN_lo][MAX_NUM_BASIS], payload 37 bytes (16-bit LEN)
        {
            uint16_t payload_len = 37U;
            Buf_Telemetry_UART4[2] = 0x01; // ID
            Buf_Telemetry_UART4[3] = (uint8_t)(payload_len >> 8);
            Buf_Telemetry_UART4[4] = (uint8_t)(payload_len & 0xFFU);
            Buf_Telemetry_UART4[5] = MAX_NUM_BASIS;
            len = 6;
        }

        // Pack floats (4 axes * 2 floats) = 8 floats = 32 bytes
        float mrac_A[8] = {
            mrac_state.pitch.e, mrac_state.pitch.u_ad,
            mrac_state.roll.e,  mrac_state.roll.u_ad,
            mrac_state.yaw.e,   mrac_state.yaw.u_ad,
            mrac_state.z_rate.e, mrac_state.z_rate.u_ad
        };
        
        for (i = 0; i < 8; i++) {
            Buf_Telemetry_UART4[len++] = BYTE0(mrac_A[i]);
            Buf_Telemetry_UART4[len++] = BYTE1(mrac_A[i]);
            Buf_Telemetry_UART4[len++] = BYTE2(mrac_A[i]);
            Buf_Telemetry_UART4[len++] = BYTE3(mrac_A[i]);
        }
        
        Buf_Telemetry_UART4[len++] = DroneStatus.ARM_Status;
        Buf_Telemetry_UART4[len++] = DroneStatus.FlyMode;
        Buf_Telemetry_UART4[len++] = sbus_lost;
        Buf_Telemetry_UART4[len++] = (uint8_t)(TWC.execute != 0 ? 1 : 0);
        Buf_Telemetry_UART4[len++] = TWC_arrived;
    }
    else // 20Hz Frame B
    {
        // FRAME B — same 16-bit payload LEN as Frame A
        // MRAC: 4 axes * (MAX_NUM_BASIS + 2) floats
        // PID: 12 loops * 3 floats = 36 floats
        // Tail: u8 + 3f + f + f + u8 = 22 bytes
        uint8_t total_floats = 4 * (MAX_NUM_BASIS + 2) + 36;
        uint16_t payload_len = (uint16_t)((uint16_t)total_floats * 4U + 22U);
        Buf_Telemetry_UART4[2] = 0x02; // ID
        Buf_Telemetry_UART4[3] = (uint8_t)(payload_len >> 8);
        Buf_Telemetry_UART4[4] = (uint8_t)(payload_len & 0xFFU);
        Buf_Telemetry_UART4[5] = MAX_NUM_BASIS;
        len = 6;
        
        // 4 Axes MRAC
        MRAC_AxisState_t* axes[4] = {&mrac_state.pitch, &mrac_state.roll, &mrac_state.yaw, &mrac_state.z_rate};
        for(int ax = 0; ax < 4; ax++) {
            for(i = 0; i < MAX_NUM_BASIS; i++) {
                Buf_Telemetry_UART4[len++] = BYTE0(axes[ax]->Theta[i]);
                Buf_Telemetry_UART4[len++] = BYTE1(axes[ax]->Theta[i]);
                Buf_Telemetry_UART4[len++] = BYTE2(axes[ax]->Theta[i]);
                Buf_Telemetry_UART4[len++] = BYTE3(axes[ax]->Theta[i]);
            }
            Buf_Telemetry_UART4[len++] = BYTE0(axes[ax]->u_nom);
            Buf_Telemetry_UART4[len++] = BYTE1(axes[ax]->u_nom);
            Buf_Telemetry_UART4[len++] = BYTE2(axes[ax]->u_nom);
            Buf_Telemetry_UART4[len++] = BYTE3(axes[ax]->u_nom);
            
            Buf_Telemetry_UART4[len++] = BYTE0(axes[ax]->xm);
            Buf_Telemetry_UART4[len++] = BYTE1(axes[ax]->xm);
            Buf_Telemetry_UART4[len++] = BYTE2(axes[ax]->xm);
            Buf_Telemetry_UART4[len++] = BYTE3(axes[ax]->xm);
        }
        
        // 12 PID loops (adds altitude Z_pos + horizontal velocity)
        PIDTypeDef* pids[12] = {&Ctrler.pitchPID, &Ctrler.rollPID, &Ctrler.yawPID, 
                               &Ctrler.gyroxPID, &Ctrler.gyroyPID, &Ctrler.gyrozPID, 
                               &Ctrler.Z_ratePID, &Ctrler.locxPID, &Ctrler.locyPID,
                               &Ctrler.Z_posPID, &Ctrler.locxsPID, &Ctrler.locysPID};
        for(i = 0; i < 12; i++) {
            Buf_Telemetry_UART4[len++] = BYTE0(pids[i]->FB);
            Buf_Telemetry_UART4[len++] = BYTE1(pids[i]->FB);
            Buf_Telemetry_UART4[len++] = BYTE2(pids[i]->FB);
            Buf_Telemetry_UART4[len++] = BYTE3(pids[i]->FB);
            
            Buf_Telemetry_UART4[len++] = BYTE0(pids[i]->Des);
            Buf_Telemetry_UART4[len++] = BYTE1(pids[i]->Des);
            Buf_Telemetry_UART4[len++] = BYTE2(pids[i]->Des);
            Buf_Telemetry_UART4[len++] = BYTE3(pids[i]->Des);
            
            Buf_Telemetry_UART4[len++] = BYTE0(pids[i]->U);
            Buf_Telemetry_UART4[len++] = BYTE1(pids[i]->U);
            Buf_Telemetry_UART4[len++] = BYTE2(pids[i]->U);
            Buf_Telemetry_UART4[len++] = BYTE3(pids[i]->U);
        }

        {
            uint8_t active_path_mode = 0;
            if (sinusoid_path.active) {
                active_path_mode = 2;
            } else if (circle_path.active) {
                active_path_mode = 3;
            } else if (TWC.execute) {
                active_path_mode = 1;
            }
            Buf_Telemetry_UART4[len++] = active_path_mode;

            {
                float tf = TWC.target_x;
                Buf_Telemetry_UART4[len++] = BYTE0(tf);
                Buf_Telemetry_UART4[len++] = BYTE1(tf);
                Buf_Telemetry_UART4[len++] = BYTE2(tf);
                Buf_Telemetry_UART4[len++] = BYTE3(tf);
            }
            {
                float tf = TWC.target_y;
                Buf_Telemetry_UART4[len++] = BYTE0(tf);
                Buf_Telemetry_UART4[len++] = BYTE1(tf);
                Buf_Telemetry_UART4[len++] = BYTE2(tf);
                Buf_Telemetry_UART4[len++] = BYTE3(tf);
            }
            {
                float tf = TWC.target_z;
                Buf_Telemetry_UART4[len++] = BYTE0(tf);
                Buf_Telemetry_UART4[len++] = BYTE1(tf);
                Buf_Telemetry_UART4[len++] = BYTE2(tf);
                Buf_Telemetry_UART4[len++] = BYTE3(tf);
            }
            {
                float tf = sinusoid_path.t_elapsed;
                Buf_Telemetry_UART4[len++] = BYTE0(tf);
                Buf_Telemetry_UART4[len++] = BYTE1(tf);
                Buf_Telemetry_UART4[len++] = BYTE2(tf);
                Buf_Telemetry_UART4[len++] = BYTE3(tf);
            }
            {
                float tf = circle_path.theta;
                Buf_Telemetry_UART4[len++] = BYTE0(tf);
                Buf_Telemetry_UART4[len++] = BYTE1(tf);
                Buf_Telemetry_UART4[len++] = BYTE2(tf);
                Buf_Telemetry_UART4[len++] = BYTE3(tf);
            }
            Buf_Telemetry_UART4[len++] = TWC_arrived;
        }
    }
    
    /* CRC8 XOR over all bytes after sync: frame type, 16-bit LEN, MAX_NUM_BASIS, payload (index 2 .. len-1) */
    crc = 0;
    for (i = 2; i < len; i++) {
        crc ^= Buf_Telemetry_UART4[i];
    }
    Buf_Telemetry_UART4[len++] = crc;
    
    frame_counter++;
    
    // DMA transfer on UART5 wireless link (DMA1_Stream7)
    while(DMA_GetCurrDataCounter(DMA1_Stream7)); 
    DMA_ClearITPendingBit(DMA1_Stream7, DMA_IT_TCIF7); 

    DMA_Cmd(DMA1_Stream7, DISABLE);				             
    DMA1_Stream7->M0AR = (uint32_t)&Buf_Telemetry_UART4;  
    DMA1_Stream7->NDTR = len;     
    DMA_Cmd(DMA1_Stream7, ENABLE);		
}

typedef struct { uint8_t id; uint8_t index; float value; } GS_Cmd_t;
extern volatile GS_Cmd_t gs_cmd_queue[8];
extern volatile uint8_t gs_cmd_head;
extern volatile uint8_t gs_cmd_tail;

/* Stop TWC / sinusoid / circle, neutral sticks, clear GS mission trigger, dangerous stop */
static void GroundStation_AbortAllPaths(void)
{
    TWC.execute = 0;
    sinusoid_path.active = 0U;
    circle_path.active = 0U;
    virtual_rc_sticks[0] = 3000.0f;
    virtual_rc_sticks[1] = 3000.0f;
    virtual_rc_sticks[2] = 3000.0f;
    virtual_rc_sticks[3] = 3000.0f;
    GS_KeySDKflag = 0U;
    DroneStatus.FlyMode = FlyMode_DangerousStop;
}

void Process_GroundStation_Command(void)
{
    while (gs_cmd_tail != gs_cmd_head)
    {
        uint8_t id = gs_cmd_queue[gs_cmd_tail].id;
        uint8_t idx = gs_cmd_queue[gs_cmd_tail].index;
        float val = gs_cmd_queue[gs_cmd_tail].value;
        
        gs_cmd_tail = (gs_cmd_tail + 1) % 8;
        
        // CMD 0x01 — PID gain update
        // INDEX encodes axis+gain: (axis 0-6). (gain 0=Kp, 1=Ki, 2=Kd)
        if (id == 0x01) {
            uint8_t axis = idx / 3;
            uint8_t gain = idx % 3;
            
            PIDTypeDef* pids[7];
            pids[0] = &Ctrler.pitchPID;
            pids[1] = &Ctrler.rollPID;
            pids[2] = &Ctrler.yawPID;
            pids[3] = &Ctrler.gyroxPID;
            pids[4] = &Ctrler.gyroyPID;
            pids[5] = &Ctrler.gyrozPID;
            pids[6] = &Ctrler.Z_ratePID;
                                   
            if (axis < 7) {
                if (gain == 0) pids[axis]->Kp = val;
                else if (gain == 1) pids[axis]->Ki = val;
                else if (gain == 2) pids[axis]->Kd = val;
            }
        }
        
        // CMD 0x02 / 0x05 / 0x08 — MRAC array element update (What_tol moved from 0x06 to 0x08; 0x06 = virtual RC)
        // High nibble: axis (0-3). Low nibble: element index.
        else if (id == 0x02 || id == 0x05 || id == 0x08) {
            uint8_t axis = (idx >> 4) & 0x0F;
            uint8_t elem = idx & 0x0F;
            
            MRAC_AxisConfig_t* configs[4];
            configs[0] = &mrac_config_pitch;
            configs[1] = &mrac_config_roll;
            configs[2] = &mrac_config_yaw;
            configs[3] = &mrac_config_z;
            
            if (axis < 4 && elem < MAX_NUM_BASIS) {
                if (id == 0x02) configs[axis]->gamma[elem] = val;
                else if (id == 0x05) configs[axis]->What_limit[elem] = val;
                else if (id == 0x08) configs[axis]->What_tol[elem] = val;
            }
        }

        // CMD 0x06 — virtual stick injection (only when SBUS lost + SDK mode; see StabilizerTask virtual_rc_sticks)
        else if (id == 0x06) {
            if (sbus_lost == 1 && DroneStatus.FlyMode == FlyMode_SDK && idx < 4) {
                virtual_rc_sticks[idx] = val;
            }
        }

        // CMD 0x07 — bench test: index 0 value 1.0 enables throttle cap on virtual RC
        else if (id == 0x07) {
            if (idx == 0) {
                bench_mode_active = (val >= 0.5f) ? 1U : 0U;
            }
        }
        
        // CMD 0x03 — Mixer/saturation update
        else if (id == 0x03) {
            MRAC_AxisConfig_t* configs[4];
            configs[0] = &mrac_config_pitch;
            configs[1] = &mrac_config_roll;
            configs[2] = &mrac_config_yaw;
            configs[3] = &mrac_config_z;
            if (idx < 4) {
                configs[idx]->mrac_to_mixer = val;
            } else if (idx < 8) {
                configs[idx - 4]->u_max = val;
            } else if (idx == 8) {
                if (val >= 0.0f && val <= 1.0f) gs_throttle_min_pct = val;
            } else if (idx == 9) {
                if (val >= 0.0f && val <= 1.0f) gs_throttle_max_pct = val;
            }
        }

        // CMD 0x09 — velocity / angle safety limits (ground station)
        else if (id == 0x09) {
            if (idx == 0) {
                if (val > 0.05f && val < 20.0f) gs_max_horizontal_speed_mps = val;
            } else if (idx == 1) {
                if (val > 0.05f && val < 10.0f) gs_max_vertical_speed_mps = val;
            } else if (idx == 2) {
                if (val >= 3.0f && val <= 60.0f) gs_max_pitch_deg = val;
            } else if (idx == 3) {
                if (val >= 3.0f && val <= 60.0f) gs_max_roll_deg = val;
            }
        }
        
        // CMD 0x04 — Flight mode (idx 0 = dangerous stop + path abort)
        else if (id == 0x04) {
            if (idx == 0) {
                GroundStation_AbortAllPaths();
                DroneStatus.ARM_Status = DisArmed;
                DroneStatus.FlyMode = FlyMode_DangerousStop;
                GS_KeySDKflag = 0U;
            } else if (idx == 1) {
                DroneStatus.FlyMode = FlyMode_SDK;
            }
        }

        /* CMD 0x0A — TWC target (point-to-point); only in SDK mode */
        else if (id == 0x0A) {
            if (DroneStatus.FlyMode != FlyMode_SDK) {
                /* ignore */
            } else if (idx == 0) {
                TWC.target_x = val;
            } else if (idx == 1) {
                TWC.target_y = val;
            } else if (idx == 2) {
                TWC.target_z = val;
            } else if (idx == 3) {
                TWC.set_yaw = val;
            } else if (idx == 4) {
                TWC.execute = ((uint8_t)(val + 0.5f) != 0) ? 1 : 0;
            }
        }

        /* CMD 0x0B — sinusoidal path parameters (FlyMode_SDK only) */
        else if (id == 0x0B) {
            if (DroneStatus.FlyMode != FlyMode_SDK) {
                /* ignore */
            } else if (idx == 0) {
                sinusoid_path.center_x = val;
            } else if (idx == 1) {
                sinusoid_path.center_y = val;
            } else if (idx == 2) {
                sinusoid_path.center_z = val;
            } else if (idx == 3) {
                sinusoid_path.amplitude = val;
            } else if (idx == 4) {
                sinusoid_path.frequency = val;
            } else if (idx == 5) {
                sinusoid_path.duration = val;
            } else if (idx == 6) {
                sinusoid_path.axis = (uint8_t)(val + 0.5f);
                if (sinusoid_path.axis > 2U) {
                    sinusoid_path.axis = 2U;
                }
            } else if (idx == 7) {
                if (((uint8_t)(val + 0.5f)) != 0) {
                    sinusoid_path.active = 1U;
                    sinusoid_path.t_elapsed = 0.0f;
                } else {
                    sinusoid_path.active = 0U;
                }
            }
        }

        /* CMD 0x0C — circle path (FlyMode_SDK only) */
        else if (id == 0x0C) {
            if (DroneStatus.FlyMode != FlyMode_SDK) {
                /* ignore */
            } else if (idx == 0) {
                circle_path.center_x = val;
            } else if (idx == 1) {
                circle_path.center_y = val;
            } else if (idx == 2) {
                circle_path.center_z = val;
            } else if (idx == 3) {
                circle_path.radius = val;
            } else if (idx == 4) {
                circle_path.angular_speed = val;
            } else if (idx == 5) {
                circle_path.duration = val;
            } else if (idx == 6) {
                if (((uint8_t)(val + 0.5f)) != 0) {
                    circle_path.active = 1U;
                    circle_path.theta = 0.0f;
                    circle_path.t_elapsed = 0.0f;
                } else {
                    circle_path.active = 0U;
                }
            }
        }

        /* CMD 0x0D — abort all paths + neutral sticks + dangerous stop */
        else if (id == 0x0D) {
            if (idx == 0) {
                GroundStation_AbortAllPaths();
            }
        }

        /* CMD 0x0E — ground-station SDK arm switch */
        else if (id == 0x0E) {
            if (idx == 0) {
                if (((uint8_t)(val + 0.5f)) != 0) {
                    GS_KeySDKflag = 1U;
                    DroneStatus.ARM_Status = Armed;
                } else {
                    GS_KeySDKflag = 0U;
                    DroneStatus.ARM_Status = DisArmed;
                }
            }
        }
    }
}

