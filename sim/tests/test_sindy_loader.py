"""Tests for sim/sindy/flight_loader.py."""
from __future__ import annotations

import csv
import tempfile
import os
from pathlib import Path

import numpy as np
import pytest

from sim.sindy.flight_loader import (
    FlightDataset,
    load_stream_log_csv,
    _FIELD_PATTERNS,
    _SUPPORTED_AXES,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _make_csv(overrides: dict) -> Path:
    defaults = {
        "t_src_ms": "0",
        "t_host_s": "0.0",
        "seq": "1",
        "mrac_state.roll.e": "0.1",
        "mrac_state.roll.u_nom": "0.5",
        "mrac_state.roll.u_ad": "0.0",
        "mrac_state.roll.xm": "1.0",
        "mrac_state.roll.Theta[0]": "0.0",
        "mrac_state.roll.Theta[1]": "0.0",
        "mrac_state.roll.Theta[2]": "0.0",
        "mrac_state.roll.Theta[3]": "0.0",
        "mrac_state.roll.Theta[4]": "0.0",
        "mrac_state.roll.Theta[5]": "0.0",
    }
    defaults.update(overrides)
    path = Path(tempfile.mktemp(suffix=".csv"))
    _write_csv(path, [defaults], list(defaults.keys()))
    return path


# ---------------------------------------------------------------------------
# Basic loading
# ---------------------------------------------------------------------------

def test_loads_minimal_csv():
    path = _make_csv({})
    ds = load_stream_log_csv(path, manifest_name="test")
    assert ds.axis == "roll"
    assert ds.n_samples == 1
    assert isinstance(ds.t, np.ndarray)
    assert ds.t[0] == 0.0
    assert ds.meta["manifest_name"] == "test"
    os.unlink(path)


def test_reconstructs_x_and_u():
    path = _make_csv({
        "mrac_state.roll.e": "0.3",
        "mrac_state.roll.u_nom": "0.5",
        "mrac_state.roll.u_ad": "0.2",
        "mrac_state.roll.xm": "1.0",
    })
    ds = load_stream_log_csv(path)
    # x = xm - e
    assert abs(ds.x[0] - 0.7) < 1e-9
    # u = u_nom + u_ad
    assert abs(ds.u[0] - 0.7) < 1e-9
    os.unlink(path)


def test_infers_recorded_hz():
    path = Path(tempfile.mktemp(suffix=".csv"))
    rows = []
    for i in range(10):
        ms = i * 50  # 20 Hz
        rows.append({
            "t_src_ms": str(ms), "t_host_s": str(ms / 1000),
            "seq": str(i + 1),
            "mrac_state.pitch.e": "0.0", "mrac_state.pitch.u_nom": "0.0",
            "mrac_state.pitch.u_ad": "0.0", "mrac_state.pitch.xm": "0.0",
            "mrac_state.pitch.Theta[0]": "0.0",
            "mrac_state.pitch.Theta[1]": "0.0",
            "mrac_state.pitch.Theta[2]": "0.0",
            "mrac_state.pitch.Theta[3]": "0.0",
            "mrac_state.pitch.Theta[4]": "0.0",
            "mrac_state.pitch.Theta[5]": "0.0",
        })
    _write_csv(path, rows, list(rows[0].keys()))
    ds = load_stream_log_csv(path, axis="pitch")
    assert 19.0 <= ds.meta["recorded_hz"] <= 21.0
    os.unlink(path)


def test_theta_extracted():
    path = Path(tempfile.mktemp(suffix=".csv"))
    theta_vals = [1.1, 2.2, 3.3, 4.4, 5.5, 6.6]
    defaults = {
        "t_src_ms": "0", "t_host_s": "0.0", "seq": "1",
        "mrac_state.yaw.e": "0.0", "mrac_state.yaw.u_nom": "0.0",
        "mrac_state.yaw.u_ad": "0.0", "mrac_state.yaw.xm": "0.0",
        "mrac_state.yaw.Theta[0]": str(theta_vals[0]),
        "mrac_state.yaw.Theta[1]": str(theta_vals[1]),
        "mrac_state.yaw.Theta[2]": str(theta_vals[2]),
        "mrac_state.yaw.Theta[3]": str(theta_vals[3]),
        "mrac_state.yaw.Theta[4]": str(theta_vals[4]),
        "mrac_state.yaw.Theta[5]": str(theta_vals[5]),
    }
    _write_csv(path, [defaults], list(defaults.keys()))
    ds = load_stream_log_csv(path, axis="yaw")
    np.testing.assert_array_almost_equal(ds.theta[0], theta_vals)
    os.unlink(path)


# ---------------------------------------------------------------------------
# Multi-axis disambiguation
# ---------------------------------------------------------------------------

def test_requires_axis_when_multiple_axes_present():
    path = Path(tempfile.mktemp(suffix=".csv"))
    row = {
        "t_src_ms": "0", "t_host_s": "0.0", "seq": "1",
        "mrac_state.roll.e": "0.0", "mrac_state.roll.u_nom": "0.0",
        "mrac_state.roll.u_ad": "0.0", "mrac_state.roll.xm": "0.0",
        "mrac_state.roll.Theta[0]": "0.0",
        "mrac_state.roll.Theta[1]": "0.0",
        "mrac_state.roll.Theta[2]": "0.0",
        "mrac_state.roll.Theta[3]": "0.0",
        "mrac_state.roll.Theta[4]": "0.0",
        "mrac_state.roll.Theta[5]": "0.0",
        "mrac_state.pitch.e": "0.0", "mrac_state.pitch.u_nom": "0.0",
        "mrac_state.pitch.u_ad": "0.0", "mrac_state.pitch.xm": "0.0",
        "mrac_state.pitch.Theta[0]": "0.0",
        "mrac_state.pitch.Theta[1]": "0.0",
        "mrac_state.pitch.Theta[2]": "0.0",
        "mrac_state.pitch.Theta[3]": "0.0",
        "mrac_state.pitch.Theta[4]": "0.0",
        "mrac_state.pitch.Theta[5]": "0.0",
    }
    _write_csv(path, [row], list(row.keys()))
    with pytest.raises(ValueError, match="multiple axes"):
        load_stream_log_csv(path)
    os.unlink(path)


def test_explicit_axis_filters_correctly():
    path = Path(tempfile.mktemp(suffix=".csv"))
    row = {
        "t_src_ms": "0", "t_host_s": "0.0", "seq": "1",
        "mrac_state.roll.e": "1.0", "mrac_state.roll.u_nom": "0.0",
        "mrac_state.roll.u_ad": "0.0", "mrac_state.roll.xm": "0.0",
        "mrac_state.roll.Theta[0]": "0.0",
        "mrac_state.roll.Theta[1]": "0.0",
        "mrac_state.roll.Theta[2]": "0.0",
        "mrac_state.roll.Theta[3]": "0.0",
        "mrac_state.roll.Theta[4]": "0.0",
        "mrac_state.roll.Theta[5]": "0.0",
        "mrac_state.pitch.e": "2.0", "mrac_state.pitch.u_nom": "0.0",
        "mrac_state.pitch.u_ad": "0.0", "mrac_state.pitch.xm": "0.0",
        "mrac_state.pitch.Theta[0]": "0.0",
        "mrac_state.pitch.Theta[1]": "0.0",
        "mrac_state.pitch.Theta[2]": "0.0",
        "mrac_state.pitch.Theta[3]": "0.0",
        "mrac_state.pitch.Theta[4]": "0.0",
        "mrac_state.pitch.Theta[5]": "0.0",
    }
    _write_csv(path, [row], list(row.keys()))
    ds = load_stream_log_csv(path, axis="pitch")
    assert ds.e[0] == 2.0
    os.unlink(path)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def test_validate_no_warnings_on_clean_data():
    path = Path(tempfile.mktemp(suffix=".csv"))
    defaults = {
        "t_src_ms": "0", "t_host_s": "0.0", "seq": "1",
        "mrac_state.roll.e": "0.0", "mrac_state.roll.u_nom": "0.0",
        "mrac_state.roll.u_ad": "0.0", "mrac_state.roll.xm": "0.0",
        "mrac_state.roll.Theta[0]": "0.0",
        "mrac_state.roll.Theta[1]": "0.0",
        "mrac_state.roll.Theta[2]": "0.0",
        "mrac_state.roll.Theta[3]": "0.0",
        "mrac_state.roll.Theta[4]": "0.0",
        "mrac_state.roll.Theta[5]": "0.0",
    }
    # Two samples so validate() has enough data to check continuity.
    row1 = dict(defaults, t_src_ms="0", seq="1")
    row2 = dict(defaults, t_src_ms="10", seq="2")
    _write_csv(path, [row1, row2], list(defaults.keys()))
    ds = load_stream_log_csv(path)
    assert ds.validate() == []
    os.unlink(path)


def test_validate_detects_non_monotonic_time():
    path = Path(tempfile.mktemp(suffix=".csv"))
    rows = []
    for i in range(3):
        rows.append({
            "t_src_ms": str([0, 20, 10][i]), "t_host_s": "0.0", "seq": str(i + 1),
            "mrac_state.roll.e": "0.0", "mrac_state.roll.u_nom": "0.0",
            "mrac_state.roll.u_ad": "0.0", "mrac_state.roll.xm": "0.0",
            "mrac_state.roll.Theta[0]": "0.0",
            "mrac_state.roll.Theta[1]": "0.0",
            "mrac_state.roll.Theta[2]": "0.0",
            "mrac_state.roll.Theta[3]": "0.0",
            "mrac_state.roll.Theta[4]": "0.0",
            "mrac_state.roll.Theta[5]": "0.0",
        })
    _write_csv(path, rows, list(rows[0].keys()))
    ds = load_stream_log_csv(path)
    warnings = ds.validate()
    assert any("non-monotonic" in w for w in warnings)
    os.unlink(path)


def test_validate_detects_rate_mismatch():
    path = Path(tempfile.mktemp(suffix=".csv"))
    rows = []
    for i in range(10):
        ms = i * 200  # 5 Hz, but meta says 50 Hz
        rows.append({
            "t_src_ms": str(ms), "t_host_s": str(ms / 1000), "seq": str(i + 1),
            "mrac_state.roll.e": "0.0", "mrac_state.roll.u_nom": "0.0",
            "mrac_state.roll.u_ad": "0.0", "mrac_state.roll.xm": "0.0",
            "mrac_state.roll.Theta[0]": "0.0",
            "mrac_state.roll.Theta[1]": "0.0",
            "mrac_state.roll.Theta[2]": "0.0",
            "mrac_state.roll.Theta[3]": "0.0",
            "mrac_state.roll.Theta[4]": "0.0",
            "mrac_state.roll.Theta[5]": "0.0",
        })
    _write_csv(path, rows, list(rows[0].keys()))
    ds = load_stream_log_csv(path, recorded_hz=50.0)
    warnings = ds.validate()
    assert any("implied sample rate" in w for w in warnings)
    os.unlink(path)


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------

def test_rejects_empty_csv(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text("t_src_ms,t_host_s,seq\n", encoding="utf-8")
    with pytest.raises(ValueError, match="empty"):
        load_stream_log_csv(path)


def test_rejects_old_format_csv():
    path = Path(tempfile.mktemp(suffix=".csv"))
    path.write_text(
        "t_s,frame,key,value\n0.0,A,mrac.roll.e,0.0\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="no MRAC columns"):
        load_stream_log_csv(path)
    os.unlink(path)


def test_rejects_missing_axis():
    path = _make_csv({})
    with pytest.raises(ValueError, match="not found"):
        load_stream_log_csv(path, axis="yaw")
    os.unlink(path)
