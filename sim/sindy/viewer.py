"""Interactive Plotly HTML viewer for the SINDy pipeline on PX4 ``.ulog`` data.

Single-file viewer. Produces one self-contained HTML page with a
**tabbed** UI:

- **Per-axis tabs** (Roll / Pitch / Yaw, one per available axis). Top
  panel: body-rate and setpoint traces on a shared time axis. Bottom
  panel: a **comprehensive fit view** showing
    - measured ``dx/dt`` vs SINDy prediction overlay,
    - a coefficient bar chart sorted by magnitude with the dominant
      terms highlighted,
    - per-feature contribution traces (each togglable — see below),
    - a metrics block reporting R², MSE, RMSE, MAE, NRMSE on train and
      test, plus ``n_active_terms`` and the feature list.
- **Joint tab** (only shown when roll + pitch + yaw are all available).
  Polynomial degree-2 features in the 6-vector ``[x_r, x_p, x_y, u_r,
  u_p, u_y]`` — 27 features. One OLS per output axis (3 outputs).
  Same bar chart + metrics structure.

Togglable features
------------------
Two flavours:

- **Per-feature visibility** (always on). Each feature has a "contrib"
  scatter trace showing ``coef_i * Phi_i`` over time. Clicking the
  legend entry toggles its visibility — this is Plotly's built-in
  behaviour. The bar chart entries also toggle.
- **Scenario dropdown** (buttons updatemenu). For each fit we
  precompute a small set of scenarios: the full model, plus one
  scenario per dropped feature. Switching scenarios swaps which
  set of bar / pred / contrib traces is visible. Capped at
  ``MAX_SCENARIOS`` per fit to bound HTML size.

The math lives in ``sim.sindy.fit_panel``. This module is purely
Plotly rendering.

The HTML is written with ``pio.write_html(..., include_plotlyjs="directory")``
so the report works offline — a sibling ``plotly.min.js`` is written
next to ``out_html``.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots

from sim.sindy.flight_loader import FlightDataset
from sim.sindy.adapters.ulog import load_ulog
from sim.sindy.fit_panel import (
    FitConfig,
    JOINT_FEATURE_NAMES,
    per_axis_fit,
    joint_fit,
    per_axis_feature_names,
)


AXES: tuple[str, ...] = ("roll", "pitch", "yaw")
DOMINANT_K: int = 3
MAX_SCENARIOS: int = 12
JOINT_TOPK_BARS: int = 12


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def view_ulog(
    ulog_path: str | Path,
    out_html: str | Path,
    *,
    fit: bool = False,
    downsamples_to: int = 5000,
    title: Optional[str] = None,
    cfg: Optional[FitConfig] = None,
) -> dict:
    """Build an interactive Plotly HTML viewer for one PX4 ulog file."""
    ulog_path = Path(ulog_path)
    out_html = Path(out_html)
    out_html.parent.mkdir(parents=True, exist_ok=True)

    datasets: dict[str, FlightDataset] = {}
    n_samples = 0
    for axis in AXES:
        ds = load_ulog(ulog_path, axis=axis)
        if ds is None:
            continue
        datasets[axis] = ds  # type: ignore[assignment]
        n_samples = max(n_samples, ds.n_samples)
    axis_coverage = sorted(datasets.keys())

    fit_payloads: Optional[dict] = None
    if fit and datasets:
        fit_payloads = _build_fit_payloads(datasets, cfg or FitConfig())

    page_title = title or f"SINDy viewer — {ulog_path.name}"
    fig = _build_figure(
        datasets,
        fit_payloads=fit_payloads,
        downsamples_to=downsamples_to,
        title=_build_title(page_title, datasets, n_samples),
    )

    pio.write_html(
        fig,
        file=str(out_html),
        include_plotlyjs="directory",
        full_html=True,
        auto_open=False,
    )
    html_size_bytes = out_html.stat().st_size

    fit_meta = _summarise_fit_payloads(fit_payloads) if fit_payloads else None

    return {
        "log_path": str(ulog_path),
        "n_samples": int(n_samples),
        "axis_coverage": axis_coverage,
        "fit_result": fit_meta,
        "html_path": str(out_html),
        "html_size_bytes": int(html_size_bytes),
    }


# ---------------------------------------------------------------------------
# Fit payloads — precompute scenarios
# ---------------------------------------------------------------------------

def _build_fit_payloads(
    datasets: dict[str, FlightDataset],
    cfg: FitConfig,
) -> dict:
    """Precompute scenarios for every available axis + the joint fit."""
    payloads: dict = {"per_axis": {}, "joint": None}
    for axis, ds in datasets.items():
        scenarios, t_data, x_data, u_data = _per_axis_scenarios(
            ds.t, ds.x, ds.u, axis, cfg
        )
        payloads["per_axis"][axis] = {
            "axis": axis,
            "feature_names": list(per_axis_feature_names(cfg)),
            "scenarios": scenarios,
            "active_idx": 0,
            # stash raw data so the per-feature contribution traces
            # can be rebuilt without re-running the fitter
            "_t": t_data, "_x": x_data, "_u": u_data, "_cfg": cfg,
        }
    if all(ax in datasets for ax in AXES):
        per_axis_full = {ax: (datasets[ax].t, datasets[ax].x, datasets[ax].u) for ax in AXES}
        scenarios = _joint_scenarios(per_axis_full, cfg)
        payloads["joint"] = scenarios
    return payloads


def _per_axis_scenarios(
    t: np.ndarray, x: np.ndarray, u: np.ndarray, axis: str, cfg: FitConfig,
) -> tuple[list, np.ndarray, np.ndarray, np.ndarray]:
    """Full per-axis fit plus drop-one scenarios."""
    feat_names = list(per_axis_feature_names(cfg))
    n_features = len(feat_names)
    full = per_axis_fit(t, x, u, cfg=cfg, label=axis)
    scenarios: list[dict] = [
        {"label": "Full model", "description": "all features", "result": full}
    ]
    for j in range(n_features):
        mask = np.ones(n_features, dtype=bool)
        mask[j] = False
        res = per_axis_fit(t, x, u, cfg=cfg, label=axis, feature_mask=mask)
        scenarios.append({
            "label": f"Without {feat_names[j]}",
            "description": f"drop {feat_names[j]}",
            "result": res,
        })
    return scenarios, t, x, u


def _joint_scenarios(
    per_axis_data: dict, cfg: FitConfig,
) -> dict:
    """Joint fit + drop-one scenarios, capped at MAX_SCENARIOS by R²."""
    n_features = len(JOINT_FEATURE_NAMES)
    full = joint_fit(per_axis_data, cfg=cfg)
    candidates: list[dict] = [{
        "label": "Full model", "description": "all 27 features", "result": full,
        "r2_train_avg": float(np.mean([full["metrics_per_axis"][a]["r2_train"] for a in AXES])),
    }]
    for j in range(n_features):
        mask = np.ones(n_features, dtype=bool)
        mask[j] = False
        try:
            res = joint_fit(per_axis_data, cfg=cfg, feature_mask=mask)
            r2_avg = float(np.mean([res["metrics_per_axis"][a]["r2_train"] for a in AXES]))
        except ValueError:
            continue
        candidates.append({
            "label": f"Without {JOINT_FEATURE_NAMES[j]}",
            "description": f"drop {JOINT_FEATURE_NAMES[j]}",
            "result": res,
            "r2_train_avg": r2_avg,
        })
    rest = sorted(candidates[1:], key=lambda c: -c["r2_train_avg"])
    keep = rest[: MAX_SCENARIOS - 1]
    scenarios = [candidates[0], *keep]
    return {
        "axis": "joint",
        "feature_names": list(JOINT_FEATURE_NAMES),
        "scenarios": scenarios,
        "active_idx": 0,
    }


def _summarise_fit_payloads(payloads: Optional[dict]) -> Optional[dict]:
    """JSON-friendly summary of the active scenarios."""
    if payloads is None:
        return None
    per_axis_summary = {}
    for axis, payload in payloads.get("per_axis", {}).items():
        active = payload["scenarios"][payload["active_idx"]]
        per_axis_summary[axis] = _summarise_scenario(active)
    joint_summary = None
    if payloads.get("joint"):
        active = payloads["joint"]["scenarios"][payloads["joint"]["active_idx"]]
        joint_summary = {
            "library": active["result"]["library"],
            "metrics_per_axis": active["result"]["metrics_per_axis"],
            "coefs": active["result"]["coefs"].tolist(),
            "feature_names": active["result"]["feature_names"],
            "active_idx": payloads["joint"]["active_idx"],
            "n_scenarios": len(payloads["joint"]["scenarios"]),
        }
    return {"per_axis": per_axis_summary, "joint": joint_summary}


def _summarise_scenario(scenario: dict) -> dict:
    res = scenario["result"]
    return {
        "label": scenario["label"],
        "library": res["library"],
        "metrics": res["metrics"],
        "coefs": [float(c) for c in res["coefs"]],
        "feature_names": list(res["feature_names"]),
    }


# ---------------------------------------------------------------------------
# Figure construction
# ---------------------------------------------------------------------------

def _build_figure(
    datasets: dict[str, FlightDataset],
    *,
    fit_payloads: Optional[dict],
    downsamples_to: int,
    title: str,
) -> go.Figure:
    """Build the multi-tab Plotly figure via the standard tab workaround:
    one Figure containing all traces for all tabs; visibility toggled by
    a buttons updatemenu acting as a tab bar.
    """
    # ----- Per-axis tabs (or placeholder) -----
    per_axis_figs: list[tuple[str, go.Figure]] = []
    for axis in AXES:
        ds = datasets.get(axis)
        if ds is None:
            per_axis_figs.append((axis.capitalize(), _placeholder_fig(f"axis '{axis}' missing in this log")))
            continue
        payload = fit_payloads["per_axis"].get(axis) if fit_payloads else None
        per_axis_figs.append((axis.capitalize(), _build_axis_tab(
            axis=axis, ds=ds, payload=payload, downsamples_to=downsamples_to,
        )))

    # ----- Joint tab -----
    if fit_payloads and fit_payloads.get("joint") and all(a in datasets for a in AXES):
        joint_fig = _build_joint_tab(
            payload=fit_payloads["joint"], downsamples_to=downsamples_to,
        )
    else:
        joint_fig = _placeholder_fig("joint cross-axis fit unavailable (need roll + pitch + yaw in this log)")

    return _wrap_tabs(
        [*per_axis_figs, ("Joint", joint_fig)],
        title=title,
    )


def _placeholder_fig(message: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text=message, xref="paper", yref="paper",
        x=0.5, y=0.5, showarrow=False,
        font=dict(size=18, color="#888"),
    )
    fig.update_layout(
        template="plotly_white",
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        margin=dict(t=40, b=40, l=40, r=40),
    )
    return fig


# ---------------------------------------------------------------------------
# Per-axis tab
# ---------------------------------------------------------------------------

def _build_axis_tab(
    *,
    axis: str,
    ds: FlightDataset,
    payload: Optional[dict],
    downsamples_to: int,
) -> go.Figure:
    """One per-axis tab. Layout (no fit): 2 rows. (with fit): 4 rows."""
    if payload is None:
        return _make_axis_timeseries_fig(axis, ds, downsamples_to)

    n_rows = 4
    fig = make_subplots(
        rows=n_rows, cols=1,
        shared_xaxes=False,
        vertical_spacing=0.06,
        row_heights=[0.28, 0.18, 0.30, 0.24],
        specs=[
            [{"secondary_y": False}],
            [{"secondary_y": False}],
            [{"secondary_y": False}],
            [{"secondary_y": True}],
        ],
        subplot_titles=(
            f"{axis} body rate (rad/s)",
            f"{axis} setpoint",
            f"{axis} fit: measured vs predicted dx/dt",
            f"{axis} coefficients (bars) — per-feature contributions overlay",
        ),
    )

    t_ds, x_ds, u_ds = _downsample_triplet(ds.t, ds.x, ds.u, downsamples_to)
    # Top time-series — single shared set of traces regardless of scenario
    fig.add_trace(
        go.Scatter(
            x=t_ds, y=x_ds, mode="lines",
            name=f"{axis} rate (rad/s)",
            legendgroup=f"ax_{axis}_raw",
            line=dict(color="#1f77b4"),
            hovertemplate=f"{axis}_rate=%{{y:.4f}} rad/s<br>t=%{{x:.3f}} s<extra></extra>",
        ),
        row=1, col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=t_ds, y=u_ds, mode="lines",
            name=f"{axis} setpoint",
            legendgroup=f"ax_{axis}_raw",
            line=dict(color="#ff7f0e"),
            hovertemplate=f"{axis}_sp=%{{y:.4f}}<br>t=%{{x:.3f}} s<extra></extra>",
        ),
        row=2, col=1,
    )

    # Fit panel — precomputed scenarios, one set of traces each
    _populate_axis_fit_panel(fig, payload, row_dx=3, row_bars=4)

    fig.update_layout(
        template="plotly_white",
        height=1100,
        margin=dict(t=80, b=40, l=60, r=20),
        hovermode="x unified",
        legend=dict(orientation="h", y=1.04, x=0.0),
        updatemenus=[_scenario_updatemenu(payload, kind="per_axis")],
        annotations=list(fig.layout.annotations) + [
            dict(
                text=_axis_metrics_html(payload),
                xref="paper", yref="paper",
                x=0.0, y=-0.07, xanchor="left", yanchor="top",
                showarrow=False, align="left",
                font=dict(family="monospace", size=10),
                bgcolor="rgba(255,255,255,0.92)", bordercolor="#444", borderwidth=1,
            )
        ],
    )
    fig.update_yaxes(title_text="rate", row=1, col=1)
    fig.update_yaxes(title_text="setpoint", row=2, col=1)
    fig.update_yaxes(title_text="dx/dt (rad/s²)", row=3, col=1)
    fig.update_yaxes(title_text="coef", row=4, col=1, secondary_y=False)
    fig.update_yaxes(title_text="contribution", row=4, col=1, secondary_y=True)
    fig.update_xaxes(title_text="time (s)", row=2, col=1)
    fig.update_xaxes(title_text="time (s)", row=3, col=1)
    fig.update_xaxes(title_text="time (s)", row=4, col=1)
    fig.update_xaxes(rangeslider=dict(visible=True), row=2, col=1)
    fig.update_xaxes(rangeslider=dict(visible=False), row=1, col=1)
    fig.update_xaxes(rangeslider=dict(visible=False), row=3, col=1)
    fig.update_xaxes(rangeslider=dict(visible=False), row=4, col=1)
    return fig


def _make_axis_timeseries_fig(
    axis: str, ds: FlightDataset, downsamples_to: int,
) -> go.Figure:
    """Per-axis tab with no fit."""
    t_ds, x_ds, u_ds = _downsample_triplet(ds.t, ds.x, ds.u, downsamples_to)
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.07,
        subplot_titles=(f"{axis} body rate", f"{axis} setpoint"),
    )
    fig.add_trace(
        go.Scatter(
            x=t_ds, y=x_ds, mode="lines", name=f"{axis} rate (rad/s)",
            line=dict(color="#1f77b4"),
            hovertemplate=f"{axis}=%{{y:.4f}}<br>t=%{{x:.3f}} s<extra></extra>",
        ),
        row=1, col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=t_ds, y=u_ds, mode="lines", name=f"{axis} setpoint",
            line=dict(color="#ff7f0e"),
            hovertemplate=f"{axis}_sp=%{{y:.4f}}<br>t=%{{x:.3f}} s<extra></extra>",
        ),
        row=2, col=1,
    )
    fig.update_layout(
        template="plotly_white",
        height=600, hovermode="x unified",
        legend=dict(orientation="h", y=1.04, x=0.0),
        margin=dict(t=80, b=40, l=60, r=20),
    )
    fig.update_yaxes(title_text="rad/s", row=1, col=1)
    fig.update_yaxes(title_text="setpoint", row=2, col=1)
    fig.update_xaxes(rangeslider=dict(visible=True), row=2, col=1)
    return fig


def _populate_axis_fit_panel(
    fig: go.Figure, payload: dict, *, row_dx: int, row_bars: int,
) -> None:
    """Add the per-axis fit traces (one set per scenario).

    Trace order per scenario:
      - 1 predicted dx/dt line
      - 1 bar chart
      - N contribution lines (one per nonzero coef)
    Plus a single measured dx/dt line at the very top (always visible).
    The scenario updatemenu uses the order to build a visibility list.
    """
    scenarios = payload["scenarios"]
    t_full = scenarios[0]["result"]["t"]
    t_stash = payload["_t"]; x_stash = payload["_x"]; u_stash = payload["_u"]
    cfg = payload["_cfg"]
    from sim.sindy.fit_panel import per_axis_features

    # measured (always visible)
    fig.add_trace(
        go.Scatter(
            x=t_full, y=scenarios[0]["result"]["y_true"], mode="lines",
            name="dx/dt measured",
            line=dict(color="#1f77b4", width=2),
            legendgroup="dx_meas",
            hovertemplate="dx_meas=%{y:.4f}<br>t=%{x:.3f} s<extra></extra>",
        ),
        row=row_dx, col=1,
    )

    n_features = len(payload["feature_names"])

    # Visibility bookkeeping: a list of bool lists per scenario.
    # Index order matches the order traces are added to fig.data.
    payload["_visibility_lists"] = []
    visible_first = [True] + [False] * (
        1 +  # measured (already added; always visible)
        0    # not counted here — measured is always-on, separate
    )

    # We need to know, for each scenario, which trace positions belong to it.
    # Start by indexing the measured trace as 0, then each scenario gets
    # 1 pred + 1 bar + K contrib lines (where K = #nonzero coefs in the scenario).
    payload["_scenario_trace_spans"] = []  # list of (start, end) into fig.data

    cursor = 1  # 0 is the measured trace; cursor is the next index
    for s_idx, scenario in enumerate(scenarios):
        res = scenario["result"]
        # Predicted dx/dt
        fig.add_trace(
            go.Scatter(
                x=t_full, y=res["y_pred"], mode="lines",
                name=f"dx/dt predicted — {scenario['label']}",
                line=dict(color="#d62728", width=2, dash="dash"),
                legendgroup=f"ax_pred_{s_idx}",
                visible=(s_idx == 0),
                hovertemplate="dx_pred=%{y:.4f}<br>t=%{x:.3f} s<extra></extra>",
            ),
            row=row_dx, col=1,
        )
        cursor += 1

        # Coefficient bar chart (sorted by magnitude)
        coefs = res["coefs"]
        feat_names = res["feature_names"]
        order = np.argsort(-np.abs(coefs))
        sorted_names = [feat_names[k] for k in order]
        sorted_coefs = coefs[order]
        bar_colors = ["#d62728" if k < DOMINANT_K else "#7f7f7f" for k in range(len(sorted_names))]
        fig.add_trace(
            go.Bar(
                x=sorted_names, y=sorted_coefs,
                name=f"coefs — {scenario['label']}",
                legendgroup=f"ax_bar_{s_idx}",
                visible=(s_idx == 0),
                marker=dict(color=bar_colors),
                hovertemplate="%{x}: %{y:.4f}<extra></extra>",
            ),
            row=row_bars, col=1, secondary_y=False,
        )
        cursor += 1

        # Per-feature contribution traces — only nonzero coefs
        Phi_full = per_axis_features(x_stash, u_stash, cfg)
        span_start = cursor
        for f_idx, (fname, coef_val) in enumerate(zip(feat_names, coefs)):
            if abs(coef_val) == 0.0:
                continue
            if f_idx >= Phi_full.shape[1]:
                continue
            contrib = coef_val * Phi_full[:, f_idx]
            fig.add_trace(
                go.Scatter(
                    x=t_full, y=contrib, mode="lines",
                    name=f"{fname} (coef={coef_val:+.3f}) — {scenario['label']}",
                    legendgroup=f"ax_contrib_{s_idx}",
                    visible=(s_idx == 0),
                    line=dict(width=1),
                    opacity=0.4,
                    hovertemplate=f"{fname} contrib=%{{y:.4f}}<br>t=%{{x:.3f}} s<extra></extra>",
                ),
                row=row_bars, col=1, secondary_y=True,
            )
            cursor += 1
        payload["_scenario_trace_spans"].append((span_start - 2, cursor))  # pred+bar+contrib

    # Now build the visibility list per scenario.
    n_total = cursor
    visibility_lists = []
    for s_idx, _ in enumerate(scenarios):
        vis = [True] + [False] * (n_total - 1)  # measured always on
        start, end = payload["_scenario_trace_spans"][s_idx]
        for k in range(start, end):
            vis[k] = True
        visibility_lists.append(vis)
    payload["_visibility_lists"] = visibility_lists


# ---------------------------------------------------------------------------
# Joint tab
# ---------------------------------------------------------------------------

def _build_joint_tab(
    *, payload: dict, downsamples_to: int,
) -> go.Figure:
    """Joint cross-axis fit tab. 4-row figure."""
    scenarios = payload["scenarios"]
    t_full = scenarios[0]["result"]["t"]
    fig = make_subplots(
        rows=4, cols=1,
        shared_xaxes=False, vertical_spacing=0.07,
        row_heights=[0.28, 0.28, 0.30, 0.14],
        subplot_titles=(
            "Joint fit: measured dx/dt (all axes)",
            "Joint fit: predicted dx/dt (active scenario)",
            "Joint coefficients — top 12 by mean |coef| (per output axis)",
            "Active scenario: metrics & dominant terms",
        ),
    )
    colors = {"roll": "#1f77b4", "pitch": "#ff7f0e", "yaw": "#2ca02c"}

    # Measured dx (always visible)
    res0 = scenarios[0]["result"]
    for ax_idx, ax in enumerate(AXES):
        fig.add_trace(
            go.Scatter(
                x=t_full, y=res0["y_true"][:, ax_idx], mode="lines",
                name=f"dx_meas {ax}",
                line=dict(color=colors[ax], width=2),
                legendgroup="j_dx_meas",
                hovertemplate=f"dx_meas_{ax}=%{{y:.4f}}<br>t=%{{x:.3f}} s<extra></extra>",
            ),
            row=1, col=1,
        )

    payload["_scenario_trace_spans"] = []
    payload["_visibility_lists"] = []
    cursor = 3  # 3 measured traces at 0..2
    for s_idx, scenario in enumerate(scenarios):
        res = scenario["result"]
        span_start = cursor
        # Predicted dx per axis
        for ax_idx, ax in enumerate(AXES):
            fig.add_trace(
                go.Scatter(
                    x=t_full, y=res["y_pred"][:, ax_idx], mode="lines",
                    name=f"dx_pred {ax} — {scenario['label']}",
                    line=dict(color=colors[ax], dash="dash", width=2),
                    legendgroup=f"j_pred_{s_idx}",
                    visible=(s_idx == 0),
                    hovertemplate=f"dx_pred_{ax}=%{{y:.4f}}<br>t=%{{x:.3f}} s<extra></extra>",
                ),
                row=2, col=1,
            )
            cursor += 1

        # Coef bars — top-K by mean abs across outputs
        coefs = res["coefs"]  # (n_features, 3)
        feat_names = res["feature_names"]
        mean_abs = np.mean(np.abs(coefs), axis=1)
        order = np.argsort(-mean_abs)[:JOINT_TOPK_BARS]
        for ax_idx, ax in enumerate(AXES):
            ax_coefs = coefs[order, ax_idx]
            ax_names = [feat_names[k] for k in order]
            fig.add_trace(
                go.Bar(
                    x=ax_names, y=ax_coefs,
                    name=f"{ax} coefs — {scenario['label']}",
                    legendgroup=f"j_bar_{s_idx}_{ax}",
                    marker=dict(color=colors[ax]),
                    visible=(s_idx == 0),
                    hovertemplate=f"{ax} %{{x}}: %{{y:.4f}}<extra></extra>",
                ),
                row=3, col=1,
            )
            cursor += 1

        payload["_scenario_trace_spans"].append((span_start, cursor))

    n_total = cursor
    visibility_lists = []
    for s_idx, _ in enumerate(scenarios):
        vis = [True] * 3 + [False] * (n_total - 3)  # measured always on
        start, end = payload["_scenario_trace_spans"][s_idx]
        for k in range(start, end):
            vis[k] = True
        visibility_lists.append(vis)
    payload["_visibility_lists"] = visibility_lists

    # Metrics + dominant text in row 4
    metrics_text = _joint_metrics_html(payload)
    fig.add_annotation(
        text=metrics_text, xref="paper", yref="paper",
        x=0.0, y=0.02, xanchor="left", yanchor="bottom",
        showarrow=False, align="left",
        font=dict(family="monospace", size=11),
        bgcolor="rgba(255,255,255,0.95)", bordercolor="#444", borderwidth=1,
    )

    fig.update_layout(
        template="plotly_white",
        height=1200, hovermode="x unified",
        legend=dict(orientation="h", y=1.02, x=0.0),
        margin=dict(t=80, b=40, l=60, r=20),
        updatemenus=[_scenario_updatemenu(payload, kind="joint")],
    )
    fig.update_yaxes(title_text="dx/dt", row=1, col=1)
    fig.update_yaxes(title_text="dx/dt", row=2, col=1)
    fig.update_yaxes(title_text="coef", row=3, col=1)
    fig.update_xaxes(title_text="time (s)", row=2, col=1)
    fig.update_xaxes(title_text="time (s)", row=3, col=1)
    fig.update_xaxes(visible=False, row=4, col=1)
    fig.update_yaxes(visible=False, row=4, col=1)
    fig.update_xaxes(rangeslider=dict(visible=True), row=2, col=1)
    fig.update_xaxes(rangeslider=dict(visible=False), row=1, col=1)
    fig.update_xaxes(rangeslider=dict(visible=False), row=3, col=1)
    return fig


# ---------------------------------------------------------------------------
# Scenario updatemenu
# ---------------------------------------------------------------------------

def _scenario_updatemenu(payload: dict, *, kind: str) -> dict:
    """Build the buttons menu that toggles which scenario is visible."""
    scenarios = payload["scenarios"]
    visibility_lists = payload.get("_visibility_lists", [])
    buttons = []
    for s_idx, scenario in enumerate(scenarios):
        if s_idx < len(visibility_lists):
            vis = visibility_lists[s_idx]
        else:
            # Should not happen if construction is consistent, but fall back
            vis = [True]
        buttons.append({
            "label": scenario["label"],
            "method": "restyle",
            "args": [{"visible": vis}],
        })
    return {
        "buttons": buttons,
        "direction": "down",
        "showactive": True,
        "x": 1.15, "xanchor": "left",
        "y": 1.0, "yanchor": "top",
    }


# ---------------------------------------------------------------------------
# Metrics text
# ---------------------------------------------------------------------------

def _axis_metrics_html(payload: dict) -> str:
    """Per-axis metrics for the active scenario, as HTML for an annotation."""
    s = payload["scenarios"][payload["active_idx"]]["result"]
    m = s["metrics"]
    lines = [
        f"<b>{s.get('label', payload['axis'])} — {m['library']}</b>",
        f"active terms: {m['n_active_terms']}/{m['n_total_terms']}",
        f"R²: train={m['r2_train']:.3f} · test={m['r2_test']:.3f}",
        f"MSE: train={m['mse_train']:.4f} · test={m['mse_test']:.4f}",
        f"RMSE: train={m['rmse_train']:.4f} · test={m['rmse_test']:.4f}",
        f"MAE: train={m['mae_train']:.4f} · test={m['mae_test']:.4f}",
        f"NRMSE: train={m['nrmse_train']:.4f} · test={m['nrmse_test']:.4f}",
        "n_scenarios=" + str(len(payload["scenarios"])),
    ]
    return "<br>".join(lines)


def _joint_metrics_html(payload: dict) -> str:
    """Joint metrics for the active scenario."""
    res = payload["scenarios"][payload["active_idx"]]["result"]
    feat_names = res["feature_names"]
    coefs = res["coefs"]
    mean_abs = np.mean(np.abs(coefs), axis=1)
    order = np.argsort(-mean_abs)
    dominant_lines = ["<b>Dominant features (mean |coef|):</b>"]
    for k in order[:DOMINANT_K + 2]:
        if mean_abs[k] == 0.0:
            continue
        row = ", ".join(f"{ax}={coefs[k, j]:+.3f}" for j, ax in enumerate(AXES))
        dominant_lines.append(
            f"  • {feat_names[k]} (mean|coef|={mean_abs[k]:.3f}; {row})"
        )
    metrics_lines = ["<b>Per-axis metrics (active scenario):</b>"]
    for ax in AXES:
        m = res["metrics_per_axis"][ax]
        metrics_lines.append(
            f"  • {ax}: R²={m['r2_train']:.3f}/{m['r2_test']:.3f} · "
            f"RMSE={m['rmse_train']:.3f}/{m['rmse_test']:.3f} · "
            f"MAE={m['mae_train']:.3f}/{m['mae_test']:.3f} · "
            f"n_active={m['n_active_terms']}/{m['n_total_terms']}"
        )
    return "<br>".join(dominant_lines + [""] + metrics_lines)


# ---------------------------------------------------------------------------
# Tab wrapping
# ---------------------------------------------------------------------------

def _wrap_tabs(
    tab_pairs: list[tuple[str, go.Figure]], *, title: str,
) -> go.Figure:
    """Combine multiple Plotly figures into a tabbed parent figure.

    Plotly doesn't support cross-figure tabs in a single HTML page, so
    we use the standard workaround: one parent Figure containing every
    trace from every tab, with visibility toggled by a buttons
    updatemenu that acts as the tab bar.
    """
    if not tab_pairs:
        return go.Figure()
    parent = tab_pairs[0][1]
    tab_sizes: list[int] = []
    for i, (_, fig) in enumerate(tab_pairs):
        if i > 0:
            for trace in fig.data:
                trace.visible = False
                parent.add_trace(trace)
        tab_sizes.append(len(fig.data))

    tab_buttons = []
    cursor = 0
    for i, (label, _) in enumerate(tab_pairs):
        n = tab_sizes[i]
        vis = [False] * sum(tab_sizes)
        for j in range(cursor, cursor + n):
            vis[j] = True
        cursor += n
        tab_buttons.append({
            "label": label,
            "method": "restyle",
            "args": [{"visible": vis}],
        })
    parent.update_layout(
        template="plotly_white",
        title=title,
        height=1200,
        margin=dict(t=120, b=120, l=60, r=20),
        updatemenus=[
            {
                "buttons": tab_buttons,
                "direction": "right",
                "showactive": True,
                "x": 0.0, "xanchor": "left",
                "y": 1.10, "yanchor": "top",
            }
        ],
    )
    return parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _downsample_uniform(t: np.ndarray, y: np.ndarray, n_target: int) -> tuple[np.ndarray, np.ndarray]:
    n = len(t)
    if n <= n_target or n_target < 2:
        return t, y
    idx = np.linspace(0, n - 1, n_target).astype(int)
    idx = np.unique(idx)
    return t[idx], y[idx]


def _downsample_triplet(
    t: np.ndarray, x: np.ndarray, u: np.ndarray, n_target: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    t_ds, x_ds = _downsample_uniform(t, x, n_target)
    _, u_ds = _downsample_uniform(t, u, n_target)
    return t_ds, x_ds, u_ds


def _build_title(page_title: str, datasets: dict[str, FlightDataset], n_samples: int) -> str:
    if "roll" in datasets:
        ds = datasets["roll"]
        return f"{page_title} · [{ds.t[0]:.2f}s .. {ds.t[-1]:.2f}s] · n={n_samples}"
    return f"{page_title} · n={n_samples}"