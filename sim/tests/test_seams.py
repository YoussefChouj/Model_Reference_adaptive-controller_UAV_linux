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


# --- #6 Spec 4b GazeboPlant seam: importable on Windows, helpful probe ---

def test_gazebo_plant_satisfies_plant_seam():
    """GazeboPlant is a Plant subclass (conformance)."""
    from sim.plant import GazeboPlant, Plant
    assert issubclass(GazeboPlant, Plant)
    # The seam declares step(u_dict) -> state_dict and reset().
    assert callable(GazeboPlant.step)
    assert callable(GazeboPlant.reset)


def test_gazebo_plant_importable_on_windows():
    """Importing sim.plant succeeds on Windows (spec 4b bridge constraint).

    The bridge to Gazebo is a separate module; sim.plant itself must
    never fail to import on Windows because Gazebo is not installed.
    """
    import sim.plant  # noqa: F401
    from sim.plant import GazeboPlant
    # Probe must be callable; it does not raise on either OS.
    avail, reason = GazeboPlant.is_available()
    assert isinstance(avail, bool)
    assert isinstance(reason, str)


def test_gazebo_plant_probe_reports_windows_when_absent():
    """On Windows with no Gazebo, the probe returns (False, reason)."""
    import platform
    from sim.plant import GazeboPlant
    avail, reason = GazeboPlant.is_available()
    if platform.system() == "Windows":
        assert avail is False
        assert "Linux" in reason or "Linux partition" in reason
    else:
        # On Linux, the probe may pass or fail depending on the
        # install — we only assert that it returns a tuple of the
        # right shape.
        assert isinstance(avail, bool)
        assert reason


def test_gazebo_plant_step_message_mentions_linux_partition():
    """GazeboPlant.step raises with a message that names the spec when
    the simulator is unavailable. On Linux with gz-jetty installed, the
    probe returns available=True and step() instead tries to start the
    bridge -- this test guards the unavailable path's message clarity,
    not the bridge path (which is exercised by the spec 4b integration
    tests on the Linux partition)."""
    from sim.plant import GazeboPlant
    avail, _ = GazeboPlant.is_available()
    if avail:
        # On a Linux box with gz-jetty installed, step() takes the
        # bridge path; the bridge-startup error is the equivalent of
        # the unavailable path's message. Skip the message check.
        pytest.skip("Gazebo is available on this host; the bridge path "
                    "is exercised by spec 4b integration tests.")
    with pytest.raises(NotImplementedError) as exc_info:
        GazeboPlant().step({"roll": 0.0, "pitch": 0.0, "yaw": 0.0, "z": 12.71})
    msg = str(exc_info.value)
    assert "spec 4b" in msg
    assert "Linux" in msg or "is_available" in msg


def test_gazebo_plant_reset_message_mentions_linux_partition():
    """GazeboPlant.reset raises with a message that names the spec when
    the simulator is unavailable. See the matching step() test for the
    reason the unavailable-path assertion is gated."""
    from sim.plant import GazeboPlant
    avail, _ = GazeboPlant.is_available()
    if avail:
        pytest.skip("Gazebo is available on this host; the bridge path "
                    "is exercised by spec 4b integration tests.")
    with pytest.raises(NotImplementedError) as exc_info:
        GazeboPlant().reset()
    msg = str(exc_info.value)
    assert "spec 4b" in msg


def test_sim_plant_does_not_pull_gazebo_at_import_time():
    """Importing sim.plant must not load gazebo (Windows must succeed).

    The Gazebo bridge is a separate optional module. If a future
    refactor ever moves the import into sim.plant, this test fails
    on any host without gazebo installed.

    The test is anchored to **gazebo-specific** module names so
    stdlib modules whose names happen to start with ``gz`` (notably
    ``gzip``, which ``xml.etree.ElementTree`` pulls in) do not
    trigger a false positive.
    """
    import sys
    for mod in list(sys.modules):
        if mod.startswith("sim.gazebo") or mod == "sim.plant":
            sys.modules.pop(mod, None)
    import sim.plant  # noqa: F401
    gazebo_mods = [
        m for m in sys.modules
        if m == "gazebo" or m.startswith("gazebo.")
        or m == "gz" or m.startswith("gz.")
        or m == "sdformat" or m.startswith("sdformat.")
    ]
    assert gazebo_mods == [], (
        f"sim.plant transitively pulled {gazebo_mods}; the Gazebo "
        f"bridge must remain a separate optional import."
    )
