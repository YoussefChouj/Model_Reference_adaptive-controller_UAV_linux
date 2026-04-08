#ifndef __global_dectare_h__
#define __global_dectare_h__

#include "stm32f4xx.h"
#include "robot_types.h"
 
#define ABS(x)   ( (x)>0?(x):-(x) ) 

#define   SBUS_OFFSET    100
#define   SBUS_THR_OFFSET    50

#define   SBUS_MID       1000
#define   SBUS_MAX       1800
#define   SBUS_MIN       200

//旧遥控器
//#define   SBUS_MID       1024
//#define   SBUS_MAX       1696
//#define   SBUS_MIN       352
#define   SBUS_CH_VALID(x)      ( ABS(x-SBUS_MID)>SBUS_OFFSET  )
#define   SBUS_THR_CH_VALID(x)      ( ABS(x-SBUS_MID)>SBUS_THR_OFFSET  ) 

#define Stick_to_MAX_Angle   18.0  //pitch roll 正负15度
#define Stick_to_MAX_Horizontal_Rate   100.0    //   cm/s
#define Stick_to_MAX_GyroZ            200.0   //  deg/s
#define Stick_to_MAX_V_height         1.0   //   m/s 
 
#define   value_limit(x,small,big)   if(x<small)x=small;if(x>big)x=big;
#define FlyMode_DangerousStop        0
#define FlyMode_SDK                  1     //SDK模式

#define ARM_Delay_time  150
#define DISARM_Delay_time  50// 50*20ms = 1s
#define DisArmed    0    //无人机解锁
#define Armed       1    //无人机上锁

#define   PI        3.14159f
#define DEG2RAD (PI / 180.0f)
#define RAD2DEG (180.0f / PI)
#define GRAVITY_MSS 9.80665f

typedef struct
{

	float temp_v_x;
	float temp_v_y;
	
	float flag1;
	float flag2;
	float flag3;
	float flag4;
	
	float t265posx;
	float t265posy;
	
	float yolo_d435i_x;
	float yolo_d435i_y;
	float yolo_d435i_z;
	float yolo_d435i_flag;
	float pos_flag;
	float init_flag;

} _linux_data_st;


typedef struct
{
	float yolo_d435i_x;
	float yolo_d435i_y;
	float yolo_d435i_z;
	
	float yolo_d435i_x_temp;
	float yolo_d435i_y_temp;
	float yolo_d435i_z_temp;
	
	float yolo_d435i_flag;
	float yolo_d435i_flag_cnt;
	float yolo_usb_x;
	float yolo_usb_y;
	float yolo_usb_flag;
	float yolo_usb_flag_cnt;
	
	float t265posx;
	float t265posy;
	float d435i_earth_x;
	float d435i_earth_y;
	
	float d435i_earth_x_filter;
	float d435i_earth_y_filter;
	
	float d435i_body_x;
	float d435i_body_y;
	
	float usb_earth_x;
	float usb_earth_y;
	float flag4;
	float init_flag;
	
	float d435i_des_x;
	float d435i_des_y;
	
	float total_x_des;
	float total_y_des;
	
	float stree_yaw_x;
	float stree_yaw_y;
	float stree_angle;
	
	float stree_angle_des;
	
} yolo_data;

typedef struct
{

	float pos_x;
	float pos_y;
	float v_x;
	float v_y;
	
	float flag1;
	float flag2;
	float flag3;
	float flag4;

} _linux_flag;


extern SYSTEM_MONITOR system_monitor;
extern RemoterTypeDef  Remoter; 
extern DroneStatusTypeDef DroneStatus; 
extern StickMotionTypeDef StickMotion;

/* Hybrid RC / computer control (see RemoterTask, StabilizerTask, send_data) */
extern volatile uint8_t sbus_lost;
extern volatile uint32_t sbus_last_valid_tick;
extern float virtual_rc_sticks[4];
extern volatile uint8_t bench_mode_active;

/* Ground-station safety limits (CMD 0x09, CMD 0x03 idx 8-9) */
extern float gs_max_horizontal_speed_mps;
extern float gs_max_vertical_speed_mps;
extern float gs_max_pitch_deg;
extern float gs_max_roll_deg;
extern float gs_throttle_min_pct;   /* 0..1 of PWM span above idle */
extern float gs_throttle_max_pct;   /* 0..1 of PWM span above idle */

/* TWC point-to-point: arrival flag (set in StabilizerTask Update_Des, sent in Frame A) */
extern volatile uint8_t TWC_arrived;

/* Sinusoidal path (CMD 0x0B, AutoflyTask_RunSinusoid) */
typedef struct {
	float center_x;
	float center_y;
	float center_z;
	float amplitude;
	float frequency;
	float duration;
	uint8_t axis;
	uint8_t active;
	float t_elapsed;
} SinusoidPath_t;

extern volatile SinusoidPath_t sinusoid_path;

/* Circle path (CMD 0x0C, AutoflyTask_RunCircle); t_elapsed tracks time for duration limit */
typedef struct {
	float center_x;
	float center_y;
	float center_z;
	float radius;
	float angular_speed;
	float duration;
	uint8_t active;
	float theta;
	float t_elapsed;
} CirclePath_t;

extern volatile CirclePath_t circle_path;

/* Ground station: parallel trigger for SDK state machine (see AutoflyTask, CMD 0x0E) */
extern volatile uint8_t GS_KeySDKflag;

#endif
