import numpy as np
from sim.mujoco_bridge import MujocoBridge, MujocoBridgeConfig

b = MujocoBridge(MujocoBridgeConfig())
b.reset()

T = 1.2961 * 9.80665
print(f"expected total: {T:.6f}")

# Step 1
s = b.step({"roll": 0, "pitch": 0, "yaw": 0, "z": T})
print(f"step 1: motor_lpf={b._motor_lpf}, applied force z={b.data.xfrc_applied[b._airframe_body][2]:.6f}")
print(f"  sum motor_lpf = {sum(b._motor_lpf):.6f}")

# Step 50 (LPF settled)
for _ in range(49):
    b.step({"roll": 0, "pitch": 0, "yaw": 0, "z": T})
print(f"step 50: motor_lpf sum = {sum(b._motor_lpf):.6f}")
print(f"  applied force z = {b.data.xfrc_applied[b._airframe_body][2]:.6f}")
print(f"  vz = {b.data.qvel[2]:.6f}, z = {b.data.qpos[2]:.6f}")

# Now apply identical force by direct method
print("\nReset and apply same force directly:")
b.reset()
for i in range(50):
    b.data.xfrc_applied[b._airframe_body] = [0, 0, sum(b._motor_lpf), 0, 0, 0]
    mujoco.mj_step(b.model, b.data)
print(f"step 50: applied = {sum(b._motor_lpf):.6f}, z={b.data.qpos[2]:.6f}, vz={b.data.qvel[2]:.6f}")