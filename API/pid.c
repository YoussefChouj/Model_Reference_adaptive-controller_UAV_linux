#include "pid.h"

CtrlerTypeDef Ctrler={

/*des FB  Kp   Ki    Kd Up Ui Ud E preE SumE U Umax Upmax Uimax Udmax SumEmax Emin***/
	{ 0,  0, 3.0, 0.1,  8, 0, 0, 0, 0, 0,   0,  0, 200,  200,  0,  10,  1000,     3},//pitch//p=15
	{ 0,  0, 3.0, 0.1,  8, 0, 0, 0, 0, 0,   0,  0, 200,  200,  0,  10,  1000,     3},//roll
	{ 0,  0, 6.0, 0.04,  0, 0, 0, 0, 0, 0,   0,  0, 120,  120,  2,  0,     50,     2},//yaw
	//skywalker  4         letian40A    3       pitch/roll KP
	//yaw KP   3   -> 4
	

	{ 0,  0, 5   , 0.01 ,10, 0,0, 0, 0, 0,   0,  0, 300,  300,  20,  100,  1000,   2},//gyrox
	{ 0,  0, 5   , 0.01 ,10, 0,0, 0, 0, 0,   0,  0, 300,  300,  20,  100,  1000,   2},//gyroy
	{ 0,  0, 8.0, 0.001 ,0.02, 0,0, 0, 0, 0,  0,  0, 250,  250,  60,  10,   2000,     20},//gyroz
	
	{ 0,  0, 0.7, 0.005 ,0.1, 0,0, 0, 0, 0,   0,  0, 1.0 , 0.9,  0.3,  0.3,  30,     0.3},//h
	{ 0,  0, 400,  0.435,  0,0,0, 0, 0, 0,   0, 0,300, 300, 60,   60,    30,    0.1},//h rate
	
		/*des FB  Kp   Ki  Kd   Up Ui Ud E preE SumE U Umax Upmax Uimax Udmax SumEmax Emin***/	  //光流的参数
	//hui fei zhe   1.8outKP    1.8 0.45inKP KI
	{ 0,  0, 0.8    , 0.01 ,4.0, 0,0, 0, 0, 0,   0,  0, 300, 300,  20,   50,     200,     30},//locx
	{ 0,  0, 0.8    , 0.01 ,4.0, 0,0, 0, 0, 0,   0,  0, 300, 300,  20,   50,     200,     30},//locy
	{ 0,  0, 3.0      , 0 ,6.00, 0,0, 0, 0, 0,   0,  0, 600, 600, 100,   100,     200,   10},//locxs
	{ 0,  0, 3.0      , 0 ,6.00, 0,0, 0, 0, 0,   0,  0, 600, 600, 100,   100,     200,   10},//locys
	
		{ 0,  0, 1.0    , 0    ,2.0, 0,0, 0, 0, 0,   0,  0, 40, 40, 0,   2,     2,    2},  //stree_yaw_speed
	  { 0,  0, 0.6    , 0    ,0.0, 0,0, 0, 0, 0,   0,  0, 80, 70, 0,   5,     2,    2}  //stree_pitch_speed
};                  

/******积分分离、积分限幅、P I D 输出限幅、总输出限幅***********************/
void ComputePID(PIDTypeDef *pPID)
{
	pPID->E = pPID->Des - pPID->FB;//计算当前偏差

	if(((pPID->U <= pPID->UMax && pPID->E > 0) || (pPID->U >= -pPID->UMax && pPID->E < 0)) \
		    && ABS(pPID->E) < pPID->EMin)//积分分离
	{
		pPID->SumE += pPID->E;//计算偏差积分
	}
	value_limit( pPID->SumE , -pPID->SumEMax , pPID->SumEMax );//积分限幅
	pPID->Ui = pPID->Ki * pPID->SumE;
	value_limit( pPID->Ui , -pPID->UiMax , pPID->UiMax );
	
	pPID->Up = pPID->Kp * pPID->E;
	value_limit( pPID->Up , -pPID->UpMax , pPID->UpMax );
	
	pPID->Ud = pPID->Kd * ( pPID->E - pPID->PreE );
	value_limit( pPID->Ud , -pPID->UdMax , pPID->UdMax );
	
	pPID->U = pPID->Up + pPID->Ui + pPID->Ud;/*位置式PID计算公式*/
  value_limit( pPID->U , -pPID->UMax , pPID->UMax );  /*PID运算输出限幅*/	
	
	pPID->PreE = pPID->E ;//保存本次偏差
}


