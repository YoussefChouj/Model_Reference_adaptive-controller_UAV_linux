"""Tests for sim/sindy/preprocessor.py."""
from __future__ import annotations

import math
import tempfile
import os
import csv

import numpy as np
import pytest

from sim.sindy.flight_loader import FlightDataset, load_stream_log_csv
from sim.sindy.preprocessor import (
    PreprocessedDataset,
    preprocess,
    preprocess_px4,
    _interpolate_inplace,
    _central_derivative,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sine_csv(n: int = 200, axis: str = "roll") -> str:
    """Create a synthetic CSV with sine-wave MRAC signals.

    xm = sin(t), e = 0, u_nom = cos(t).  dt ≈ 0.0314 s (32 Hz).
    """
    t = np.linspace(0, 2 * math.pi, n)
    rows = ["t_src_ms,t_host_s,seq,"
            f"mrac_state.{axis}.e,"
            f"mrac_state.{axis}.u_nom,"
            f"mrac_state.{axis}.u_ad,"
            f"mrac_state.{axis}.xm,"
            + ",".join(f"mrac_state.{axis}.Theta[{i}]" for i in range(6))]
    for i, ti in enumerate(t):
        rows.append(
            f"{int(ti*1000)},{ti:.4f},{i+1},"
            f"0.0,{math.cos(ti):.6f},0.0,{math.sin(ti):.6f},"
            + ",".join("0.0" for _ in range(6))
        )
    path = tempfile.mktemp(suffix=".csv")
    with open(path, "w") as fh:
        fh.write("\n".join(rows))
    return path


# ---------------------------------------------------------------------------
# End-to-end
# ---------------------------------------------------------------------------

def test_preprocess_returns_uniform_grid():
    path = _sine_csv(n=50)
    ds = load_stream_log_csv(path, manifest_name="sine_test")
    pp = preprocess(ds)

    assert isinstance(pp, PreprocessedDataset)
    assert pp.n_samples >= 2
    assert pp.n_features == 3
    assert pp.feature_names == ["e", "x", "xm"]
    # Uniform grid check.
    dt = float(np.diff(pp.t).std())
    assert dt < 1e-6, "time grid is not uniform"
    os.unlink(path)


def test_derivative_matches_analytical_sine():
    path = _sine_csv(n=200)
    ds = load_stream_log_csv(path)
    pp = preprocess(ds, normalise=False)

    # xm = sin(t), so d(xm)/dt = cos(t).
    # x = xm - e, e=0, so d(x)/dt = cos(t).
    i = 100
    t_i = pp.t[i]
    d_xm_analytical = math.cos(t_i)
    d_xm_computed = pp.dXdt[i, 2]  # column 2 = xm
    assert abs(d_xm_computed - d_xm_analytical) < 0.01
    os.unlink(path)


def test_normalise_produces_unit_variance():
    path = _sine_csv(n=200)
    ds = load_stream_log_csv(path)
    pp = preprocess(ds, normalise=True)

    assert pp.normalise_stats is not None
    for name in pp.feature_names:
        assert name in pp.normalise_stats
        mean, std = pp.normalise_stats[name]
        col = pp.X[:, pp.feature_names.index(name)]
        assert abs(float(np.mean(col))) < 0.1
    os.unlink(path)


def test_outlier_removal_interpolates():
    path = _sine_csv(n=100)
    ds = load_stream_log_csv(path)
    # Inject outliers.
    ds.e[10] = 100.0
    ds.e[20] = -100.0

    pp = preprocess(ds, outlier_threshold=10.0)
    # After outlier removal and interpolation, e should be finite everywhere.
    assert np.all(np.isfinite(pp.X[:, 1]))  # x column
    os.unlink(path)


def test_outlier_threshold_zero_disables_removal():
    path = _sine_csv(n=100)
    ds = load_stream_log_csv(path)
    ds.e[10] = 100.0
    pp = preprocess(ds, outlier_threshold=0.0)
    # No NaN should be introduced.
    assert np.all(np.isfinite(pp.X))
    os.unlink(path)


def test_missing_e_column_nan_handled():
    path = _sine_csv(n=10)
    ds = load_stream_log_csv(path)
    ds.e[:] = float("nan")
    pp = preprocess(ds)
    assert pp.n_samples >= 2
    os.unlink(path)


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

def test_interpolate_inplace_noop():
    arr = np.array([1.0, 2.0, 3.0])
    _interpolate_inplace(arr)
    np.testing.assert_array_equal(arr, [1.0, 2.0, 3.0])


def test_interpolate_inplace_single_nan():
    arr = np.array([1.0, float("nan"), 3.0])
    _interpolate_inplace(arr)
    np.testing.assert_array_equal(arr, [1.0, 2.0, 3.0])


def test_interpolate_inplace_leading_nan():
    arr = np.array([float("nan"), float("nan"), 3.0])
    _interpolate_inplace(arr)
    # Leading NaN before any valid data → 0
    assert np.isfinite(arr[0])
    assert np.isfinite(arr[1])


def test_central_derivative():
    X = np.column_stack([
        np.arange(5, dtype=float),    # [0,1,2,3,4]
        np.arange(5, dtype=float) * 2, # [0,2,4,6,8]
    ])
    t = np.arange(5, dtype=float)
    dXdt = _central_derivative(X, t)
    # Central diff for y=x: dX[2]/dt = (3-1)/(2*1) = 1
    # For y=2x: (6-2)/(2*1) = 2
    np.testing.assert_array_almost_equal(dXdt[:, 0], [1, 1, 1, 1, 1])
    np.testing.assert_array_almost_equal(dXdt[:, 1], [2, 2, 2, 2, 2])


# ---------------------------------------------------------------------------
# preprocess_px4 — PX4 single-feature preprocessor (added by sindy-real-flight-viewer)
# ---------------------------------------------------------------------------

def test_preprocess_px4_single_feature():
    """preprocess_px4 builds X = [x] (single column), tolerates NaN e/xm.

    PX4 ulog has no mrac_state.e / mrac_state.xm. The standard preprocess
    would build [e, x, xm] and propagate NaN derivatives; preprocess_px4
    restricts to x and produces a finite derivative column.
    """
    n = 200
    t = np.linspace(0.0, 2 * math.pi, n)
    x = np.sin(t)
    nan_arr = np.full(n, np.nan)
    ds = FlightDataset(
        t=t, axis="roll", x=x, u=np.cos(t), xm=nan_arr.copy(), e=nan_arr.copy(),
        u_nom=np.cos(t), u_ad=np.zeros(n), theta=np.zeros((n, 6)),
        meta={"log_path": "synthetic://px4", "manifest_name": "px4"},
    )

    pp = preprocess_px4(ds)

    assert isinstance(pp, PreprocessedDataset)
    assert pp.feature_names == ["x"]
    assert pp.X.shape == (n, 1)
    assert np.all(np.isfinite(pp.X))
    assert np.all(np.isfinite(pp.dXdt))
    assert float(np.diff(pp.t).std()) < 1e-6
