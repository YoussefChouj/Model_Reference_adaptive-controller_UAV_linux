import numpy as np
from sim.mujoco_bridge import MujocoBridge, MujocoBridgeConfig

b = MujocoBridge(MujocoBridgeConfig())
b.reset()
T = 1.2961 * 9.80665
for i in range(200):
    s = b.step({"roll": 0, "pitch": 0, "yaw": 0, "z": T})
print(f"after 200 hover ticks: z={s['z']:.4f}, qpos={b.data.qpos[:3]}")
print(f"p={s['p']:.5f}, q={s['q']:.5f}, r={s['r']:.5f}")

# Free-fall
b.reset()
for i in range(50):
    s = b.step({"roll": 0, "pitch": 0, "yaw": 0, "z": 0})
print(f"after 50 free-fall ticks: z={s['z']:.4f}, vz={s['vz']:.4f}")

# Roll step
b.reset()
for i in range(100):
    s = b.step({"roll": 1.0, "pitch": 0.0, "yaw": 0.0, "z": T})
print(f"after 100 roll-step ticks: p={s['p']:.5f}, phi={s['phi']:.5f}")