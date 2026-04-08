#ifndef __RM_ROBOT_H__
#define __RM_ROBOT_H__

#include "data_types.h"
#include "stm32f4xx.h"

typedef struct 
{
  float Des;//控制变量目标值
  float FB;//控制变量反馈值
	
	float Kp;//比例系数Kp
	float Ki;//积分系数Ki
	float Kd;//微分系数Kd
	
	float Up;//比例输出
	float Ui;//积分输出
	float Ud;//微分输出
	
	float E;//本次偏差
	float PreE;//上次偏差
  float SumE;//总偏差
	float U;//本次PID运算结果
	
	float UMax;//PID运算后输出最大值及做遇限削弱时的上限值
	float UpMax;//比例项输出最大值
	float UiMax;//积分项输出最大值
	float UdMax;//微分项输出最大值
	float SumEMax;//积分饱和值
	float EMin;//积分分离阈值
}PIDTypeDef;

typedef struct 
{
	PIDTypeDef    pitchPID;
	PIDTypeDef    rollPID;
	PIDTypeDef    yawPID;
	PIDTypeDef    gyroxPID;
	PIDTypeDef    gyroyPID;
	PIDTypeDef    gyrozPID;
	PIDTypeDef    Z_posPID;
	PIDTypeDef    Z_ratePID;
	PIDTypeDef    locxPID;
	PIDTypeDef    locyPID;
	PIDTypeDef    locxsPID;
	PIDTypeDef    locysPID;
	
	PIDTypeDef   stree_yaw_speed ;
	PIDTypeDef   stree_pitch_speed ;
}CtrlerTypeDef;


typedef struct
{
	unsigned int LeftStick_LeftDown_cnt;
	unsigned int LeftStick_LeftUp_cnt;
	unsigned int LeftStick_RightDown_cnt;
	unsigned int LeftStick_RightUp_cnt;
	
	unsigned int RightStick_LeftDown_cnt;
	unsigned int RightStick_LeftUp_cnt;
	unsigned int RightStick_RightDown_cnt;
	unsigned int RightStick_RightUp_cnt;
}StickMotionTypeDef;


typedef struct
{
	unsigned int  PIDingDelayMS;
	unsigned char SensorsStatus;
	unsigned char AdjustStatus;
	unsigned char ARM_Status;
	unsigned char FlyMode;
	_Bool         Is_GetingGyroZero;

}DroneStatusTypeDef;


	typedef struct
{
	unsigned short System_cnt;
	double         System_cnt_100ms;
	unsigned short IMUSampleTask_fps;
	unsigned short IMUUpdateTask_fps;
	unsigned short stabilizerTask_fps;
	unsigned short remoter_task_fps;
	unsigned short USART1_task_fps;
	unsigned short USART2_task_fps;
	unsigned short USART4_task_fps;
	unsigned short USART5_task_fps;
	unsigned short AutoflyTask_fps;
	
	unsigned short IMUSampleTask_cnt;
	unsigned short IMUUpdateTask_cnt;
	unsigned short stabilizerTask_cnt;
	unsigned short remoter_task_cnt;
	unsigned short USART1_task_cnt;
	unsigned short USART2_task_cnt;
	unsigned short USART4_task_cnt;
	unsigned short USART5_task_cnt;
	unsigned short AutoflyTask_cnt;
}SYSTEM_MONITOR;

typedef struct
{
	unsigned short PitCtrler;
	unsigned short RolCtrler;
	unsigned short YawCtrler;
	unsigned short ThrCtrler;
	unsigned short DinggaoSwitch;
	unsigned short DingdianSwitch;
	unsigned short StopSwitch;
}RemoterTypeDef;

typedef struct
{
	USART_TypeDef* USARTx;            //串口
	DMA_Stream_TypeDef* DMAy_Streamx; //DMA数据流
	UCHAR8* pMailbox;                 //邮箱(有效数据)数组
  __IO UCHAR8* pDMAbuf;             //DMA数组
	USHORT16 MbLen;                   //mailbox长度
	USHORT16 DMALen;                  //DMA长度
	USHORT16 rxConter;                //本次DMA长度
	USHORT16 rxBufferPtr;             //上次的长度  长度也代表位置
  USHORT16 rxSize;                  //本次接收的长度
}USART_RX_TypeDef;

typedef struct
{
	FP32 rol;
	FP32 pit;
	FP32 yaw;
	FP32 wx;
	FP32 wy;
	FP32 wz;
}ST_IMU_DATA;
//视觉数据处理结构体


typedef union
{
	ST_IMU_DATA st_imu_data;
	u8 data[24];
}UN_IMU_DATA;

typedef struct
{
    float angle_180;
    float angle_180_pre;
    float angle_inf;
} ST_ANGLE;

