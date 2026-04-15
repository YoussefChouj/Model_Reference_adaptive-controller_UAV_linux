# FreeRTOS Primitives Used

> Documents **only** the FreeRTOS API primitives this firmware actually uses, what they do, and — critically — what the firmware **does not use** and the architectural consequences of those omissions.

**Canonical reference**: [FreeRTOS API Reference](https://www.freertos.org/a00106.html) — do **not** copy; link only.

**Related wiki**: [[Multi-rate Task Partitioning]], [[STM32F4 Peripherals Reference]], [[Interrupt Map]]

---

## 1. Primitives Used

### 1.1 `xTaskCreate()` — Task Creation

**FreeRTOS API**: Creates a new task and adds it to the ready queue.

```c
BaseType_t xTaskCreate(
    TaskFunction_t pxTaskCode,      // Function pointer
    const char * pcName,            // Debug name
    uint16_t usStackDepth,          // Stack size in words (not bytes)
    void * pvParameters,            // Argument passed to task
    UBaseType_t uxPriority,         // Priority (higher number = higher priority)
    TaskHandle_t * pxCreatedTask    // Handle for later control
);
```

**Usage in this firmware**: `main.c:20–89` creates 7 tasks in `start_task()`:

| Task | Function | Period | Stack constant | Priority constant |
|:---|:---|:---|:---|:---|
| start_task | `start_task()` | One-shot | `START_STK_SIZE` | `START_TASK_PRIO` |
| SystemMonitor | `SystemMonitor_Task()` | 1 Hz (1000 ms) | `SYSTEMMONITOR_STK_SIZE` | `SYSTEMMONITOR_TASK_PRIO` |
| IMU_DataDeal | `IMU_DataDeal_Task()` | 1 kHz (1 ms) | `IMU_DataDeal_STK_SIZE` | `IMU_DataDeal_TASK_PRIO` |
| IMUSample | `IMUSample_Task()` | 1 kHz (1 ms) | `IMUSAMPLE_STK_SIZE` | `IMUSAMPLE_TASK_PRIO` |
| Stabilizer | `Stabilizer_Task()` | 200 Hz (5 ms) | `STABILIZER_STK_SIZE` | `STABILIZER_Task_TASK_PRIO` |
| Remoter | `Remoter_Task()` | 100 Hz (10 ms) | `REMOTERTASK_STK_SIZE` | `REMOTERTASK_TASK_PRIO` |
| Autofly | `Autofly_Task()` | 200 Hz (5 ms) | `AUTOFLYTASK_STK_SIZE` | `AUTOFLYTASK_TASK_PRIO` |
| Send | `Send_Task()` | 100 Hz (10 ms) | `SENDTASK_STK_SIZE` | `SENDTASK_PRIO` |

The priority/stack constants are defined in a header (not tracked in git). The exact values are not visible in the repository, but the relative ordering is inferred from the comment structure and task criticality.

**Architectural choice**: All tasks are created at boot in `start_task()`, which then deletes itself (`main.c:91`). No tasks are created dynamically at runtime. This is a common pattern in embedded systems — it avoids heap fragmentation and makes memory usage deterministic.

### 1.2 `vTaskStartScheduler()` — Start Multitasking

**FreeRTOS API**: Starts the FreeRTOS tick interrupt and begins scheduling tasks. This function **never returns** under normal operation.

**Usage**: `main.c:26` — called once after `start_task` is created.

```c
vTaskStartScheduler();  // Never returns
```

Before this call, only `main()` runs (single-threaded). After this call, the scheduler takes over and the highest-priority ready task runs.

### 1.3 `vTaskDelayUntil()` — Deterministic Periodic Scheduling

**FreeRTOS API**: Blocks the calling task until an absolute tick count is reached, providing **jitter-free periodic execution**.

```c
void vTaskDelayUntil(
    TickType_t * pxPreviousWakeTime,  // Updated each call
    TickType_t xTimeIncrement         // Period in ticks
);
```

**Why not `vTaskDelay()`?**

`vTaskDelay(n)` delays for `n` ticks *from the current moment*. If the task's computation takes variable time, the actual period varies:

```
vTaskDelay(5):     |---compute(2)---delay(5)---|---compute(3)---delay(5)---|
Actual period:              7 ms                         8 ms
```

`vTaskDelayUntil()` delays until an absolute time, absorbing computation jitter:

```
vTaskDelayUntil(5): |---compute(2)---wait(3)---|---compute(3)---wait(2)---|
Actual period:              5 ms                         5 ms
```

This is critical for control loops where `dt` must be constant. The Mahony filter (`imu_update.c:53`) and MRAC (`mrac.h:194`) both hardcode their dt values assuming their respective tasks run at exactly the specified period.

**Usage pattern** (all 7 periodic tasks follow this template):

```c
void SomeTask(void *pvParameters)
{
    TickType_t PreviousWakeTime;
    const TickType_t TimeIncrement = pdMS_TO_TICKS(5);  // 5 ms = 200 Hz
    PreviousWakeTime = xTaskGetTickCount();
    while(1)
    {
        do_work();
        vTaskDelayUntil(&PreviousWakeTime, TimeIncrement);
    }
}
```

### 1.4 `pdMS_TO_TICKS()` — Convert Milliseconds to Ticks

**FreeRTOS macro**: Converts a time in milliseconds to the equivalent number of scheduler ticks.

```c
#define pdMS_TO_TICKS(xTimeInMs) ((TickType_t)(xTimeInMs * configTICK_RATE_HZ / 1000))
```

**Usage**: Every task in `main.c` uses this to set the period:

| Task | Call | Period |
|:---|:---|:---|
| SystemMonitor | `pdMS_TO_TICKS(1000)` | 1 Hz |
| IMU_DataDeal | `pdMS_TO_TICKS(1)` | 1 kHz |
| IMUSample | `pdMS_TO_TICKS(1)` | 1 kHz |
| Stabilizer | `pdMS_TO_TICKS(5)` | 200 Hz |
| Remoter | `pdMS_TO_TICKS(10)` | 100 Hz |
| Autofly | `pdMS_TO_TICKS(5)` | 200 Hz |
| Send | `pdMS_TO_TICKS(10)` | 100 Hz |

The `configTICK_RATE_HZ` value is set in FreeRTOSConfig.h (not tracked in the repository). For `pdMS_TO_TICKS(1)` to resolve to exactly 1 tick, `configTICK_RATE_HZ` must be 1000. This is the standard value for 1 kHz control systems.

### 1.5 `xTaskGetTickCount()` / `xTaskGetTickCountFromISR()` — Current Tick

**FreeRTOS API**: Returns the current scheduler tick count (a monotonically increasing counter).

- `xTaskGetTickCount()` — call from task context
- `xTaskGetTickCountFromISR()` — call from ISR context (does not use critical sections)

**Usage in this firmware**:

1. **Task initialization**: Every periodic task calls `xTaskGetTickCount()` once to initialize `PreviousWakeTime` (e.g., `main.c:104`)
2. **SBUS timeout detection**: `DrvSbusGetOneByte()` in `BSP/usart1.c` uses `xTaskGetTickCountFromISR()` to record `sbus_last_valid_tick` — the timestamp of the last valid SBUS frame. The `Remoter_Task` compares this against the current tick to detect RC signal loss (see [[RemoterTask]])

### 1.6 `taskENTER_CRITICAL()` / `taskEXIT_CRITICAL()` — Critical Sections

**FreeRTOS API**: Disables all interrupts with priority at or below `configMAX_SYSCALL_INTERRUPT_PRIORITY`. This prevents both task preemption and ISR interruption.

**Usage**: `main.c:33, 92` — wraps the task creation block in `start_task()`:

```c
void start_task(void *pvParameters)
{
    taskENTER_CRITICAL();    // Disable interrupts
    // ... create all tasks ...
    vTaskDelete(StartTask_Handler);
    taskEXIT_CRITICAL();     // Re-enable (never reached — task deleted above)
}
```

The critical section here prevents any interrupt from firing during task creation. This ensures all tasks are created atomically before the scheduler starts dispatching them. The `taskEXIT_CRITICAL()` at line 92 is technically dead code since `vTaskDelete()` never returns, but it's good practice for maintainability.

**Not used elsewhere**: No other code in the firmware uses critical sections. All shared data access between tasks is unprotected — see Section 3.

### 1.7 `vTaskDelete()` — Task Deletion

**FreeRTOS API**: Removes a task from the scheduler and frees its stack memory.

**Usage**: `main.c:91` — `start_task()` deletes itself after creating all other tasks:

```c
vTaskDelete(StartTask_Handler);
```

This is the only use of `vTaskDelete()` in the firmware. No other task is ever deleted at runtime.

---

## 2. `configTICK_RATE_HZ` and Task Period Mapping

The tick rate determines the finest granularity of `vTaskDelayUntil()`. For this firmware to achieve 1 kHz IMU tasks with `pdMS_TO_TICKS(1) = 1 tick`, the tick rate must be:

```
configTICK_RATE_HZ = 1000
```

This means:
- 1 tick = 1 ms
- SysTick interrupt fires every 1 ms
- `pdMS_TO_TICKS(5)` = 5 ticks = 5 ms = 200 Hz
- `pdMS_TO_TICKS(10)` = 10 ticks = 10 ms = 100 Hz

**Jitter consideration**: The SysTick interrupt has the lowest NVIC priority (typically 15 under `NVIC_PriorityGroup_4`). If a higher-priority ISR (e.g., USART1 at priority 0) is executing when SysTick fires, the tick is delayed. For a typical UART byte ISR taking ~1–5 µs, this jitter is negligible compared to the 1 ms tick period. But if a DMA TC handler or a long ISR chain delays SysTick by >100 µs, the 1 kHz IMU task timing could be affected.

---

## 3. What This Firmware Does NOT Use

This is arguably the most important section. The absence of these primitives has direct architectural consequences.

### 3.1 NOT Used: Queues (`xQueueCreate`, `xQueueSend`, `xQueueReceive`)

**What they do**: Thread-safe FIFO buffers for passing data between tasks.

**Consequence of absence**: All inter-task data sharing is via **global variables** with **no synchronization**. For example:
- `imu_data` (written by `IMU_DataDeal_Task` at 1 kHz, read by `Stabilizer_Task` at 200 Hz)
- `Ctrler` (written by `Stabilizer_Task`, read by `Send_Task`)
- `sbus_channel[]` (written in USART1 ISR, read by `Remoter_Task`)

This works in practice because:
1. Most shared variables are `float` (32-bit atomic read/write on Cortex-M4 with FPU)
2. Writers and readers operate at different frequencies with natural time separation
3. The scheduler is preemptive but tasks are synchronized to the tick boundary

It does **not** work perfectly — a reader can see a partially-updated multi-field struct if preempted mid-write. This is a known limitation, not a bug, for this class of firmware.

### 3.2 NOT Used: Semaphores / Mutexes (`xSemaphoreCreate`, `xSemaphoreTake/Give`)

**What they do**: Mutual exclusion for shared resources, priority inversion protection.

**Consequence of absence**: No protection against concurrent access to shared data. If two tasks need to atomically read-modify-write the same structure, they cannot guarantee consistency. In this firmware, each global is effectively "owned" by one writer task, with others as readers — a disciplined convention that avoids the need for mutexes.

### 3.3 NOT Used: Event Groups (`xEventGroupCreate`, `xEventGroupSetBits`)

**What they do**: Synchronize tasks on multiple conditions (logical AND/OR of event flags).

**Consequence of absence**: Task coordination is achieved purely through shared flags (`DroneStatus.ARM_Status`, `sbus_lost`, `TWC.execute`) checked at polling rate. There's no event-driven wake-up — every task runs at its fixed period regardless of whether there's new data.

### 3.4 NOT Used: Software Timers (`xTimerCreate`)

**What they do**: Schedule callbacks at configurable intervals without dedicating a full task.

**Consequence of absence**: Every periodic function requires a dedicated FreeRTOS task with its own stack. The firmware uses 7 tasks, each with its own stack allocation. Software timers could have replaced the simpler tasks (SystemMonitor, Send_Task) with less memory overhead.

### 3.5 NOT Used: Task Notifications (`xTaskNotify`)

**What they do**: Lightweight, faster alternative to semaphores for task signaling.

**Consequence of absence**: ISRs cannot efficiently wake specific tasks when data arrives. Instead, all tasks run at their fixed rate and check for new data each cycle, even if nothing arrived.

### 3.6 NOT Used: Stack Overflow Detection

The FreeRTOS `configCHECK_FOR_STACK_OVERFLOW` option, if enabled, calls `vApplicationStackOverflowHook()` when a task's stack usage exceeds its allocation. The default value in `FreeRTOS.h:407–408` is 0 (disabled).

**Consequence of absence**: If any task's stack overflows (e.g., deep recursion in PID computation during a transient), it silently corrupts adjacent memory. There is no runtime warning. Stack sizing must be verified offline by static analysis or worst-case estimation.

---

## 4. Memory Architecture

FreeRTOS manages two types of memory for tasks:

| Component | Size | Location |
|:---|:---|:---|
| Task Control Block (TCB) | ~92 bytes per task | FreeRTOS heap |
| Task stack | `usStackDepth × 4` bytes per task | FreeRTOS heap |
| FreeRTOS heap | `configTOTAL_HEAP_SIZE` bytes | Static array in RAM |

With 7 tasks (after start_task deletes itself), the minimum RAM consumption is approximately:
- 7 TCBs × 92 bytes = 644 bytes
- 7 stacks × (estimated 256–512 words) × 4 bytes = 7–14 KB
- FreeRTOS kernel overhead ≈ 1 KB
- **Total estimate: ~10–16 KB** (STM32F405 has 128 KB SRAM + 64 KB CCM RAM)

The `Stabilizer_Task` likely needs the largest stack due to the deep call chain: `stabilizer_Task()` → `Compute_Motor()` → `Update_Des()` → `ComputePID()` × many loops → `MRAC_Control()` → projection/RBF math.

---

## 5. Evidence vs. Inference

### Verified from Code

- All 7 `xTaskCreate()` calls with task functions and names (`main.c:20–89`)
- `vTaskStartScheduler()` at `main.c:26`
- `vTaskDelayUntil()` used in all 7 periodic tasks with `pdMS_TO_TICKS()` conversion
- `taskENTER_CRITICAL()` / `taskEXIT_CRITICAL()` at `main.c:33, 92`
- `vTaskDelete(StartTask_Handler)` at `main.c:91`
- `xTaskGetTickCount()` in every task's initialization
- `xTaskGetTickCountFromISR()` used in SBUS processing (referenced from usart1.c include of `task.h`)
- No `xQueueCreate`, `xSemaphoreCreate`, `xEventGroupCreate`, or `xTimerCreate` anywhere in the application code
- `configCHECK_FOR_STACK_OVERFLOW` defaults to 0 in `FreeRTOS.h:407–408`

### Inferred / Theoretical Context

- `configTICK_RATE_HZ = 1000` is inferred from `pdMS_TO_TICKS(1)` needing to equal 1 tick; the FreeRTOSConfig.h file is not tracked in the repository
- Stack size estimates are approximate — the actual constants are defined in a header not tracked by git
- The claim about float atomicity on Cortex-M4 relies on the ARM architecture guarantee of single-cycle 32-bit load/store, which is true for naturally-aligned accesses
- SysTick priority assignment is inferred from standard FreeRTOS Cortex-M4 port behavior

---

## 6. Further Reading

- **FreeRTOS Cortex-M4 port**: [FreeRTOS ARM Cortex-M4F port](https://www.freertos.org/RTOS-Cortex-M3-M4.html) — interrupt priority configuration details
- **vTaskDelayUntil vs vTaskDelay**: [FreeRTOS timing tutorial](https://www.freertos.org/vtaskdelayuntil.html)
- **This codebase**: [[Multi-rate Task Partitioning]] for task scheduling analysis, [[Interrupt Map]] for ISR/task interaction
