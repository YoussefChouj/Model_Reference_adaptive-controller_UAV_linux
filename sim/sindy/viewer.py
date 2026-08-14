"""Interactive Plotly HTML viewer for SINDy pipeline on PX4 ``.ulog`` data.

Builds a single self-contained HTML page with:

- A pair of stacked subplots per axis (roll / pitch / yaw):
  ``body rates (rad/s)`` on top, ``rate setpoints`` below, shared time axis.
- ``hovermode="x unified"`` so the cursor shows every trace at one time.
- A range slider on the bottom subplot for zooming.
- An updatemenus dropdown ("All" / "Roll only" / "Pitch only" / "Yaw only")
  that toggles trace visibility by axis.
- An optional ``fit=True`` third subplot that runs ``preprocess_px4`` +
  ``fit_sindy(library="linear")`` on the roll axis and overlays the SINDy
  prediction against the measured ``dx/dt``, plus a coefficient bar chart
  and R² annotation.

The HTML is written with ``pio.write_html(..., include_plotlyjs="directory")``
so the report works offline — a sibling ``plotly.min.js`` (~3 MB) is
written next to ``out_html``.

The module is offline-capable and has no hard dependency on real
``.ulog`` files at import time — tests inject a synthetic ``FlightDataset``
shaped like the one returned by ``adapters.ulog.load_ulog``.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence

import numpy as np
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots

from sim.sindy.flight_loader import FlightDataset
from sim.sindy.adapters.ulog import load_ulog


AXES: tuple[str, ...] = ("roll", "pitch", "yaw")


def _downsample_uniform(t: np.ndarray, y: np.ndarray, n_target: int) -> tuple[np.ndarray, np.ndarray]:
    """Uniform-stride downsample to at most ``n_target`` points.

    LTTB-style min-max preservation is overkill for a viewer; we keep the
    first and last sample and stride evenly between them.
    """
    n = len(t)
    if n <= n_target or n_target < 2:
        return t, y
    idx = np.linspace(0, n - 1, n_target).astype(int)
    # De-duplicate indices (rare when n > n_target; safe to handle).
    idx = np.unique(idx)
    return t[idx], y[idx]


def _load_axis(ulog_path: str | Path, axis: str) -> Optional[FlightDataset]:
    """Load one axis from the ulog. Returns None if the axis is missing."""
    ds = load_ulog(ulog_path, axis=axis)
    if ds is None:
        return None
    return ds  # type: ignore[return-value]


def _build_figure(
    datasets: dict[str, FlightDataset],
    *,
    fit_result: Optional[dict] = None,
    title: str = "",
) -> go.Figure:
    """Construct the Plotly Figure from per-axis datasets and optional fit."""
    n_rows = 3 if fit_result is not None else 2
    subplot_titles = ("Body rates (rad/s)", "Rate setpoints")
    row_heights = [0.5, 0.5]
    # Per-row specs: only the SINDy row needs a secondary y-axis for the bar trace.
    if fit_result is not None:
        subplot_titles = (*subplot_titles, "SINDy fit (roll axis, linear library)")
        row_heights = [0.4, 0.35, 0.25]
        specs = [
            [{"secondary_y": False}],
            [{"secondary_y": False}],
            [{"secondary_y": True}],
        ]
    else:
        specs = [
            [{"secondary_y": False}],
            [{"secondary_y": False}],
        ]

    fig = make_subplots(
        rows=n_rows,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        row_heights=row_heights,
        subplot_titles=subplot_titles,
        specs=specs,
    )

    # Trace group index — first axis added is group "1", second "2", third "3".
    # The dropdown menu toggles visibility by group.
    for grp, axis in enumerate(AXES, start=1):
        ds = datasets.get(axis)
        if ds is None:
            continue
        t_ds, x_ds = _downsample_uniform(ds.t, ds.x, 5000)
        _, u_ds = _downsample_uniform(ds.t, ds.u, 5000)
        fig.add_trace(
            go.Scatter(
                x=t_ds, y=x_ds,
                mode="lines",
                name=f"{axis} (rad/s)",
                legendgroup=str(grp),
                hovertemplate=f"{axis}=%{{y:.4f}} rad/s<br>t=%{{x:.3f}} s<extra></extra>",
            ),
            row=1, col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=t_ds, y=u_ds,
                mode="lines",
                name=f"{axis} setpoint",
                legendgroup=str(grp),
                hovertemplate=f"{axis}_sp=%{{y:.4f}}<br>t=%{{x:.3f}} s<extra></extra>",
            ),
            row=2, col=1,
        )

    # SINDy fit panel.
    if fit_result is not None:
        t_fit = fit_result["t"]
        dx_measured = fit_result["dx_measured"]
        dx_pred = fit_result["dx_pred"]
        coef_names = fit_result["coef_names"]
        coefs = fit_result["coefs"]
        r2_train = fit_result["r2_train"]
        r2_test = fit_result["r2_test"]

        fig.add_trace(
            go.Scatter(
                x=t_fit, y=dx_measured, mode="lines",
                name="dx/dt measured", legendgroup="fit",
                line=dict(color="#1f77b4"),
                hovertemplate="dx_meas=%{y:.4f}<br>t=%{x:.3f} s<extra></extra>",
            ),
            row=3, col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=t_fit, y=dx_pred, mode="lines",
                name="dx/dt SINDy", legendgroup="fit",
                line=dict(color="#d62728", dash="dash"),
                hovertemplate="dx_sindy=%{y:.4f}<br>t=%{x:.3f} s<extra></extra>",
            ),
            row=3, col=1,
        )
        fig.add_trace(
            go.Bar(
                x=coef_names, y=coefs,
                name="active coefs", legendgroup="fit",
                hovertemplate="%{x}: %{y:.4f}<extra></extra>",
            ),
            row=3, col=1, secondary_y=True,
        )
        fig.add_annotation(
            text=f"R² train={r2_train:.3f} · R² test={r2_test:.3f}",
            xref="paper", yref="paper",
            x=0.01, y=0.10, showarrow=False,
            bgcolor="rgba(255,255,255,0.85)", bordercolor="#444", borderwidth=1,
            font=dict(size=12),
        )

    # Layout.
    fig.update_layout(
        template="plotly_white",
        title=title or "SINDy viewer",
        hovermode="x unified",
        height=900 if fit_result is not None else 700,
        legend=dict(orientation="h", y=1.02, x=0.0),
        margin=dict(t=80, b=40, l=60, r=20),
    )
    fig.update_xaxes(title_text="time (s)", row=n_rows, col=1)
    fig.update_yaxes(title_text="rate (rad/s)", row=1, col=1)
    fig.update_yaxes(title_text="setpoint", row=2, col=1)
    if fit_result is not None:
        fig.update_yaxes(title_text="dx/dt (rad/s²)", row=3, col=1, secondary_y=False)
        fig.update_yaxes(title_text="coef", row=3, col=1, secondary_y=True)
    # Range slider on the bottom subplot only.
    fig.update_xaxes(rangeslider=dict(visible=True), row=n_rows, col=1)
    # Disable range slider on intermediate rows so we get exactly one slider.
    for r in range(1, n_rows):
        fig.update_xaxes(rangeslider=dict(visible=False), row=r, col=1)

    # Dropdown menu — toggles legendgroup visibility.
    axis_buttons = [{"label": "All", "method": "restyle", "args": [{"visible": True}]}]
    visible_mask = [True] * len(fig.data)
    for axis in AXES:
        # Compute visibility mask: only traces whose legendgroup starts with
        # the axis ordinal remain visible.
        group_idx = AXES.index(axis) + 1
        args_mask = []
        for tr in fig.data:
            lg = tr.legendgroup
            if lg == str(group_idx):
                args_mask.append(True)
            elif lg == "fit":
                args_mask.append(True)
            else:
                args_mask.append(False)
        axis_buttons.append({
            "label": f"{axis.capitalize()} only",
            "method": "restyle",
            "args": [{"visible": args_mask}],
        })
    fig.update_layout(
        updatemenus=[{
            "buttons": axis_buttons,
            "direction": "down",
            "showactive": True,
            "x": 1.15, "xanchor": "left",
            "y": 1.0, "yanchor": "top",
        }]
    )
    return fig


def view_ulog(
    ulog_path: str | Path,
    out_html: str | Path,
    *,
    fit: bool = False,
    downsamples_to: int = 5000,
    title: Optional[str] = None,
) -> dict:
    """Build an interactive Plotly HTML viewer for one PX4 ulog file.

    Parameters
    ----------
    ulog_path
        Path to a PX4 ``.ulog`` file.
    out_html
        Destination HTML path. The sibling ``plotly.min.js`` is written
        next to it (``include_plotlyjs="directory"``).
    fit
        If True, also run ``preprocess_px4`` + ``fit_sindy("linear")`` on
        the roll axis and add the result as a third subplot panel.
    downsamples_to
        Maximum samples per trace after uniform-stride downsampling.
    title
        Optional HTML title.

    Returns
    -------
    dict
        ``log_path``, ``n_samples``, ``axis_coverage``, ``fit_result``
        (None or dict with ``library`` / ``r2_train`` / ``r2_test`` /
        ``coefs`` / ``coef_names`` / ``t`` / ``dx_measured`` / ``dx_pred``),
        ``html_path``, ``html_size_bytes``.
    """
    ulog_path = Path(ulog_path)
    out_html = Path(out_html)
    out_html.parent.mkdir(parents=True, exist_ok=True)

    datasets: dict[str, FlightDataset] = {}
    n_samples = 0
    for axis in AXES:
        ds = _load_axis(ulog_path, axis)
        if ds is None:
            continue
        datasets[axis] = ds
        n_samples = max(n_samples, ds.n_samples)
    axis_coverage = sorted(datasets.keys())

    fit_result: Optional[dict] = None
    if fit and "roll" in datasets:
        fit_result = _fit_roll(datasets["roll"])

    page_title = title or f"SINDy viewer — {ulog_path.name}"
    fig = _build_figure(
        datasets, fit_result=fit_result,
        title=f"{page_title} · [{datasets['roll'].t[0]:.2f} s .. {datasets['roll'].t[-1]:.2f} s]"
        if "roll" in datasets else page_title,
    )

    pio.write_html(
        fig,
        file=str(out_html),
        include_plotlyjs="directory",
        full_html=True,
        auto_open=False,
    )
    html_size_bytes = out_html.stat().st_size

    fit_meta: Optional[dict] = None
    if fit_result is not None:
        fit_meta = {
            "library": fit_result["library"],
            "r2_train": fit_result["r2_train"],
            "r2_test": fit_result["r2_test"],
            "n_active_terms": int(fit_result["n_active_terms"]),
            "coefs": [float(c) for c in fit_result["coefs"]],
            "coef_names": list(fit_result["coef_names"]),
        }

    return {
        "log_path": str(ulog_path),
        "n_samples": int(n_samples),
        "axis_coverage": axis_coverage,
        "fit_result": fit_meta,
        "html_path": str(out_html),
        "html_size_bytes": int(html_size_bytes),
    }


def _fit_roll(ds: FlightDataset) -> dict:
    """Run ``preprocess_px4`` + linear-fit on a roll dataset.

    The standard ``fit_sindy(..., library="linear")`` helper requires 3
    features (``[e, x, xm]``), but for the PX4 case we have only ``x``.
    We assemble the equivalent linear fit here: ``dx/dt ≈ coef_x * x``,
    matching PySINDy's ``IdentityLibrary`` on a single column.

    Returns a flat dict so the viewer does not need to import the fitter's
    dataclasses.
    """
    from sim.sindy.preprocessor import preprocess_px4

    pp = preprocess_px4(ds)
    dt = float(pp.t[1] - pp.t[0]) if len(pp.t) > 1 else 0.0
    sindy = _linear_fit_1feature(pp.X[:, 0], pp.dXdt[:, 0])

    # Apply the learned linear coefficient to predict dx_pred for every sample.
    dx_pred = sindy["coefs"][0] * pp.X[:, 0]

    return {
        "library": sindy["library"],
        "r2_train": float(sindy["r2_train"]),
        "r2_test": float(sindy["r2_test"]),
        "n_active_terms": int(sindy["n_active_terms"]),
        "coefs": [float(c) for c in sindy["coefs"]],
        "coef_names": list(sindy["coef_names"]),
        "t": pp.t,
        "dx_measured": pp.dXdt[:, 0],
        "dx_pred": np.asarray(dx_pred).flatten(),
    }


def _linear_fit_1feature(x: np.ndarray, dx: np.ndarray) -> dict:
    """One-feature linear least-squares: ``dx ≈ coef_x * x``.

    PySINDy's ``fit_sindy`` rejects single-column input by design (it is
    scoped for the canonical ``[e, x, xm]`` problem). For the PX4 demo we
    re-implement the equivalent here using ``numpy.linalg.lstsq``.

    Splits samples 80/20 (deterministic), reports R² on each half.
    """
    n = len(x)
    rng = np.random.RandomState(42)
    indices = rng.permutation(n)
    n_train = max(int(0.8 * n), 10)
    train_idx = indices[:n_train]
    test_idx = indices[n_train:]

    X_train = np.column_stack([x[train_idx]])
    y_train = dx[train_idx]
    coef, *_ = np.linalg.lstsq(X_train, y_train, rcond=None)

    y_pred_train = X_train @ coef
    r2_train = _r2(y_train, y_pred_train)

    if len(test_idx) > 1:
        X_test = np.column_stack([x[test_idx]])
        y_test = dx[test_idx]
        y_pred_test = X_test @ coef
        r2_test = _r2(y_test, y_pred_test)
    else:
        r2_test = r2_train

    abs_coefs = np.abs(coef)
    n_active = int(np.sum(abs_coefs > 0.05 * max(abs_coefs.max(), 1e-12)))

    return {
        "library": "linear",
        "coefs": [float(c) for c in coef.flatten()],
        "coef_names": ["x"],
        "r2_train": float(r2_train),
        "r2_test": float(r2_test),
        "n_active_terms": n_active,
    }


def _r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    ss_res = float(np.sum((y_true - y_pred) ** 2))
    ss_tot = float(np.sum((y_true - np.mean(y_true)) ** 2))
    if ss_tot == 0:
        return 1.0
    return float(1.0 - ss_res / ss_tot)
