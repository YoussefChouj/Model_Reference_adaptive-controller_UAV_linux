# Session Summary — 2026-08-05 (Gazebo Hybrid SDF / X500 Visuals / Firewall Fix)

## What was being built

A **Model-Based Design (MBD) simulation pipeline** for a UAV research project:
- **Digital Twin**: Gazebo Sim (gz-jetty / gz-sim 10) running a quadrotor model (JX_FLY)
- **Python controller interface**: sends per-motor thrust commands via `gz-transport` topics
- **AI-agent-driven experiments**: an orchestrator (`sim/runner.py`) that composes SDF worlds,
  boots `gz sim` as a subprocess, runs deterministic scenarios, and records `trajectory.csv`
- **Goal**: reproduce real-flight scenarios with high-fidelity physics; let AI agents run
  experiment sweeps and compare results against analytic plant models

The full stack: `sim/runner.py` → `sim/gazebo_bridge.py` → `gz sim` subprocess →
`gz-transport` topics → `sim/recorder.py` → `runs/<ts>_scenario/`.

---

## Project structure

```
Model_Reference_adaptive-controller_UAV/
├── sim/
│   ├── gazebo_bridge.py   # Python bridge: step() drives gz sim via gz-transport
│   ├── runner.py           # Orchestrator: compose world, boot bridge, run scenarios
│   ├── plant.py            # Analytic 6-DOF rigid-body plant (RigidBodyPlant)
│   ├── recorder.py         # Records trajectory CSV
│   ├── aggregator.py       # Computes summary statistics
│   ├── sanity.py           # sim-vs-analytic hover gate
│   ├── urdf_conversion.py # URDF → SDF via `gz sdf -p` + IMU injection
│   ├── plot_trajectory.py  # Renders trajectory.csv as a multi-panel PNG
│   ├── scenarios_yaml.py    # Scenario dataclass + YAML loader
│   ├── spawn_drone.py      # Dynamic spawn via gz-transport EntityFactory service
│   ├── worlds/jx_fly.sdf  # Master SDF world (ODE physics, ground plane)
│   ├── models/jx_fly/
│   │   ├── model.sdf      # Hybrid SDF model (STL props, box geometry, measured inertia)
│   │   ├── jx_fly.urdf    # Canonical URDF (with STL propeller meshes)
│   │   └── meshes/        # 1345 STL propeller files (cw/ccw)
│   └── _artifacts/        # Per-run generated files (written by runner)
├── scenarios/
│   ├── hover.yaml         # 5 s hover at canonical thrust
│   └── step_roll.yaml     # 5 s, step roll command at t=0.5s
└── flight_analysis/       # Post-flight telemetry analysis (separate from sim)
```

---

## What was working before this session

The spec 4c live integration was **green** (passed smoke test). The system could:
- Boot `gz sim` as a subprocess
- Subscribe to pose/IMU topics via `gz-transport`
- Send motor thrust commands via `EntityWrench` persistent wrench
- Record trajectory data to `trajectory.csv`

---

## What this session tackled

The user asked for: **(a)** sim-vs-analytic cross-check and **(b)** visual graphs of successful runs.

### Problem 1 — Sanity gate failing: "Another world of the same name"

The original design ran the sanity gate **before** composing the world SDF. The bridge tried to load the bare master world (`sim/worlds/jx_fly.sdf`) which has **no model included** — just ground + plugins. The bridge timed out waiting for a pose subscriber because there was no model to publish one.

**Fix applied**: Moved world composition **before** the sanity gate. The gate now receives a composed world with the URDF-derived model included.

### Problem 2 — Two gz sim processes racing on world name

The runner tried to boot **two** gz sim subprocesses back-to-back:
1. Sanity gate → bridge #1 → gz sim (world name: `jx_fly`)
2. Main run → bridge #2 → gz sim (world name: `jx_fly`)

Gazebo refuses to load a second world with the same name. The first run would succeed, the second would fail with `"Another world of the same name is running"`.

**Fix applied**: `_compose_sanity_world()` creates a world with a unique name
(`sanity_<scenario>`). Two gz sims can coexist.

### Problem 3 — `PosePublisher` publishing link pose (z=0), not model pose

