# GETTING STARTED: Build, Run, and Explore This STM32 + FreeRTOS Project

This guide walks you through the essential steps to build, flash, and begin exploring the project as a beginner. It complements `.github/copilot-instructions.md` with practical, click-by-click instructions.

## 1. Prerequisites
- Install Keil MDK (uVision) and ensure the STM32F4 Pack is present (see `USER/JX_FLY.uvprojx` for PackID).
- (Optional) Install SEGGER J-Link or ST-Link tools if you have compatible hardware.

## 2. Clean the Workspace
Open PowerShell in the project root and run:
```powershell
.\keilkilll.bat
```
This removes old build artifacts and ensures a fresh build.

## 3. Open the Project in Keil
- Launch Keil uVision.
- Go to `File > Open Project...` and select `USER/JX_FLY.uvprojx`.
- Wait for the IDE to load all groups and files.

## 4. Build the Project
- Click the 'Build' (hammer) icon or press `F7`.
- Watch the output window for errors. Successful builds create output files in `OBJ/`.

## 5. Flash to Hardware (if available)
- Connect your STM32 board via J-Link or ST-Link.
- Click the 'Download' (arrow) icon or press `Ctrl+F8`.
- Wait for flashing to complete.

## 6. Debug/Run
- Set breakpoints in files like `USER/main.c` (e.g., on `main()` or task creation lines).
- Click 'Start/Stop Debug Session' (bug icon) or press `Ctrl+F5`.
- Step through code, inspect variables, and watch task execution.

## 7. Explore Key Files
- `USER/main.c` — entry point, RTOS task creation (see lines 3–40 for main and start_task).
- `API/imu_update.c` — IMU update logic (see lines 20–80 for Mahony filter and sensor fusion).
- `Global_file/algorithm.c` — algorithms and filters (see lines 10–30 for low-pass filter example).
- `BSP/pwm.c` — motor PWM output.
- `FreeRTOS/portable/RVDS/ARM_CM4F/` — RTOS port for STM32F4.

## 8. Make a Simple Edit
- Try adding a debug UART log in `USER/main.c` (e.g., after `BSP_Init();`).
- Rebuild and re-flash to see your change.

## 9. Where to Learn More
- See `.github/copilot-instructions.md` for a full beginner learning path, concepts, and recommended resources.
- For Keil IDE help, use `Help > Contents` or visit [Keil's documentation](https://www.keil.com/support/man/docs/uv4/uv4.htm).

---
If you get stuck, check the output window for error messages, and consult the project instructions for troubleshooting tips.
