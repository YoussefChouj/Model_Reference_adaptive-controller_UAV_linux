import mujoco, numpy as np
m = mujoco.MjModel.from_xml_path(r"sim\models\jx_fly\jx_fly_mujoco.xml")
d = mujoco.MjData(m)
af = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, "airframe")
T = 1.2961 * 9.80665

print("Test A: set once, step many times")
d.xfrc_applied[af] = [0, 0, T, 0, 0, 0]
for i in range(200):
    mujoco.mj_step(m, d)
    if i in (1, 99, 199):
        print(f"  step {i}: xfrc_applied={d.xfrc_applied[af]}, z={d.qpos[2]:.4f}, vz={d.qvel[2]:.4f}")

mujoco.mj_resetData(m, d)
print("\nTest B: set every step")
for i in range(200):
    d.xfrc_applied[af] = [0, 0, T, 0, 0, 0]
    mujoco.mj_step(m, d)
    if i in (1, 99, 199):
        print(f"  step {i}: xfrc_applied={d.xfrc_applied[af]}, z={d.qpos[2]:.4f}, vz={d.qvel[2]:.4f}")