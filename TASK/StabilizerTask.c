#include "StabilizerTask.h"
#include "math.h"
#include "pid.h"
#include "ADC.h"
#include "mrac.h"
unsigned char cnt_h,cnt_loc,cnt_locs,cnt_yaw;
float Throttle_out,u_gyrox,u_gyroy,u_gyroz;
short Throttle_th = 2200;
float Cos_Yaw_01= 0;
float Sin_Yaw_01= 0;

float Sin_roll_01= 0;
float Cos_roll_01= 0;
float Sin_pitch_01= 0;
float Cos_pitch_01= 0;
//
TargetSet_WorldReal_Coordinate TWC;

static float eff_rc_thr(void)
{
	float v = sbus_lost ? virtual_rc_sticks[0] : (float)Remoter.ThrCtrler;
	if (bench_mode_active) {
		const float tmin = 2000.0f;
		const float tmax = 4000.0f;
		float cap = tmin + 0.2f * (tmax - tmin);
		if (v > cap) {
			v = cap;
		}
	}
	return v;
}

static float eff_rc_pit(void) { return sbus_lost ? virtual_rc_sticks[1] : (float)Remoter.PitCtrler; }
static float eff_rc_rol(void) { return sbus_lost ? virtual_rc_sticks[2] : (float)Remoter.RolCtrler; }
static float eff_rc_yaw(void) { return sbus_lost ? virtual_rc_sticks[3] : (float)Remoter.YawCtrler; }

static int eff_thr_ch_valid(void)
{
	if (sbus_lost) {
		return ABS((int)virtual_rc_sticks[0] - 3000) > SBUS_THR_OFFSET;
	}
	return SBUS_THR_CH_VALID(THR_CH);
}
static int eff_ch_valid_pitch(void)
{
	if (sbus_lost) {
		return ABS((int)virtual_rc_sticks[1] - 3000) > SBUS_OFFSET;
	}
	return SBUS_CH_VALID(PITCH_CH);
}
static int eff_ch_valid_roll(void)
{
	if (sbus_lost) {
		return ABS((int)virtual_rc_sticks[2] - 3000) > SBUS_OFFSET;
	}
	return SBUS_CH_VALID(ROLL_CH);
}
static int eff_ch_valid_yaw(void)
{
	if (sbus_lost) {
		return ABS((int)virtual_rc_sticks[3] - 3000) > SBUS_OFFSET;
	}
	return SBUS_CH_VALID(YAW_CH);
}

//
void stabilizer_Task(void)
{
	 Check_Fly_Mode(); //判断无人机的状态
	
	 Update_Data();
	 
	 Compute_Motor();
	 
	 Update_Motor();
	
//	 Get_Voltage();//计算电压

} 

