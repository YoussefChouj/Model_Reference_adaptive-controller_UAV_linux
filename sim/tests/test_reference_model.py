"""TDD slice 2 — sim/reference_model.py.

Pins firmware parity with API/mrac.c:168-196. The reference model is the in-loop
runtime path, NOT the design-time scipy calculator (compute_reference_model.py):
firmware integrates the reference with semi-implicit / forward Euler and uses a
*scalar heuristic* Lyapunov gain P = 1/(2*wn) (2nd order) or 1/(2*bw) (1st), even
though a matrix P exists on paper (ADR-0003). For byte-for-byte parameter parity
the sim must reproduce that exact recurrence and that exact scalar P.

Conventions pinned here:
  * RefType values match the firmware CMD 0x13 enum: 0 passthrough, 1 first, 2 second.
  * step(r) advances xm THEN returns it (mrac.c updates xm before e = x - xm),
    the opposite of plant.step which returns y before the state update.
  * reset(x0) is the bumpless snap: xm = x0, xm_dot = 0 (mrac.c:417-421).
"""
import numpy as np
import pytest

from sim.reference_model import ReferenceModel, RefType

DT = 0.005  # MRAC_DT, 200 Hz


def test_reftype_values_match_firmware_cmd_0x13_enum():
    assert (int(RefType.PASSTHROUGH), int(RefType.FIRST_ORDER),
            int(RefType.SECOND_ORDER)) == (0, 1, 2)


def test_passthrough_is_infinite_bandwidth_and_unit_gain():
    rm = ReferenceModel(RefType.PASSTHROUGH, dt=DT)
    assert rm.step(3.7) == 3.7          # xm = r instantly
    assert rm.xm_dot == 0.0
    assert rm.P == 1.0                  # mrac.c:191
    assert rm.error(5.0) == 5.0 - 3.7   # e = x - xm


def test_first_order_matches_firmware_forward_euler_and_scalar_P():
    bw = 30.0
    rm = ReferenceModel(RefType.FIRST_ORDER, bw=bw, dt=DT)
    assert rm.P == pytest.approx(1.0 / (2.0 * bw))
    rng = np.random.default_rng(0)
    r_seq = rng.standard_normal(300)
    # firmware golden recurrence (mrac.c:178-184)
    xm = 0.0
    for r in r_seq:
        dx = bw * (r - xm)
        xm += DT * dx
        assert rm.step(float(r)) == pytest.approx(xm, rel=0, abs=1e-12)
        assert rm.xm_dot == pytest.approx(dx, rel=0, abs=1e-12)


def test_second_order_matches_firmware_semi_implicit_euler_and_scalar_P():
    wn, zeta = 44.0, 0.8
    rm = ReferenceModel(RefType.SECOND_ORDER, bw=wn, zeta=zeta, dt=DT)
    assert rm.P == pytest.approx(1.0 / (2.0 * wn))   # heuristic scalar, NOT matrix P
    rng = np.random.default_rng(1)
    r_seq = rng.standard_normal(400)
    # firmware golden recurrence (mrac.c:169-176): xm_dot updated first, then xm
    xm, xm_dot = 0.0, 0.0
    for r in r_seq:
        acc = wn * wn * (r - xm) - 2.0 * zeta * wn * xm_dot
        xm_dot += DT * acc
        xm += DT * xm_dot
        assert rm.step(float(r)) == pytest.approx(xm, rel=0, abs=1e-12)
        assert rm.xm_dot == pytest.approx(xm_dot, rel=0, abs=1e-12)


def test_first_and_second_order_track_a_constant_to_unity_dc_gain():
    for rm in (ReferenceModel(RefType.FIRST_ORDER, bw=30.0, dt=DT),
               ReferenceModel(RefType.SECOND_ORDER, bw=44.0, zeta=0.8, dt=DT)):
        for _ in range(4000):  # 20 s, well past settling
            rm.step(2.0)
        assert rm.xm == pytest.approx(2.0, abs=1e-3)
        assert rm.xm_dot == pytest.approx(0.0, abs=1e-3)


def test_reset_is_a_bumpless_snap_to_plant_state():
    rm = ReferenceModel(RefType.SECOND_ORDER, bw=44.0, zeta=0.8, dt=DT)
    for _ in range(50):
        rm.step(1.0)
    rm.reset(x0=0.42)
    assert rm.xm == 0.42 and rm.xm_dot == 0.0


def test_for_axis_factory_uses_firmware_configs():
    # roll/pitch -> 2nd-order bw=44 zeta=0.8; yaw -> 1st-order bw=30 (mrac.c:324-360)
    roll = ReferenceModel.for_axis("roll", dt=DT)
    assert roll.kind is RefType.SECOND_ORDER and roll.bw == 44.0 and roll.zeta == 0.8
    pitch = ReferenceModel.for_axis("pitch", dt=DT)
    assert pitch.kind is RefType.SECOND_ORDER and pitch.bw == 44.0
    yaw = ReferenceModel.for_axis("yaw", dt=DT)
    assert yaw.kind is RefType.FIRST_ORDER and yaw.bw == 30.0
