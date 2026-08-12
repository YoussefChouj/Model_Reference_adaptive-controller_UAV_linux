"""Tests for prior-10 trajectory scenario infrastructure.

Tests cover:
  * Firmware-matched presets (sinusoid, figure8) — deterministic shape
  * WaypointAccumulator parity with the firmware algorithm
  * Closed-form cross-track on analytically known cases
  * Trajectory scenario registry and Δs sweep
  * End-to-end trajectory run with all new parameters
"""
import math

import numpy as np
import pytest

from sim import metrics as M
from sim.trajectories import (
    BernoulliCurve,
    CircleCurve,
    SinusoidCurve,
    closed_form_cross_track,
    figure8,
    lemniscate,
    sinusoid,
)
from sim.trajectory_runner import WaypointAccumulator, run_trajectory


# ---------------------------------------------------------------------------
# Preset shape tests
# ---------------------------------------------------------------------------

def test_sinusoid_deterministic():
    """Same parameters -> identical waypoints."""
    t1 = sinusoid(axis=0, center=(0.0, 0.0, 1.0), amplitude=0.5,
                  frequency=0.5, duration=2.0)
    t2 = sinusoid(axis=0, center=(0.0, 0.0, 1.0), amplitude=0.5,
                  frequency=0.5, duration=2.0)
    np.testing.assert_array_equal(t1.waypoints, t2.waypoints)


def test_sinusoid_axis_injection():
    """Sinusoid on axis 0 modulates X around centre_x; Y stays at centre_y."""
    t = sinusoid(axis=0, center=(1.0, 2.0, 3.0), amplitude=0.5,
                 frequency=1.0, duration=1.0)
    # At t=0, sin(0)=0 -> x = centre_x
    np.testing.assert_allclose(t.waypoints[0, 1], 1.0, atol=1e-6)
    np.testing.assert_allclose(t.waypoints[0, 2], 2.0, atol=1e-6)
    np.testing.assert_allclose(t.waypoints[0, 3], 3.0, atol=1e-6)
    # At t=0.25 s, f=1 Hz, phase=π/2 -> sin=1 -> x = centre_x + amp
    idx_quarter = int(0.25 / 0.005)
    np.testing.assert_allclose(t.waypoints[idx_quarter, 1],
                               1.0 + 0.5, atol=1e-6)
    np.testing.assert_allclose(t.waypoints[idx_quarter, 2], 2.0, atol=1e-6)


def test_sinusoid_y_axis():
    """Sinusoid on axis=1 modulates Y, not X."""
    t = sinusoid(axis=1, center=(0.0, 0.0, 1.0), amplitude=0.5,
                 frequency=1.0, duration=1.0)
    # Y should vary; X should stay near 0.
    y_std = float(np.std(t.waypoints[:, 2]))
    x_std = float(np.std(t.waypoints[:, 1]))
    assert y_std > 0.3  # significant variation
    assert x_std < 1e-6  # effectively constant


def test_figure8_bernoulli_matches_firmware():
    """Bernoulli parametric form: x = amp*cos(t)/(1+sin²(t)), y = amp*sin(t)*cos(t)/(1+sin²(t))."""
    t = figure8(center=(0.0, 0.0, 1.0), amplitude=1.0,
                 angular_speed=1.0, type=0, duration=2.0)
    # At t=0: sin(0)=0, cos(0)=1 -> x=1, y=0
    np.testing.assert_allclose(t.waypoints[0, 1], 1.0, atol=1e-6)
    np.testing.assert_allclose(t.waypoints[0, 2], 0.0, atol=1e-6)
    # At t=π: sin(π)=0, cos(π)=-1 -> x=-1, y=0 (closed path)
    idx_pi = np.argmax(t.waypoints[:, 0] >= math.pi)
    np.testing.assert_allclose(t.waypoints[idx_pi, 1], -1.0, atol=1e-3)


def test_figure8_gerono_matches_firmware():
    """Gerono parametric form: x = 0.5*amp*sin(2t), y = amp*sin(t)."""
    t = figure8(center=(0.0, 0.0, 1.0), amplitude=1.0,
                 angular_speed=1.0, type=1, duration=2.0)
    # At t=0: sin(0)=0 -> x=0, y=0
    np.testing.assert_allclose(t.waypoints[0, 1], 0.0, atol=1e-6)
    np.testing.assert_allclose(t.waypoints[0, 2], 0.0, atol=1e-6)
    # At t=π/2: sin(π/2)=1, sin(π)=0 -> x=0, y=1
    idx_halfpi = np.argmax(t.waypoints[:, 0] >= math.pi / 2)
    np.testing.assert_allclose(t.waypoints[idx_halfpi, 1], 0.0, atol=1e-3)
    np.testing.assert_allclose(t.waypoints[idx_halfpi, 2], 1.0, atol=1e-3)


