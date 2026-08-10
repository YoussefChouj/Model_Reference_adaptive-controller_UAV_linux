import numpy as np
from sim.mujoco_bridge import MujocoBridge, MujocoBridgeConfig

b = MujocoBridge(MujocoBridgeConfig())
b.reset()

T = 1.2961 * 9.80665
# Run hover steps
for i in range(200):
    s = b.step({"roll": 0, "pitch": 0, "yaw": 0, "z": T})

# Check the residual: applied force vs mass*g
applied = b.data.xfrc_applied[b._airframe_body]
print(f"applied force: {applied}")
print(f"mass: {b.model.body_mass[b._airframe_body]}")
print(f"gravity: {b.model.opt.gravity}")
print(f"m*g_z: {b.model.body_mass[b._airframe_body] * b.model.opt.gravity[2]}")
print(f"net acceleration (force/m + g): {applied[2]/b.model.body_mass[b._airframe_body] + b.model.opt.gravity[2]}")
print(f"vz: {b.data.qvel[2]}")

# Check forces on the body
print(f"qfrc_constraint: {b.data.qfrc_constraint}")
print(f"qfrc_applied: {b.data.qfrc_applied}")
print(f"qfrc_bias: {b.data.qfrc_bias}")

# Also test: bypass LPF, apply direct force
b.reset()
applied_force = T  # 12.71 N
for _ in range(200):
    b.data.xfrc_applied[b._airframe_body] = [0, 0, applied_force, 0, 0, 0]
    mujoco.mj_step(b.model, b.data)
print(f"\nDirect force (bypass LPF): z={b.data.qpos[2]:.6f}, vz={b.data.qvel[2]:.6f}")