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


# ------------------------------------------------------------------
# ADR-0011 Phase 3 + Phase 4 — calibrator integration scenarios
# ------------------------------------------------------------------

def cold_with_bias(*, duration: float = 4.2) -> Scenario:
    """Scenario A (Phase 3): accel bias on flat surface, cold-cal gate then AccBiasTrim.

    Plant has constant +50 mg Z-accel bias (sensor reads high: g_meas = 1050 mg).
    Ticks 0-400 (0-2 s): cold-cal ground, no AccBiasTrim update.
    Ticks 400-600 (2-3 s): take-off transient, no update.
    Ticks 600-840 (3-4.2 s): AccBiasTrim runs at 200 Hz for 240 ticks.
    With mu=0.02: (1-0.02)^240 ≈ 0.008, residual < 0.8% → settled < 5 mg.

    Firmware residual: residual = g_ref - (g_meas + b_a), so it learns b_a = -50 mg
    (removes the positive sensor bias).  Flat surface: no tilt ambiguity.

    Assertion: |b_a_z − (−50)| < 5 mg at end of run.
    """
    def _plant_factory(dt: float) -> Plant:
        from sim.plant import IdentifiedPlant
        base = IdentifiedPlant.canonical(dt)
        # Positive Z bias: g_meas_z = 1000 + 50 = 1050 mg
        return _AccBiasOnlyPlant(dt, base, acc_bias_mg=(0.0, 0.0, 50.0))

    return Scenario(
        name="cold_with_bias",
        axis="pitch",
        duration=duration,
        setpoint=_zero,
        plant_factory=_plant_factory,
        description=(
            "Phase 3: +50 mg accel-bias Z, flat surface, "
            "cold-cal gate then AccBiasTrim from tick 600"
        ),
    )


def hot_gyro_drift(*, duration: float = 6.0) -> Scenario:
    """Scenario B (Phase 4): gyro bias 0.02 rad/s on Y during clean hover.

    After 1 s of stable hover the GyroBiasHotFsm has accumulated enough still-time
    (100 ticks) to enter ACCUM, then 400 ticks to COMMIT. The FSM runs from tick 0
    but its guards prevent accumulation until flying=True.

    Assertion: 0 < b_g_y < 0.01 rad/s — correct direction (toward 0.02) but
    alpha=1e-4 makes it < 50 % of injected value after one commit.
    """
    def _plant_factory(dt: float) -> Plant:
        from sim.plant import IdentifiedPlant
        base = IdentifiedPlant.canonical(dt)
        return _GyroBiasPlant(dt, base, gyro_bias_rads=(0.0, 0.02, 0.0))

    return Scenario(
        name="hot_gyro_drift",
        axis="pitch",
        duration=duration,
        setpoint=_zero,
        plant_factory=_plant_factory,
        description=(
            "Phase 4: 0.02 rad/s gyro bias Y, clean hover, "
            "GyroBiasHotFsm converges slowly (alpha=1e-4)"
        ),
    )


# ------------------------------------------------------------------
# Plant wrappers that inject sensor bias for the calibrator scenarios
# ------------------------------------------------------------------

class _AccBiasOnlyPlant:
    """Plant that reports body-frame accel with a constant sensor bias.

    Models: g_meas = (0, 0, g_world) + b_a  [mg]
    for use with AccBiasTrim (Phase 3).  No tilt; no rotation.
    """

    def __init__(self, dt: float, base: Plant, acc_bias_mg: tuple):
        self._base = base
        self._acc_bias = acc_bias_mg

    def step(self, u: dict) -> dict:
        return self._base.step(u)

    def get_accel_mg(self) -> tuple:
        # World gravity (mg, no tilt) + sensor bias
        # g_meas = g_world + b_a; g_world = (0, 0, 1000)
        return (self._acc_bias[0],
                self._acc_bias[1],
                1000.0 + self._acc_bias[2])

    def get_gyro_rads(self) -> tuple:
        return (0.0, 0.0, 0.0)

    def reset(self) -> None:
        self._base.reset()


