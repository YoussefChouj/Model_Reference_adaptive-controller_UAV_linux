#include  "BSP.h"
#include "SINS.h"
#include "ADC.h"
 void BSP_Init(void)
 {
	 NVIC_PriorityGroupConfig(NVIC_PriorityGroup_4);

	 LED_Init();
	 PWM_TIM3_Init();  
	 ADC1_Configuration();//千万别忘了初始化！！否则系统卡死
	 delay_ms(2000);
	 
	 SPI_Configuration();
	 bmi088_init();
	 USART1_Configuration();  //遥控器
	 USART2_Configuration();  //
	 USART3_Configuration();//串口三
	 UART4_Configuration();   //机载电脑
	 UART5_Configuration();   //无线串口
	 
	 BEEP_Init();
	 GPIO_ResetBits(GPIOA,GPIO_Pin_11 ); //绿色
	 GPIO_SetBits(GPIOA,GPIO_Pin_12 );
	 GPIO_SetBits(GPIOC,GPIO_Pin_8 );
   delay_ms(2000);
	 PWM_TIM4_Init();
	 
	 linux_yolo_data.stree_angle = 90.0f;

 }

