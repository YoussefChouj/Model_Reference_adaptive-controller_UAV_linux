"""Custom HTML dashboard builder for the SINDy viewer.

Produces a self-contained HTML file with:
- Dark-navy theme (reference: dashboardkpi HTML template)
- Gold accent for active states
- Left sidebar with tab buttons (Roll / Pitch / Yaw / Joint)
- KPI metric strips at the top of each tab
- Embedded Plotly chart (figure embedded as JSON, plotly.js loaded from CDN)
- Coefficient summary table below the chart
- Per-feature toggle via JS (no reload needed)

Architecture:
- Python generates a complete HTML string by rendering the Plotly figure
  to JSON (via ``pio.to_json`` which handles numpy arrays), embedding it
  as a JSON-escaped string, and wrapping it in a custom dashboard shell.
- The JS reads the embedded JSON string, parses it with ``JSON.parse``,
  and renders the Plotly chart in a designated div. No scenario switching
  (all scenarios are precomputed in the JSON; JS swaps which traces are
  visible).

This approach gives us full CSS/HTML control over layout, KPI strips,
sidebar, and typography — while keeping Plotly's interactive zoom/hover.

The HTML template uses:
- Google Fonts: DM Sans (body) + DM Serif Display (headings)
- CSS custom properties for the color system
- Pure CSS grid for layout
- Vanilla JS for tab switching and feature toggles
"""

from __future__ import annotations

import json
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

# ---------------------------------------------------------------------------
# Dark-navy HTML shell template
# ---------------------------------------------------------------------------

