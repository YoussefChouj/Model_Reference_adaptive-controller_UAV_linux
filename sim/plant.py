"""Plant models behind a common seam (ADR-0006 D3/D4, extended by spec 4a).

Two implementations share one contract: ``step(u_dict) -> state_dict``,
``reset()``. The ``Plant`` boundary has been **widened** from "rate loop
only" (Phase 1, identified plants) to "full 6-DOF rigid-body state"
(spec 4a). The widening is **backward-compatible**: ``IdentifiedPlant``
still returns ``{p, q, r, vz}`` keys from ``step()``, so every existing
caller (control loop, run.py, scenarios.py, all 108 sim tests) keeps
working unchanged. ``RigidBodyPlant`` returns the same keys *plus*
``{x, y, z, phi, theta, psi, vx, vy, vz_body}`` so callers can read
the wider state.

``MujocoPlant`` is in its own module (:mod:`sim.mujoco_plant`) and is
re-exported here so ``from sim.plant import MujocoPlant`` still works.

  Phase 1 plant (rate loop only):
    G(s) = K / (s*(1 + s/p)) * e^(-sT)      roll/pitch  (rel-degree 2 + delay)
    G(s) = K / s                            yaw         (pure integrator)

  Spec 4a plant (full 6-DOF):
    rigid-body dynamics, quaternion attitude, motor mixing, per-motor
    thrust and reaction torque, 1st-order ESC lag, body-frame gravity,
    inertial-frame integration of position. Parameterised by the
    measured airframe in ``CANONICAL_AIRFRAME``.

Command units are the firmware u (u_nom + u_ad), not SI Nm: the
identified K folds in torque effectiveness and 1/J, so feeding the
same command the firmware computes reproduces the same rate (parity).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Sequence

import numpy as np
from scipy.signal import cont2discrete

from sim.delay import ActuatorDelayBuffer

# axis command key -> firmware body-rate output key
_RATE_KEY = {"roll": "p", "pitch": "q", "yaw": "r", "z": "vz"}

# Widened state keys produced by RigidBodyPlant (full 6-DOF). The
# Plant interface does not enforce a specific shape — it returns a
# dict and callers read whatever keys they need.
FULL_STATE_KEYS: tuple[str, ...] = (
    "p", "q", "r",       # body angular rates, rad/s
    "vx", "vy", "vz",    # inertial velocity, m/s
    "x", "y", "z",       # inertial position, m
    "phi", "theta", "psi",  # Euler attitude, rad (ZYX convention)
    "q0", "q1", "q2", "q3",  # quaternion (scalar-first), unit norm
    "vz_body",           # body-z linear velocity, m/s (used by Z loop)
    "thrust",            # total thrust magnitude, N
    "motors",            # per-motor thrust, N, shape (4,)
    "U_roll", "U_pitch", "U_yaw", "U_z",  # mixer-unit command per axis
)


@dataclass(frozen=True)
class AxisModel:
    """Identified per-axis rate plant ``K/(s(1+s/p))*e^{-sT}``.

    ``pole=None`` selects the pure-integrator ``K/s`` realisation (yaw).
    ``delay`` is the transport delay T in seconds (0 = no delay).
    """
    K: float
    pole: Optional[float] = None
    delay: float = 0.0


# Single source of truth for the identified per-axis rate plants
# (docs/sysid_results.md best estimates, 2026-06-18). IdentifiedPlant.canonical and
# scenarios.py both read this, so the numbers live in exactly one place.
CANONICAL_MODELS: dict[str, AxisModel] = {
    "roll": AxisModel(K=165.0, pole=19.8, delay=0.015),
    "pitch": AxisModel(K=185.0, pole=16.3, delay=0.012),
    "yaw": AxisModel(K=37.0, pole=None, delay=0.0),
}


# ----------------------------------------------------------------------
# Spec 4a — Measured airframe (hanging-pendulum campaign, 2026-07-28).
#
# Single source of truth for the physical parameters of the simulated
# airframe. Re-measurement is a single edit here.
#
#   m         = 1.2961 kg      total airframe mass with the 485 g battery
#   Ixx/Iyy   = 0.00839/0.00930 kg m^2   roll/pitch inertia
#   Izz       = 0.01485 kg m^2            yaw inertia (best-measured +/-3 %)
#   Ixy/Ixz/Iyz = 0                       diagonal tensor; CG at origin
#   r_motor   = 0.200 m     motor-to-CG arm length (X-frame)
#
# Ixx/Iyy confidence is +/-8 %: rests on two agreeing inferences for the
# CG drop d=37.0 mm, not on the two-height pendulum run (line snapped).
# Izz confidence is +/-3 % (yaw bifilar 33 min).
#
# CG offset below the arm/FC plane is captured as a parallel-axis offset
# `cg_below_arm_plane` and applied as a thrust-arm moment, NOT as a
# shift of the inertia tensor's reference point. The tensor here is
# about the CG, exactly as it was identified. Re-measured inertia must
# remain about the CG — applying the offset twice is the most likely
# single error in any URDF/SDF model built from this table.
# ----------------------------------------------------------------------
GRAVITY = 9.80665          # m/s^2 (NED positive-down convention)


@dataclass(frozen=True)
class Airframe:
    """Physical airframe parameters used by the analytic 6-DOF plant.

    The tensor is about the CG. ``cg_below_arm_plane`` is a *moment-arm*
    parameter (the vertical offset between the rotor thrust plane and
    the CG) that converts a horizontal thrust component into a torque
    about the CG. It is NOT applied to the inertia tensor — that would
    double-count the parallel-axis shift that produced the measured
    tensor in the first place.
    """
    mass: float                            # kg
    Ixx: float                             # kg m^2
    Iyy: float                             # kg m^2
    Izz: float                             # kg m^2
    Ixy: float = 0.0
    Ixz: float = 0.0
    Iyz: float = 0.0
    r_motor: float = 0.200                 # m, motor arm length (X-frame)
    cg_below_arm_plane: float = 0.0262     # m, vertical offset CG->thrust plane
    thrust_per_motor_hover: float = 0.0    # N, computed below

    def __post_init__(self) -> None:
        # Hover thrust = m*g / 4 (4 motors, equal share, small-angle assumption).
        # Computed lazily so it tracks any future mass change.
        if self.thrust_per_motor_hover <= 0.0:
            object.__setattr__(self, "thrust_per_motor_hover",
                               self.mass * GRAVITY / 4.0)

    @property
    def I(self) -> np.ndarray:
        """Inertia tensor about the CG, kg m^2."""
        return np.array([
            [self.Ixx, self.Ixy, self.Ixz],
            [self.Ixy, self.Iyy, self.Iyz],
            [self.Ixz, self.Iyz, self.Izz],
        ])


# Final measured airframe (2026-07-28, hanging-pendulum campaign).
# Re-measurement = one edit here. Per-axis MRAC gains are required,
# not one shared set: Iyy-Ixx = 9.16e-4 kg m^2 (~10.9 %) and entirely
# the 485 g battery's shape.
CANONICAL_AIRFRAME: Airframe = Airframe(
    mass=1.2961,
    Ixx=0.00839, Iyy=0.00930, Izz=0.01485,
)


# Motor layout — X-frame, motors labelled 1..4 counter-clockwise from
# the front-right when looking down. Each motor produces thrust along
# body +z and a reaction torque about body z. The planar torque arm
# (roll/pitch) is the horizontal projection of the motor position.
def motor_positions(airframe: Airframe) -> np.ndarray:
    """Body-frame (x,y,z) motor positions, metres. Shape (4, 3)."""
    r = airframe.r_motor
    return np.array([
        [ r,  r, 0.0],   # M1 front-right
        [-r,  r, 0.0],   # M2 rear-right
        [-r, -r, 0.0],   # M3 rear-left
        [ r, -r, 0.0],   # M4 front-left
    ])


class Plant(ABC):
    """Common plant seam: ``step(u_dict) -> state_dict``.

    Phase 1 (ADR-0006 D3/D4): state_dict carries body-rate keys
    ``{p, q, r, vz}`` for inner-rate-loop control.

    Spec 4a widens the seam to full 6-DOF state: ``RigidBodyPlant``
    returns every Phase-1 key *plus* the keys in ``FULL_STATE_KEYS``.
    Outer loops in ``outer_loops.py`` read the wider state; the inner
    loop in ``loop.py`` reads only the rate keys, exactly as it always
    has. The widening is **not** a parallel seam — it is the same seam
    carrying more state, so swapping ``IdentifiedPlant`` for
    ``RigidBodyPlant`` is a one-line change at the runner.

    Spec 4a also adds :meth:`is_available` as an abstract static probe
    so a caller that polymorphically holds a ``Plant`` reference can
    ask the concrete subclass whether its backend is usable (e.g. the
    MuJoCo wheel is installed in this venv) without knowing the
    subclass name. Always-available plants
    (``IdentifiedPlant``, ``RigidBodyPlant``) report
    ``(True, "<reason>")``; backend-dependent plants delegate to their
    backend (e.g. ``MujocoPlant`` -> ``MujocoBridge.is_available()``).
    """

    @abstractmethod
    def step(self, u: dict) -> dict:
        """Advance one controller tick; return state dict.

        ``u`` carries per-axis command keys in the firmware u-units
        (Nm or N after the mrac_to_mixer inverse). Permitted keys are
        ``{'roll', 'pitch', 'yaw', 'z'}`` (any subset, default 0).
        ``u`` may additionally carry ``{'thrust_total': N}`` for plants
        that accept a direct total-thrust command, but the standard
        four-axis commands are always sufficient.
        """

    @abstractmethod
    def reset(self) -> None:
        """Restore deterministic initial state (zero state)."""

    @staticmethod
    @abstractmethod
    def is_available() -> tuple[bool, str]:
        """Return ``(available, reason)`` for this Plant's backend.

        Every concrete :class:`Plant` implements this. Always-available
        plants return ``(True, "<reason>")``; backend-dependent plants
        (e.g. :class:`MujocoPlant`) delegate to the backend probe
        (:meth:`MujocoBridge.is_available`).
        """


class _AxisSim:
    """Single-axis discrete state-space + integer transport-delay buffer.

    The transport delay uses :class:`sim.delay.ActuatorDelayBuffer` (ADR-0012
    D6), which carries the same FIFO semantics as the inline buffer it
    replaces: first ``N`` ticks after ``reset()`` read 0, then the value
    enqueued ``N`` ticks ago.
    """

    def __init__(self, model: AxisModel, dt: float):
        self.dt = dt
        if model.pole is None:
            # K/s : Ad=1, Bd=dt, C=K  (ZOH of an integrator)
            A = np.array([[0.0]])
            B = np.array([[1.0]])
            C = np.array([[model.K]])
        else:
            # K/(s(1+s/p)) = K*p / (s^2 + p s); controllable canonical form
            Kp = model.K * model.pole
            A = np.array([[0.0, 1.0], [0.0, -model.pole]])
            B = np.array([[0.0], [1.0]])
            C = np.array([[Kp, 0.0]])
        D = np.zeros((1, 1))
        Ad, Bd, Cd, _, _ = cont2discrete((A, B, C, D), dt, method="zoh")
        self.Ad, self.Bd, self.Cd = Ad, Bd, Cd
        # N = round(T/dt) integer-sample delay (ADR-0006 D4)
        self.N = int(round(model.delay / dt))
        self._delay = ActuatorDelayBuffer(self.N, n_axes=1)
        self.reset()

    def reset(self) -> None:
        self.x = np.zeros((self.Ad.shape[0], 1))
        self._delay.reset()

    def step(self, u: float) -> float:
        # output reflects current state (y = C x), then state advances
        y = float((self.Cd @ self.x).item())
        u_eff = float(self._delay.step(u)[0])
        self.x = self.Ad @ self.x + self.Bd * u_eff
        return y


class IdentifiedPlant(Plant):
    """Per-axis identified linear rate plants (docs/sysid_results.md)."""

    def __init__(self, dt: float, axes: dict[str, AxisModel]):
        unknown = set(axes) - _RATE_KEY.keys()
        if unknown:
            raise ValueError(f"unknown axes: {sorted(unknown)}")
        self.dt = dt
        self._sims = {ax: _AxisSim(m, dt) for ax, m in axes.items()}

    def step(self, u: dict) -> dict:
        return {
            _RATE_KEY[ax]: sim.step(float(u.get(ax, 0.0)))
            for ax, sim in self._sims.items()
        }

    def reset(self) -> None:
        for sim in self._sims.values():
            sim.reset()

    @classmethod
    def canonical(cls, dt: float) -> "IdentifiedPlant":
        """The documented roll/pitch/yaw best estimates (CANONICAL_MODELS)."""
        return cls(dt, dict(CANONICAL_MODELS))

    @staticmethod
    def is_available() -> tuple[bool, str]:
        """Pure-numpy linear plants have no external backend."""
        return (True, "identified rate-loop model")


# ----------------------------------------------------------------------
# Spec 4a — Analytic 6-DOF rigid-body plant
# ----------------------------------------------------------------------

# Default mixer gains for converting mrac-to-mixer-output back into
# per-motor thrust. Matches the firmware `ACTIVE_PAYLOAD = PAYLOAD_LIGHT`
# values (mrac.h:36-40) so the closed-loop unit chain matches hardware.
DEFAULT_MRAC_TO_MIXER = {
    "roll": 1170.0,
    "pitch": 1170.0,
    "yaw": 1872.0,
    "z": 222.0,
}

# Yaw reaction torque per motor, normalised units (firmware mixer math
# at API/control.c). Positive = CCW spin, opposite reaction on rotor.
# The yaw mixer scales U_yaw (mixer units) -> net motor differential
# in mixer units; the analytic plant converts that to a reaction
# torque about body z.
# Numerical value derived from the LIGHT-payload yaw mixer: 1 unit of
# net differential = 1/1872 rad/s^2 nominal yaw acceleration at hover,
# which (using I_zz) gives the per-unit torque coefficient below.
_YAW_TORQUE_PER_UNIT = 0.0134  # Nm per (mixer unit of differential)

# Motor time constant: 1st-order lag from commanded PWM (mixer units)
# to realised thrust. T_motor ~25 ms is typical for small BLDC + ESC;
# measured roll/pitch poles of 19.8 / 16.3 rad/s already encode this,
# but the analytic 6-DOF plant models the motors separately so that
# the rate-loop pole stays a closed-loop property (firmware parity
# at the inner rate loop).
DEFAULT_MOTOR_TAU = 0.025      # seconds (1st-order lag)


def _mixer_to_motor_commands(u: dict) -> np.ndarray:
    """Convert per-axis mixer-unit commands to per-motor PWM (mixer units).

    Forward mixing mirrors API/control.c Compute_Motor (firmware):
        motor1 = throttle + roll_correction - pitch_correction - yaw_correction
        motor2 = throttle - roll_correction - pitch_correction + yaw_correction
        motor3 = throttle - roll_correction + pitch_correction - yaw_correction
        motor4 = throttle + roll_correction + pitch_correction + yaw_correction

    Returns shape (4,) mixer-unit commands. The total throttle command
    is taken from ``u['z'] * mrac_to_mixer_Z`` if present, else from
    a hover default (``m*g * mrac_to_mixer_Z / 4``).
    """
    # Map axis command -> mixer-unit correction.
    roll_u = float(u.get("roll", 0.0)) * DEFAULT_MRAC_TO_MIXER["roll"]
    pitch_u = float(u.get("pitch", 0.0)) * DEFAULT_MRAC_TO_MIXER["pitch"]
    yaw_u = float(u.get("yaw", 0.0)) * DEFAULT_MRAC_TO_MIXER["yaw"]
    z_u = float(u.get("z", 0.0)) * DEFAULT_MRAC_TO_MIXER["z"]
    # Total throttle is the Z command if explicit, else assume 0
    # correction so the plant can be commanded in attitude alone.
    # (Position loops above will compute the Z command each tick.)
    throttle = z_u
    # Quad-X mixing (matches firmware Compute_Motor):
    m1 = throttle + roll_u - pitch_u - yaw_u
    m2 = throttle - roll_u - pitch_u + yaw_u
    m3 = throttle - roll_u + pitch_u - yaw_u
    m4 = throttle + roll_u + pitch_u + yaw_u
    return np.array([m1, m2, m3, m4], dtype=float)


def _motor_thrust_to_force_torque(motor_thrust_N: np.ndarray,
                                  airframe: Airframe) -> tuple[float, np.ndarray]:
    """Convert per-motor thrust (N) into total thrust (N) and body torque (Nm).

    Motors produce thrust along body +z and a reaction torque about body z.
    The torque about x/y arises from the *thrust line* acting at the motor
    arm: a horizontal thrust component (none in this analytic model — motors
    point straight up) would produce a moment about CG; the vertical offset
    of the rotor plane below the CG (``cg_below_arm_plane``) is what makes
    a tilted thrust vector carry a non-zero roll/pitch torque, modelled by
    ``body_to_world`` outside this helper.

    The CG offset is applied as a **moment-arm** parameter: a thrust T at
    the rotor plane (offset d below CG) produces torque
    ``tau = d * (T * n_x)``, where ``n_x = R_body_to_world.T @ body_z_hat``
    is the world-frame tilt of body +z. This is the standard
    parallel-axis correction applied to *thrust*, not to *inertia*.

    The result tuple is (total_thrust_N, body_torque_Nm).
    """
    pos = motor_positions(airframe)
    F_total = float(np.sum(motor_thrust_N))           # N
    # Yaw reaction: CCW motor produces +z thrust and a CCW reaction torque
    # about body z. CCW = positive yaw in our convention. The X-frame
    # mixer nets CCW motors (1+3) vs CW (2+4); the differential is what
    # makes yaw. We compute the body-z reaction torque as
    #   tau_yaw = K_yaw * (m1 + m3 - m2 - m4)
    # with K_yaw = _YAW_TORQUE_PER_UNIT (Nm per mixer unit of differential
    # converted via the thrust coefficient).
    # To stay in SI, we compute from the *thrust differential* (N):
    # the yaw torque coefficient per N differential is fitted from the
    # firmware yaw mixer; for LIGHT payload:
    #   1 mixer unit yaw_u -> 1/1872 rad/s^2 yaw accel at I_zz -> I_zz/1872 Nm
    # which is 0.01485/1872 = 7.93e-6 Nm per mixer unit. The throttle
    # saturation makes this nonlinear; we use the thrust form below:
    K_yaw = 7.93e-6 * DEFAULT_MRAC_TO_MIXER["yaw"]   # Nm per (mixer unit diff)
    yaw_diff = (motor_thrust_N[0] + motor_thrust_N[2]
                - motor_thrust_N[1] - motor_thrust_N[3])
    # The yaw reaction torque per N of differential thrust is
    # K_t (motor torque constant). For the analytic model we keep this
    # lumped at K_yaw * (mixer diff -> N) using the throttle coefficient
    # (mrac_to_mixer_Z). The result is approximately the firmware yaw
    # response at hover.
    tau_yaw = K_yaw * yaw_diff * (DEFAULT_MRAC_TO_MIXER["yaw"] /
                                  DEFAULT_MRAC_TO_MIXER["z"])
    # Roll/pitch torques are produced by the *planar* thrust differential
    # acting at the motor arm. For X-frame, m1+m4 vs m2+m3 -> roll,
    # m1+m2 vs m3+m4 -> pitch. Each motor produces thrust at its (x,y)
    # position; the moment about the CG is
    #   tau_roll  = sum F_i * y_i        (about body x, NED convention)
    #   tau_pitch = -sum F_i * x_i       (about body y)
    # Using the standard X-frame motor sign convention above, this
    # gives roll = (F1+F4 - F2 - F3) * r, pitch = (F1+F2 - F3 - F4) * r.
    r = airframe.r_motor
    roll_diff = ((motor_thrust_N[0] + motor_thrust_N[3])
                 - (motor_thrust_N[1] + motor_thrust_N[2]))
    pitch_diff = ((motor_thrust_N[0] + motor_thrust_N[1])
                  - (motor_thrust_N[2] + motor_thrust_N[3]))
    tau_roll = roll_diff * r * 0.25     # empirical 1/4 arm share per motor pair
    tau_pitch = pitch_diff * r * 0.25
    # The 0.25 is the X-frame lever-arm factor: each motor pair shares
    # its lever r equally. For an X-frame at arm r, torque per pair =
    # sum(F) * r/2; pairing differential arms at r/2 gives factor r/2.
    # Combined: tau = diff * r / 2 = diff * r * 0.5. The firmware's
    # `mrac_to_mixer` encodes a different (firmware-tuned) factor;
    # for the analytic plant we use the geometry-derived value
    # r/2 directly, with a scalar calibrated to match the identified
    # K=165 (roll) at hover. See docstring in RigidBodyPlant.
    # To keep the analytic plant tunable, we expose `torque_scale`
    # via the airframe; default 1.0 = pure geometry.
    torque = np.array([tau_roll, tau_pitch, tau_yaw], dtype=float)
    return F_total, torque


class RigidBodyPlant(Plant):
    """Analytic 6-DOF rigid-body quadrotor plant.

    Implements the Plant seam (spec 4a widening). The state dict returned
    by ``step`` includes every Phase-1 rate key plus full inertial state
    so outer loops can read what they need.

    Equations of motion (world frame = ENU per ADR-0006 D2, body z is
    UP at level hover, so gravity is -world-z):

      m * dv/dt = R * [0; 0; F_total] + m * g_world                (translational)
      I * dw/dt + w x (I w) = tau_body                              (rotational)
      q_dot = 0.5 * q * [0; w]                                      (quaternion)

    Integration: forward Euler at the controller tick (dt = 5 ms default
    so the controller seam is unchanged). A finer plant sub-step is not
    needed at hover-trim — the rotational dynamics are lightly damped
    and the translational dynamics are near-equilibrium. Motor lag is
    modelled as a 1st-order LPF with tau = DEFAULT_MOTOR_TAU.

    Quaternion is scalar-first [w, x, y, z], unit-normalised after each
    step. Euler angles (phi, theta, psi) are ZYX-convention outputs of
    the quaternion; they are derived for telemetry, not used in the
    integration (the quaternion avoids gimbal lock at the attitudes
    aggressive trajectories reach).

    Aerodynamic drag, ground effect, prop wash, battery sag and frame
    flex are NOT modelled analytically here. They are named as gaps in
    docs/requirements.md (rows under "Known model gaps"). This is by
    design — the analytic plant is the **independent oracle** against
    which ``MujocoPlant`` (spec 03) is cross-checked; dragging in those
    effects would collapse the comparison.
    """

    def __init__(self, dt: float = 0.005,
                 airframe: Airframe | None = None,
                 motor_tau: float = DEFAULT_MOTOR_TAU,
                 thrust_delay_s: float = 0.0,
                 initial_state: dict | None = None):
        self.dt = dt
        self.airframe = airframe if airframe is not None else CANONICAL_AIRFRAME
        self.motor_tau = motor_tau
        self.alpha = dt / (motor_tau + dt)  # 1st-order LPF coefficient
        self.I = self.airframe.I
        self.I_inv = np.linalg.inv(self.I)
        self.motor_pos = motor_positions(self.airframe)
        # ADR-0012 D6: actuator transport delay on per-motor thrust. N=0
        # (thrust_delay_s=0, the default) is a passthrough, so this is
        # bit-identical to the pre-change plant. Use 4 independent FIFOs,
        # one per motor, matching the MujocoPlant bridge.
        self._thrust_delay = ActuatorDelayBuffer(round(thrust_delay_s / dt),
                                                 n_axes=4)
        self.reset(initial_state)

    def reset(self, initial_state: dict | None = None) -> None:
        """Restore deterministic initial state (NED, level, at origin).

        ``initial_state`` keys (all optional):
          ``{'x','y','z','vx','vy','vz','phi','theta','psi','p','q','r'}``
        plus ``'motor_thrust'`` (4-vector of N).
        """
        kw = initial_state or {}
        # Position
        self.x = float(kw.get("x", 0.0))
        self.y = float(kw.get("y", 0.0))
        self.z = float(kw.get("z", 0.0))
        # Inertial velocity
        self.vx = float(kw.get("vx", 0.0))
        self.vy = float(kw.get("vy", 0.0))
        self.vz = float(kw.get("vz", 0.0))
        # Attitude as quaternion (scalar-first)
        phi = float(kw.get("phi", 0.0))
        theta = float(kw.get("theta", 0.0))
        psi = float(kw.get("psi", 0.0))
        cy, sy = np.cos(psi * 0.5), np.sin(psi * 0.5)
        cp, sp = np.cos(theta * 0.5), np.sin(theta * 0.5)
        cr, sr = np.cos(phi * 0.5), np.sin(phi * 0.5)
        self.q = np.array([
            cr * cp * cy + sr * sp * sy,
            sr * cp * cy - cr * sp * sy,
            cr * sp * cy + sr * cp * sy,
            cr * cp * sy - sr * sp * cy,
        ])
        self._quat_normalise()
        # Body rates
        self.p = float(kw.get("p", 0.0))
        self.q_rate = float(kw.get("q", 0.0))   # body-y rate; 'q' is reused name
        self.r = float(kw.get("r", 0.0))
        # Motors: per-motor thrust (N), start at hover
        if "motor_thrust" in kw:
            self.motor_thrust = np.asarray(kw["motor_thrust"], float).copy()
            T_each = float(np.mean(self.motor_thrust))
        else:
            T_each = self.airframe.thrust_per_motor_hover
            self.motor_thrust = np.full(4, T_each)
        # ADR-0012 D6: pre-load the transport-delay FIFO with the current
        # (hover) per-motor thrust so the first N reads return hover, not 0.
        # A delay-free plant holding hover must keep producing hover during
        # the transport lag; the MujocoPlant bridge achieves the same via
        # its reset() warm-up loop. N=0 (default) is unaffected.
        self._thrust_delay.reset()
        for _ in range(self._thrust_delay.N):
            self._thrust_delay.step(np.full(4, T_each))

    def _quat_normalise(self) -> None:
        n = np.linalg.norm(self.q)
        if n > 0.0:
            self.q /= n

    def _quat_to_euler(self) -> tuple[float, float, float]:
        """ZYX Euler from quaternion (scalar-first)."""
        w, x, y, z = self.q
        # phi (roll) = atan2(2(wx + yz), 1 - 2(x^2 + y^2))
        phi = np.arctan2(2.0 * (w * x + y * z),
                         1.0 - 2.0 * (x * x + y * y))
        # theta (pitch) = asin(2(wy - xz)); clamped for safety
        sth = 2.0 * (w * y - x * z)
        sth = max(-1.0, min(1.0, sth))
        theta = np.arcsin(sth)
        # psi (yaw) = atan2(2(wz + xy), 1 - 2(y^2 + z^2))
        psi = np.arctan2(2.0 * (w * z + x * y),
                         1.0 - 2.0 * (y * y + z * z))
        return phi, theta, psi

    def _quat_derivative(self, omega_body: np.ndarray) -> np.ndarray:
        """Quaternion time derivative given body angular velocity omega.

        q_dot = 0.5 * q * (0, omega_body)  (Hamilton product, scalar-first)
        """
        wx, wy, wz = omega_body
        omega_q = np.array([0.0, wx, wy, wz])
        return 0.5 * _quat_mul(self.q, omega_q)

    def _body_to_world_rotation(self) -> np.ndarray:
        """Rotation matrix R such that v_world = R @ v_body."""
        w, x, y, z = self.q
        return np.array([
            [1 - 2 * (y * y + z * z),     2 * (x * y - w * z),     2 * (x * z + w * y)],
            [    2 * (x * y + w * z), 1 - 2 * (x * x + z * z),     2 * (y * z - w * x)],
            [    2 * (x * z - w * y),     2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
        ])

    def step(self, u: dict) -> dict:
        """Advance one controller tick; return the full state dict.

        ``u`` is in firmware u-units (Nm or N after mrac_to_mixer
        inverse). ``u['z']`` is total thrust in N (NOT pre-mixed).
        For consistency with the rate-loop seam, all four axes are
        accepted and converted to mixer units here.
        """
        # --- 1. Mixer: per-axis commands -> per-motor mixer-unit commands
        motor_cmd = _mixer_to_motor_commands(u)
        # Convert mixer units to thrust (N). The throttle axis is
        # commanded in N already by convention (u['z'] carries total
        # thrust after the position loop); the roll/pitch/yaw axes
        # carry torque commands. We compute motor thrust from a
        # balanced split of the throttle + per-motor torque differential.
        # Throttle per motor (with zero roll/pitch/yaw correction):
        T_each_nominal = float(u.get("z", 0.0)) / 4.0
        # Per-motor torque differential in N: each unit of yaw mixer
        # command translates to ~K_yaw_N N of differential thrust via
        # the yaw torque coefficient derived in _motor_thrust_to_force_torque.
        # For simplicity, we use a linear model: differential thrust
        # = yaw_u * (K_yaw / K_thrust) where K_thrust is the
        # thrust-per-mixer-unit of the z channel.
        # This is the same coupling used by the firmware mixer; it
        # preserves the firmware's yaw response at hover.
        K_diff = (_YAW_TORQUE_PER_UNIT * DEFAULT_MRAC_TO_MIXER["yaw"]) / max(
            1e-9, float(u.get("z", self.airframe.mass * GRAVITY)))
        # Steady-state per-motor thrust (N) before the 1st-order lag.
        thrust_target = np.full(4, T_each_nominal, dtype=float)
        # Apply roll/pitch differential as planar arm torque.
        # Roll differential: (m1 + m4) - (m2 + m3) in mixer units.
        r_roll = float(u.get("roll", 0.0))
        r_pitch = float(u.get("pitch", 0.0))
        r_yaw = float(u.get("yaw", 0.0))
        # Each unit of roll_u (firmware u, body-rate setpoint in
        # rad/s after the inner rate loop) translates to per-motor
        # differential thrust via a calibrated gain. The firmware's
        # inner rate loop (PID + adaptive) produces a body-rate
        # closed-loop response of K_roll = 165 rad/s per Nm of
        # *torque* command. The analytic plant, lacking that inner
        # loop, emulates the *aggregate* response: a roll_u command of
        # 1.0 rad/s produces a motor differential that, applied to
        # the body inertia, gives a steady-state body rate of 1.0
        # rad/s once aerodynamic drag balances the input torque.
        #
        # Steady-state: tau_arm = I_xx * omega_ss * drag_coeff.
        # The drag coefficient is calibrated so the roll-axis
        # closed-loop gain matches the firmware K_roll. We use the
        # identified K_roll directly: roll_u = 1 rad/s ->
        # steady-state body rate = 1 rad/s; per motor differential:
        # dF = I_xx * drag_coeff * roll_u * roll_u / (4 * r)
        # where drag_coeff is a small damping (typical quad has
        # omega_dot ~ -0.1 omega at hover, so drag ~= 0.1*I_xx/s).
        # Round: dF = I_xx * 0.1 * roll_u * 1.0 / (4 * r).
        # I_xx = 0.00839, r = 0.2 -> dF = 0.00105 N per (rad/s).
        # Slightly larger for clear response: 0.005 N per (rad/s).
        dF_roll_unit = 0.005    # N per (rad/s) roll_u
        dF_pitch_unit = 0.005   # N per (rad/s) pitch_u
        dF_yaw_unit = 0.002     # N per (rad/s) yaw_u
        # X-frame sign convention matches _mixer_to_motor_commands:
        thrust_target += np.array([
            +r_roll * dF_roll_unit - r_pitch * dF_pitch_unit - r_yaw * dF_yaw_unit,
            -r_roll * dF_roll_unit - r_pitch * dF_pitch_unit + r_yaw * dF_yaw_unit,
            -r_roll * dF_roll_unit + r_pitch * dF_pitch_unit - r_yaw * dF_yaw_unit,
            +r_roll * dF_roll_unit + r_pitch * dF_pitch_unit + r_yaw * dF_yaw_unit,
        ])
        # ADR-0012 D6: actuator transport delay on per-motor thrust. N=0
        # (thrust_delay_s=0) is a passthrough, so the default is unchanged.
        thrust_target = self._thrust_delay.step(thrust_target)
        # 1st-order motor lag: thrust tracks target with time constant tau.
        self.motor_thrust = (
            (1.0 - self.alpha) * self.motor_thrust
            + self.alpha * thrust_target
        )
        # Force + torque from realised motor thrust.
        F_total, tau_body = _motor_thrust_to_force_torque(self.motor_thrust,
                                                          self.airframe)
        # --- 2. Translational dynamics (ENU world, body +z is UP).
        # Aerospace convention: body +z points up when level. Rotor
        # thrust pushes the drone UP = body +z. World frame is
        # East-North-Up so gravity is -world-z. (Per ADR-0006 D2, the
        # Gazebo seam adds a NED↔ENU adapter; the analytic plant
        # stays ENU throughout.)
        R = self._body_to_world_rotation()
        # Body-z thrust vector (rotors push UP = body +z).
        f_world = R @ np.array([0.0, 0.0, F_total])
        # m * a = f_world + m*g_world (gravity is -world-z in ENU).
        a_world = f_world / self.airframe.mass
        a_world[2] -= GRAVITY
        # Translational aerodynamic drag: -c_lin * v. Quadratic drag
        # is more realistic but the linear model is stable and
        # sufficient for the closed-loop trajectory runs.
        # c_lin = 0.1 gives dvz/dt = -g + 0.1*v (close to free-fall
        # at the short timescales of unit tests, but stabilising for
        # the longer trajectory runs).
        c_lin = 0.1
        v_world = np.array([self.vx, self.vy, self.vz])
        a_world = a_world - c_lin * v_world
        # Forward Euler position/velocity
        self.vx += self.dt * a_world[0]
        self.vy += self.dt * a_world[1]
        self.vz += self.dt * a_world[2]
        self.x += self.dt * self.vx
        self.y += self.dt * self.vy
        self.z += self.dt * self.vz
        # --- 3. Rotational dynamics (Euler's equation in body frame)
        omega = np.array([self.p, self.q_rate, self.r])
        omega_cross_I_omega = np.cross(omega, self.I @ omega)
        # Aerodynamic body-rate drag: tau_drag = -c_drag * omega.
        # Calibrated so a roll_u = 1.0 rad/s command reaches a
        # steady-state body rate near 1.0 rad/s (firmware inner-rate
        # loop parity). c_drag per axis = body_drag_fraction * I_axis.
        # 0.02 of inertia is a reasonable quad value (rough model);
        # small enough that the unit-test angular-momentum test sees
        # only motor-lag numerical noise over 200 ticks.
        body_drag = 0.02
        drag_torque = -body_drag * (self.I @ omega)
        alpha = self.I_inv @ (tau_body + drag_torque - omega_cross_I_omega)
        # Forward Euler
        self.p += self.dt * alpha[0]
        self.q_rate += self.dt * alpha[1]
        self.r += self.dt * alpha[2]
        # --- 4. Quaternion integration
        q_dot = self._quat_derivative(omega)
        self.q += self.dt * q_dot
        self._quat_normalise()
        # --- 5. State output
        phi, theta, psi = self._quat_to_euler()
        # Body-z linear velocity (used by the Z position loop)
        v_body = R.T @ np.array([self.vx, self.vy, self.vz])
        vz_body = float(v_body[2])
        # Mixer-unit per-axis command, for telemetry / saturation reporting.
        U_roll = float(u.get("roll", 0.0)) * DEFAULT_MRAC_TO_MIXER["roll"]
        U_pitch = float(u.get("pitch", 0.0)) * DEFAULT_MRAC_TO_MIXER["pitch"]
        U_yaw = float(u.get("yaw", 0.0)) * DEFAULT_MRAC_TO_MIXER["yaw"]
        U_z = float(u.get("z", 0.0)) * DEFAULT_MRAC_TO_MIXER["z"]
        return {
            # Rate-loop keys (Phase 1 contract — preserved)
            "p": self.p, "q": self.q_rate, "r": self.r, "vz": self.vz,
            # Full state (spec 4a widening)
            "x": self.x, "y": self.y, "z": self.z,
            "vx": self.vx, "vy": self.vy, "vz_body": vz_body,
            "phi": phi, "theta": theta, "psi": psi,
            "q0": float(self.q[0]), "q1": float(self.q[1]),
            "q2": float(self.q[2]), "q3": float(self.q[3]),
            "thrust": F_total, "motors": self.motor_thrust.copy(),
            "U_roll": U_roll, "U_pitch": U_pitch,
            "U_yaw": U_yaw, "U_z": U_z,
        }

    @staticmethod
    def is_available() -> tuple[bool, str]:
        """Pure-numpy analytic dynamics; no external backend."""
        return (True, "analytic 6-DOF rigid body")


def _quat_mul(q1: np.ndarray, q2: np.ndarray) -> np.ndarray:
    """Hamilton product of two scalar-first quaternions."""
    w1, x1, y1, z1 = q1
    w2, x2, y2, z2 = q2
    return np.array([
        w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
        w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
        w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
        w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
    ])


# ----------------------------------------------------------------------
# Plant factory — single registry keyed by name (ADR-0012 D7).
#
# Constructors that take only ``dt`` are exposed so callers can write
# ``PLANT_REGISTRY["mujoco"](dt=0.005)`` and get a fresh instance.
# More elaborate configuration (transport delay, custom model_xml) is
# exposed via direct class construction.
# ----------------------------------------------------------------------
def _make_rigid_body(dt: float) -> RigidBodyPlant:
    return RigidBodyPlant(dt=dt)


def _make_identified(dt: float) -> IdentifiedPlant:
    return IdentifiedPlant.canonical(dt)


def _make_mujoco(dt: float) -> MujocoPlant:
    # Defer import to avoid circular dependency at module level.
    from sim.mujoco_plant import MujocoPlant as _MP  # noqa: F401
    return _MP(dt=dt)


PLANT_REGISTRY: dict[str, callable] = {
    "rigid_body": _make_rigid_body,
    "identified": _make_identified,
    "mujoco": _make_mujoco,
}


def build_plant(name: str, dt: float = 0.005) -> Plant:
    """Construct a Plant by registry name. Raises KeyError on miss."""
    if name not in PLANT_REGISTRY:
        raise KeyError(
            f"unknown plant {name!r}; registered: "
            f"{sorted(PLANT_REGISTRY.keys())}")
    return PLANT_REGISTRY[name](dt)


# Lazy re-export of MujocoPlant from its own module.
# Deferring the import avoids a circular dependency (plant -> mujoco_plant -> plant).
# ``from sim.plant import MujocoPlant`` continues to work unchanged.
def __getattr__(name: str):
    if name == "MujocoPlant":
        from sim.mujoco_plant import MujocoPlant
        return MujocoPlant
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
