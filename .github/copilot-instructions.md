Purpose
-------
This file gives focused, actionable guidance for AI coding assistants working in this STM32 + FreeRTOS Keil project so they can be productive immediately.

Model Selection Guide
---------------------
Note: These model tiers apply to direct-fix tasks (<=1 function, <=1 file) and to the planner/reviewer role. For multi-file tasks, use the /multiagent-workflow skill which delegates coding to free OpenRouter models.

Quick start / build
-------------------
- Primary project file: `USER/JX_FLY.uvprojx` (Keil uVision). Open in Keil MDK-ARM and build.
- Clean workspace: run the repository root `keilkilll.bat` to remove build artifacts (deletes `*.axf`, `*.o`, `*.map`, `OBJ/`, etc.).
- Output artifacts are written to `OBJ/` (see `USER/JX_FLY.uvprojx` -> OutputDirectory).
- Toolchain: Keil/ARMCC (uvprojx shows PackID `Keil.STM32F4xx_DFP` and ARM CC toolset).

Big-picture architecture
------------------------
- Entry point / app logic: `USER/main.c` (project 'USER' group).
- Board support layer: `BSP/` (pwm, spi, usart, etc.) — low-level HAL wrappers for this board.
- Peripheral & sensor drivers: `API/` (IMU, GPS, tf-mini lidar, bmi088 driver, filters, etc.).
- Application-level algorithms & globals: `Global_file/` (`algorithm.c`, `global_declare.c`, `globaluse_basic_function.c`).
- RTOS: `FreeRTOS/` contains kernel sources and `FreeRTOS/portable/` RVDS/ARM_CM4F port used by this project.
- Startup / vendor libs: `stm32_lib/` (startup assembly, peripheral library drivers).
- Tasks folder(s): `TASK/` and `USER/` contain task code and application modules.

Key files to inspect
--------------------
- `USER/JX_FLY.uvprojx` — build configuration, include paths, preprocessor defines, and output settings.
- `keilkilll.bat` — quick clean script (repo root).
- `stm32_lib/startup_stm32f40_41xxx.s` — reset vector/startup code.
- `FreeRTOS/portable/RVDS/ARM_CM4F` — port layer for the MCU/RTOS integration.
- `Global_file/global_declare.h` / `global_declare.c` — where globals are defined and referenced; many modules depend on these.

Project-specific conventions & patterns
-------------------------------------
- File roles: `BSP/` = board-specific drivers; `API/` = higher-level sensor/algorithm modules; `Global_file/` = cross-cutting globals & helpers.
- Naming: C sources live next to corresponding `.h` files (e.g., `API/imu_update.c` + `.h`).
- Globals: shared state is commonly placed in `global_declare.*` and accessed across files — avoid introducing duplicate globals; add new externs here.
- FreeRTOS tasks: RTOS hooks and tasks follow the standard `FreeRTOS/` API; look for task creation in `USER/` or `TASK/` sources.
- Includes & defines: project relies on defines like `STM32F40_41xxx` and `USE_STDPERIPH_DRIVER` (set in `uvprojx`).

Integration points & external dependencies
-----------------------------------------
- Keil MDK (uVision) and ARMCC toolchain — project files are Keil-specific. The `uvprojx` references Keil Packs (`Keil.STM32F4xx_DFP`).
- Flash/Debug driver referenced in `uvprojx` (UL2CM3 flash driver). Typical flashing/debugging flows use Keil's debugger or external J-Link tools.
- FreeRTOS is vendored in-tree; do not swap versions without updating port layer (`FreeRTOS/portable/`).

How to add code safely
----------------------
1. Add new source files into the appropriate logical folder (`API/`, `BSP/`, `USER/`, or `TASK/`).
2. Add the file entry to `USER/JX_FLY.uvprojx` under the correct Group so Keil builds it (or update project in uVision GUI).
3. Update headers and `global_declare.h` only when necessary; prefer passing state via function arguments if possible.
4. Keep MCU-specific code in `BSP/` and algorithmic code in `Global_file/` or `API/`.

Common pitfalls
---------------
- Many include paths in `.vscode/c_cpp_properties.json` are user-local absolute paths — do not rely on them for CI. Prefer relative include paths found in `uvprojx` (`IncludePath` element).
- Changing `FreeRTOS/portable` without testing on Keil can break the build; test on hardware or with Keil simulator.
- Be careful modifying `stm32_lib/` startup or linker-related settings — they affect memory layout and flashing.

If you need more
---------------
- To change build automation: ask to add a simple wrapper script that calls Keil command-line tools (uvision/UV4/UV5 CLI) or to produce an export-friendly Makefile.
- If something references a non-present Keil pack or path, point to `USER/JX_FLY.uvprojx` and `USER/.vscode/c_cpp_properties.json` for hints of required packs/toolchain locations.

Examples (where to look for tasks & drivers)
- IMU updates: `API/imu_update.c`
- Motor PWM: `BSP/pwm.c`
- Control algorithm: `Global_file/algorithm.c`
- Main application entry: `USER/main.c`

Update / merge notes
--------------------
- No existing `.github/copilot-instructions.md` or AGENT docs detected; this file was generated from direct inspection of `USER/JX_FLY.uvprojx`, `keilkilll.bat`, `FreeRTOS/`, `BSP/`, `API/`, and `Global_file/`.
- If you have team conventions (naming, commit message format, CI hooks), provide them and I will merge them into this file.

Questions for maintainers
------------------------
- Preferred developer workflow for local builds (Keil GUI vs CLI)?
- Preferred flashing/debug connector (J-Link vs ST-Link)?
- Any non-discoverable scripts or CI steps to include?

