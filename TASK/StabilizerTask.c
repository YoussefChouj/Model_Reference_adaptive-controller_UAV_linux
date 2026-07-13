#include "StabilizerTask.h"
#include "math.h"
#include "pid.h"
#include "ADC.h"
#include "mrac.h"
#include "gyro_filter.h"
#include "sysid.h"
#include "rc_input.h"
#include "flight_fsm.h"

/**
 * @module  StabilizerTask.c
 * @subsystem  control
 * @depends  StabilizerTask.h, pid.h, ADC.h, mrac.h
 * @owns  state update, setpoint update, motor mixing, and arm-mode motor output gating
 * @caution  mixer sign conventions and motor channel ordering are safety critical
 */
unsigned char cnt_h,cnt_loc,cnt_locs,cnt_yaw;
float Throttle_out,u_gyrox,u_gyroy,u_gyroz;
short Throttle_th = 2200;

/* LAND setpoint ramp: 0.0015 m/tick at 200 Hz = 0.30 m/s descent rate.
 * PID follows the setpoint to ground — no throttle ramp needed.
 * Touchdown detected by Z_ratePID.FB → 0 on frame contact. */
#define LAND_DES_STEP   0.0015f
/* Safety net: 2000 ticks at 200 Hz = 10 s max landing time before forced disarm. */
#define LAND_MAX_TICKS  2000U
/* Motor bench-test dead-man: stabilizer runs at 200 Hz, so 100 ticks = 500 ms.
 * If the dashboard stops sending CMD 0x16 heartbeats, motors are zeroed. */
#define MOTOR_TEST_DEADMAN_TICKS  100U
float Cos_Yaw_01= 0;
float Sin_Yaw_01= 0;

float Sin_roll_01= 0;
float Cos_roll_01= 0;
float Sin_pitch_01= 0;
float Cos_pitch_01= 0;
//
TargetSet_WorldReal_Coordinate TWC;

/* Accumulated near-ground sink bias (m/s). Ramps up while drone is stuck against
 * ground effect; adapts to battery voltage without needing voltage measurement.
 * Reset on every landing exit so it starts fresh each attempt. */
static float s_land_sink_bias = 0.0f;

/* OF velocity-bias calibration (docs/tracking_baseline_and_drift.md, mitigation #1).
 * of2_dx_fix/of2_dy_fix carry a small constant offset (measured ~12-14 / ~2-3 raw
 * units on the bench) that integrates into unbounded locx/locyPID.FB drift.
 *
 * Gated on quiescence rather than the arm edge: arming (stick gesture) happens
 * before the drone is physically settled (still being placed/held), so a fixed
 * 2 s window starting at arm captures placement motion, not the true bias
 * (confirmed on the bench 2026-07-12 — drift was unchanged by an arm-edge-triggered
 * version of this calibration).
 *
 * "Quiescent" = gyro rate below OF_BIAS_STILL_THRESH_RADPS on all 3 axes AND
 * pitch/roll RC sticks centered (RCInput_IsActive false) — the same condition
 * under which case_Update_loc_Des already latches locxPID.Des = locxPID.FB
 * (StabilizerTask.c ~line 629), i.e. the moments position hold assumes the drone
 * is holding still. Requiring sticks-centered (not just gyro-still) avoids folding
 * a real, constant-velocity manual translation into the bias estimate.
 *
 * Once OF_BIAS_STILL_TICKS of quiescence is seen, average of2_dx_fix/dy_fix for
 * OF_BIAS_CAL_TICKS; if quiescence breaks mid-average, discard and re-wait. Unlike
 * a one-shot arm-time calibration, completing a window does NOT freeze the bias —
 * it goes back to waiting so the next quiescent moment (e.g. every time the pilot
 * releases the sticks to hover) refreshes it, tracking the slow thermal drift
 * observed on the bench (~13% bias drift over 13 min) throughout a flight instead
 * of only at t=0. */
#define OF_BIAS_STILL_THRESH_RADPS  0.05236f /* ~3 deg/s */
#define OF_BIAS_STILL_TICKS         100U     /* 100 ticks @ 200 Hz = 0.5 s settled before starting */
#define OF_BIAS_CAL_TICKS           400U     /* 400 ticks @ 200 Hz = 2.0 s averaging window */
typedef enum { OF_BIAS_WAIT_STILL = 0, OF_BIAS_ACCUMULATING = 1 } OfBiasState_t;
static u8            s_of_bias_prev_armed = 0;
static OfBiasState_t s_of_bias_state      = OF_BIAS_WAIT_STILL;
static u16           s_of_bias_still_tick = 0;
static u16           s_of_bias_cal_tick   = 0;
static float s_of_bias_sum_x = 0.0f, s_of_bias_sum_y = 0.0f;
/* Non-static: streamed in the 0x05 OF-calibration frame (send_data.c) to validate the v3
 * bias against an offline-derived Kalman estimate. See docs/tracking_baseline_and_drift.md. */
float s_of_bias_x = 0.0f, s_of_bias_y = 0.0f;

//
void stabilizer_Task(void)
{
	 Check_Fly_Mode(); //�ж����˻���״̬
	
	 Update_Data();
	 
	 Compute_Motor();
	 
	 Update_Motor();
	
//	 Get_Voltage();//�����ѹ

} 

