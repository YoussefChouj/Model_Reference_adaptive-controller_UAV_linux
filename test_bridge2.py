import numpy as np
import mujoco
from sim.mujoco_bridge import MujocoBridge, MujocoBridgeConfig, _HAS_MUJOCO

b = MujocoBridge(MujocoBridgeConfig())
b.reset()

T = 1.2961 * 9.80665
print(f"hover thrust total: {T:.4f} N")
print(f"per-motor target: {T/4:.4f} N")

# Apply one step and inspect everything
s = b.step({"roll": 0, "pitch": 0, "yaw": 0, "z": T})
print(f"after 1 step:")
print(f"  motor_lpf (N): {b._motor_lpf}")
print(f"  xfrc_applied[airframe]: {b.data.xfrc_applied[b._airframe_body]}")
print(f"  qpos: {b.data.qpos[:3]}")
print(f"  qvel: {b.data.qvel[:6]}")
print(f"  ctrl: {b.data.ctrl}")
print(f"  qfrc_applied: {b.data.qfrc_applied}")
print(f"  xfrc_applied sum: {b.data.xfrc_applied.sum()}")
print(f"  nu: {b.model.nu}, nbody: {b.model.nbody}")

# After 200 steps, what's the motor_lpf?
for _ in range(199):
    b.step({"roll": 0, "pitch": 0, "yaw": 0, "z": T})
print(f"after 200 steps:")
print(f"  motor_lpf: {b._motor_lpf}")
print(f"  xfrc_applied[airframe]: {b.data.xfrc_applied[b._airframe_body]}")
print(f"  qpos: {b.data.qpos[:3]}")
print(f"  z drift: {b.data.qpos[2]:.4f}")