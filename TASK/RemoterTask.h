#ifndef __REMOTERTASK_H
#define __REMOTERTASK_H	 

#include "global_declare.h"
#include "usart1.h"
#include "GlobalUse_Basic_Function.h"
#include "usart2.h"
#include "imu_update.h"
#include "usart4.h"
#include "AutoflyTask.h"
#include "StabilizerTask.h"
#include "usart3.h"

#define  PITCH_CH    sbus_channel[1]
#define  ROLL_CH     sbus_channel[0]
#define  YAW_CH      sbus_channel[3]
#define  THR_CH      sbus_channel[2]

/////////////////////////////////////////////////////////////////////////////////////
//数据拆分宏定义，在发送大于1字节的数据类型时，比如int16、float等，需要把数据拆分成单独字节进行发送
#define BYTE0(dwTemp)       ( *( (char *)(&dwTemp)      ) )
#define BYTE1(dwTemp)       ( *( (char *)(&dwTemp) + 1) )
#define BYTE2(dwTemp)       ( *( (char *)(&dwTemp) + 2) )
#define BYTE3(dwTemp)       ( *( (char *)(&dwTemp) + 3) )
	

void remoter_task(void);
void Check_Fly_Mode(void);
void ANO_Report_UserData1(void);
void send_to_linux(void);

#endif
