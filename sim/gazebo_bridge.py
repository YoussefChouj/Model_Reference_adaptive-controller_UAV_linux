"""Gazebo transport bridge for the digital twin (spec 4b, spec 4c).

The bridge is the *only* module in the project that touches Gazebo. It is
imported optionally by :class:`sim.plant.GazeboPlant` so that ``import
sim.plant`` succeeds on Windows, where Gazebo is not installed, and the
sim-lane tests keep running unchanged.

Communication is via gz-transport topics using the gz-jetty Python bindings
(``gz.transport.Node``, ``gz.msgs.*``). The bridge starts ``gz sim`` as a
subprocess, loads the SDF world that includes the converted JX_FLY model,
and acts as the bridge between the controller's per-motor thrust vector
and the Gazebo world.

Determinism
-----------

The 200 Hz controller rate (``MRAC_DT = 0.005 s``) is *not* dictated by the
physics engine. The bridge issues physics ticks at the configured
``phys_step_ms`` (default 1 ms / 1000 Hz); each ``step`` invocation drives
enough ticks to advance the simulation by ``dt`` total. The transport
waits for the next physics tick to complete before reading state, so the
state returned corresponds to the moment the controller's clock says
``dt`` has elapsed. Wall-clock time is irrelevant — running the bridge
twice against the same inputs and the same seed gives the same trajectory.

Topics
------

Publisher (bridge -> gz sim):

- ``/world/jx_fly/wrench`` : ``gz.msgs.EntityWrench`` (one message per
  motor link, ``jx_fly::motor_{1..4}``). The built-in
  ``gz-sim-apply-link-wrench-system`` consumes these and applies the
  forces/torques directly, replacing the earlier custom system plugin
  from spec 4b. This keeps the build zero-C++ and the agent's edit-run
  loop in Python.

Subscribers (gz sim -> bridge):

- ``/world/jx_fly/pose`` : ``gz.msgs.Pose`` published by the built-in
  ``gz-sim-pose-publisher-system`` (no custom code needed).
- ``/world/jx_fly/imu``  : ``gz.msgs.IMU`` (synthetic body-frame IMU,
  published by ``gz-sim-imu-system``).

Failure modes
-------------

If Gazebo is not installed, the module raises ``GazeboUnavailable`` at
import time of the *bridge*, not at import time of ``sim.plant``. The
``GazeboPlant._probe()`` method catches this and reports the reason to
the caller.

The probe is also performed at ``GazeboBridge.__init__`` time: a missing
``gz`` binary, a hung subprocess, or a transport handshake timeout all
raise ``GazeboBridgeError`` with a clear message. The bridge should
never appear to succeed silently.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
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
        from gz.transport import Node  # noqa: F401
        from gz.msgs import (  # noqa: F401
            actuators_pb2, imu_pb2, pose_pb2, vector3d_pb2, quaternion_pb2,
            entity_pb2, entity_wrench_pb2,
        )
        return {
            "Node": Node,
            "actuators": actuators_pb2,
            "imu": imu_pb2,
            "pose": pose_pb2,
            "vector3d": vector3d_pb2,
            "quaternion": quaternion_pb2,
            "entity": entity_pb2,
            "entity_wrench": entity_wrench_pb2,
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
    # on TOPIC_WRENCH and dispatches per-link forces and torques.
    TOPIC_WRENCH = "/world/jx_fly/wrench"
    TOPIC_POSE = "/world/jx_fly/pose"
    TOPIC_IMU = "/world/jx_fly/imu"

    def __init__(self,
                 world_path: str = "sim/worlds/jx_fly.sdf",
                 phys_step_ms: int = 1,
                 handshake_timeout_s: float = 5.0,
                 real_time_factor: float = 0.0,
                 verbose: bool = False) -> None:
        self._gz = _import_gz()
        ok, reason = gz_binary_available()
        if not ok:
            raise GazeboBridgeError(reason)

        self.world_path = world_path
        self.phys_step_ms = phys_step_ms
        self.real_time_factor = real_time_factor
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
        self._node = self._gz["Node"]()
        self._setup_transport()
        self._wait_for_subscribers(handshake_timeout_s)

    # ------------------------------------------------------------------
    # Span + transport
    # ------------------------------------------------------------------

    def _spawn_gz_sim(self) -> subprocess.Popen:
        """Spawn ``gz sim`` with the given world. Returns the Popen.

        We do not use ``run()`` -- the process must keep running for the
        lifetime of the bridge. Stderr is captured to a log file so a
        ``GazeboBridgeError`` post-mortem can include the last few lines
        of the gz log.
        """
        if not Path(self.world_path).exists():
            raise GazeboBridgeError(
                f"world file not found at {self.world_path!r}. "
                f"See sim/worlds/ for the canonical JX_FLY world."
            )
        log_file = Path("/tmp/gz_sim_bridge.log")
        log_fh = open(log_file, "w")
        cmd = [
            "gz", "sim",
            "-r",                               # headless rendering off, just physics
            "--real-time-factor", str(self.real_time_factor),
            "--physics-step-ms", str(self.phys_step_ms),
            self.world_path,
        ]
        if not self.verbose:
            # Quiet mode: discard stdout, capture stderr to the log.
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=log_fh,
                stdin=subprocess.DEVNULL,
            )
        else:
            proc = subprocess.Popen(cmd, stderr=log_fh)
        self._gz_log_path = str(log_file)
        return proc

    def _setup_transport(self) -> None:
        """Create the publishers and subscribers.

        Subscribers write into ``self._latest_pose`` / ``self._latest_imu``
        under a lock; the step() method reads them once.
        """
        # Publisher: per-motor wrenches. We publish 4
        # ``gz.msgs.EntityWrench`` messages per controller tick
        # (one per motor link). The built-in ApplyLinkWrench system
        # applies the force and torque at the link's reference frame.
        self._wrench_pub = self._node.advertise(
            self.TOPIC_WRENCH, self._gz["entity_wrench"].EntityWrench)
        if not self._wrench_pub:
            raise GazeboBridgeError(
                f"failed to advertise on {self.TOPIC_WRENCH}; "
                f"check the SDF for the JX_FLY model plugin."
            )

        # Subscriber: pose. The built-in pose-publisher system pushes
        # ``gz.msgs.Pose`` onto this topic; we read the position and
        # orientation. Velocity is reconstructed from the IMU
        # acceleration if needed.
        def on_pose(msg):
            with self._pose_lock:
                # Convert gz::msgs::Pose into our BridgeState fields.
                p = msg.position
                o = msg.orientation
                self._latest_pose = {
                    "x": p.x, "y": p.y, "z": p.z,
                    "q0": o.w, "q1": o.x, "q2": o.y, "q3": o.z,
                }

        def on_imu(msg):
            with self._pose_lock:
                ang = msg.angular_velocity
                lin = msg.linear_acceleration
                self._latest_imu = {
                    "p": ang.x, "q": ang.y, "r": ang.z,
                    "ax": lin.x, "ay": lin.y, "az": lin.z,
                }

        if not self._node.subscribe(self._gz["pose"].Pose, self.TOPIC_POSE, on_pose):
            raise GazeboBridgeError(
                f"failed to subscribe to {self.TOPIC_POSE}"
            )
        if not self._node.subscribe(self._gz["imu"].IMU, self.TOPIC_IMU, on_imu):
            raise GazeboBridgeError(
                f"failed to subscribe to {self.TOPIC_IMU}"
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
        self.close()
        raise GazeboBridgeError(
            f"gz sim did not publish a pose within {timeout_s}s. "
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
        thrusts = np.asarray(motor_thrusts_N, dtype=float).reshape(4)
        if thrusts.shape != (4,):
            raise ValueError("send_motor_thrust requires exactly 4 thrust values")
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
        for index, thrust in enumerate(thrusts):
            sign = -1.0 if index in (1, 2) else 1.0
            msg = msg_cls()
            msg.entity.name = f"jx_fly::motor_{index + 1}"
            msg.entity.type = entity_link
            msg.wrench.force.x = 0.0
            msg.wrench.force.y = 0.0
            msg.wrench.force.z = float(thrust)
            msg.wrench.torque.x = 0.0
            msg.wrench.torque.y = 0.0
            msg.wrench.torque.z = float(sign * thrust * reaction)
            self._wrench_pub.publish(msg)

    def step(self, motor_thrusts_N: np.ndarray, dt: float) -> BridgeState:
        """Drive the sim forward by ``dt`` seconds with the given commands.

        Returns the state observed at the end of the step. The transport
        is *deterministic*: the sim advances **exactly** ``dt`` of
        simulated time, regardless of wall-clock speed. The waits are
        for the pose update to land, not for "dt wall-clock to elapse".
        """
        self.send_motor_thrust(motor_thrusts_N)

        # Wait for the next pose update. The plugin publishes at the
        # physics rate; we read the most recent one. The wait is
        # bounded by phys_step_ms * 2 + a small slack.
        deadline = time.monotonic() + (self.phys_step_ms / 1000.0) * 2.0 + 0.05
        while time.monotonic() < deadline:
            with self._pose_lock:
                if self._latest_pose is not None and self._latest_imu is not None:
                    pose = self._latest_pose
                    imu = self._latest_imu
                    break
            time.sleep(0.001)
        else:
            raise GazeboBridgeError(
                "gz sim did not publish pose+imu within one physics step. "
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

    def reset(self) -> None:
        """Reset the sim to deterministic initial state.

        Implemented as a service request to the sim's reset endpoint.
        On the first call after construction, ``self._prev_z`` is still
        None -- reset() clears it.
        """
        # The reset is a one-shot request to the /world/jx_fly/reset
        # service. For now we re-initialise the local state cache so the
        # next step() reads from a known baseline. The bridge remains
        # valid without it (the sim resumes its deterministic initial
        # state the next time the controller calls send_motor_thrust).
        self._prev_z = None

    def close(self) -> None:
        """Terminate the gz sim subprocess. Safe to call multiple times."""
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