_CSS = """
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=DM+Serif+Display&display=swap');

:root {
  --navy:       #0A3476;
  --navy-dark:  #071f4a;
  --navy-mid:  #12428f;
  --gold:       #FCB040;
  --gold-light: #FDD17A;
  --gold-pale:  #FEF0D0;
  --white:      #ffffff;
  --off-white:  #f7f8fc;
  --text:       #e2e8f0;
  --text-muted: #94a3b8;
  --border:     rgba(255,255,255,0.10);
  --sidebar-w:  200px;
  --green:      #22c55e;
  --red:        #ef4444;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: 'DM Sans', sans-serif;
  background: var(--navy-dark);
  color: var(--text);
  height: 100vh;
  overflow: hidden;
}

.container {
  display: flex;
  height: 100vh;
}

/* ── Sidebar ── */
.sidebar {
  width: var(--sidebar-w);
  background: #050e22;
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}

.sidebar-header {
  padding: 1.5rem 1rem;
  border-bottom: 1px solid var(--border);
}

.sidebar-header h1 {
  font-family: 'DM Serif Display', serif;
  font-size: 1rem;
  color: var(--gold);
  line-height: 1.2;
}

.sidebar-header .meta {
  font-size: 0.7rem;
  color: var(--text-muted);
  margin-top: 0.25rem;
  line-height: 1.4;
}

.sidebar nav {
  padding: 0.75rem 0;
  flex: 1;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.65rem 1rem;
  color: var(--text-muted);
  text-decoration: none;
  font-size: 0.85rem;
  cursor: pointer;
  border-left: 3px solid transparent;
  transition: all 0.15s;
  user-select: none;
}

.nav-item:hover {
  background: rgba(252,176,64,0.08);
  color: var(--gold-light);
  border-left-color: rgba(252,176,64,0.3);
}

.nav-item.active {
  background: rgba(252,176,64,0.12);
  color: var(--gold);
  border-left-color: var(--gold);
  font-weight: 700;
}

.nav-item .badge {
  margin-left: auto;
  font-size: 0.65rem;
  padding: 0.1rem 0.4rem;
  border-radius: 999px;
  background: rgba(252,176,64,0.2);
  color: var(--gold);
}

/* ── Main ── */
.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--navy-dark);
  min-height: 0;
}

.page-header {
  padding: 1rem 1.5rem 0.5rem;
  border-bottom: 1px solid var(--border);
  background: var(--navy-dark);
  flex-shrink: 0;
}

.page-header h2 {
  font-family: 'DM Serif Display', serif;
  font-size: 1.3rem;
  color: var(--white);
}

.page-header .updated {
  font-size: 0.72rem;
  color: var(--text-muted);
  margin-top: 0.2rem;
}

/* ── KPI strips ── */
.kpi-strip {
  display: flex;
  gap: 0.75rem;
  padding: 0.75rem 1.5rem;
  background: var(--navy-dark);
  border-bottom: 1px solid var(--border);
  overflow-x: auto;
  flex-shrink: 0;
}

.kpi-card {
  display: flex;
  flex-direction: column;
  padding: 0.6rem 1rem;
  background: var(--navy);
  border: 1px solid var(--border);
  border-radius: 8px;
  min-width: 120px;
  flex-shrink: 0;
}

.kpi-card .label {
  font-size: 0.65rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.25rem;
}

.kpi-card .value {
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--white);
  line-height: 1;
}

.kpi-card .value.good { color: var(--green); }
.kpi-card .value.bad  { color: var(--red); }
.kpi-card .sub {
  font-size: 0.65rem;
  color: var(--text-muted);
  margin-top: 0.2rem;
}

/* ── Tab content ── */
.tab-content {
  flex: 1;
  overflow-y: auto;
  padding: 1rem 1.5rem;
  display: none;
}

.tab-content.active { display: block; }

/* ── Chart area ── */
.chart-wrap {
  background: var(--navy);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 0.75rem;
  margin-bottom: 1rem;
}

.chart-wrap .chart-title {
  font-size: 0.72rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.5rem;
}

/* ── Coefficients table ── */
.coef-section { margin-bottom: 1rem; }

.section-title {
  font-size: 0.8rem;
  font-weight: 700;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.5rem;
  padding-bottom: 0.25rem;
  border-bottom: 1px solid var(--border);
}

.coef-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 0.5rem;
}

.coef-chip {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.4rem 0.6rem;
  background: var(--navy);
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 0.8rem;
  cursor: pointer;
  transition: all 0.15s;
  user-select: none;
}

.coef-chip:hover {
  border-color: var(--gold);
  background: rgba(252,176,64,0.05);
}

.coef-chip.dominant {
  border-color: var(--gold);
  background: rgba(252,176,64,0.08);
}

.coef-chip.dominant .chip-name {
  color: var(--gold);
  font-weight: 700;
}

.coef-chip.inactive {
  opacity: 0.35;
}

.chip-bar {
  width: 6px;
  height: 28px;
  border-radius: 3px;
  flex-shrink: 0;
}

.chip-body { flex: 1; min-width: 0; }

.chip-name {
  font-size: 0.8rem;
  color: var(--text);
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.chip-value {
  font-size: 0.7rem;
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
}

.chip-value.pos { color: #60a5fa; }
.chip-value.neg { color: #f87171; }

/* ── Feature toggle area ── */
.toggle-section { margin-bottom: 1rem; }

.toggle-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.toggle-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.18rem 0.5rem;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: rgba(255,255,255,0.04);
  color: var(--text-muted);
  font-size: 0.72rem;
  font-family: 'DM Sans', sans-serif;
  cursor: pointer;
  transition: all 0.15s;
  user-select: none;
  white-space: nowrap;
  line-height: 1.4;
}

.toggle-btn:hover { border-color: var(--gold); color: var(--text); }
.toggle-btn.active { background: rgba(252,176,64,0.15); border-color: var(--gold); color: var(--gold); }
.toggle-btn .dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--text-muted);
  flex-shrink: 0;
}
.toggle-btn.active .dot { background: var(--gold); }

/* ── Actual vs Predicted mini-table ── */
.avp-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 0.5rem;
}

.avp-card {
  background: var(--navy);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 0.6rem 0.75rem;
}

.avp-card .avp-label {
  font-size: 0.65rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.3rem;
}

.avp-card .avp-value {
  font-size: 1.1rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.avp-card .avp-sub {
  font-size: 0.65rem;
  color: var(--text-muted);
  margin-top: 0.15rem;
}

/* ── Plotly chart container ── */
#plotly-chart {
  width: 100%;
}

/* ── Joint cross-axis layout ── */
.cross-axis-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.cross-axis-grid .chart-wrap { margin-bottom: 0; }

/* ── Legend styling override ── */
.js-plotly-plot .plotly .modebar {
  top: 4px !important;
  right: 4px !important;
}
"""

_HTML_HEAD = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>{css}</style>
</head>
<body>
<div class="container">
  <aside class="sidebar">
    <div class="sidebar-header">
      <h1>SINDy Viewer</h1>
      <div class="meta">{meta}</div>
    </div>
    <nav>{nav_items}</nav>
  </aside>

  <main class="main">
    <div class="page-header">
      <h2>{page_title}</h2>
      <div class="updated">{time_range}</div>
    </div>
    <div class="kpi-strip" id="kpi-strip"></div>
    <div id="tab-container">{tab_contents}</div>
  </main>
</div>

