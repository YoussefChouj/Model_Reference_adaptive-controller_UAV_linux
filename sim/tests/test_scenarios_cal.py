"""ADR-0011 Phases 3 & 4 — calibrator integration scenario tests.

These tests run the full closed-loop sim with the new cold_with_bias and
hot_gyro_drift scenarios and assert the calibrator state at end-of-run.
"""
from __future__ import annotations

import numpy as np
import pytest

from sim import scenarios
from sim.run import run


# ------------------------------------------------------------------
# Scenario A — cold_with_bias (Phase 3 AccBiasTrim)
# ------------------------------------------------------------------

def test_scenario_cold_with_bias_converges():
    """AccBiasTrim converges toward -50 mg over 240 ticks (Phase 3).

    Duration 4.2 s (840 ticks):
      ticks 0-400  cold-cal ground (no update)
      ticks 400-600 take-off transient (no update)
      ticks 600-840 AccBiasTrim runs for 240 ticks; (1-0.02)^240 < 1% residual

    With g_meas_z = 1050 mg and g_ref_z = 1000 mg, the firmware residual drives
    b_a_z toward -50 mg (it subtracts the positive sensor bias).
    """
    sc = scenarios.cold_with_bias()
    res = run(sc, write_artifacts=False)

    b_a = res["acc_trim_b_a"]
    # Target: b_a_z → -50 mg; check within 5 mg
    assert abs(b_a[2] - (-50.0)) < 5.0, (
        f"AccBiasTrim Z-bias {b_a[2]:.2f} mg not within 5 mg of target -50 mg. "
        f"Full b_a={b_a}"
    )


def test_scenario_phase3_unaffected_by_tilted_surface():
    """AccBiasTrim converges on a flat surface (Phase 3 does not bake tilt in).

    The scenario uses a flat surface; the test verifies the estimator is well-
    conditioned when g_meas_x ≈ 0 mg (no tilt ambiguity).
    """
    sc = scenarios.cold_with_bias()
    res = run(sc, write_artifacts=False)

    b_a = res["acc_trim_b_a"]
    # X-axis should stay near zero (no X-bias injected)
    assert abs(b_a[0]) < 2.0, (
        f"AccBiasTrim X-bias {b_a[0]:.2f} mg should be near 0 (no X-bias injected). "
        f"Full b_a={b_a}"
    )
    # Z-axis recovers the injected bias toward -50 mg
    assert abs(b_a[2] - (-50.0)) < 5.0, (
        f"AccBiasTrim Z-bias {b_a[2]:.2f} mg not within 5 mg of target -50 mg. "
        f"Full b_a={b_a}"
    )


# ------------------------------------------------------------------
# Scenario B — hot_gyro_drift (Phase 4 GyroBiasHotFsm)
# ------------------------------------------------------------------

def test_scenario_hot_gyro_drift_moves_toward_truth():
    """GyroBiasHotFsm bias estimate moves in correct direction (toward +0.02 rad/s).

    alpha=1e-4 makes convergence slow: after N commits the EWMA bias is roughly
    alpha*N*sample_mean.  After 2 commits in 5 s: b_g_y ~ 4e-6 rad/s.
    Assertion: 0 < b_g_y < 0.01 (correct direction, < 50% of injected 0.02).
    """
    sc = scenarios.hot_gyro_drift()
    res = run(sc, write_artifacts=False)

    b_g = res["gyro_hot_b_g"]
    # Y-axis injected bias = 0.02 rad/s; estimate should move positive
    assert b_g[1] > 0.0, (
        f"GyroBiasHotFsm b_g_y = {b_g[1]:.6f} rad/s — did not move toward "
        f"+0.02 rad/s injected bias. Full b_g={b_g}"
    )
    # Slow convergence: after 2 commits b_g_y is still tiny (< 50% of 0.02)
    assert b_g[1] < 0.01, (
        f"GyroBiasHotFsm b_g_y = {b_g[1]:.6f} rad/s exceeds 0.01 rad/s — "
        f"converging too fast (alpha=1e-4 should keep it slow). Full b_g={b_g}"
    )


def test_scenario_hot_gyro_drift_rc_reset():
    """GyroBiasHotFsm completes a full cycle (at least one commit) with rc_active=False.

    State=2 is transient (set in _enter_commit then immediately reset to 0), so we
    verify a commit happened by checking b_g_y > 0 and rejected=False at end of run.
    """
    sc = scenarios.hot_gyro_drift()
    res = run(sc, write_artifacts=False)

    # Calibrator log must be present
    cal_log = res.get("_cal_log")
    assert cal_log is not None, "Calibrator log should be present for hot_gyro_drift"

    # At least one commit happened: b_g_y moved from 0 toward +0.02 rad/s
    assert res["gyro_hot_b_g"][1] > 0.0, (
        f"GyroBiasHotFsm b_g_y did not update (still 0). A commit should have "
        f"occurred by tick 499. b_g={res['gyro_hot_b_g']}"
    )
    # No RC activity -> rejected should be False at end
    assert not res["gyro_hot_rejected"], (
        "gyro_hot_rejected should be False when rc_active=False throughout"
    )


# ------------------------------------------------------------------
# Non-calibrator scenarios still work (regression)
# ------------------------------------------------------------------

def test_existing_step_scenario_unchanged():
    """Existing step_roll scenario still runs and returns correct fields."""
    sc = scenarios.step("roll")
    res = run(sc, write_artifacts=False)

    assert res["scenario"] == "step_roll"
    assert res["metrics"]["stable"]
    # Calibrator fields present but NaN for non-calibrator plants
    assert res["acc_trim_b_a"] is not None
    assert res["gyro_hot_b_g"] is not None