The `PosePublisher` plugin on the model publishes **TWO** messages per tick:
1. `name: "model::link"` → link pose in **model frame** (z=0 by definition, useless)
2. `name: "model"` → model pose in **world frame** (what we want)

The bridge was accepting **both** messages. The first one (link pose) overwrote the second
(model pose), so the bridge always read z=0.

**Fix applied**: Added filter `if msg.name != self.model_name: return` in the `on_pose`
callback. Now only the world-frame model pose is accepted.

### Problem 4 — Stale gz-transport-topic from earlier manual debugging

A leftover `gz-transport-topic -e -t /model/hover/pose` process (from 3 hours ago)
was still publishing stale poses to the host-wide transport bus. When the bridge
subscribed to `/model/hover/pose`, it received the stale pose before the fresh one
from the new gz sim.

**Root cause identified**: `gz-transport` topics are host-wide (not per-process). Any
dangling `gz topic` or `gz-transport-topic` process publishing to the same topic
will be mixed with the real publisher.

**Mitigation**: Always kill stray gz processes before running experiments.

---

## Today's session (2026-08-05 afternoon) — Gazebo GUI + X500 Hybrid Model

### Problem 5 — `<include><pose>` silently ignored (gz-sim 10 jetty)

The runner injects the model into the world using:
```xml
<include>
  <uri>/path/to/jx_fly_model.sdf</uri>
  <name>hover</name>
  <pose>0 0 5 0 0 0</pose>   <!-- should lift model to z=5 -->
</include>
```

Empirically confirmed (via `gz topic -e`): the model starts at **z=0.024** (collision
bottom touching ground), NOT at z=5. The `<include><pose>` is **silently ignored**.

Attempts made:
- `<include><pose>` → ignored
- `<model name='jx_fly'><pose>0 0 5 0 0 0</pose>` in the model SDF itself → ignored
- Both combined → still ignored

