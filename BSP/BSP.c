#include  "BSP.h"
#include "SINS.h"
#include "ADC.h"
 void BSP_Init(void)
 {
	 NVIC_PriorityGroupConfig(NVIC_PriorityGroup_4);

	 LED_Init();
	 PWM_TIM2_Init();
	 PWM_TIM3_Init();
	 ADC1_Configuration();//ǧ������˳�ʼ����������ϵͳ����
	 delay_ms(2000);
	 
	 SPI_Configuration();
	 bmi088_init();
	 USART1_Configuration();  //ң����
	 USART2_Configuration();  //
	 USART3_Configuration();//������
	 UART4_Configuration();   //���ص���
	 UART5_Configuration();   //���ߴ���
	 
	 BEEP_Init();
	 GPIO_ResetBits(GPIOA,GPIO_Pin_11 ); //��ɫ
	 GPIO_SetBits(GPIOA,GPIO_Pin_12 );
	 GPIO_SetBits(GPIOC,GPIO_Pin_8 );
   delay_ms(2000);
	 PWM_TIM4_Init();
	 
	 linux_yolo_data.stree_angle = 90.0f;

 }