<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<script>
const FIG_DATA = JSON.parse({fig_json});
const PAYLOADS = JSON.parse({payloads_json});
let activeTab = null;
let activeFeatures = {{}};  // tab -> set of feature names
let initialized = false;

function init() {{
  const tabs = {tab_ids_json};
  // init activeFeatures
  Object.values(tabs).forEach(id => {{ activeFeatures[id] = null; }});
  switchTab(Object.keys(tabs)[0]);
  initialized = true;
}}

function switchTab(tabId) {{
  if (!initialized) {{ activeTab = tabId; }}
  // Nav
  document.querySelectorAll('.nav-item').forEach(el => {{
    el.classList.toggle('active', el.dataset.tab === tabId);
  }});
  // Content
  document.querySelectorAll('.tab-content').forEach(el => {{
    el.classList.toggle('active', el.dataset.tab === tabId);
  }});
  activeTab = tabId;
  renderKpiStrip(tabId);
  renderPlot(tabId);
  renderCoefSection(tabId);
  renderToggleSection(tabId);
}}

function renderKpiStrip(tabId) {{
  const strip = document.getElementById('kpi-strip');
  const payload = PAYLOADS[tabId];
  if (!payload) {{ strip.innerHTML = ''; return; }}
  const m = payload.metrics || {{}};
  const active = payload.activeScenario || 'Full model';
  const chips = [
    ['R² train', m.r2_train, '', m.r2_train >= 0.7 ? 'good' : m.r2_train >= 0.3 ? '' : 'bad'],
    ['R² test', m.r2_test, '', m.r2_test >= 0.7 ? 'good' : m.r2_test >= 0.3 ? '' : 'bad'],
    ['RMSE', m.rmse_train, 'train / ' + (m.rmse_test || 0).toFixed(3) + ' test', ''],
    ['MAE', m.mae_train, 'train / ' + (m.mae_test || 0).toFixed(3) + ' test', ''],
    ['NRMSE', m.nrmse_train, 'train / ' + (m.nrmse_test || 0).toFixed(3) + ' test', ''],
    ['Active', m.n_active_terms, '/' + m.n_total_terms + ' terms', ''],
  ];
  strip.innerHTML = chips.map(([label, val, sub, cls]) => `
    <div class="kpi-card">
      <div class="label">${{label}}</div>
      <div class="value ${{cls || ''}}">${{typeof val === 'number' ? val.toFixed(3) : '—'}}</div>
      <div class="sub">${{sub}}</div>
    </div>`).join('');
}}

function renderPlot(tabId) {{
  const fig = FIG_DATA[tabId];
  if (!fig) return;
  // Apply feature mask to traces
  const mask = activeFeatures[tabId];
  if (mask) {{
    const payload = PAYLOADS[tabId];
    const featNames = payload.feature_names;
    const keptSet = new Set();
    featNames.forEach((f, i) => {{ if (mask[i]) keptSet.add(f); }});
    // Filter traces: keep if no legendgroup, or if legendgroup matches active features
    const filtered = {{
      ...fig,
      data: fig.data.map(tr => {{
        // Determine if this trace is a feature contribution
        const name = tr.name || '';
        // Feature contrib traces have names like "x (coef=+3.4)"
        const featMatch = featNames.some(f => name.startsWith(f + ' (coef='));
        if (!featMatch) return tr;  // keep non-feature traces
        const featName = featNames.find(f => name.startsWith(f + ' (coef='));
        return {{
          ...tr,
          visible: keptSet.has(featName),
          showlegend: keptSet.has(featName),
        }};
      }})
    }};
    Plotly.newPlot('plotly-chart-' + tabId, filtered);
  }} else {{
    Plotly.newPlot('plotly-chart-' + tabId, fig);
  }}
}}

function renderCoefSection(tabId) {{
  const el = document.getElementById('coef-section-' + tabId);
  const payload = PAYLOADS[tabId];
  if (!el || !payload) return;
  const featNames = payload.feature_names;
  const coefs = payload.coefs;
  if (!coefs) {{ el.innerHTML = ''; return; }}
  // Sort by magnitude
  const order = Array.from({{length: coefs.length}}, (_,i)=>i)
    .sort((a,b) => Math.abs(coefs[b]) - Math.abs(coefs[a]));
  const mask = activeFeatures[tabId];
  el.innerHTML = '<div class="coef-grid">' + order.map(idx => {{
    const name = featNames[idx];
    const val = coefs[idx];
    const abs = Math.abs(val);
    const isDom = order.indexOf(idx) < 3;
    const isActive = !mask || mask[idx];
    const barColor = val >= 0 ? '#60a5fa' : '#f87171';
    return `<div class="coef-chip ${{isDom ? 'dominant' : ''}} ${{!isActive ? 'inactive' : ''}}"
      onclick="toggleFeature('${{tabId}}', ${{idx}})">
      <div class="chip-bar" style="background:${{barColor}}; opacity:${{0.3 + 0.7*abs/Math.max(...order.map(i=>Math.abs(coefs[i])))}}"></div>
      <div class="chip-body">
        <div class="chip-name">${{name}}</div>
        <div class="chip-value ${{val >= 0 ? 'pos' : 'neg'}}">${{val >= 0 ? '+' : ''}}${{val.toFixed(3)}}</div>
      </div>
    </div>`;
  }}).join('') + '</div>';
}}

