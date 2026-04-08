#include "main.h"
#include "creat_task.h"

// main() is the entry point of the program; execution starts here after reset and startup code runs
int main(void)
{ 
    BSP_Init(); // Initialize Board Support Package (hardware peripherals: GPIO, timers, UART, etc.)

  //创建开始任务 (chuàng jiàn kāi shǐ rèn wù) - "Create start task"
  // xTaskCreate() is a FreeRTOS function that creates a new task
  xTaskCreate((TaskFunction_t )start_task,            //任务函数 (rèn wù hán shù) - "task function" - pointer to the function that will run as the task
        (const char*    )"start_task",          //任务名称 (rèn wù míng chēng) - "task name" - human-readable string for debugging
        (uint16_t       )START_STK_SIZE,        //任务堆栈大小 (rèn wù duī zhàn dà xiǎo) - "task stack size" - amount of memory (in words) reserved for this task's stack
        (void*          )NULL,                  //传递给任务函数的参数 (chuán dì gěi rèn wù hán shù de cān shù) - "parameter passed to task function" - NULL means no parameter
        (UBaseType_t    )START_TASK_PRIO,       //任务优先级 (rèn wù yōu xiān jí) - "task priority" - higher number = higher priority
        (TaskHandle_t*  )&StartTask_Handler);   //任务句柄 (rèn wù jù bǐng) - "task handle" - a reference/ID to control this task later
  vTaskStartScheduler();          //开启任务调度 (kāi qǐ rèn wù diào dù) - "start task scheduler" - begins FreeRTOS multitasking; this function never returns
}

//开始任务任务函数 (kāi shǐ rèn wù rèn wù hán shù) - "Start task function"
// This task's job is to create all other application tasks, then delete itself
void start_task(void *pvParameters)
{
  taskENTER_CRITICAL();           //进入临界区 (jìn rù lín jiè qū) - "enter critical section" - disables interrupts to protect the following code from being interrupted
 
  // Create SystemMonitor_Task - runs at 1 Hz to check system health
  xTaskCreate((TaskFunction_t )SystemMonitor_Task,     
        (const char*    )"SystemMonitor_Task",   
        (uint16_t       )SYSTEMMONITOR_STK_SIZE, 
        (void*          )NULL,
        (UBaseType_t    )SYSTEMMONITOR_TASK_PRIO,
        (TaskHandle_t*  )&SystemMonitorTask_Handler);       

  // Create IMU_DataDeal_Task - processes IMU (Inertial Measurement Unit) sensor data at 1000 Hz
  xTaskCreate((TaskFunction_t )IMU_DataDeal_Task,     
        (const char*    )"IMU_DataDeal_Task",   
        (uint16_t       )IMU_DataDeal_STK_SIZE, 
        (void*          )NULL,
        (UBaseType_t    )IMU_DataDeal_TASK_PRIO,
        (TaskHandle_t*  )&IMU_DataDealTask_Handler);  
                
    // Create IMUSample_Task - samples raw IMU sensor readings at 1000 Hz
    xTaskCreate((TaskFunction_t )IMUSample_Task,     
        (const char*    )"IMUSample_Task",   
        (uint16_t       )IMUSAMPLE_STK_SIZE, 
        (void*          )NULL,
        (UBaseType_t    )IMUSAMPLE_TASK_PRIO,
        (TaskHandle_t*  )&IMUSampleTask_Handler); 


  // Create Stabilizer_Task - controls aircraft attitude (orientation) at 200 Hz
  xTaskCreate((TaskFunction_t )Stabilizer_Task,     
        (const char*    )"Stabilizer_Task",   
        (uint16_t       )STABILIZER_STK_SIZE, 
        (void*          )NULL,
        (UBaseType_t    )STABILIZER_Task_TASK_PRIO,
        (TaskHandle_t*  )&Stabilizer_Task_Handler); 

  // Create Remoter_Task - handles remote control input at 100 Hz
  xTaskCreate((TaskFunction_t )Remoter_Task,     
        (const char*    )"Remoter_Task",   
        (uint16_t       )REMOTERTASK_STK_SIZE, 
        (void*          )NULL,
        (UBaseType_t    )REMOTERTASK_TASK_PRIO,
        (TaskHandle_t*  )&RemoterTaskTask_Handler); 			

   // Create Autofly_Task - autonomous flight control at 200 Hz
   xTaskCreate((TaskFunction_t )Autofly_Task,     
        (const char*    )"Autofly_Task",   
        (uint16_t       )AUTOFLYTASK_STK_SIZE, 
        (void*          )NULL,
        (UBaseType_t    )AUTOFLYTASK_TASK_PRIO,
        (TaskHandle_t*  )&AutoflyTask_Handler); 		
  // Create Send_Task - wireless UART communication at 100 Hz
  xTaskCreate((TaskFunction_t )Send_Task,     
        (const char*    )"Send_Task",   
        (uint16_t       )SENDTASK_STK_SIZE, 
        (void*          )NULL,
        (UBaseType_t    )SENDTASK_PRIO,
        (TaskHandle_t*  )&SendTask_Handler); 								
                
  vTaskDelete(StartTask_Handler); //删除开始任务 (shān chú kāi shǐ rèn wù) - "delete start task" - this task deletes itself since its job (creating other tasks) is done
  taskEXIT_CRITICAL();            //退出临界区 (tuì chū lín jiè qū) - "exit critical section" - re-enables interrupts (though this line never executes because task was deleted)
}


