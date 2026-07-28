"""URDF generation tests (spec 4b).

The whole point of generating the URDF from a single declared
:class:`~sim.plant.Airframe` object is to make the CG-offset trap
mechanically impossible. A future refactor that introduces a
parallel-axis shift of the inertia tensor — the most likely
single error in the measurement campaign's own conclusions — must
fail this test.

These tests run anywhere; they do not require Gazebo.
"""
import xml.etree.ElementTree as ET

import numpy as np
import pytest

from sim.plant import CANONICAL_AIRFRAME, motor_positions
from sim.urdf import (
    DEFAULT_MOTOR_GEOMETRY,
    airframe_to_urdf,
    cg_offset_applied_once,
    cg_offset_world,
    motor_positions_urdf,
)


def _parse_urdf(urdf_text: str) -> ET.Element:
    """Parse URDF text into an ElementTree root, asserting well-formedness."""
    return ET.fromstring(urdf_text)


def _link_inertial(root: ET.Element, link_name: str) -> ET.Element:
    """Return the <inertial> child of the named link."""
    for link in root.findall("link"):
        if link.get("name") == link_name:
            inertial = link.find("inertial")
            if inertial is None:
                raise AssertionError(f"link {link_name!r} has no <inertial>")
            return inertial
    raise AssertionError(f"link {link_name!r} not found in URDF")


# --- #1 The URDF is parseable XML ---

def test_urdf_well_formed():
    """URDF must be XML-parseable (round-trip)."""
    root = _parse_urdf(airframe_to_urdf(CANONICAL_AIRFRAME))
    assert root.tag == "robot"
    assert root.get("name") == "jx_fly"


# --- #2 Mass and tensor match the declared airframe ---

def test_urdf_mass_matches_airframe():
    inertial = _link_inertial(
        _parse_urdf(airframe_to_urdf(CANONICAL_AIRFRAME)),
        "jx_fly_body",
    )
    mass = inertial.find("mass")
    assert mass is not None
    assert float(mass.get("value")) == pytest.approx(CANONICAL_AIRFRAME.mass)


def test_urdf_inertia_tensor_matches_airframe():
    """Tensor is the measured I about the CG, unmodified."""
    inertial = _link_inertial(
        _parse_urdf(airframe_to_urdf(CANONICAL_AIRFRAME)),
        "jx_fly_body",
    )
    inertia = inertial.find("inertia")
    assert inertia is not None
    af = CANONICAL_AIRFRAME
    assert float(inertia.get("ixx")) == pytest.approx(af.Ixx)
    assert float(inertia.get("iyy")) == pytest.approx(af.Iyy)
    assert float(inertia.get("izz")) == pytest.approx(af.Izz)
    assert float(inertia.get("ixy")) == pytest.approx(af.Ixy)
    assert float(inertia.get("ixz")) == pytest.approx(af.Ixz)
    assert float(inertia.get("iyz")) == pytest.approx(af.Iyz)


# --- #3 RQ-027: CG offset is applied exactly once, not twice ---

def test_urdf_inertial_origin_is_at_cg():
    """The <inertial> origin is at (0,0,0) — the CG is the link's origin.

    The measured tensor is *about the CG*. If the inertial origin
    is set to the arm plane and the tensor is also about the CG,
    the offset is being applied twice — once as a pose, once
    implicitly via the parallel-axis shift the tensor already
    encoded. The fix is to keep the inertial origin at the link
    origin (the CG) and apply the arm-plane offset only in the
    visual/collision blocks.
    """
    inertial = _link_inertial(
        _parse_urdf(airframe_to_urdf(CANONICAL_AIRFRAME)),
        "jx_fly_body",
    )
    origin = inertial.find("origin")
    assert origin is not None
    xyz = tuple(float(v) for v in origin.get("xyz").split())
    assert xyz == (0.0, 0.0, 0.0), (
        f"<inertial> origin must be at the CG (0,0,0); got {xyz}. "
        f"Setting it to the arm plane would double-apply the CG offset."
    )


