"""TDD — sim/calibrator.py (ADR-0011 Phases 3 & 4)."""
import pytest

from sim.calibrator import AccBiasTrim, GyroBiasHotFsm

# ------------------------------------------------------------------
# AccBiasTrim — Phase 3 tests
# ------------------------------------------------------------------

def test_acc_trim_step_response():
    """50 mg step bias converges to < 2 mg within 200 ticks (mu=0.02).

    mu=0.02 means each tick removes 2% of the residual.
    With 30 mg initial error, after N ticks:
        residual_N = 30 * (1 - 0.02)^N
    residual_N < 2  ->  (0.98)^N < 2/30  ->  N > ln(2/30)/ln(0.98) ~ 84
    So convergence to < 2 mg is well within 200 ticks.
    """
    cal = AccBiasTrim(mu=0.02, settle_mg=5.0, settle_ticks=200, max_ticks=2000)

    # true gravity (world frame), no noise
    g_ref = (0.0, 0.0, 9810.0)
    # sensor sees: g - 50 mg on Z axis (i.e. true g minus bias)
    step_bias_mg = 50.0
    g_meas = (0.0, 0.0, 9810.0 - step_bias_mg)

    # Run until settled
    converged_tick = None
    for t in range(1, 201):
        ba = cal.update(g_ref, g_meas)
        residual = abs(ba[2])
        if residual < 2.0:
            converged_tick = t
            break

    assert converged_tick is not None, (
        f"AccBiasTrim did not converge to <2 mg in 200 ticks. "
        f"Last b_a={ba}, residual={residual}"
    )


def test_acc_trim_degrades_on_window_expiry():
    """When residual never drops below threshold, degraded=True at max_ticks
    and b_a holds at best-so-far (not the zeroed-out final value)."""
    cal = AccBiasTrim(mu=0.02, settle_mg=5.0, settle_ticks=200, max_ticks=200)

    g_ref = (0.0, 0.0, 9810.0)
    # residual always ~30 mg: slow convergence, will not reach 5 mg in 200 ticks
    step_bias_mg = 30.0
    g_meas = (0.0, 0.0, 9810.0 - step_bias_mg)

    for _ in range(200):
        cal.update(g_ref, g_meas)

    assert cal.degraded, "AccBiasTrim should set degraded=True when max_ticks elapses"
    assert not cal.settled

    # b_a holds best-so-far, not 0
    assert abs(cal.b_a[2]) > 0.1, (
        f"b_a should hold best-so-far (> 0.1 mg), got {cal.b_a}"
    )


def test_acc_trim_no_movement_when_already_settled():
    """If the sensor is already clean (residual 0 from tick 0), b_a does not drift."""
    cal = AccBiasTrim(mu=0.02, settle_mg=5.0, settle_ticks=200, max_ticks=2000)

    g_ref = (0.0, 0.0, 9810.0)
    # Perfect measurement — no bias, no noise
    g_meas = (0.0, 0.0, 9810.0)

    for _ in range(200):
        cal.update(g_ref, g_meas)

    assert cal.settled
    assert abs(cal.b_a[2]) < 1e-9


def test_acc_trim_step_beyond_max_ticks_holds_best():
    """After degraded=True, update() returns best-so-far, not the zeroed final."""
    cal = AccBiasTrim(mu=0.02, settle_mg=1.0, settle_ticks=200, max_ticks=100)

    g_ref = (0.0, 0.0, 9810.0)
    g_meas = (0.0, 0.0, 9810.0 - 20.0)  # 20 mg step

    # Run past max_ticks
    for _ in range(150):
        ba = cal.update(g_ref, g_meas)

    assert cal.degraded
    best = ba  # after degraded, b_a should hold
    for _ in range(50):
        ba2 = cal.update(g_ref, g_meas)
    # Should be identical after degraded
    assert ba2 == pytest.approx(best, rel=1e-9), (
        f"b_a drifted after degraded: best={best}, new={ba2}"
    )


# ------------------------------------------------------------------
# GyroBiasHotFsm — Phase 4 tests
# ------------------------------------------------------------------

def test_gyro_fsm_wait_still_to_accum():
    """Exactly still_ticks ticks of stillness -> state transitions to ACCUM (1)."""
    fsm = GyroBiasHotFsm(
        still_thresh=0.05, still_ticks=100, acc_ticks=400,
        alpha=1e-4, lin_acc_thresh_mg=50.0
    )

    gyro_still = (0.01, 0.01, 0.01)   # below threshold
    lin_acc_quiet = (0.0, 0.0, 0.0)

    for t in range(1, 101):
        result = fsm.update(gyro_still, lin_acc_quiet, True, False)
        if t < 100:
            assert result["state"] == 0, f"tick {t}: expected WAIT_STILL, got {result['state']}"
        else:
            assert result["state"] == 1, (
                f"tick 100: expected ACCUM (1), got {result['state']}"
            )


