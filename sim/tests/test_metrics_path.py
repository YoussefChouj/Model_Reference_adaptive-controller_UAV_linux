"""Tests for the path-tracking metric group (spec 4a).

Asserts on synthetic logs with analytically known answers, mirroring
how sim/tests/test_metrics.py already tests rate-loop metrics.
"""
import numpy as np
import pytest

from sim import metrics as M


def _synthetic_path_log(n: int = 100, dt: float = 0.005,
                         x_offset: float = 0.0, y_offset: float = 0.0,
                         z_offset: float = 0.0) -> dict:
    """Build a synthetic trajectory log with a known constant offset."""
    t = np.arange(n) * dt
    x_target = np.linspace(0.0, 1.0, n)
    y_target = np.zeros(n)
    z_target = np.zeros(n)
    return {
        "t": t,
        "x_target": x_target, "y_target": y_target, "z_target": z_target,
        "yaw_target": np.zeros(n),
        "x": x_target + x_offset, "y": y_target + y_offset, "z": z_target + z_offset,
        "vx": np.ones(n), "vy": np.zeros(n), "vz": np.zeros(n),
        "phi": np.zeros(n), "theta": np.zeros(n), "psi": np.zeros(n),
        "p": np.zeros(n), "q": np.zeros(n), "r": np.zeros(n),
        "thrust": np.full(n, 12.71),
        "roll_cmd": np.zeros(n), "pitch_cmd": np.zeros(n),
        "yaw_cmd": np.zeros(n), "z_cmd": np.full(n, 12.71),
        "x_err": np.full(n, x_offset), "y_err": np.full(n, y_offset),
        "z_err": np.full(n, z_offset),
        "cross_track_err": np.full(n, np.sqrt(x_offset ** 2 + y_offset ** 2)),
        "along_track_err": np.zeros(n),
    }


def test_known_constant_offset_yields_exact_cross_track():
    """A constant XY offset (0.1, 0) -> cross-track RMSE = 0.1 exactly."""
    log = _synthetic_path_log(n=200, x_offset=0.1)
    m = M.compute_path(log, dt=0.005)
    assert m["path_rms_cross_track"] == pytest.approx(0.1, abs=1e-9)
    assert m["path_max_cross_track"] == pytest.approx(0.1, abs=1e-9)
    assert m["path_mean_cross_track"] == pytest.approx(0.1, abs=1e-9)


def test_perfect_tracking_zero_cross_track():
    """Perfectly tracked path -> cross-track error = 0, position RMSE = 0."""
    log = _synthetic_path_log(n=100)
    m = M.compute_path(log, dt=0.005)
    assert m["path_rms_cross_track"] == pytest.approx(0.0, abs=1e-12)
    assert m["path_max_cross_track"] == pytest.approx(0.0, abs=1e-12)
    assert m["path_rms_position"] == pytest.approx(0.0, abs=1e-12)


def test_path_position_rmse_matches_xyz_offset():
    """position RMSE = sqrt(x_off^2 + y_off^2 + z_off^2)."""
    log = _synthetic_path_log(n=100, x_offset=0.1, y_offset=0.2, z_offset=0.3)
    m = M.compute_path(log, dt=0.005)
    expected = np.sqrt(0.01 + 0.04 + 0.09)
    assert m["path_rms_position"] == pytest.approx(expected, rel=1e-9)


def test_path_per_axis_rms_xyz():
    """path_rms_xyz reports per-axis RMSE."""
    log = _synthetic_path_log(n=100, x_offset=0.1, y_offset=0.2, z_offset=0.3)
    m = M.compute_path(log, dt=0.005)
    assert m["path_rms_xyz"]["x"] == pytest.approx(0.1, abs=1e-9)
    assert m["path_rms_xyz"]["y"] == pytest.approx(0.2, abs=1e-9)
    assert m["path_rms_xyz"]["z"] == pytest.approx(0.3, abs=1e-9)


def test_path_along_track_zero_on_perfect_track():
    """Perfect track -> along-track error = 0."""
    log = _synthetic_path_log(n=100)
    m = M.compute_path(log, dt=0.005)
    assert m["path_rms_along_track"] == pytest.approx(0.0, abs=1e-12)
    assert m["path_max_abs_along_track"] == pytest.approx(0.0, abs=1e-12)


def test_saturation_fraction_uses_z_umax():
    """Z saturation fraction counts |z_cmd| >= z_umax."""
    log = _synthetic_path_log(n=100)
    log["z_cmd"] = np.where(np.arange(100) < 25, 50.0, 10.0)  # 25% saturated
    m = M.compute_path(log, dt=0.005, z_umax=40.0)
    assert m["path_sat_fraction_z"] == pytest.approx(0.25, abs=1e-9)


def test_att_rate_rms_zero_on_zero_rates():
    """Zero body rates -> path_att_rate_rms = 0."""
    log = _synthetic_path_log(n=100)
    m = M.compute_path(log, dt=0.005)
    assert m["path_att_rate_rms"] == pytest.approx(0.0, abs=1e-12)


def test_path_metrics_handles_empty_log():
    """Empty log -> empty metric dict (no crash)."""
    empty = {k: np.empty(0) for k in (
        "t", "x_target", "y_target", "z_target", "yaw_target",
        "x", "y", "z", "vx", "vy", "vz",
        "phi", "theta", "psi", "p", "q", "r", "thrust",
        "roll_cmd", "pitch_cmd", "yaw_cmd", "z_cmd",
        "x_err", "y_err", "z_err",
        "cross_track_err", "along_track_err")}
    m = M.compute_path(empty, dt=0.005)
    assert m == {}