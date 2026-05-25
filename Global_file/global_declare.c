#include "global_declare.h"

/*------------------------------------------------------
�����ܣ����ȫ�ֱ���
--------------------------------------------------------*/


SYSTEM_MONITOR system_monitor  =  {0}; //ϵͳ������

RemoterTypeDef  Remoter;               //ң����

DroneStatusTypeDef DroneStatus;        //���˻�״̬

StickMotionTypeDef StickMotion;        //ң��������

volatile uint8_t sbus_lost = 0;
volatile uint32_t sbus_last_valid_tick = 0;
volatile uint8_t bench_mode_active = 0;

float gs_max_horizontal_speed_mps = 1.0f;
float gs_max_vertical_speed_mps = 1.0f;
float gs_max_pitch_deg = 15.0f;
float gs_max_roll_deg = 15.0f;
float gs_throttle_min_pct = 0.0f;
float gs_throttle_max_pct = 1.0f;

volatile uint8_t TWC_arrived = 0;
volatile uint8_t drone_mode = 1;      /* start in FLY mode */
volatile uint8_t sbus_flyup_trigger = 0;

volatile uint8_t sbus_path_trigger = 0;

volatile SinusoidPath_t sinusoid_path = {0};

volatile CirclePath_t circle_path = {0};

volatile uint8_t GS_KeySDKflag = 0;


