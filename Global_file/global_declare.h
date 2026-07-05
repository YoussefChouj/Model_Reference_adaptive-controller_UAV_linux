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

//��ң����
//#define   SBUS_MID       1024
//#define   SBUS_MAX       1696
//#define   SBUS_MIN       352
#define   SBUS_CH_VALID(x)      ( ABS(x-SBUS_MID)>SBUS_OFFSET  )
#define   SBUS_THR_CH_VALID(x)      ( ABS(x-SBUS_MID)>SBUS_THR_OFFSET  ) 

#define Stick_to_MAX_Angle   18.0f
#define Stick_to_MAX_Horizontal_Rate   100.0f   //   cm/s
#define Stick_to_MAX_GyroZ            200.0f   //  deg/s
#define Stick_to_MAX_V_height         1.0f   //   m/s
 
#define   value_limit(x,small,big)   if(x<small)x=small;if(x>big)x=big;
#define FlyMode_DangerousStop        0
#define FlyMode_SDK                  1     //SDKģʽ

/* Ground-station protocol version (uint8, appended as last byte of Frame A payload).
 * Increment when the frame layout or CMD semantics change. Must match GS_PROTO_VERSION
 * in ground_station/comm/serial_bridge.py. v8: bench frame 0x04 payload grew 12->20 B (4x u16 RPM). */
#define GS_PROTO_VERSION             8U

#define ARM_Delay_time  150
#define DISARM_Delay_time  50// 50*20ms = 1s
#define DisArmed    0    //���˻�����
#define Armed       1    //���˻�����

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

/* Hybrid RC / computer control (see RemoterTask, rc_input) */
extern volatile uint8_t sbus_lost;
extern volatile uint32_t sbus_last_valid_tick;
extern volatile uint8_t bench_mode_active;

/* Motor bench-test mode (CMD 0x16, DISARMED-only) — drives a single chosen motor
 * to a commanded CCR for the thrust-stand experiment (docs/bench_characterization.md).
 * WRITTEN BY: send_data.c CMD 0x16 (active/id/ccr) and StabilizerTask (dead-man clears active).
 * READ BY: StabilizerTask Update_Motor (actuator drive) and send_data.c frame 0x04. */
extern volatile uint8_t  motor_test_active;    /* 1 = bench test is driving a motor */
extern volatile uint8_t  motor_test_id;        /* 1..4 = M1..M4 (0 = none) */
extern volatile uint16_t motor_test_ccr;       /* commanded CCR, clamped [2000,4000] */
extern volatile uint32_t motor_test_watchdog;  /* ticks since last heartbeat (stabilizer-owned dead-man) */

/* Ground-station safety limits.
 * WRITTEN BY: send_data.c CMD 0x09 (speeds/angles) and CMD 0x03 idx 8-9 (throttle).
 * READ BY: StabilizerTask (accel_to_lean_angles, Update_v_h_Des, PWM clamp).
 * All are 32-bit floats — single stores are atomic on Cortex-M4; no critical section needed. */
extern float gs_max_horizontal_speed_mps;
extern float gs_max_vertical_speed_mps;
extern float gs_max_pitch_deg;
extern float gs_max_roll_deg;
extern float gs_throttle_min_pct;   /* 0..1 of PWM span above idle */
extern float gs_throttle_max_pct;   /* 0..1 of PWM span above idle */

/* TWC point-to-point: arrival flag (set in StabilizerTask Update_Des, sent in Frame A) */
extern volatile uint8_t TWC_arrived;


/* Set by RemoterTask on SBUS ch7 rising edge to command fly-up to Z=0.5 m.
 * Cleared by StabilizerTask after loading TWC target. */
extern volatile uint8_t sbus_flyup_trigger;

/* Set by RemoterTask on SBUS channel 8 rising edge to trigger preset path launch.
 * Cleared by the path execution handler after processing. */
extern volatile uint8_t sbus_path_trigger;

/* Sinusoidal path parameters.
 * WRITTEN BY: send_data.c CMD 0x0B handler (RemoterTask context).
 *   Config fields (center_x/y/z, amplitude, frequency, duration, axis): single
 *   float/uint8 writes — naturally atomic on Cortex-M4.
 *   Activation (active=1 + t_elapsed=0): taskENTER_CRITICAL guard required
 *   because AutoflyTask can preempt between the two stores.
 * READ/MUTATED BY: AutoflyTask_RunSinusoid (t_elapsed, active), AutoflyTask_PathArbitrate (active).
 * READ FOR TELEMETRY BY: send_data.c Frame B path tail (active, t_elapsed, theta). */
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

/* Circle path parameters.
 * WRITTEN BY: send_data.c CMD 0x0C handler (RemoterTask context).
 *   Config fields: naturally atomic. Activation (active=1 + theta=0 + t_elapsed=0):
 *   taskENTER_CRITICAL guard required.
 * READ/MUTATED BY: AutoflyTask_RunCircle (theta, t_elapsed, active), AutoflyTask_PathArbitrate (active).
 * READ FOR TELEMETRY BY: send_data.c Frame B path tail (active, theta, t_elapsed). */
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

/* Figure-8 (lemniscate) path parameters. CMD 0x11. FlyMode_SDK only.
 * type: 0 = Bernoulli (lying infinity), 1 = Gerono (vertical figure-8).
 * Same concurrency rules as circle_path (taskENTER_CRITICAL on activation). */
typedef struct {
	float center_x;
	float center_y;
	float center_z;
	float amplitude;      /* A, metres */
	float angular_speed;  /* rad/s, advances theta */
	float duration;       /* s, 0 = run until aborted */
	uint8_t type;         /* 0 = Bernoulli, 1 = Gerono */
	uint8_t active;
	float theta;
	float t_elapsed;
} Figure8Path_t;

extern volatile Figure8Path_t figure8_path;

/* Shared waypoint-density spacing (reference quantization), metres. CMD 0x12 idx 0.
 * 0 = continuous reference. Applied to sinusoid/circle/figure-8 via a reference
 * arc-length accumulator in AutoflyTask (see AutoflyTask_CommitRef). */
extern volatile float waypoint_spacing;
extern void AutoflyTask_WaypointReset(void);

/* Ground station: parallel trigger for SDK state machine (see AutoflyTask, CMD 0x0E) */
extern volatile uint8_t GS_KeySDKflag;

#endif
