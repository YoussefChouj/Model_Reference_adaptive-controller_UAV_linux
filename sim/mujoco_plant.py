"""MujocoPlant — MuJoCo-backed 6-DOF quadrotor plant.

Wraps :class:`sim.mujoco_bridge.MujocoBridge`. The state-dict shape
is the same as :class:`sim.plant.RigidBodyPlant` so the two engines are
interchangeable at the seam.

:class:`MujocoPlant` lives here so it can be authored, tested, and
imported independently of the analytic plant. Callers holding a
:class:`sim.plant.Plant` reference import it via this module.

.. rubric:: Loading a file-based MJCF

Pass ``model_xml="sim/models/jx_fly.xml"`` to use the validated
airframe model instead of the programmatic default. See
:func:`sim.plant.build_plant` for the registry entry that makes
``MujocoPlant`` available as ``build_plant("mujoco", dt=0.005)``.
"""
from __future__ import annotations

from typing import Optional

from sim.plant import Airframe, CANONICAL_AIRFRAME, Plant

try:
    from sim.mujoco_bridge import (
        MujocoBridge,
        MujocoBridgeConfig,
    )
    _HAS_MUJOCO_BRIDGE_IMPORT = True
except Exception:
    MujocoBridge = None  # type: ignore
    MujocoBridgeConfig = None  # type: ignore
    _HAS_MUJOCO_BRIDGE_IMPORT = False


# Mirror DEFAULT_MOTOR_TAU from sim.plant so this module is self-contained.
DEFAULT_MOTOR_TAU = 0.025  # seconds — 1st-order ESC lag


class MujocoPlant(Plant):
    """MuJoCo-backed 6-DOF quadrotor plant.

    Default configuration matches the canonical airframe and the
    identified motor time constant (25 ms). The MJCF is generated
    programmatically from the bridge config (no external file needed);
    pass ``model_xml`` to load the validated ``sim/models/jx_fly.xml``
    authored by this spec.

    The transport delay ``thrust_delay_s`` defaults to 0; ADR-0012 D6
    requires it for any plant used to learn priors — set it explicitly
    when adapting.
    """

    def __init__(self,
                 dt: float = 0.005,
                 airframe: Optional[Airframe] = None,
                 thrust_delay_s: float = 0.0,
                 motor_tau: float = DEFAULT_MOTOR_TAU,
                 model_xml: Optional[str] = None):
        if not _HAS_MUJOCO_BRIDGE_IMPORT:
            raise RuntimeError(
                "MujocoPlant: sim.mujoco_bridge is not importable.")
        self.dt = dt
        self.airframe = airframe if airframe is not None else CANONICAL_AIRFRAME
        self.thrust_delay_s = float(thrust_delay_s)
        self.motor_tau = float(motor_tau)
        self.model_xml = model_xml
        cfg = MujocoBridgeConfig(
            dt=dt,
            mass=self.airframe.mass,
            Ixx=self.airframe.Ixx,
            Iyy=self.airframe.Iyy,
            Izz=self.airframe.Izz,
            r_motor=self.airframe.r_motor,
            motor_tau=self.motor_tau,
            thrust_delay_s=self.thrust_delay_s,
            model_xml=model_xml,
        )
        self._bridge = MujocoBridge(cfg)
        self._last_U: dict[str, float] = {
            "roll": 0.0, "pitch": 0.0, "yaw": 0.0, "z": 0.0,
        }

    @staticmethod
    def is_available() -> tuple[bool, str]:
        """Probe whether the MuJoCo backend is reachable.

        Thin delegate to :meth:`MujocoBridge.is_available`. The single
        error message ("mujoco is not installed in this venv") matches
        the bridge's so a caller holding a :class:`Plant` reference gets
        the same wording as a caller probing the bridge directly.
        """
        if not _HAS_MUJOCO_BRIDGE_IMPORT:
            return (False, "mujoco is not installed in this venv")
        return MujocoBridge.is_available()

    def reset(self) -> None:
        """Restore deterministic zero state (level, at origin).

        Warm-starts the motor LPF to hover thrust so the plant does
        not free-fall during the LPF convergence transient (~5*tau).
        This keeps :meth:`step` deterministic *from t=0* — the analytic
        ``RigidBodyPlant`` initialises its motor LPF at hover for the
        same reason.
        """
        self._bridge.reset()
        self._last_U = {"roll": 0.0, "pitch": 0.0, "yaw": 0.0, "z": 0.0}
        # Warm-up: motor LPF converges in ~5*tau seconds; use 10*tau
        # so the LPF is at 99.9% of target by construction.
        warmup_ticks = max(50, int(round(10 * self.motor_tau / self.dt)))
        hover_total = self.airframe.mass * 9.80665
        for _ in range(warmup_ticks):
            self._bridge.step({
                "roll": 0.0, "pitch": 0.0, "yaw": 0.0, "z": hover_total,
            })
        # The warm-up leaves the body slightly above origin and with
        # a small upward velocity. Zero both without disturbing the
        # now-settled motor LPF state.
        d = self._bridge.data
        d.qpos[0] = d.qpos[1] = d.qpos[2] = 0.0
        d.qpos[3] = 1.0  # qw
        d.qpos[4] = d.qpos[5] = d.qpos[6] = 0.0  # qx,qy,qz
        d.qvel[:] = 0.0

    def step(self, u: dict) -> dict:
        """Advance one controller tick; return the same state dict as RigidBodyPlant."""
        self._last_U = {
            "roll": float(u.get("roll", 0.0)),
            "pitch": float(u.get("pitch", 0.0)),
            "yaw": float(u.get("yaw", 0.0)),
            "z": float(u.get("z", 0.0)),
        }
        return self._bridge.step(self._last_U)

