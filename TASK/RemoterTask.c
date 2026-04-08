#include "RemoterTask.h"
#include "FreeRTOS.h"
#include "task.h"

float channel[4];
/*************************************************************************
函 数 名：void remoter_task(void)
函数功能：遥控器任务
备    注：10ms执行一次
*************************************************************************/
void remoter_task(void)
{
	
			// 旧遥控器
//		channel[0]= (sbus_channel[0]-1024)/672.0*1000.0+3000.0; 
//	  channel[1]= (sbus_channel[1]-1024)/672.0*1000.0+3000.0; 
//	  channel[2]= (sbus_channel[2]-1024)/672.0*1000.0+3000.0; 
//		channel[3]= (sbus_channel[3]-1024)/672.0*1000.0+3000.0; 
	
	
    channel[0]= (sbus_channel[0]-1000)/800.0*1000.0+3000.0; 
	  channel[1]= (sbus_channel[1]-1000)/800.0*1000.0+3000.0; 
	  channel[2]= (sbus_channel[2]-1000)/800.0*1000.0+3000.0; 
		channel[3]= (sbus_channel[3]-1000)/800.0*1000.0+3000.0; 
		
//		channel[0] = Clip(channel[0],2000,4000);
//		channel[1] = Clip(channel[1],2000,4000);
//		channel[2] = Clip(channel[2],2000,4000);
//		channel[3] = Clip(channel[3],2000,4000);
	
		if(channel[0]<1800||channel[0]>4200)channel[0]=3000;
		if(channel[1]<1800||channel[1]>4200)channel[1]=3000;
		if(channel[2]<1800||channel[2]>4200)channel[2]=3000;
		if(channel[3]<1800||channel[3]>4200)channel[3]=3000;
				
		Remoter.PitCtrler	= channel[1] ;
		Remoter.RolCtrler = channel[0] ;
		Remoter.ThrCtrler = channel[2] ;
		Remoter.YawCtrler = channel[3] ;	

	{
		TickType_t now = xTaskGetTickCount();
		if (sbus_last_valid_tick == 0U) {
			if (now > pdMS_TO_TICKS(500)) {
				sbus_lost = 1U;
			}
		} else {
			if ((now - sbus_last_valid_tick) > pdMS_TO_TICKS(500)) {
				sbus_lost = 1U;
			} else {
				sbus_lost = 0U;
			}
		}
	}
}

#define is_Stick_MAX(value)      ( value>3900 &&  value<4100)//4000
#define is_Stick_MIN(value)      ( value>1900 &&  value<2100)//2000
#define is_Stick_MID(value)      ( value>2900 &&  value<3100)//3000

void Check_Stick_Motion(void)
{
	if( is_Stick_MIN(Remoter.ThrCtrler) &&  is_Stick_MAX(Remoter.YawCtrler) )//  arm  右下
		StickMotion.LeftStick_RightDown_cnt++;
	else StickMotion.LeftStick_RightDown_cnt=0;
	
	if( is_Stick_MIN(Remoter.ThrCtrler) &&  is_Stick_MIN(Remoter.YawCtrler) )  // disarm
		StickMotion.LeftStick_LeftDown_cnt++;
	else StickMotion.LeftStick_LeftDown_cnt=0;
	
	if( is_Stick_MAX(Remoter.ThrCtrler) &&  is_Stick_MIN(Remoter.YawCtrler) )  // adjust
		StickMotion.LeftStick_LeftUp_cnt++;
	else StickMotion.LeftStick_LeftUp_cnt=0;

	if( is_Stick_MAX(Remoter.ThrCtrler) &&  is_Stick_MAX(Remoter.YawCtrler) )  // debug
		StickMotion.LeftStick_RightUp_cnt++;
	else StickMotion.LeftStick_RightUp_cnt=0;
	
	
	if( is_Stick_MIN(Remoter.PitCtrler) &&  is_Stick_MIN(Remoter.RolCtrler) )  // 
		StickMotion.RightStick_LeftDown_cnt++;
	else StickMotion.RightStick_LeftDown_cnt=0;
	
	if( is_Stick_MIN(Remoter.PitCtrler) &&  is_Stick_MAX(Remoter.RolCtrler) )  // 
		StickMotion.RightStick_RightDown_cnt++;
	else StickMotion.RightStick_RightDown_cnt=0;

	if( is_Stick_MAX(Remoter.PitCtrler) &&  is_Stick_MIN(Remoter.RolCtrler) )  // 
		StickMotion.RightStick_LeftUp_cnt++;
	else StickMotion.RightStick_LeftUp_cnt=0;

	if( is_Stick_MAX(Remoter.PitCtrler) &&  is_Stick_MAX(Remoter.RolCtrler) )  // 
		StickMotion.RightStick_RightUp_cnt++;
	else StickMotion.RightStick_RightUp_cnt=0;

	

	if(StickMotion.LeftStick_RightDown_cnt>=ARM_Delay_time)
	{
		DroneStatus.ARM_Status=Armed;//右下解锁

		StickMotion.LeftStick_RightDown_cnt=0;StickMotion.LeftStick_LeftDown_cnt=0;
	}
	if(StickMotion.LeftStick_LeftDown_cnt>=DISARM_Delay_time)
	{
		DroneStatus.ARM_Status=DisArmed;//左下上锁
		StickMotion.LeftStick_RightDown_cnt=0;StickMotion.LeftStick_LeftDown_cnt=0;
	}
}
/*************************************************************************
函 数 名：void Check_Fly_Mode(void)
函数功能：检查飞行状态
备    注：PA10(USART1_RX)
*************************************************************************/
void Check_Fly_Mode(void)
{
	static int DangerousStop_cnt = 0;
	Check_Stick_Motion();
	
		if( sbus_channel[4] ==200 ) //拨杆拨到了最上方
	{	
			DangerousStop_cnt ++;
	}
	else
	{
		DangerousStop_cnt = 0;
	}
	
	if(DangerousStop_cnt>10) //50ms
	{
		DroneStatus.FlyMode = FlyMode_DangerousStop;//紧急停机
		
	}	
	else
	{
     DroneStatus.FlyMode = FlyMode_SDK ;
	}
}

