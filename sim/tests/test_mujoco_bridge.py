"""Unit tests for ``sim.mujoco_bridge`` (ADR-0012 D6/D7).

The bridge is the lowest layer under ``MujocoPlant``. These tests
exercise it in isolation: model loading, free-fall, motor-lag LPF,
the transport-delay buffer (D6), and the state-dict shape.

Mujoco may not be installed in all environments; bridge-construction
tests guard with MujocoBridge.is_available() and skip if absent.
"""
from __future__ import annotations

import numpy as np
import pytest

from sim.mujoco_bridge import (
    MujocoBridge,
    MujocoBridgeConfig,
    _MotorDelayBuffer,
)


def _bridge_available():
    avail, _ = MujocoBridge.is_available()
    return avail


# --- availability ---


def test_bridge_is_available_returns_tuple():
    """is_available() returns (bool, str) on any host."""
    avail, reason = MujocoBridge.is_available()
    assert isinstance(avail, bool)
    assert isinstance(reason, str)


# --- construction (requires mujoco) ---


def test_bridge_loads_mjcf():
    avail, reason = MujocoBridge.is_available()
    if not avail:
        pytest.skip(f"MujocoBridge unavailable: {reason}")
    cfg = MujocoBridgeConfig()
    b = MujocoBridge(cfg)
    assert b.model is not None
    assert b.data is not None


def test_bridge_missing_xml_raises_file_not_found(tmp_path):
    avail, reason = MujocoBridge.is_available()
    if not avail:
        pytest.skip(f"MujocoBridge unavailable: {reason}")
    cfg = MujocoBridgeConfig(model_xml=str(tmp_path / "nope.xml"))
    with pytest.raises(FileNotFoundError):
        MujocoBridge(cfg)


# --- transport-delay buffer (D6) ---


def test_delay_buffer_passthrough_when_N_zero():
    d = _MotorDelayBuffer(T=0.0, dt=0.005)
    assert d.N == 0
    assert d.push(1.0) == 1.0
    assert d.push(2.0) == 2.0


def test_delay_buffer_holds_N_ticks_before_releasing():
    d = _MotorDelayBuffer(T=0.015, dt=0.005)  # N=3
    assert d.N == 3
    assert d.push(1.0) == 0.0  # buffer primed with zeros
    assert d.push(2.0) == 0.0
    assert d.push(3.0) == 0.0
    assert d.push(4.0) == 1.0  # first pushed sample emerges
    assert d.push(5.0) == 2.0
    assert d.push(6.0) == 3.0


def test_delay_buffer_reset_clears_to_zero():
    d = _MotorDelayBuffer(T=0.015, dt=0.005)
    d.push(7.0)
    d.reset()
    for _ in range(d.N):
        assert d.push(99.0) == 0.0


# --- state-dict shape (requires mujoco) ---


def test_state_dict_contains_phase1_and_widened_keys():
    avail, reason = MujocoBridge.is_available()
    if not avail:
        pytest.skip(f"MujocoBridge unavailable: {reason}")
    b = MujocoBridge(MujocoBridgeConfig())
    b.reset()
    s = b.step({"roll": 0.0, "pitch": 0.0, "yaw": 0.0, "z": 12.71})
    for k in ("p", "q", "r", "vz"):
        assert k in s, f"missing Phase-1 key {k!r}"
    for k in ("x", "y", "z", "phi", "theta", "psi",
              "vx", "vy", "vz_body",
              "q0", "q1", "q2", "q3",
              "thrust", "motors",
              "U_roll", "U_pitch", "U_yaw", "U_z"):
        assert k in s, f"missing widened key {k!r}"


def test_state_dict_quaternion_unit_norm():
    avail, reason = MujocoBridge.is_available()
    if not avail:
        pytest.skip(f"MujocoBridge unavailable: {reason}")
    b = MujocoBridge(MujocoBridgeConfig())
    b.reset()
    s = b.step({"roll": 0.1, "pitch": 0.0, "yaw": 0.0, "z": 12.71})
    q = np.array([s["q0"], s["q1"], s["q2"], s["q3"]])
    assert np.linalg.norm(q) == pytest.approx(1.0, abs=1e-9)


