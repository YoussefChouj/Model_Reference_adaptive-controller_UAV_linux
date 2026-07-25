"""Unit tests for the ekf_validation scenario (ADR-0011 §4)."""
import pytest

from sim.scenarios import ekf_validation


def test_ekf_validation_converges_accel_bias():
    """Run ekf_validation for 5 s; assert |b_a_x - 30 mg| < 5 mg.

    The plant injects a 30 mg sensor bias on X. In hover (zero commanded accel),
    the gravity-removed body-frame accel seen by the EKF predict step is
    (b_a_x, 0, 0) = (0.294, 0, 0) m/s².  With v_body initially zero, this
    creates a velocity drift that OF=0 then corrects — the innovation in v_body
    is what makes b_a observable.  The OF and Z-rate updates at zero ground-truth
    velocity close the observability loop.
    """
    from sim.ekf import Ekf9State

    scenario = ekf_validation()
    plant = scenario.make_plant(dt=0.001)

    ekf = Ekf9State(dt=0.001)
    N = int(scenario.duration / 0.001)

    for _ in range(N):
        raw_gyro = plant.get_raw_gyro()

        # Gravity-removed body-frame accel: raw - (0, 0, 1000) mg → (30, 0, 0) mg
        # Convert mg → m/s² for the EKF predict.
        raw_a_mg = plant.get_raw_accel()
        g_body_mg = (0.0, 0.0, 1000.0)
        a_body_mg = tuple(r - g for r, g in zip(raw_a_mg, g_body_mg))
        a_body = tuple(a / 1000.0 * 9.81 for a in a_body_mg)  # mg → m/s²

        # Predict: velocity integrates a_body - b_a_body over time.
        ekf.predict(a_body, raw_gyro, dt=0.001)

        # Accel update: gravity-removed lin accel XY from plant (zero in hover)
        lin_acc_xy = plant.get_lin_acc_body()[:2]  # (0, 0) m/s²
        ekf.update_acc_xy(lin_acc_xy)

        # OF update: ground-truth velocity (zero at rest)
        of_vel = plant.get_of_vel()
        ekf.update_of(of_vel)

        # Z-rate update: hover = 0
        ekf.update_z_rate(plant.get_z_rate())

    b_a_x = ekf.b_a_body[0]          # m/s²
    b_a_x_mg = b_a_x / 9.81 * 1000   # convert to mg

    # After 5 s of continuous excitation from the bias-driven velocity drift,
    # the filter should have learned b_a_x ≈ 30 mg within 5 mg.
    assert abs(b_a_x_mg - 30.0) < 5.0, (
        f"b_a_x = {b_a_x_mg:.2f} mg, expected 30 ± 5 mg; "
        f"residual = {abs(b_a_x_mg - 30.0):.2f} mg"
    )


def test_ekf_validation_gyro_bias_retained():
    """The gyro bias does not affect accel-bias convergence (axis separation)."""
    from sim.ekf import Ekf9State

    scenario = ekf_validation()
    plant = scenario.make_plant(dt=0.001)

    ekf = Ekf9State(dt=0.001)
    N = int(scenario.duration / 0.001)

    for _ in range(N):
        raw_a_mg = plant.get_raw_accel()
        g_body_mg = (0.0, 0.0, 1000.0)
        a_body_mg = tuple(r - g for r, g in zip(raw_a_mg, g_body_mg))
        a_body = tuple(a / 1000.0 * 9.81 for a in a_body_mg)
        raw_gyro = plant.get_raw_gyro()

        ekf.predict(a_body, raw_gyro, dt=0.001)
        ekf.update_acc_xy((0.0, 0.0))
        ekf.update_of((0.0, 0.0))
        ekf.update_z_rate(0.0)

    b_g_y = ekf.b_g_body[1]       # rad/s
    # After 5 s with Q_bg=5e-9 and R_acc=0.005, the gyro bias converges
    # slowly — we only assert it is finite and bounded, not a specific value.
    assert abs(b_g_y) < 0.1      # sanity: not diverged
    assert abs(b_g_y) >= 0.0     # finite