function toggleFeature(tabId, featIdx) {{
  const payload = PAYLOADS[tabId];
  if (!payload) return;
  const featNames = payload.feature_names;
  if (!activeFeatures[tabId]) {{
    activeFeatures[tabId] = new Array(featNames.length).fill(true);
  }}
  activeFeatures[tabId][featIdx] = !activeFeatures[tabId][featIdx];
  renderCoefSection(tabId);
  renderPlot(tabId);
}}

function resetFeatures(tabId) {{
  activeFeatures[tabId] = null;
  renderCoefSection(tabId);
  renderPlot(tabId);
}}

function renderToggleSection(tabId) {{
  // Renders feature-toggle pill buttons in the toggle-grid-{ctabId} div.
  const el = document.getElementById('toggle-grid-' + tabId);
  const payload = PAYLOADS[tabId];
  if (!el || !payload) {{ el.innerHTML = ''; return; }}
  const featNames = payload.feature_names || [];
  const coefs = payload.coefs || [];
  if (!featNames.length) {{ el.innerHTML = '<span style="color:var(--text-muted);font-size:0.75rem">No features</span>'; return; }}
  // Initialise mask if needed
  if (activeFeatures[tabId] === null) {{
    activeFeatures[tabId] = new Array(featNames.length).fill(true);
  }}
  const mask = activeFeatures[tabId];
  const nActive = mask.filter(Boolean).length;
  el.innerHTML = featNames.map((fname, idx) => {{
    const isOn = mask[idx];
    const coef = coefs[idx];
    const valStr = (coef !== undefined && coef !== null)
      ? (coef >= 0 ? '+' : '') + Number(coef).toFixed(3)
      : '';
    return `<button class="toggle-btn ${{isOn ? 'active' : ''}}"
      onclick="toggleFeature('${{tabId}}', ${{idx}})"
      title="Toggle ${{fname}} (coef=${{valStr}})">
      <span class="dot"></span>${{fname}}
      <span style="margin-left:0.3em;opacity:0.7;font-size:0.65rem">${{valStr}}</span>
    </button>`;
  }}).join('');
  // Summary line
  el.innerHTML += `<span style="margin-left:0.5em;font-size:0.7rem;color:var(--text-muted)">${{nActive}}/${{featNames.length}} active</span>`;
}}

function toggleFeature(tabId, featIdx) {{
  const payload = PAYLOADS[tabId];
  if (!payload) return;
  const featNames = payload.feature_names || [];
  if (activeFeatures[tabId] === null) {{
    activeFeatures[tabId] = new Array(featNames.length).fill(true);
  }}
  activeFeatures[tabId][featIdx] = !activeFeatures[tabId][featIdx];
  renderToggleSection(tabId);
  renderPlot(tabId);
}}

function resetFeatures(tabId) {{
  activeFeatures[tabId] = null;
  renderToggleSection(tabId);
  renderPlot(tabId);
}}

// Tab nav click
document.addEventListener('DOMContentLoaded', init);
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Figure builders
# ---------------------------------------------------------------------------

