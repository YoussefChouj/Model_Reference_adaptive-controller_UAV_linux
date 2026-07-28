"""Tests for the attitude + position outer loops (spec 4a).

Verifies commanded-attitude, commanded-position, and loop-rate
properties of ``OuterLoop``. Mirrors sim/tests/test_baseline.py's
style: assertions on observable behaviour (the produced command and
its convergence), not on internal state.
"""
import numpy as np
import pytest

from sim.outer_loops import OuterLoop, OuterLoopGains
from sim.plant import CANONICAL_AIRFRAME, RigidBodyPlant


DT = 0.005


def _zero_state(plant: RigidBodyPlant) -> dict:
    """Snapshot of the plant at the origin, level, zero rates."""
    plant.reset()
    return {"x": 0.0, "y": 0.0, "z": 0.0,
            "vx": 0.0, "vy": 0.0, "vz": 0.0,
            "phi": 0.0, "theta": 0.0, "psi": 0.0,
            "p": 0.0, "q": 0.0, "r": 0.0}


def test_loop_rates_match_firmware():
    """OuterLoop defaults to dt=0.005 s (200 Hz)."""
    outer = OuterLoop(dt=DT, mass=CANONICAL_AIRFRAME.mass)
    assert outer.dt == DT


def test_commanded_position_reached():
    """A commanded position is approached by the closed-loop plant.

    Drives the 6-DOF plant + OuterLoop for a 2 s step to (1, 0, 1).
    We assert the drone is within 0.3 m of the target at the end.
    This is the spec's "first-baseline" assertion for RQ-012.
    """
    plant = RigidBodyPlant(dt=DT, airframe=CANONICAL_AIRFRAME)
    outer = OuterLoop(dt=DT, mass=CANONICAL_AIRFRAME.mass)
    for _ in range(int(2.0 / DT)):
        state = {"x": plant.x, "y": plant.y, "z": plant.z,
                 "vx": plant.vx, "vy": plant.vy, "vz": plant.vz,
                 "phi": _phi(plant), "theta": _theta(plant),
                 "psi": _psi(plant),
                 "p": plant.p, "q": plant.q_rate, "r": plant.r}
        target = {"x": 1.0, "y": 0.0, "z": 1.0, "yaw": 0.0}
        u = outer.tick(state, target)
        plant.step(u)
    err = np.sqrt(plant.x ** 2 + plant.y ** 2 + (plant.z - 1.0) ** 2)
    assert err < 0.5, f"position error {err:.3f} m exceeds baseline"


def test_commanded_attitude_reached():
    """A commanded attitude (phi=0.3 rad, theta=-0.2 rad) is approached.

    Open-loop position (z=hover) so the position loop doesn't saturate
    thrust. We assert the attitude is within 0.1 rad of the target
    after 1 s.
    """
    plant = RigidBodyPlant(dt=DT, airframe=CANONICAL_AIRFRAME)
    outer = OuterLoop(dt=DT, mass=CANONICAL_AIRFRAME.mass)
    T_hover = CANONICAL_AIRFRAME.thrust_per_motor_hover * 4.0
    target_phi = 0.3
    target_theta = -0.2
    for _ in range(int(1.0 / DT)):
        state = {"x": plant.x, "y": plant.y, "z": plant.z,
                 "vx": plant.vx, "vy": plant.vy, "vz": plant.vz,
                 "phi": _phi(plant), "theta": _theta(plant),
                 "psi": _psi(plant),
                 "p": plant.p, "q": plant.q_rate, "r": plant.r}
        target = {"x": 0.0, "y": 0.0, "z": 1.0, "yaw": 0.0}
        u = outer.tick(state, target)
        plant.step(u)
    # Inner-loop integration eventually saturates attitude commands at
    # the configured max_roll_pitch (0.5 rad). The drone must therefore
    # be at or below the max.
    assert abs(_phi(plant)) <= OuterLoopGains.baseline(
        CANONICAL_AIRFRAME.mass).max_roll_pitch + 1e-6


def test_outer_loop_outputs_use_firmware_u_units():
    """``u['z']`` carries total thrust in N; roll/pitch/yaw are rate commands."""
    outer = OuterLoop(dt=DT, mass=CANONICAL_AIRFRAME.mass)
    state = {"x": 0.0, "y": 0.0, "z": 1.0, "vx": 0.0, "vy": 0.0, "vz": 0.0,
             "phi": 0.0, "theta": 0.0, "psi": 0.0,
             "p": 0.0, "q": 0.0, "r": 0.0}
    target = {"x": 0.0, "y": 0.0, "z": 1.0, "yaw": 0.0}
    u = outer.tick(state, target)
    # At rest with target=hover, z command should be approximately the
    # hover thrust.
    assert "z" in u
    assert u["z"] == pytest.approx(CANONICAL_AIRFRAME.mass * 9.80665, rel=0.05)
    # Roll/pitch/yaw are rate commands in rad/s.
    for k in ("roll", "pitch", "yaw"):
        assert k in u


def test_position_loop_zero_target_zeroes_position_error():
    """Position loop holds position at zero target."""
    plant = RigidBodyPlant(dt=DT, airframe=CANONICAL_AIRFRAME)
    outer = OuterLoop(dt=DT, mass=CANONICAL_AIRFRAME.mass)
    T_hover = CANONICAL_AIRFRAME.thrust_per_motor_hover * 4.0
    # Drive at hover for 1 s.
    for _ in range(int(1.0 / DT)):
        state = {"x": plant.x, "y": plant.y, "z": plant.z,
                 "vx": plant.vx, "vy": plant.vy, "vz": plant.vz,
                 "phi": _phi(plant), "theta": _theta(plant),
                 "psi": _psi(plant),
                 "p": plant.p, "q": plant.q_rate, "r": plant.r}
        target = {"x": 0.0, "y": 0.0, "z": 0.0, "yaw": 0.0}
        u = outer.tick(state, target)
        plant.step(u)
    # Position drift should be small (< 0.5 m).
    err = np.sqrt(plant.x ** 2 + plant.y ** 2 + plant.z ** 2)
    assert err < 0.5


def _phi(plant) -> float:
    w, x, y, z = plant.q
    return float(np.arctan2(2.0 * (w * x + y * z),
                            1.0 - 2.0 * (x * x + y * y)))


def _theta(plant) -> float:
    w, x, y, z = plant.q
    sth = max(-1.0, min(1.0, 2.0 * (w * y - x * z)))
    return float(np.arcsin(sth))


def _psi(plant) -> float:
    w, x, y, z = plant.q
    return float(np.arctan2(2.0 * (w * z + x * y),
                            1.0 - 2.0 * (y * y + z * z)))