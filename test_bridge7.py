import mujoco, numpy as np
m = mujoco.MjModel.from_xml_path(r"sim\models\jx_fly\jx_fly_mujoco.xml")
d = mujoco.MjData(m)
af = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, "airframe")
T = 1.2961 * 9.80665

print("Test 1: xfrc_applied only")
for _ in range(200):
    d.xfrc_applied[af] = [0, 0, T, 0, 0, 0]
    mujoco.mj_step(m, d)
print(f"  final z={d.qpos[2]:.6f}, vz={d.qvel[2]:.6f}")

mujoco.mj_resetData(m, d)
print("\nTest 2: xfrc_applied continuously + observe mid-step velocity")
for i in range(200):
    d.xfrc_applied[af] = [0, 0, T, 0, 0, 0]
    mujoco.mj_step(m, d)
    if i in (49, 99, 149):
        print(f"  step {i}: z={d.qpos[2]:.6f}, vz={d.qvel[2]:.6f}, xfrc_applied={d.xfrc_applied[af]}")
print(f"  final z={d.qpos[2]:.6f}, vz={d.qvel[2]:.6f}")