def _build_axis_figure(
    axis: str,
    ds: FlightDataset,
    payload: dict,
    downsamples_to: int,
) -> dict:
    """Build the Plotly figure dict for one axis tab."""
    n_rows = 3
    fig = make_subplots(
        rows=n_rows, cols=1,
        shared_xaxes=False,
        vertical_spacing=0.10,
        row_heights=[0.35, 0.35, 0.30],
        specs=[
            [{"secondary_y": True}],
            [{"secondary_y": False}],
            [{"secondary_y": True}],
        ],
        subplot_titles=(
            f"<b>{axis.upper()}</b> — body rate (rad/s) vs setpoint",
            f"<b>{axis.upper()}</b> — fit: measured vs predicted dx/dt",
            f"<b>{axis.upper()}</b> — coefficient contribution traces",
        ),
    )
    t_ds, x_ds, u_ds = _downsample_triplet(ds.t, ds.x, ds.u, downsamples_to)
    # Row 1: rate + setpoint
    fig.add_trace(
        go.Scatter(x=t_ds, y=x_ds, mode="lines", name=f"{axis} rate",
                   line=dict(color="#60a5fa", width=1.5),
                   hovertemplate=f"{axis}_rate=%{{y:.4f}}<br>t=%{{x:.3f}} s<extra></extra>"),
        row=1, col=1,
    )
    fig.add_trace(
        go.Scatter(x=t_ds, y=u_ds, mode="lines", name=f"{axis} setpoint",
                   line=dict(color="#FCB040", width=1.5, dash="dash"),
                   hovertemplate=f"{axis}_sp=%{{y:.4f}}<br>t=%{{x:.3f}} s<extra></extra>"),
        row=1, col=1, secondary_y=True,
    )

    # Fit data
    fit = payload["scenarios"][0]["result"]
    t_fit = fit["t"]
    from sim.sindy.fit_panel import per_axis_features
    cfg = payload.get("_cfg", FitConfig())
    x_full, u_full = payload["_x"], payload["_u"]
    Phi = per_axis_features(x_full, u_full, cfg)

    # Row 2: dx/dt measured + predicted
    fig.add_trace(
        go.Scatter(x=t_fit, y=fit["y_true"], mode="lines",
                   name="dx/dt measured",
                   line=dict(color="#60a5fa", width=2),
                   hovertemplate="dx_meas=%{y:.4f}<br>t=%{x:.3f} s<extra></extra>"),
        row=2, col=1,
    )
    fig.add_trace(
        go.Scatter(x=t_fit, y=fit["y_pred"], mode="lines",
                   name="dx/dt predicted",
                   line=dict(color="#FCB040", width=2, dash="dash"),
                   hovertemplate="dx_pred=%{y:.4f}<br>t=%{x:.3f} s<extra></extra>"),
        row=2, col=1,
    )

    # Row 3: per-feature contribution traces
    feat_names = payload["feature_names"]
    coefs = fit["coefs"]
    for f_idx, (fname, coef_val) in enumerate(zip(feat_names, coefs)):
        if f_idx >= Phi.shape[1]:
            continue
        if abs(coef_val) < 1e-10:
            continue
        contrib = coef_val * Phi[:, f_idx]
        fig.add_trace(
            go.Scatter(x=t_fit, y=contrib, mode="lines",
                       name=f"{fname} (coef={coef_val:+.3f})",
                       line=dict(width=1.5),
                       opacity=0.7,
                       hovertemplate=f"{fname} contrib=%{{y:.4f}}<br>t=%{{x:.3f}} s<extra></extra>"),
            row=3, col=1,
        )

    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="#071f4a",
        plot_bgcolor="#0A3476",
        font_color="#e2e8f0",
        font=dict(family="DM Sans, sans-serif", size=11),
        height=700,
        margin=dict(t=50, b=30, l=60, r=20),
        hovermode="x unified",
        showlegend=True,
        legend=dict(
            orientation="h", y=1.08, x=0.0,
            bgcolor="rgba(7,31,74,0.8)",
            bordercolor="rgba(255,255,255,0.1)",
            borderwidth=1,
            font=dict(size=10),
        ),
        xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.06)", zeroline=False,
                   tickfont=dict(color="#94a3b8")),
        xaxis2=dict(showgrid=True, gridcolor="rgba(255,255,255,0.06)", zeroline=False,
                    tickfont=dict(color="#94a3b8")),
        xaxis3=dict(showgrid=True, gridcolor="rgba(255,255,255,0.06)", zeroline=False,
                    tickfont=dict(color="#94a3b8")),
        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.06)", zeroline=False,
                   tickfont=dict(color="#94a3b8")),
        yaxis2=dict(showgrid=True, gridcolor="rgba(255,255,255,0.06)", zeroline=False,
                    tickfont=dict(color="#94a3b8")),
        yaxis3=dict(showgrid=True, gridcolor="rgba(255,255,255,0.06)", zeroline=False,
                    tickfont=dict(color="#94a3b8")),
        yaxis2_title=dict(text="dx/dt rad/s²", font=dict(color="#e2e8f0")),
        yaxis3_title=dict(text="contribution", font=dict(color="#e2e8f0")),
        yaxis_title=dict(text="rad/s", font=dict(color="#e2e8f0")),
    )
    return fig.to_dict()


