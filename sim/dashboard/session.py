"""The dashboard's deep interface.

A :class:`FitSession` is the dashboard's unit of work: one log file, one
basis, one feature mask per axis. Six methods on the surface — load,
mutate to a feature subset, render the three plots per axis, and a
metrics table. Everything else (loading, fitting, downsampling, KPI
computation, plot construction) is hidden behind this interface.

Sub-modules own their own implementations and have no business logic
that callers need to know about.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import scipy.linalg
import scipy.stats
from plotly.subplots import make_subplots

from sim.sindy.fit_panel import (
    FitConfig,
    per_axis_feature_names,
    per_axis_fit,
)
from sim.dashboard.adapters import get_adapter


# ---------------------------------------------------------------------------
# Result of one per-axis fit. Plain dataclass so it's easy to inspect and
# feed straight into a pandas DataFrame for the metrics table.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AxisFit:
    axis: str
    feature_names: tuple[str, ...]
    coefs: np.ndarray            # shape (n_features,), zero for masked
    feature_mask: np.ndarray     # shape (n_features,) bool
    metrics: dict[str, float]    # r2_train / r2_test / rmse_train / ...
    t: np.ndarray
    y_true: np.ndarray
    y_pred: np.ndarray
    train_idx: np.ndarray
    test_idx: np.ndarray
    library: str = "polynomial_per_axis"


# ---------------------------------------------------------------------------
# The session itself.
# ---------------------------------------------------------------------------

class FitSession:
    """One (log, axes, basis) combination, ready to render."""

    def __init__(
        self,
        log_path: Path,
        datasets: dict[str, "object"],
        cfg: FitConfig,
        feature_masks: dict[str, np.ndarray] | None = None,
    ) -> None:
        self.log_path = Path(log_path)
        self.datasets = datasets                       # axis -> FlightDataset
        self.cfg = cfg
        self.feature_masks: dict[str, np.ndarray] = feature_masks or {
            ax: np.ones(len(per_axis_feature_names(cfg)), dtype=bool)
            for ax in datasets
        }

    # ----- construction ----------------------------------------------------

    @classmethod
    def from_log(
        cls,
        path: str | Path,
        cfg: FitConfig | None = None,
    ) -> "FitSession":
        """Load any supported log file and return a session."""
        p = Path(path)
        adapter = get_adapter(p)
        datasets = adapter.load(p)
        if not datasets:
            raise ValueError(f"no axis data found in {p.name}")
        return cls(p, datasets, cfg or FitConfig())

    # ----- mutation --------------------------------------------------------

    def with_feature_subset(self, axis: str, kept: Sequence[int]) -> "FitSession":
        """Return a new session with ``axis`` using only the features at
        indices in ``kept``. Other axes are unchanged."""
        n_features = len(per_axis_feature_names(self.cfg))
        mask = np.zeros(n_features, dtype=bool)
        for i in kept:
            mask[int(i)] = True
        new_masks = dict(self.feature_masks)
        new_masks[axis] = mask
        return FitSession(self.log_path, self.datasets, self.cfg, new_masks)

    # ----- per-axis fit (cached) ------------------------------------------

    def fit(self, axis: str) -> AxisFit:
        """Fit ``axis`` with the current feature mask. Result is cached on
        the session instance so repeated plot calls don't refit."""
        if hasattr(self, "_fit_cache"):
            cache = self._fit_cache
        else:
            cache = self._fit_cache = {}
        if axis in cache:
            return cache[axis]
        ds = self.datasets[axis]
        result = per_axis_fit(
            ds.t, ds.x, ds.u,
            cfg=self.cfg,
            feature_mask=self.feature_masks.get(axis),
            label=axis,
            xm=ds.xm,
            u_nom=ds.u_nom,
        )
        cache[axis] = AxisFit(
            axis=axis,
            feature_names=tuple(result["feature_names"]),
            coefs=result["coefs"],
            feature_mask=result["feature_mask"],
            metrics=result["metrics"],
            t=result["t"],
            y_true=result["y_true"],
            y_pred=result["y_pred"],
            train_idx=result["train_idx"],
            test_idx=result["test_idx"],
            library=result["library"],
        )
        return cache[axis]

    # ----- plots -----------------------------------------------------------

    # Shared Plotly style constants — scientific palette, accessible colours.
    _P = dict(
        primary="#6366F1",   # indigo  — measured, true
        secondary="#F59E0B", # amber   — predicted, setpoint
        error="#EF4444",     # red     — residuals, error
        ok="#22C55E",      # green   — good R2
        accent="#8B5CF6",   # purple  — active terms
        dim="#94A3B8",      # slate   — references, grid
        bg="#ffffff",
        surface="#F8FAFC",
        text="#0F172A",
        subtext="#475569",
    )
    # Hex + alpha equivalents for rgba() properties (Plotly doesn't support #hex+a).
    _GRID = "rgba(148,163,184,0.25)"
    _BAND = "rgba(239,68,68,0.08)"
    _LINE = dict(width=2.0)
    _DOT  = dict(width=1.5, dash="dash")

    def tracking_error(self, axis: str) -> go.Figure:
        """Time-series: rate (x), setpoint (u), tracking error (e)."""
        ds = self.datasets[axis]
        p = self._P

        fig = make_subplots(
            rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.12,
            row_heights=[0.6, 0.4],
        )

        # Row 1 — rate vs setpoint
        fig.add_trace(go.Scatter(
            x=ds.t, y=ds.x, mode="lines", name="rate",
            line=dict(color=p["primary"], **self._LINE),
            hovertemplate="rate=%{y:.4f}<br>t=%{x:.3f} s<extra></extra>",
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=ds.t, y=ds.u, mode="lines", name="setpoint",
            line=dict(color=p["secondary"], **self._DOT),
            hovertemplate="setpt=%{y:.4f}<br>t=%{x:.3f} s<extra></extra>",
        ), row=1, col=1)

        # Row 2 — tracking error with ±3σ band
        fig.add_hline(y=0, line=dict(color=p["dim"], width=1, dash="dot"), row=2, col=1)
        err_std = float(np.std(ds.e))
        fig.add_trace(go.Scatter(
            x=ds.t, y=ds.e, mode="lines", name="error",
            line=dict(color=p["error"], **self._LINE),
            hovertemplate="e=%{y:.4f}<br>t=%{x:.3f} s<extra></extra>",
        ), row=2, col=1)
        if err_std > 1e-6:
            fig.add_trace(go.Scatter(
                x=np.concatenate([ds.t, ds.t[::-1]]),
                y=np.concatenate([ds.e + 3 * err_std, (ds.e - 3 * err_std)[::-1]]),
                fill="toself", fillcolor=self._BAND,
                line=dict(color="rgba(0,0,0,0)"), name="3σ band",
                hoverinfo="skip", showlegend=False,
            ), row=2, col=1)

        # Titles
        for row, label in enumerate(
            [f"<b>{axis.upper()} — rate vs setpoint</b>",
             f"<b>{axis.upper()} — tracking error</b>"], start=1
        ):
            fig.add_annotation(
                text=label,
                x=0.5, y=1.02, xref="paper", yref="paper",
                showarrow=False, font=dict(size=13, color=p["text"]),
                xanchor="center", yanchor="bottom", row=row, col=1,
            )

        fig.update_layout(
            paper_bgcolor=p["bg"], plot_bgcolor=p["surface"],
            font=dict(color=p["text"], size=12, family="Inter, Arial, sans-serif"),
            margin=dict(t=52, b=50, l=62, r=28),
            hovermode="x unified", showlegend=True,
            legend=dict(orientation="h", y=1.08, x=0.0,
                        bgcolor="rgba(0,0,0,0)", borderwidth=0),
            height=520,
        )
        fig.update_xaxes(title_text="Time (s)", row=2, col=1,
                         gridcolor=self._GRID, showgrid=True)
        fig.update_yaxes(title_text="rad/s", row=1, col=1,
                         gridcolor=self._GRID, showgrid=True, tickformat=".2f")
        fig.update_yaxes(title_text="rad/s", row=2, col=1,
                         gridcolor=self._GRID, showgrid=True, tickformat=".3f")
        return fig

    def fit_quality(self, axis: str) -> go.Figure:
        """dx/dt measured vs predicted, with train/test split shaded."""
        fit = self.fit(axis)
        m = fit.metrics
        p = self._P

        fig = go.Figure()
        if len(fit.test_idx) > 0:
            fig.add_vrect(
                x0=float(fit.t[fit.test_idx[0]]),
                x1=float(fit.t[fit.test_idx[-1]]),
                fillcolor="rgba(148,163,184,0.10)", line_width=0,
            )
            fig.add_vline(
                x=float(fit.t[fit.test_idx[0]]),
                line=dict(color=p["dim"], width=1, dash="dot"),
            )
        fig.add_trace(go.Scatter(
            x=fit.t, y=fit.y_true, mode="lines", name="measured",
            line=dict(color=p["primary"], **self._LINE),
            hovertemplate="meas=%{y:.4f}<br>t=%{x:.3f} s<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=fit.t, y=fit.y_pred, mode="lines", name="predicted",
            line=dict(color=p["secondary"], **self._DOT),
            hovertemplate="pred=%{y:.4f}<br>t=%{x:.3f} s<extra></extra>",
        ))
        fig.add_hline(y=0, line=dict(color=p["dim"], width=1, dash="dot"))
        fig.add_annotation(
            text=(
                f"<b>R2 train</b>={m.get('r2_train', 0):.3f}  "
                f"<b>R2 test</b>={m.get('r2_test', 0):.3f}  "
                f"<b>RMSE train</b>={m.get('rmse_train', 0):.4f}  "
                f"<b>RMSE test</b>={m.get('rmse_test', 0):.4f}"
            ),
            x=0.5, y=1.02, xref="paper", yref="paper",
            showarrow=False, font=dict(size=12, color=p["subtext"]),
            xanchor="center", yanchor="bottom",
        )

        fig.update_layout(
            paper_bgcolor=p["bg"], plot_bgcolor=p["surface"],
            font=dict(color=p["text"], size=12, family="Inter, Arial, sans-serif"),
            height=460, margin=dict(t=52, b=50, l=62, r=28),
            hovermode="x unified",
            legend=dict(orientation="h", y=1.06, x=0.0,
                        bgcolor="rgba(0,0,0,0)", borderwidth=0),
        )
        fig.update_xaxes(title_text="Time (s)", gridcolor=self._GRID, showgrid=True)
        fig.update_yaxes(title_text="dx/dt (rad/s2)", tickformat=".3f",
                         gridcolor=self._GRID, showgrid=True)
        return fig

    def coefficient_contributions(self, axis: str) -> go.Figure:
        """Horizontal bar chart of |coef|, coloured by sign, with signed values."""
        fit = self.fit(axis)
        names = list(fit.feature_names)
        coefs = np.asarray(fit.coefs, dtype=np.float64)
        order = np.argsort(-np.abs(coefs))
        sorted_names = [names[i] for i in order]
        sorted_abs = np.abs(coefs[order])
        sorted_sgn = coefs[order]
        p = self._P

        bar_colors = [p["primary"] if v >= 0 else p["error"] for v in sorted_sgn]

        fig = go.Figure(go.Bar(
            y=sorted_names[::-1], x=sorted_abs[::-1],
            orientation="h",
            marker_color=bar_colors[::-1],
            hovertemplate="<b>%{y}</b><br>|Theta|=%{x:.5f}<extra></extra>",
            name="|Theta|",
        ))
        # Signed value annotation in left margin
        for name, val in zip(sorted_names[::-1], sorted_sgn[::-1]):
            sign = "+" if val >= 0 else "-"
            fig.add_annotation(
                x=-0.02, y=name,
                text=f"{sign}{abs(val):.4f}",
                showarrow=False, font=dict(size=10, color=p["subtext"]),
                xref="paper", xanchor="right",
            )

        fig.update_layout(
            paper_bgcolor=p["bg"], plot_bgcolor=p["surface"],
            font=dict(color=p["text"], size=12, family="Inter, Arial, sans-serif"),
            height=max(320, 16 * len(sorted_names)),
            margin=dict(t=30, b=36, l=90, r=80),
            showlegend=False,
            xaxis=dict(title_text="|Theta|", gridcolor=self._GRID, showgrid=True,
                       tickformat=".3f"),
        )
        return fig

    # ----- advanced analysis -------------------------------------------------

    def residual_analysis(self, axis: str) -> go.Figure:
        """Residual diagnostics: time series, histogram, ACF, Q-Q."""
        fit = self.fit(axis)
        residuals = fit.y_true - fit.y_pred
        n = len(residuals)
        p = self._P

        # ACF
        max_lag = max(1, int(n * 0.05))
        acf = np.correlate(
            residuals - residuals.mean(), residuals - residuals.mean(), mode="full"
        )
        acf = acf[n - 1 : n + max_lag]
        acf /= acf[0]
        lags = np.arange(0, max_lag + 1)
        conf = 1.96 / np.sqrt(n)

        # Q-Q: properly scaled theoretical quantiles
        sorted_resid = np.sort(residuals)
        tq = scipy.stats.norm.ppf((np.arange(1, n + 1) - 0.5) / n)

        fig = make_subplots(
            rows=2, cols=2,
            row_heights=[0.5, 0.5],
            horizontal_spacing=0.10,
            vertical_spacing=0.14,
        )
        # Residual time series
        fig.add_trace(go.Scatter(
            x=fit.t, y=residuals, mode="lines",
            line=dict(color=p["primary"], width=1.4),
            name="residual",
            hovertemplate="t=%{x:.3f}<br>r=%{y:.4f}<extra></extra>",
        ), row=1, col=1)
        fig.add_hline(y=0, line=dict(color=p["dim"], width=1, dash="dot"), row=1, col=1)
        # Histogram
        fig.add_trace(go.Histogram(
            x=residuals, nbinsx=40,
            histnorm="probability density",
            marker_color=p["primary"], opacity=0.75,
            name="residuals",
        ), row=1, col=2)
        x_range = np.linspace(residuals.min(), residuals.max(), 200)
        std = max(residuals.std(), 1e-12)
        pdf = np.exp(-0.5 * ((x_range - residuals.mean()) / std) ** 2) / std
        fig.add_trace(go.Scatter(
            x=x_range, y=pdf, mode="lines", name="N(mu,sigma2)",
            line=dict(color=p["secondary"], width=2.5),
        ), row=1, col=2)
        # ACF
        bar_colors = [p["primary"] if abs(v) > conf else p["dim"] for v in acf]
        fig.add_trace(go.Bar(
            x=lags, y=acf, marker_color=bar_colors,
            name="ACF",
            hovertemplate="lag=%{x}<br>acf=%{y:.3f}<extra></extra>",
        ), row=2, col=1)
        fig.add_hline(y=conf, line=dict(color=p["dim"], width=1, dash="dot"), row=2, col=1)
        fig.add_hline(y=-conf, line=dict(color=p["dim"], width=1, dash="dot"), row=2, col=1)
        fig.add_hline(y=0, line=dict(color=p["dim"], width=1), row=2, col=1)
        # Q-Q
        fig.add_trace(go.Scatter(
            x=tq, y=sorted_resid, mode="markers",
            marker=dict(color=p["primary"], size=4),
            name="Q-Q", showlegend=False,
            hovertemplate="theor=%{x:.3f}<br>sample=%{y:.4f}<extra></extra>",
        ), row=2, col=2)
        r_min, r_max = sorted_resid.min(), sorted_resid.max()
        fig.add_trace(go.Scatter(
            x=[r_min, r_max], y=[r_min, r_max],
            mode="lines", line=dict(color=p["secondary"], width=1.5, dash="dash"),
            showlegend=False,
        ), row=2, col=2)

        # Subplot titles
        titles = [
            "Residuals vs time", "Histogram",
            f"ACF (95% CI = {conf:.3f})", "Q-Q plot",
        ]
        for i, txt in enumerate(titles):
            fig.add_annotation(
                text=f"<b>{txt}</b>",
                x=0.5, y=1.06, xref="x domain", yref="paper",
                showarrow=False, font=dict(size=12, color=p["text"]),
                xanchor="center", row=i // 2 + 1, col=i % 2 + 1,
            )

        fig.update_layout(
            paper_bgcolor=p["bg"], plot_bgcolor=p["surface"],
            font=dict(color=p["text"], size=12, family="Inter, Arial, sans-serif"),
            height=600, margin=dict(t=52, b=50, l=62, r=20),
            showlegend=False,
        )
        fig.update_xaxes(title_text="Time (s)", row=1, col=1,
                         gridcolor=self._GRID, showgrid=True)
        fig.update_yaxes(row=1, col=1, gridcolor=self._GRID, showgrid=True)
        fig.update_xaxes(title_text="Time lag", row=2, col=1)
        fig.update_yaxes(title_text="ACF", row=2, col=1)
        return fig

    def threshold_sweep(self, axis: str) -> go.Figure:
        """R2 (train + test) vs STLSQ threshold — model complexity trade-off."""
        fit = self.fit(axis)
        p = self._P

        thresholds = np.logspace(-4, 0, 60)
        r2_train_vals: list[float] = []
        r2_test_vals: list[float] = []
        n_active_vals: list[int] = []

        def _ols(A, b):
            c, *_ = scipy.linalg.lstsq(
                A, b, cond=1e-6, overwrite_a=False, overwrite_b=False
            )
            return np.asarray(c, dtype=np.float64)

        dx = np.asarray(fit.y_true, dtype=np.float64)
        from sim.sindy.fit_panel import per_axis_features, _train_test_split
        ds = self.datasets[axis]
        full_Phi = per_axis_features(
            np.asarray(ds.x, dtype=np.float64),
            np.asarray(ds.u, dtype=np.float64),
            self.cfg,
            xm=np.asarray(ds.xm, dtype=np.float64),
            u_nom=np.asarray(ds.u_nom, dtype=np.float64),
        )
        full_Phi = np.nan_to_num(full_Phi, nan=0.0, posinf=0.0, neginf=0.0)
        train_idx, test_idx = _train_test_split(len(dx), self.cfg)

        for thr in thresholds:
            keep = np.abs(fit.coefs) >= thr
            if not keep.any():
                r2_train_vals.append(float("nan"))
                r2_test_vals.append(float("nan"))
                n_active_vals.append(0)
                continue
            A = full_Phi[train_idx][:, keep]
            c = _ols(A, dx[train_idx])
            y_pred_train = A @ c
            y_pred_test = (
                full_Phi[test_idx][:, keep] @ c if test_idx.size
                else y_pred_train
            )
            for arr, pred, dest in [
                (train_idx, y_pred_train, r2_train_vals),
                (test_idx, y_pred_test, r2_test_vals),
            ]:
                if len(arr) == 0:
                    dest.append(float("nan"))
                    continue
                ss_tot = np.sum((dx[arr] - dx[arr].mean()) ** 2)
                ss_res = np.sum((dx[arr] - pred) ** 2)
                dest.append(1 - ss_res / ss_tot if ss_tot > 0 else 0.0)
            n_active_vals.append(int(keep.sum()))

        fig = make_subplots(rows=1, cols=2, horizontal_spacing=0.14)
        fig.add_trace(go.Scatter(
            x=thresholds, y=r2_train_vals, mode="lines",
            name="R2 train",
            line=dict(color=p["primary"], **self._LINE),
            hovertemplate="thr=%{x:.4f}<br>R2_train=%{y:.3f}<extra></extra>",
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=thresholds, y=r2_test_vals, mode="lines",
            name="R2 test",
            line=dict(color=p["secondary"], **self._LINE),
            hovertemplate="thr=%{x:.4f}<br>R2_test=%{y:.3f}<extra></extra>",
        ), row=1, col=1)
        fig.add_vline(
            x=float(self.cfg.threshold),
            line=dict(color=p["accent"], width=1.5, dash="dot"),
            annotation_text=f"current = {self.cfg.threshold:.3f}",
            annotation_position="top right",
            annotation_font_color=p["subtext"],
            row=1, col=1,
        )
        fig.add_trace(go.Scatter(
            x=thresholds, y=n_active_vals, mode="lines",
            name="active terms",
            line=dict(color=p["accent"], **self._LINE),
            hovertemplate="thr=%{x:.4f}<br>n=%{y}<extra></extra>",
        ), row=1, col=2)

        for col in (1, 2):
            fig.update_xaxes(
                type="log", title_text="STLSQ threshold",
                row=1, col=col, gridcolor=self._GRID, showgrid=True,
            )

        fig.update_layout(
            paper_bgcolor=p["bg"], plot_bgcolor=p["surface"],
            font=dict(color=p["text"], size=12, family="Inter, Arial, sans-serif"),
            height=400, margin=dict(t=52, b=50, l=62, r=20),
            legend=dict(orientation="h", y=1.08, x=0.0,
                        bgcolor="rgba(0,0,0,0)", borderwidth=0),
        )
        fig.update_yaxes(title_text="R2", row=1, col=1,
                         gridcolor=self._GRID, showgrid=True)
        fig.update_yaxes(title_text="n active terms", row=1, col=2,
                         gridcolor=self._GRID, showgrid=True)
        return fig

    def cross_axis_comparison(self) -> go.Figure:
        """Compare R2 and active terms across all axes."""
        rows = []
        for axis in self.axes:
            fit = self.fit(axis)
            rows.append({
                "axis": axis,
                "r2_train": fit.metrics.get("r2_train", float("nan")),
                "r2_test": fit.metrics.get("r2_test", float("nan")),
                "n_active": int(fit.metrics.get("n_active_terms", 0)),
                "n_total": int(fit.metrics.get("n_total_terms", 0)),
            })
        df = pd.DataFrame(rows)
        p = self._P
        palette = [p["primary"], p["secondary"], p["accent"]]

        fig = make_subplots(rows=1, cols=2, horizontal_spacing=0.18)
        for i, row in df.iterrows():
            c = palette[i % len(palette)]
            fig.add_trace(go.Bar(
                x=["train", "test"],
                y=[row["r2_train"], row["r2_test"]],
                name=row["axis"].upper(),
                marker_color=c,
                text=[f"{row['r2_train']:.3f}", f"{row['r2_test']:.3f}"],
                textposition="outside",
                hovertemplate=(
                    f"<b>{row['axis'].upper()}</b><br>"
                    f"train={row['r2_train']:.3f}<br>test={row['r2_test']:.3f}<extra></extra>"
                ),
            ), row=1, col=1)
            fig.add_trace(go.Bar(
                x=[row["axis"].upper()],
                y=[row["n_active"]],
                name=row["axis"].upper(),
                marker_color=c,
                text=f"{row['n_active']}/{row['n_total']}",
                textposition="outside",
                hovertemplate=(
                    f"<b>{row['axis'].upper()}</b><br>"
                    f"{row['n_active']}/{row['n_total']} terms<extra></extra>"
                ),
            ), row=1, col=2)
        fig.add_hline(
            y=1.0, line=dict(color=p["ok"], width=1.5, dash="dash"),
            annotation_text="R2 = 1.0", annotation_font_color=p["subtext"],
            annotation_position="top right", row=1, col=1,
        )
        fig.update_layout(
            paper_bgcolor=p["bg"], plot_bgcolor=p["surface"],
            font=dict(color=p["text"], size=12, family="Inter, Arial, sans-serif"),
            height=380, margin=dict(t=52, b=50, l=62, r=20),
            showlegend=False,
        )
        fig.update_yaxes(title_text="R2", range=[-0.05, 1.12], row=1, col=1,
                         gridcolor=self._GRID, showgrid=True)
        fig.update_yaxes(title_text="n active terms", row=1, col=2,
                         gridcolor=self._GRID, showgrid=True)
        return fig

    def stability_summary(self, axis: str) -> go.Figure:
        """Coefficient table with sign, magnitude, and quality callout."""
        fit = self.fit(axis)
        coefs = np.asarray(fit.coefs, dtype=np.float64)
        names = list(fit.feature_names)
        p = self._P

        active_mask = np.abs(coefs) > 1e-8
        active_names = [n for n, a in zip(names, active_mask) if a]
        active_coefs = coefs[active_mask]

        rows_data = []
        for n, c in sorted(zip(active_names, active_coefs), key=lambda x: -abs(x[1])):
            sign = "+" if c >= 0 else "-"
            sign_color = p["ok"] if c >= 0 else p["error"]
            rows_data.append((f"<b>{n}</b>", sign, f"{c:.5f}", sign_color))

        r2 = fit.metrics.get("r2_test", float("nan"))
        if r2 < 0:
            quality = ("no predictive power", p["error"])
        elif r2 < 0.5:
            quality = ("moderate fit", p["secondary"])
        elif r2 < 0.8:
            quality = ("good fit", p["ok"])
        else:
            quality = ("excellent fit", p["ok"])

        fig = go.Figure()
        fig.add_trace(go.Table(
            header=dict(
                values=["<b>Feature</b>", "<b>Sign</b>", "<b>Theta</b>"],
                fill_color=p["primary"],
                font_color="#ffffff",
                font_size=13,
                align="left",
                height=34,
            ),
            cells=dict(
                values=[list(t) for t in zip(*rows_data)] if rows_data
                        else [["--"], ["--"], ["--"]],
                fill_color=[[p["surface"]] * len(rows_data)],
                font_color=[[r[3] for r in rows_data]] if rows_data
                           else [[p["subtext"]] * 3],
                font_size=12,
                align="left",
                height=28,
            ),
        ))
        fig.add_annotation(
            text=(
                f"<b>Stability</b>: {quality[0]} -- "
                f"R2 test = {r2:.3f}. "
                f"{len(active_names)}/{len(names)} terms active."
            ),
            x=0.5, y=-0.08, xref="paper", yref="paper",
            showarrow=False, font=dict(size=12, color=quality[1]),
            xanchor="center",
        )
        fig.update_layout(
            paper_bgcolor=p["bg"],
            font=dict(color=p["text"], size=12, family="Inter, Arial, sans-serif"),
            height=max(220, 60 + len(rows_data) * 30 + 40),
            margin=dict(t=30, b=36, l=10, r=10),
        )
        return fig

    # ----- summary ---------------------------------------------------------

    def metrics_table(self) -> pd.DataFrame:
        rows = []
        for axis in self.datasets:
            fit = self.fit(axis)
            kept = fit.feature_mask.sum()
            total = len(fit.feature_names)
            rows.append({
                "axis": axis,
                "n_features_used": int(kept),
                "n_features_total": total,
                "r2_train": fit.metrics.get("r2_train", float("nan")),
                "r2_test": fit.metrics.get("r2_test", float("nan")),
                "rmse_train": fit.metrics.get("rmse_train", float("nan")),
                "rmse_test": fit.metrics.get("rmse_test", float("nan")),
                "mae_train": fit.metrics.get("mae_train", float("nan")),
                "mae_test": fit.metrics.get("mae_test", float("nan")),
                "nrmse_train": fit.metrics.get("nrmse_train", float("nan")),
                "nrmse_test": fit.metrics.get("nrmse_test", float("nan")),
            })
        return pd.DataFrame(rows)

    @property
    def axes(self) -> list[str]:
        return list(self.datasets)

    @property
    def feature_options(self) -> list[str]:
        return list(per_axis_feature_names(self.cfg))

    def __repr__(self) -> str:
        return f"FitSession({self.log_path.name}, axes={self.axes})"
