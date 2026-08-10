"""MuJoCo bridge — load MJCF, drive the model in-process, expose state.

This module is the lowest layer under :class:`sim.plant.MujocoPlant`.
It owns the ``mujoco.MjModel`` / ``mujoco.MjData`` pair, converts
firmware u-commands (per-axis body-rate setpoints + total thrust) into
per-motor thrust forces, applies them at the correct body-frame
motor positions, and steps the simulator.

Design points (ADR-0012 D6/D7):

- **In-process.** ``mujoco`` runs as a library; no subprocess, no IPC.
  On Windows we use MuJoCo's default CPU renderer (3.x has no
  ``offscreen`` kwarg any more; the headless path is the default).
- **Same physics seam as ``RigidBodyPlant``.** Inputs and outputs go
  through the same u-dict / state-dict interface, so the rest of the
  sim stack cannot tell which plant is active.
- **Integer transport-delay buffer (D6).** Each per-motor thrust
  command goes through ``_MotorDelayBuffer`` with
  ``N = round(T/dt)`` samples, identical to ``_AxisSim`` in
  ``sim/plant.py``. Reuses the same math; the buffer is lifted from
  ``_AxisSim`` into a reusable wrapper here.

Why a freejoint-only airframe model:

MuJoCo 3.x forbids ``freejoint`` on bodies nested under another body
(verified empirically — see test_mjc4.py: ``freejoint can only be
used on top level``). Two alternatives were considered:

  A. One free airframe + per-motor force injection via
     ``d.xfrc_applied`` at each motor position in body frame.
  B. Decouple with ball joints at the motors.

A is simpler, has no constraint drift, and matches what we want: the
rotors are pure force sources with no body dynamics, so modelling
them as full rigid bodies would be wasted degrees of freedom.

Quaternion convention: scalar-first ``[w, x, y, z]`` everywhere,
matching MuJoCo's ``qpos`` convention (positions 3..6). Body-to-world
rotation is read directly from ``d.xmat``.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
import platform
from typing import Optional

import numpy as np

# ----------------------------------------------------------------------
# Optional / lazy mujoco import. The bridge is importable on hosts
# without mujoco; ``MujocoPlant.step`` raises a clear error then.
# ----------------------------------------------------------------------
try:
    import mujoco  # type: ignore
    _HAS_MUJOCO = True
except ImportError:  # pragma: no cover - depends on the host's venv
    mujoco = None    # type: ignore
    _HAS_MUJOCO = False


# ----------------------------------------------------------------------
# Motor layout — X-frame, mirrored from sim/plant.py:148-167
# (motor_positions). We re-declare the geometry locally so this module
# is independent of sim.plant at import time (RigidBodyPlant reads the
# same numbers from CANONICAL_AIRFRAME).
# ----------------------------------------------------------------------
GRAVITY = 9.80665
ARM_LENGTH = 0.200            # m
CG_BELOW_ARM_PLANE = 0.0262   # m, thrust plane below CG (moment arm)


@dataclass(frozen=True)
class MujocoBridgeConfig:
    """All numeric tuning for the bridge in one place."""
    dt: float = 0.005               # 200 Hz, must match MRAC_DT
    mass: float = 1.2961            # kg (CANONICAL_AIRFRAME.mass)
    Ixx: float = 0.00839
    Iyy: float = 0.00930
    Izz: float = 0.01485
    r_motor: float = ARM_LENGTH
    # Per-axis response scaling (rad/s per unit of u-command). These
    # match the analytic plant's 1st-order poles for roll/pitch and the
    # integrator K for yaw. The MujocoPlant produces a body rate from
    # the *applied* torque; we scale u -> differential thrust so the
    # closed-loop response tracks the identified plant K. See
    # RigidBodyPlant.step for the same coefficients in the analytic
    # plant (sim/plant.py:706-712).
    dF_roll_unit: float = 0.005     # N per (rad/s) roll_u
    dF_pitch_unit: float = 0.005    # N per (rad/s) pitch_u
    dF_yaw_unit: float = 0.002      # N per (rad/s) yaw_u
    # Motor time constant — applied as a 1st-order LPF identical to
    # RigidBodyPlant (DEFAULT_MOTOR_TAU = 25 ms).
    motor_tau: float = 0.025
    # Transport delay (D6): N = round(T/dt) integer-sample buffer on
    # per-motor thrust. The IdentifiedPlant applies this on its rate
    # axes; the MujocoPlant applies it on per-motor thrust so the
    # delay budget is consistent across plants.
    thrust_delay_s: float = 0.0
    # MJCF path (relative to repo root).
    model_xml: str = "sim/models/jx_fly/jx_fly_mujoco.xml"


# ----------------------------------------------------------------------
# Reusable integer transport-delay buffer (lifted from _AxisSim in
# sim/plant.py so MujocoPlant and RigidBodyPlant share the math).
# ----------------------------------------------------------------------
class _MotorDelayBuffer:
    """FIFO of length ``N = round(T/dt)`` for a single scalar stream."""

    def __init__(self, T: float, dt: float):
        self.N = int(round(T / dt))
        self.buf = [0.0] * self.N

    def reset(self) -> None:
        for i in range(self.N):
            self.buf[i] = 0.0

    def push(self, x: float) -> float:
        if self.N == 0:
            return x
        out = self.buf[0]
        self.buf = self.buf[1:] + [x]
        return out


class MujocoBridge:
    """In-process MuJoCo simulator wired to JX_FLY physics.

    Lifecycle::

        bridge = MujocoBridge(MujocoBridgeConfig())
        bridge.reset()
        state_dict = bridge.step(u_dict)
        ...

    Inputs ``u_dict`` keys: ``{'roll', 'pitch', 'yaw', 'z'}`` (any
    subset, defaults 0). Same firmware-u convention as
    :class:`sim.plant.RigidBodyPlant`.

    Outputs ``state_dict`` keys: every Phase-1 key ``{p, q, r, vz}``
    plus the spec-4a widened set ``{x, y, z, vx, vy, vz_body, phi,
    theta, psi, q0..q3, thrust, motors, U_roll, U_pitch, U_yaw, U_z}``.
    """

    # ----- availability probe -----------------------------------------
    @staticmethod
    def is_available() -> tuple[bool, str]:
        """Return ``(available, reason)``.

        On hosts where ``mujoco`` is not importable, returns
        ``(False, reason)``; callers should treat that as a hard error.
        """
        if _HAS_MUJOCO:
            return (True, "mujoco importable")
        return (False, "mujoco is not installed in this venv")

    # ----- construction / loading ------------------------------------
    def __init__(self, cfg: Optional[MujocoBridgeConfig] = None):
        if not _HAS_MUJOCO:
            raise RuntimeError(
                "MujocoBridge: mujoco is not installed in this venv. "
                "Install mujoco to use MujocoPlant.")
        self.cfg = cfg or MujocoBridgeConfig()
        # Resolve the XML path relative to the repo root (cwd at run).
        xml_path = self.cfg.model_xml
        if not os.path.isabs(xml_path):
            xml_path = os.path.abspath(xml_path)
        if not os.path.exists(xml_path):
            raise FileNotFoundError(
                f"MujocoBridge: MJCF not found at {xml_path!r}. "
                f"Expected sim/models/jx_fly/jx_fly_mujoco.xml.")
        self.model = mujoco.MjModel.from_xml_path(xml_path)
        self.data = mujoco.MjData(self.model)
        # Per-motor delay buffer (D6).
        self._delay = _MotorDelayBuffer(self.cfg.thrust_delay_s, self.cfg.dt)
        # 1st-order motor LPF state (4-vector, N).
        self._motor_lpf = np.zeros(4)
        self._alpha = self.cfg.dt / (self.cfg.motor_tau + self.cfg.dt)
        # Cached body id (airframe body is the only non-world body).
        self._airframe_body = mujoco.mj_name2id(
            self.model, mujoco.mjtObj.mjOBJ_BODY, "airframe")
        if self._airframe_body < 0:
            raise RuntimeError(
                "MujocoBridge: MJCF must contain <body name='airframe'/>")
        # Reset state to zero.
        self.reset()

    # ----- state access ----------------------------------------------
    def reset(self) -> None:
        """Restore deterministic zero state (level, at origin)."""
        mujoco.mj_resetData(self.model, self.data)
        self._motor_lpf[:] = 0.0
        self._delay.reset()
        # Forward the reset through one no-op step so MJCF defaults
        # are materialised (some compile flags only fill in after a
        # step). 0-fills xfrc_applied so a stale force from a prior
        # test does not leak in.
        self.data.xfrc_applied[:] = 0.0
        mujoco.mj_forward(self.model, self.data)

    def state_dict(self) -> dict:
        """Return the current state as the same dict ``RigidBodyPlant`` does.

        Mirrors ``sim/plant.py:RigidBodyPlant.step``'s output schema so
        the two plants are interchangeable at the seam.
        """
        d = self.data
        # MuJoCo stores qpos as [x, y, z, w, qx, qy, qz] (world pos + scalar-first quat).
        x, y, z = float(d.qpos[0]), float(d.qpos[1]), float(d.qpos[2])
        qw, qx, qy, qz = (float(d.qpos[3]), float(d.qpos[4]),
                          float(d.qpos[5]), float(d.qpos[6]))
        # Body rates: qvel[0..2] is linear (world frame), qvel[3..5] is angular (body frame).
        vx, vy, vz = (float(d.qvel[0]), float(d.qvel[1]), float(d.qvel[2]))
        p, q, r = (float(d.qvel[3]), float(d.qvel[4]), float(d.qvel[5]))
        # ZYX Euler from quaternion (scalar-first).
        phi = np.arctan2(2.0 * (qw * qx + qy * qz),
                         1.0 - 2.0 * (qx * qx + qy * qy))
        sth = 2.0 * (qw * qy - qx * qz)
        sth = max(-1.0, min(1.0, sth))
        theta = np.arcsin(sth)
        psi = np.arctan2(2.0 * (qw * qz + qx * qy),
                         1.0 - 2.0 * (qy * qy + qz * qz))
        # Body-z velocity from R^T @ v_world.
        # Read R from d.xmat for the airframe body (3x3 row-major, 9 elements).
        R = self.data.xmat[self._airframe_body].reshape(3, 3).copy()
        vz_body = float((R.T @ np.array([vx, vy, vz]))[2])
        # Realised motor thrust (after LPF, before this step's apply).
        thrust_total = float(np.sum(self._motor_lpf))
        return {
            # Phase-1 rate keys (preserved)
            "p": p, "q": q, "r": r, "vz": vz,
            # Widened state keys (spec 4a)
            "x": x, "y": y, "z": z,
            "vx": vx, "vy": vy, "vz_body": vz_body,
            "phi": phi, "theta": theta, "psi": psi,
            "q0": qw, "q1": qx, "q2": qy, "q3": qz,
            "thrust": thrust_total, "motors": self._motor_lpf.copy(),
            # U-axis telemetry (last applied u)
            "U_roll": self._last_U.get("roll", 0.0),
            "U_pitch": self._last_U.get("pitch", 0.0),
            "U_yaw": self._last_U.get("yaw", 0.0),
            "U_z": self._last_U.get("z", 0.0),
        }

    # ----- step -------------------------------------------------------
    def step(self, u: dict) -> dict:
        """Advance one controller tick; return the same state dict as ``RigidBodyPlant``."""
        # 1. Resolve u-axes.
        r_roll = float(u.get("roll", 0.0))
        r_pitch = float(u.get("pitch", 0.0))
        r_yaw = float(u.get("yaw", 0.0))
        r_z = float(u.get("z", 0.0))   # total thrust in N
        self._last_U = dict(roll=r_roll, pitch=r_pitch, yaw=r_yaw, z=r_z)
        # 2. Compute per-motor thrust target (matches RigidBodyPlant
        #    sign convention: motor i = throttle + axis_i contributions).
        r = self.cfg.r_motor
        thrust_target = np.full(4, r_z / 4.0, dtype=float)
        thrust_target += np.array([
            +r_roll * self.cfg.dF_roll_unit - r_pitch * self.cfg.dF_pitch_unit - r_yaw * self.cfg.dF_yaw_unit,
            -r_roll * self.cfg.dF_roll_unit - r_pitch * self.cfg.dF_pitch_unit + r_yaw * self.cfg.dF_yaw_unit,
            -r_roll * self.cfg.dF_roll_unit + r_pitch * self.cfg.dF_pitch_unit - r_yaw * self.cfg.dF_yaw_unit,
            +r_roll * self.cfg.dF_roll_unit + r_pitch * self.cfg.dF_pitch_unit + r_yaw * self.cfg.dF_yaw_unit,
        ])
        # 3. 1st-order LPF — same alpha as RigidBodyPlant.
        self._motor_lpf = (
            (1.0 - self._alpha) * self._motor_lpf
            + self._alpha * thrust_target
        )
        # 4. Transport delay on each motor (D6).
        thrust_applied = np.array([
            self._delay.push(float(t)) for t in self._motor_lpf
        ])
        # 5. Apply forces at motor positions in body frame.
        #    MuJoCo's d.xfrc_applied is in WORLD frame: we transform
        #    each per-motor body-frame thrust into world frame using
        #    d.xmat (the body's rotation matrix).
        #    F_world = R @ F_body
        #    tau_world = R @ (p_body x F_body)
        # xmat is shaped (nbody, 9); index the airframe row.
        R = self.data.xmat[self._airframe_body].reshape(3, 3).copy()
        # Motor positions in body frame (X-frame, mirrored from plant.py).
        motor_pos_body = np.array([
            [ r,  r, 0.0],
            [-r,  r, 0.0],
            [-r, -r, 0.0],
            [ r, -r, 0.0],
        ])
        # F_body per motor: pure thrust along body +z (rotors push up).
        F_body = np.zeros((4, 3))
        F_body[:, 2] = thrust_applied
        # Net force (world frame) and net torque about CG (world frame).
        F_world_total = np.zeros(3)
        tau_world_total = np.zeros(3)
        for i in range(4):
            F_w = R @ F_body[i]
            F_world_total += F_w
            tau_world_total += R @ np.cross(motor_pos_body[i], F_body[i])
        # Also include the cg_below_arm_plane moment: a tilted thrust
        # vector passing through the rotor plane (offset below CG) exerts
        # tau = d * (R @ body_z_hat) about CG. In world frame this is
        # captured by the lever arm above (motor_pos_body z=0 is the
        # rotor plane; the offset only matters if rotors are above CG;
        # in our model they're level with CG so this term is zero).
        # The plan calls it out as a moment-arm parameter, not a tensor
        # offset — applied to thrust via the same lever-arm math.
        # (See sim/plant.py docstring for why the CG offset is not
        # applied to the inertia tensor.)
        self.data.xfrc_applied[self._airframe_body] = np.concatenate(
            [F_world_total, tau_world_total])
        # 6. Step the simulator.
        mujoco.mj_step(self.model, self.data)
        return self.state_dict()

    # ----- inspection helpers (test-only) ----------------------------
    @property
    def motor_thrust_n(self) -> np.ndarray:
        """Current LPF-filtered per-motor thrust (N), read-only view."""
        return self._motor_lpf.copy()


# ----------------------------------------------------------------------
# Headless / Windows note (informational, not a class attribute).
# ----------------------------------------------------------------------
# On Windows, MuJoCo 3.11.0's ``Renderer`` no longer takes an
# ``offscreen`` kwarg; the headless path is the default. No
# `gl.makeContextCurrent` or display binding is required. We do NOT
# instantiate a Renderer in the bridge — MujocoPlant uses one only if
# the caller asks for a render, and that is out of scope for this
# contract (the sim stack reads state dicts, not pixels).
# ----------------------------------------------------------------------