def test_figure8_invalid_type_raises():
    with pytest.raises(ValueError):
        figure8(type=2)


# ---------------------------------------------------------------------------
# WaypointAccumulator — firmware parity tests
# ---------------------------------------------------------------------------

def test_accum_continuous_delta_s_zero():
    """Δs=0 passes through the continuous target unchanged."""
    accum = WaypointAccumulator(delta_s_m=0.0)
    accum.reset()
    cx, cy, cz = accum.tick(1.0, 2.0, 3.0)
    assert (cx, cy, cz) == (1.0, 2.0, 3.0)
    cx2, cy2, cz2 = accum.tick(2.0, 3.0, 4.0)
    assert (cx2, cy2, cz2) == (2.0, 3.0, 4.0)


def test_accum_holds_until_delta_s_reached():
    """Accumulator holds the last committed waypoint until accumulated distance >= Δs."""
    accum = WaypointAccumulator(delta_s_m=1.0)  # 1 metre threshold
    accum.reset()
    # First tick: committed immediately (no last point).
    cx, cy, cz = accum.tick(0.0, 0.0, 0.0)
    assert (cx, cy, cz) == (0.0, 0.0, 0.0)
    # Second tick: moves by 0.3 m (in XY); not enough to commit.
    cx2, cy2, cz2 = accum.tick(0.3, 0.0, 0.0)
    assert (cx2, cy2, cz2) == (0.0, 0.0, 0.0)  # still holding
    # Third tick: moves another 0.4 m -> total 0.7 m; still not enough.
    cx3, cy3, cz3 = accum.tick(0.7, 0.0, 0.0)
    assert (cx3, cy3, cz3) == (0.0, 0.0, 0.0)  # still holding
    # Fourth tick: moves another 0.5 m -> total 1.2 m >= Δs. Commits.
    cx4, cy4, cz4 = accum.tick(1.2, 0.0, 0.0)
    assert (cx4, cy4, cz4) == (1.2, 0.0, 0.0)  # now committed


def test_accum_z_scaled_by_100():
    """Z delta is scaled ×100 before Euclidean sum (firmware unit contract)."""
    accum = WaypointAccumulator(delta_s_m=1.0)
    accum.reset()
    # Z moves 0.01 m = 1 cm. Scaled: 1 cm * 100 = 1 m-equivalent.
    # XY stays at 0. So 1 m-equivalent >= Δs=1.0 -> commits.
    accum.tick(0.0, 0.0, 0.0)
    cx, cy, cz = accum.tick(0.0, 0.0, 0.01)
    # 1 m-equivalent >= 1.0 -> committed
    assert (cx, cy, cz) == (0.0, 0.0, 0.01)


def test_accum_z_small_delta_below_threshold():
    """Z moves 0.001 m = 0.1 cm-equivalent; below Δs=1.0 -> holds."""
    accum = WaypointAccumulator(delta_s_m=1.0)
    accum.reset()
    accum.tick(0.0, 0.0, 0.0)
    cx, cy, cz = accum.tick(0.0, 0.0, 0.001)
    assert (cx, cy, cz) == (0.0, 0.0, 0.0)  # still holding


def test_accum_reset():
    """reset() clears all state."""
    accum = WaypointAccumulator(delta_s_m=1.0)
    accum.reset()
    accum.tick(0.0, 0.0, 0.0)
    accum.tick(0.5, 0.0, 0.0)  # held, accum ~0.5
    accum.reset()
    # After reset, next tick commits immediately.
    cx, cy, cz = accum.tick(10.0, 0.0, 0.0)
    assert (cx, cy, cz) == (10.0, 0.0, 0.0)


# ---------------------------------------------------------------------------
# Closed-form cross-track tests
# ---------------------------------------------------------------------------

def test_circle_cross_track_exactly_on_circle_is_zero():
    """A point exactly on the circle centre+radius -> cross-track = 0."""
    curve = CircleCurve(cx=0.0, cy=0.0, radius=1.0)
    ct = curve.cross_track(1.0, 0.0)  # (r, 0) on the circle
    assert ct == pytest.approx(0.0, abs=1e-12)


def test_circle_cross_track_10cm_inside():
    """10 cm inside the circle."""
    curve = CircleCurve(cx=0.0, cy=0.0, radius=1.0)
    ct = curve.cross_track(0.9, 0.0)  # 0.9 m from centre = 10 cm inside
    assert ct == pytest.approx(0.10, abs=1e-6)


