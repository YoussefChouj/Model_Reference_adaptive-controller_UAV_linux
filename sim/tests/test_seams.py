"""Architecture-deepening seams: the Lyapunov drive (#4), the ref_model_type knob
(#2), and the shared canonical-plant source of truth (#3)."""
import pytest

from sim import scenarios
from sim.drive import for_law, scalar_drive, state_space_drive
from sim.plant import CANONICAL_MODELS
from sim.reference_model import ReferenceModel, RefType
from sim.run import run


def _skip_mujoco_if_unavailable():
    from sim.plant import MujocoPlant
    avail, _ = MujocoPlant.is_available()
    if not avail:
        pytest.skip("MujocoPlant requires mujoco (not installed in this venv)")


# --- #4 Lyapunov drive seam ---

def test_scalar_drive_ignores_derivative_channel():
    # s = e * P only; e_dot/Pe/Pedot must not change it
    s = scalar_drive(PBe=0.3, P=2.0, e_dot=99.0, Pe=5.0, Pedot=7.0)
    assert s == pytest.approx(0.6)


def test_state_space_drive_uses_both_channels():
    s = state_space_drive(PBe=0.3, P=99.0, e_dot=0.2, Pe=2.0, Pedot=5.0)
    assert s == pytest.approx(0.3 * 2.0 + 0.2 * 5.0)


def test_for_law_selects_adapter():
    assert for_law(False) is scalar_drive
    assert for_law(True) is state_space_drive


# --- #2 ref_model_type seam ---

def test_ref_model_type_override_forces_order_on_axis():
    # roll defaults to 2nd order; force passthrough / 1st order
    assert ReferenceModel.for_axis("roll").kind is RefType.SECOND_ORDER
    assert ReferenceModel.for_axis("roll", ref_model_type=0).kind is RefType.PASSTHROUGH
    assert ReferenceModel.for_axis("roll", ref_model_type=1).kind is RefType.FIRST_ORDER


def test_passthrough_keeps_axis_bandwidth():
    # overriding the order must keep the axis' configured bw/zeta
    roll2 = ReferenceModel.for_axis("roll")
    roll0 = ReferenceModel.for_axis("roll", ref_model_type=0)
    assert roll0.bw == roll2.bw and roll0.zeta == roll2.zeta


def test_run_reports_selected_ref_model_type():
    res = run(scenarios.step("roll"), ref_model_type=0, write_artifacts=False)
    assert res["ref_model_type"] == 0
    assert res["metrics"]["stable"]


# --- #3 single canonical-plant source of truth ---

def test_scenarios_share_the_plant_source_of_truth():
    # scenarios._CANON must BE plant.CANONICAL_MODELS, not a copy
    from sim import scenarios as sc
    assert sc._CANON is CANONICAL_MODELS
    assert CANONICAL_MODELS["roll"].K == 165.0


# --- #5 Spec 4a Plant seam widening ---

def test_rigid_body_plant_satisfies_plant_seam():
    """RigidBodyPlant conforms to the Plant interface."""
    from sim.plant import RigidBodyPlant
    p = RigidBodyPlant(dt=0.005)
    state = p.step({"roll": 0.0, "pitch": 0.0, "yaw": 0.0, "z": 12.71})
    assert "p" in state and "q" in state and "r" in state
    p.reset()


def test_seam_swap_identified_for_rigid_body_unchanged_phase1_keys():
    """Swapping plants preserves Phase-1 keys (p, q, r, vz).

    The seam widening is **not** a parallel interface; it is the same
    Plant seam carrying more state. IdentifiedPlant returns {p,q,r};
    RigidBodyPlant returns {p,q,r,...}. The inner rate loop reads
    only the Phase-1 keys and works against either plant unchanged.
    """
    from sim.plant import IdentifiedPlant, RigidBodyPlant
    id_state = IdentifiedPlant.canonical(0.005).step(
        {"roll": 0.0, "pitch": 0.0, "yaw": 0.0})
    rb_state = RigidBodyPlant(dt=0.005).step(
        {"roll": 0.0, "pitch": 0.0, "yaw": 0.0, "z": 12.71})
    assert "p" in id_state and "p" in rb_state
    assert "q" in id_state and "q" in rb_state
    assert "r" in id_state and "r" in rb_state


def test_canonical_airframe_is_measured_values():
    """CANONICAL_AIRFRAME numbers are the final 2026-07-28 campaign."""
    from sim.plant import CANONICAL_AIRFRAME
    af = CANONICAL_AIRFRAME
    assert af.mass == pytest.approx(1.2961, rel=1e-9)
    assert af.Ixx == pytest.approx(0.00839, rel=1e-9)
    assert af.Iyy == pytest.approx(0.00930, rel=1e-9)
    assert af.Izz == pytest.approx(0.01485, rel=1e-9)


# --- #6 Spec 03 MujocoPlant seam (ADR-0012) ---

def test_mujoco_plant_satisfies_plant_seam():
    """MujocoPlant conforms to the Plant interface."""
    _skip_mujoco_if_unavailable()
    from sim.plant import MujocoPlant, Plant
    assert issubclass(MujocoPlant, Plant)
    p = MujocoPlant(dt=0.005)
    try:
        state = p.step({"roll": 0.0, "pitch": 0.0, "yaw": 0.0, "z": 12.71})
        # Phase-1 keys (rate loop contract)
        for k in ("p", "q", "r", "vz"):
            assert k in state, f"MujocoPlant missing Phase-1 key {k!r}"
        # Spec-4a widened keys
        for k in ("x", "y", "z", "phi", "theta", "psi", "thrust", "motors"):
            assert k in state, f"MujocoPlant missing widened key {k!r}"
    finally:
        p.reset()


def test_mujoco_plant_is_in_plant_registry():
    """PLANT_REGISTRY exposes 'mujoco' so callers can build by name."""
    _skip_mujoco_if_unavailable()
    from sim.plant import PLANT_REGISTRY, MujocoPlant, build_plant
    assert "mujoco" in PLANT_REGISTRY
    p = build_plant("mujoco", dt=0.005)
    try:
        assert isinstance(p, MujocoPlant)
    finally:
        p.reset()


def test_mujoco_plant_reset_is_deterministic():
    """Two reset()-then-step() runs produce the same first state."""
    _skip_mujoco_if_unavailable()
    from sim.plant import MujocoPlant
    p = MujocoPlant(dt=0.005)
    p.reset()
    s1 = p.step({"roll": 0.0, "pitch": 0.0, "yaw": 0.0, "z": 12.71})
    p.reset()
    s2 = p.step({"roll": 0.0, "pitch": 0.0, "yaw": 0.0, "z": 12.71})
    for k in ("p", "q", "r", "vz", "z", "phi", "theta", "psi"):
        assert s1[k] == pytest.approx(s2[k], abs=1e-9), (
            f"reset not deterministic on key {k!r}: {s1[k]} vs {s2[k]}")


def test_mujoco_plant_importable_when_bridge_missing():
    """MujocoPlant.is_available() returns (False, reason) when the
    bridge module is not importable. We do NOT need to actually break
    the import — the probe is the contract."""
    from sim.plant import MujocoPlant
    avail, reason = MujocoPlant.is_available()
    assert isinstance(avail, bool)
    assert isinstance(reason, str)
    # On this host, mujoco is installed, so we expect availability.
    if avail:
        p = MujocoPlant(dt=0.005)
        try:
            p.step({"roll": 0.0, "pitch": 0.0, "yaw": 0.0, "z": 12.71})
        finally:
            p.reset()
