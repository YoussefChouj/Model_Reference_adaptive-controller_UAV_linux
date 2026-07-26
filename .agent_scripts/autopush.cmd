@echo off
REM Wrapper so Windows Task Scheduler needs only one quoted path.
REM Removes the task:  schtasks /Delete /TN "UAV-autopush" /F
cd /d "%~dp0.."
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" ".agent_scripts\autopush.py" %*
) else (
    python ".agent_scripts\autopush.py" %*
)
