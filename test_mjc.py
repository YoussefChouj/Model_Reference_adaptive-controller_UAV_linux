import mujoco
xml = """<mujoco>
  <worldbody>
    <body name="b" pos="0 0 0">
      <freejoint/>
      <inertial pos="0 0 0" mass="1.0" diaginertia="0.1 0.1 0.1"/>
    </body>
  </worldbody>
</mujoco>"""
m = mujoco.MjModel.from_xml_string(xml)
d = mujoco.MjData(m)
mujoco.mj_step(m, d)
print(f"mujoco ok: nq={m.nq}, nv={m.nv}")
print(f"mujoco version: {mujoco.__version__}")
# Check renderer
try:
    r = mujoco.Renderer(m)  # 3.x: no offscreen kwarg
    print("renderer: ok")
    buf = np.zeros(r.viewport.width * r.viewport.height * 3, dtype=np.uint8)
    # Try readPixels
    try:
        r.read_pixels(buf, None, True)  # (buffer, scene, depth)
        print("read_pixels: ok")
    except Exception as e:
        print(f"read_pixels: {e}")
except Exception as e:
    print(f"renderer: {e}")

import numpy as np
# Check actuator (thr) element
xml2 = """<mujoco>
  <worldbody>
    <body name="b" pos="0 0 0">
      <freejoint/>
      <inertial pos="0 0 0" mass="1.0" diaginertia="0.1 0.1 0.1"/>
    </body>
  </worldbody>
  <actuator>
    <motor joint="freejoint" ctrllimited="true" ctrlrange="-1 1"/>
  </actuator>
</mujoco>"""
m2 = mujoco.MjModel.from_xml_string(xml2)
d2 = mujoco.MjData(m2)
print(f"nctrl={m2.nctrl}, nq={m2.nq}")
d2.ctrl[0] = 0.5
mujoco.mj_step(m2, d2)
print(f"ctrl applied: d2.ctrl[0]={d2.ctrl[0]}")
print("actuator motor on freejoint: ok")