/*************************************************************************
函 数 名：void Update_Data(void);
函数功能：更新反馈值
备    注：
*************************************************************************/
void Update_Data(void)
{
	
	Cos_Yaw_01=cos(-imu_data.yaw* DEG2RAD);
	Sin_Yaw_01=sin(-imu_data.yaw* DEG2RAD);
	
	Cos_roll_01=cos(imu_data.rol* DEG2RAD);
	Sin_roll_01 = sin(imu_data.rol* DEG2RAD);
	Cos_pitch_01=cos(imu_data.pit* DEG2RAD);
	Sin_pitch_01 = sin(imu_data.pit* DEG2RAD);
	
	//////////////////位置环反馈值更新/////////////////////////
		ano_of.DISTANCE_X = ano_of.DISTANCE_X+ano_of.of2_dx_fix*0.005f;
	  ano_of.DISTANCE_Y = ano_of.DISTANCE_Y+ano_of.of2_dy_fix*0.005f;

	
			//光流在世界坐标系下的值
	  ano_of.earth_x = ano_of.earth_x + (ano_of.of2_dx_fix*0.005f*Cos_Yaw_01 + ano_of.of2_dy_fix*0.005f*Sin_Yaw_01 );
	
	  ano_of.earth_y = ano_of.earth_y + (ano_of.of2_dy_fix*0.005f*Cos_Yaw_01 - ano_of.of2_dx_fix*0.005f*Sin_Yaw_01 );
	  ano_of.earth_x_ture  =  ano_of.earth_y;
	  ano_of.earth_y_ture  =  -ano_of.earth_x;
	
	  Ctrler.locxPID.FB= ano_of.earth_x_ture ;  //世界坐标系下
	  Ctrler.locyPID.FB= ano_of.earth_y_ture ; //x (世界)<----
		//                                                     |
		//                                                     | y(世界)
		//保护性措施  //t265向后装的代码
//		if(linux_data.t265posy>-1000000.0f && linux_data.t265posy<1000000.0f)
//		{
//			Ctrler.locxPID.FB= linux_data.t265posy  ;  //世界坐标系下	
//		}
//		if(linux_data.t265posx>-1000000.0f && linux_data.t265posx<1000000.0f)
//		{
//			Ctrler.locyPID.FB= -linux_data.t265posx ;
//		}
		
	//光流速度反馈                                                    ^y(机体)
//	  Ctrler.locxsPID.FB= ano_of.of2_dy;                           |
//    Ctrler.locysPID.FB= -ano_of.of2_dx;   //机体坐标系下          |-->x(机体)          

		Ctrler.locxsPID.FB= (ano_of.of2_dy) *Cos_Yaw_01 +(-ano_of.of2_dx)*Sin_Yaw_01;
    Ctrler.locysPID.FB=  (-ano_of.of2_dx) * Cos_Yaw_01 - (ano_of.of2_dy)*Sin_Yaw_01; //世界坐标系下
	
	  if( ano_of.of_alt_cm>0.5f &&ano_of.of_alt_cm<500.0f)
		{
			ano_of.of2_raw_h = ano_of.of_alt_cm*0.01f*Cos_roll_01*Cos_pitch_01;
		}
	
	ano_of.of2_h =ano_of.of2_raw_h; 
	ano_of.of2_h_v = (ano_of.of2_h - ano_of.of2_last_h )/(0.005f);  //除以时间5ms
	ano_of.of2_last_h = ano_of.of2_h;
  ano_of.of2_h_f2_v  = ano_of.of2_h_f2_v  *0.9f +ano_of.of2_h_v *0.1f;
	 
	Ctrler.Z_posPID.FB =  ano_of.of2_h;
	Ctrler.Z_ratePID.FB = ano_of.of2_h_f2_v ;
	
	////////////////////姿态环角度值更新//////////////////////////////////  
	
	Ctrler.pitchPID.FB = -imu_data.pit  ;
	Ctrler.rollPID.FB  = imu_data.rol ;
	Ctrler.yawPID.FB   = -imu_data.yaw;

	Ctrler.gyroyPID.FB = -Gyro_Y_Real*RAD2DEG ;
	Ctrler.gyroxPID.FB = Gyro_X_Real*RAD2DEG ;
	Ctrler.gyrozPID.FB = -Gyro_Z_Real*RAD2DEG;
	
}
/*************************************************************************
函 数 名：void Update_Motor(void);
函数功能：更新四个电机的状态
备    注：
*************************************************************************/
void Update_Motor(void)
{
		if(DroneStatus.ARM_Status==Armed)//解锁了
		{
			
       if( DroneStatus.FlyMode == FlyMode_SDK   )//SDK模式	
			{			
					if(Ctrler.Z_posPID.FB < 0.3f && eff_rc_thr()<2150.0f)
				{
					Set_IDLE_Motors();//还没起飞（落地、触地），油门最低，怠速
				}
				else if(SDK_DelayWakeFlag==1)  //SDK_DelayWakeFlag这个标志位为1的时候会怠速
				{
					Set_IDLE_Motors();
				}
				else 
				{
					Set_PWM_Motors();
				}			
			}
			else if(DroneStatus.FlyMode == FlyMode_DangerousStop )//强制停机
			{
				Set_Zero_Motors();
				DroneStatus.ARM_Status = DisArmed;
			}
			else 
			{
				Set_Zero_Motors();
				DroneStatus.ARM_Status = DisArmed;
			}
		}
		else//上锁状态清除积分值，并且电机绝对不转
		{
		  SDK_StateMachine_Init();
			Clear_Structure();
			Set_Zero_Motors();
			
		}
}
//以下是校准电调代码
//   if( DroneStatus.FlyMode == FlyMode_SDK   )//SDK模式	
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
函 数 名：void Compute_Motor(void);
函数功能：计算PID参数
备    注：
*************************************************************************/
void Compute_Motor(void)
{
////////////////计算高度数据//////////////////////////////////////////////////////////
				
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
	SDK_Set_V_Loc();//！！！

	ComputePID(&Ctrler.locxsPID);
	ComputePID(&Ctrler.locysPID);
  }
	
