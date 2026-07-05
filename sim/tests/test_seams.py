"""Architecture-deepening seams: the Lyapunov drive (#4), the ref_model_type knob
(#2), and the shared canonical-plant source of truth (#3)."""
import pytest

from sim import scenarios
from sim.drive import for_law, scalar_drive, state_space_drive
from sim.plant import CANONICAL_MODELS
from sim.reference_model import ReferenceModel, RefType
from sim.run import run


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
