"""Analytic-versus-Gazebo hover sanity gate (spec 4c)."""
from __future__ import annotations

import math
from typing import Callable

import numpy as np

from sim.gazebo_bridge import GazeboBridgeError, GazeboUnavailable
from sim.plant import CANONICAL_AIRFRAME, RigidBodyPlant


# BOTH analytic plant and Gazebo world start at the same z-offset so
# the position-error comparison is fair. The composed world lifts the
# model 5 m above ground (see sim/runner.py::_compose_world); the
# analytic plant is given the same initial z so the trace divergence
# measures real physics divergence, not an initial-condition offset.
SHARED_INITIAL_Z_M = 5.0


def analytic_hover_trace(
    duration_s: float = 5.0,
    dt: float = 0.005,
) -> list[dict]:
    """Run the analytic RigidBodyPlant for ``duration_s`` under hover thrust.

    Returns one state dict per controller tick. Caller can compare element-wise
    against the Gazebo trace it produces in lockstep.
    """
    initial = {
        "motor_thrust": [CANONICAL_AIRFRAME.thrust_per_motor_hover] * 4,
        "z": SHARED_INITIAL_Z_M,
    }
    analytic = RigidBodyPlant(dt=dt, airframe=CANONICAL_AIRFRAME, initial_state=initial)
    trace = []
    for _ in range(int(duration_s / dt)):
        state = analytic.step({
            "z": CANONICAL_AIRFRAME.mass * 9.80665,
            "roll": 0.0, "pitch": 0.0, "yaw": 0.0,
        })
        trace.append(state)
    return trace


def compare_analytic_to_gazebo(
    gazebo_states: list,
    analytic_states: list[dict],
) -> tuple[bool, dict]:
    """Compare a recorded Gazebo trace against the analytic trace."""
    if len(gazebo_states) != len(analytic_states):
        return False, {
            "reason": "trace length mismatch",
            "gazebo_n": len(gazebo_states),
            "analytic_n": len(analytic_states),
        }
    if not gazebo_states:
        return False, {"reason": "empty traces"}
    diffs = []
    for gz, an in zip(gazebo_states, analytic_states):
        for key in ("x", "y", "z"):
            diffs.append(abs(float(getattr(gz, key)) - float(an[key])))
    position_error = math.sqrt(sum(
        (float(getattr(gazebo_states[-1], key)) - float(analytic_states[-1][key])) ** 2
        for key in ("x", "y", "z")
    ))
    attitude_error = max(
        abs(float(getattr(gazebo_states[-1], key)) - float(analytic_states[-1][key]))
        for key in ("phi", "theta", "psi")
    )
    comparison = {
        "position_error_m": position_error,
        "max_attitude_error_deg": math.degrees(attitude_error),
        "position_tolerance_m": 0.10,
        "attitude_tolerance_deg": 2.0,
        "gazebo_n": len(gazebo_states),
        "analytic_n": len(analytic_states),
    }
    passes = position_error <= 0.10 and math.degrees(attitude_error) <= 2.0
    return passes, comparison


def sim_vs_analytic_hover(
    timeout_s: float = 30.0,
    *,
    bridge_factory: Callable | None = None,
    world_path: str | None = None,
    model_name: str = "jx_fly",
) -> tuple[bool, dict]:
    """Run identical five-second hover inputs through both physics backends.

    Convenience wrapper that boots its own bridge. Production callers
    (the runner) should instead compose the world, build a single
    bridge, run :func:`analytic_hover_trace` and
    :func:`compare_analytic_to_gazebo` against the same bridge's trace
    -- otherwise two gz sim subprocesses race on the same world name.

    The bridge path is invoked exactly the same way as
    :func:`sim.runner.run_experiment` -- through the supplied
    ``bridge_factory`` -- so any breakage in the bridge's transport
    surfaces a clean typed exception here rather than masquerading as
    a numeric divergence.

    ``world_path`` lets callers pass a *composed* world SDF (one with
    the URDF-derived model included at a known pose) instead of the
    bare master template. The default ``None`` falls back to the
    master ``sim/worlds/jx_fly.sdf`` for callers that don't care.
    """
    if bridge_factory is None:
        from sim.gazebo_bridge import GazeboBridge
        bridge_factory = GazeboBridge
    dt = 0.005
    duration_s = 5.0
    hover_motors = np.full(4, CANONICAL_AIRFRAME.thrust_per_motor_hover)
    bridge = None
    gazebo_states: list = []
    analytic_states: list[dict] = []
    try:
        kwargs = {"handshake_timeout_s": timeout_s, "model_name": model_name}
        if world_path is not None:
            kwargs["world_path"] = world_path
        bridge = bridge_factory(**kwargs)
        bridge.reset()
        analytic_states = analytic_hover_trace(duration_s=duration_s, dt=dt)
        for tick in range(int(duration_s / dt)):
            gazebo_states.append(bridge.step(hover_motors, dt))
    except GazeboUnavailable as exc:
        return False, {"reason": "gz bindings unavailable", "detail": str(exc)}
    except GazeboBridgeError as exc:
        return False, {"reason": "gz sim did not become ready", "detail": str(exc)}
    finally:
        if bridge is not None:
            bridge.close()
    return compare_analytic_to_gazebo(gazebo_states, analytic_states)


__all__ = [
    "sim_vs_analytic_hover",
    "analytic_hover_trace",
    "compare_analytic_to_gazebo",
]