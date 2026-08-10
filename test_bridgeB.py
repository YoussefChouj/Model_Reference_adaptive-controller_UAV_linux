import mujoco
import numpy as np
from sim.mujoco_bridge import MujocoBridgeConfig

m = mujoco.MjModel.from_xml_path(r"sim\models\jx_fly\jx_fly_mujoco.xml")
d = mujoco.MjData(m)
af = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, "airframe")
T = 1.2961 * 9.80665
cfg = MujocoBridgeConfig()

motor_lpf = np.zeros(4)
alpha = cfg.dt / (cfg.motor_tau + cfg.dt)

for i in range(200):
    thrust_target = np.full(4, T / 4.0)
    motor_lpf = (1 - alpha) * motor_lpf + alpha * thrust_target
    R = d.xmat[af].reshape(3, 3).copy()
    F_world_total = np.zeros(3)
    for mi in range(4):
        F_w = R @ np.array([0.0, 0.0, motor_lpf[mi]])
        F_world_total += F_w
    d.xfrc_applied[af] = np.concatenate([F_world_total, np.zeros(3)])
    mujoco.mj_step(m, d)
    if i in (1, 49, 99, 199):
        print(f"step {i}: motor_lpf={motor_lpf}, sum={sum(motor_lpf):.6f}, z={d.qpos[2]:.4f}, vz={d.qvel[2]:.4f}")
print(f"final: z={d.qpos[2]:.6f}, vz={d.qvel[2]:.6f}")