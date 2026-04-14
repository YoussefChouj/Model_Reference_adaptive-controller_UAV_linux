#include "pwm.h"

/**
 * @module  pwm.c
 * @subsystem  drivers
 * @depends  pwm.h
 * @owns  timer PWM initialization and final actuator compare-register writes
 * @caution  CCR channel mapping must stay aligned with motor mixing assumptions in TASK/StabilizerTask.c
 */

//APB1   42m
//APB2   84m
//21分频到 84000000/21 = 4M   0.25us

/*初始化高电平时间1000us（4000份）*/
#define INIT_DUTY 3000 //u16(1000/0.25)
/*频率400hz*/
#define HZ        400
/*精度10000，每份0.25us*/
#define ACCURACY 10000 //u16(2500/0.25) //accuracy

MOTORTypeDef mymotor;
void PWM_TIM3_Init (void) //300hz
{
    TIM_TimeBaseInitTypeDef  TIM_TimeBaseStructure;
    TIM_OCInitTypeDef  TIM_OCInitStructure;
    GPIO_InitTypeDef GPIO_InitStructure;

	  GPIO_StructInit(&GPIO_InitStructure);
    TIM_TimeBaseStructInit ( &TIM_TimeBaseStructure );
    TIM_OCStructInit ( &TIM_OCInitStructure );

    RCC_APB1PeriphClockCmd ( RCC_APB1Periph_TIM3, ENABLE );
    RCC_AHB1PeriphClockCmd ( RCC_AHB1Periph_GPIOA | RCC_AHB1Periph_GPIOB, ENABLE );

/////////////////////////////////////////////////////////////////////////////设置舵机
    GPIO_InitStructure.GPIO_Pin = GPIO_Pin_6 | GPIO_Pin_7 ;
    GPIO_InitStructure.GPIO_Mode = GPIO_Mode_AF;
    GPIO_InitStructure.GPIO_Speed = GPIO_Speed_100MHz;
    GPIO_InitStructure.GPIO_OType = GPIO_OType_PP;
    GPIO_InitStructure.GPIO_PuPd = GPIO_PuPd_UP ;
    GPIO_Init ( GPIOA, &GPIO_InitStructure );

    GPIO_PinAFConfig ( GPIOA, GPIO_PinSource6, GPIO_AF_TIM3 );  //TIM3 CH1
    GPIO_PinAFConfig ( GPIOA, GPIO_PinSource7, GPIO_AF_TIM3 );  //TIM3 CH2
		
		
		GPIO_InitStructure.GPIO_Pin = GPIO_Pin_0 | GPIO_Pin_1 ;
    GPIO_InitStructure.GPIO_Mode = GPIO_Mode_AF;
    GPIO_InitStructure.GPIO_Speed = GPIO_Speed_100MHz;
    GPIO_InitStructure.GPIO_OType = GPIO_OType_PP;
    GPIO_InitStructure.GPIO_PuPd = GPIO_PuPd_UP ;
    GPIO_Init ( GPIOB, &GPIO_InitStructure );
		
    GPIO_PinAFConfig ( GPIOB, GPIO_PinSource0, GPIO_AF_TIM3 );  //TIM3 CH3
    GPIO_PinAFConfig ( GPIOB, GPIO_PinSource1, GPIO_AF_TIM3 );  //TIM3 CH4

    /* Time base configuration */
    TIM_TimeBaseStructure.TIM_Period = 10000-1;    //2M/10000 = 200HZ
    TIM_TimeBaseStructure.TIM_Prescaler = 42-1;  //84M/42 =2M  0.5us
    TIM_TimeBaseStructure.TIM_ClockDivision = 0;
    TIM_TimeBaseStructure.TIM_CounterMode = TIM_CounterMode_Up;
    TIM_TimeBaseStructure.TIM_RepetitionCounter = 0;
    TIM_TimeBaseInit ( TIM3, &TIM_TimeBaseStructure );


    TIM_OCInitStructure.TIM_OCMode = TIM_OCMode_PWM1;
    TIM_OCInitStructure.TIM_OutputNState = TIM_OutputNState_Disable;
    TIM_OCInitStructure.TIM_OCPolarity = TIM_OCPolarity_High;
    TIM_OCInitStructure.TIM_OCNPolarity = TIM_OCNPolarity_Low;
    TIM_OCInitStructure.TIM_OCIdleState = TIM_OCIdleState_Set;
    TIM_OCInitStructure.TIM_OCNIdleState = TIM_OCNIdleState_Reset;

    /* PWM1 Mode configuration: Channel1 */
    TIM_OCInitStructure.TIM_OutputState = TIM_OutputState_Enable;
    TIM_OCInitStructure.TIM_Pulse = 0;
    TIM_OC1Init ( TIM3, &TIM_OCInitStructure );
    //TIM_OC1PreloadConfig(TIM1, TIM_OCPreload_Enable);

    /* PWM1 Mode configuration: Channel2 */
    //TIM_OCInitStructure.TIM_OutputState = TIM_OutputState_Enable;
    TIM_OCInitStructure.TIM_Pulse = 0;
    TIM_OC2Init ( TIM3, &TIM_OCInitStructure );
    //TIM_OC2PreloadConfig(TIM1, TIM_OCPreload_Enable);

    /* PWM1 Mode configuration: Channel3 */
    //TIM_OCInitStructure.TIM_OutputState = TIM_OutputState_Enable;
    TIM_OCInitStructure.TIM_Pulse = 0;
    TIM_OC3Init ( TIM3, &TIM_OCInitStructure );
    //TIM_OC3PreloadConfig(TIM1, TIM_OCPreload_Enable);

    /* PWM1 Mode configuration: Channel4 */
    //TIM_OCInitStructure.TIM_OutputState = TIM_OutputState_Enable;
    TIM_OCInitStructure.TIM_Pulse = 0;
    TIM_OC4Init ( TIM3, &TIM_OCInitStructure );
    //TIM_OC4PreloadConfig(TIM1, TIM_OCPreload_Enable);

    TIM_CtrlPWMOutputs ( TIM3, ENABLE );
    TIM_ARRPreloadConfig ( TIM3, ENABLE );
    TIM_Cmd ( TIM3, ENABLE );
		
		Set_Zero_Motors();

//  mymotor.motor1 = 2000; //左上  顺
//  mymotor.motor2 = 2000;  //右下 顺
//	mymotor.motor3 = 2000; //左下  逆
//	mymotor.motor4 = 2000;  //右上  逆
	
}
void PWM_TIM2_Init (void) //300hz
{
    TIM_TimeBaseInitTypeDef  TIM_TimeBaseStructure;
    TIM_OCInitTypeDef  TIM_OCInitStructure;
    GPIO_InitTypeDef GPIO_InitStructure;

	  GPIO_StructInit(&GPIO_InitStructure);
    TIM_TimeBaseStructInit ( &TIM_TimeBaseStructure );
    TIM_OCStructInit ( &TIM_OCInitStructure );

	  RCC_APB1PeriphClockCmd ( RCC_APB1Periph_TIM2, ENABLE );
    RCC_AHB1PeriphClockCmd ( RCC_AHB1Periph_GPIOA | RCC_AHB1Periph_GPIOB, ENABLE );

	
/////////////////////////////////////////////////////////////////////////////设置电机
    GPIO_InitStructure.GPIO_Pin = GPIO_Pin_5  ;
    GPIO_InitStructure.GPIO_Mode = GPIO_Mode_AF;
    GPIO_InitStructure.GPIO_Speed = GPIO_Speed_100MHz;
    GPIO_InitStructure.GPIO_OType = GPIO_OType_PP;
    GPIO_InitStructure.GPIO_PuPd = GPIO_PuPd_UP ;
    GPIO_Init ( GPIOA, &GPIO_InitStructure );

    GPIO_PinAFConfig ( GPIOA, GPIO_PinSource5, GPIO_AF_TIM2 );  //TIM2 CH1

			
		GPIO_InitStructure.GPIO_Pin = GPIO_Pin_3 | GPIO_Pin_10 | GPIO_Pin_11;
    GPIO_InitStructure.GPIO_Mode = GPIO_Mode_AF;
    GPIO_InitStructure.GPIO_Speed = GPIO_Speed_100MHz;
    GPIO_InitStructure.GPIO_OType = GPIO_OType_PP;
    GPIO_InitStructure.GPIO_PuPd = GPIO_PuPd_UP ;
    GPIO_Init ( GPIOB, &GPIO_InitStructure );
		
    GPIO_PinAFConfig ( GPIOB, GPIO_PinSource3,  GPIO_AF_TIM2 );  //TIM3 CH2
    GPIO_PinAFConfig ( GPIOB, GPIO_PinSource10, GPIO_AF_TIM2 );  //TIM3 CH3
		GPIO_PinAFConfig ( GPIOB, GPIO_PinSource11, GPIO_AF_TIM2 );  //TIM3 CH4

    /* Time base configuration */
    TIM_TimeBaseStructure.TIM_Period = 10000-1;    //3M/10000 = 300HZ
    TIM_TimeBaseStructure.TIM_Prescaler = 28-1;  //84M/28 =3M
    TIM_TimeBaseStructure.TIM_ClockDivision = 0;
    TIM_TimeBaseStructure.TIM_CounterMode = TIM_CounterMode_Up;
    TIM_TimeBaseStructure.TIM_RepetitionCounter = 0;
    TIM_TimeBaseInit ( TIM2, &TIM_TimeBaseStructure );


    TIM_OCInitStructure.TIM_OCMode = TIM_OCMode_PWM1;
    TIM_OCInitStructure.TIM_OutputNState = TIM_OutputNState_Disable;
    TIM_OCInitStructure.TIM_OCPolarity = TIM_OCPolarity_High;
    TIM_OCInitStructure.TIM_OCNPolarity = TIM_OCNPolarity_Low;
    TIM_OCInitStructure.TIM_OCIdleState = TIM_OCIdleState_Set;
    TIM_OCInitStructure.TIM_OCNIdleState = TIM_OCNIdleState_Reset;

    /* PWM1 Mode configuration: Channel1 */
    TIM_OCInitStructure.TIM_OutputState = TIM_OutputState_Enable;
    TIM_OCInitStructure.TIM_Pulse = 0;
    TIM_OC1Init ( TIM2, &TIM_OCInitStructure );
    //TIM_OC1PreloadConfig(TIM1, TIM_OCPreload_Enable);

    /* PWM1 Mode configuration: Channel2 */
    //TIM_OCInitStructure.TIM_OutputState = TIM_OutputState_Enable;
    TIM_OCInitStructure.TIM_Pulse = 0;
    TIM_OC2Init ( TIM2, &TIM_OCInitStructure );
    //TIM_OC2PreloadConfig(TIM1, TIM_OCPreload_Enable);

    /* PWM1 Mode configuration: Channel3 */
    //TIM_OCInitStructure.TIM_OutputState = TIM_OutputState_Enable;
    TIM_OCInitStructure.TIM_Pulse = 0;
    TIM_OC3Init ( TIM2, &TIM_OCInitStructure );
    //TIM_OC3PreloadConfig(TIM1, TIM_OCPreload_Enable);

    /* PWM1 Mode configuration: Channel4 */
    //TIM_OCInitStructure.TIM_OutputState = TIM_OutputState_Enable;
    TIM_OCInitStructure.TIM_Pulse = 0;
    TIM_OC4Init ( TIM2, &TIM_OCInitStructure );
    //TIM_OC4PreloadConfig(TIM1, TIM_OCPreload_Enable);

    TIM_CtrlPWMOutputs ( TIM2, ENABLE );
    TIM_ARRPreloadConfig ( TIM2, ENABLE );
    TIM_Cmd ( TIM2, ENABLE );

		//Set_Zero_Motors();
}


