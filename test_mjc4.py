import mujoco
import numpy as np

# Use xfrc_applied approach: airframe is the only free body.
# Apply thrust forces at motor positions in body frame.
xml = """<mujoco>
  <option gravity="0 0 -9.81" integrator="Euler" timestep="0.005"/>
  <worldbody>
    <body name="airframe" pos="0 0 0">
      <freejoint name="root"/>
      <inertial pos="0 0 0" mass="1.0" diaginertia="0.01 0.01 0.01"/>
      <geom type="box" size="0.21 0.21 0.05" pos="0 0 0.026" rgba="0.15 0.15 0.2 1"/>
    </body>
  </worldbody>
</mujoco>"""
m = mujoco.MjModel.from_xml_string(xml)
d = mujoco.MjData(m)
print(f"airframe only: nq={m.nq}, nv={m.nv}, nu={m.nu}")
print(f"body_mass={m.body_mass[1]}, body_inertia={m.body_inertia[1]}")
print(f"nbody={m.nbody}, ngeom={m.ngeom}")

# Apply force at body frame point (0.2, 0.2, 0) in body +z direction
# xfrc_applied[0]: x force in world frame
# xfrc_applied[1]: y force in world frame
# xfrc_applied[2]: z force in world frame (up = positive)
# xfrc_applied[3..5]: torque in world frame
# To apply body-frame torque and body-frame force at point, we need
# to compute world-frame equivalents using mju_transmissionForce or
# manually using the rotation matrix.

# Simpler: use d.xfrc_applied directly.
# When we apply a force at point (px, py, pz) in body frame, and want the
# body-frame force Fb in body-frame direction, we compute:
#   F_world = R @ Fb
#   tau_world = R @ (p_body x Fb)   (cross product)
# Then set d.xfrc_applied[body_id] = [Fx_w, Fy_w, Fz_w, tx_w, ty_w, tz_w]

# For level hover: F_world = (0, 0, +m*g), tau_world = 0
# So d.xfrc_applied[1] = [0, 0, +1*9.81, 0, 0, 0]
d.xfrc_applied[1] = [0, 0, 9.81, 0, 0, 0]
for _ in range(50):
    mujoco.mj_step(m, d)
print(f"after 50 hover steps: qpos={d.qpos[:3]} (expect ~0 if hover)")

# Reset and try free fall
mujoco.mj_resetData(m, d)
for _ in range(50):
    mujoco.mj_step(m, d)
print(f"after 50 free-fall steps: qpos_z={d.qpos[2]} (expect negative, falling)")

# Try tilted force (roll torque)
mujoco.mj_resetData(m, d)
# 1 N offset motor force at (0.2, 0.2, 0) in body-frame +z direction
# Need body-to-world rotation R. At qpos[3..7] = identity quat (1,0,0,0),
# R is identity. Force in body frame = (0, 0, 1).
# World frame force = (0, 0, 1).
# Torque in body frame = (0.2, 0.2, 0) x (0, 0, 1) = (0.2, -0.2, 0).
# World frame torque = (0.2, -0.2, 0) (identity rotation).
d.xfrc_applied[1] = [0, 0, 9.81, 0.2, -0.2, 0]
for _ in range(100):
    mujoco.mj_step(m, d)
# Read the quaternion and convert to euler
w, x, y, z = d.qpos[3], d.qpos[4], d.qpos[5], d.qpos[6]
# ZYX Euler
phi = np.arctan2(2*(w*x + y*z), 1 - 2*(x*x + y*y))
theta = np.arcsin(max(-1, min(1, 2*(w*y - x*z))))
psi = np.arctan2(2*(w*z + x*y), 1 - 2*(y*y + z*z))
print(f"after 100 steps with roll torque: phi={phi:.3f}, theta={theta:.3f}, psi={psi:.3f}")
print(f"  qpos_z={d.qpos[2]:.3f}, qvel ang x={d.qvel[3]:.4f}")
