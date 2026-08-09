"""Gazebo transport bridge for the digital twin (spec 4c).

The bridge is the *only* module in the project that touches Gazebo. It is
imported optionally by :class:`sim.plant.GazeboPlant` so that ``import
sim.plant`` succeeds on Windows, where Gazebo is not installed, and the
sim-lane tests keep running unchanged.

Communication is via gz-transport topics using the gz-jetty Python bindings
(``gz.transport.Node``, ``gz.msgs.*``). The bridge starts ``gz sim`` as a
subprocess, loads the SDF world that includes the converted JX_FLY model,
and acts as the bridge between the controller's per-motor thrust vector
and the Gazebo world.

Determinism (revised 2026-08-05)
---------------------------------

The original design used real_time_factor=0 + -r (run on start), which
caused a free-fall race: the model spawns at z=5 but falls to the ground
in <1ms of wall-clock time before the bridge can subscribe. The fix
boots gz sim **paused** (no -r flag) and drives physics deterministically
via the /world/<name>/control service (WorldControl with multi_step=N).
This gives bit-for-bit repeatable runs regardless of host CPU speed.

Transport isolation: each bridge instance uses a unique GZ_PARTITION so
stale topics from previous runs cannot contaminate the current session.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np


# ---------------------------------------------------------------------------
# Module-level probe: do the gz bindings exist on this host?
# ---------------------------------------------------------------------------

class GazeboUnavailable(ImportError):
    """Raised when the gz-jetty bindings are not installed on this host.

    The message is the value the ``GazeboPlant._probe()`` reason string
    uses when the optional ``sim.gazebo_bridge`` import fails. Callers
    on Windows see this; callers on Linux with gz-jetty installed do not.
    """


class GazeboBridgeError(RuntimeError):
    """Raised by ``GazeboBridge`` when the sim cannot be brought up or
    the transport handshake fails. Always carries a clear message -- the
    bridge never fails silently."""


def _import_gz():
    """Import the gz-jetty Python bindings, raising ``GazeboUnavailable``
    with a clean message if they are absent. This is the only place in
    the bridge that touches the gz import, so the rest of the file can
    be read without worrying about the import path."""
    try:
        from gz.transport import Node, NodeOptions  # noqa: F401
        from gz.msgs import (  # noqa: F401
            actuators_pb2, imu_pb2, pose_pb2, vector3d_pb2, quaternion_pb2,
            entity_pb2, entity_wrench_pb2,
        )
        from gz.msgs import world_control_pb2 as world_control
        return {
            "Node": Node,
            "NodeOptions": NodeOptions,
            "actuators": actuators_pb2,
            "imu": imu_pb2,
            "pose": pose_pb2,
            "vector3d": vector3d_pb2,
            "quaternion": quaternion_pb2,
            "entity": entity_pb2,
            "entity_wrench": entity_wrench_pb2,
            "world_control": world_control,
        }
    except ImportError as exc:
        raise GazeboUnavailable(
            f"gz-jetty Python bindings not importable: {exc}. "
            f"Install gz-jetty on the Linux partition (apt repo "
            f"packages.osrfoundation.org). See spec 4b."
        ) from exc


def gz_binary_available() -> tuple[bool, str]:
    """``(available, reason)`` -- is the ``gz`` CLI on PATH?"""
    if shutil.which("gz") is not None:
        return (True, "gz reachable")
    return (False, "gz binary not on PATH; install gz-jetty.")


# ---------------------------------------------------------------------------
# State object returned by step()
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BridgeState:
    """State returned by ``GazeboBridge.step()``.

    Keys mirror :data:`sim.plant.FULL_STATE_KEYS` so the analytic and
    Gazebo plants can be swapped behind the same controller without the
    controller caring which backend is in use. Units and conventions
    match the analytic plant:

    - All positions in metres, body frame = NED (positive-down).
    - Attitude as ZYX Euler (phi/theta/psi) AND a scalar-first unit
      quaternion (q0, q1, q2, q3).
    - Body rates in rad/s.
    - Inertial velocity in m/s.
    - Total thrust in newtons (sum of the four realised motor thrusts).
    - Per-motor thrust in newtons, shape (4,).
    """
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    vz: float = 0.0
    phi: float = 0.0
    theta: float = 0.0
    psi: float = 0.0
    q0: float = 1.0
    q1: float = 0.0
    q2: float = 0.0
    q3: float = 0.0
    p: float = 0.0
    q: float = 0.0
    r: float = 0.0
    vz_body: float = 0.0
    thrust: float = 0.0
    motors: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)

    def as_state_dict(self) -> dict:
        """Render as the ``state_dict`` shape ``Plant.step()`` returns."""
        return {
            "x": self.x, "y": self.y, "z": self.z,
            "vx": self.vx, "vy": self.vy, "vz": self.vz,
            "phi": self.phi, "theta": self.theta, "psi": self.psi,
            "q0": self.q0, "q1": self.q1, "q2": self.q2, "q3": self.q3,
            "p": self.p, "q": self.q, "r": self.r,
            "vz_body": self.vz_body,
            "thrust": self.thrust,
            "motors": np.array(self.motors, dtype=float),
        }


# ---------------------------------------------------------------------------
# Bridge
# ---------------------------------------------------------------------------

class GazeboBridge:
    """Transport between the controller and a running ``gz sim`` instance.

    The constructor starts ``gz sim`` as a subprocess loading the given
    SDF world (which embeds the JX_FLY URDF), waits for the gz-transport
    node to come up, and creates the publisher/subscribers. It is
    expensive (subprocess spawn + handshake); one bridge instance is
    expected to live for an entire trajectory.

    Parameters
    ----------
    world_path : str
        Path to the SDF world file. Default: ``sim/worlds/jx_fly.sdf``.
    phys_step_ms : int
        Physics step in milliseconds. Default 1 ms (1000 Hz) -- chosen
        so that 5 physics steps fit comfortably inside one controller
        tick (5 ms) without dragging the sim to real-time.
    handshake_timeout_s : float
        Maximum time to wait for the gz-transport handshake. Default 5 s.
    real_time_factor : float
        Real-time factor passed to ``gz sim``. Default 0.0 (as fast as
        possible, deterministic). 1.0 lets the sim run in wall-clock
        time; leave at 0 for repeatable batch runs.
    verbose : bool
        Stream ``gz sim`` output to stderr. Default False (quiet for
        batch runs).
    """

    # Topic names. The world's model name is "jx_fly"; Gazebo scopes
    # topics under the world/model: /world/{world_name}/model/{model_name}/...
    # The ApplyLinkWrench system listens for ``gz.msgs.EntityWrench``
    # on the per-tick ``/world/<name>/wrench`` topic AND on the
    # ``/world/<name>/wrench/persistent`` topic for a force that is
    # re-applied every tick until cleared. We use the *persistent*
    # variant because the controller ticks at 200 Hz but the physics
    # engine ticks at 1000 Hz (1 ms step); publishing one wrench per
    # controller step would leave 4/5 of the physics ticks with no
    # thrust, so the body would just fall. The persistent topic holds
    # the last published wrench and re-applies it on every physics
    # tick, decoupling the controller rate from the physics rate.
    TOPIC_WRENCH_PERSISTENT = "/world/jx_fly/wrench/persistent"
    TOPIC_WRENCH_CLEAR = "/world/jx_fly/wrench/clear"
    TOPIC_POSE = "/world/jx_fly/pose"
    TOPIC_IMU = "/world/jx_fly/imu"

    def __init__(self,
                 world_path: str = "sim/worlds/jx_fly.sdf",
                 phys_step_ms: int = 1,
                 handshake_timeout_s: float = 5.0,
                 real_time_factor: float = 0.0,
                 model_name: str = "jx_fly",
                 verbose: bool = False) -> None:
        self._gz = _import_gz()
        ok, reason = gz_binary_available()
        if not ok:
            raise GazeboBridgeError(reason)

        self.world_path = world_path
        self.phys_step_ms = phys_step_ms
        self.real_time_factor = real_time_factor
        self.model_name = model_name
        # Parse the world name from the SDF file so we can construct the
        # correct world-scoped topic paths. The file path is not reliable
        # (e.g. jx_fly_run_world.sdf -> world name is still "jx_fly").
        self._world_name = self._parse_world_name(world_path)
        self.verbose = verbose

        # Latest state from the gz sim. Updated by the pose/IMU
        # subscribers on their own threads; the step() call reads the
        # most recent committed values.
        self._latest_pose: Optional[dict] = None
        self._latest_imu: Optional[dict] = None
        self._pose_lock = __import__("threading").Lock()
        self._gz_started_at: float = 0.0
        self._prev_z: Optional[float] = None

        self._proc = self._spawn_gz_sim()
        # gz sim takes a moment to initialize its transport layer. Without this
        # delay, the transport Node and subscribers may connect before gz sim is
        # ready, missing all messages.
        time.sleep(2.0)

        # The transport Node inherits GZ_PARTITION from os.environ.
        self._node = self._gz["Node"]()
        if self.verbose:
            print(f"[GazeboBridge] Node created, os.environ GZ_PARTITION={os.environ.get('GZ_PARTITION', 'not set')}")

        # CRITICAL: Subscribe to pose/IMU BEFORE stepping physics.
        # gz-transport delivers messages published AFTER a subscription is
        # established. If we step first, we miss the messages.
        self._setup_transport()

        # Give gz-transport discovery time to propagate the subscription to
        # the gz sim publisher. Empirical minimum on this host is ~1.0s;
        # with stat-based readiness this timeout is just the worst case.
        time.sleep(2.0)

        # Boot gz sim paused (no -r flag). Physics does NOT advance on its own.
        # We step once now to trigger the first PosePublisher publication so
        # the subscribers receive the initial spawn pose.
        self._advance_physics(1)

        self._wait_for_subscribers(handshake_timeout_s)

    def _parse_world_name(self, world_path: str) -> str:
        """Extract the world name from the SDF file.

        The world name is in <world name='...'>. The root <sdf> element does
        not have a name attribute. We search for the first <world> child.
        """
        import xml.etree.ElementTree as ET
        tree = ET.parse(world_path)
        root = tree.getroot()
        # SDF files have <sdf><world name="...">...</world></sdf> structure.
        for child in root:
            if child.tag == "world":
                return child.attrib["name"]
        raise GazeboBridgeError(
            f"Could not find <world> element in {world_path}"
        )

    # ------------------------------------------------------------------
    # Span + transport
    # ------------------------------------------------------------------

    def _spawn_gz_sim(self) -> subprocess.Popen:
        """Spawn ``gz sim`` with the given world. Returns the Popen.

        We do not use ``run()`` -- the process must keep running for the
        lifetime of the bridge. Stderr is captured to a log file so a
        ``GazeboBridgeError`` post-mortem can include the last few lines
        of the gz log.

        The gz sim boots **paused** (no -r flag). Physics advances only
        when the bridge calls the /world/<name>/control service with
        WorldControl(multi_step=N). This gives deterministic, reproducible
        stepping regardless of host CPU speed.
        """
        if not Path(self.world_path).exists():
            raise GazeboBridgeError(
                f"world file not found at {self.world_path!r}. "
                f"See sim/worlds/ for the canonical JX_FLY world."
            )
        log_file = Path("/tmp/gz_sim_bridge.log")
        log_fh = open(log_file, "w")

        # Each run gets its own transport partition to prevent stale topics
        # from contaminating the current session. Set GZ_PARTITION in the
        # environment BEFORE spawning gz sim AND before creating the transport
        # Node (which caches the partition at import/init time).
        partition = f"sim_{uuid.uuid4().hex[:8]}"
        # Set BEFORE both the subprocess and the Node see it.
        os.environ["GZ_PARTITION"] = partition
        env = os.environ.copy()
        if self.verbose:
            print(f"[GazeboBridge] partition={partition}, world={self._world_name}")

        cmd = [
            "gz", "sim",
            "-s",                    # server-only (headless, no GUI)
            self.world_path,          # NO -r flag -- physics starts paused
        ]
        if not self.verbose:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=log_fh,
                stdin=subprocess.DEVNULL,
                env=env,
            )
        else:
            proc = subprocess.Popen(cmd, stderr=log_fh, env=env)
        self._gz_log_path = str(log_file)
        self._partition = partition
        return proc

    def _setup_transport(self) -> None:
        """Create the publishers and subscribers.

        Subscribers write into ``self._latest_pose`` / ``self._latest_imu``
        under a lock; the step() method reads them once.
        """
        # Instance-level topic paths using the actual world name parsed from SDF.
        # gz-sim PosePublisher on an included model publishes to
        # /model/<name>/pose (model-scoped). ApplyLinkWrench wrench topics
        # are world-scoped (attached to the world plugin).
        topic_wrench_persistent = f"/world/{self._world_name}/wrench/persistent"
        topic_wrench_clear = f"/world/{self._world_name}/wrench/clear"
        topic_pose = f"/model/{self.model_name}/pose"

        # Publisher: motor commands. We publish one combined
        # ``gz.msgs.EntityWrench`` per controller tick to the
        # ``persistent`` topic, so each physics tick sees the most
        # recent thrust regardless of the controller-vs-physics rate
        # mismatch. The ``clear`` publisher is used to wipe the
        # persistent force on close() so the next run does not inherit
        # a stale thrust.
        self._wrench_pub = self._node.advertise(
            topic_wrench_persistent, self._gz["entity_wrench"].EntityWrench)
        if not self._wrench_pub:
            raise GazeboBridgeError(
                f"failed to advertise on {topic_wrench_persistent}; "
                f"check the SDF for the JX_FLY model plugin."
            )
        self._wrench_clear_pub = self._node.advertise(
            topic_wrench_clear, self._gz["entity"].Entity)

        # Subscriber: pose. The built-in pose-publisher system pushes
        # ``gz.msgs.Pose`` onto this topic; we read the position and
        # orientation. Velocity is reconstructed from the IMU
        # acceleration if needed.
        #
        # PosePublisher publishes TWO messages per tick on a model:
        #   1. ``child_frame_id = "<model>::<link>"`` -> pose of the
        #      link measured in the MODEL frame (z=0, identity quat by
        #      definition, useless here).
        #   2. ``child_frame_id = "<model>"`` -> pose of the MODEL in
        #      the WORLD frame. This is what we actually want.
        # Subscribe to both and select the world-frame one.
        self._pose_callback_count = 0  # debug counter
        if self.verbose:
            print(f"[GazeboBridge] subscribing to pose topic: {topic_pose}")
        def on_pose(msg):
            self._pose_callback_count += 1
            if self.verbose:
                print(f"[GazeboBridge] pose callback #{self._pose_callback_count}: name={msg.name}")
            with self._pose_lock:
                # ``name`` field is the child frame name. We want the
                # message whose ``name`` equals the model name itself
                # (i.e. the model pose in world frame), not the link.
                if msg.name != self.model_name:
                    return
                p = msg.position
                o = msg.orientation
                self._latest_pose = {
                    "x": p.x, "y": p.y, "z": p.z,
                    "q0": o.w, "q1": o.x, "q2": o.y, "q3": o.z,
                }

        def on_imu(msg):
            if self.verbose:
                print(f"[GazeboBridge] IMU callback: p={msg.angular_velocity.x:.3f}")
            with self._pose_lock:
                ang = msg.angular_velocity
                lin = msg.linear_acceleration
                self._latest_imu = {
                    "p": ang.x, "q": ang.y, "r": ang.z,
                    "ax": lin.x, "ay": lin.y, "az": lin.z,
                }

        if not self._node.subscribe(self._gz["pose"].Pose, topic_pose, on_pose):
            raise GazeboBridgeError(
                f"failed to subscribe to {topic_pose}"
            )

        # Try multiple IMU topic paths. The model SDF has the IMU plugin but
        # gz-sim publishes it under the ORIGINAL world name (jx_fly), not the
        # composed world name. We try the fallback (jx_fly) first since that's
        # where the model SDF publishes. If both fail, the bridge will still
        # fail but with a clearer error.
        imu_topics = [
            "/world/jx_fly/imu",           # original model SDF's world name (ACTUAL publisher)
            f"/world/{self._world_name}/imu",  # composed world name (does not exist)
        ]
        imu_sub_ok = False
        for imu_topic in imu_topics:
            if self.verbose:
                print(f"[GazeboBridge] subscribing to IMU topic: {imu_topic}")
            if self._node.subscribe(self._gz["imu"].IMU, imu_topic, on_imu):
                if self.verbose:
                    print(f"[GazeboBridge] IMU subscribed on {imu_topic}")
                imu_sub_ok = True
                break
        if not imu_sub_ok:
            raise GazeboBridgeError(
                f"failed to subscribe to IMU (tried: {imu_topics})"
            )

        self._gz_started_at = time.monotonic()

    def _wait_for_subscribers(self, timeout_s: float) -> None:
        """Block until the gz sim has published at least one pose.

        The custom plugin publishes the pose at the configured rate; we
        wait up to ``timeout_s`` for the first message to arrive. If
        the deadline elapses, the bridge is unusable and we tear down
        the subprocess with a clear error.
        """
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            with self._pose_lock:
                if self._latest_pose is not None:
                    return
            time.sleep(0.02)
        callback_count = getattr(self, '_pose_callback_count', 0)
        self.close()
        raise GazeboBridgeError(
            f"gz sim did not publish a pose within {timeout_s}s "
            f"(pose callback invoked {callback_count} times). "
            f"Check {self._gz_log_path} for plugin errors."
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def send_motor_command(self, motor_thrusts_N: np.ndarray) -> None:
        """Backwards-compatible Actuators publishing path.

        Retained so 4b-era callers keep working. Internally delegates to
        :meth:`send_motor_thrust`, which is the canonical transport
        surface (4c). New code should call :meth:`send_motor_thrust`
        directly.
        """
        self.send_motor_thrust(motor_thrusts_N)

    def send_motor_thrust(self, motor_thrusts_N: np.ndarray) -> None:
        """Translate the 4-element per-motor thrust vector into four
        ``gz.msgs.EntityWrench`` messages and publish them.

        Forces are applied along world +z at each motor link's body-frame
        position. Torques encode the X-frame reaction (CCW motors 1 and 3,
        CW motors 2 and 4) so yaw tracks the firmware mixer.
        """
        arr = np.asarray(motor_thrusts_N, dtype=float)
        if arr.shape != (4,):
            raise ValueError(
                f"send_motor_thrust requires exactly 4 thrust values, got "
                f"shape {arr.shape}"
            )
        thrusts = arr
        msg_cls = self._gz["entity_wrench"].EntityWrench
        # The ``Entity.Type`` enum lives on ``gz.msgs.entity_pb2.Entity``;
        # ``EntityWrench`` only carries an ``entity`` field. ``LINK`` is
        # value 3 in the canonical proto.
        entity_link = self._gz["entity"].Entity.LINK
        # Reaction torque per motor (Nm) for a unit of thrust
        # differential. Calibrated so a single-channel differential of
        # 1 N produces the same yaw acceleration as the firmware's
        # mixer-unit gain. Acts along world +z; sign flips for CW motors.
        reaction = 0.0134
        # Each motor's force is applied at the *center of mass* of
        # ``jx_fly_body``. The roll/pitch moment is encoded directly in
        # the wrench's torque field (rather than as a force at an offset)
        # because ApplyLinkWrench applies forces in the body frame, so
        # an offset would require coord conversion each step. The URDF
        # uses ``fixed_joint lump__motor_N`` so there is no separate
        # motor_N link to target.
        BODY_LINK = f"{self.model_name}::jx_fly_body"
        # Motor geometric layout (X-frame, m1=FR, m2=RR, m3=RL, m4=FL).
        # y_offsets[i] = body-y of motor i (positive = right side).
        # x_offsets[i] = body-x of motor i (positive = front side).
        # A positive roll moment about body +x comes from motors on the
        # +y side producing more thrust (right side lifts): the roll
        # command in the mixer is [+d, +d, -d, -d] for [m1,m2,m3,m4].
        # A positive pitch moment about body +y comes from motors on
        # the +x side producing more thrust (front side lifts): the
        # pitch command is [+d, -d, -d, +d].
        x_offsets = (0.2, -0.2, -0.2, 0.2)
        y_offsets = (0.2, 0.2, -0.2, -0.2)
        # Reaction torque gain: empirically tuned so the yaw produced
        # by a single-channel differential matches the analytic plant.
        reaction = 0.0134
        cummulative_force_z = 0.0
        cummulative_torque_x = 0.0
        cummulative_torque_y = 0.0
        cummulative_torque_z = 0.0
        for index, thrust in enumerate(thrusts):
            sign = -1.0 if index in (1, 2) else 1.0
            cummulative_force_z += float(thrust)
            # Roll (about +x): force at +y offset gives +torque_x.
            cummulative_torque_x += y_offsets[index] * float(thrust)
            # Pitch (about +y): force at +x offset gives -torque_y.
            cummulative_torque_y += -x_offsets[index] * float(thrust)
            # Yaw reaction (reactive torque): CCW motors contribute +
            cummulative_torque_z += sign * float(thrust) * reaction

        msg = msg_cls()
        msg.entity.name = BODY_LINK
        msg.entity.type = entity_link
        msg.wrench.force.x = 0.0
        msg.wrench.force.y = 0.0
        msg.wrench.force.z = cummulative_force_z
        msg.wrench.torque.x = cummulative_torque_x
        msg.wrench.torque.y = cummulative_torque_y
        msg.wrench.torque.z = cummulative_torque_z
        self._wrench_pub.publish(msg)

    def step(self, motor_thrusts_N: np.ndarray, dt: float) -> BridgeState:
        """Drive the sim forward by ``dt`` seconds with the given commands.

        Returns the state observed at the end of the step. Physics advances
        **exactly** ``dt`` of simulated time via the WorldControl
        multi_step service, then we wait for the pose/IMU update to land.
        No wall-clock polling -- the service call blocks until the requested
        number of steps completes.

        The gz sim was booted paused (no -r flag). Physics only advances
        when we call the control service here.
        """
        self.send_motor_thrust(motor_thrusts_N)

        # Advance physics by dt seconds. Each physics step is phys_step_ms.
        # WorldControl(multi_step=N) advances N steps and re-pauses.
        n_steps = max(1, int(round(dt / (self.phys_step_ms / 1000.0))))
        self._advance_physics(n_steps)

        # Wait for the pose/IMU update after stepping. The subscribers
        # update _latest_pose/_latest_imu on receipt. A brief spin-wait
        # handles transport latency (typically <1ms on localhost).
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            with self._pose_lock:
                if self._latest_pose is not None and self._latest_imu is not None:
                    pose = self._latest_pose
                    imu = self._latest_imu
                    break
            time.sleep(0.001)
        else:
            raise GazeboBridgeError(
                "gz sim did not publish pose+imu after stepping. "
                f"Check {self._gz_log_path}."
            )

        # Convert the (Z-Y-X) quaternion to Euler. The gz convention is
        # body-to-world; we follow the analytic plant's convention where
        # phi/theta/psi are body ZYX euler.
        q0 = pose["q0"]; q1 = pose["q1"]; q2 = pose["q2"]; q3 = pose["q3"]
        # Phi (roll) -- about body x
        sinr_cosp = 2.0 * (q0 * q1 + q2 * q3)
        cosr_cosp = 1.0 - 2.0 * (q1 * q1 + q2 * q2)
        phi = float(np.arctan2(sinr_cosp, cosr_cosp))
        # Theta (pitch) -- about body y
        sinp = 2.0 * (q0 * q2 - q3 * q1)
        theta = float(np.arcsin(max(-1.0, min(1.0, sinp))))
        # Psi (yaw) -- about body z
        siny_cosp = 2.0 * (q0 * q3 + q1 * q2)
        cosy_cosp = 1.0 - 2.0 * (q2 * q2 + q3 * q3)
        psi = float(np.arctan2(siny_cosp, cosy_cosp))

        # The body-frame z velocity is the projection of the inertial
        # velocity onto body +z. We do not have an inertial velocity in
        # the pose msg; the IMU gives accel only. Use the analytic
        # fallback: take the derivative of z once we have two samples.
        # For now, report body-z velocity as the derivative of (z) over
        # dt, which is exact for the small-dt limit.
        vz_body = float(pose["z"] - self._prev_z) / dt if self._prev_z is not None else 0.0
        self._prev_z = float(pose["z"])

        return BridgeState(
            x=float(pose["x"]), y=float(pose["y"]), z=float(pose["z"]),
            vx=0.0, vy=0.0, vz=0.0,         # not in pose; analytic plant's
                                            # (informational) vx/vy/vz are
                                            # returned by the IMU's
                                            # integrated signal. Kept at
                                            # 0 until the IMU is wired.
            phi=phi, theta=theta, psi=psi,
            q0=q0, q1=q1, q2=q2, q3=q3,
            p=float(imu["p"]), q=float(imu["q"]), r=float(imu["r"]),
            vz_body=vz_body,
            thrust=float(np.sum(motor_thrusts_N)),
            motors=(float(motor_thrusts_N[0]), float(motor_thrusts_N[1]),
                    float(motor_thrusts_N[2]), float(motor_thrusts_N[3])),
        )

    def _advance_physics(self, n_steps: int) -> None:
        """Advance physics by n_steps using the WorldControl service.

        The gz sim is paused. We call /world/<world>/control with
        WorldControl(pause=True, multi_step=n_steps) which advances
        n_steps physics ticks then re-pauses. This is the deterministic
        equivalent of wall-clock time in a real-time sim.
        """
        from gz.msgs import boolean_pb2

        req = self._gz["world_control"].WorldControl()
        req.pause = True
        req.multi_step = n_steps

        service = f"/world/{self._world_name}/control"
        if self.verbose:
            print(f"[GazeboBridge] calling {service} multi_step={n_steps}")
        ok, rep = self._node.request(
            service,
            req,
            self._gz["world_control"].WorldControl,
            boolean_pb2.Boolean,
            5000,  # timeout in ms
        )
        if self.verbose:
            print(f"[GazeboBridge] WorldControl result: ok={ok}")
        if not ok:
            raise GazeboBridgeError(
                f"WorldControl service {service} failed for {n_steps} steps. "
                f"Check {self._gz_log_path}."
            )

    def verify_pose(self, *, z_expected: float = 5.0, tolerance: float = 0.1) -> float:
        """Verify the model is at the expected spawn pose while the sim is paused.

        Reads the current pose from the subscriber without stepping physics.
        Returns the actual z coordinate. Use this immediately after __init__
        to confirm the model spawned at the intended altitude before any
        free-fall can occur.

        Raises ``GazeboBridgeError`` if the pose is not within tolerance of
        the expected value.
        """
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            with self._pose_lock:
                if self._latest_pose is not None:
                    actual_z = float(self._latest_pose["z"])
                    if abs(actual_z - z_expected) <= tolerance:
                        return actual_z
            time.sleep(0.005)
        raise GazeboBridgeError(
            f"Model did not reach z={z_expected} (tolerance {tolerance}m). "
            f"Got z={actual_z:.3f}. Check the SDF spawn pose and the "
            f"_set_model_pose injection in runner._prepare_artifacts. "
            f"See {self._gz_log_path}."
        )

        return BridgeState(
            x=float(pose["x"]), y=float(pose["y"]), z=float(pose["z"]),
            vx=0.0, vy=0.0, vz=0.0,         # not in pose; analytic plant's
                                            # (informational) vx/vy/vz are
                                            # returned by the IMU's
                                            # integrated signal. Kept at
                                            # 0 until the IMU is wired.
            phi=phi, theta=theta, psi=psi,
            q0=q0, q1=q1, q2=q2, q3=q3,
            p=float(imu["p"]), q=float(imu["q"]), r=float(imu["r"]),
            vz_body=vz_body,
            thrust=float(np.sum(motor_thrusts_N)),
            motors=(float(motor_thrusts_N[0]), float(motor_thrusts_N[1]),
                    float(motor_thrusts_N[2]), float(motor_thrusts_N[3])),
        )

    def reset(self) -> None:
        """Reset the sim to deterministic initial state.

        Implementation: send a zero-thrust persistent wrench for one
        physics tick, then re-publish the new thrust in step(). This
        clears the wrench left over from the previous step so the
        ``x5000 / apply_link_wrench`` style "each tick sees the latest"
        persistent mode doesn't carry an old thrust into the new run.
        """
        zero = np.zeros(4)
        self.send_motor_thrust(zero)
        time.sleep(0.01)
        self._prev_z = None

    def close(self) -> None:
        """Terminate the gz sim subprocess. Safe to call multiple times."""
        # Clear any persistent wrench first so a stale thrust does not
        # linger into the next run.
        if self._wrench_clear_pub is not None:
            try:
                clear_msg = self._gz["entity"].Entity()
                clear_msg.name = f"{self.model_name}::jx_fly_body"
                clear_msg.type = self._gz["entity"].Entity.LINK
                self._wrench_clear_pub.publish(clear_msg)
            except Exception:
                pass
        if self._proc is not None and self._proc.poll() is None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait(timeout=2.0)
        self._proc = None

    def __enter__(self) -> "GazeboBridge":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass


__all__ = [
    "GazeboUnavailable",
    "GazeboBridgeError",
    "BridgeState",
    "GazeboBridge",
    "gz_binary_available",
]
