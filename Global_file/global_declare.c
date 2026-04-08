#include "global_declare.h"

/*------------------------------------------------------
任务功能：存放全局变量
--------------------------------------------------------*/


SYSTEM_MONITOR system_monitor  =  {0}; //系统监视器

RemoterTypeDef  Remoter;               //遥控器

DroneStatusTypeDef DroneStatus;        //无人机状态

StickMotionTypeDef StickMotion;        //遥控器拨杆

volatile uint8_t sbus_lost = 0;
volatile uint32_t sbus_last_valid_tick = 0;
float virtual_rc_sticks[4] = {3000.0f, 3000.0f, 3000.0f, 3000.0f};
volatile uint8_t bench_mode_active = 0;

float gs_max_horizontal_speed_mps = 1.0f;
float gs_max_vertical_speed_mps = 1.0f;
float gs_max_pitch_deg = 15.0f;
float gs_max_roll_deg = 15.0f;
float gs_throttle_min_pct = 0.0f;
float gs_throttle_max_pct = 1.0f;

volatile uint8_t TWC_arrived = 0;

volatile SinusoidPath_t sinusoid_path = {0};

volatile CirclePath_t circle_path = {0};

volatile uint8_t GS_KeySDKflag = 0;