typedef struct
{
	FP32 Kp;
	FP32 Ki;
	FP32 Kd;	
}PID_Param;


//陀螺仪
typedef enum {OFF = 0, ON = 1, TWINKLE = 2}LED_MODE;
typedef enum {INIT = 0, NORMAL = 1, CALIBRATION = 2}IMU_MODE;
typedef enum {LOOP = 0, IDENTIFY = 1}CTRL_MODE;

typedef struct
{
	float preout;
	float out;
	float in;
	float off_freq;
	float samp_tim;
}ST_LPF;



/*PID控制器结构体*/
typedef struct 
{
  FP32 fpDes;//控制变量目标值
  FP32 fpFB;//控制变量反馈值
	
	FP32 fpKp;//比例系数Kp
	FP32 fpKi;//积分系数Ki
	FP32 fpKd;//微分系数Kd
	
	FP32 fpUp;//比例输出
	FP32 fpUi;//积分输出
	FP32 fpUd;//微分输出
	
	FP32 fpE;//本次偏差
	FP32 fpPreE;//上次偏差
  FP32 fpSumE;//总偏差
	FP32 fpU;//本次PID运算结果
	
	FP32 fpUMax;//PID运算后输出最大值及做遇限削弱时的上限值
	FP32 fpEpMax;//比例项输出最大值
	FP32 fpEiMax;//积分项输出最大值
	FP32 fpEdMax;//微分项输出最大值
	FP32 fpEMin;//积分上限
}ST_PID;

typedef struct
{
	FP32 fpRawValue; //当前采样值
	FP32 fpPreRawValue; // 上次采样值
	FP32 fpDiff;  //两次采样偏差
	FP32 fpSumValue; //最终输出值
	FP32 fpOffsetValue; //标定复位值
	bool InitState; //初始化完成标志
}ST_GYRO;

typedef struct
{
	SINT32 Renew_FLAG;
	SINT32 Beat_State;
	FP32 Beat_Yaw;
	FP32 Beat_Pitch;
}ST_ENEMY_POS;

typedef union
{
	ST_ENEMY_POS stEnemyPos;	
	UCHAR8 ucPosData[16];
}UN_VIRTUAL_DATA;

typedef struct
{
	FP32 Is_Rcg_FLAG;  //led_flag
	FP32 E_Pitch;   //蜂鸣器
	FP32 E_Yaw;     //openmv
}ST_ENEMY_Aim;

typedef union
{
	ST_ENEMY_Aim stEnemyE;	
	UCHAR8 ucEData[12];
}UN_AIM_DATA;

typedef struct
{
	FP32 AimToPC;
	FP32 PitchToAim;	
	FP32 YawToAim;
}ST_SEND_ANGLE;

typedef union
{
	ST_SEND_ANGLE st_SendAngle;
	UCHAR8 ucPitchData[12]; 
}Send_Aim_DATA;

typedef union
{
	FP32 VisualState;
	UCHAR8 ucStateData[4];
}SEND_VISUAL_STATE;


typedef struct
{
	double raw_value;
	double xbuf[18];
	double ybuf[18];
	double filtered_value;
}Filter_t;



typedef struct
{
	USHORT16 TxHead1;
	USHORT16 TxHead2;
  FP32 data[10];
  USHORT16 TxTail1;
	USHORT16 TxTail2;
}ST_OFFLINE_TX_BUF;

typedef union
{
	ST_OFFLINE_TX_BUF st_usart_tx_buf;
	UCHAR8 ucdata[48];
}UN_OFFLINE_TX_BUF;


typedef struct
{
  float raw_value;
  float filtered_value[2];
  float xhat_data[2], xhatminus_data[2], z_data[2],Pminus_data[4], K_data[4];
  float P_data[4];
  float AT_data[4], HT_data[4];
  float A_data[4];
  float H_data[4];
  float Q_data[4];
  float R_data[4];
} kalman_filter_init_t;


//typedef struct
//{
//	FP32 x1;
//	FP32 x2;
//	FP32 x;
//	FP32 r;
//	FP32 h;
//	FP32 aim;
//}TD;

enum
{
	X = 0,
	Y = 1,
	Z = 2,
	VEC_XYZ,
};

typedef struct
{
	float q0;//q0;
	float q1;//q1;
	float q2;//q2;
	float q3;//q3;
	
	float gkp;
	float gki;

	float x_vec[VEC_XYZ];
	float y_vec[VEC_XYZ];
	float z_vec[VEC_XYZ];

	float a_acc[VEC_XYZ];
	float gacc_deadzone[VEC_XYZ];
	float gra_acc[VEC_XYZ];
	
	float rol;
	float pit;
	float yaw;
} _imu_st ;



#endif