/*************************************************************************
�� �� ����void Update_Data(void);
�������ܣ����·���ֵ
��    ע��
*************************************************************************/
void Update_Data(void)
{
	
	Cos_Yaw_01=cos(-imu_data.yaw* DEG2RAD);
	Sin_Yaw_01=sin(-imu_data.yaw* DEG2RAD);
	
	Cos_roll_01=cos(imu_data.rol* DEG2RAD);
	Sin_roll_01 = sin(imu_data.rol* DEG2RAD);
	Cos_pitch_01=cos(imu_data.pit* DEG2RAD);
	Sin_pitch_01 = sin(imu_data.pit* DEG2RAD);
	
	//////////////////λ�û�����ֵ����/////////////////////////
		{
			u8 armed_now = (DroneStatus.ARM_Status == Armed);
			if (armed_now && !s_of_bias_prev_armed) {
				/* Just armed: (re)start the stillness-gated calibration sequence. */
				s_of_bias_state      = OF_BIAS_WAIT_STILL;
				s_of_bias_still_tick = 0;
				s_of_bias_cal_tick   = 0;
				s_of_bias_sum_x = 0.0f;
				s_of_bias_sum_y = 0.0f;
			}
			s_of_bias_prev_armed = armed_now;

			if (armed_now) {
				u8 is_quiescent = (fabsf(Gyro_X_Real) < OF_BIAS_STILL_THRESH_RADPS)
				               && (fabsf(Gyro_Y_Real) < OF_BIAS_STILL_THRESH_RADPS)
				               && (fabsf(Gyro_Z_Real) < OF_BIAS_STILL_THRESH_RADPS)
				               && !RCInput_IsActive(RC_AXIS_PITCH)
				               && !RCInput_IsActive(RC_AXIS_ROLL);

				if (s_of_bias_state == OF_BIAS_WAIT_STILL) {
					s_of_bias_still_tick = is_quiescent ? (s_of_bias_still_tick + 1U) : 0U;
					if (s_of_bias_still_tick >= OF_BIAS_STILL_TICKS) {
						s_of_bias_state = OF_BIAS_ACCUMULATING;
						s_of_bias_cal_tick = 0;
						s_of_bias_sum_x = 0.0f;
						s_of_bias_sum_y = 0.0f;
					}
				} else { /* OF_BIAS_ACCUMULATING */
					if (!is_quiescent) {
						/* Motion resumed before the window finished: discard and re-wait. */
						s_of_bias_state      = OF_BIAS_WAIT_STILL;
						s_of_bias_still_tick = 0;
					} else {
						s_of_bias_sum_x += (float)ano_of.of2_dx_fix;
						s_of_bias_sum_y += (float)ano_of.of2_dy_fix;
						s_of_bias_cal_tick++;
						if (s_of_bias_cal_tick >= OF_BIAS_CAL_TICKS) {
							s_of_bias_x = s_of_bias_sum_x / (float)OF_BIAS_CAL_TICKS;
							s_of_bias_y = s_of_bias_sum_y / (float)OF_BIAS_CAL_TICKS;
							/* Refreshed, not frozen: go back and look for the next
							 * quiescent window so slow bias drift keeps getting tracked. */
							s_of_bias_state      = OF_BIAS_WAIT_STILL;
							s_of_bias_still_tick = 0;
						}
					}
				}
			}
		}
		{
			float of_dx_deb = ano_of.of2_dx_fix - s_of_bias_x;
			float of_dy_deb = ano_of.of2_dy_fix - s_of_bias_y;

			ano_of.DISTANCE_X = ano_of.DISTANCE_X+of_dx_deb*0.005f;
			ano_of.DISTANCE_Y = ano_of.DISTANCE_Y+of_dy_deb*0.005f;

			//��������������ϵ�µ�ֵ
			ano_of.earth_x = ano_of.earth_x + (of_dx_deb*0.005f*Cos_Yaw_01 + of_dy_deb*0.005f*Sin_Yaw_01 );

			ano_of.earth_y = ano_of.earth_y + (of_dy_deb*0.005f*Cos_Yaw_01 - of_dx_deb*0.005f*Sin_Yaw_01 );
		}
	  ano_of.earth_x_ture  =  ano_of.earth_y;
	  ano_of.earth_y_ture  =  -ano_of.earth_x;
	
	  Ctrler.locxPID.FB= ano_of.earth_x_ture ;  //��������ϵ��
	  Ctrler.locyPID.FB= ano_of.earth_y_ture ; //x (����)<----
		//                                                     |
		//                                                     | y(����)
		//�����Դ�ʩ  //t265���װ�Ĵ���
//		if(linux_data.t265posy>-1000000.0f && linux_data.t265posy<1000000.0f)
//		{
//			Ctrler.locxPID.FB= linux_data.t265posy  ;  //��������ϵ��	
//		}
//		if(linux_data.t265posx>-1000000.0f && linux_data.t265posx<1000000.0f)
//		{
//			Ctrler.locyPID.FB= -linux_data.t265posx ;
//		}
		
	//�����ٶȷ���                                                    ^y(����)
//	  Ctrler.locxsPID.FB= ano_of.of2_dy;                           |
//    Ctrler.locysPID.FB= -ano_of.of2_dx;   //��������ϵ��          |-->x(����)          

		Ctrler.locxsPID.FB= (ano_of.of2_dy) *Cos_Yaw_01 +(-ano_of.of2_dx)*Sin_Yaw_01;
    Ctrler.locysPID.FB=  (-ano_of.of2_dx) * Cos_Yaw_01 - (ano_of.of2_dy)*Sin_Yaw_01; //��������ϵ��
	
	  if( ano_of.of_alt_cm>0.5f &&ano_of.of_alt_cm<500.0f)
		{
			ano_of.of2_raw_h = ano_of.of_alt_cm*0.01f*Cos_roll_01*Cos_pitch_01;
		}
	
	ano_of.of2_h =ano_of.of2_raw_h; 
	ano_of.of2_h_v = (ano_of.of2_h - ano_of.of2_last_h )/(0.005f);  //����ʱ��5ms
	ano_of.of2_last_h = ano_of.of2_h;
  ano_of.of2_h_f2_v  = ano_of.of2_h_f2_v  *0.9f +ano_of.of2_h_v *0.1f;
	 
	Ctrler.Z_posPID.FB =  ano_of.of2_h;
	Ctrler.Z_ratePID.FB = ano_of.of2_h_f2_v ;
	
	////////////////////��̬���Ƕ�ֵ����//////////////////////////////////  
	
	Ctrler.pitchPID.FB = -imu_data.pit  ;
	Ctrler.rollPID.FB  = imu_data.rol ;
	Ctrler.yawPID.FB   = -imu_data.yaw;

	// Phase-1 gyro low-pass (default pass-through; enable via CMD 0x15). Filters the rate FB that
	// the rate PID, MRAC, and the system-ID frame all consume — see API/gyro_filter.c / ADR-0004.
	Ctrler.gyroyPID.FB = GyroFilter_Apply(GYRO_FILT_PITCH, -Gyro_Y_Real*RAD2DEG);
	Ctrler.gyroxPID.FB = GyroFilter_Apply(GYRO_FILT_ROLL,   Gyro_X_Real*RAD2DEG);
	Ctrler.gyrozPID.FB = GyroFilter_Apply(GYRO_FILT_YAW,   -Gyro_Z_Real*RAD2DEG);
	
}
/*************************************************************************
�� �� ����void Update_Motor(void);
�������ܣ������ĸ������״̬
��    ע��
*************************************************************************/
void Update_Motor(void)
{
    static uint8_t  s_land_init    = 0U;
    static int      s_stable_ticks = 0;
    static uint16_t s_land_timeout = 0U;

    FlightState_t state = FlightFSM_GetState();

    /* Motor bench-test override (CMD 0x16): drive ONE chosen motor to a commanded CCR
     * for the thrust-stand experiment. Strictly DISARMED-only, with a dead-man — if the
     * dashboard stops sending heartbeats (watchdog exceeds the window) or anything leaves
     * DISARMED, motors are zeroed and test mode exits. RC/arming stays the final authority.
     * Set_PWM_Motors() applies the [2000,4000] clamp. See docs/bench_characterization.md. */
    if (motor_test_active)
    {
        if (state != FLIGHT_STATE_DISARMED ||
            ++motor_test_watchdog > MOTOR_TEST_DEADMAN_TICKS)
        {
            motor_test_active = 0U;
            Set_Zero_Motors();
            return;
        }
        mymotor.motor1 = (motor_test_id == 1U) ? (short)motor_test_ccr : Motor_PWM_ZERO;
        mymotor.motor2 = (motor_test_id == 2U) ? (short)motor_test_ccr : Motor_PWM_ZERO;
        mymotor.motor3 = (motor_test_id == 3U) ? (short)motor_test_ccr : Motor_PWM_ZERO;
        mymotor.motor4 = (motor_test_id == 4U) ? (short)motor_test_ccr : Motor_PWM_ZERO;
        Set_PWM_Motors();
        return;
    }

    if (state == FLIGHT_STATE_ARMED)
    {
        if (flight_phase == FLIGHT_PHASE_LANDING)
        {
            if (!s_land_init)
            {
                s_stable_ticks = 0;
                s_land_timeout = 0U;
                s_land_init    = 1U;
            }

            /* PID-controlled descent: Z_posPID.Des ramps down in case_Update_height_Des
             * at 0.30 m/s; rate cascade follows; Throttle_out drives motors to ground.
             * Integrator winds negative during descent so Throttle_out is already below
             * hover at touchdown — no motor spike when LANDED fires. */
            Set_PWM_Motors();

            /* Touchdown detection: rate stable for 0.25 s AND near ground.
             * Below 0.20 m a 0.15 m/s sink bias is active, so widen threshold to
             * 0.08 m/s — the drone decelerates through that on contact.
             * Above 0.20 m keep tight (0.02 m/s) to avoid false triggers mid-descent.
             * Safety net: force disarm after LAND_MAX_TICKS (10 s) regardless. */
            {
                float rate_thr = (Ctrler.Z_posPID.FB < 0.20f) ? 0.08f : 0.02f;
                if (fabsf(Ctrler.Z_ratePID.FB) < rate_thr)
                    s_stable_ticks++;
                else
                    s_stable_ticks = 0;
            }

            s_land_timeout++;

            if ((s_stable_ticks >= 10 && Ctrler.Z_posPID.FB < 0.15f) ||
                s_land_timeout >= LAND_MAX_TICKS)
            {
                s_stable_ticks    = 0;
                s_land_timeout    = 0U;
                s_land_init       = 0U;
                s_land_sink_bias  = 0.0f;
                flight_phase      = FLIGHT_PHASE_LANDED;
                FlightFSM_Event(FLIGHT_EVENT_DISARM_REQUEST);
                Set_Zero_Motors();
            }
        }
        else if (flight_phase == FLIGHT_PHASE_GROUND_IDLE)
        {
            /* Auto-detect takeoff: transition to FLYING once airborne. */
            if (Ctrler.Z_posPID.FB > 0.2f)
                flight_phase = FLIGHT_PHASE_FLYING;

            /* IDLE motors: hold until pilot or policy pushes THR above 20%. */
            if (!TWC.execute && RCInput_Get(RC_AXIS_THR) < 0.2f)
                Set_IDLE_Motors();
            else if (SDK_DelayWakeFlag == 1)
                Set_IDLE_Motors();
            else
                Set_PWM_Motors();
        }
        else if (flight_phase == FLIGHT_PHASE_FLYING)
        {
            Set_PWM_Motors();
        }
        /* FLIGHT_PHASE_LANDED: disarm was issued this tick; do nothing — motors
         * were already zeroed by the LANDING block that triggered this transition. */
    }
    else if (state == FLIGHT_STATE_EMERGENCY)
    {
        s_land_init      = 0U;
        s_stable_ticks   = 0;
        s_land_timeout   = 0U;
        s_land_sink_bias = 0.0f;
        Set_Zero_Motors();
    }
    else   /* DISARMED */
    {
        s_land_init      = 0U;
        s_stable_ticks   = 0;
        s_land_timeout   = 0U;
        s_land_sink_bias = 0.0f;
        TWC.execute = 0U;
        sbus_flyup_trigger = 0U;
        SDK_StateMachine_Init();
        Clear_Structure();
        Set_Zero_Motors();
    }
}
//������У׼�������
//   if( DroneStatus.FlyMode == FlyMode_SDK   )//SDKģʽ	
//			{
//				 if(sbus_channel[5] >=1000) 
//				 {
//				   mymotor.motor1 = 4000;
//				   mymotor.motor2 = 4000;
//					 mymotor.motor3 = 4000;
//					 mymotor.motor4 = 4000;
//				 }
//				 else if(sbus_channel[5] <=500)
//				 {
//				   mymotor.motor1 = 2000;
//				   mymotor.motor2 = 2000;
//					 mymotor.motor3 = 2000;
//					 mymotor.motor4 = 2000;
//				 }
//				Set_PWM_Motors();
//			}
//		else 
//		{
//		  Clear_Structure();
//			Set_Zero_Motors();
//		}
//}
/*************************************************************************
�� �� ����void Compute_Motor(void);
�������ܣ�����PID����
��    ע��
*************************************************************************/
void Compute_Motor(void)
{
////////////////����߶�����//////////////////////////////////////////////////////////
				
	Update_Des(case_Update_height_Des);  
	cnt_h++;
	if(cnt_h>=2)
	{
		ComputePID(&Ctrler.Z_posPID);
		cnt_h=0;
	}
  Update_Des(case_Update_v_h_Des);
	ComputePID(&Ctrler.Z_ratePID);


	cnt_loc++;
	if(cnt_loc>=2)
	{
	Update_Des(case_Update_loc_Des);
	ComputePID(&Ctrler.locxPID);
	ComputePID(&Ctrler.locyPID);
		
  cnt_loc=0;
  Update_Des(case_Update_v_loc_Des);
	SDK_Set_V_Loc();//������

	ComputePID(&Ctrler.locxsPID);
	ComputePID(&Ctrler.locysPID);
  }
	
//////////////////////������̬����////////////////////////////////////////////////////////////
	
	Update_Des(case_Update_pitrol_Des);  //����pit��roll�Ƕ�ֵ
	ComputePID(&Ctrler.pitchPID);
	ComputePID(&Ctrler.rollPID);
	
	Update_Des(case_Update_yaw_Des);    //����yaw�ĽǶ�
	ComputeYawPID(&Ctrler.yawPID);
	
	
	Update_Des(case_Update_gyro_Des);   //���½��ٶ�
	
	SDK_Set_Gyroz();

	// SysID excitation (ADR-0004): tick the signal generator + safety FSM, then SUPERIMPOSE the
	// excitation onto the active axis's RATE setpoint with += (closed-loop SysID). The outer
	// angle/position cascade stays live, so position hold keeps the drone on station (it wiggles in
	// place instead of translating open-loop and walking out of the green zone). Pitch/roll/yaw here;
	// Z is injected at the Z_ratePID.Des site. No-op while the FSM is IDLE.
	// NOTE: the rate setpoint now = outer-loop output + dither, so the logged `r`/`u` are closed-loop
	// signals. Plant ID is done offline with the direct method (Phi_xu/Phi_uu) on u_nom+u_ad -> x.
	SysID_Update();
	if (SysID_IsAxisActive(SYSID_AXIS_PITCH)) Ctrler.gyroyPID.Des += SysID_GetRateSetpoint(SYSID_AXIS_PITCH);
	if (SysID_IsAxisActive(SYSID_AXIS_ROLL))  Ctrler.gyroxPID.Des += SysID_GetRateSetpoint(SYSID_AXIS_ROLL);
	if (SysID_IsAxisActive(SYSID_AXIS_YAW))   Ctrler.gyrozPID.Des += SysID_GetRateSetpoint(SYSID_AXIS_YAW);

	ComputePID(&Ctrler.gyroxPID);
	ComputePID(&Ctrler.gyroyPID);
	ComputePID(&Ctrler.gyrozPID);
	
	// Execute MRAC after all PID controllers have computed their nominal outputs (u_nom)
	// MRAC uses the current PID rates, references, and nominal outputs to learn and compute u_ad.
	MRAC_Control(&Ctrler);
	
 

	 //Throttle_th=2800+(16.70f-real_voltage)*105.5f;  //4s������+d435i+t265+orin  
	 Throttle_th=2950;

#if ENABLE_MRAC_OUTPUT_INJECTION == 1
	// Runtime shadow-mode gate (mrac_flags.output_injection_on, CMD 0x0F idx 10).
	// When OFF the motors see pure PID even though MRAC keeps learning/logging u_ad.
	if (mrac_flags.output_injection_on) {
		// Inject MRAC adaptive signals.
		// u_total = u_nom + (u_ad * scaling_factor)
		// NaN/Inf guard: if u_ad is not finite (e.g. due to diverged adaptive weights),
		// fall back to zero correction so the PID baseline always reaches the motors.
		float mrac_z     = mrac_state.z_rate.u_ad * mrac_config_z.mrac_to_mixer;
		float mrac_roll  = mrac_state.roll.u_ad  * mrac_config_roll.mrac_to_mixer;
		float mrac_pitch = mrac_state.pitch.u_ad * mrac_config_pitch.mrac_to_mixer;
		float mrac_yaw   = mrac_state.yaw.u_ad   * mrac_config_yaw.mrac_to_mixer;
		if (!isfinite(mrac_z))     mrac_z     = 0.0f;
		if (!isfinite(mrac_roll))  mrac_roll  = 0.0f;
		if (!isfinite(mrac_pitch)) mrac_pitch = 0.0f;
		if (!isfinite(mrac_yaw))   mrac_yaw   = 0.0f;
		Throttle_out = Ctrler.Z_ratePID.U + Throttle_th + mrac_z;
		u_gyrox      = Ctrler.gyroxPID.U  + mrac_roll;
		u_gyroy      = -(Ctrler.gyroyPID.U + mrac_pitch); // Motor mixer needs gyroy reversed
		u_gyroz      = Ctrler.gyrozPID.U  + mrac_yaw;
	} else {
		// Runtime shadow mode: MRAC computes silently, motors see normal PID output.
		Throttle_out = Ctrler.Z_ratePID.U + Throttle_th;
		u_gyrox  = Ctrler.gyroxPID.U;
		u_gyroy  = -Ctrler.gyroyPID.U;
		u_gyroz  = Ctrler.gyrozPID.U;
	}
#else
	// Compile-time shadow mode: MRAC computes silently, but motors only see normal PID output.
    Throttle_out=Ctrler.Z_ratePID.U + Throttle_th;

	u_gyrox  = Ctrler.gyroxPID.U ;
	u_gyroy  = -Ctrler.gyroyPID.U;
	u_gyroz  = Ctrler.gyrozPID.U ;
#endif
	{
		float pwm_lo = 2000.0f + gs_throttle_min_pct * 2000.0f;
		float pwm_hi = 2000.0f + gs_throttle_max_pct * 2000.0f;
		if (pwm_hi < pwm_lo) {
			float t = pwm_hi;
			pwm_hi = pwm_lo;
			pwm_lo = t;
		}
		Throttle_out = Constrain_Float(Throttle_out, pwm_lo, pwm_hi);
	}
	
	// CONSTRAINT: Keep these mixer signs in sync with the physical motor map and pwm.h channel mapping.
	// WHY: Sign or channel drift here can invert closed-loop attitude response.
	mymotor.motor1= Throttle_out
									-u_gyroy//pitch
									-u_gyrox//
									+u_gyroz;//rollyaw
	
	mymotor.motor2= Throttle_out
									+u_gyroy//pitch
									+u_gyrox//roll
									+u_gyroz;//yaw
	
	mymotor.motor3= Throttle_out
									-u_gyroy//pitch
									+u_gyrox//roll
									-u_gyroz;//yaw
	
  mymotor.motor4= Throttle_out
									+u_gyroy//pitch
									-u_gyrox//roll
									-u_gyroz;//yaw  
			
}
/*************************************************************************
�� �� ����void Update_Des(unsigned char which_level);
�������ܣ���������
��    ע��
*************************************************************************/
float des_pitch = 0;
float	des_roll = 0;
void Update_Des(unsigned char which_level)
{
//TWC.target_x = 0;
//TWC.target_y = 0;
//TWC.target_z = 0;
TWC.world_x = Ctrler.locxPID.FB;
TWC.world_y = Ctrler.locyPID.FB;
TWC.world_z = Ctrler.Z_posPID.FB;
//TWC.execute = 0;
//TWC.set_yaw = 0;
TWC.real_yaw = Ctrler.yawPID.FB; //�ṹ���Ա������ʼ��һ��Ҫд�ں����ڲ�������һ��ʼ�ͳ�ʼ��

	if (TWC.execute == 1) {
		float dx = (Ctrler.locxPID.FB - TWC.target_x) * 0.01f; /* cm → m */
		float dy = (Ctrler.locyPID.FB - TWC.target_y) * 0.01f; /* cm → m */
		float dz = Ctrler.Z_posPID.FB - TWC.target_z;           /* already m */
		float dist = sqrtf(dx * dx + dy * dy + dz * dz);
		TWC_arrived = (dist < 0.15f) ? 1U : 0U;
	} else {
		TWC_arrived = 0U;
	}

  static unsigned char is_last_thr_valid,is_last_yaw_valid,is_last_pitch_valid,is_last_roll_valid;
	switch(which_level)
	{
		
		//////////////////////�߶�����/////////////////////////////////////////////////////
		
		case case_Update_height_Des://���¸߶�����

			/* SBUS ch8 rising-edge preset-path trigger — handler to be added.
			 * sbus_path_trigger is set by RemoterTask; clear it here for now. */
			if (sbus_path_trigger)
			{
				/* TODO: launch preset path sequence */
				sbus_path_trigger = 0U;
			}

			/* SBUS ch7 fly-up: release authority so physical RC takeover detection
			 * works normally during flight. TWC.execute=1 gates the IDLE block. */
			if (sbus_flyup_trigger)
			{
				sbus_flyup_trigger = 0U;
				RCInput_SetAuthority(0U);   /* release IDLE throttle lock */
				TWC.target_x = TWC.world_x;
				TWC.target_y = TWC.world_y;
				TWC.target_z = 0.5f;
				TWC.execute  = 1U;
			}

			/* LANDING: ramp Z setpoint down at 0.30 m/s (LAND_DES_STEP at 200 Hz).
			 * Snap Des = min(Des, FB) so a setpoint above current altitude cannot
			 * pull the drone upward at landing entry (case A fix). */
			if (flight_phase == FLIGHT_PHASE_LANDING)
			{
				TWC.execute = 0U;
				if (Ctrler.Z_posPID.Des > Ctrler.Z_posPID.FB)
					Ctrler.Z_posPID.Des = Ctrler.Z_posPID.FB;
				Ctrler.Z_posPID.Des -= LAND_DES_STEP;
				if (Ctrler.Z_posPID.Des < 0.0f) Ctrler.Z_posPID.Des = 0.0f;
				break;
			}
			/* LANDED: hold setpoint at zero while disarm completes this tick. */
			if (flight_phase == FLIGHT_PHASE_LANDED)
			{
				TWC.execute = 0U;
				Ctrler.Z_posPID.Des = 0.0f;
				break;
			}

			/* GROUND_IDLE hold: pin Z setpoint until pilot pushes THR above 20%. */
			if (flight_phase == FLIGHT_PHASE_GROUND_IDLE && !TWC.execute && RCInput_Get(RC_AXIS_THR) < 0.2f)
			{
				Ctrler.Z_posPID.Des = Ctrler.Z_posPID.FB;
				break;
			}

			/* FLY mode (normal) */
			if (is_last_thr_valid && (!RCInput_IsActive(RC_AXIS_THR)))
				Ctrler.Z_posPID.Des = Ctrler.Z_posPID.FB;

			is_last_thr_valid = RCInput_IsActive(RC_AXIS_THR);

			if (TWC.execute == 1)
			{
				/* Rate-limit Z setpoint to 0.5 m/s (0.005 m/cycle at ~100 Hz)
				 * to prevent overshoot when target is far above current altitude. */
				float z_err = TWC.target_z - Ctrler.Z_posPID.Des;
				if      (z_err >  0.005f) Ctrler.Z_posPID.Des += 0.005f;
				else if (z_err < -0.005f) Ctrler.Z_posPID.Des -= 0.005f;
				else                      Ctrler.Z_posPID.Des  = TWC.target_z;
			}

       break;
			
		case case_Update_v_h_Des://������ֱ�ٶ�����
			/* Landing: THR stick must not override PID cascade — rate setpoint
			 * comes exclusively from Z_posPID.U throughout the descent. */
			if (flight_phase == FLIGHT_PHASE_LANDING || flight_phase == FLIGHT_PHASE_LANDED)
			{
				Ctrler.Z_ratePID.Des = Ctrler.Z_posPID.U;
				/* Progressive sink bias: once setpoint has reached the floor, ramp up
				 * commanded sink rate while the drone is slow (stuck in ground effect).
				 * 0.001 m/s per tick at 200 Hz → reaches 0.15 m/s in 0.75 s, max 0.40 m/s.
				 * Adapts to any battery voltage — no altitude threshold needed. */
				if (Ctrler.Z_posPID.Des <= 0.01f)
				{
					if (fabsf(Ctrler.Z_ratePID.FB) < 0.10f)
						s_land_sink_bias += 0.001f;
					if (s_land_sink_bias > 0.40f) s_land_sink_bias = 0.40f;
					Ctrler.Z_ratePID.Des -= s_land_sink_bias;
				}
			}
			else if (flight_phase == FLIGHT_PHASE_GROUND_IDLE && !TWC.execute && RCInput_Get(RC_AXIS_THR) < 0.2f)
				Ctrler.Z_ratePID.Des = 0.0f;
			else if(RCInput_IsActive(RC_AXIS_THR))
 				Ctrler.Z_ratePID.Des = RCInput_Get(RC_AXIS_THR) * gs_max_vertical_speed_mps ;
			else
				Ctrler.Z_ratePID.Des = Ctrler.Z_posPID.U;
       break;
			
		////////////////////ˮƽλ������////////////////////////////////////////////////////	
			
		case case_Update_loc_Des://����λ������
			
			if( is_last_roll_valid && (!RCInput_IsActive(RC_AXIS_ROLL)) )
			{
				Ctrler.locxPID.Des = Ctrler.locxPID.FB;
			}
			if( is_last_pitch_valid && (!RCInput_IsActive(RC_AXIS_PITCH)) )
			{
				Ctrler.locyPID.Des = Ctrler.locyPID.FB;
			}

			is_last_pitch_valid = RCInput_IsActive(RC_AXIS_PITCH);
			is_last_roll_valid = RCInput_IsActive(RC_AXIS_ROLL);
			/* Manual pitch/roll input cancels TWC XY target so the drone
			 * does not snap back to the fly-up launch point after ch7. */
			if (RCInput_IsActive(RC_AXIS_ROLL) || RCInput_IsActive(RC_AXIS_PITCH))
				TWC.execute = 0U;
			if(TWC.execute == 1){Ctrler.locxPID.Des = TWC.target_x;Ctrler.locyPID.Des = TWC.target_y;}//��Ŀ���ת��
			break;
			
    case case_Update_v_loc_Des://����ˮƽ�ٶ�����

				if(RCInput_IsActive(RC_AXIS_PITCH))
					   Ctrler.locysPID.Des = -RCInput_Get(RC_AXIS_PITCH) * (gs_max_horizontal_speed_mps * 100.0f);
				else if (Ctrler.locyPID.U>120.0f)
						Ctrler.locysPID.Des = 120.0f;
				else if (Ctrler.locyPID.U< -120.0f)
						Ctrler.locysPID.Des = -120.0f;
				else
					Ctrler.locysPID.Des = 	Ctrler.locyPID.U;//����˾Ͷ���
					
				if(RCInput_IsActive(RC_AXIS_ROLL))
					Ctrler.locxsPID.Des = -RCInput_Get(RC_AXIS_ROLL) * (gs_max_horizontal_speed_mps * 100.0f);
				else if(Ctrler.locxPID.U>120.0f)
					Ctrler.locxsPID.Des = 120.0f;
				else if(Ctrler.locxPID.U< -120.0f)
					Ctrler.locxsPID.Des = -120.0f;
				else
					Ctrler.locxsPID.Des = 	Ctrler.locxPID.U;//����˾Ͷ���

       break;
		////////////////////////��̬����////////////////////////////////////////////////////	
		
		case case_Update_pitrol_Des://���� pitch roll����
			
			des_pitch = (Ctrler.locysPID.U)*Cos_Yaw_01 + (Ctrler.locxsPID.U)*Sin_Yaw_01;
		  des_roll = (Ctrler.locxsPID.U)*Cos_Yaw_01 - (Ctrler.locysPID.U)*Sin_Yaw_01;
				
     	accel_to_lean_angles( des_pitch,-des_roll,
			  &Ctrler.pitchPID.Des,&Ctrler.rollPID.Des); 	
	
    break;
			
		case case_Update_yaw_Des://����yaw����
			
			if(is_last_yaw_valid && (!RCInput_IsActive(RC_AXIS_YAW)) )
			Ctrler.yawPID.Des = Ctrler.yawPID.FB;
			is_last_yaw_valid = RCInput_IsActive(RC_AXIS_YAW);
		
			if(TWC.execute == 1){Ctrler.yawPID.Des = TWC.set_yaw; }//��Ŀ���ת��
    break;
			
		case case_Update_gyro_Des://���½��ٶ�����

			Ctrler.gyroyPID.Des = Ctrler.pitchPID.U ;
			Ctrler.gyroxPID.Des = Ctrler.rollPID.U ;
			if(RCInput_IsActive(RC_AXIS_YAW))
				Ctrler.gyrozPID.Des = RCInput_Get(RC_AXIS_YAW) * Stick_to_MAX_GyroZ ;
			else
				if(Ctrler.yawPID.U>60.0f)
					Ctrler.gyrozPID.Des  = 60.0f;
				else if(Ctrler.yawPID.U< -60.0f)
					Ctrler.gyrozPID.Des  = -60.0f;
				else
					Ctrler.gyrozPID.Des = Ctrler.yawPID.U ;		
       break;
			
    default: 
       break;
	}
}



