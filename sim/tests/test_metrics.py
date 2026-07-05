"""sim/metrics.py — the run-evaluation module is now a real seam, so it is tested
directly on hand-built logs (no closed loop needed). Architecture deepening #1."""
import numpy as np
import pytest

from sim import metrics as M


def _log(n=200, dt=0.005, **over):
    """A minimal finished-run log; override any column with a keyword."""
    t = np.arange(n) * dt
    base = {"t": t, "r": np.zeros(n), "d": np.zeros(n), "xm": np.zeros(n),
            "x": np.zeros(n), "e": np.zeros(n), "u_nom": np.zeros(n),
            "u_ad": np.zeros(n), "u": np.zeros(n), "U": np.zeros(n),
            "wnorm": np.zeros(n), "edot": np.zeros(n)}
    base.update(over)
    return base, dt


def test_iae_ise_itae_match_hand_integration():
    n, dt = 100, 0.01
    e = np.full(n, 2.0)
    log, _ = _log(n, dt, e=e)
    m = M.compute(log, np.zeros((n, 6)), dt)
    assert m["track_iae"] == pytest.approx(2.0 * n * dt)        # |e|*dt
    assert m["track_ise"] == pytest.approx(4.0 * n * dt)        # e^2*dt
    assert m["rmse_track"] == pytest.approx(2.0)


def test_settling_time_is_last_exit_from_band():
    # |e| large for the first 0.5 s, then inside the 5%-of-ref band forever
    n, dt = 200, 0.005
    x = np.ones(n)                      # ref_scale -> 1.0, band -> 0.05
    e = np.where(np.arange(n) < 100, 0.5, 0.0)
    log, _ = _log(n, dt, x=x, e=e)
    m = M.compute(log, np.zeros((n, 6)), dt)
    assert m["track_settling_time"] == pytest.approx(100 * dt)


def test_never_settling_reports_none():
    n, dt = 100, 0.005
    log, _ = _log(n, dt, x=np.ones(n), e=np.full(n, 0.5))
    m = M.compute(log, np.zeros((n, 6)), dt)
    assert m["track_settling_time"] is None


def test_saturation_fraction_uses_umax():
    n, dt = 100, 0.005
    U = np.where(np.arange(n) < 30, 300.0, 0.0)   # saturated 30% of the run
    log, _ = _log(n, dt, U=U)
    m = M.compute(log, np.zeros((n, 6)), dt, umax=300.0)
    assert m["ctrl_sat_fraction"] == pytest.approx(0.30)


def test_upper_saturation_flag_per_basis():
    n, dt = 10, 0.005
    theta = np.zeros((n, 6))
    theta[-1] = [0.15, 0.0, 0.0, 0.0, 0.0, 0.0]   # basis 0 pinned at its upper limit
    log, _ = _log(n, dt)
    m = M.compute(log, theta, dt,
                  what_limit=[0.15, 0.05, 0.02, 0.05, 0.20, 0.15],
                  what_tol=[0.03, 0.01, 0.005, 0.01, 0.04, 0.03])
    assert m["adapt_upper_sat"][0] is True
    assert m["adapt_any_upper_sat"] is True


def test_disturbance_recovery_only_when_disturbance_present():
    n, dt = 200, 0.005
    log_no, _ = _log(n, dt)
    assert "dist_onset_t" not in M.compute(log_no, np.zeros((n, 6)), dt)

    d = np.where(np.arange(n) >= 100, 0.08, 0.0)
    x = np.ones(n)                                 # band 0.05
    e = np.where((np.arange(n) >= 100) & (np.arange(n) < 150), 0.5, 0.0)
    log, _ = _log(n, dt, d=d, x=x, e=e)
    m = M.compute(log, np.zeros((n, 6)), dt)
    assert m["dist_onset_t"] == pytest.approx(100 * dt)
    assert m["dist_peak_dev"] == pytest.approx(0.5)
    assert m["dist_recovery_time"] == pytest.approx(50 * dt)


def test_edot_rms_present_only_with_edot_column():
    n, dt = 50, 0.005
    log, _ = _log(n, dt, edot=np.full(n, 3.0))
    m = M.compute(log, np.zeros((n, 6)), dt)
    assert m["robust_edot_rms"] == pytest.approx(3.0)
