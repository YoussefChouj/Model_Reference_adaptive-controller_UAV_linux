#include "send_data.h"
#include "mrac.h"
#include "gyro_filter.h"
#include "sysid.h"
#include "pid.h"
#include "robot_types.h"
#include "global_declare.h"
#include "rc_input.h"
#include "flight_fsm.h"
#include "Ano_OF.h"
#include "rpm.h"
#include "FreeRTOS.h"
#include "task.h"

/**
 * @module  send_data.c
 * @subsystem  comm
 * @depends  send_data.h, mrac.h, pid.h, robot_types.h, global_declare.h
 * @owns  telemetry frame serialization and ground-station command dispatch
 * @caution  command and telemetry byte layouts are shared contracts with ground_station/comm/serial_bridge.py
 */

_linux_flag stm32_to_linux_flag;
/*************************************************************************
�� �� ����void ANO_Report_UserData1(void)
�������ܣ����ߴ��ڷ�������
��    ע��PA10(USART1_RX)
*************************************************************************/
void ANO_Report_UserData1(void)  //����5
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
	
	/*--------------------------����DMA����---------------------------*/
	
  while(DMA_GetCurrDataCounter(DMA1_Stream7));		   //��֮ǰ�ķ���
  DMA_ClearITPendingBit(DMA1_Stream7, DMA_IT_TCIF7); //����DMA_Mode_Normal,����û��ʹ������ж�ҲҪ�������������ֻ��һ��
    
  DMA_Cmd(DMA1_Stream7, DISABLE);				             //���õ�ǰ����ֵǰ�Ƚ���DMA
  DMA1_Stream7->M0AR = (uint32_t)&Custom_DataBuf;  //���õ�ǰ�������ݻ���ַ:Memory0 tARget
  DMA1_Stream7->NDTR = 68;     //���õ�ǰ���������ݵ�����:Number of Data units to be TRansferred
  DMA_Cmd(DMA1_Stream7, ENABLE);		
                                        //����DMA���� 
                                        //����DMA���� 		
}