Beginner step-by-step tutorial (how to learn this project)
---------------------------------------------------------

This path is ordered so a beginner can build mental layers from basic tools and concepts up to the control algorithms. Each step references specific code lines and files to help you connect concepts to real code.

1) Prerequisites & tools (30–120 min)
	- Install Keil MDK (uVision) with the STM32F4 Pack referenced in `USER/JX_FLY.uvprojx` (PackID: `Keil.STM32F4xx_DFP`).
	- Optional: install SEGGER/J-Link tools if you have a J-Link debugger.
	- Quick check: from the repo root run the clean script in PowerShell to ensure tools are in place:
	  - See `keilkilll.bat` (lines 1–30): batch file for cleaning build artifacts.
	- Concepts to learn: basic C syntax, how compilers and linkers work, what a uVision (uvprojx) project contains. Resources: "C Programming" (K&R short intro) and Keil MDK docs.

2) High-level read (30–60 min)
	- Open `USER/JX_FLY.uvprojx` in Keil and skim project groups.
	- Open `USER/main.c` (lines 1–40): see `main()` and `start_task()` for entry and RTOS task creation.
	- Concepts to learn: program entry on embedded devices, startup code vs main, linker memory sections. Resource: "Embedded C" tutorials; ARM Cortex-M startup guides.

3) RTOS fundamentals (1–3 hours)
	- Read `FreeRTOS/portable/RVDS/ARM_CM4F/port.c` (lines 1–80): see context switching and porting details.
	- In `USER/main.c` (lines 10–40): see `xTaskCreate` and `vTaskStartScheduler` usage.
	- Concepts to learn: tasks, queues, ISRs, context switching. Resources: FreeRTOS official book and interactive examples.

4) Global state & configuration (30–60 min)
	- Inspect `Global_file/global_declare.h` and `global_declare.c` (lines 1–40): see global variable declarations and initializations.
	- Concepts: extern/global patterns in C, header guards, configuration constants.

5) Board/driver layer (1–2 hours)
	- Read `BSP/BSP.c` (lines 1–40): board initialization routines.
	- Read `BSP/pwm.c` (lines 1–40): motor PWM output setup.
	- Concepts: HAL vs BSP layers, peripheral initialization, GPIO, timers, PWM, UART, SPI. Resource: STM32F4 reference manual & ST Standard Peripheral Library examples.

6) Sensors and algorithms (2–4 hours)
	- Review `API/imu_update.c` (lines 20–80): Mahony filter and sensor fusion logic.
	- Read `Global_file/algorithm.c` (lines 10–30): low-pass filter implementation.
	- Concepts: IMU basics (accelerometer/gyro), sensor fusion, filters (complementary, Kalman basics), and control basics (PID). Resources: sensor fusion primers and the PID tutorial by ControlTutorials.com.

7) Follow a runtime trace (hands-on) (1–3 hours)
	- Build the project in Keil; flash/run on hardware or use the Keil simulator.
	- Set breakpoints in `USER/main.c` (lines 3–40), `API/imu_update.c` (lines 20–80), and `BSP/pwm.c` (lines 10–40). Step through a single loop to see data flow.
	- Concepts: debugging embedded code, reading memory/registers, using semihosting/RTT or UART logs.

8) Small edits & tests (1–4 hours)
	- Make a trivial change: add a debug UART printf in `USER/main.c` (after `BSP_Init();` in lines 5–10) or increment a counter in a periodic task.
	- Rebuild and flash to see your change.
	- Concepts: safe incremental edits, build-flash-debug cycle, observing side effects on hardware.

9) Control tuning & experiments (days)
	- Investigate PID constants in `API/pid.c` (lines 1–40) or `Global_file/algorithm.c` (lines 10–30) and test small parameter changes in controlled conditions.
	- Concepts: control stability, testing methodology, data logging for analysis.

10) Advanced topics (ongoing)
	- Read `stm32_lib/startup_stm32f40_41xxx.s` (lines 1–40): vector table and reset flow.
	- Explore FreeRTOS port files for interrupt/stack management (`FreeRTOS/portable/RVDS/ARM_CM4F/port.c`, lines 80–160).
	- Concepts: interrupt priorities on Cortex-M, hard faults analysis, linker scatter files / memory layout.

Learning resources (concise)
- C & Embedded C: "The C Programming Language" (K&R intro) + "Embedded C" primers.
- ARM Cortex-M: ARM Cortex-M4 generic user guide, STM32F4 reference manual.
- FreeRTOS: FreeRTOS documentation and "Using FreeRTOS" book.
- Keil: Keil MDK user guides and uVision project docs.
- Sensors & Control: "An Introduction to the Kalman Filter" (Welch & Bishop), ControlTutorials PID guide.

Mini-exercises (recommended)
- Exercise A: Build and run the default project (confirm `OBJ/` populated). Use `keilkilll.bat` then rebuild.
- Exercise B: Add a UART log in `USER/main.c` (lines 5–10) and confirm messages on serial console.
- Exercise C: Locate and instrument the IMU update pipeline (`API/imu_update.c`, lines 20–80) to print raw sensor values.

How I verified these steps
- I inspected `USER/JX_FLY.uvprojx`, `keilkilll.bat`, `USER/.vscode/c_cpp_properties.json` and key folders (`API/`, `BSP/`, `Global_file/`, `FreeRTOS/`, `stm32_lib/`). The steps above reference files visible in the repo.

If you want I can also:
- Add short example snippets (non-intrusive) for safe printf-style logging via UART in `USER/main.c`.
- Create a small checklist file `GETTING_STARTED.md` with the exact sequence of clicks/Keil menu items to build & flash.