def _build_joint_figure(payload: dict, downsamples_to: int) -> dict:
    """Build the Plotly figure dict for the joint tab."""
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=False,
        vertical_spacing=0.12,
        row_heights=[0.55, 0.45],
        subplot_titles=(
            "<b>JOINT</b> — measured vs predicted dx/dt (all axes)",
            "<b>JOINT</b> — top-12 coefficient contributions per axis",
        ),
    )
    colors = {"roll": "#60a5fa", "pitch": "#FCB040", "yaw": "#22c55e"}
    fit = payload["scenarios"][0]["result"]
    t_fit = fit["t"]
    for ax_idx, ax in enumerate(AXES):
        fig.add_trace(
            go.Scatter(x=t_fit, y=fit["y_true"][:, ax_idx], mode="lines",
                       name=f"{ax} dx_meas",
                       line=dict(color=colors[ax], width=1.5),
                       hovertemplate=f"dx_meas_{ax}=%{{y:.4f}}<br>t=%{{x:.3f}} s<extra></extra>"),
            row=1, col=1,
        )
        fig.add_trace(
            go.Scatter(x=t_fit, y=fit["y_pred"][:, ax_idx], mode="lines",
                       name=f"{ax} dx_pred",
                       line=dict(color=colors[ax], width=1.5, dash="dash"),
                       hovertemplate=f"dx_pred_{ax}=%{{y:.4f}}<br>t=%{{x:.3f}} s<extra></extra>"),
            row=1, col=1,
        )
    # Coefficient bar chart — top 12 features by mean |coef|
    coefs = fit["coefs"]
    feat_names = fit["feature_names"]
    mean_abs = np.mean(np.abs(coefs), axis=1)
    order = np.argsort(-mean_abs)[:12]
    for ax_idx, ax in enumerate(AXES):
        ax_coefs = coefs[order, ax_idx]
        ax_names = [feat_names[k] for k in order]
        fig.add_trace(
            go.Bar(x=ax_names, y=ax_coefs,
                   name=f"{ax} coef",
                   marker=dict(color=colors[ax]),
                   hovertemplate=f"{ax} %{{x}}: %{{y:.4f}}<extra></extra>"),
            row=2, col=1,
        )
    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="#071f4a",
        plot_bgcolor="#0A3476",
        font_color="#e2e8f0",
        font=dict(family="DM Sans, sans-serif", size=11),
        height=650,
        margin=dict(t=50, b=30, l=60, r=20),
        hovermode="x unified",
        showlegend=True,
        legend=dict(
            orientation="h", y=1.06, x=0.0,
            bgcolor="rgba(7,31,74,0.8)",
            bordercolor="rgba(255,255,255,0.1)",
            borderwidth=1,
            font=dict(size=10),
        ),
        xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.06)", zeroline=False,
                   tickfont=dict(color="#94a3b8")),
        xaxis2=dict(showgrid=True, gridcolor="rgba(255,255,255,0.06)", zeroline=False,
                    tickfont=dict(color="#94a3b8")),
        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.06)", zeroline=False,
                   tickfont=dict(color="#94a3b8")),
        yaxis2=dict(showgrid=True, gridcolor="rgba(255,255,255,0.06)", zeroline=False,
                    tickfont=dict(color="#94a3b8")),
    )
    return fig.to_dict()