//////////////////////计算姿态数据////////////////////////////////////////////////////////////
	
	Update_Des(case_Update_pitrol_Des);  //更新pit和roll角度值
	ComputePID(&Ctrler.pitchPID);
	ComputePID(&Ctrler.rollPID);
	
	Update_Des(case_Update_yaw_Des);    //更新yaw的角度
	ComputeYawPID(&Ctrler.yawPID);
	
	
	Update_Des(case_Update_gyro_Des);   //更新角速度
	
	SDK_Set_Gyroz();
	ComputePID(&Ctrler.gyroxPID);
	ComputePID(&Ctrler.gyroyPID);
	ComputePID(&Ctrler.gyrozPID);
	
	// Execute MRAC after all PID controllers have computed their nominal outputs (u_nom)
	// MRAC uses the current PID rates, references, and nominal outputs to learn and compute u_ad.
	MRAC_Control(&Ctrler);
	
 

	 //Throttle_th=2800+(16.70f-real_voltage)*105.5f;  //4s电池裸机+d435i+t265+orin  
	 Throttle_th=2800;

#if ENABLE_MRAC_OUTPUT_INJECTION == 1
	// Inject MRAC adaptive signals.
	// u_total = u_nom + (u_ad * scaling_factor)
	Throttle_out = Ctrler.Z_ratePID.U + Throttle_th + (mrac_state.z_rate.u_ad * mrac_config_z.mrac_to_mixer);
	
	u_gyrox = Ctrler.gyroxPID.U + (mrac_state.roll.u_ad * mrac_config_roll.mrac_to_mixer);
	
	// Motor mixer needs gyroy reversed
	u_gyroy = -(Ctrler.gyroyPID.U + (mrac_state.pitch.u_ad * mrac_config_pitch.mrac_to_mixer)); 
	
	u_gyroz = Ctrler.gyrozPID.U + (mrac_state.yaw.u_ad * mrac_config_yaw.mrac_to_mixer);
