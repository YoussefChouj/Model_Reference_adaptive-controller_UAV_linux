#ifndef __IMU_UPDATE__
#define __IMU_UPDATE__

#include "global_declare.h"
#include "bmi088_driver.h"


extern	_imu_st imu_data	; 

void IMU_Update_Mahony(_imu_st *imu,float dt);

#endif

