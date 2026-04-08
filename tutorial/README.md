Tutorial Visualizer README

This folder contains a simple Python visualizer to plot IMU CSV output from the firmware.

Files:
- `visualize_imu.py` ¡ª reads CSV and shows accel/gyro and attitude estimates.
- `requirements.txt` ¡ª Python dependencies.

How to run (Windows PowerShell):

1. Create a virtual environment (optional but recommended):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install dependencies:

```powershell
python -m pip install -r tutorial\requirements.txt
```

3. Run the visualizer on your captured CSV (saved from PuTTY or your terminal):

```powershell
python tutorial\visualize_imu.py C:\path\to\imu.csv
```

CSV format expected: timestamp,ax,ay,az,gx,gy,gz (comma-separated). Timestamp should be in seconds.

Hints:
- If your firmware prints values in raw units, adapt the column indices or convert units in the script.
- If the plot appears noisy, try a longer capture or apply a moving-average filter in the script.
