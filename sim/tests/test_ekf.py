"""Unit tests for sim/ekf.py."""
import pytest
import numpy as np

from sim.ekf import Ekf9State


def test_ekf_init_zero_state():
    ekf = Ekf9State()
    assert ekf.v_body == (0.0, 0.0, 0.0)
    assert ekf.b_a_body == (0.0, 0.0, 0.0)
    assert ekf.b_g_body == (0.0, 0.0, 0.0)
    # P starts small (equal to Q diagonal)
    p = ekf.p_diag
    assert p[0] == pytest.approx(1e-3)
    assert p[3] == pytest.approx(1e-6)
    assert p[6] == pytest.approx(5e-9)
    assert ekf.nis == 0.0


def test_ekf_predict_constant_velocity():
    ekf = Ekf9State()
    # Zero accel and gyro, 100 ticks
    for _ in range(100):
        ekf.predict((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), dt=0.001)
    # v_body should still be ~0
    assert ekf.v_body == pytest.approx((0.0, 0.0, 0.0), abs=1e-12)
    # P_v grows slightly (process noise)
    p_vx = ekf.p_diag[0]
    assert p_vx > 1e-3
    assert p_vx < 1e-1  # but not wildly large


def test_ekf_predict_with_accel_integration():
    ekf = Ekf9State()
    # Constant 1 m/s² acceleration on X, no bias
    accel = (1.0, 0.0, 0.0)
    for _ in range(1000):
        ekf.predict(accel, (0.0, 0.0, 0.0), dt=0.001)
    # v_body ~ a * dt * N = 1 * 0.001 * 1000 = 1 m/s
    assert ekf.v_body[0] == pytest.approx(1.0, rel=1e-3)
    assert abs(ekf.v_body[1]) < 1e-6
    assert abs(ekf.v_body[2]) < 1e-6


def test_ekf_predict_with_bias_removal():
    ekf = Ekf9State()
    # 1 m/s² accel on X, but 0.5 m/s² bias on b_a_x — net = 0.5 m/s²
    ekf.x[3] = 0.5  # inject bias into state
    accel = (1.0, 0.0, 0.0)
    for _ in range(1000):
        ekf.predict(accel, (0.0, 0.0, 0.0), dt=0.001)
    # v_body ~ (1 - 0.5) * 0.001 * 1000 = 0.5 m/s
    assert ekf.v_body[0] == pytest.approx(0.5, rel=1e-3)


def test_ekf_update_of_pulls_velocity_to_measurement():
    ekf = Ekf9State()
    # Zero velocity state, OF reports 1 m/s on X
    ekf.update_of((1.0, 0.0))
    # v_body should be pulled toward 1
    assert ekf.v_body[0] > 0.0
    assert ekf.v_body[0] < 1.0  # partially corrected (measurement weight + prior)
    assert abs(ekf.v_body[1]) < 1e-6


def test_ekf_update_of_both_axes():
    ekf = Ekf9State()
    ekf.update_of((0.5, -0.3))
    assert ekf.v_body[0] > 0.0
    assert ekf.v_body[1] < 0.0


def test_ekf_update_acc_xy_zero_when_still():
    ekf = Ekf9State()
    # Plant is still: lin_acc = (0, 0)
    ekf.update_acc_xy((0.0, 0.0))
    # v_body and b_a should stay ~0
    assert ekf.v_body[0] == pytest.approx(0.0, abs=1e-9)
    assert ekf.v_body[1] == pytest.approx(0.0, abs=1e-9)
    assert ekf.b_a_body[0] == pytest.approx(0.0, abs=1e-9)
    assert ekf.b_a_body[1] == pytest.approx(0.0, abs=1e-9)


def test_ekf_bias_convergence_static():
    ekf = Ekf9State()
    # Inject a 30 mg = 0.294 m/s² bias on X in the predict step
    # Run predict + accel update for 1000 ticks
    # With lin_acc = (0, 0) measurement, the filter should learn b_a_x
    for _ in range(1000):
        # The accelerometer reports 0.294 m/s² while the vehicle is genuinely stationary,
        # so all of it is bias. z=(0,0) is a zero-velocity update (ZUPT) — a VELOCITY of
        # zero, not an acceleration. That is the only valid use of update_acc_xy; passing
        # a real lin_acc there is a unit error (see its docstring). The filter keeps
        # v_body pinned at 0 and therefore attributes the whole 0.294 to b_a.
        ekf.predict((0.294, 0.0, 0.0), (0.0, 0.0, 0.0), dt=0.001)
        ekf.update_acc_xy((0.0, 0.0))
    # After convergence, b_a_x should track ~0.294 m/s²
    b_a_x = ekf.b_a_body[0]
    assert abs(b_a_x - 0.294) < 0.05  # within 5 mg (0.049 m/s²)


def test_ekf_update_z_rate():
    ekf = Ekf9State()
    ekf.update_z_rate(0.5)
    assert ekf.v_body[2] > 0.0
    assert ekf.v_body[2] < 0.5


def test_ekf_nis_finite():
    ekf = Ekf9State()
    ekf.predict((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
    ekf.update_of((0.1, -0.1))
    assert np.isfinite(ekf.nis)
    assert ekf.nis >= 0.0

    ekf.update_acc_xy((0.05, -0.05))
    assert np.isfinite(ekf.nis)

    ekf.update_z_rate(0.2)
    assert np.isfinite(ekf.nis)


def test_ekf_p_symmetric():
    ekf = Ekf9State()
    for _ in range(200):
        ekf.predict((0.1, -0.05, 0.02), (0.01, -0.01, 0.005), dt=0.001)
        ekf.update_of((0.08, -0.04))
        ekf.update_acc_xy((0.05, -0.02))
        ekf.update_z_rate(0.01)
    P = ekf.P
    # Diagonal positive
    assert np.all(np.diag(P) > 0)
    # Symmetric
    assert np.allclose(P, P.T, atol=1e-12)


def test_ekf_p_diagonal_stays_positive():
    ekf = Ekf9State()
    for _ in range(50):
        ekf.predict((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
        ekf.update_of((0.0, 0.0))
        ekf.update_z_rate(0.0)
    p = ekf.p_diag
    assert all(v > 0 for v in p)


def test_ekf_kalman_gain_exposed():
    ekf = Ekf9State()
    ekf.update_of((1.0, 0.5))
    k = ekf.kalman_gain
    assert len(k) == 3
    assert all(isinstance(v, float) for v in k)


def test_ekf_nis_resets_on_predict():
    ekf = Ekf9State()
    ekf.update_of((1.0, 0.0))
    assert ekf.nis > 0
    ekf.predict((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
    assert ekf.nis == 0.0


def test_ekf_custom_q_r():
    ekf = Ekf9State(q_v=1e-2, q_ba=1e-5, q_bg=1e-8,
                     r_of=1e-3, r_acc=1e-2, r_z=1e-1)
    assert ekf.p_diag[0] == pytest.approx(1e-2)
    assert ekf.p_diag[3] == pytest.approx(1e-5)
    assert ekf.p_diag[6] == pytest.approx(1e-8)


def test_ekf_predict_dt_override():
    ekf = Ekf9State(dt=0.001)
    ekf.predict((1.0, 0.0, 0.0), (0.0, 0.0, 0.0), dt=0.01)
    # With dt=0.01, one tick at 1 m/s² gives 0.01 m/s
    assert ekf.v_body[0] == pytest.approx(0.01, rel=1e-3)