/*********�޷�����*******/
float Constrain_Float(float amt, float low, float high)
{
  return ((amt)<(low)?(low):((amt)>(high)?(high):(amt)));
}

float fast_atan(float v)
{
    float v2 = v*v;
    return (v*(1.6867629106f+v2*0.4378497304f)/(1.6867633134f+v2));
}


void accel_to_lean_angles(float acc_tar_forward,float acc_tar_right,float *tar_pitch,float *tar_roll)//cm/s^2
{
  float lim_p = gs_max_pitch_deg;
  float lim_r = gs_max_roll_deg;
	
	float my_Cos_Roll;
	float my_Cos_Pitch;
	my_Cos_Roll = cos(imu_data.rol*DEG2RAD);//*Cos_Roll
	my_Cos_Pitch = cos(imu_data.pit*DEG2RAD);
	
  *tar_pitch=Constrain_Float(
									fast_atan(    acc_tar_forward    *my_Cos_Roll   /(GRAVITY_MSS*100)    )*RAD2DEG,
														-lim_p,lim_p);//pitch
  *tar_roll = Constrain_Float(
									fast_atan(acc_tar_right * my_Cos_Pitch /(GRAVITY_MSS*100))*RAD2DEG,
														-lim_r,lim_r);//roll
}

const float fast_atan_table[257] = 
{
	0.000000e+00, 3.921549e-03, 7.842976e-03, 1.176416e-02,
	1.568499e-02, 1.960533e-02, 2.352507e-02, 2.744409e-02,
	3.136226e-02, 3.527947e-02, 3.919560e-02, 4.311053e-02,
	4.702413e-02, 5.093629e-02, 5.484690e-02, 5.875582e-02,
	6.266295e-02, 6.656816e-02, 7.047134e-02, 7.437238e-02,
	7.827114e-02, 8.216752e-02, 8.606141e-02, 8.995267e-02,
	9.384121e-02, 9.772691e-02, 1.016096e-01, 1.054893e-01,
	1.093658e-01, 1.132390e-01, 1.171087e-01, 1.209750e-01,
	1.248376e-01, 1.286965e-01, 1.325515e-01, 1.364026e-01,
	1.402496e-01, 1.440924e-01, 1.479310e-01, 1.517652e-01,
	1.555948e-01, 1.594199e-01, 1.632403e-01, 1.670559e-01,
	1.708665e-01, 1.746722e-01, 1.784728e-01, 1.822681e-01,
	1.860582e-01, 1.898428e-01, 1.936220e-01, 1.973956e-01,
	2.011634e-01, 2.049255e-01, 2.086818e-01, 2.124320e-01,
	2.161762e-01, 2.199143e-01, 2.236461e-01, 2.273716e-01,
	2.310907e-01, 2.348033e-01, 2.385093e-01, 2.422086e-01,
	2.459012e-01, 2.495869e-01, 2.532658e-01, 2.569376e-01,
	2.606024e-01, 2.642600e-01, 2.679104e-01, 2.715535e-01,
	2.751892e-01, 2.788175e-01, 2.824383e-01, 2.860514e-01,
	2.896569e-01, 2.932547e-01, 2.968447e-01, 3.004268e-01,
	3.040009e-01, 3.075671e-01, 3.111252e-01, 3.146752e-01,
	3.182170e-01, 3.217506e-01, 3.252758e-01, 3.287927e-01,
	3.323012e-01, 3.358012e-01, 3.392926e-01, 3.427755e-01,
	3.462497e-01, 3.497153e-01, 3.531721e-01, 3.566201e-01,
	3.600593e-01, 3.634896e-01, 3.669110e-01, 3.703234e-01,
	3.737268e-01, 3.771211e-01, 3.805064e-01, 3.838825e-01,
	3.872494e-01, 3.906070e-01, 3.939555e-01, 3.972946e-01,
	4.006244e-01, 4.039448e-01, 4.072558e-01, 4.105574e-01,
	4.138496e-01, 4.171322e-01, 4.204054e-01, 4.236689e-01,
	4.269229e-01, 4.301673e-01, 4.334021e-01, 4.366272e-01,
	4.398426e-01, 4.430483e-01, 4.462443e-01, 4.494306e-01,
	4.526070e-01, 4.557738e-01, 4.589307e-01, 4.620778e-01,
	4.652150e-01, 4.683424e-01, 4.714600e-01, 4.745676e-01,
	4.776654e-01, 4.807532e-01, 4.838312e-01, 4.868992e-01,
	4.899573e-01, 4.930055e-01, 4.960437e-01, 4.990719e-01,
	5.020902e-01, 5.050985e-01, 5.080968e-01, 5.110852e-01,
	5.140636e-01, 5.170320e-01, 5.199904e-01, 5.229388e-01,
	5.258772e-01, 5.288056e-01, 5.317241e-01, 5.346325e-01,
	5.375310e-01, 5.404195e-01, 5.432980e-01, 5.461666e-01,
	5.490251e-01, 5.518738e-01, 5.547124e-01, 5.575411e-01,
	5.603599e-01, 5.631687e-01, 5.659676e-01, 5.687566e-01,
	5.715357e-01, 5.743048e-01, 5.770641e-01, 5.798135e-01,
	5.825531e-01, 5.852828e-01, 5.880026e-01, 5.907126e-01,
	5.934128e-01, 5.961032e-01, 5.987839e-01, 6.014547e-01,
	6.041158e-01, 6.067672e-01, 6.094088e-01, 6.120407e-01,
	6.146630e-01, 6.172755e-01, 6.198784e-01, 6.224717e-01,
	6.250554e-01, 6.276294e-01, 6.301939e-01, 6.327488e-01,
	6.352942e-01, 6.378301e-01, 6.403565e-01, 6.428734e-01,
	6.453808e-01, 6.478788e-01, 6.503674e-01, 6.528466e-01,
	6.553165e-01, 6.577770e-01, 6.602282e-01, 6.626701e-01,
	6.651027e-01, 6.675261e-01, 6.699402e-01, 6.723452e-01,
	6.747409e-01, 6.771276e-01, 6.795051e-01, 6.818735e-01,
	6.842328e-01, 6.865831e-01, 6.889244e-01, 6.912567e-01,
	6.935800e-01, 6.958943e-01, 6.981998e-01, 7.004964e-01,
	7.027841e-01, 7.050630e-01, 7.073330e-01, 7.095943e-01,
	7.118469e-01, 7.140907e-01, 7.163258e-01, 7.185523e-01,
	7.207701e-01, 7.229794e-01, 7.251800e-01, 7.273721e-01,
	7.295557e-01, 7.317307e-01, 7.338974e-01, 7.360555e-01,
	7.382053e-01, 7.403467e-01, 7.424797e-01, 7.446045e-01,
	7.467209e-01, 7.488291e-01, 7.509291e-01, 7.530208e-01,
	7.551044e-01, 7.571798e-01, 7.592472e-01, 7.613064e-01,
	7.633576e-01, 7.654008e-01, 7.674360e-01, 7.694633e-01,
	7.714826e-01, 7.734940e-01, 7.754975e-01, 7.774932e-01,
	7.794811e-01, 7.814612e-01, 7.834335e-01, 7.853983e-01,
	7.853983e-01
};

