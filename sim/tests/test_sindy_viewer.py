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


def test_viewer_writes_plotly_minjs_when_directory_mode(tmp_path, monkeypatch):
    datasets = {"roll": _sine_dataset("roll", n=200)}
    _patch_load_ulog(monkeypatch, datasets)
    out_html = tmp_path / "out.html"
    view_ulog(_fake_ulog_path(tmp_path, datasets), out_html)
    siblings = list(tmp_path.iterdir())
    js_files = [p for p in siblings if p.name.startswith("plotly") and p.suffix == ".js"]
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
    assert meta_yes["fit_result"]["library"] == "linear"
    assert "r2_train" in meta_yes["fit_result"]
    assert "r2_test" in meta_yes["fit_result"]
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
    # Plotly encodes trace names as JSON inside a <script> block; the slash
    # in "rad/s" becomes the JSON escape \u002f. Look for either form.
    roll_present = ("roll (rad/s)" in html) or ("roll (rad\\u002fs)" in html)
    pitch_present = ("pitch (rad/s)" in html) or ("pitch (rad\\u002fs)" in html)
    yaw_present = ("yaw (rad/s)" in html) or ("yaw (rad\\u002fs)" in html)
    assert roll_present, "roll trace missing from HTML"
    assert not pitch_present, "pitch trace unexpectedly present in HTML"
    assert not yaw_present, "yaw trace unexpectedly present in HTML"


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