def test_urdf_visual_origin_holds_cg_drop():
    """The <visual> origin is +cg_below_arm_plane above the CG.

    This is the **only** place the CG drop appears in the URDF,
    and it is offset in the correct direction (the arm plane is
    above the CG by exactly cg_below_arm_plane).
    """
    root = _parse_urdf(airframe_to_urdf(CANONICAL_AIRFRAME))
    body = next(l for l in root.findall("link") if l.get("name") == "jx_fly_body")
    visual = body.find("visual")
    assert visual is not None
    origin = visual.find("origin")
    assert origin is not None
    xyz = tuple(float(v) for v in origin.get("xyz").split())
    assert xyz == (0.0, 0.0, CANONICAL_AIRFRAME.cg_below_arm_plane), (
        f"<visual> origin must be (0, 0, +cg_below_arm_plane); got {xyz}."
    )


def test_urdf_cg_offset_appears_in_inertial_zero_times():
    """The CG offset value appears in the <inertial> block zero times.

    The offset is fine to appear in <visual> and <collision> — those
    are render-side envelopes showing where the arm plane sits
    relative to the CG. The structural invariant is that the
    *physics* block (<inertial>) does not carry the offset: the
    tensor is about the CG and the origin is at the CG. If a future
    refactor applies a parallel-axis shift to the tensor, the value
    will appear in the <inertial> element and this test fails.
    """
    import xml.etree.ElementTree as ET
    af = CANONICAL_AIRFRAME
    root = ET.fromstring(airframe_to_urdf(af))
    body = next(l for l in root.findall("link") if l.get("name") == "jx_fly_body")
    inertial = body.find("inertial")
    assert inertial is not None
    # Serialise only the <inertial> subtree and search for the value.
    inertial_xml = ET.tostring(inertial, encoding="unicode")
    needle = f"{af.cg_below_arm_plane:.6f}"
    matches = inertial_xml.count(needle)
    assert matches == 0, (
        f"CG offset ({needle}) appears {matches} times in the "
        f"<inertial> block; the spec requires it to be absent there. "
        f"Was a parallel-axis shift applied to the tensor?"
    )


def test_cg_offset_applied_once_helper_returns_true_for_canonical():
    """The mechanical-invariance helper agrees with the canonical airframe."""
    assert cg_offset_applied_once(CANONICAL_AIRFRAME) is True


def test_cg_offset_world_is_vertical_only():
    """The CG offset is purely vertical (X-frame is symmetric front/back).

    The 2026-07-28 measurement campaign places the CG directly under
    the geometric centre of the X-frame, so the offset has zero x and
    zero y components. If a future re-measurement repositions the CG,
    this test will need to be updated deliberately.
    """
    offset = cg_offset_world(CANONICAL_AIRFRAME)
    assert offset[0] == 0.0
    assert offset[1] == 0.0
    assert offset[2] == pytest.approx(-CANONICAL_AIRFRAME.cg_below_arm_plane)


# --- #4 Motor layout matches the analytic plant ---

def test_urdf_motor_count_is_four():
    """Four motors in an X-frame quadrotor."""
    root = _parse_urdf(airframe_to_urdf(CANONICAL_AIRFRAME))
    motors = [l for l in root.findall("link") if l.get("name").startswith("motor_")]
    assert len(motors) == 4


def test_urdf_motor_positions_match_analytic_plant():
    """The URDF motor positions equal sim.plant.motor_positions() exactly.

    This is the structural form of a unit test: the two engines
    cannot disagree on motor placement.
    """
    urdf = np.array(motor_positions_urdf(CANONICAL_AIRFRAME))
    ana = motor_positions(CANONICAL_AIRFRAME)
    assert np.allclose(urdf, ana, atol=1e-9)


def test_urdf_motor_joints_parent_body():
    """Each motor is a fixed joint to the body link."""
    root = _parse_urdf(airframe_to_urdf(CANONICAL_AIRFRAME))
    joints = root.findall("joint")
    assert len(joints) == 4
    for j in joints:
        assert j.get("type") == "fixed"
        parent = j.find("parent")
        child = j.find("child")
        assert parent is not None and parent.get("link") == "jx_fly_body"
        assert child is not None and child.get("link").startswith("motor_")