/*--------------------------------------------------------
函数功能： 系统监视器 (hán shù gōng néng: xì tǒng jiān shì qì) - "Function: System monitor"
帧率    ：  1 (zhèn lǜ: 1) - "Frame rate: 1 Hz" (runs once per second)
----------------------------------------------------------*/
void SystemMonitor_Task(void *pvParameters)
{
    TickType_t PreviousWakeTime; // Stores the last time this task was woken up
    const TickType_t TimeIncrement = pdMS_TO_TICKS(1000); // Convert 1000 milliseconds to RTOS ticks
    PreviousWakeTime = xTaskGetTickCount(); // Initialize with current tick count
    while(1) // Infinite loop - task runs forever
  {
      SystemErrorDetect(); // Check for system errors or faults
      
      vTaskDelayUntil(&PreviousWakeTime, TimeIncrement ); // Sleep until exactly 1000ms has passed since last wake (maintains precise 1 Hz timing)
  }
}

/*--------------------------------------------------------
函数功能： 无线串口任务 (hán shù gōng néng: wú xiàn chuàn kǒu rèn wù) - "Function: Wireless serial port task"
帧率    ：  100 (zhèn lǜ: 100) - "Frame rate: 100 Hz" (runs 100 times per second)
----------------------------------------------------------*/
void Send_Task(void *pvParameters)
{
    TickType_t PreviousWakeTime;
    const TickType_t TimeIncrement = pdMS_TO_TICKS(10); // 10ms period = 100 Hz
    PreviousWakeTime = xTaskGetTickCount();	
  while(1)
  {
        ANO_Report_UserData1(); // Send telemetry data (ANO protocol - a common Chinese flight controller protocol)
        send_to_linux(); // Send data to Linux companion computer (if present)
        Send_Groundstation_Telemetry_UART4(); // Send telemetry to Ground Station
        Process_GroundStation_Command(); // Process received commands
        usart3_send();//串口三发送任务 (chuàn kǒu sān fā sòng rèn wù) - "UART3 send task" - transmit data via UART3 peripheral
        system_monitor.USART2_task_cnt++; // Increment task execution counter (for monitoring task health)
        vTaskDelayUntil(&PreviousWakeTime, TimeIncrement );
  }
}

/*--------------------------------------------------------
函数功能： 陀螺仪更新 (hán shù gōng néng: tuó luó yí gēng xīn) - "Function: Gyroscope update" (actually full IMU sensor fusion)
帧率    ： 1000 (zhèn lǜ: 1000) - "Frame rate: 1000 Hz"
----------------------------------------------------------*/
extern _imu_st imu_data; // 'extern' means this variable is defined in another file; we're just declaring we'll use it here

