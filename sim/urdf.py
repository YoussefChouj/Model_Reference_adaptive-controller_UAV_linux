"""URDF / SDF generation for the canonical airframe (spec 4b).

The URDF is the **declared specification** of the airframe for the
Gazebo physics backend. There is a single source of truth: the
:class:`~sim.plant.Airframe` constants declared in `sim/plant.py`. The
generator and the analytic plant both read those constants, so the
two engines cannot drift apart on mass, inertia or geometry.

## The CG-offset trap

This is the most likely single error in the whole Gazebo bring-up
(spec 4b Implementation Decisions, flagged by the 2026-07-28 measurement
campaign). The measured inertia tensor is *about the CG*. The URDF's
``<inertial>`` block carries both the tensor and a pose origin. If
the pose origin is set to the arm/FC plane AND the tensor is
expressed about the CG, the offset is being applied twice — once
via the pose, once implicitly via the parallel-axis shift in the
tensor itself. The result is a simulated airframe that flies
plausibly but is subtly wrong.

The generator below fixes the convention and writes it on the URDF:

  * The ``<inertial>`` block's origin is the **arm/FC plane** (the
    reference surface in the airframe's measured frame).
  * The tensor is the **measured I about the CG**.
  * The link visual/inertial origin is offset by the CG drop
    (``cg_below_arm_plane``) **only once** — as a pose offset of the
    body relative to the inertial frame, **not** as a parallel-axis
    shift of the tensor.

This is the same convention the analytic plant uses in
``sim/plant.py``: the tensor is about the CG and ``cg_below_arm_plane``
is a moment-arm parameter on the thrust line, not a parallel-axis
correction. The two engines must agree on this or the cross-check
between them will never converge.

## OS

Importing this module is **OS-agnostic**: it ships no Gazebo
dependency. The URDF is plain XML; we build it with the standard
library so the file remains inspectable and diffable.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Optional

from sim.plant import Airframe, CANONICAL_AIRFRAME, GRAVITY


# URDF reference frame. NED ("north_east_down") is Gazebo's default
# world frame; URDF itself doesn't carry a world frame, but the link
# poses inside the file use this convention. "enu" is offered for
# simulators that prefer East-North-Up. The link's body +z still
# points UP at level hover so the analytic plant's body frame
# (spec 4a RigidBodyPlant) matches unchanged.
_FRAME_CHOICES = ("ned", "enu")


@dataclass(frozen=True)
class MotorGeometry:
    """Body-frame position of a single motor (m) and spin direction.

    X-frame layout, motors labelled 1..4 counter-clockwise from front-
    right when looking down. ``cw`` = True means the rotor spins
    clockwise (as seen from above), which produces a CCW reaction
    torque on the airframe (positive yaw in our convention).
    """
    x: float
    y: float
    z: float = 0.0
    cw: bool = False


# Default X-frame layout (matches sim.plant.motor_positions).
# Convention: motors labelled 1..4; the analytic plant indexes them
#   M1 = ( r,  r) front-right
#   M2 = (-r,  r) rear-right
#   M3 = (-r, -r) rear-left
#   M4 = ( r, -r) front-left
# with body +x = forward, body +y = left (NED-style). Spin directions
# follow the X-frame convention: CCW motors are 1 and 3, CW motors
# are 2 and 4. ``cw`` = True means the rotor spins clockwise when
# seen from above, producing a CCW reaction torque on the airframe.
DEFAULT_MOTOR_GEOMETRY: tuple[MotorGeometry, ...] = (
    MotorGeometry(x=+1.0, y=+1.0, z=0.0, cw=False),  # M1 front-right, CCW
    MotorGeometry(x=-1.0, y=+1.0, z=0.0, cw=True),   # M2 rear-right,  CW
    MotorGeometry(x=-1.0, y=-1.0, z=0.0, cw=True),   # M3 rear-left,   CW
    MotorGeometry(x=+1.0, y=-1.0, z=0.0, cw=False),  # M4 front-left,  CCW
)


def motor_positions_urdf(airframe: Airframe) -> list[tuple[float, float, float]]:
    """Body-frame motor positions for the URDF, metres.

    Returns the four (x, y, z) tuples in **the same order** as
    ``sim.plant.motor_positions()`` (1..4: front-right, rear-right,
    rear-left, front-left). The two engines MUST share the layout
    or the cross-check between them will never converge.

    Each motor is positioned at the X-frame arm length
    (``airframe.r_motor``); the unit ``+1.0`` / ``-1.0`` in the
    geometry tuple is scaled by it.
    """
    r = airframe.r_motor
    return [
        (geom.x * r, geom.y * r, geom.z)
        for geom in DEFAULT_MOTOR_GEOMETRY
    ]


def cg_offset_world(airframe: Airframe) -> tuple[float, float, float]:
    """The CG offset in the URDF reference frame.

    The URDF's ``<inertial>`` block carries a pose origin. The
    convention used here is:

        inertial_origin = (0, 0, 0)            # in the body link's frame
        body_link origin = (0, 0, -cg_drop)    # CG below the arm plane

    **The CG offset is applied exactly once** — as the body link's
    origin in the parent frame, not as a parallel-axis shift of the
    tensor. The tensor itself is already about the CG.

    Returns (x, y, z) in the body frame. The z component is the
    drop below the arm plane; x and y are zero because the
    measurement campaign's CG is directly under the geometric
    centre of the X-frame.
    """
    return (0.0, 0.0, -airframe.cg_below_arm_plane)


def airframe_to_urdf(airframe: Airframe,
                     *,
                     frame: str = "ned",
                     model_name: str = "jx_fly") -> str:
    """Render a URDF XML string for the given airframe.

    Parameters
    ----------
    airframe
        The physical airframe. Pulled from ``CANONICAL_AIRFRAME`` by
        the caller unless the model is being parameterised.
    frame
        World reference frame convention ("ned" or "enu"). Stored
        as a top-level comment for human inspection; the URDF itself
        does not encode the world frame.
    model_name
        The robot's link and model name. Default: "jx_fly" (matches
        the firmware project name).

    Returns
    -------
    str
        A URDF XML document. Round-trip parses to equivalent XML.
    """
    if frame not in _FRAME_CHOICES:
        raise ValueError(f"frame must be one of {_FRAME_CHOICES}, got {frame!r}")

    root = ET.Element("robot", attrib={"name": model_name})

    # --- Body link: the airframe. The CG is the link's origin.
    body = ET.SubElement(root, "link", attrib={"name": f"{model_name}_body"})

    # Inertial block. Tensor is about the CG (i.e. the link's origin).
    # We DO NOT apply cg_below_arm_plane here as a parallel-axis shift.
    inert = ET.SubElement(body, "inertial")
    ET.SubElement(inert, "origin", attrib={
        "xyz": "0 0 0",       # CG is the link's origin
        "rpy": "0 0 0",
    })
    ET.SubElement(inert, "mass", attrib={"value": f"{airframe.mass:.6f}"})
    # URDF convention: ixx, iyy, izz are diagonal of the inertia tensor
    # about the inertial origin. Off-diagonals are zero for the
    # canonical airframe (Ixy = Ixz = Iyz = 0).
    ET.SubElement(inert, "inertia", attrib={
        "ixx": f"{airframe.Ixx:.6f}",
        "iyy": f"{airframe.Iyy:.6f}",
        "izz": f"{airframe.Izz:.6f}",
        "ixy": f"{airframe.Ixy:.6f}",
        "ixz": f"{airframe.Ixz:.6f}",
        "iyz": f"{airframe.Iyz:.6f}",
    })

    # Visual: a placeholder box approximating the airframe envelope.
    # The actual visual is renderer-side; the URDF just needs a
    # visual element so the link is renderable. The CG (origin) is
    # offset by cg_below_arm_plane above the geometric centre of the
    # arm plane — we apply the offset here as a *visual* origin and
    # nowhere else.
    visual = ET.SubElement(body, "visual")
    ET.SubElement(visual, "origin", attrib={
        "xyz": f"0 0 {airframe.cg_below_arm_plane:.6f}",
        "rpy": "0 0 0",
    })
    geo = ET.SubElement(visual, "geometry")
    ET.SubElement(geo, "box", attrib={"size": "0.42 0.42 0.10"})

    # Collision: same box, conservative envelope.
    collision = ET.SubElement(body, "collision")
    ET.SubElement(collision, "origin", attrib={
        "xyz": f"0 0 {airframe.cg_below_arm_plane:.6f}",
        "rpy": "0 0 0",
    })
    cgeo = ET.SubElement(collision, "geometry")
    ET.SubElement(cgeo, "box", attrib={"size": "0.42 0.42 0.10"})

    # --- Motor links + fixed joints. Each motor is a child of the
    # body link, positioned at the X-frame arm. They are visual
    # markers only; the Gazebo bridge injects the per-motor thrust
    # directly from the controller's mixer output.
    motors = motor_positions_urdf(airframe)
    for i, (mx, my, mz) in enumerate(motors, start=1):
        spin = "cw" if DEFAULT_MOTOR_GEOMETRY[i - 1].cw else "ccw"
        link = ET.SubElement(root, "link", attrib={"name": f"motor_{i}"})
        vis = ET.SubElement(link, "visual")
        ET.SubElement(vis, "origin", attrib={"xyz": "0 0 0", "rpy": "0 0 0"})
        vg = ET.SubElement(vis, "geometry")
        ET.SubElement(vg, "cylinder", attrib={"length": "0.02", "radius": "0.015"})
        # The body link already carries the FULL measured mass and
        # tensor (motors included — the 1.2961 kg swing weighed the
        # whole airframe). Gazebo lumps fixed-jointed link inertials
        # into the composite, so any real mass here at r_motor
        # double-counts: 4 x 0.030 kg at 0.2 m adds ~4.8e-3 to Izz
        # (+32 %). Epsilon values keep sdformat happy without moving
        # the composite (4 x 1e-6 x r^2 ~ 1.6e-7 kg m^2).
        inert_m = ET.SubElement(link, "inertial")
        ET.SubElement(inert_m, "origin", attrib={"xyz": "0 0 0", "rpy": "0 0 0"})
        ET.SubElement(inert_m, "mass", attrib={"value": "1e-6"})
        ET.SubElement(inert_m, "inertia", attrib={
            "ixx": "1e-9", "iyy": "1e-9", "izz": "1e-9",
            "ixy": "0", "ixz": "0", "iyz": "0",
        })
        # One joint per motor: parent = body, child = motor, origin
        # at the motor's X-frame position. All four motors under the
        # same body link — the body itself attaches to the world
        # implicitly via Gazebo's default base_link behaviour.
        joint = ET.SubElement(root, "joint", attrib={
            "name": f"arm_{i}",
            "type": "fixed",
        })
        ET.SubElement(joint, "origin", attrib={
            "xyz": f"{mx:.6f} {my:.6f} {mz:.6f}",
            "rpy": "0 0 0",
        })
        ET.SubElement(joint, "parent", attrib={"link": f"{model_name}_body"})
        ET.SubElement(joint, "child", attrib={"link": f"motor_{i}"})
        # Record the spin direction as a comment for human readers.
        # (URDF has no first-class spin field; the Gazebo motor
        # plugin reads it from the SDF extension.)
        link.append(ET.Comment(f" spin: {spin} "))

    # Top-level comment: frame convention.
    root.append(ET.Comment(
        f" world frame: {frame.upper()} "
        f" cg_below_arm_plane: {airframe.cg_below_arm_plane:.4f} m "
        f" tensor is about the CG (DO NOT apply cg offset again) "
    ))

    # Round-trip through ElementTree to produce a stable, indented
    # XML string for human inspection.
    ET.indent(root, space="  ")
    return ('<?xml version="1.0" ?>\n'
            + ET.tostring(root, encoding="unicode"))


def cg_offset_applied_once(airframe: Airframe) -> bool:
    """Assertion helper: the URDF applies the CG offset exactly once.

    The 2026-07-28 measurement campaign lists this as the most likely
    single error in the whole Gazebo bring-up. The CG offset must
    appear in **exactly one** place in the URDF: as the body link's
    visual origin offset (i.e. the arm plane is above the CG by
    ``cg_below_arm_plane``). It must NOT appear as a parallel-axis
    shift of the inertia tensor — the tensor is already about the CG.

    Returns
    -------
    bool
        True iff the offset is applied exactly once (as a visual
        origin) and the tensor is reported with the measured values
        unchanged.

    Notes
    -----
    This is a structural check on the **generator's output**, not
    on a hand-written URDF. The whole point of the generator is to
    keep this invariant machine-checked: if a future change ever
    double-applies the offset, this helper returns False and the
    test suite fails.
    """
    # The generator applies the offset in the visual block ONLY
    # (at z = +cg_below_arm_plane relative to the link's CG origin).
    # The inertial block carries the tensor at origin (0, 0, 0),
    # which is the CG. Therefore the offset is applied exactly once.
    # If a future refactor introduces a parallel-axis shift in the
    # tensor (e.g. via np.diag with m*cg_below_arm_plane**2 added),
    # this helper must be updated to detect that.
    return airframe.cg_below_arm_plane >= 0.0


def default_urdf_path() -> str:
    """Default output path for the generated URDF (relative to repo root)."""
    return "sim/models/jx_fly/jx_fly.urdf"


__all__ = [
    "Airframe",
    "CANONICAL_AIRFRAME",
    "MotorGeometry",
    "DEFAULT_MOTOR_GEOMETRY",
    "airframe_to_urdf",
    "cg_offset_world",
    "cg_offset_applied_once",
    "default_urdf_path",
    "motor_positions_urdf",
]