# ---------------------------------------------------------------------------
# Main viewer
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
    """Build the custom-HTML SINDy viewer for a PX4 ulog file.

    Generates a self-contained HTML dashboard with dark-navy theme,
    sidebar tabs, KPI strips, embedded Plotly charts, and interactive
    coefficient toggling.
    """
    ulog_path = Path(ulog_path)
    out_html = Path(out_html)
    out_html.parent.mkdir(parents=True, exist_ok=True)

    cfg = cfg or FitConfig()

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
        fit_payloads = _build_fit_payloads(datasets, cfg)

    # ── Build per-tab data ──
    fig_data: dict = {}
    tab_ids: dict = {}
    payloads_out: dict = {}

    for axis in AXES:
        tab_id = f"axis_{axis}"
        ds = datasets.get(axis)
        if ds is None:
            payloads_out[tab_id] = None
            fig_data[tab_id] = None
            continue
        tab_ids[axis.capitalize()] = tab_id
        payload = fit_payloads["per_axis"].get(axis) if fit_payloads else None
        if payload:
            fig_data[tab_id] = pio.to_json(
                _build_axis_figure(axis, ds, payload, downsamples_to)
            )
            payloads_out[tab_id] = _payload_summary(payload)
        else:
            fig_data[tab_id] = None
            payloads_out[tab_id] = None

    joint_tab_id = "joint"
    if fit_payloads and fit_payloads.get("joint") and all(a in datasets for a in AXES):
        tab_ids["Joint"] = joint_tab_id
        fig_data[joint_tab_id] = pio.to_json(
            _build_joint_figure(fit_payloads["joint"], downsamples_to)
        )
        payloads_out[joint_tab_id] = _joint_summary(fit_payloads["joint"])
    else:
        payloads_out[joint_tab_id] = None
        fig_data[joint_tab_id] = None

    # ── Build nav items ──
    nav_parts: list[str] = []
    for label, tab_id in tab_ids.items():
        p = payloads_out.get(tab_id) or {}
        lib = p.get("library", "—") or "—"
        badge = f'<span class="badge">{lib}</span>'
        nav_parts.append(
            f'<div class="nav-item" data-tab="{tab_id}" onclick="switchTab(\'{tab_id}\')">'
            f'<span>{label}</span>{badge}</div>'
        )
    nav_items = "".join(nav_parts)

    # ── Build tab contents ──
    tab_contents = ""
    for label, tab_id in tab_ids.items():
        active = " active" if label == list(tab_ids.keys())[0] else ""
        payload = payloads_out.get(tab_id)
        fig = fig_data.get(tab_id)
        tab_contents += (
            f'<div class="tab-content{active}" data-tab="{tab_id}">'
            f'  <div class="chart-wrap">'
            f'    <div class="chart-title">Interactive chart — click legend to toggle traces</div>'
            f'    <div id="plotly-chart-{tab_id}"></div>'
            f'  </div>'
            f'  <div class="coef-section" id="coef-section-{tab_id}"></div>'
            f'  <div class="toggle-section">'
            f'    <div class="section-title">Feature toggles</div>'
            f'    <div class="toggle-grid" id="toggle-grid-{tab_id}"></div>'
            f'  </div>'
            f'</div>'
        )

    # ── Page metadata ──
    page_title = title or f"SINDy — {ulog_path.name}"
    if "roll" in datasets:
        t0 = datasets["roll"].t[0]
        t1 = datasets["roll"].t[-1]
        time_range = f"{t0:.2f}s → {t1:.2f}s · {n_samples} samples · {', '.join(axis_coverage)}"
    else:
        time_range = f"{n_samples} samples"
    meta = f"axis: {', '.join(axis_coverage) or 'none'} · library: polynomial"

    # ── Render HTML ──
    # Build the JSON strings; they are always valid JSON and contain no
    # format-key-like substrings so safe to substitute directly.
    fig_json_str = json.dumps(fig_data)
    payloads_json_str = json.dumps(payloads_out)
    tab_ids_json_str = json.dumps(tab_ids)

    html = (
        _HTML_HEAD
        .replace("{title}", page_title)
        .replace("{meta}", meta)
        .replace("{page_title}", page_title)
        .replace("{time_range}", time_range)
        .replace("{nav_items}", nav_items)
        .replace("{tab_contents}", tab_contents)
        .replace("{css}", _CSS)
        .replace("{fig_json}", fig_json_str)
        .replace("{payloads_json}", payloads_json_str)
        .replace("{tab_ids_json}", tab_ids_json_str)
    )

    out_html.write_text(html, encoding="utf-8")
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


def _payload_summary(payload: dict) -> dict:
    """Extract the minimal payload needed by the HTML JS."""
    if not payload:
        return {}
    fit = payload["scenarios"][0]["result"]
    return {
        "library": fit["library"],
        "feature_names": list(fit["feature_names"]),
        "coefs": [float(c) for c in fit["coefs"]],
        "metrics": {k: float(v) for k, v in fit["metrics"].items()
                       if isinstance(v, (int, float, np.floating))},
        "activeScenario": payload["scenarios"][0]["label"],
    }