void IMU_DataDeal_Task(void *pvParameters)
{
    TickType_t PreviousWakeTime;
    const TickType_t TimeIncrement = pdMS_TO_TICKS(1); // 1ms period = 1000 Hz
    PreviousWakeTime = xTaskGetTickCount();	
  while(1)
  {
        IMU_Update_Mahony(&imu_data,1e-3f); // Run Mahony filter algorithm to fuse gyro/accel into attitude estimate; 1e-3f = 0.001 = 1ms sample time
        system_monitor.IMUUpdateTask_cnt++; // Count executions for health monitoring
        vTaskDelayUntil(&PreviousWakeTime, TimeIncrement );
  }
}

/*--------------------------------------------------------
函数功能： 陀螺仪采样 (hán shù gōng néng: tuó luó yí cǎi yàng) - "Function: Gyroscope sampling" (raw sensor reading)
帧率    ： 1000 (zhèn lǜ: 1000) - "Frame rate: 1000 Hz"
----------------------------------------------------------*/
void IMUSample_Task(void *pvParameters)
{
    TickType_t PreviousWakeTime;
    const TickType_t TimeIncrement = pdMS_TO_TICKS(1); // 1ms = 1000 Hz
    PreviousWakeTime = xTaskGetTickCount();	
  while(1)
  {
        Sensor_Data_Prepare(); // Read raw sensor values from IMU hardware (SPI/I2C communication)
        system_monitor.IMUSampleTask_cnt++;
        vTaskDelayUntil(&PreviousWakeTime, TimeIncrement );
  }
  
}
/*--------------------------------------------------------
函数功能： 控制姿态任务 (hán shù gōng néng: kòng zhì zī tài rèn wù) - "Function: Control attitude task" (stabilization/flight control)
帧率    ： 200 (zhèn lǜ: 200) - "Frame rate: 200 Hz"
----------------------------------------------------------*/
void Stabilizer_Task(void *pvParameters)
{
    TickType_t PreviousWakeTime;
    const TickType_t TimeIncrement = pdMS_TO_TICKS(5); // 5ms = 200 Hz
    PreviousWakeTime = xTaskGetTickCount();	
  while(1)
    {	
        stabilizer_Task(); // Run PID controllers and compute motor outputs to stabilize aircraft

        system_monitor.stabilizerTask_cnt++;
        vTaskDelayUntil(&PreviousWakeTime, TimeIncrement );
  }
}

/*--------------------------------------------------------
函数功能： 遥控器任务 (hán shù gōng néng: yáo kòng qì rèn wù) - "Function: Remote controller task"
帧率    ： 100 (zhèn lǜ: 100) - "Frame rate: 100 Hz"
----------------------------------------------------------*/
void Remoter_Task(void *pvParameters)
{
    TickType_t PreviousWakeTime;
    const TickType_t TimeIncrement = pdMS_TO_TICKS(10); // 10ms = 100 Hz
    PreviousWakeTime = xTaskGetTickCount();	
  while(1)
  {
        remoter_task(); // Process remote control receiver input (RC radio commands)
        system_monitor.remoter_task_cnt++;
        vTaskDelayUntil(&PreviousWakeTime, TimeIncrement );
  }
}

/*--------------------------------------------------------
函数功能： 自主飞行任务 (hán shù gōng néng: zì zhǔ fēi xíng rèn wù) - "Function: Autonomous flight task"
帧率    ： 200 (zhèn lǜ: 200) - "Frame rate: 200 Hz"
----------------------------------------------------------*/
void Autofly_Task(void *pvParameters)
{
    TickType_t PreviousWakeTime;
    const TickType_t TimeIncrement = pdMS_TO_TICKS(5); // 5ms = 200 Hz
    PreviousWakeTime = xTaskGetTickCount();	
  while(1)
  {
        AutoflyTask(); // Execute autonomous navigation algorithms (waypoint following, etc.)
        system_monitor.AutoflyTask_cnt++;
        vTaskDelayUntil(&PreviousWakeTime, TimeIncrement );
  }
}



