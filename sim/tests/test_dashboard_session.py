"""Tests for the dashboard's deep interface :class:`FitSession` and the
:mod:`sim.dashboard.adapters` registry.

These tests intentionally don't touch Streamlit (which has its own
runtime) — they exercise the deep module that the app sits on top of,
so any refactor of the UI doesn't break the test surface.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from sim.dashboard import FitSession, get_adapter, list_supported_exts
from sim.dashboard.adapters import CsvAdapter, UlogAdapter
from sim.sindy.fit_panel import FitConfig


REF_ULOG = Path("sim/flight_logs/uav_sead_smallest.ulg")


def test_adapter_registry_lists_supported_exts():
    exts = list_supported_exts()
    assert ".csv" in exts
    assert ".ulg" in exts


def test_get_adapter_picks_csv_for_csv():
    assert isinstance(get_adapter("foo/bar.csv"), CsvAdapter)


def test_get_adapter_picks_ulog_for_ulg():
    assert isinstance(get_adapter("foo/bar.ulg"), UlogAdapter)


def test_get_adapter_rejects_unknown_extension():
    with pytest.raises(ValueError, match="no adapter registered"):
        get_adapter("foo/bar.parquet")


def test_session_loads_real_ulog():
    if not REF_ULOG.exists():
        pytest.skip(f"{REF_ULOG} not present in this checkout")
    s = FitSession.from_log(REF_ULOG)
    assert {"roll", "pitch", "yaw"}.issubset(set(s.axes))
    assert len(s.feature_options) >= 3


def test_session_fit_returns_metrics():
    if not REF_ULOG.exists():
        pytest.skip(f"{REF_ULOG} not present in this checkout")
    s = FitSession.from_log(REF_ULOG)
    fit = s.fit("roll")
    assert "r2_train" in fit.metrics
    assert fit.coefs.shape == (len(s.feature_options),)


def test_session_with_feature_subset_refits():
    if not REF_ULOG.exists():
        pytest.skip(f"{REF_ULOG} not present in this checkout")
    s = FitSession.from_log(REF_ULOG)
    all_fit = s.fit("roll")
    reduced = s.with_feature_subset("roll", [0])   # keep only the linear x term
    red_fit = reduced.fit("roll")
    # With only one feature, coefs has zeros everywhere except position 0.
    assert red_fit.coefs.shape == all_fit.coefs.shape
    assert np.sum(red_fit.coefs != 0) <= 1


def test_session_plots_have_data_traces():
    if not REF_ULOG.exists():
        pytest.skip(f"{REF_ULOG} not present in this checkout")
    s = FitSession.from_log(REF_ULOG)
    for axis in s.axes:
        for fn in ("tracking_error", "fit_quality", "coefficient_contributions"):
            fig = getattr(s, fn)(axis)
            assert len(fig.data) > 0, f"{axis}/{fn} rendered empty figure"


def test_session_metrics_table_is_well_formed():
    if not REF_ULOG.exists():
        pytest.skip(f"{REF_ULOG} not present in this checkout")
    s = FitSession.from_log(REF_ULOG)
    df = s.metrics_table()
    assert list(df.columns)[:3] == ["axis", "n_features_used", "n_features_total"]
    assert len(df) == len(s.axes)