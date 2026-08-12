"""Smoke tests for the MujocoPlant seam and render module (prior-03).

These tests cover the seam introduced by spec prior-03:
``MujocoPlant`` extraction, the MJCF asset, and the renderer.

Existing tests in ``test_plant.py`` and ``test_mujoco_bridge.py`` are NOT
duplicated here — they remain the authoritative contract. This module
covers only the new paths introduced by the architectural separation.
"""
from __future__ import annotations

import os

import numpy as np
import pytest

DT = 0.005  # 200 Hz


def _mujoco_available():
    from sim.mujoco_plant import MujocoPlant
    avail, _ = MujocoPlant.is_available()
    return avail


def _skip_if_mujoco_unavailable():
    if not _mujoco_available():
        pytest.skip("MujocoPlant requires mujoco (not installed in this venv)")


# ----------------------------------------------------------------------
# Import paths — backward compat and new module
# ----------------------------------------------------------------------


def test_mujoco_plant_importable_from_plant():
    """``from sim.plant import MujocoPlant`` still works (backward compat)."""
    from sim.plant import MujocoPlant
    assert MujocoPlant is not None


def test_mujoco_plant_importable_from_own_module():
    """``from sim.mujoco_plant import MujocoPlant`` works (new import path)."""
    from sim.mujoco_plant import MujocoPlant
    assert MujocoPlant is not None


def test_mujoco_plant_is_subclass_of_plant():
    """MujocoPlant subclasses Plant (seam contract)."""
    from sim.plant import Plant, MujocoPlant
    assert issubclass(MujocoPlant, Plant)


def test_mujoco_plant_is_available_returns_tuple():
    """is_available() returns (bool, str) regardless of backend presence."""
    from sim.mujoco_plant import MujocoPlant
    avail, reason = MujocoPlant.is_available()
    assert isinstance(avail, bool)
    assert isinstance(reason, str)


def test_mujoco_plant_default_constructor():
    """Default construction (programmatic MJCF) succeeds when mujoco is present."""
    _skip_if_mujoco_unavailable()
    from sim.mujoco_plant import MujocoPlant
    plant = MujocoPlant(dt=DT)
    assert plant.dt == DT
    assert plant.model_xml is None


# ----------------------------------------------------------------------
# File-based MJCF asset
# ----------------------------------------------------------------------


def test_mujoco_plant_loads_jx_fly_xml():
    """MujocoPlant(model_xml="sim/models/jx_fly.xml") loads without error."""
    _skip_if_mujoco_unavailable()
    from sim.mujoco_plant import MujocoPlant
    xml_path = os.path.join(os.path.dirname(__file__), os.pardir,
                             "models", "jx_fly.xml")
    plant = MujocoPlant(dt=DT, model_xml=xml_path)
    assert plant._bridge.model is not None


def test_mujoco_plant_loads_jx_fly_xml_relative():
    """MujocoPlant(model_xml="sim/models/jx_fly.xml") resolves relative to cwd."""
    _skip_if_mujoco_unavailable()
    from sim.mujoco_plant import MujocoPlant
    # The mujoco_bridge resolves relative paths to absolute using os.path.abspath.
    plant = MujocoPlant(dt=DT, model_xml="sim/models/jx_fly.xml")
    assert plant._bridge.model is not None


def test_mujoco_plant_missing_xml_raises_file_not_found():
    """Non-existent model_xml raises FileNotFoundError."""
    _skip_if_mujoco_unavailable()
    from sim.mujoco_plant import MujocoPlant
    with pytest.raises(FileNotFoundError):
        MujocoPlant(dt=DT, model_xml="no/such/file.xml")


# ----------------------------------------------------------------------
# reset() behaviour — warm-start invariant
# ----------------------------------------------------------------------


