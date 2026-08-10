"""Verify warm-start fix."""
from sim.plant import MujocoPlant, RigidBodyPlant, CANONICAL_AIRFRAME

T_hover = CANONICAL_AIRFRAME.mass * 9.80665

mj = MujocoPlant(dt=0.005)
mj.reset()
print("AFTER reset:", "z=", mj._bridge.data.qpos[2], "vz=", mj._bridge.data.qvel[2], "motor_lpf=", mj._bridge._motor_lpf)
for i in range(2000):
    s = mj.step({"roll": 0.0, "pitch": 0.0, "yaw": 0.0, "z": T_hover})
print(f"MujocoPlant 10s hover: z={s['z']:.4f}, p={s['p']:.4f}, q={s['q']:.4f}, r={s['r']:.4f}")