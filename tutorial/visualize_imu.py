"""
Simple IMU CSV visualizer.

Input CSV expected columns (header optional): timestamp,ax,ay,az,gx,gy,gz
- ax,ay,az in m/s^2 (or raw units)
- gx,gy,gz in deg/s (or rad/s) ¡ª code will assume deg/s unless you change it

This script plots raw accel/gyro and computes roll/pitch via a complementary filter.

Run (PowerShell):
    python tutorial\visualize_imu.py path\to\imu.csv

"""
import sys
import numpy as np
import matplotlib.pyplot as plt

if len(sys.argv) < 2:
    print("Usage: python tutorial/visualize_imu.py path/to/imu.csv")
    sys.exit(1)

path = sys.argv[1]
# Try to load CSV with or without header
try:
    data = np.loadtxt(path, delimiter=',')
except Exception as e:
    print('Failed to load CSV:', e)
    sys.exit(1)

if data.shape[1] < 7:
    print('CSV must have at least 7 columns: t,ax,ay,az,gx,gy,gz')
    sys.exit(1)

t = data[:,0]
ax = data[:,1]
ay = data[:,2]
az = data[:,3]
 gx = data[:,4]
gy = data[:,5]
gz = data[:,6]

# Convert gyro to deg/s if needed (assumed already deg/s)
# Integrate gyro to get angle estimation

# Compute roll/pitch from accelerometer (small-angle approx)
roll_acc = np.degrees(np.arctan2(ay, az))
pitch_acc = np.degrees(np.arctan2(-ax, np.sqrt(ay**2 + az**2)))

# Complementary filter
alpha = 0.98
roll = np.zeros_like(roll_acc)
pitch = np.zeros_like(pitch_acc)
roll[0] = roll_acc[0]
pitch[0] = pitch_acc[0]

for i in range(1, len(t)):
    dt = t[i] - t[i-1]
    if dt <= 0:
        dt = 0.01
    # gyro rates
    gx_rate = gx[i]
    gy_rate = gy[i]
    # integrate (assuming gx is roll rate in deg/s)
    roll_gyro = roll[i-1] + gx_rate * dt
    pitch_gyro = pitch[i-1] + gy_rate * dt
    # combine
    roll[i] = alpha * roll_gyro + (1-alpha) * roll_acc[i]
    pitch[i] = alpha * pitch_gyro + (1-alpha) * pitch_acc[i]

# Plot
plt.figure(figsize=(12,8))
plt.subplot(3,1,1)
plt.plot(t, ax, label='ax')
plt.plot(t, ay, label='ay')
plt.plot(t, az, label='az')
plt.legend(); plt.title('Accelerometer')

plt.subplot(3,1,2)
plt.plot(t, gx, label='gx')
plt.plot(t, gy, label='gy')
plt.plot(t, gz, label='gz')
plt.legend(); plt.title('Gyroscope')

plt.subplot(3,1,3)
plt.plot(t, roll_acc, label='roll_acc')
plt.plot(t, pitch_acc, label='pitch_acc')
plt.plot(t, roll, label='roll_cf')
plt.plot(t, pitch, label='pitch_cf')
plt.legend(); plt.title('Attitude (acc vs complementary filter)')

plt.tight_layout()
plt.show()