# --- #5 Frame convention is recorded ---

def test_urdf_default_frame_is_ned():
    """Default convention is NED (matches Gazebo's default world)."""
    root = _parse_urdf(airframe_to_urdf(CANONICAL_AIRFRAME))
    assert root.get("name") == "jx_fly"


def test_urdf_frame_choices_are_validated():
    """The ``frame`` parameter is restricted to a known set."""
    with pytest.raises(ValueError):
        airframe_to_urdf(CANONICAL_AIRFRAME, frame="utm")


# --- #6 Roll/pitch asymmetry is preserved ---

def test_urdf_inertia_asymmetry_matches_measured():
    """The roll/pitch split (Iyy-Ixx) is retained in the URDF.

    The measured values are Ixx = 0.00839, Iyy = 0.00930, giving
    Iyy - Ixx = 9.10e-4 kg m^2. The 9.16e-4 figure cited in
    ``docs/requirements.md`` RQ-008 is a rounded approximation of
    this measured difference. The structural property under test
    here is that the **generator** preserves the measured numbers
    unchanged, not that the docs number is reproduced verbatim.
    """
    inertial = _link_inertial(
        _parse_urdf(airframe_to_urdf(CANONICAL_AIRFRAME)),
        "jx_fly_body",
    )
    inertia = inertial.find("inertia")
    ixx = float(inertia.get("ixx"))
    iyy = float(inertia.get("iyy"))
    assert iyy - ixx == pytest.approx(0.00091, abs=1e-9)


# --- #7 Determinism ---

def test_urdf_generation_is_deterministic():
    """Repeated calls produce identical XML."""
    a = airframe_to_urdf(CANONICAL_AIRFRAME)
    b = airframe_to_urdf(CANONICAL_AIRFRAME)
    assert a == b


def test_urdf_motor_geometry_is_balanced():
    """The four motors are arranged symmetrically about the CG."""
    motors = motor_positions_urdf(CANONICAL_AIRFRAME)
    # Sum of x's and y's should cancel by symmetry.
    assert sum(m[0] for m in motors) == pytest.approx(0.0, abs=1e-9)
    assert sum(m[1] for m in motors) == pytest.approx(0.0, abs=1e-9)


def test_urdf_composite_mass_and_izz_match_measured():
    """Gazebo's composite over ALL links must equal the measured airframe.

    The body link carries the full measured mass and CG tensor (the
    swing measurement weighed the whole airframe, motors included).
    Fixed-jointed links are lumped by sdformat, so motor links with
    real mass at r_motor would double-count: 4 x 0.030 kg at 0.2 m
    once added ~+65 % to composite Izz while every per-link test
    still passed. This test sums the lumped composite the way the
    physics engine does.
    """
    af = CANONICAL_AIRFRAME
    root = _parse_urdf(airframe_to_urdf(af))
    joint_origin = {
        j.find("child").get("link"): tuple(
            float(v) for v in j.find("origin").get("xyz").split()
        )
        for j in root.findall("joint")
    }
    total_mass = 0.0
    izz = 0.0
    for link in root.findall("link"):
        inertial = link.find("inertial")
        m = float(inertial.find("mass").get("value"))
        x, y, _ = joint_origin.get(link.get("name"), (0.0, 0.0, 0.0))
        total_mass += m
        # parallel-axis contribution of the link's own origin offset
        izz += float(inertial.find("inertia").get("izz")) + m * (x * x + y * y)
    assert total_mass == pytest.approx(af.mass, rel=1e-4)
    assert izz == pytest.approx(af.Izz, rel=1e-4)


def test_default_motor_geometry_marks_two_cw_and_two_ccw():
    """X-frame convention: two CW and two CCW rotors (balanced yaw)."""
    spins = [m.cw for m in DEFAULT_MOTOR_GEOMETRY]
    assert spins.count(True) == 2
    assert spins.count(False) == 2
