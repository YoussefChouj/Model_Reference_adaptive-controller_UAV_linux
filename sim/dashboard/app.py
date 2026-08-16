"""Streamlit entrypoint — run with:

    .venv/bin/python -m streamlit run sim/dashboard/app.py --server.headless true

The script is intentionally thin: every interaction is ``FitSession`` in,
plotly figure out. State lives in ``st.session_state`` keyed on the file
path so the dashboard remembers which features were toggled off.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from sim.dashboard import FitSession
from sim.dashboard.adapters import list_supported_exts
from sim.sindy.fit_panel import FitConfig


# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="MRAC / SINDy Research Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("MRAC / SINDy Research Dashboard")
st.caption(
    "Interactive fit exploration. Pick a log, toggle features, see the "
    "tracking performance change in real time."
)


# ---------------------------------------------------------------------------
# File picker — searches a few known roots.
# ---------------------------------------------------------------------------

SEARCH_ROOTS = [
    Path("sim/flight_logs"),
    Path("sim/runs"),
    Path("raw/papers/downloads"),
    Path("/tmp"),
]

def _discover_logs() -> list[Path]:
    found: list[Path] = []
    for root in SEARCH_ROOTS:
        if not root.exists():
            continue
        for ext in list_supported_exts():
            found.extend(sorted(root.rglob(f"*{ext}")))
    # de-dup while preserving order
    seen: set[Path] = set()
    out: list[Path] = []
    for p in found:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


with st.sidebar:
    st.header("Log file")
    known = _discover_logs()
    if known:
        choice = st.selectbox(
            "Discovered logs",
            options=["(pick one)"] + [str(p) for p in known],
            index=0,
        )
        uploaded = None
    else:
        st.caption("No logs found in known roots; upload below.")
        choice = "(pick one)"
        uploaded = None
    uploaded = st.file_uploader(
        "…or upload a log file",
        type=list_supported_exts(),
        accept_multiple_files=False,
    )

    if uploaded is not None:
        log_source = Path("/tmp") / uploaded.name
        log_source.write_bytes(uploaded.getbuffer())
        log_path: Path | None = log_source
    elif choice != "(pick one)":
        log_path = Path(choice)
    else:
        log_path = None

    st.divider()
    st.header("Axes")
    axes_enabled: list[str] = []   # filled after session is built

    st.divider()
    st.header("Fit configuration")
    cfg_eps = st.number_input(
        "STLSQ threshold", min_value=0.0, max_value=1.0,
        value=0.05, step=0.01, format="%.3f",
    )
    cfg_max_iter = st.number_input(
        "STLSQ max iterations", min_value=1, max_value=3000, value=5,
    )
    cfg_library = st.selectbox(
        "Feature library",
        options=["extended", "poly"],
        index=0,
        help=(
            "**extended** (default, 22 features): 4 tiers — MRAC basis, polynomial, "
            "nonlinear, cross-xm. Best for exploratory SINDy.\n"
            "**poly** (5–6 features): Simple polynomial [1?, x, u, x², xu, u²]. "
            "Fast, good for comparing against MRAC basis."
        ),
    )
    cfg_include_bias = st.checkbox(
        "Include bias (Φ₀ = 1)",
        value=True,
        help="Adds a constant column so the model can fit a DC offset. "
             "MRAC uses Φ₀ = 1.0 — keep this on unless you know the plant has zero mean error.",
    )
    cfg_train_frac = st.slider(
        "Train fraction", min_value=0.5, max_value=0.95,
        value=0.8, step=0.05,
    )

    run_clicked = st.button(
        "Run fit", type="primary",
        disabled=(log_path is None),
    )

    with st.expander("ℹ️ About the parameters"):
        st.markdown("""
        **Feature library — extended** (default, 21 features across 4 tiers):
        - **MRAC basis** — mirrors `API/mrac.c` Φ: 1 (bias), x, x·tanh(x), cross-coup, u_nom, xm
        - **Polynomial** — x, u, x², x·u, u²
        - **Nonlinear** — tanh(x), |x|, x³, u³, x·u², x²·u, sign(u)
        - **Cross-xm** — x·xm, u·xm, xm² (captures how reference trajectory modulates dynamics)

        **Feature library — poly** (5–6 features): classical polynomial [1?, x, u, x², xu, u²].
        Fast; useful as a baseline to compare against the MRAC basis.

        **STLSQ threshold** — Coefficients with |value| below this are hard-zeroed
        after each iteration. Smaller ⇒ denser model (more terms survive), larger ⇒
        sparser model. Use the **Threshold sweep** tab to find the sweet spot.

        **STLSQ max iterations** — Each iteration re-fits on the kept columns then
        re-thresholds. More iterations let previously-zeroed terms re-enter if the
        supporting columns shift. `5` is usually enough; `1` gives a single thresholded
        OLS (fast, sometimes sufficient).

        **Train fraction** — Fraction of log samples used for fitting; the remainder
        is the held-out test set. The split is deterministic (seed 42) so re-running
        the same config gives the same split.

        **Include bias (Φ₀ = 1)** — Relevant only for the **poly** library (the extended
        library always includes bias as part of the MRAC basis). Adds a constant column
        so the model can fit a DC offset. MRAC uses Φ₀ = 1.0 — keep this on unless you
        know the plant has zero mean error at zero input.
        """)


# ---------------------------------------------------------------------------
# Session — keyed by log path so feature toggles persist across reruns.
# ---------------------------------------------------------------------------

def _session_state_key(path: Path) -> str:
    return f"session::{path.resolve()}"


def _build_session(log_path: Path) -> FitSession:
    cfg = FitConfig(
        feature_library=str(cfg_library),
        include_bias=bool(cfg_include_bias),
        threshold=float(cfg_eps),
        max_iter=int(cfg_max_iter),
        train_fraction=float(cfg_train_frac),
    )
    return FitSession.from_log(log_path, cfg=cfg)


if log_path is not None and run_clicked:
    with st.spinner(f"Loading {log_path.name}…"):
        try:
            st.session_state[_session_state_key(log_path)] = _build_session(log_path)
            st.session_state["active_log"] = str(log_path.resolve())
        except Exception as exc:
            st.error(f"Failed to load {log_path.name}: {exc}")

active_key = st.session_state.get("active_log")
session: FitSession | None = None
if active_key is not None:
    session = st.session_state.get(f"session::{active_key}")


# ---------------------------------------------------------------------------
# Main area
# ---------------------------------------------------------------------------

if session is None:
    st.info("Pick a log file in the sidebar and press **Run fit** to begin.")
    st.stop()


# Show file metadata
meta = next(iter(session.datasets.values())).meta  # type: ignore[attr-defined]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Log file", session.log_path.name)
c2.metric("Axes loaded", ", ".join(session.axes))
c3.metric("Samples", int(next(iter(session.datasets.values())).n_samples))  # type: ignore[attr-defined]
c4.metric(
    "Recorded Hz",
    f"{float(meta.get('recorded_hz', 0)):.1f}"
    if meta.get("recorded_hz") else "—",
)


# ---------------------------------------------------------------------------
# Per-axis sidebar + main layout
# ---------------------------------------------------------------------------

st.subheader("Axes")
axis_cols = st.columns(len(session.axes))
for col, axis in zip(axis_cols, session.axes):
    with col:
        enabled = st.checkbox(f"{axis.upper()}", value=True, key=f"axis::{axis}")
        if enabled:
            axes_enabled.append(axis)

if not axes_enabled:
    st.warning("Select at least one axis in the sidebar.")
    st.stop()


# ---------------------------------------------------------------------------
# Feature selector + plots per axis
# ---------------------------------------------------------------------------

feat_options = session.feature_options
default_kept = list(range(len(feat_options)))   # all on

for axis in axes_enabled:
    st.markdown(f"### {axis.upper()}")

    # Feature toggles — kept set drives the session mutation.
    toggles = st.multiselect(
        f"Features for {axis}",
        options=feat_options,
        default=feat_options,
        key=f"feat::{axis}",
        help="Removing a feature refits the model without that regressor column.",
    )
    kept_idx = [feat_options.index(f) for f in toggles if f in feat_options]
    axis_session = session.with_feature_subset(axis, kept_idx)

    # Cache the per-axis session so plot reruns don't refit.
    cache_key = f"ax_session::{active_key}::{axis}::{','.join(toggles)}"
    if cache_key not in st.session_state:
        st.session_state[cache_key] = axis_session
    axis_session = st.session_state[cache_key]

    tab_err, tab_fit, tab_coef, tab_resid, tab_sweep, tab_stability, tab_metrics = st.tabs([
        "Tracking", "Fit quality", "Coefficients",
        "Residuals", "Threshold sweep", "Stability", "Metrics",
    ])
    with tab_err:
        st.plotly_chart(axis_session.tracking_error(axis))
    with tab_fit:
        st.plotly_chart(axis_session.fit_quality(axis))
    with tab_coef:
        st.plotly_chart(axis_session.coefficient_contributions(axis))
    with tab_resid:
        st.plotly_chart(axis_session.residual_analysis(axis))
    with tab_sweep:
        st.plotly_chart(axis_session.threshold_sweep(axis))
    with tab_stability:
        st.plotly_chart(axis_session.stability_summary(axis))
    with tab_metrics:
        fit = axis_session.fit(axis)
        st.dataframe(
            pd.DataFrame([
                {"metric": k, "value": float(v)}
                for k, v in fit.metrics.items()
                if isinstance(v, (int, float))
            ]),
            hide_index=True, use_container_width=True,
        )


# ---------------------------------------------------------------------------
# Summary table across all axes (uses the latest per-axis session).
# ---------------------------------------------------------------------------

st.divider()
st.subheader("Summary across axes")
st.plotly_chart(session.cross_axis_comparison())
summary_rows = []
for axis in session.axes:
    axis_session = st.session_state.get(
        f"ax_session::{active_key}::{axis}::{','.join(st.session_state.get(f'feat::{axis}', feat_options))}"
    )
    if axis_session is None:
        continue
    fit = axis_session.fit(axis)
    summary_rows.append({
        "axis": axis,
        "n_features": int(fit.feature_mask.sum()),
        "r2_train": fit.metrics.get("r2_train", float("nan")),
        "r2_test": fit.metrics.get("r2_test", float("nan")),
        "rmse_train": fit.metrics.get("rmse_train", float("nan")),
        "rmse_test": fit.metrics.get("rmse_test", float("nan")),
    })
if summary_rows:
    st.dataframe(pd.DataFrame(summary_rows), use_container_width=True)