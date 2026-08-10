import numpy as np
from sim.mujoco_bridge import MujocoBridge, MujocoBridgeConfig
b = MujocoBridge(MujocoBridgeConfig())
b.reset()

T = 1.2961 * 9.80665
# Simple P controller to hold position around z=0
Kp = 3.0
for i in range(2000):
    s = b.step({"roll": 0, "pitch": 0, "yaw": 0, "z": T + Kp * (0 - s["z"]) - 0.5 * s["vz"]})
    if i in (99, 499, 999, 1999):
        print(f"step {i}: z={s['z']:.4f}, vz={s['vz']:.4f}, commanded={T + Kp * (0 - s['z']) - 0.5 * s['vz']:.4f}")