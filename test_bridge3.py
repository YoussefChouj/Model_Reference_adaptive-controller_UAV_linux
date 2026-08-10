import mujoco, numpy as np
xml = """<mujoco><option gravity="0 0 0" integrator="Euler" timestep="0.005"/><worldbody><body name="airframe" pos="0 0 0"><freejoint name="root"/><inertial pos="0 0 0" mass="1.0" diaginertia="0.1 0.1 0.1"/></body></worldbody></mujoco>"""
m = mujoco.MjModel.from_xml_string(xml)
d = mujoco.MjData(m)
af = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, "airframe")
d.xfrc_applied[af] = [0, 0, 9.81, 0, 0, 0]
for _ in range(100):
    mujoco.mj_step(m, d)
print(f"F=+9.81N, no gravity, 100 steps: z={d.qpos[2]:.4f}, vz={d.qvel[2]:.4f}")
print(f"expected v=4.905, z=1.226; got v={d.qvel[2]:.3f}, z={d.qpos[2]:.3f}")

# Now with gravity (default)
xml2 = """<mujoco><option gravity="0 0 -9.81" integrator="Euler" timestep="0.005"/><worldbody><body name="airframe" pos="0 0 0"><freejoint name="root"/><inertial pos="0 0 0" mass="1.0" diaginertia="0.1 0.1 0.1"/></body></worldbody></mujoco>"""
m2 = mujoco.MjModel.from_xml_string(xml2)
d2 = mujoco.MjData(m2)
af2 = mujoco.mj_name2id(m2, mujoco.mjtObj.mjOBJ_BODY, "airframe")
d2.xfrc_applied[af2] = [0, 0, 9.81, 0, 0, 0]
for _ in range(100):
    mujoco.mj_step(m2, d2)
print(f"F=+9.81N, with gravity: z={d2.qpos[2]:.4f}, vz={d2.qvel[2]:.4f}")
print(f"expected: stationary at z=0")