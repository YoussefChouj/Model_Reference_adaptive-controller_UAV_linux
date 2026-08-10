import mujoco

xml = """<mujoco>
  <worldbody>
    <body name="b" pos="0 0 0">
      <freejoint name="f"/>
      <inertial pos="0 0 0" mass="1" diaginertia="0.1 0.1 0.1"/>
    </body>
  </worldbody>
  <actuator>
    <general name="a" joint="f" type="force" ctrllimited="true" ctrlrange="-1 5"/>
  </actuator>
</mujoco>"""
m = mujoco.MjModel.from_xml_string(xml)
print(f"ok: nq={m.nq}, nv={m.nv}, nu={m.nu}")
d = mujoco.MjData(m)
d.ctrl[0] = 2.0
mujoco.mj_step(m, d)
print(f"after step: qpos={d.qpos[:3]}, cvel={d.cvel[:3]}")
