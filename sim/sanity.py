"""Analytic-versus-Gazebo hover sanity gate (spec 4c)."""
from __future__ import annotations

import math
from typing import Callable

import numpy as np

from sim.gazebo_bridge import GazeboBridgeError, GazeboUnavailable
from sim.plant import CANONICAL_AIRFRAME, RigidBodyPlant


def sim_vs_analytic_hover(
    timeout_s: float = 30.0,
    *,
    bridge_factory: Callable | None = None,
) -> tuple[bool, dict]:
    """Run identical five-second hover inputs through both physics backends.

    The bridge path is invoked exactly the same way as
    :func:`sim.runner.run_experiment` -- through the supplied
    ``bridge_factory`` -- so any breakage in the bridge's transport
    surfaces a clean typed exception here rather than masquerading as
    a numeric divergence.
    """
    if bridge_factory is None:
        from sim.gazebo_bridge import GazeboBridge
        bridge_factory = GazeboBridge
    dt = 0.005
    initial = {"motor_thrust": [CANONICAL_AIRFRAME.thrust_per_motor_hover] * 4}
    analytic = RigidBodyPlant(dt=dt, airframe=CANONICAL_AIRFRAME, initial_state=initial)
    hover_motors = np.full(4, CANONICAL_AIRFRAME.thrust_per_motor_hover)
    bridge = None
    gazebo_state = None
    analytic_state = None
    try:
        bridge = bridge_factory(
            world_path="sim/worlds/jx_fly.sdf",
            handshake_timeout_s=timeout_s,
        )
        bridge.reset()
        for _ in range(int(5.0 / dt)):
            gazebo_state = bridge.step(hover_motors, dt)
            analytic_state = analytic.step({
                "z": CANONICAL_AIRFRAME.mass * 9.80665,
                "roll": 0.0, "pitch": 0.0, "yaw": 0.0,
            })
    except GazeboUnavailable as exc:
        return False, {"reason": "gz bindings unavailable", "detail": str(exc)}
    except GazeboBridgeError as exc:
        return False, {"reason": "gz sim did not become ready", "detail": str(exc)}
    finally:
        if bridge is not None:
            bridge.close()
    assert gazebo_state is not None and analytic_state is not None
    position_error = math.sqrt(sum(
        (float(getattr(gazebo_state, key)) - float(analytic_state[key])) ** 2
        for key in ("x", "y", "z")
    ))
    attitude_error = max(
        abs(float(getattr(gazebo_state, key)) - float(analytic_state[key]))
        for key in ("phi", "theta", "psi")
    )
    comparison = {
        "position_error_m": position_error,
        "max_attitude_error_deg": math.degrees(attitude_error),
        "position_tolerance_m": 0.10,
        "attitude_tolerance_deg": 2.0,
    }
    passes = position_error <= 0.10 and math.degrees(attitude_error) <= 2.0
    return passes, comparison


__all__ = ["sim_vs_analytic_hover"]