void PWM_TIM4_Init (void) //300hz  设置舵机
{
    TIM_TimeBaseInitTypeDef  TIM_TimeBaseStructure;
    TIM_OCInitTypeDef  TIM_OCInitStructure;
    GPIO_InitTypeDef GPIO_InitStructure;

	  GPIO_StructInit(&GPIO_InitStructure);
    TIM_TimeBaseStructInit ( &TIM_TimeBaseStructure );
    TIM_OCStructInit ( &TIM_OCInitStructure );

    RCC_APB1PeriphClockCmd ( RCC_APB1Periph_TIM4, ENABLE );
    RCC_AHB1PeriphClockCmd ( RCC_AHB1Periph_GPIOB, ENABLE );

/////////////////////////////////////////////////////////////////////////////设置舵机
    GPIO_InitStructure.GPIO_Pin = GPIO_Pin_6 | GPIO_Pin_7;
    GPIO_InitStructure.GPIO_Mode = GPIO_Mode_AF;
    GPIO_InitStructure.GPIO_Speed = GPIO_Speed_100MHz;
    GPIO_InitStructure.GPIO_OType = GPIO_OType_PP;
    GPIO_InitStructure.GPIO_PuPd = GPIO_PuPd_UP ;
    GPIO_Init ( GPIOB, &GPIO_InitStructure );

    GPIO_PinAFConfig ( GPIOB, GPIO_PinSource6, GPIO_AF_TIM4 );  //TIM4 CH1
		GPIO_PinAFConfig ( GPIOB, GPIO_PinSource7, GPIO_AF_TIM4 );  //TIM4 CH2
    
    /* Time base configuration */
    TIM_TimeBaseStructure.TIM_Period = 20000-1;    //1M/20000 = 50HZ
    TIM_TimeBaseStructure.TIM_Prescaler = 84-1;  //84M/84 =1M //1us
    TIM_TimeBaseStructure.TIM_ClockDivision = 0;
    TIM_TimeBaseStructure.TIM_CounterMode = TIM_CounterMode_Up;
    TIM_TimeBaseStructure.TIM_RepetitionCounter = 0;
    TIM_TimeBaseInit ( TIM4, &TIM_TimeBaseStructure );


    TIM_OCInitStructure.TIM_OCMode = TIM_OCMode_PWM1;
    TIM_OCInitStructure.TIM_OutputNState = TIM_OutputNState_Disable;
    TIM_OCInitStructure.TIM_OCPolarity = TIM_OCPolarity_High;
    TIM_OCInitStructure.TIM_OCNPolarity = TIM_OCNPolarity_Low;
    TIM_OCInitStructure.TIM_OCIdleState = TIM_OCIdleState_Set;
    TIM_OCInitStructure.TIM_OCNIdleState = TIM_OCNIdleState_Reset;

    /* PWM1 Mode configuration: Channel1 */
    TIM_OCInitStructure.TIM_OutputState = TIM_OutputState_Enable;
    TIM_OCInitStructure.TIM_Pulse = INIT_DUTY;
		
    TIM_OC1Init ( TIM4, &TIM_OCInitStructure );
		TIM_OC1PreloadConfig(TIM4, TIM_OCPreload_Enable);
		
		TIM_OC2Init ( TIM4, &TIM_OCInitStructure );
		TIM_OC2PreloadConfig(TIM4, TIM_OCPreload_Enable);

    TIM_CtrlPWMOutputs ( TIM4, ENABLE );
    TIM_ARRPreloadConfig ( TIM4, ENABLE );
    TIM_Cmd ( TIM4, ENABLE );
		
		SetPitchAngle(40); //保持初始位置，免得抽风
		SetRollAngle(90);
		//SetRollAngle(0);
}

