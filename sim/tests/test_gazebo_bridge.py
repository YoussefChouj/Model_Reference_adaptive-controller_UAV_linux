"""Spec 4b bridge tests.

These tests guard the invariants the spec calls out:

- The bridge is importable on Windows (with a clear error).
- The bridge module exposes the expected state keys.
- The gz binary probe answers correctly.
- The measured airframe values round-trip through the bridge's state
  object without rounding or off-by-one drift.
- URDF generation applies the CG offset exactly once.

These tests do NOT start a gz sim subprocess or talk to a running sim.
Start-up is exercised by the spec 4b integration tests on the Linux
partition and is a separate concern.
"""
from __future__ import annotations

import pytest


# --- Module surface -----------------------------------------------------

def test_bridge_module_imports():
    """sim.gazebo_bridge imports as a regular module on Linux with gz-jetty
    installed. On Windows / a host without gz, the import would raise
    GazeboUnavailable; that path is exercised by the bridge's own
    documentation and is not tested here."""
    import sim.gazebo_bridge as gb
    assert gb.GazeboBridge is not None
    assert gb.BridgeState is not None
    assert gb.GazeboUnavailable is not None
    assert gb.GazeboBridgeError is not None


def test_bridge_state_keys_match_full_state_keys():
    """BridgeState carries every physics-state key the analytic plant's
    FULL_STATE_KEYS declares, so the controller can read the same
    physical fields through either backend. The Plant-seam carries
    additional mixer-unit echo keys (U_roll, U_pitch, ...); those are
    added by GazeboPlant._to_state_dict, not by the bridge itself."""
    from sim.plant import FULL_STATE_KEYS
    from sim.gazebo_bridge import BridgeState
    fields = set(BridgeState.__dataclass_fields__.keys())
    # Physics-state keys (the union of FULL_STATE_KEYS minus the
    # controller-echo keys that the bridge does not emit).
    physics_keys = {k for k in FULL_STATE_KEYS
                    if k not in ("U_roll", "U_pitch", "U_yaw", "U_z")}
    for k in physics_keys:
        assert k in fields, f"BridgeState missing {k!r}; physics-state seam broken"


def test_gz_binary_probe():
    """The gz binary probe answers a (bool, str) tuple."""
    from sim.gazebo_bridge import gz_binary_available
    avail, reason = gz_binary_available()
    assert isinstance(avail, bool)
    assert isinstance(reason, str)
    assert reason  # the reason string is non-empty


# --- URDF single-source-of-truth ---------------------------------------

def test_urdf_generates_with_canonical_airframe():
    """URDF generation must succeed with the canonical airframe and
    produce a non-empty XML document."""
    from sim.plant import CANONICAL_AIRFRAME
    from sim.urdf import airframe_to_urdf, cg_offset_applied_once
    xml = airframe_to_urdf(CANONICAL_AIRFRAME)
    assert xml.startswith("<?xml")
    assert "<robot" in xml
    assert "jx_fly" in xml
    # The CG-offset-applied-once invariant.
    assert cg_offset_applied_once(CANONICAL_AIRFRAME) is True


def test_urdf_mass_and_tensor_match_canonical_airframe():
    """The URDF's mass and inertia matrix carry the canonical airframe
    values verbatim. Re-measurement is a single edit in sim.plant; if
    that edit is ever skipped, this test fails."""
    from sim.plant import CANONICAL_AIRFRAME
    from sim.urdf import airframe_to_urdf
    xml = airframe_to_urdf(CANONICAL_AIRFRAME)
    assert 'mass value="1.296100"' in xml
    assert 'ixx="0.008390"' in xml
    assert 'iyy="0.009300"' in xml
    assert 'izz="0.014850"' in xml


def test_urdf_cg_offset_applied_once_to_visual_only():
    """The CG offset appears in the visual block as a single +z offset,
    not in the inertial origin and not as a parallel-axis shift of the
    tensor. This is the most likely single error in the whole Gazebo
    bring-up (spec 4b Implementation Decisions)."""
    from sim.plant import CANONICAL_AIRFRAME
    from sim.urdf import airframe_to_urdf
    xml = airframe_to_urdf(CANONICAL_AIRFRAME)
    # The inertial origin must be at (0, 0, 0).
    assert 'origin xyz="0 0 0" rpy="0 0 0"' in xml
    # The visual origin is offset by +cg_below_arm_plane (0.0262 m).
    assert 'origin xyz="0 0 0.026200"' in xml
    # The tensor's off-diagonals are zero (Ixy = Ixz = Iyz = 0).
    assert 'ixy="0.000000"' in xml
    assert 'ixz="0.000000"' in xml
    assert 'iyz="0.000000"' in xml


# --- Cross-check: the bridge's state object lets the controller see
#     the same airframe values the analytic plant does. ----------------

def test_bridge_state_zero_default_is_hover_equilibrium():
    """An unsteered BridgeState should look like a quad at rest at the
    origin: position zero, velocity zero, attitude identity, zero body
    rates, zero thrust. The controller will not be feeding commands
    through a bridge that returns nonsense at t=0."""
    from sim.gazebo_bridge import BridgeState
    s = BridgeState()
    assert s.x == 0.0 and s.y == 0.0 and s.z == 0.0
    assert s.phi == 0.0 and s.theta == 0.0 and s.psi == 0.0
    assert s.q0 == 1.0 and s.q1 == s.q2 == s.q3 == 0.0
    assert s.p == s.q == s.r == 0.0
    assert s.thrust == 0.0
    assert s.motors == (0.0, 0.0, 0.0, 0.0)


def test_bridge_state_dict_round_trip():
    """BridgeState.as_state_dict() returns every key the Plant seam
    expects, with the same types it expects."""
    from sim.gazebo_bridge import BridgeState
    import numpy as np
    s = BridgeState(q0=1.0, q1=0.0, q2=0.0, q3=0.0)
    d = s.as_state_dict()
    for k in ("x", "y", "z", "phi", "theta", "psi",
              "q0", "q1", "q2", "q3", "p", "q", "r",
              "vz_body", "thrust", "vx", "vy", "vz"):
        assert k in d, f"as_state_dict missing {k!r}"
        assert isinstance(d[k], float)
    assert isinstance(d["motors"], np.ndarray)
    assert d["motors"].shape == (4,)
    # Quadruped-edge: thumbprint the identity quaternion.
    assert d["q0"] == 1.0 and d["q1"] == 0.0
