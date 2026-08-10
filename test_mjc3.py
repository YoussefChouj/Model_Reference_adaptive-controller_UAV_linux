import mujoco
# general actuator without type attribute
xml = """<mujoco>
  <worldbody>
    <body name="b" pos="0 0 0">
      <freejoint name="f"/>
      <inertial pos="0 0 0" mass="1" diaginertia="0.1 0.1 0.1"/>
    </body>
  </worldbody>
  <actuator>
    <general name="a" joint="f" ctrllimited="true" ctrlrange="-1 5"/>
  </actuator>
</mujoco>"""
m = mujoco.MjModel.from_xml_string(xml)
print(f"ok: nq={m.nq}, nv={m.nv}, nu={m.nu}, act_type={m.actuator_actnum}")
d = mujoco.MjData(m)
d.ctrl[0] = 2.0
mujoco.mj_step(m, d)
print(f"after step: qpos={d.qpos[:3]}, qvel={d.qvel[:6]}")
print(f"actuator_ctrlrange={m.actuator_ctrlrange}")

# Now test with separate motor bodies (each freejoint)
xml2 = """<mujoco>
  <worldbody>
    <body name="airframe" pos="0 0 0">
      <freejoint name="root"/>
      <inertial pos="0 0 0" mass="1" diaginertia="0.1 0.1 0.1"/>
      <body name="motor1" pos="0.2 0.2 0">
        <freejoint name="motor1_joint"/>
        <inertial pos="0 0 0" mass="1e-6" diaginertia="1e-9 1e-9 1e-9"/>
      </body>
    </body>
  </worldbody>
  <actuator>
    <general name="motor1" joint="motor1_joint" ctrllimited="true" ctrlrange="-1 5"/>
  </actuator>
</mujoco>"""
m2 = mujoco.MjModel.from_xml_string(xml2)
print(f"hier ok: nbody={m2.nbody}, nq={m2.nq}, nu={m2.nu}")
d2 = mujoco.MjData(m2)
d2.ctrl[0] = 1.0
for _ in range(5):
    mujoco.mj_step(m2, d2)
print(f"after 5 steps: qpos_root={d2.qpos[:3]}")