//180度舵机：  1us
//0.5ms  ---0度     500
//1.0ms ----45度   1000
//1.5ms ----90度    1500
//2.0ms -----135度  2000
//2.5ms ----180度    2500

void SetPitchAngle(float angle)
{	
    TIM_SetCompare2(TIM4 , (2.5f + 10*angle/180)/100*20000);   // 修改 TIM4_CCR1 来控制占空比
}

void SetRollAngle(float angle)
{
    TIM_SetCompare1(TIM4 , (2.5f + 10*angle/180)/100*20000);   // 修改 TIM4_CCR1 来控制占空比
}

void Set_PWM_Motors(void)  //设置电机  
{
  // CONSTRAINT: Macro mapping M1/M4/M2/M3 in pwm.h is intentional and must not be reordered independently.
  // ARCH: This layer clamps and forwards mixer outputs; it does not redefine axis signs.
	value_limit( mymotor.motor1 , Motor_PWM_ZERO , Motor_PWM_MAX );		
	M1=mymotor.motor1;
	
	value_limit( mymotor.motor2 , Motor_PWM_ZERO , Motor_PWM_MAX );		
	M2=mymotor.motor2;
	
	value_limit( mymotor.motor3 , Motor_PWM_ZERO , Motor_PWM_MAX );		
	M3=mymotor.motor3;
	
	value_limit( mymotor.motor4 , Motor_PWM_ZERO , Motor_PWM_MAX );		
	M4=mymotor.motor4;
	
}

void Set_Zero_Motors(void)
{
	 M1 = Motor_PWM_ZERO;
	 M2 = Motor_PWM_ZERO; 
	 M3 = Motor_PWM_ZERO;
	 M4 = Motor_PWM_ZERO;
}

void Set_IDLE_Motors(void)
{
	 M1 = Motor_PWM_IDLE;
	 M2 = Motor_PWM_IDLE;
	 M3 = Motor_PWM_IDLE;
	 M4 = Motor_PWM_IDLE;
}

void SetBeep(int B)
{
	if(B==0)
	{
		TIM_SetCompare3(TIM4 , 0);     //从右往左看第三个    目前是蜂鸣器
    //0---->不响      1500----->中等音量
	}
	else
	{
		TIM_SetCompare3(TIM4 , 1000);
	}
}