# --- physics (requires mujoco) ---


def test_free_fall_velocity_matches_g():
    avail, reason = MujocoBridge.is_available()
    if not avail:
        pytest.skip(f"MujocoBridge unavailable: {reason}")
    b = MujocoBridge(MujocoBridgeConfig())
    b.reset()
    for _ in range(100):  # 0.5 s
        s = b.step({"roll": 0.0, "pitch": 0.0, "yaw": 0.0, "z": 0.0})
    expected_vz = -9.80665 * 0.5
    assert s["vz"] == pytest.approx(expected_vz, rel=1e-3)


def test_motor_lpf_settles_to_target():
    avail, reason = MujocoBridge.is_available()
    if not avail:
        pytest.skip(f"MujocoBridge unavailable: {reason}")
    cfg = MujocoBridgeConfig(motor_tau=0.025)
    b = MujocoBridge(cfg)
    b.reset()
    target = 4.0   # total thrust target, N
    warmup = int(round(10 * cfg.motor_tau / cfg.dt))
    for _ in range(warmup):
        s = b.step({"roll": 0.0, "pitch": 0.0, "yaw": 0.0, "z": target})
    assert s["thrust"] == pytest.approx(target, rel=0.01)


def test_total_thrust_equals_sum_of_motors():
    avail, reason = MujocoBridge.is_available()
    if not avail:
        pytest.skip(f"MujocoBridge unavailable: {reason}")
    b = MujocoBridge(MujocoBridgeConfig())
    b.reset()
    for _ in range(50):
        s = b.step({"roll": 0.05, "pitch": 0.02, "yaw": 0.0, "z": 12.0})
    assert s["thrust"] == pytest.approx(float(np.sum(s["motors"])), abs=1e-9)


# --- reset determinism (requires mujoco) ---


def test_reset_then_step_is_deterministic():
    avail, reason = MujocoBridge.is_available()
    if not avail:
        pytest.skip(f"MujocoBridge unavailable: {reason}")
    b1 = MujocoBridge(MujocoBridgeConfig())
    b1.reset()
    s1 = b1.step({"roll": 0.0, "pitch": 0.0, "yaw": 0.0, "z": 12.71})
    b2 = MujocoBridge(MujocoBridgeConfig())
    b2.reset()
    s2 = b2.step({"roll": 0.0, "pitch": 0.0, "yaw": 0.0, "z": 12.71})
    for k in ("p", "q", "r", "vz", "x", "y", "z", "phi", "theta", "psi"):
        assert s1[k] == pytest.approx(s2[k], abs=1e-9)


def test_plant_is_available_contract_unified():
    """Every concrete ``Plant`` reports ``(bool, str)`` and matches the
    documented contract; ``MujocoPlant`` delegates to ``MujocoBridge``.

    This is the spec-4a contract: a caller holding a polymorphic
    ``Plant`` reference can probe any subclass by name without knowing
    whether the backend is optional. ``MujocoPlant`` skips when the
    mujoco wheel is absent from the venv.
    """
    from sim.plant import IdentifiedPlant, MujocoPlant, Plant, RigidBodyPlant

    # Plant ABC exposes is_available as an abstract static method.
    assert "is_available" in Plant.__abstractmethods__, (
        "Plant.is_available must be an abstract method on the seam"
    )

    # Always-available plants return their documented (True, reason) tuple.
    assert IdentifiedPlant.is_available() == (True, "identified rate-loop model")
    assert RigidBodyPlant.is_available() == (True, "analytic 6-DOF rigid body")

    # Backend-dependent plant delegates to its backend probe.
    bridge_avail, _ = MujocoBridge.is_available()
    if bridge_avail:
        assert MujocoPlant.is_available() == MujocoBridge.is_available()
    else:
        # mujoco missing in this venv — the thin delegate still returns a
        # (bool, str) tuple with the documented unavailable reason.
        avail, reason = MujocoPlant.is_available()
        assert avail is False
        assert isinstance(reason, str) and reason
