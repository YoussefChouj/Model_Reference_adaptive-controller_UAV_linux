import numpy as np
from sim.mujoco_bridge import MujocoBridge, MujocoBridgeConfig
b = MujocoBridge(MujocoBridgeConfig())
b.reset()
T = 1.2961 * 9.80665
for i in range(2000):
    s = b.step({"roll": 0, "pitch": 0, "yaw": 0, "z": T})
    if i in (99, 499, 999, 1499, 1999):
        print(f"step {i}: z={b.data.qpos[2]:.4f}, vz={b.data.qvel[2]:.6f}, sum_lpf={sum(b._motor_lpf):.6f}")