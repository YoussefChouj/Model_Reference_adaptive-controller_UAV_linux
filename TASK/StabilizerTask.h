#ifndef _STABILIZERTASK__H_
#define _STABILIZERTASK__H_

#include "algorithm.h"
#include "robot_types.h"
#include "pid.h"
#include "pwm.h"
#include "global_declare.h"
#include "imu_update.h"
#include "bmi088_driver.h"
#include "Ano_OF.h"
#include "tf_mini_plus.h"
#include "AutoflyTask.h"
#include "stm32f4xx_it.h"
#include "SINS.h"
#include "usart4.h"
#include "GPS.h"

#define case_Update_loc_Des          1
#define case_Update_v_loc_Des        2
#define case_Update_height_Des       3
#define case_Update_v_h_Des          4
#define case_Update_pitrol_Des       5
#define case_Update_yaw_Des          6
#define case_Update_gyro_Des         7

#define REAL   float
#define TAN_MAP_SIZE    256
#define TAN_MAP_RES     0.003921569f     /* (smallest non-zero value in table) */

void stabilizer_Task(void);
void Update_Motor(void); 
void Compute_Motor(void);
void Update_Des(unsigned char which_level);
void Update_Data(void);
void accel_to_lean_angles(float acc_tar_forward,float acc_tar_right,float *tar_pitch,float *tar_roll);

void Get_Voltage(void);
	
float Constrain_Float(float amt, float low, float high);
float fast_atan(float v);
REAL fast_atan2(REAL y, REAL x);

typedef struct 
{
float target_x;//设定目标点x坐标
float target_y;//设定目标点y坐标
float target_z;//设定目标点z坐标
float world_x; //真实世界坐标
float world_y; //真实世界坐标
float world_z; //真实世界坐标
int execute;//置0可以修改目标坐标，置1飞行器飞向目标	
float set_yaw;//设定偏航角
float real_yaw;//实际偏航角
}TargetSet_WorldReal_Coordinate;
extern TargetSet_WorldReal_Coordinate TWC;

extern float real_voltage; //测量电池实际电压
extern float earth_x;
extern float earth_y;
extern float Cos_Yaw_01;
extern int track_fly_mode;

#endif

