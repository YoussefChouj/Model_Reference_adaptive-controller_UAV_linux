#include "imu_update.h"

/**
 * @module  imu_update.c
 * @subsystem  sensors
 * @depends  imu_update.h
 * @owns  Mahony attitude update and quaternion-to-Euler conversion
 * @caution  gyroscope units and task-provided dt must remain consistent to avoid estimator drift
 */

_imu_st imu_data =  {1,0,0,0,0,0,
					{0,0,0},
					{0,0,0},
					{0,0,0},
					{0,0,0},
					{0,0,0},
					{0,0,0},
					 0,0,0};

float Kp = 0.5f;/**/
float Ki = 0.001f;/**/
/**/
float exInt = 0.0f;
float eyInt = 0.0f;
float ezInt = 0.0f;
/**/
static float q0 = 1.0f;	
static float q1 = 0.0f;
static float q2 = 0.0f;
static float q3 = 0.0f;


float invSqrt(float x)
{
	float halfx = 0.5f * x;
	float y = x;
	long i = *(long*)&y;
	i = 0x5f3759df - (i>>1);
	y = *(float*)&i;
	y = y * (1.5f - (halfx * y * y));
	return y;
}
/* Gravity-removed body-frame linear acceleration (mg), computed from the fresh Mahony
 * gravity direction each update. Streamed in the 0x05 OF-calibration frame for the
 * IMU+OF fusion filter (prereq #1, docs/tracking_baseline_and_drift.md). 1 G = 1000 mg. */
float Lin_Acc_X_body = 0.0f, Lin_Acc_Y_body = 0.0f;

void IMU_Update_Mahony(_imu_st *imu,float dt)
{
	float normalise;
	float nor_acc[VEC_XYZ] = {0};
	float ex, ey, ez;//
	float q0s, q1s, q2s, q3s;/*  */
	static float R11,R21;/* (1,1),(2,1) */
	static float vecxZ, vecyZ, veczZ;/* z(0,0,1)' */
	// CONSTRAINT: dt is supplied by the 1 kHz task in USER/main.c and must match actual loop period.
	// WHY: PI correction and quaternion propagation are both dt-scaled.
	float half_T = 0.5f * dt;

	float q0Last = q0;
	float q1Last = q1;
	float q2Last = q2;
	float q3Last = q3;
	float delta_theta[3];/* xyz */
	float delta_theta_s;/* xyz */

	/* 0 */
	if((Acc_X_Real != 0.0f) || (Acc_Y_Real != 0.0f) || (Acc_Z_Real != 0.0f))
	{
		nor_acc[X] = Acc_X_Real;
		nor_acc[Y] = Acc_Y_Real;
		nor_acc[Z] = Acc_Z_Real;
		
		/*  */
		normalise = invSqrt(nor_acc[X] * nor_acc[X] + nor_acc[Y] * nor_acc[Y] + nor_acc[Z] * nor_acc[Z]);
		nor_acc[X] *= normalise;
		nor_acc[Y] *= normalise;
		nor_acc[Z] *= normalise;

		/* , */
		/* |a x b| = |a|*|b|*sin(theta);|a|=|b|=1,thetasin(theta)theta, */
		ex = (nor_acc[Y] * veczZ - nor_acc[Z] * vecyZ);
		ey = (nor_acc[Z] * vecxZ - nor_acc[X] * veczZ);
		ez = (nor_acc[X] * vecyZ - nor_acc[Y] * vecxZ);
		
		/* , */
		exInt += Ki * ex * dt ;  
		eyInt += Ki * ey * dt ;
		ezInt += Ki * ez * dt ;
		
		/* PI, */
 		Gyro_X_Real += Kp * ex + exInt;
 		Gyro_Y_Real += Kp * ey + eyInt;
 		Gyro_Z_Real += Kp * ez + ezInt;
	}

	/* TkTk+1, */
	delta_theta[0] = Gyro_X_Real*half_T;
	delta_theta[1] = Gyro_Y_Real*half_T;
	delta_theta[2] = Gyro_Z_Real*half_T;
	delta_theta_s = delta_theta[0]*delta_theta[0] + delta_theta[1]*delta_theta[1] + delta_theta[2]*delta_theta[2];
	/* , */
	/* Q(Tk+1)=(I+0.5*delta_theta)Q(Tk) */
// 	q0 += -q1Last * delta_theta[0] - q2Last * delta_theta[1] - q3Last * delta_theta[2];
// 	q1 +=  q0Last * delta_theta[0] + q2Last * delta_theta[2] - q3Last * delta_theta[1];
// 	q2 +=  q0Last * delta_theta[1] - q1Last * delta_theta[2] + q3Last * delta_theta[0];
// 	q3 +=  q0Last * delta_theta[2] + q1Last * delta_theta[1] - q2Last * delta_theta[0];

	/*  */
	/* Q(Tk+1)=((1-0.125*delta_theta_s)I+0.5*delta_theta)Q(Tk) */	
	q0 = q0Last*(1-delta_theta_s) - q1Last * delta_theta[0] - q2Last * delta_theta[1] - q3Last * delta_theta[2];
	q1 = q1Last*(1-delta_theta_s) + q0Last * delta_theta[0] + q2Last * delta_theta[2] - q3Last * delta_theta[1];
	q2 = q2Last*(1-delta_theta_s) + q0Last * delta_theta[1] - q1Last * delta_theta[2] + q3Last * delta_theta[0];
	q3 = q3Last*(1-delta_theta_s) + q0Last * delta_theta[2] + q1Last * delta_theta[1] - q2Last * delta_theta[0];
	
	/*  */
	normalise = invSqrt(q0 * q0 + q1 * q1 + q2 * q2 + q3 * q3);
	q0 *= normalise;
	q1 *= normalise;
	q2 *= normalise;
	q3 *= normalise;
	/*  */
	q0s = q0 * q0;
	q1s = q1 * q1;
	q2s = q2 * q2;
	q3s = q3 * q3;
	
	R11 = q0s + q1s - q2s - q3s;/* (1,1) */
	R21 = 2 * (q1 * q2 + q0 * q3);/* (2,1) */

	/* z(0,0,1) */
	vecxZ = 2 * (q1 * q3 - q0 * q2);/* (3,1) */
	vecyZ = 2 * (q0 * q1 + q2 * q3);/* (3,2) */
	veczZ = q0s - q1s - q2s + q3s;	/* (3,3) */
	
	if (vecxZ>1) vecxZ=1;
	if (vecxZ<-1) vecxZ=-1;
	
	/* roll pitch yaw  */
	imu->pit = -asinf(vecxZ) *RAD2DEG;
	imu->rol = atan2f(vecyZ, veczZ) * RAD2DEG;
	imu->yaw = atan2f(R21, R11) * RAD2DEG;

	/* Remove gravity in body frame: linear accel = measured - G*gravity_direction (mg).
	 * (vecxZ,vecyZ,veczZ) is the body-frame gravity unit vector; static & level => lin ~ 0. */
	Lin_Acc_X_body = Acc_X_Real - 1000.0f * vecxZ;
	Lin_Acc_Y_body = Acc_Y_Real - 1000.0f * vecyZ;
}

	 