def test_reset_produces_deterministic_state():
    """reset() → step(hover) → zero-rate, near-origin state."""
    _skip_if_mujoco_unavailable()
    from sim.mujoco_plant import MujocoPlant
    from sim.plant import CANONICAL_AIRFRAME
    T_hover = CANONICAL_AIRFRAME.mass * 9.80665

    plant = MujocoPlant(dt=DT)
    plant.reset()
    s = plant.step({"roll": 0.0, "pitch": 0.0, "yaw": 0.0, "z": T_hover})

    # Body rates should be near zero after one tick at hover.
    assert abs(s["p"]) < 1e-3
    assert abs(s["q"]) < 1e-3
    assert abs(s["r"]) < 1e-3


def test_reset_no_free_fall():
    """After reset, the first N hover steps do not produce large z drift."""
    _skip_if_mujoco_unavailable()
    from sim.mujoco_plant import MujocoPlant
    from sim.plant import CANONICAL_AIRFRAME
    T_hover = CANONICAL_AIRFRAME.mass * 9.80665

    plant = MujocoPlant(dt=DT)
    plant.reset()
    # 50 ticks of hover (~0.25 s); motor LPF should be within 99% of target.
    for _ in range(50):
        s = plant.step({"roll": 0.0, "pitch": 0.0, "yaw": 0.0, "z": T_hover})
    # z should not have drifted more than 0.1 m (MUCHO larger than physical).
    assert abs(s["z"]) < 0.1


def test_reset_is_deterministic():
    """Two reset() + step(hover) sequences produce identical state."""
    _skip_if_mujoco_unavailable()
    from sim.mujoco_plant import MujocoPlant
    from sim.plant import CANONICAL_AIRFRAME
    T_hover = CANONICAL_AIRFRAME.mass * 9.80665

    plant1 = MujocoPlant(dt=DT)
    plant2 = MujocoPlant(dt=DT)
    plant1.reset()
    plant2.reset()
    s1 = plant1.step({"roll": 0.0, "pitch": 0.0, "yaw": 0.0, "z": T_hover})
    s2 = plant2.step({"roll": 0.0, "pitch": 0.0, "yaw": 0.0, "z": T_hover})

    for k in ("p", "q", "r", "z"):
        assert s1[k] == pytest.approx(s2[k], abs=1e-9)


# ----------------------------------------------------------------------
# Plant factory registration
# ----------------------------------------------------------------------


def test_build_plant_mujoco_constructs_mujoco_plant():
    """build_plant("mujoco", dt) returns a MujocoPlant instance."""
    _skip_if_mujoco_unavailable()
    from sim.plant import build_plant, MujocoPlant
    plant = build_plant("mujoco", dt=DT)
    assert isinstance(plant, MujocoPlant)


def test_registry_has_mujoco_key():
    """PLANT_REGISTRY contains "mujoco"."""
    from sim.plant import PLANT_REGISTRY
    assert "mujoco" in PLANT_REGISTRY


# ----------------------------------------------------------------------
# Roll-step smoke (mirrors test_plant.py but uses the new module import)
# ----------------------------------------------------------------------


def test_roll_step_produces_roll_response():
    """A positive roll command produces a positive roll rate (no axis swap)."""
    _skip_if_mujoco_unavailable()
    from sim.mujoco_plant import MujocoPlant
    from sim.plant import CANONICAL_AIRFRAME
    T_hover = CANONICAL_AIRFRAME.mass * 9.80665

    plant = MujocoPlant(dt=DT)
    plant.reset()
    for _ in range(20):  # warm-up ticks
        plant.step({"roll": 0.0, "pitch": 0.0, "yaw": 0.0, "z": T_hover})
    # Apply roll step.
    states = []
    for _ in range(100):
        states.append(plant.step({"roll": 0.02, "pitch": 0.0,
                                   "yaw": 0.0, "z": T_hover}))
    # Roll rate should increase and stay positive.
    assert states[-1]["p"] > states[0]["p"]
    assert states[-1]["p"] > 0.0
    # No cross-coupling into pitch/yaw.
    assert abs(states[-1]["q"]) < 1e-3
    assert abs(states[-1]["r"]) < 1e-3


# ----------------------------------------------------------------------
# State-dict keys (mirrors test_mujoco_bridge.py but via MujocoPlant)
# ----------------------------------------------------------------------


