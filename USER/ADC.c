#include "ADC.h"

void ADC1_Configuration(void)      //ADC检测电源电压
{
	//GPIOA  ADC时钟
	RCC_AHB1PeriphClockCmd(RCC_AHB1Periph_GPIOA, ENABLE);
	RCC_APB2PeriphClockCmd(RCC_APB2Periph_ADC1, ENABLE);
	
  //PA4模拟输入
	GPIO_InitTypeDef GPIO_InitStruct;
	GPIO_InitStruct.GPIO_Pin = GPIO_Pin_4;
	GPIO_InitStruct.GPIO_Mode = GPIO_Mode_AN;
	GPIO_InitStruct.GPIO_PuPd = GPIO_PuPd_NOPULL;
	GPIO_Init(GPIOA, &GPIO_InitStruct);
	
	// SET ADC
	ADC_InitTypeDef ADC_InitStruct;
	ADC_StructInit(&ADC_InitStruct);
	ADC_InitStruct.ADC_Resolution = ADC_Resolution_12b;  // 12位分辨率
	ADC_InitStruct.ADC_ScanConvMode = DISABLE;           // 单通道转换
	ADC_InitStruct.ADC_ContinuousConvMode = DISABLE;     // 单次转换
	ADC_InitStruct.ADC_ExternalTrigConv = ADC_ExternalTrigConv_T1_CC1; // 外部触发
	ADC_Init(ADC1, &ADC_InitStruct);
	
  //ADC 通道
	ADC_RegularChannelConfig(ADC1, ADC_Channel_4, 1, ADC_SampleTime_3Cycles);

	//使能
	ADC_Cmd(ADC1, ENABLE);
	
//	ADC_ResetCalibration(ADC1);
//	while(ADC_GetResetCalibrationStatus(ADC1));
//	ADC_StartCalibration(ADC1);
//	while(ADC_GetCalibrationStatus(ADC1));
}

uint16_t ADC_Read(void) 
{
  //启动转换
	ADC_SoftwareStartConv(ADC1);
	//等待转换完成
  while(!ADC_GetFlagStatus(ADC1, ADC_FLAG_EOC));
  //读取ADC值
	uint16_t value = ADC_GetConversionValue(ADC1);
  ADC_ClearFlag(ADC1, ADC_FLAG_EOC);
  return value;
}

float Voltage_Calculation(uint16_t adc_value) 
{
  float voltage = adc_value * (3.3f / 4095);  
  return voltage;
}