UCHAR8 DataBuf_to_linux[52] = {0}; 
void send_to_linux(void)    //����4
{
	float senddata[13];

	//senddata[0]  ��Ϊ֡ͷ
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
	senddata[11]= 11;   //Ԥ��
	senddata[12]= 12;   //Ԥ��

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
	
  while(DMA_GetCurrDataCounter(DMA1_Stream4));		   //��֮ǰ�ķ���
  DMA_ClearITPendingBit(DMA1_Stream4, DMA_IT_TCIF4); //����DMA_Mode_Normal,����û��ʹ������ж�ҲҪ�������������ֻ��һ��
    
  DMA_Cmd(DMA1_Stream4, DISABLE);				             //���õ�ǰ����ֵǰ�Ƚ���DMA
  DMA1_Stream4->M0AR = (uint32_t)&DataBuf_to_linux;  //���õ�ǰ�������ݻ���ַ:Memory0 tARget
  DMA1_Stream4->NDTR = 52;     //���õ�ǰ���������ݵ�����:Number of Data units to be TRansferred
  DMA_Cmd(DMA1_Stream4, ENABLE);		
                                        //����DMA���� 		

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
	
	
  while(DMA_GetCurrDataCounter(DMA1_Stream3));		   //��֮ǰ�ķ���
  DMA_ClearITPendingBit(DMA1_Stream3, DMA_IT_TCIF3); //����DMA_Mode_Normal,����û��ʹ������ж�ҲҪ�������������ֻ��һ��
    
  DMA_Cmd(DMA1_Stream3, DISABLE);				             //���õ�ǰ����ֵǰ�Ƚ���DMA
  DMA1_Stream3->M0AR = (uint32_t)&str_USART;  //���õ�ǰ�������ݻ���ַ:Memory0 tARget
  DMA1_Stream3->NDTR =16;     //���õ�ǰ���������ݵ�����:Number of Data units to be TRansferred
  DMA_Cmd(DMA1_Stream3, ENABLE);		
                                        //����DMA���� 
                                        //����DMA���� 		
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
    
    if (motor_test_active) // FRAME 0x04 — motor bench-test stream @100Hz (replaces A/B while active)
    {
        // Payload (20 B): u32 sample_counter, u8 motor_id, u16 commanded_ccr, f real_voltage, u8 active,
        // {u16 rpm0, u16 rpm1, u16 rpm2, u16 rpm3} — ADR-0010. Layout `<I B H f B 4H`.
        // Thrust is read off an external scale by hand; the firmware streams the operating point
        // (which motor, what CCR, pack voltage, measured RPM) at the loop-adjacent rate so the dashboard
        // logs each manually-entered thrust point against fresh voltage and measured ω. Get_Voltage() is
        // called here because SystemMonitor_Task only refreshes real_voltage at 1 Hz (too slow to catch
        // pack sag during a sweep). sample_counter detects dropped frames. RPMs are averaged per-channel
        // and stale channels read 0 (sensor unplugged / motor stopped). See docs/bench_characterization.md.
        static uint32_t bench_sample_counter = 0;
        uint16_t payload_len = 20U;
        float tf;
        uint16_t rpm_vals[RPM_NUM_CH];
        uint8_t i;

        for (i = 0; i < RPM_NUM_CH; i++) {
            rpm_vals[i] = RPM_Get(i);
        }

        Get_Voltage(); // fresh pack voltage per frame (overrides the 1 Hz SystemMonitor read)

        Buf_Telemetry_UART4[2] = 0x04; // bench frame type
        Buf_Telemetry_UART4[3] = (uint8_t)(payload_len >> 8);
        Buf_Telemetry_UART4[4] = (uint8_t)(payload_len & 0xFFU);
        Buf_Telemetry_UART4[5] = MAX_NUM_BASIS; // header parity with other frames
        len = 6;

        Buf_Telemetry_UART4[len++] = (uint8_t)(bench_sample_counter & 0xFFU);
        Buf_Telemetry_UART4[len++] = (uint8_t)((bench_sample_counter >> 8) & 0xFFU);
        Buf_Telemetry_UART4[len++] = (uint8_t)((bench_sample_counter >> 16) & 0xFFU);
        Buf_Telemetry_UART4[len++] = (uint8_t)((bench_sample_counter >> 24) & 0xFFU);

        Buf_Telemetry_UART4[len++] = motor_test_id;
        Buf_Telemetry_UART4[len++] = (uint8_t)(motor_test_ccr & 0xFFU);
        Buf_Telemetry_UART4[len++] = (uint8_t)((motor_test_ccr >> 8) & 0xFFU);

        tf = real_voltage;
        Buf_Telemetry_UART4[len++] = BYTE0(tf);
        Buf_Telemetry_UART4[len++] = BYTE1(tf);
        Buf_Telemetry_UART4[len++] = BYTE2(tf);
        Buf_Telemetry_UART4[len++] = BYTE3(tf);

        Buf_Telemetry_UART4[len++] = motor_test_active;

        // ADR-0010: 4 channels × u16 little-endian RPM after the active byte.
        // Reordered by channel index, NOT motor number — physical plugging decides pairing.
        for (i = 0; i < RPM_NUM_CH; i++) {
            Buf_Telemetry_UART4[len++] = (uint8_t)(rpm_vals[i] & 0xFFU);
            Buf_Telemetry_UART4[len++] = (uint8_t)((rpm_vals[i] >> 8) & 0xFFU);
        }
        bench_sample_counter++;
    }
    else if (mrac_flags.id_frame_on) // FRAME 0x03 — high-rate system-ID stream @100Hz (replaces A/B while active)
    {
        // Payload (36 B): u32 sample_counter, u8 axis_id, {r,x,u_nom,u_ad,xm} floats for THE EXCITED
        // AXIS ONLY, f sysid_dither, f real_voltage, u8 ARM, u8 FlyMode, u8 SysID FSM state.
        // Single-axis: a run excites one axis; logging only it shrinks the frame from 95->36 B so the
        // GS frame's DMA busy-wait drops ~8.5->~3.7 ms, letting Send_Task stream at 200 Hz (1:1 with
        // the control loop) for clean 2nd-order+ plant ID. axis_id (0 pitch,1 roll,2 yaw,3 z) tells
        // the GS which axis these signals belong to.
        // sysid_dither = raw excitation (exogenous instrument) for unbiased closed-loop IV ID.
        // u_nom and u_ad kept SEPARATE: u_nom+u_ad is the plant input; u_ad alone is the adaptive signal.
        // sample_counter is the firmware time base (detects dropped frames via counter gaps).
        static uint32_t id_sample_counter = 0;
        MRAC_AxisState_t* idax[4];
        MRAC_AxisState_t* a;
        uint8_t axis_id = SysID_GetAxis();
        float idvals[5];
        uint16_t payload_len = 36U;
        int k;

        Buf_Telemetry_UART4[2] = 0x03; // ID frame type
        Buf_Telemetry_UART4[3] = (uint8_t)(payload_len >> 8);
        Buf_Telemetry_UART4[4] = (uint8_t)(payload_len & 0xFFU);
        Buf_Telemetry_UART4[5] = MAX_NUM_BASIS;
        len = 6;

        Buf_Telemetry_UART4[len++] = (uint8_t)(id_sample_counter & 0xFFU);
        Buf_Telemetry_UART4[len++] = (uint8_t)((id_sample_counter >> 8) & 0xFFU);
        Buf_Telemetry_UART4[len++] = (uint8_t)((id_sample_counter >> 16) & 0xFFU);
        Buf_Telemetry_UART4[len++] = (uint8_t)((id_sample_counter >> 24) & 0xFFU);

        Buf_Telemetry_UART4[len++] = axis_id;

        idax[0] = &mrac_state.pitch; idax[1] = &mrac_state.roll;
        idax[2] = &mrac_state.yaw;   idax[3] = &mrac_state.z_rate;
        a = idax[axis_id & 0x03U];
        idvals[0] = a->r;      // rate command into axis (rad/s)
        idvals[1] = a->x;      // measured rate (rad/s)
        idvals[2] = a->u_nom;  // nominal PID effort (SI Nm / N)
        idvals[3] = a->u_ad;   // adaptive effort (SI Nm / N) — plant input = u_nom + u_ad
        idvals[4] = a->xm;     // reference-model state (rad/s)
        for (k = 0; k < 5; k++) {
            Buf_Telemetry_UART4[len++] = BYTE0(idvals[k]);
            Buf_Telemetry_UART4[len++] = BYTE1(idvals[k]);
            Buf_Telemetry_UART4[len++] = BYTE2(idvals[k]);
            Buf_Telemetry_UART4[len++] = BYTE3(idvals[k]);
        }
        {
            float dval = SysID_GetDither(); // exogenous excitation -> clean IV instrument offline
            Buf_Telemetry_UART4[len++] = BYTE0(dval);
            Buf_Telemetry_UART4[len++] = BYTE1(dval);
            Buf_Telemetry_UART4[len++] = BYTE2(dval);
            Buf_Telemetry_UART4[len++] = BYTE3(dval);
        }
        {
            // real_voltage is refreshed at 1 Hz by Get_Voltage() in SystemMonitor_Task (battery
            // changes slowly; that single periodic read also drives the low-battery beep and the
            // dashboard battery widget in all modes). Operating-point voltage matters for SysID
            // because actuator effectiveness scales with pack voltage -> it modulates the gain K.
            float tf = real_voltage;
            Buf_Telemetry_UART4[len++] = BYTE0(tf);
            Buf_Telemetry_UART4[len++] = BYTE1(tf);
            Buf_Telemetry_UART4[len++] = BYTE2(tf);
            Buf_Telemetry_UART4[len++] = BYTE3(tf);
        }
        Buf_Telemetry_UART4[len++] = DroneStatus.ARM_Status;
        Buf_Telemetry_UART4[len++] = DroneStatus.FlyMode;
        Buf_Telemetry_UART4[len++] = SysID_GetState(); // live FSM state for the GS System ID tab (ADR-0004 dec.6)
        id_sample_counter++;
    }
    else if (frame_counter % 5 != 0) // 100Hz Frame A
    {
        // FRAME A �� header: [type][LEN_hi][LEN_lo][MAX_NUM_BASIS], payload 37 bytes (16-bit LEN)
        {
            uint16_t payload_len = 39U; /* +1 rc_authority +1 GS_PROTO_VERSION */
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
        Buf_Telemetry_UART4[len++] = RCInput_GetAuthority(); /* 1=PC authority, 0=RC */
        Buf_Telemetry_UART4[len++] = GS_PROTO_VERSION; /* protocol version — must match serial_bridge.py */
    }
    else // 20Hz Frame B
    {
        // FRAME B �� same 16-bit payload LEN as Frame A
        // MRAC: 4 axes * (MAX_NUM_BASIS + 2) floats
        // PID: 12 loops * 3 floats = 36 floats
        // Tail: u8 + 3f + f + f + u8 + f(real_voltage) = 26 bytes
        uint8_t total_floats = 4 * (MAX_NUM_BASIS + 2) + 36;
        uint16_t payload_len = (uint16_t)((uint16_t)total_floats * 4U + 26U);
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
            } else if (figure8_path.active) {
                active_path_mode = 4;
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
            {
                float tf = real_voltage;   /* battery pack voltage (4S), logged as status.vbat */
                Buf_Telemetry_UART4[len++] = BYTE0(tf);
                Buf_Telemetry_UART4[len++] = BYTE1(tf);
                Buf_Telemetry_UART4[len++] = BYTE2(tf);
                Buf_Telemetry_UART4[len++] = BYTE3(tf);
            }
        }
    }
    
    // CONSTRAINT: CRC coverage must match the host parser exactly.
    // WHY: Any mismatch causes silent frame drops in serial_bridge.
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
extern volatile GS_Cmd_t gs_cmd_queue[16];
extern volatile uint8_t gs_cmd_head;
extern volatile uint8_t gs_cmd_tail;

/* Stop TWC / sinusoid / circle, neutral sticks, clear GS mission trigger, dangerous stop */
static void GroundStation_AbortAllPaths(void)
{
    // ARCH: Centralized abort keeps all stop paths synchronized.
    TWC.execute = 0;
    sinusoid_path.active = 0U;
    circle_path.active = 0U;
    figure8_path.active = 0U;
    RCInput_SetAuthority(0U);
    GS_KeySDKflag = 0U;
    FlightFSM_Event(FLIGHT_EVENT_DANGEROUS_STOP);
}

void Process_GroundStation_Command(void)
{
    while (gs_cmd_tail != gs_cmd_head)
    {
        uint8_t id = gs_cmd_queue[gs_cmd_tail].id;
        uint8_t idx = gs_cmd_queue[gs_cmd_tail].index;
        float val = gs_cmd_queue[gs_cmd_tail].value;
        
        gs_cmd_tail = (gs_cmd_tail + 1) % 16;
        
        // CMD 0x01 �� PID gain update
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
                                   
            if (axis < 7 && val >= 0.0f && val <= 200.0f) {
                if (gain == 0) pids[axis]->Kp = val;
                else if (gain == 1) pids[axis]->Ki = val;
                else if (gain == 2) pids[axis]->Kd = val;
            }
        }
        
        // CMD 0x02 / 0x05 / 0x08 �� MRAC array element update (What_tol moved from 0x06 to 0x08; 0x06 = virtual RC)
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
                if      (id == 0x02 && val >  0.0f) configs[axis]->gamma[elem]      = val;
                else if (id == 0x05 && val >= 0.0f) configs[axis]->What_limit[elem] = val;
                else if (id == 0x08 && val >= 0.0f) configs[axis]->What_tol[elem]   = val;
            }
        }

        // CMD 0x06 — virtual stick injection. val is normalised [-1.0, +1.0]. idx: [0]=thr,[1]=pitch,[2]=roll,[3]=yaw.
        // Gate: FlyMode_SDK only (physical RC mode switch is still the hard kill via Check_Fly_Mode).
        // sbus_lost is NOT checked: RC stays ON as emergency fallback; authority flag in RCInput routes the signal.
        else if (id == 0x06) {
            if (DroneStatus.FlyMode == FlyMode_SDK && idx < 4) {
                float v = val;
                if (v >  1.0f) v =  1.0f;
                if (v < -1.0f) v = -1.0f;
                RCInput_SetVirtualStick((RC_Axis_t)idx, v);
            }
        }

        // CMD 0x07 �� bench test: index 0 value 1.0 enables throttle cap on virtual RC
        else if (id == 0x07) {
            if (idx == 0) {
                bench_mode_active = (val >= 0.5f) ? 1U : 0U;
            }
        }
        
        // CMD 0x03 �� Mixer/saturation update
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

        // CMD 0x09 �� velocity / angle safety limits (ground station)
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
        
        // CMD 0x04 �� Flight mode (idx 0 = dangerous stop + path abort)
        else if (id == 0x04) {
            if (idx == 0) {
                GroundStation_AbortAllPaths();
                GS_KeySDKflag = 0U;
            } else if (idx == 1) {
                FlightFSM_Event(FLIGHT_EVENT_RECOVER_SDK);
            }
        }

        /* CMD 0x0A �� TWC target (point-to-point); only in SDK mode */
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

        /* CMD 0x0B �� sinusoidal path parameters (FlyMode_SDK only) */
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
                    taskENTER_CRITICAL();
                    sinusoid_path.active = 1U;
                    sinusoid_path.t_elapsed = 0.0f;
                    AutoflyTask_WaypointReset();
                    taskEXIT_CRITICAL();
                } else {
                    sinusoid_path.active = 0U;
                }
            }
        }

        /* CMD 0x0C �� circle path (FlyMode_SDK only) */
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
                    taskENTER_CRITICAL();
                    circle_path.active = 1U;
                    circle_path.theta = 0.0f;
                    circle_path.t_elapsed = 0.0f;
                    AutoflyTask_WaypointReset();
                    taskEXIT_CRITICAL();
                } else {
                    circle_path.active = 0U;
                }
            }
        }

        /* CMD 0x11 - figure-8 (lemniscate) path (FlyMode_SDK only) */
        else if (id == 0x11) {
            if (DroneStatus.FlyMode != FlyMode_SDK) {
                /* ignore */
            } else if (idx == 0) {
                figure8_path.center_x = val;
            } else if (idx == 1) {
                figure8_path.center_y = val;
            } else if (idx == 2) {
                figure8_path.center_z = val;
            } else if (idx == 3) {
                figure8_path.amplitude = val;
            } else if (idx == 4) {
                figure8_path.angular_speed = val;
            } else if (idx == 5) {
                figure8_path.duration = val;
            } else if (idx == 6) {
                figure8_path.type = (uint8_t)(val + 0.5f);
                if (figure8_path.type > 1U) {
                    figure8_path.type = 1U;
                }
            } else if (idx == 7) {
                if (((uint8_t)(val + 0.5f)) != 0) {
                    taskENTER_CRITICAL();
                    figure8_path.active = 1U;
                    figure8_path.theta = 0.0f;
                    figure8_path.t_elapsed = 0.0f;
                    AutoflyTask_WaypointReset();
                    taskEXIT_CRITICAL();
                } else {
                    figure8_path.active = 0U;
                }
            }
        }

        /* CMD 0x12 - shared waypoint-density spacing (loc-PID units = cm; GUI sends Δs_m*100); 0 = continuous */
        else if (id == 0x12) {
            if (idx == 0) {
                waypoint_spacing = (val < 0.0f) ? 0.0f : val;
                AutoflyTask_WaypointReset();
            }
        }

        /* CMD 0x0D �� abort all paths + neutral sticks + dangerous stop */
        else if (id == 0x0D) {
            if (idx == 0) {
                GroundStation_AbortAllPaths();
            }
        }

        /* CMD 0x0F - MRAC feature-flag runtime toggle (val >= 0.5 = ON, else OFF).
         * idx: 0=adaptation_on  1=projection_on  2=deadzone_on  3=hard_freeze_on
         *      4=tanh_saturation_on  5=e_modification_on  6=l1_filtering_on
         *      7=axis_enable_pitch  8=axis_enable_roll  9=axis_enable_yaw
         *      10=output_injection_on (shadow-mode gate: 0=motors see pure PID)
         *      11=id_frame_on (high-rate system-ID telemetry frame 0x03 @100Hz, replaces A/B)  */
        else if (id == 0x0F) {
            uint8_t on = ((uint8_t)(val + 0.5f)) != 0U ? 1U : 0U;
            switch (idx) {
                case 0: mrac_flags.adaptation_on      = on; break;
                case 1: mrac_flags.projection_on      = on; break;
                case 2: mrac_flags.deadzone_on        = on; break;
                case 3: mrac_flags.hard_freeze_on     = on; break;
                case 4: mrac_flags.tanh_saturation_on = on; break;
                case 5: mrac_flags.e_modification_on  = on; break;
                case 6: mrac_flags.l1_filtering_on    = on; break;
                case 7: mrac_flags.axis_enable_pitch  = on; break;
                case 8: mrac_flags.axis_enable_roll   = on; break;
                case 9: mrac_flags.axis_enable_yaw    = on; break;
                case 10: mrac_flags.output_injection_on = on; break;
                case 11: mrac_flags.id_frame_on         = on; break;
                default: break;
            }
        }

        /* CMD 0x13 — reference model type selector (idx 0, val = 0/1/2).
         *   0 = passthrough (xm = r), 1 = first-order, 2 = second-order.
         * Snaps all reference states to plant on change for bumpless switching. */
        else if (id == 0x13) {
            if (idx == 0) {
                uint8_t t = (uint8_t)(val + 0.5f);
                if (t > 2U) t = 2U;
                mrac_flags.ref_model_type = t;
                mrac_state.pitch.xm  = mrac_state.pitch.x;   mrac_state.pitch.xm_dot  = 0.0f;
                mrac_state.roll.xm   = mrac_state.roll.x;    mrac_state.roll.xm_dot   = 0.0f;
                mrac_state.yaw.xm    = mrac_state.yaw.x;     mrac_state.yaw.xm_dot    = 0.0f;
                mrac_state.z_rate.xm = mrac_state.z_rate.x;  mrac_state.z_rate.xm_dot = 0.0f;
            }
        }

        /* CMD 0x14 — SysID excitation control (ADR-0004). Set params (idx 0-5) then start/abort (idx 6).
         *   idx 0=axis(0 pitch,1 roll,2 yaw,3 Z)  1=signal(0 chirp,1 multisine)  2=f0 Hz  3=f1 Hz
         *       4=amplitude (deg/s; Z in m/s)  5=duration s  6=start(>=0.5)/abort(<0.5)
         *       7=geofence enable (>=0.5 ON default, <0.5 OFF — pilot-watch override)
         * Dashboard sends CMD 0x10 (OF-origin reset) immediately before idx 6 start. */
        else if (id == 0x14) {
            static uint8_t sx_axis = 0U, sx_sig = 0U;
            static float sx_f0 = 1.0f, sx_f1 = 12.0f, sx_amp = 30.0f, sx_dur = 20.0f;
            switch (idx) {
                case 0: sx_axis = (uint8_t)(val + 0.5f); break;
                case 1: sx_sig  = (uint8_t)(val + 0.5f); break;
                case 2: sx_f0 = val; break;
                case 3: sx_f1 = val; break;
                case 4: sx_amp = val; break;
                case 5: sx_dur = val; break;
                case 6:
                    if (((uint8_t)(val + 0.5f)) != 0U) {
                        /* Self-sufficient OF-origin reset (ADR-0004 dec.6/finding #13): do not rely
                         * on the GS having sent CMD 0x10 first, so the green-zone centre is always
                         * captured at a fresh (0,0) origin. Mirrors the 0x10 handler below. */
                        ano_of.earth_x       = 0.0f;
                        ano_of.earth_y       = 0.0f;
                        ano_of.earth_x_ture  = 0.0f;
                        ano_of.earth_y_ture  = 0.0f;
                        ano_of.DISTANCE_X    = 0.0f;
                        ano_of.DISTANCE_Y    = 0.0f;
                        Ctrler.locxPID.FB    = 0.0f;
                        Ctrler.locyPID.FB    = 0.0f;
                        Ctrler.locxPID.Des   = 0.0f;
                        Ctrler.locyPID.Des   = 0.0f;
                        Ctrler.locxsPID.Des  = 0.0f;
                        Ctrler.locysPID.Des  = 0.0f;
                        SysID_Start((SysID_Axis_e)sx_axis, (SysID_Signal_e)sx_sig, sx_f0, sx_f1, sx_amp, sx_dur);
                    } else {
                        SysID_Abort();
                    }
                    break;
                case 7: SysID_SetGeofence(((uint8_t)(val + 0.5f)) != 0U ? 1U : 0U); break;
                default: break;
            }
        }

        /* CMD 0x15 — gyro low-pass filter (Phase 1, ADR-0004).
         *   idx 0 = enable (val>=0.5 ON, else pass-through)
         *   idx 1 = cutoff Hz (applied to pitch/roll/yaw)  */
        else if (id == 0x15) {
            if (idx == 0) {
                GyroFilter_SetEnabled(((uint8_t)(val + 0.5f)) != 0U ? 1U : 0U);
            } else if (idx == 1) {
                GyroFilter_SetCutoff(GYRO_FILT_PITCH, val);
                GyroFilter_SetCutoff(GYRO_FILT_ROLL,  val);
                GyroFilter_SetCutoff(GYRO_FILT_YAW,   val);
            }
        }

        /* CMD 0x10 — reset world-frame optical flow origin.
         * Zeros accumulated earth_x/y position so the drone's current location
         * becomes the new (0, 0) world origin.  Also syncs position setpoints
         * to avoid a sudden jump on the next control tick. */
        else if (id == 0x10) {
            if (idx == 0) {
                ano_of.earth_x       = 0.0f;
                ano_of.earth_y       = 0.0f;
                ano_of.earth_x_ture  = 0.0f;
                ano_of.earth_y_ture  = 0.0f;
                ano_of.DISTANCE_X    = 0.0f;
                ano_of.DISTANCE_Y    = 0.0f;
                Ctrler.locxPID.FB    = 0.0f;
                Ctrler.locyPID.FB    = 0.0f;
                Ctrler.locxPID.Des   = 0.0f;
                Ctrler.locyPID.Des   = 0.0f;
                Ctrler.locxsPID.Des  = 0.0f;
                Ctrler.locysPID.Des  = 0.0f;
            }
        }

        /* CMD 0x0E - ground-station SDK arm switch */
        else if (id == 0x0E) {
            if (idx == 0) {
                if (((uint8_t)(val + 0.5f)) != 0) {
                    GS_KeySDKflag = 1U;
                    FlightFSM_Event(FLIGHT_EVENT_ARM_REQUEST);
                    RCInput_SetAuthority(1U);
                    /* If already airborne, override the -1.0f throttle floor that
                     * SetAuthority just set.  Without this, the motor-idle guard
                     * (Z_pos.FB < 0.3 && THR < -0.85) fires immediately and cuts
                     * motors mid-flight.  On the ground the floor stays at -1.0f
                     * so the pilot must raise the throttle slider deliberately. */
                    if (Ctrler.Z_posPID.FB > 0.35f) {
                        RCInput_SetVirtualStick(RC_AXIS_THR, 0.0f);
                    }
                } else {
                    /* ARM REQ OFF: relinquish PC authority only — drone stays ARMED.
                     * Physical RC resumes immediately so the pilot can land safely.
                     * DISARM_REQUEST is intentionally omitted: firing it mid-air cuts
                     * motors. Pilot disarms via RC stick gesture after landing. */
                    GS_KeySDKflag = 0U;
                    RCInput_SetAuthority(0U);
                }
            }
        }

        /* CMD 0x16 — motor bench test (DISARMED-only; thrust-stand experiment).
         *   idx 0 = enable / heartbeat (val>=0.5 ON; each send pets the dead-man)
         *   idx 1 = motor select (1..4 = M1..M4; 0 = none)
         *   idx 2 = commanded CCR (clamped to [2000,4000])
         * The stabilizer drives only the selected motor and zeroes everything if no
         * heartbeat arrives within MOTOR_TEST_DEADMAN_TICKS or the FSM leaves DISARMED.
         * See docs/bench_characterization.md. */
        else if (id == 0x16) {
            if (idx == 0) {
                if (((uint8_t)(val + 0.5f)) != 0U) {
                    motor_test_active   = 1U;
                    motor_test_watchdog = 0U;   /* heartbeat: pet the dead-man */
                } else {
                    motor_test_active = 0U;
                }
            } else if (idx == 1) {
                uint8_t m = (uint8_t)(val + 0.5f);
                motor_test_id = (m <= 4U) ? m : 0U;
            } else if (idx == 2) {
                float c = val;
                if (c < 2000.0f) c = 2000.0f;
                if (c > 4000.0f) c = 4000.0f;
                motor_test_ccr = (uint16_t)(c + 0.5f);
            }
        }
    }
}

