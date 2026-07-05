"""TDD slice 3a — sim/regressor.py.

Hand-ported from MRAC_GenerateStructuredBasis (API/mrac.c:65-91) under the
active firmware flags USE_STRUCTURED_UNCERTAINTY=1 + INCLUDE_CONTROL_IN_REGRESSOR=1
=> MAX_NUM_BASIS = 6. The 6 terms are:

    Phi[0] = 1                bias
    Phi[1] = x                damping (this axis' body rate)
    Phi[2] = x*tanh(x)        bounded nonlinear drag
    Phi[3] = cross_coupling   pitch/roll only; 0 for yaw & z
    Phi[4] = u_nom            control scaling
    Phi[5] = xm               reference feedforward

Cross terms (mrac.c:445-446, note the firmware's p=pitch/q=roll/r=yaw aliasing):
    pitch axis: cross = roll_rate * yaw_rate
    roll  axis: cross = pitch_rate * yaw_rate
    yaw/z axis: cross = 0

This is the parity linchpin: the golden vector below is restated independently
from the firmware formula, so if mrac.c drifts this test fails loudly.
"""
import math

import numpy as np
import pytest

from sim.regressor import NUM_BASIS, cross_coupling, structured_regressor


def test_basis_length_is_six():
    assert NUM_BASIS == 6
    assert structured_regressor("yaw", x=0.0, u_nom=0.0, xm=0.0).shape == (6,)


def test_bias_damping_drag_terms():
    x = 0.3
    phi = structured_regressor("yaw", x=x, u_nom=0.0, xm=0.0)
    assert phi[0] == 1.0
    assert phi[1] == x
    assert phi[2] == pytest.approx(x * math.tanh(x))


def test_pitch_roll_put_cross_coupling_in_slot3():
    phi = structured_regressor("pitch", x=0.1, u_nom=0.5, xm=0.2, cross=0.07)
    assert phi[3] == 0.07


@pytest.mark.parametrize("axis", ["yaw", "z"])
def test_yaw_and_z_keep_slot3_empty(axis):
    # cross is ignored for yaw/z (u_nom already lives in slot 4) -> no collinear drift
    phi = structured_regressor(axis, x=0.1, u_nom=0.5, xm=0.2, cross=0.07)
    assert phi[3] == 0.0


def test_control_features_in_slots_4_and_5():
    phi = structured_regressor("roll", x=0.1, u_nom=0.5, xm=0.2, cross=0.0)
    assert phi[4] == 0.5   # u_nom
    assert phi[5] == 0.2   # xm


def test_cross_coupling_matches_firmware_products():
    pr, rr, yr = 0.11, 0.22, 0.33  # pitch_rate, roll_rate, yaw_rate
    assert cross_coupling("pitch", pitch_rate=pr, roll_rate=rr, yaw_rate=yr) == pytest.approx(rr * yr)
    assert cross_coupling("roll", pitch_rate=pr, roll_rate=rr, yaw_rate=yr) == pytest.approx(pr * yr)
    assert cross_coupling("yaw", pitch_rate=pr, roll_rate=rr, yaw_rate=yr) == 0.0
    assert cross_coupling("z", pitch_rate=pr, roll_rate=rr, yaw_rate=yr) == 0.0


def test_golden_vector_full_pitch_axis():
    # fully hand-computed independent of the implementation
    x, u_nom, xm = 0.4, -0.6, 0.25
    pitch_rate, roll_rate, yaw_rate = 0.4, 0.5, 0.2
    cross = roll_rate * yaw_rate  # = 0.10 for pitch axis
    phi = structured_regressor(
        "pitch", x=x, u_nom=u_nom, xm=xm,
        cross=cross_coupling("pitch", pitch_rate=pitch_rate,
                             roll_rate=roll_rate, yaw_rate=yaw_rate),
    )
    expected = np.array([1.0, 0.4, 0.4 * math.tanh(0.4), 0.10, -0.6, 0.25])
    np.testing.assert_allclose(phi, expected, rtol=1e-12, atol=1e-15)