class _GyroBiasPlant:
    """Plant that injects a constant gyro bias for GyroBiasHotFsm testing."""

    def __init__(self, dt: float, base: Plant, gyro_bias_rads: tuple):
        self._base = base
        self._gyro_bias = gyro_bias_rads
        self._last_rates = (0.0, 0.0, 0.0)

    def step(self, u: dict) -> dict:
        out = self._base.step(u)
        self._last_rates = (out.get("p", 0.0), out.get("q", 0.0), out.get("r", 0.0))
        return out

    def get_accel_mg(self) -> tuple:
        """No accel bias — gravity only, mg."""
        return (0.0, 0.0, 1000.0)

    def get_gyro_rads(self) -> tuple:
        """Rates from plant + constant injected gyro bias."""
        return (self._last_rates[0] + self._gyro_bias[0],
                self._last_rates[1] + self._gyro_bias[1],
                self._last_rates[2] + self._gyro_bias[2])

    def reset(self) -> None:
        self._base.reset()
        self._last_rates = (0.0, 0.0, 0.0)


# ------------------------------------------------------------------
# ADR-0011 §4 — 9-state EKF validation scenario
# ------------------------------------------------------------------

def ekf_validation(*, duration: float = 5.0) -> Scenario:
    """ADR-0011 validation: EKF learns 30 mg accel bias X and 0.02 rad/s gyro bias Y.

    5 s of clean hover at 1 kHz tick rate. The plant reports raw (unbiased) accel
    and gyro; the EKF predict step receives the raw sensor values, and its accel
    update receives zero body-frame linear acceleration (hover, no translation).
    The filter must converge b_a_x toward 30 mg.

    Assertion: |b_a_x − 30 mg| < 5 mg after 5 s (5000 ticks).
    """
    def _plant_factory(dt: float) -> Plant:
        from sim.plant import IdentifiedPlant
        base = IdentifiedPlant.canonical(dt)
        return _EKFValidationPlant(dt, base,
                                   acc_bias_mg=(30.0, 0.0, 0.0),
                                   gyro_bias_rads=(0.0, 0.02, 0.0))

    return Scenario(
        name="ekf_validation",
        axis="pitch",
        duration=duration,
        setpoint=_zero,
        plant_factory=_plant_factory,
        description=(
            "EKF validation: 30 mg accel-bias X, 0.02 rad/s gyro-bias Y, "
            "clean hover 5 s; b_a_x converges to 30 mg within 5 mg"
        ),
    )


class _EKFValidationPlant:
    """Plant that exposes both raw accel/gyro and ground-truth body velocity.

    Exposes ``get_raw_accel``, ``get_raw_gyro``, and ``get_lin_acc_body`` (zero
    in hover) for the EKF predict/accel-update steps.  Velocity is zero because
    the plant runs at rest.
    """

    def __init__(self, dt: float, base: Plant,
                 acc_bias_mg: tuple, gyro_bias_rads: tuple):
        self._base = base
        self._acc_bias = acc_bias_mg
        self._gyro_bias = gyro_bias_rads
        self._last_rates = (0.0, 0.0, 0.0)

    def step(self, u: dict) -> dict:
        out = self._base.step(u)
        self._last_rates = (out.get("p", 0.0), out.get("q", 0.0), out.get("r", 0.0))
        return out

    def get_raw_accel(self) -> tuple:
        """Raw body-frame accel: gravity component + sensor bias (mg)."""
        # Hover: gravity points down in body frame, plus sensor bias
        # g_world_z = 1000 mg in world frame; for flat hover with zero pitch/roll,
        # body frame also sees it as (0, 0, 1000)
        return (self._acc_bias[0],
                self._acc_bias[1],
                1000.0 + self._acc_bias[2])

    def get_raw_gyro(self) -> tuple:
        """Raw gyro: true rates + constant sensor bias (rad/s)."""
        return (self._last_rates[0] + self._gyro_bias[0],
                self._last_rates[1] + self._gyro_bias[1],
                self._last_rates[2] + self._gyro_bias[2])

    def get_lin_acc_body(self) -> tuple:
        """Body-frame linear accel (gravity removed): ~0 in hover."""
        return (0.0, 0.0, 0.0)

    def get_of_vel(self) -> tuple:
        """Ground-truth body velocity: zero at rest."""
        return (0.0, 0.0)

    def get_z_rate(self) -> float:
        """Z-rate (altitude derivative): zero in hover."""
        return 0.0

    def reset(self) -> None:
        self._base.reset()
        self._last_rates = (0.0, 0.0, 0.0)
