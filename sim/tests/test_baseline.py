"""TDD slice 4a -- sim/baseline.py.

PARITY: API/pid.c ComputePID (positional form) + inner-rate gains in Ctrler[].
The golden ticks below are hand-computed straight from pid.c:32-55 so the port is
pinned: conditional integration with the EMin band, per-term clamps, the raw
first-difference derivative, and the final output clamp.
"""
import pytest

from sim.baseline import RatePID, RatePIDConfig


def test_for_axis_gains_match_firmware():
    r = RatePIDConfig.for_axis("roll")
    assert (r.Kp, r.Ki, r.Kd) == (5.0, 0.01, 10.0)
    assert r.mrac_to_mixer == 1170.0
    y = RatePIDConfig.for_axis("yaw")
    assert (y.Kp, y.Ki, y.Kd) == (8.0, 0.001, 0.02)
    assert y.mrac_to_mixer == 1872.0


def test_single_tick_p_and_d_no_integration_outside_emin():
    # EMin=2: |E| must be < 2 to integrate. E=10 -> no integration this tick.
    cfg = RatePIDConfig.for_axis("roll")
    pid = RatePID(cfg)
    U = pid.step(des=10.0, fb=0.0)            # E = 10
    # Up = 5*10 = 50, Ud = 10*(10-0) = 100 (clamped to UdMax=100), Ui = 0
    assert pid.Up == pytest.approx(50.0)
    assert pid.Ud == pytest.approx(100.0)
    assert pid.Ui == 0.0
    assert U == pytest.approx(150.0)
    assert pid.SumE == 0.0


def test_integration_only_within_emin_band():
    cfg = RatePIDConfig.for_axis("roll")
    pid = RatePID(cfg)
    pid.step(des=1.0, fb=0.0)                 # E=1 < EMin=2 -> integrates
    assert pid.SumE == pytest.approx(1.0)
    assert pid.Ui == pytest.approx(0.01)      # Ki*SumE = 0.01*1


def test_output_clamped_to_umax():
    cfg = RatePIDConfig.for_axis("roll")
    pid = RatePID(cfg)
    U = pid.step(des=1000.0, fb=0.0)          # huge error
    assert U == cfg.UMax == 300.0


def test_u_nom_divides_by_mrac_to_mixer():
    cfg = RatePIDConfig.for_axis("roll")
    pid = RatePID(cfg)
    pid.step(des=1000.0, fb=0.0)              # saturates U at 300
    assert pid.u_nom() == pytest.approx(300.0 / 1170.0)


def test_derivative_uses_previous_error():
    cfg = RatePIDConfig.for_axis("roll")
    pid = RatePID(cfg)
    pid.step(des=1.0, fb=0.0)                 # E=1, PreE becomes 1
    pid.step(des=1.0, fb=0.0)                 # E=1 again -> dE=0 -> Ud=0
    assert pid.Ud == pytest.approx(0.0)


def test_reset_clears_state():
    pid = RatePID(RatePIDConfig.for_axis("roll"))
    pid.step(des=1.0, fb=0.0)
    pid.reset()
    assert pid.SumE == 0.0 and pid.PreE == 0.0 and pid.U == 0.0