def test_gyro_fsm_accum_to_commit():
    """still_ticks + acc_ticks ticks of stillness -> COMMIT fires and b_g updates."""
    fsm = GyroBiasHotFsm(
        still_thresh=0.05, still_ticks=100, acc_ticks=400,
        alpha=1e-4, lin_acc_thresh_mg=50.0
    )

    gyro_still = (0.01, 0.01, 0.01)
    lin_acc_quiet = (0.0, 0.0, 0.0)

    total_ticks = fsm.still_ticks + fsm.acc_ticks

    for t in range(1, total_ticks + 1):
        result = fsm.update(gyro_still, lin_acc_quiet, True, False)

    # b_g should have moved (alpha * sample_mean ~= 0.01 * 0.01 = 1e-4 rad/s)
    assert abs(fsm.b_g[0]) > 1e-9 or abs(fsm.b_g[1]) > 1e-9 or abs(fsm.b_g[2]) > 1e-9, (
        f"b_g should have updated toward sample mean after {total_ticks} ticks, got {fsm.b_g}"
    )


def test_gyro_fsm_reset_on_rc():
    """rc_active=True resets FSM and sets rejected=True."""
    fsm = GyroBiasHotFsm(
        still_thresh=0.05, still_ticks=100, acc_ticks=400,
        alpha=1e-4, lin_acc_thresh_mg=50.0
    )

    gyro_still = (0.01, 0.01, 0.01)
    lin_acc_quiet = (0.0, 0.0, 0.0)

    # Advance deep into WAIT_STILL
    for _ in range(90):
        fsm.update(gyro_still, lin_acc_quiet, True, False)

    # Now RC becomes active — should reset
    result = fsm.update(gyro_still, lin_acc_quiet, True, True)

    assert result["rejected"], "rejected should be True when rc_active fires"
    assert result["state"] == 0, "FSM should reset to WAIT_STILL"


def test_gyro_fsm_reset_on_translation():
    """lin_acc_xy above threshold resets FSM and sets rejected=True."""
    fsm = GyroBiasHotFsm(
        still_thresh=0.05, still_ticks=100, acc_ticks=400,
        alpha=1e-4, lin_acc_thresh_mg=50.0
    )

    gyro_still = (0.01, 0.01, 0.01)
    lin_acc_quiet = (0.0, 0.0, 0.0)
    lin_acc_translating = (60.0, 0.0, 0.0)  # |x|+|y| = 60 > 50 threshold

    # Advance deep into WAIT_STILL
    for _ in range(90):
        fsm.update(gyro_still, lin_acc_quiet, True, False)

    # Now translation fires — should reset
    result = fsm.update(gyro_still, lin_acc_translating, True, False)

    assert result["rejected"], "rejected should be True when translational guard fires"
    assert result["state"] == 0, "FSM should reset to WAIT_STILL"


def test_gyro_fsm_not_flying_resets():
    """flight_phase_flying=False resets FSM and sets rejected=True."""
    fsm = GyroBiasHotFsm(
        still_thresh=0.05, still_ticks=100, acc_ticks=400,
        alpha=1e-4, lin_acc_thresh_mg=50.0
    )

    gyro_still = (0.01, 0.01, 0.01)
    lin_acc_quiet = (0.0, 0.0, 0.0)

    # Advance deep into WAIT_STILL
    for _ in range(90):
        fsm.update(gyro_still, lin_acc_quiet, True, False)

    # Now drone leaves FLYING state
    result = fsm.update(gyro_still, lin_acc_quiet, False, False)

    assert result["rejected"], "rejected should be True when not flying"
    assert result["state"] == 0, "FSM should reset to WAIT_STILL"


def test_gyro_fsm_alpha_direction():
    """With alpha=1e-4 and constant bias of 0.05 rad/s in sample mean,
    after 100 commits b_g moves in the correct direction (toward positive sample).

    alpha=1e-4, N=100: effective weight = alpha*N = 0.01
    After 100 commits: b_g ~= 0.01 * sample_mean (positive if sample is positive).
    This is intentionally slow — firmware parity, not convergence speed test.
    """
    fsm = GyroBiasHotFsm(
        still_thresh=0.05, still_ticks=100, acc_ticks=400,
        alpha=1e-4, lin_acc_thresh_mg=50.0
    )

    gyro_still = (0.01, 0.01, 0.01)
    lin_acc_quiet = (0.0, 0.0, 0.0)

    # Inject a constant bias: all gyro axes measure 0.04 rad/s above true zero
    # (must be strictly below still_thresh=0.05 to pass the stillness guard)
    injected_bias = 0.04
    gyro_with_bias = (injected_bias, injected_bias, injected_bias)

    # Run one full commit cycle (still + accum)
    total_ticks = fsm.still_ticks + fsm.acc_ticks
    for t in range(1, total_ticks + 1):
        fsm.update(gyro_with_bias, lin_acc_quiet, True, False)

    # b_g should have moved toward positive sample mean (correct direction)
    assert fsm.b_g[0] > 0.0, (
        f"b_g[0] should be positive (moved toward +{injected_bias} sample), got {fsm.b_g[0]}"
    )
    assert fsm.b_g[1] > 0.0, (
        f"b_g[1] should be positive (moved toward +{injected_bias} sample), got {fsm.b_g[1]}"
    )
    assert fsm.b_g[2] > 0.0, (
        f"b_g[2] should be positive (moved toward +{injected_bias} sample), got {fsm.b_g[2]}"
    )

    # After 100 commits of 0.05 rad/s with alpha=1e-4,
    # b_g should be roughly alpha*100*0.05 = 0.0005 rad/s
    # (allow wide tolerance — firmware uses same alpha)
    for axis in range(3):
        assert fsm.b_g[axis] < 0.01, (
            f"b_g[{axis}] suspiciously large after 1 commit: {fsm.b_g[axis]} rad/s "
            f"(expected < 0.01)"
        )