void ComputeYawPID(PIDTypeDef *pPID)
{
	pPID->E = pPID->Des - pPID->FB;//计算当前偏差
	
	if(pPID->E>=180)pPID->E-=360;
	if(pPID->E<=-180)pPID->E+=360;

	if(((pPID->U <= pPID->UMax && pPID->E > 0) || (pPID->U >= -pPID->UMax && pPID->E < 0)) \
		    && ABS(pPID->E) < pPID->EMin)//积分分离
	{
		pPID->SumE += pPID->E;//计算偏差积分
	}
	value_limit( pPID->SumE , -pPID->SumEMax , pPID->SumEMax );//积分限幅
	pPID->Ui = pPID->Ki * pPID->SumE;
	value_limit( pPID->Ui , -pPID->UiMax , pPID->UiMax );
	
	pPID->Up = pPID->Kp * pPID->E;
	value_limit( pPID->Up , -pPID->UpMax , pPID->UpMax );
	
	pPID->Ud = pPID->Kd * ( pPID->E - pPID->PreE );
	value_limit( pPID->Ud , -pPID->UdMax , pPID->UdMax );
	
	pPID->U = pPID->Up + pPID->Ui + pPID->Ud;/*位置式PID计算公式*/
  value_limit( pPID->U , -pPID->UMax , pPID->UMax );  /*PID运算输出限幅*/
  
	
	
	pPID->PreE = pPID->E ;//保存本次偏差
}


//计算x和y位置方向pid，机体坐标系转换到导航坐标系
void ComputePID_locx(PIDTypeDef *pPID)
{
	//pPID->E = pPID->Des - pPID->FB;//计算当前偏差

	Ctrler.locxPID.E = (Ctrler.locxPID.Des-Ctrler.locxPID.FB)*Cos_Yaw - (Ctrler.locyPID.Des-Ctrler.locyPID.FB)*Sin_Yaw ;
	
	pPID->E = 	Ctrler.locxPID.E ;
	
	if(((pPID->U <= pPID->UMax && pPID->E > 0) || (pPID->U >= -pPID->UMax && pPID->E < 0)) \
		    && ABS(pPID->E) < pPID->EMin)//积分分离
	{
		pPID->SumE += pPID->E;//计算偏差积分
	}
	value_limit( pPID->SumE , -pPID->SumEMax , pPID->SumEMax );//积分限幅
	pPID->Ui = pPID->Ki * pPID->SumE;
	value_limit( pPID->Ui , -pPID->UiMax , pPID->UiMax );
	
	pPID->Up = pPID->Kp * pPID->E;
	value_limit( pPID->Up , -pPID->UpMax , pPID->UpMax );
	
	pPID->Ud = pPID->Kd * ( pPID->E - pPID->PreE );
	value_limit( pPID->Ud , -pPID->UdMax , pPID->UdMax );
	
	pPID->U = pPID->Up + pPID->Ui + pPID->Ud;/*位置式PID计算公式*/
  value_limit( pPID->U , -pPID->UMax , pPID->UMax );  /*PID运算输出限幅*/	
	
	pPID->PreE = pPID->E ;//保存本次偏差
}

void ComputePID_locy(PIDTypeDef *pPID)
{
	//pPID->E = pPID->Des - pPID->FB;//计算当前偏差

	Ctrler.locyPID.E = (Ctrler.locyPID.Des-Ctrler.locyPID.FB)*Cos_Yaw + (Ctrler.locxPID.Des-Ctrler.locxPID.FB)*Sin_Yaw ;
	
	pPID->E = Ctrler.locyPID.E ;
	
	if(((pPID->U <= pPID->UMax && pPID->E > 0) || (pPID->U >= -pPID->UMax && pPID->E < 0)) \
		    && ABS(pPID->E) < pPID->EMin)//积分分离
	{
		pPID->SumE += pPID->E;//计算偏差积分
	}
	value_limit( pPID->SumE , -pPID->SumEMax , pPID->SumEMax );//积分限幅
	pPID->Ui = pPID->Ki * pPID->SumE;
	value_limit( pPID->Ui , -pPID->UiMax , pPID->UiMax );
	
	pPID->Up = pPID->Kp * pPID->E;
	value_limit( pPID->Up , -pPID->UpMax , pPID->UpMax );
	
	pPID->Ud = pPID->Kd * ( pPID->E - pPID->PreE );
	value_limit( pPID->Ud , -pPID->UdMax , pPID->UdMax );
	
	pPID->U = pPID->Up + pPID->Ui + pPID->Ud;/*位置式PID计算公式*/
  value_limit( pPID->U , -pPID->UMax , pPID->UMax );  /*PID运算输出限幅*/	
	
	pPID->PreE = pPID->E ;//保存本次偏差
}

void Clear_Structure(void)
{
	Ctrler.pitchPID.SumE=0;
	Ctrler.rollPID.SumE=0;
	Ctrler.yawPID.SumE=0;
	Ctrler.gyroxPID.SumE=0;
	Ctrler.gyroyPID.SumE=0;
	Ctrler.gyrozPID.SumE=0;
	Ctrler.Z_posPID.SumE=0;
	Ctrler.Z_ratePID.SumE=0;
  
	Ctrler.locxPID.Des=Ctrler.locxPID.FB;
	Ctrler.locyPID.Des=Ctrler.locyPID.FB;
	
//	Ctrler.locxsPID.Des=0;
//	Ctrler.locysPID.Des=0;
//	Ctrler.pitchPID.Des=0;
//	Ctrler.rollPID.Des=0;
	Ctrler.yawPID.Des = Ctrler.yawPID.FB;
}