REAL fast_atan2(REAL y, REAL x) 
{
	REAL x_abs, y_abs, z;
	REAL alpha, angle, base_angle;
	int index;

	/* don't divide by zero! */
	if ((y == 0.0f) && (x == 0.0f))
		angle = 0.0f;
	else 
	{
		/* normalize to +/- 45 degree range */
		y_abs = abs_fl(y);
		x_abs = abs_fl(x);
		//z = (y_abs < x_abs ? y_abs / x_abs : x_abs / y_abs);
		if (y_abs < x_abs)
			z = y_abs / x_abs;
		else
			z = x_abs / y_abs;
		/* when ratio approaches the table resolution, the angle is */
		/*      best approximated with the argument itself...       */
		if (z < TAN_MAP_RES)
			base_angle = z;
		else 
		{
			/* find index and interpolation value */
			alpha = z * (REAL) TAN_MAP_SIZE - .5f;
			index = (int) alpha;
			alpha -= (REAL) index;
			/* determine base angle based on quadrant and */
			/* add or subtract table value from base angle based on quadrant */
			base_angle = fast_atan_table[index];
			base_angle += (fast_atan_table[index + 1] - fast_atan_table[index]) * alpha;
		}

		if (x_abs > y_abs) 
		{        /* -45 -> 45 or 135 -> 225 */
			if (x >= 0.0f) 
			{           /* -45 -> 45 */
				if (y >= 0.0f)
					angle = base_angle;   /* 0 -> 45, angle OK */
				else
					angle = -base_angle;  /* -45 -> 0, angle = -angle */
				  return angle;
			} 
			else
			{                  /* 135 -> 180 or 180 -> -135 */
				angle = 3.14159265358979323846;

				if (y >= 0.0f)
					angle -= base_angle;  /* 135 -> 180, angle = 180 - angle */
				else
					angle = base_angle - angle;   /* 180 -> -135, angle = angle - 180 */

			}
		} 
		else 
		{                    /* 45 -> 135 or -135 -> -45 */
			if (y >= 0.0f) 
			{           /* 45 -> 135 */
				angle = 1.57079632679489661923;

				if (x >= 0.0f)
					angle -= base_angle;  /* 45 -> 90, angle = 90 - angle */
				else
					angle += base_angle;  /* 90 -> 135, angle = 90 + angle */
			} 
			else
			{                  /* -135 -> -45 */
				angle = -1.57079632679489661923;

				if (x >= 0.0f)
					angle += base_angle;  /* -90 -> -45, angle = -90 + angle */
				else
					angle -= base_angle;  /* -135 -> -90, angle = -90 - angle */
			}
		}
	}
	return angle;
}

float voltage;    //������ѹֵ(2.67-2.99)    
float real_voltage;    //ʵ�ʵ�ѹֵ
uint16_t adc_value ;
void Get_Voltage(void)     //ͨ��ADC����ص�ѹ
{
	adc_value = ADC_Read();
	voltage = Voltage_Calculation(adc_value);
	real_voltage = 7.0663f*voltage + 0.8930f;   //2-pt cal 2026-06-24: (2.21289V,16.53) (1.98081V,14.89)
	if(real_voltage<15.0f)
	{
		SetBeep(1);//�����ź�
		
	}
}
