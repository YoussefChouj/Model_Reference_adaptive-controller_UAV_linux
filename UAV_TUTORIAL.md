# UAV Flight Controller ！ Beginner Tutorial

This tutorial walks you from zero to understanding the STM32 + FreeRTOS UAV project in this repository.
It is written for beginners and is structured like you're building the project from scratch.

How to use this tutorial
- Work through sections in order.
- Try the "Mini-exercises" after each section.
- Use the `tutorial/visualize_imu.py` example to plot IMU data exported from the project.

---

## 1) Overview & Goal

Project goal: a 6-DoF flight controller running on an STM32F4 that reads IMU/GPS sensors, runs sensor fusion and control algorithms, and outputs motor PWM signals.

High-level components you'll learn:
- Hardware & wiring
- Board support and peripherals (BSP)
- Sensor drivers and IMU reading
- Sensor fusion (Mahony / AHRS)
- Control (PID loops)
- FreeRTOS tasks and scheduling
- Debugging and visualization

Mini-exercise: open `USER/JX_FLY.uvprojx` in Keil (if installed) to inspect project groups.

---

## 2) Tooling & setup (Windows)

Required tools (minimum):
- Keil MDK (uVision) + STM32F4 pack ！ recommended for building embedded firmware.
- A serial terminal (PuTTY, Tera Term) to view `printf`/UART logs.
- Python 3.8+ (for visualization examples) with `numpy` and `matplotlib` (see `tutorial/requirements.txt`).
- Optional: ST-Link or J-Link for flashing and debugging.

Mini-exercise: install Python and run `python --version` in PowerShell.

---

## 3) Recreating the project from scratch (conceptual steps)

We'll view the project as small modules you can implement independently.

Contract (what each module should do):
- BSP: initialize clocks, timers, PWM, UART and SPI. Inputs: hardware registers; outputs: initialized peripherals.
- Drivers: read sensor registers and produce raw sensor frames (accel/gyro/mag/GPS). Inputs: SPI/I2C/UART; outputs: timestamped samples.
- IMU update: fuse raw data into an orientation (quaternion or Euler angles). Inputs: raw sensor samples; outputs: yaw/pitch/roll.
- Control: take desired setpoints and current attitude to compute motor outputs. Inputs: attitude, setpoints; outputs: PWM commands.
- Tasks: schedule sensor reading, fusion, control, and telemetry using FreeRTOS.

Mini-exercise: sketch a block diagram showing the flow from sensors -> fusion -> controller -> motors.

---

## 4) File-by-file orientation (where to look)

Important files in this repo:
- `USER/main.c` ！ program entry; RTOS start.
- `BSP/` ！ `pwm.c`, `spi.c`, `usart*.c` ！ hardware abstractions.
- `API/` ！ `bmi088_driver.c`, `imu_update.c`, `GPS.c`, `pid.c` ！ drivers and algorithms.
- `Global_file/` ！ `global_declare.h/c`, `algorithm.c` ！ shared state and high-level algorithms.
- `FreeRTOS/` ！ kernel sources.

Mini-exercise: open `API/imu_update.c` and identify where the Mahony or complementary filter runs.

---

## 5) Implementing the pieces ！ small guided examples

A. Blink/heartbeat task (learning FreeRTOS basics)
- Create a FreeRTOS task that toggles an LED every 500 ms.
- Purpose: learn xTaskCreate, vTaskDelay, and the scheduler.

B. Read IMU raw data and print via UART
- Use the existing IMU driver (`API/bmi088_driver.c`) to read raw accelerometer/gyro.
- Print a CSV line: `timestamp,ax,ay,az,gx,gy,gz` so you can capture it on your PC.

C. Simple complementary filter on the PC
- Export raw data to CSV, then run `tutorial/visualize_imu.py` to compute and plot roll/pitch estimates using a complementary filter; this helps you understand sensor fusion without changing firmware.

D. Add a simple PID controller in `Global_file/algorithm.c` and tune constants.
- Start with small gains; test in a safe setup (props removed) and observe outputs printed over UART.

Mini-exercise: implement A and B in the project, capture 5 seconds of IMU CSV, and run the visualizer.

---

## 6) Debugging tips (practical)

- If build fails in Keil: first run `keilkilll.bat` to clean, then open `USER/JX_FLY.uvprojx` and fix include paths.
- Use UART logging to stream sensor values. Avoid heavy logging inside interrupts.
- Use the Keil debugger to set breakpoints; inspect stack/heap if crashes occur.

Mini-exercise: add a `printf` in the periodic IMU task and watch output in a terminal.

---

## 7) Visualization & learning more

- Use `tutorial/visualize_imu.py` (created with this tutorial) to plot raw accelerometer/gyro and computed attitude.
- Plotting helps you see noisy sensors, bias, and how filters smooth data.

---

## 8) Next steps and projects to try

- Add a ROS node that reads telem CSV and visualizes 3D attitude.
- Implement a logging mode to store data on an SD card.
- Replace the Mahony filter with an extended Kalman filter for improved performance.

---

## Appendix: Where to find things in this repo

- Build configuration: `USER/JX_FLY.uvprojx` (open in Keil)
- Clean script: `keilkilll.bat`
- IMU update: `API/imu_update.c`
- PID: `API/pid.c`
- PWM outputs: `BSP/pwm.c`


If you'd like, I will split this into separate files (`UAV_TUTORIAL.md` and `UAV_EXERCISES.md`) and add the Python visualizer now (I already added the task list). Do you want me to proceed and create the example files?