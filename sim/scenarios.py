"""Test scenarios for the closed-loop sim.

A Scenario fully specifies one run: which axis is excited, the rate command r(t)
(rad/s, the SI/MRAC space), an optional disturbance torque injected at the plant
input (Nm), and how to build the plant (a dt -> Plant factory, so a scenario can
swap in a modified plant). Per ADR-0006 D5 only the in-loop limits are modelled in
Phase 1; operational limits are deferred.

Two families, picked because they exercise different MRAC behaviours:
  * reference tracking  -- step / doublet / yaw_test: does x follow xm?
  * dynamics change     -- inertia_offset (scales the identified gain, i.e. a
    mass/inertia/voltage shift the adaptation must absorb) and disturbance
    rejection (a constant torque bias). The user asked specifically for the
    dynamics-changing stressors, since absorbing them is the whole point of MRAC.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable

from sim.plant import CANONICAL_MODELS, IdentifiedPlant, Plant

DEG2RAD = 0.0174533

# shared single source of truth (sim/plant.py); kept under the old name locally.
_CANON = CANONICAL_MODELS


def _zero(_t: float) -> float:
    return 0.0


def _canonical_factory(dt: float) -> Plant:
    return IdentifiedPlant.canonical(dt)


@dataclass
class Scenario:
    name: str
    axis: str
    duration: float                                   # seconds
    setpoint: Callable[[float], float]                # r(t) -> rad/s (active axis)
    disturbance: Callable[[float], float] = _zero     # d(t) -> Nm at plant input
    plant_factory: Callable[[float], Plant] = _canonical_factory
    description: str = ""

    def make_plant(self, dt: float) -> Plant:
        return self.plant_factory(dt)


def step(axis: str, *, amp_dps: float = 30.0, t0: float = 0.2,
         duration: float = 2.0) -> Scenario:
    """Single rate step (amp in deg/s, converted to rad/s)."""
    amp = amp_dps * DEG2RAD
    return Scenario(name=f"step_{axis}", axis=axis, duration=duration,
                    setpoint=lambda t: amp if t >= t0 else 0.0,
                    description=f"{amp_dps:g} deg/s step at t={t0}s")


def doublet(axis: str, *, amp_dps: float = 30.0, t0: float = 0.2,
            width: float = 0.4, duration: float = 2.0) -> Scenario:
    """+amp then -amp rate doublet -- excites both directions symmetrically."""
    amp = amp_dps * DEG2RAD

    def r(t: float) -> float:
        if t0 <= t < t0 + width:
            return amp
        if t0 + width <= t < t0 + 2 * width:
            return -amp
        return 0.0

    return Scenario(name=f"doublet_{axis}", axis=axis, duration=duration,
                    setpoint=r, description=f"+/-{amp_dps:g} deg/s doublet")


def yaw_test(*, amp_dps: float = 45.0, duration: float = 6.0) -> Scenario:
    """The kept yaw scenario: a staircase of yaw-rate steps (+, 0, -, 0)."""
    amp = amp_dps * DEG2RAD
    edges = [(0.5, amp), (2.0, 0.0), (3.0, -amp), (4.5, 0.0)]

    def r(t: float) -> float:
        val = 0.0
        for t_edge, v in edges:
            if t >= t_edge:
                val = v
        return val

    return Scenario(name="yaw_test", axis="yaw", duration=duration, setpoint=r,
                    description=f"yaw-rate staircase +/-{amp_dps:g} deg/s")


def inertia_offset(axis: str, *, factor: float = 0.6, amp_dps: float = 30.0,
                   t0: float = 0.2, duration: float = 2.5) -> Scenario:
    """Step command on a plant whose gain is scaled by ``factor`` (mass/inertia/
    voltage change). The baseline PID is tuned for the nominal plant, so the
    adaptation has to make up the difference -- a dynamics change, not a bias."""
    scaled = replace(_CANON[axis], K=_CANON[axis].K * factor)
    sc = step(axis, amp_dps=amp_dps, t0=t0, duration=duration)
    return replace(sc, name=f"inertia_offset_{axis}",
                   description=f"gain x{factor:g} ({amp_dps:g} deg/s step)",
                   plant_factory=lambda dt: IdentifiedPlant(dt, {axis: scaled}))


def disturbance_rejection(axis: str, *, torque_nm: float = 0.08, t0: float = 0.5,
                          duration: float = 2.5) -> Scenario:
    """Hold zero rate, then a constant torque bias hits the plant input."""
    return Scenario(name=f"disturbance_{axis}", axis=axis, duration=duration,
                    setpoint=_zero,
                    disturbance=lambda t: torque_nm if t >= t0 else 0.0,
                    description=f"{torque_nm:g} Nm bias at t={t0}s, r=0")


ALL: dict[str, Callable[[], Scenario]] = {
    "step_roll": lambda: step("roll"),
    "step_pitch": lambda: step("pitch"),
    "doublet_roll": lambda: doublet("roll"),
    "yaw_test": yaw_test,
    "inertia_offset_roll": lambda: inertia_offset("roll"),
    "disturbance_roll": lambda: disturbance_rejection("roll"),
}
