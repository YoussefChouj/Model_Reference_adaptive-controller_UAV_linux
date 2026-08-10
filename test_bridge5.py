import numpy as np
from sim.mujoco_bridge import MujocoBridge, MujocoBridgeConfig

b = MujocoBridge(MujocoBridgeConfig())
b.reset()

T = 1.2961 * 9.80665
# Run 200 hover steps and log
for i in range(200):
    s = b.step({"roll": 0, "pitch": 0, "yaw": 0, "z": T})
    if i < 5 or i % 50 == 0:
        print(f"step {i}: z={s['z']:.4f}, vz={s['vz']:.4f}, thrust={s['thrust']:.4f}, motors={b._motor_lpf[0]:.4f}")
print(f"final z={b.data.qpos[2]:.6f}")
print(f"final vz={b.data.qvel[2]:.6f}")
print(f"final motors={b._motor_lpf}")
print(f"final xfrc_applied={b.data.xfrc_applied[b._airframe_body]}")