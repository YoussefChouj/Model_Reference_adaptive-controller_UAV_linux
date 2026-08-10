import mujoco, numpy as np
m = mujoco.MjModel.from_xml_path(r"sim\models\jx_fly\jx_fly_mujoco.xml")
d = mujoco.MjData(m)
af = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, "airframe")
print(f"mass: {m.body_mass[af]}")
print(f"gravity: {m.opt.gravity}")

T = 1.2961 * 9.80665
print(f"applied total thrust target: {T:.6f}")
print(f"mass*|g|: {1.2961 * 9.80665:.6f}")

# Apply exact hover force each step
vz_log = []
z_log = []
for i in range(200):
    d.xfrc_applied[af] = [0, 0, T, 0, 0, 0]
    mujoco.mj_step(m, d)
    vz_log.append(d.qvel[2])
    z_log.append(d.qpos[2])
    if i < 10 or i % 50 == 0:
        print(f"step {i}: z={d.qpos[2]:.6f}, vz={d.qvel[2]:.6f}")
print(f"final z={d.qpos[2]:.6f}")
print(f"max |vz|: {max(abs(v) for v in vz_log):.6f}")
print(f"sum |vz|: {sum(abs(v) for v in vz_log):.6f}")
print(f"final z drift: {d.qpos[2]:.6f}")