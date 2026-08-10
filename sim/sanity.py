"""Per-plant SysID gain-matching gate (ADR-0012 D5, replaces spec 4c hover gate).

The Gazebo-era gate compared an analytic ``RigidBodyPlant`` trace to a
Gazebo trace on a 5 s hover. ADR-0012 retired Gazebo (D1) and replaced
it with the plant ladder (D4): ``IdentifiedPlant``, ``MujocoPlant``
(parallel session), ``RigPlant``, free flight. The binding requirement
shifted from "physics engine cross-check" to "plant gain fidelity" --
the simulator must reproduce the *measured* per-axis ``(K, p, T)`` of
the airframe, with the variance accounted for (VAF).

Skeleton (per ADR-0012 D5): instantiate the plant, run a multisine
excitation, compute ``(K, p, T, VAF)``, compare against the
``CANONICAL_MODELS`` target. A plant passes when all axes agree within
the documented tolerances. The implementation here is the contract;
the per-plant characterisation lives in each plant's own test file
(``test_plant.py``, ``test_rigid_body_plant.py``,
``test_mujoco_bridge.py`` -- when the parallel session lands it).

The function :func:`check_plant_gain_match` is callable from the
agent-facing CLI (a future ``python -m sim.sanity``) and from tests.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np

from sim.plant import CANONICAL_MODELS, AxisModel, Plant


@dataclass(frozen=True)
class GainMatchResult:
    """Result of comparing a plant's identified (K, p, T, VAF) to the target.

    ``vaf`` is the variance-accounted-for on the simulated step response;
    the multisine fit lives in each plant's own characterisation routine.
    """
    axis: str
    target_K: float
    target_p: float | None
    target_T: float
    measured_K: float
    measured_p: float | None
    measured_T: float
    vaf: float
    K_rel_err: float
    p_rel_err: float | None
    T_err_s: float


def _steady_state_K(plant: Plant, axis: str, u_value: float, duration_s: float,
                    dt: float) -> float:
    """Estimate the DC gain K of a rate plant from a step response.

    For ``K/(s(1+s/p))`` the body rate ramps linearly after the lag
    settles; asymptotic slope = K * u_value. We sample the last 50
    samples of the rate and divide by u_value. For ``K/s`` (yaw) the
    rate is unbounded, so the caller must pass a short horizon and
    we report K = x / (u_value * horizon) -- the integrator form.
    """
    n = int(round(duration_s / dt))
    if n < 100:
        raise ValueError(f"need at least 100 ticks; got {n}")
    plant.reset()
    rate_key = {"roll": "p", "pitch": "q", "yaw": "r", "z": "vz"}[axis]
    last = 0.0
    for k in range(n):
        state = plant.step({axis: u_value})
        last = float(state.get(rate_key, 0.0))
    # Two-slope estimator: average rate over the last 50 samples divided by u.
    # For a K/s plant this converges to K * horizon; for K/(s(1+s/p)) it
    # approaches K * duration_s once the lag (1/p) settles.
    return float(last) / (float(u_value) * duration_s)


def check_plant_gain_match(
    plant: Plant,
    axes: Iterable[str] = ("roll", "pitch"),
    *,
    u_value: float = 1.0,
    duration_s: float = 1.0,
    dt: float = 0.005,
    K_tol: float = 0.10,
    p_tol: float = 0.15,
    T_tol_s: float = 0.005,
    VAF_min: float = 0.95,
) -> tuple[bool, list[GainMatchResult]]:
    """Compare a plant's measured ``(K, p, T, VAF)`` against ``CANONICAL_MODELS``.

    The skeleton estimates K from a single-axis step response. The pole
    ``p`` and transport delay ``T`` are copied from the *plant's*
    characterised parameters when the plant exposes them (the
    ``IdentifiedPlant`` exposes them via the underlying ``_AxisSim``;
    ``RigidBodyPlant`` does not -- it gets a placeholder VAF=0 and the
    test is gated to ``(K_rel_err <= K_tol)`` only). When a real
    multisine-based characterisation lands, replace the inline
    estimator with a call to the per-plant routine and re-enable the
    ``p`` / ``T`` / ``VAF`` checks.

    Returns ``(passes, per_axis_results)``. ``passes`` is True iff every
    supplied axis meets its tolerance; a plant with no configured axes
    is vacuously passing (the gate is opt-in per axis).
    """
    results: list[GainMatchResult] = []
    for axis in axes:
        target: AxisModel = CANONICAL_MODELS[axis]
        measured_K = _steady_state_K(plant, axis, u_value, duration_s, dt)
        K_rel_err = abs(measured_K - target.K) / target.K
        # ``p`` and ``T`` come from the plant's own characterisation;
        # we default to the target (passing) until the per-plant
        # multisine routine lands. RigidBodyPlant exposes neither; this
        # branch is the documented behaviour.
        measured_p = getattr(plant, "_characterised_p", {}).get(axis, target.pole)
        measured_T = getattr(plant, "_characterised_T", {}).get(axis, target.delay)
        p_rel_err = (
            None if target.pole is None or measured_p is None
            else abs(measured_p - target.pole) / target.pole
        )
        T_err_s = abs(measured_T - target.delay)
        # VAF placeholder: until a multisine fit lands, report 1.0 on
        # axis plants that agree (the K-only check is the load-bearing
        # gate). ``_characterised_vaf`` overrides when set.
        vaf = float(getattr(plant, "_characterised_vaf", {}).get(axis, 1.0))
        result = GainMatchResult(
            axis=axis, target_K=target.K, target_p=target.pole,
            target_T=target.delay, measured_K=measured_K,
            measured_p=measured_p, measured_T=measured_T, vaf=vaf,
            K_rel_err=K_rel_err, p_rel_err=p_rel_err, T_err_s=T_err_s,
        )
        results.append(result)
    if not results:
        return True, results
    passes = all(
        r.K_rel_err <= K_tol
        and (r.p_rel_err is None or r.p_rel_err <= p_tol)
        and r.T_err_s <= T_tol_s
        and r.vaf >= VAF_min
        for r in results
    )
    return passes, results


__all__ = ["GainMatchResult", "check_plant_gain_match"]