def test_step_state_dict_contains_all_widened_keys():
    """MujocoPlant.step() returns the full widened state dict."""
    _skip_if_mujoco_unavailable()
    from sim.mujoco_plant import MujocoPlant
    from sim.plant import CANONICAL_AIRFRAME
    T_hover = CANONICAL_AIRFRAME.mass * 9.80665

    plant = MujocoPlant(dt=DT)
    plant.reset()
    s = plant.step({"roll": 0.0, "pitch": 0.0, "yaw": 0.0, "z": T_hover})

    for k in ("p", "q", "r", "vz"):
        assert k in s
    for k in ("x", "y", "z", "phi", "theta", "psi",
              "vx", "vy", "vz_body",
              "q0", "q1", "q2", "q3",
              "thrust", "motors",
              "U_roll", "U_pitch", "U_yaw", "U_z"):
        assert k in s, f"missing key {k!r}"


# ----------------------------------------------------------------------
# MJCF model validation — site positions
# ----------------------------------------------------------------------


def test_jx_fly_xml_contains_airframe_body():
    """The MJCF contains a body named 'airframe' (required by MujocoBridge)."""
    _skip_if_mujoco_unavailable()
    import mujoco
    xml_path = os.path.join(os.path.dirname(__file__), os.pardir,
                             "models", "jx_fly.xml")
    model = mujoco.MjModel.from_xml_path(xml_path)
    body_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "airframe")
    assert body_id >= 0, "'airframe' body not found in MJCF"


def test_jx_fly_xml_motor_sites_match_x_frame():
    """Motor site positions match the X-frame arm geometry.

    Sites are ordered M1, M2, M3, M4 at (+r,+r), (-r,+r), (-r,-r), (+r,-r)
    in body frame. arm_length=0.200 m.
    """
    _skip_if_mujoco_unavailable()
    import mujoco
    xml_path = os.path.join(os.path.dirname(__file__), os.pardir,
                             "models", "jx_fly.xml")
    model = mujoco.MjModel.from_xml_path(xml_path)
    airframe_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "airframe")

    expected = [
        ( 0.200,  0.200),  # M1 front-right
        (-0.200,  0.200),  # M2 rear-right
        (-0.200, -0.200),  # M3 rear-left
        ( 0.200, -0.200),  # M4 front-left
    ]
    for i, (ex, ey) in enumerate(expected):
        site_name = f"motor_M{i+1}"
        site_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, site_name)
        assert site_id >= 0, f"Site {site_name!r} not found"
        pos = model.site_pos[site_id]
        assert pos[0] == pytest.approx(ex, abs=1e-6)
        assert pos[1] == pytest.approx(ey, abs=1e-6)
        assert pos[2] == pytest.approx(0.0, abs=1e-6)


# ----------------------------------------------------------------------
# Render seam
# ----------------------------------------------------------------------


def test_renderer_is_available_returns_tuple():
    """render.is_available() returns (bool, str) always."""
    from sim import render
    avail, reason = render.MujocoRenderer.is_available()
    assert isinstance(avail, bool)
    assert isinstance(reason, str)


def test_renderer_smoke_when_available():
    """MujocoRenderer renders one frame without error when available."""
    from sim import render
    avail, _ = render.MujocoRenderer.is_available()
    if not avail:
        pytest.skip("Renderer requires EGL (not available in this environment)")

    from sim.mujoco_plant import MujocoPlant
    from sim.plant import CANONICAL_AIRFRAME
    T_hover = CANONICAL_AIRFRAME.mass * 9.80665

    plant = MujocoPlant(dt=DT)
    plant.reset()
    renderer = render.MujocoRenderer(plant._bridge.model, width=160, height=120)
    plant.step({"roll": 0.0, "pitch": 0.0, "yaw": 0.0, "z": T_hover})
    frame = renderer.render(plant._bridge.data)
    assert frame.shape == (120, 160, 3)
    assert frame.dtype == np.uint8
    renderer.close()
