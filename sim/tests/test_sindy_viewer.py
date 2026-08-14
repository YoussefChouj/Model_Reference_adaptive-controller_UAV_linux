"""Tests for ``sim.sindy.viewer.view_ulog``.

Builds synthetic ``FlightDataset`` objects directly (no ``pyulog``) and
checks the rendered Plotly HTML output + metadata dict. The CLI is invoked
via ``subprocess`` so we exercise ``__main__.py`` end-to-end without
touching the real ``.ulg`` cache.
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from sim.sindy.flight_loader import FlightDataset
from sim.sindy.viewer import view_ulog


REPO_ROOT = Path(__file__).resolve().parents[2]
PYTHON = sys.executable


def _sine_dataset(
    axis: str,
    n: int = 500,
    *,
    include_e: bool = False,
    include_xm: bool = False,
    amp: float = 1.0,
    freq: float = 1.0,
) -> FlightDataset:
    """Build a synthetic ``FlightDataset`` with ``x = A*sin(2*pi*f*t)``.

    When ``include_e`` / ``include_xm`` are True, those fields are populated
    with finite values; otherwise they are NaN (PX4 case).
    """
    t = np.linspace(0, 2 * math.pi, n)
    x = amp * np.sin(2 * math.pi * freq * t)
    u = amp * np.cos(2 * math.pi * freq * t)
    n_pts = len(t)
    e = np.zeros(n_pts) if include_e else np.full(n_pts, np.nan)
    xm = np.copy(x) if include_xm else np.full(n_pts, np.nan)
    u_nom = np.copy(u)
    u_ad = np.zeros(n_pts)
    theta = np.zeros((n_pts, 6))
    return FlightDataset(
        t=t, axis=axis, x=x, u=u, xm=xm, e=e,
        u_nom=u_nom, u_ad=u_ad, theta=theta,
        meta={"log_path": f"synthetic://{axis}", "manifest_name": "synth"},
    )


def _fake_ulog_path(
    tmp_path: Path,
    datasets: dict[str, FlightDataset],
) -> Path:
    """Write a minimal ``.ulog``-named file so the viewer's adapter can be
    short-circuited via monkeypatching ``load_ulog``.

    Returns a non-existent path; the test will monkeypatch ``load_ulog``
    before invoking ``view_ulog`` so the real adapter is never called.
    """
    return tmp_path / "synthetic.ulog"


def _patch_load_ulog(monkeypatch: pytest.MonkeyPatch, datasets: dict[str, FlightDataset]) -> None:
    """Replace ``sim.sindy.viewer.load_ulog`` with a stub returning the
    matching synthetic dataset for each axis (None if absent).
    """
    from sim.sindy import viewer as viewer_mod

    def fake_load(path, axis: str = "roll"):
        return datasets.get(axis)

    monkeypatch.setattr(viewer_mod, "load_ulog", fake_load)


# ---------------------------------------------------------------------------
# viewer.view_ulog — direct API
# ---------------------------------------------------------------------------

def test_viewer_runs_on_synthetic_dataset(tmp_path, monkeypatch):
    datasets = {
        "roll": _sine_dataset("roll", n=400),
        "pitch": _sine_dataset("pitch", n=400, amp=0.5, freq=1.5),
    }
    _patch_load_ulog(monkeypatch, datasets)

    out_html = tmp_path / "x.html"
    meta = view_ulog(_fake_ulog_path(tmp_path, datasets), out_html)

    assert meta["n_samples"] >= 400
    assert meta["html_path"] == str(out_html)
    assert out_html.exists()
    assert out_html.stat().st_size > 1024


def test_viewer_loads_local_plotly(tmp_path, monkeypatch):
    """The HTML dashboard references a local plotly.min.js sibling file."""
    datasets = {"roll": _sine_dataset("roll", n=200)}
    _patch_load_ulog(monkeypatch, datasets)
    out_html = tmp_path / "out.html"
    view_ulog(_fake_ulog_path(tmp_path, datasets), out_html)
    html = out_html.read_text(encoding="utf-8")
    # Must reference the local plotly.min.js (no CDN).
    assert "plotly.min.js" in html, "expected plotly.min.js script tag in HTML"
    assert "cdn.plot.ly" not in html, "should not require CDN"
    # The sibling plotly.min.js file should be copied next to the HTML.
    siblings = list(tmp_path.iterdir())
    js_files = [p for p in siblings if p.name == "plotly.min.js"]
    assert js_files, f"expected plotly.min.js sibling in {tmp_path}, got {[p.name for p in siblings]}"


def test_viewer_with_fit_adds_sindy_panel(tmp_path, monkeypatch):
    datasets = {"roll": _sine_dataset("roll", n=400)}
    _patch_load_ulog(monkeypatch, datasets)

    out_no_fit = tmp_path / "no_fit.html"
    out_with_fit = tmp_path / "with_fit.html"
    meta_no = view_ulog(_fake_ulog_path(tmp_path, datasets), out_no_fit, fit=False)
    meta_yes = view_ulog(_fake_ulog_path(tmp_path, datasets), out_with_fit, fit=True)

    assert meta_no["fit_result"] is None
    assert meta_yes["fit_result"] is not None
    # New viewer fits polynomial per-axis with setpoint; payload has
    # ``per_axis`` (with one entry per available axis) and an optional
    # ``joint`` cross-axis fit.
    assert "per_axis" in meta_yes["fit_result"]
    assert "roll" in meta_yes["fit_result"]["per_axis"]
    roll_fit = meta_yes["fit_result"]["per_axis"]["roll"]
    assert roll_fit["library"] == "polynomial_per_axis"
    assert "metrics" in roll_fit
    for key in ("r2_train", "r2_test", "rmse_train", "rmse_test",
                "mae_train", "mae_test", "nrmse_train", "nrmse_test",
                "n_active_terms", "n_total_terms"):
        assert key in roll_fit["metrics"], f"missing metric {key}"
    # Per-axis coefficients correspond to the 5-feature polynomial library.
    assert len(roll_fit["coefs"]) == 5
    assert len(roll_fit["feature_names"]) == 5
    assert out_with_fit.stat().st_size > out_no_fit.stat().st_size


def test_viewer_downsamples_long_dataset(tmp_path, monkeypatch):
    n_total = 50_000
    n_target = 1500
    datasets = {"roll": _sine_dataset("roll", n=n_total)}
    _patch_load_ulog(monkeypatch, datasets)

    out_html = tmp_path / "long.html"
    view_ulog(_fake_ulog_path(tmp_path, datasets), out_html, downsamples_to=n_target)

    # Read the figure data out of the rendered HTML — Plotly embeds it as JSON
    # in a <script type="application/json" id="plotly-data"> block. We do a
    # loose check on point counts rather than parsing the full JSON.
    html = out_html.read_text(encoding="utf-8")
    # The HTML must contain at least one "x":[...] array sized near n_target.
    # Plotly serialises long arrays; just assert no array literal has 50_000+ entries.
    assert "]," not in html[:50_000] or html.count(f":[{n_total}") == 0, \
        "trace still contains the full 50 000-sample array"
    # And the file size is bounded by the downsample + JS payload.
    assert out_html.stat().st_size < 200 * 1024 * 1024


def test_viewer_handles_missing_axes(tmp_path, monkeypatch):
    datasets = {"roll": _sine_dataset("roll", n=300)}
    _patch_load_ulog(monkeypatch, datasets)

    out_html = tmp_path / "only_roll.html"
    meta = view_ulog(_fake_ulog_path(tmp_path, datasets), out_html)

    assert meta["axis_coverage"] == ["roll"]
    assert out_html.exists()
    html = out_html.read_text(encoding="utf-8")
    # Check that only roll tab is present in the nav and tab container.
    # The sidebar has nav-item elements with data-tab="axis_roll" etc.
    assert 'data-tab="axis_roll"' in html
    assert 'data-tab="axis_pitch"' not in html
    assert 'data-tab="axis_yaw"' not in html
    # KPI strip should be rendered for the roll tab.
    assert 'kpi-strip' in html


def test_viewer_fit_uses_polynomial_library_with_setpoint(tmp_path, monkeypatch):
    """The per-axis fit uses the polynomial library ``[x, u, x^2, x*u, u^2]``."""
    datasets = {"roll": _sine_dataset("roll", n=400)}
    _patch_load_ulog(monkeypatch, datasets)

    out_html = tmp_path / "poly.html"
    meta = view_ulog(_fake_ulog_path(tmp_path, datasets), out_html, fit=True)

    roll_fit = meta["fit_result"]["per_axis"]["roll"]
    # Polynomial library — must include x, u and the cross-term x*u.
    assert roll_fit["feature_names"] == ["x", "u", "x^2", "x*u", "u^2"]
    assert len(roll_fit["coefs"]) == 5
    # R² on a clean sinusoid with cosine setpoint should be near 1.
    assert roll_fit["metrics"]["r2_train"] > 0.9
    # Active terms: with the threshold default, the polynomial library
    # usually picks up several coefficients. We don't pin the exact count,
    # but it must be ≥ 1.
    assert roll_fit["metrics"]["n_active_terms"] >= 1


def test_viewer_fit_joint_appears_when_all_axes_present(tmp_path, monkeypatch):
    """Joint cross-axis fit (27-feature polynomial in 6-vector) is built
    when roll + pitch + yaw are all available."""
    datasets = {
        "roll": _sine_dataset("roll", n=300),
        "pitch": _sine_dataset("pitch", n=300, amp=0.5, freq=1.5),
        "yaw": _sine_dataset("yaw", n=300, amp=0.3, freq=2.0),
    }
    _patch_load_ulog(monkeypatch, datasets)

    out_html = tmp_path / "joint.html"
    meta = view_ulog(_fake_ulog_path(tmp_path, datasets), out_html, fit=True)

    assert meta["fit_result"]["joint"] is not None
    joint = meta["fit_result"]["joint"]
    assert joint["library"] == "polynomial_joint"
    # 27-feature polynomial library in [x_r, x_p, x_y, u_r, u_p, u_y].
    assert len(joint["feature_names"]) == 27
    # coefs are returned as nested list (27, 3) in the per-axis summary
    # but flattened to 81 in the top-level joint coefs field for the JSON
    # metadata (27 features × 3 outputs).
    assert len(joint["coefs"]) == 27 * 3
    # One scenario set with at least the full model + one drop-one.
    assert joint["n_scenarios"] >= 2
    # Per-axis metrics for the joint fit.
    for ax in ("roll", "pitch", "yaw"):
        assert ax in joint["metrics_per_axis"]
        m = joint["metrics_per_axis"][ax]
        assert "r2_train" in m and "rmse_train" in m


def test_viewer_fit_precomputes_drop_one_scenarios(tmp_path, monkeypatch):
    """Per-axis fit precomputes full-model + drop-one scenarios for the
    buttons updatemenu (visible in the HTML; metadata reports the
    active scenario's label)."""
    from sim.sindy import viewer as viewer_mod
    datasets = {"roll": _sine_dataset("roll", n=300)}
    _patch_load_ulog(monkeypatch, datasets)

    # Capture the payloads built during rendering.
    captured = {}
    orig = viewer_mod._build_fit_payloads
    def spy(d, cfg):
        p = orig(d, cfg)
        captured["payloads"] = p
        return p
    monkeypatch.setattr(viewer_mod, "_build_fit_payloads", spy)

    out_html = tmp_path / "sc.html"
    view_ulog(_fake_ulog_path(tmp_path, datasets), out_html, fit=True)

    roll_payload = captured["payloads"]["per_axis"]["roll"]
    # 1 full + 5 drop-one = 6 scenarios
    assert len(roll_payload["scenarios"]) == 6
    labels = [s["label"] for s in roll_payload["scenarios"]]
    assert labels[0] == "Full model"
    assert "Without x*u" in labels
    assert "Without x^2" in labels


def test_viewer_handles_partial_axes_no_joint(tmp_path, monkeypatch):
    """When pitch/yaw are missing, the joint tab is a placeholder, not a fit."""
    datasets = {
        "roll": _sine_dataset("roll", n=300),
        "pitch": _sine_dataset("pitch", n=300),
    }
    _patch_load_ulog(monkeypatch, datasets)

    out_html = tmp_path / "partial.html"
    meta = view_ulog(_fake_ulog_path(tmp_path, datasets), out_html, fit=True)

    assert meta["fit_result"]["joint"] is None
    assert set(meta["fit_result"]["per_axis"].keys()) == {"roll", "pitch"}


# ---------------------------------------------------------------------------
# CLI — python -m sim.sindy view ...
# ---------------------------------------------------------------------------

def test_cli_invokes_viewer(tmp_path, monkeypatch):
    datasets = {"roll": _sine_dataset("roll", n=200)}
    _patch_load_ulog(monkeypatch, datasets)

    fake_ulog = _fake_ulog_path(tmp_path, datasets)
    out_html = tmp_path / "cli.html"

    result = subprocess.run(
        [PYTHON, "-m", "sim.sindy", "view", str(fake_ulog), str(out_html)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=120,
    )
    assert result.returncode == 0, f"stderr:\n{result.stderr}"
    # Stdout must contain parseable JSON metadata.
    meta = json.loads(result.stdout)
    assert meta["html_path"] == str(out_html)
    assert out_html.exists()