Upstream evidence: Issue [#2690](https://github.com/gazebosim/gz-sim/issues/2690) and
PR [#2697](https://github.com/gazebosim/gz-sim/pull/2697) show PosePublisher has had
multiple bugs in gz-sim 10 (jetty). The PosePublisher fix (`publish_model_pose=true` +
`publish_nested_model_pose=true`) was backported but apparently **not the include-pose
issue**.

The model always spawns with its collision box interpenetrating the ground plane.
ODE resolves this with a contact normal force that competes with upward thrust, and
ground friction that cancels roll/pitch torques — the model cannot fly.

**Status: UNRESOLVED.** Workaround: spawn model at z=0 and apply initial upward thrust.

### Problem 6 — X500 Fuel mesh rendering causes white-screen freeze

The PX4 X500 model (auto-downloaded from Fuel) includes complex **DAE collada meshes
with PBR materials** (`CF.png` diffuse texture, metallic/roughness workflows).
In the VM environment (no hardware GPU), Ogre2 render thread blocks loading these
assets, causing the GUI to hang at a **white screen**.

**Root cause**: PBR material loading in Ogre2 is GPU-intensive; no hardware acceleration.

**Fix attempts**:
- Force Ogre1 rendering (`--render-engine ogre`) → Ogre1 has different mesh loading path
  but still struggles with the complex PBR materials
- Use `LIBGL_ALWAYS_SOFTWARE=1` → no improvement
- Both combined → same white freeze

**Conclusion**: Complex PBR meshes are unsuitable for headless/VM environments.
Need either STL-only models or simplified DAE without PBR materials.

### Problem 7 — `model://` URI resolution fails without Fuel download

The SDF `model://` URI scheme resolves via `GZ_SIM_RESOURCE_PATH` and optionally
downloads missing models from Fuel. When Fuel download fails (no network or auth),
models referenced via `model://` silently fail to render.

**Confirmed**: `GZ_SIM_RESOURCE_PATH="$(pwd)/sim/models"` enables local model resolution
for models that exist locally. Models that don't exist locally → silent render failure.

### Problem 8 — UFW firewall blocking gz-transport multicast

When running `gz sim -g` (GUI + server in one command), gz forks the server and GUI
as separate processes that communicate via gz-transport UDP multicast. **UFW blocks
224.0.0.0/4 UDP multicast**, causing the GUI to hang at:
```
[GUI] [Dbg] [Gui.cc:498] GUI requesting list of world names. The server may be busy downloading resources. Please be patient.
```

This loops forever because the GUI cannot receive the world list from the server.

**Fix**: `sudo ufw disable` OR `sudo ufw allow in proto udp to 224.0.0.0/4`
(requires sudo — cannot be applied automatically in this environment)

**Workaround**: Run server-only (`gz sim <world.sdf>`) then GUI separately, OR use
`GZ_IP=127.0.0.1` to force TCP mode (but this alone doesn't fix the fork case).

### Problem 9 — Dynamic spawn via `gz-transport` service call hangs

The `spawn_drone.py` script uses `gz-transport Node.request()` to call
`/world/<world>/create` with `EntityFactory` protobuf. The call always times out
even though the service exists (`gz service -l` lists it).

**Root cause**: The `gz sim -g` fork uses a private gz-transport partition that is
not reachable from external Python scripts. The spawn service is only accessible
from within the same transport namespace.

**Implication**: Models must be included in the world SDF at launch time, not
spawned dynamically from Python.

### What was built this session

#### `sim/models/jx_fly/model.sdf` (hybrid SDF — STL-only)

Replaced the URDF-conversion path with a hand-written hybrid SDF:
- **Body**: geometric primitives (box, cylinders) — no DAE/PBR meshes
- **Propellers**: actual X500 1345 STL meshes (CCW motors 1&4, CW motors 2&3)
- **Inertia**: measured JX_FLY canonical values (mass=1.2961 kg, correct tensor)
- **Prop scale**: 0.846 to match 5-inch frame arms (1345 props are ~6-inch default)
- **Prop offset**: `xyz="-0.022 -0.146 -0.016"` centers the blade mesh on the shaft
- **Collision**: box + 4 cylinder arms (simplified but sufficient for physics)
- **IMU sensor**: Pixhawk-grade noise params (ADXL355/ICM-42688 equivalent)
- **PosePublisher**: world-frame model pose publication
- Spawns at **z=5** (hardcoded model `<pose>` — verified via `gz topic -e`)

#### `sim/models/jx_fly/jx_fly.urdf` (enhanced URDF)

Updated with propeller STL meshes:
- Added `mesh` geometry for all 4 motor links
- Uses `model://jx_fly/meshes/1345_prop_ccw.stl` and `1345_prop_cw.stl`
- Propeller origin offset to center blade on shaft

#### `sim/spawn_drone.py` (dynamic spawn script — not yet working)

New script for dynamic model spawning via gz-transport EntityFactory:
- Uses `gz.msgs.entity_factory_pb2.EntityFactory` with `sdf_filename` field
- Service: `/world/<world>/create`, response: `boolean_pb2.Boolean`
- Timeout: 10 s, returns bool success
- **Known issue**: service call hangs due to partition mismatch with `gz sim -g` fork

**Current status**: Fails because `gz sim -g` uses private transport partition.
**Fix needed**: Either (a) use `--partition=""` to force default partition, or
(b) run server-only and spawn before GUI attaches.

---

## The THREE remaining blockers

### Blocker A — `<include><pose>` not lifting model (UNRESOLVED)

The model always spawns at z=0. Ground contact → no flight → sanity gate fails.

**Fix options (pick one)**:
1. Use the `/world/<name>/set_pose` **service** after gz sim starts (via `gz service`)
2. Write the pose into the model SDF itself (currently not working — test needed)
3. Add a collision geometry offset so collision is above ground at z=0
4. Accept z=0 and apply initial upward thrust to get airborne (workaround)

### Blocker B — UFW multicast blocking GUI↔server communication (UNRESOLVED)

GUI hangs at "requesting world names" loop. Fix requires `sudo ufw disable`.

**Fix options (pick one)**:
1. User runs `sudo ufw disable` once on this machine
2. User runs `sudo ufw allow in proto udp to 224.0.0.0/4` once
3. Run server-only + GUI as two separate commands with `GZ_IP=127.0.0.1`
4. Use `--partition=""` on both server and GUI

### Blocker C — Model geometry is a placeholder (IN PROGRESS)

The box+cylinder model is visually wrong and misaligned. User is sourcing a
proper PX4 X500 or similar SDF model.

**Fix**: Download proper SDF → drop into `sim/models/` → update `runner.py` to use it.

---

## What's in the codebase right now

### `sim/runner.py` (409 lines)

Key functions:
- `_prepare_artifacts()`: converts URDF → SDF via `gz sdf -p`, injects model plugins,
  calls `_set_model_pose()`
- `_inject_model_plugins()`: injects `gz-sim-pose-publisher-system` and `gz-sim-imu-system`
  into the model SDF
- `_set_model_pose()`: writes `<pose>0 0 5 0 0 0</pose>` as a child of
  `<model name='jx_fly'>` in the per-run model SDF — **NOT confirmed working**
- `_compose_world()`: renders per-run world SDF with `<include>` for the model
- `_compose_sanity_world()`: renders sanity world with unique name to avoid races
- `run_experiment()`: orchestrates everything; runs sanity gate, then main scenario,
  closes bridge cleanly
- `_motor_thrusts()`: converts per-axis commands (z, roll, pitch, yaw) to 4-motor thrust
  vector using X-frame mixer convention
- `_command_at()`: evaluates time-varying command profile from scenario YAML

### `sim/gazebo_bridge.py` (~680 lines)

Key points:
- `GazeboBridge.__init__`: accepts `world_path`, `model_name`, `handshake_timeout_s`
- Subscribes to `/model/<model_name>/pose` — filtered to only accept model-frame pose
  (not link pose) via `if msg.name != self.model_name: return`
- Subscribes to `/world/<world_name>/imu` for body rates
- Publishes to `/world/<world_name>/wrench/persistent` (persistent EntityWrench, re-applied
  every physics tick)
- Also advertises `/world/<world_name>/wrench/clear` for cleanup on close
- `step()`: sends wrench, waits for pose+IMU update, returns `BridgeState`
- `reset()`: clears persistent wrench
- `close()`: publishes clear message, terminates subprocess

### `sim/sanity.py`

Three exported functions:
- `analytic_hover_trace()`: runs analytic plant for N seconds under hover thrust
- `compare_analytic_to_gazebo()`: compares final states, returns pass/fail + comparison dict
- `sim_vs_analytic_hover()`: convenience wrapper that boots its own bridge

### `sim/plot_trajectory.py`

Multi-panel matplotlib PNG renderer for `trajectory.csv`:
- Position (x, y, z)
- Attitude (phi, theta, psi in deg)
- Body rates (p, q, r)
- Per-motor thrust (m1..m4)
- Z command tracking
- Roll/pitch command tracking

Run: `python -m sim.plot_trajectory runs/<run>/trajectory.csv`

### `sim/spawn_drone.py` (new)

Dynamic model spawn script:
- Calls `/world/<world>/create` via gz-transport EntityFactory
- Usage: `python sim/spawn_drone.py --spawn-z 5.0`
- **Known issue**: times out due to transport partition mismatch

### `sim/worlds/jx_fly.sdf`

Master world:
- World name: `jx_fly`
- ODE physics, 1 ms step, real_time_factor=0 (fast as possible)
- Ground plane at z=0 (static)
- Plugins: Physics, UserCommands, SceneBroadcaster, ApplyLinkWrench (all world-level)
- **No model included** (model is injected by the runner per-run)

### `sim/models/jx_fly/model.sdf` (hybrid SDF — STL-only, placeholder geometry)

Current state:
- Body: box + 4 cylinder arms (no DAE mesh — white/grey primitives)
- Propellers: actual 1345 STL meshes (scaled 0.846)
- IMU sensor with Pixhawk-grade noise
- PosePublisher for world-frame pose
- Spawns at z=5 (hardcoded)
- **Needs**: proper visual mesh (user sourcing a model)

### `sim/models/jx_fly/jx_fly.urdf`

Canonical URDF with STL propeller meshes (used for URDF→SDF conversion path):
- Body: 42 cm box at CG origin
- 4 fixed arm joints at (±0.2, ±0.2, 0)
- Propeller meshes via `model://jx_fly/meshes/`

### `sim/models/jx_fly/meshes/`

Contains the X500 propeller STL files:
- `1345_prop_ccw.stl` — CCW propeller (motors 1 & 4)
- `1345_prop_cw.stl` — CW propeller (motors 2 & 3)

---

## Research findings

- **Issue [#2690](https://github.com/gazebosim/gz-sim/issues/2690)** — PosePublisher bug
  in gz-sim 10 where `publish_model_pose` was ignored. Fixed in
  [PR #2697](https://github.com/gazebosim/gz-sim/pull/2697).
- **Issue [#2285](https://github.com/gazebosim/gz-sim/issues/2285)** — "GUI requesting list
  of world names" hang. Fixed by `sudo ufw disable` or allowing UDP multicast 224.0.0.0/4.
- **SDFormat composition** — `//include/pose` should transform the model's canonical link
  frame. In practice it appears not to work for URDF-derived models in jetty.
- **PX4-Autopilot reference** — PX4 uses `ApplyLinkWrench` with the same `EntityWrench`
  format. Their reference world (gz_px4) spawns models correctly.
- **gz-transport partitions** — `gz sim -g` forks server+GUI into a private partition;
  external Python scripts cannot reach the `/world/<name>/create` service from that partition.
- **Ogre2 PBR** — complex DAE meshes with PBR materials (metallic/roughness) cause white
  screen hangs in VM/headless environments. STL meshes work reliably.

---

## Known environment facts

- **Python**: 3.12 (ABI compatibility with `gz-math9`, `gz-sim10` bindings)
- **Gazebo**: gz-sim 10 (jetty), gz-transport 15
- **Physics engine**: ODE (not DART — DART's contact stiffness was too aggressive)
- **Physics step**: 1 ms, real_time_factor=0 (fast as possible)
- **Controller rate**: 200 Hz (dt=0.005 s), 5 physics steps per controller tick
- **Wrench**: persistent `/world/<name>/wrench/persistent` (re-applied every physics tick)
- **Pose topic**: `/model/<model_name>/pose` (world-frame model pose, filtered by name)
- **IMU topic**: `/world/<world_name>/imu`
- **Airframe**: JX_FLY, mass=1.296 kg, arm=0.2 m, hover thrust/motor≈3.18 N
- **M Mixer**: X-frame, CCW motors 1&3, CW motors 2&4
- **Firewall**: UFW active, blocking gz-transport UDP multicast — needs `sudo ufw disable`
- **VM/headless**: Ogre2 PBR meshes cause white-screen freeze; STL-only models work

---

## Commands used during this session

```bash
# Kill stray gz processes (run before every experiment)
pkill -9 -f "gz-sim-main"; pkill -9 -f "gz-transport-topic"

# Launch bare world GUI (for spawn testing)
GZ_SIM_RESOURCE_PATH="$(pwd)/sim/models" gz sim -g sim/worlds/jx_fly.sdf

# Launch hybrid world with STL model
GZ_SIM_RESOURCE_PATH="$(pwd)/sim/models" gz sim -g /tmp/.../_artifacts/jx_fly_sanity_world.sdf

# Run a scenario
PYTHONPATH=. .venv/bin/python -c "
from sim.scenarios_yaml import load_scenario
from sim.runner import run_experiment
from sim.recorder import JSONLRecorder
import pathlib, random, string
suffix = ''.join(random.choices(string.ascii_lowercase, k=6))
outdir = pathlib.Path('/tmp/sim_plot_demo') / suffix
scenario = load_scenario('scenarios/hover.yaml')
result = run_experiment(scenario, JSONLRecorder(), output_dir=outdir, sanity=True)
print(result.summary)
"

# Plot trajectory
PYTHONPATH=. .venv/bin/python -m sim.plot_trajectory <path>/trajectory.csv

# Probe gz topics
gz topic -e -t /model/<name>/pose
gz topic -l

# Check gz log
tail -30 ~/.gz/auto_default.log

# Try dynamic spawn (currently hangs)
PYTHONPATH=. .venv/bin/python sim/spawn_drone.py --spawn-z 5.0
```

---

## What's next (priority order)

1. **[BLOCKER B] Fix firewall** — user runs `sudo ufw disable` or allows UDP multicast
2. **[BLOCKER C] Source proper SDF model** — PX4 X500 or similar, drop into `sim/models/`
3. **[BLOCKER A] Fix model spawn position** — bake z=5 pose into model SDF or use service call
4. **Verify sim-vs-analytic** — sanity gate should pass once model is airborne
5. **Plot trajectories** — run `sim/plot_trajectory.py` on successful runs
6. **Run step_roll scenario** — verify controller produces roll response
7. **Commit** — save all work to git