#else
	// Shadow mode: MRAC computes silently, but motors only see normal PID output.
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
函 数 名：void Update_Des(unsigned char which_level);
函数功能：更新数据
备    注：
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
TWC.real_yaw = Ctrler.yawPID.FB; //结构体成员变量初始化一定要写在函数内部，不能一开始就初始化

	if (TWC.execute == 1) {
		float dx = Ctrler.locxPID.FB - TWC.target_x;
		float dy = Ctrler.locyPID.FB - TWC.target_y;
		float dz = Ctrler.Z_posPID.FB - TWC.target_z;
		float dist = sqrtf(dx * dx + dy * dy + dz * dz);
		TWC_arrived = (dist < 0.15f) ? 1U : 0U;
	} else {
		TWC_arrived = 0U;
	}

  static unsigned char is_last_thr_valid,is_last_yaw_valid,is_last_pitch_valid,is_last_roll_valid;
	switch(which_level)
	{
		
		//////////////////////高度数据/////////////////////////////////////////////////////
		
		case case_Update_height_Des://更新高度期望
			
			if(is_last_thr_valid && (!eff_thr_ch_valid()) )
				Ctrler.Z_posPID.Des=  Ctrler.Z_posPID.FB;  

			  is_last_thr_valid = eff_thr_ch_valid();
			
			if(TWC.execute == 1){Ctrler.Z_posPID.Des = TWC.target_z; }//向目标点转移

       break;
			
		case case_Update_v_h_Des://更新竖直速度期望
			if(eff_thr_ch_valid())
 				Ctrler.Z_ratePID.Des =  ((eff_rc_thr()-3000.0f)/1000.0f)*gs_max_vertical_speed_mps ;
			else
				Ctrler.Z_ratePID.Des = Ctrler.Z_posPID.U;
       break;
			
		////////////////////水平位置数据////////////////////////////////////////////////////	
			
		case case_Update_loc_Des://更新位置期望
			
			if( is_last_roll_valid && (!eff_ch_valid_roll()) )  //上一次动了，现在回中
			{
				Ctrler.locxPID.Des = Ctrler.locxPID.FB;
			}
			if( is_last_pitch_valid && (!eff_ch_valid_pitch()) )
			{
				Ctrler.locyPID.Des = Ctrler.locyPID.FB;
			}
			
			is_last_pitch_valid = eff_ch_valid_pitch();
			is_last_roll_valid = eff_ch_valid_roll();
			if(TWC.execute == 1){Ctrler.locxPID.Des = TWC.target_x;Ctrler.locyPID.Des = TWC.target_y;}//向目标点转移
			break;
			
    case case_Update_v_loc_Des://更新水平速度期望

				if(eff_ch_valid_pitch())//打杆对应期望水平速度
					   Ctrler.locysPID.Des = -((eff_rc_pit()-3000.0f)/1000.0f)*(gs_max_horizontal_speed_mps * 100.0f);
				else if (Ctrler.locyPID.U>120.0f)
						Ctrler.locysPID.Des = 120.0f;
				else if (Ctrler.locyPID.U< -120.0f)
						Ctrler.locysPID.Des = -120.0f;
				else
					Ctrler.locysPID.Des = 	Ctrler.locyPID.U;//不打杆就定点
					
				if(eff_ch_valid_roll())//打杆对应期望水平速度
					Ctrler.locxsPID.Des = -((eff_rc_rol()-3000.0f)/1000.0f)*(gs_max_horizontal_speed_mps * 100.0f);  
				else if(Ctrler.locxPID.U>120.0f)
					Ctrler.locxsPID.Des = 120.0f;
				else if(Ctrler.locxPID.U< -120.0f)
					Ctrler.locxsPID.Des = -120.0f;
				else
					Ctrler.locxsPID.Des = 	Ctrler.locxPID.U;//不打杆就定点

       break;
		////////////////////////姿态数据////////////////////////////////////////////////////	
		
		case case_Update_pitrol_Des://更新 pitch roll期望
			
			des_pitch = (Ctrler.locysPID.U)*Cos_Yaw_01 + (Ctrler.locxsPID.U)*Sin_Yaw_01;
		  des_roll = (Ctrler.locxsPID.U)*Cos_Yaw_01 - (Ctrler.locysPID.U)*Sin_Yaw_01;
				
     	accel_to_lean_angles( des_pitch,-des_roll,
			  &Ctrler.pitchPID.Des,&Ctrler.rollPID.Des); 	
	
    break;
			
		case case_Update_yaw_Des://更新yaw期望
			
			if(is_last_yaw_valid && (!eff_ch_valid_yaw()) )
			Ctrler.yawPID.Des = Ctrler.yawPID.FB;
			//！！！yawdes为何会飘?什么鬼
			is_last_yaw_valid = eff_ch_valid_yaw();
		
			if(TWC.execute == 1){Ctrler.yawPID.Des = TWC.set_yaw; }//向目标点转移
    break;
			
		case case_Update_gyro_Des://更新角速度期望

			Ctrler.gyroyPID.Des = Ctrler.pitchPID.U ;
			Ctrler.gyroxPID.Des = Ctrler.rollPID.U ;
			if(eff_ch_valid_yaw())
				Ctrler.gyrozPID.Des =  ((eff_rc_yaw()-3000.0f)/1000.0f)*Stick_to_MAX_GyroZ ;
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



/*********限幅函数*******/
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

float voltage;    //测量电压值(2.67-2.99)    
float real_voltage;    //实际电压值
uint16_t adc_value ;
void Get_Voltage(void)     //通过ADC检测电池电压
{
	adc_value = ADC_Read();
	voltage = Voltage_Calculation(adc_value);
	real_voltage = (voltage/2.85f)*16.8f;     //理论上2.99
	if(real_voltage<15.0f)
	{
		SetBeep(1);//警告信号
		
	}
}