def _joint_summary(payload: dict) -> dict:
    """Extract joint payload for the HTML JS."""
    if not payload:
        return {}
    fit = payload["scenarios"][0]["result"]
    # Average metrics across axes
    avg_m = {}
    for key in ("r2_train", "r2_test", "rmse_train", "rmse_test",
                "mae_train", "mae_test", "nrmse_train", "nrmse_test"):
        vals = [fit["metrics_per_axis"][ax].get(key, 0) for ax in AXES]
        avg_m[key] = float(np.mean(vals))
    avg_m["n_active_terms"] = int(np.mean([
        fit["metrics_per_axis"][ax].get("n_active_terms", 0) for ax in AXES
    ]))
    avg_m["n_total_terms"] = int(fit["metrics_per_axis"]["roll"].get("n_total_terms", 27))
    # Flatten metrics_per_axis: each axis gets a clean float dict
    flat_metrics_per_axis = {}
    for ax in AXES:
        raw = fit["metrics_per_axis"].get(ax, {})
        flat_metrics_per_axis[ax] = {
            k: float(v) for k, v in raw.items()
            if isinstance(v, (int, float, np.floating))
        }
    return {
        "library": "polynomial_joint",
        "feature_names": list(fit["feature_names"]),
        "coefs": [float(c) for row in fit["coefs"] for c in row],
        "metrics": avg_m,
        "metrics_per_axis": flat_metrics_per_axis,
        "activeScenario": payload["scenarios"][0]["label"],
        "n_scenarios": len(payload["scenarios"]),
    }


def _summarise_fit_payloads(payloads: Optional[dict]) -> Optional[dict]:
    if payloads is None:
        return None
    per_axis_summary = {}
    for axis, payload in payloads.get("per_axis", {}).items():
        per_axis_summary[axis] = _payload_summary(payload)
    joint_summary = None
    if payloads.get("joint"):
        joint_summary = _joint_summary(payloads["joint"])
    return {"per_axis": per_axis_summary, "joint": joint_summary}


def _build_fit_payloads(
    datasets: dict[str, FlightDataset],
    cfg: FitConfig,
) -> dict:
    payloads: dict = {"per_axis": {}, "joint": None}
    for axis, ds in datasets.items():
        scenarios, t, x, u = _per_axis_scenarios(ds.t, ds.x, ds.u, axis, cfg)
        payloads["per_axis"][axis] = {
            "axis": axis,
            "feature_names": list(per_axis_feature_names(cfg)),
            "scenarios": scenarios,
            "active_idx": 0,
            "_t": t, "_x": x, "_u": u, "_cfg": cfg,
        }
    if all(ax in datasets for ax in AXES):
        per_axis_full = {ax: (datasets[ax].t, datasets[ax].x, datasets[ax].u) for ax in AXES}
        scenarios = _joint_scenarios(per_axis_full, cfg)
        payloads["joint"] = scenarios
    return payloads


def _joint_scenarios(
    per_axis_data: dict, cfg: FitConfig,
) -> dict:
    """Joint fit + drop-one scenarios, capped at MAX_SCENARIOS by R²."""
    n_features = len(JOINT_FEATURE_NAMES)
    full = joint_fit(per_axis_data, cfg=cfg)
    candidates: list = [{
        "label": "Full model", "result": full,
        "r2_train_avg": float(np.mean([
            full["metrics_per_axis"][a]["r2_train"] for a in AXES
        ])),
    }]
    for j in range(n_features):
        mask = np.ones(n_features, dtype=bool)
        mask[j] = False
        try:
            res = joint_fit(per_axis_data, cfg=cfg, feature_mask=mask)
            r2_avg = float(np.mean([
                res["metrics_per_axis"][a]["r2_train"] for a in AXES
            ]))
        except ValueError:
            continue
        candidates.append({
            "label": f"Without {JOINT_FEATURE_NAMES[j]}",
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


def _per_axis_scenarios(
    t: np.ndarray, x: np.ndarray, u: np.ndarray, axis: str, cfg: FitConfig,
) -> tuple:
    from sim.sindy.fit_panel import per_axis_fit, per_axis_feature_names
    feat_names = list(per_axis_feature_names(cfg))
    n_features = len(feat_names)
    full = per_axis_fit(t, x, u, cfg=cfg, label=axis)
    scenarios: list = [{"label": "Full model", "result": full}]
    for j in range(n_features):
        mask = np.ones(n_features, dtype=bool)
        mask[j] = False
        res = per_axis_fit(t, x, u, cfg=cfg, label=axis, feature_mask=mask)
        scenarios.append({"label": f"Without {feat_names[j]}", "result": res})
    return scenarios, t, x, u


def _downsample_uniform(t: np.ndarray, y: np.ndarray, n_target: int) -> tuple:
    n = len(t)
    if n <= n_target or n_target < 2:
        return t, y
    idx = np.unique(np.linspace(0, n - 1, n_target).astype(int))
    return t[idx], y[idx]


def _downsample_triplet(
    t: np.ndarray, x: np.ndarray, u: np.ndarray, n_target: int,
) -> tuple:
    t_ds, x_ds = _downsample_uniform(t, x, n_target)
    _, u_ds = _downsample_uniform(t, u, n_target)
    return t_ds, x_ds, u_ds