def test_circle_cross_track_10cm_outside():
    """10 cm outside the circle."""
    curve = CircleCurve(cx=0.0, cy=0.0, radius=1.0)
    ct = curve.cross_track(1.1, 0.0)
    assert ct == pytest.approx(0.10, abs=1e-6)


def test_bernoulli_cross_track_on_curve_is_zero():
    """A point exactly on the Bernoulli lemniscate -> cross-track ≈ 0."""
    curve = BernoulliCurve(cx=0.0, cy=0.0, amplitude=1.0)
    # At t=0: (1, 0) is on the curve.
    ct = curve.cross_track(1.0, 0.0)
    assert ct == pytest.approx(0.0, abs=1e-6)


def test_sinusoid_x_cross_track_perpendicular():
    """Sinusoid on X: cross-track is perpendicular distance from the Y axis."""
    curve = SinusoidCurve(axis=0, center=(0.0, 0.0, 1.0),
                          amplitude=0.5, frequency=0.5)
    ct = curve.cross_track(0.0, 1.0)  # on Y axis, 1 m away
    assert ct == pytest.approx(1.0, abs=1e-6)


def test_closed_form_cross_track_circle():
    """closed_form_cross_track delegates to CircleCurve."""
    traj = lemniscate(aggressiveness=1.0, duration=8.0)
    # Build a circle trajectory explicitly.
    from sim.trajectories import circle
    circ = circle(aggressiveness=1.0, radius=1.0, duration=8.0)
    ct, at = closed_form_cross_track(circ, 1.1, 0.0, 0.0)
    assert ct == pytest.approx(0.10, abs=1e-3)


def test_closed_form_cross_track_falls_back_to_polyline():
    """Polygon and lemniscate fall back to polyline (no closed form registered)."""
    from sim.trajectories import polygon
    poly = polygon(n_sides=4, duration=4.0)
    # Should not raise; falls back to polyline.
    ct, at = closed_form_cross_track(poly, 0.5, 0.5, 1.0)
    assert ct >= 0.0


# ---------------------------------------------------------------------------
# New metrics: max_error and transient_error
# ---------------------------------------------------------------------------

def test_max_error_is_vector_magnitude_max():
    """path_max_error = max ||pos_err|| over the run."""
    t = np.arange(100) * 0.005
    log = {
        "t": t,
        "x_target": np.zeros(100), "y_target": np.zeros(100),
        "z_target": np.zeros(100), "yaw_target": np.zeros(100),
        "x": np.array([0.0, 0.3, 0.0] * 34)[:100],  # max 0.3 at idx 1
        "y": np.zeros(100),
        "z": np.zeros(100),
        "vx": np.zeros(100), "vy": np.zeros(100), "vz": np.zeros(100),
        "phi": np.zeros(100), "theta": np.zeros(100), "psi": np.zeros(100),
        "p": np.zeros(100), "q": np.zeros(100), "r": np.zeros(100),
        "thrust": np.zeros(100),
        "roll_cmd": np.zeros(100), "pitch_cmd": np.zeros(100),
        "yaw_cmd": np.zeros(100), "z_cmd": np.zeros(100),
        "x_err": np.zeros(100), "y_err": np.zeros(100), "z_err": np.zeros(100),
        "cross_track_err": np.zeros(100), "along_track_err": np.zeros(100),
    }
    m = M.compute_path(log, dt=0.005)
    assert m["path_max_error"] == pytest.approx(0.3, abs=1e-6)


def test_transient_error_is_max_over_first_n_seconds():
    """path_transient_error = max ||pos_err|| over the first transient_seconds."""
    t = np.arange(100) * 0.005  # 0 to 0.495 s
    # Position error spikes early: 0.5 m at t=0, decays to 0 after.
    x_err = np.array([0.5 if i < 20 else 0.0 for i in range(100)])
    log = {
        "t": t,
        "x_target": np.zeros(100), "y_target": np.zeros(100),
        "z_target": np.zeros(100), "yaw_target": np.zeros(100),
        "x": x_err, "y": np.zeros(100), "z": np.zeros(100),
        "vx": np.zeros(100), "vy": np.zeros(100), "vz": np.zeros(100),
        "phi": np.zeros(100), "theta": np.zeros(100), "psi": np.zeros(100),
        "p": np.zeros(100), "q": np.zeros(100), "r": np.zeros(100),
        "thrust": np.zeros(100),
        "roll_cmd": np.zeros(100), "pitch_cmd": np.zeros(100),
        "yaw_cmd": np.zeros(100), "z_cmd": np.zeros(100),
        "x_err": x_err, "y_err": np.zeros(100), "z_err": np.zeros(100),
        "cross_track_err": np.zeros(100), "along_track_err": np.zeros(100),
    }
    # transient_seconds=0.1 s -> indices 0..19 (t <= 0.1)
    m = M.compute_path(log, dt=0.005, transient_seconds=0.1)
    assert m["path_transient_error"] == pytest.approx(0.5, abs=1e-6)
    # transient_seconds=0.5 s -> whole run
    m2 = M.compute_path(log, dt=0.005, transient_seconds=0.5)
    assert m2["path_transient_error"] == pytest.approx(0.5, abs=1e-6)


