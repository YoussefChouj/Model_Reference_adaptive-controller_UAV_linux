# UAV Tutorial ！ Exercises and Hints

This file contains hands-on exercises referenced by `UAV_TUTORIAL.md` and suggested check-ins for beginners.

Exercise 1 ！ Build tools check
- Goal: verify Keil and Python are available.
- Steps:
  1. Open PowerShell and run `python --version`.
  2. If you have Keil, open `USER/JX_FLY.uvprojx`.

Exercise 2 ！ Heartbeat task (FreeRTOS)
- Create a new file or modify the user task to include a task that toggles a GPIO/LED every 500 ms:
  - Use `xTaskCreate()` to create `vHeartbeatTask`.
  - In the task: `for(;;) { ToggleLED(); vTaskDelay(pdMS_TO_TICKS(500)); }`
- Hint: ensure correct GPIO initialization in `BSP/BSP.c`.

Exercise 3 ！ IMU CSV logger
- Modify the IMU read path to print CSV lines via UART: `timestamp,ax,ay,az,gx,gy,gz`.
- Capture the output with PuTTY and save to a file.

Exercise 4 ！ Visualize IMU data locally
- Use `tutorial/visualize_imu.py` to plot the CSV. It computes simple roll/pitch using accelerometer and gyroscope integration and a complementary filter.

Exercise 5 ！ Simple PID control test
- Implement a small PID in `Global_file/algorithm.c`.
- Print the PID output and tune gains to see the step response.

Hints & answers
- If your UART output is garbled, check baud rate and encoding: set PuTTY to the same baud (e.g., 115200) and CR/LF.
- If IMU values are zero or constant, check SPI wiring and chip select.

Notes
- Keep propellers removed during initial testing.
- Use the visualizer to get intuition before changing firmware.

---

If you want, I can create code snippets for these exercises and add them to the repo as example files.