# ---------------------------------------------------------------------------
# End-to-end trajectory run with new parameters
# ---------------------------------------------------------------------------

def test_run_trajectory_delta_s_zero_runs():
    """run_trajectory with delta_s=0.0 (continuous) completes without error."""
    traj = sinusoid(axis=0, duration=2.0)
    out = run_trajectory(traj, dt=0.005, write_artifacts=False, delta_s=0.0)
    assert "log" in out
    assert len(out["log"]["t"]) > 0


def test_run_trajectory_delta_s_sparse_runs():
    """run_trajectory with delta_s=0.25 m (sparse staircase)."""
    traj = sinusoid(axis=0, duration=4.0)
    out = run_trajectory(traj, dt=0.005, write_artifacts=False,
                         delta_s=0.25)
    assert "log" in out
    assert len(out["log"]["t"]) > 0


def test_run_trajectory_use_closed_form_ct_flag():
    """run_trajectory with use_closed_form_ct=True runs without error."""
    traj = figure8(type=0, duration=2.0)
    out = run_trajectory(traj, dt=0.005, write_artifacts=False,
                         use_closed_form_ct=True)
    assert "log" in out
    # Cross-track should be stored.
    assert "cross_track_err" in out["log"]
    assert len(out["log"]["cross_track_err"]) > 0


def test_run_trajectory_all_new_presets_run():
    """All new presets (sinusoid, figure8) run end-to-end without error."""
    presets = [
        sinusoid(axis=0, duration=1.0),
        sinusoid(axis=1, duration=1.0),
        sinusoid(axis=2, duration=1.0),
        figure8(type=0, duration=2.0),
        figure8(type=1, duration=2.0),
    ]
    for traj in presets:
        out = run_trajectory(traj, dt=0.005, write_artifacts=False)
        assert "log" in out
        assert np.all(np.isfinite(out["log"]["x"]))
        assert np.all(np.isfinite(out["log"]["cross_track_err"]))


# ---------------------------------------------------------------------------
# Scenario registry and Δs sweep
# ---------------------------------------------------------------------------

def test_scenario_registry_populated():
    """TRAJECTORY_SCENARIOS contains all named presets."""
    from sim.scenarios import TRAJECTORY_SCENARIOS
    assert "traj_circle" in TRAJECTORY_SCENARIOS
    assert "traj_sinusoid_x" in TRAJECTORY_SCENARIOS
    assert "traj_figure8_bernoulli" in TRAJECTORY_SCENARIOS


def test_ds_sweep_values():
    """DS_SWEEP_VALUES contains {0, 0.02, 0.05, 0.10, 0.25}."""
    from sim.scenarios import DS_SWEEP_VALUES
    assert set(DS_SWEEP_VALUES) == {0.0, 0.02, 0.05, 0.10, 0.25}


def test_make_delta_s_variants():
    """make_delta_s_variants produces one scenario per Δs value."""
    from sim.scenarios import make_delta_s_variants, TRAJECTORY_SCENARIOS
    circle_scenario = TRAJECTORY_SCENARIOS["traj_circle"]
    variants = make_delta_s_variants(circle_scenario)
    assert len(variants) == 5
    names = [v.name for v in variants]
    assert "traj_circle_ds0.00" in names
    assert "traj_circle_ds0.25" in names


def test_run_trajectory_scenario():
    """run_trajectory_scenario wires a TrajectoryScenario end-to-end."""
    from sim.scenarios import TRAJECTORY_SCENARIOS, run_trajectory_scenario
    scenario = TRAJECTORY_SCENARIOS["traj_circle"]
    result = run_trajectory_scenario(scenario, write_artifacts=False)
    assert "log" in result
    assert result["scenario"] == "traj_circle"
    assert "description" in result


def test_run_ds_sweep_returns_all_variants():
    """run_ds_sweep produces one result per Δs value."""
    from sim.scenarios import TRAJECTORY_SCENARIOS, run_ds_sweep
    scenario = TRAJECTORY_SCENARIOS["traj_circle"]
    results = run_ds_sweep(scenario, write_artifacts=False)
    assert len(results) == 5
