"""Closed-loop runner: wires plant + reference model + baseline PID + MRAC.

One tick is delegated to sim.loop.ControlLoop (the wiring seam, PARITY:
API/mrac.c:424-485). This module owns the simulation clock, the log arrays, the
metrics call (sim.metrics), and the per-run artifact folder.

Each run writes sim/runs/<ts>_<scenario>/{plots/, data.csv, metrics.json, report.md}
(ADR-0006 D7). Pass write_artifacts=False for a pure in-memory run (tests).
"""
from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

import numpy as np

from sim import metrics as metrics_mod
from sim.adaptive_law import AdaptiveFlags, AdaptiveLaw, AxisAdaptiveConfig
from sim.baseline import RatePID, RatePIDConfig
from sim.loop import ControlLoop
from sim.reference_model import ReferenceModel, RefType

_RUNS_DIR = Path(__file__).resolve().parent / "runs"

# log columns, in CSV order
_COLS = ["t", "r", "d", "xm", "x", "e", "u_nom", "u_ad", "u", "U", "wnorm", "edot"]


def run(scenario, *, injection: bool = True, flags: AdaptiveFlags | None = None,
        config: AxisAdaptiveConfig | None = None,
        q1: float = 1.0, q2: float = 1.0, wc_edot: float = 30.0,
        crm_l1: float = 0.0, crm_l2: float = 0.0,
        ref_model_type: int | None = None,
        dt: float = 0.005, write_artifacts: bool = True,
        runs_dir: Path | None = None) -> dict:
    """Simulate one scenario closed-loop; return a log+metrics dict.

    ``config`` overrides the firmware-default adaptive config for the axis.
    ``q1``/``q2`` are the Lyapunov Q diagonal for the 2nd-order matrix-P law
    (ADR-0007; ignored for 1st-order/passthrough); ``wc_edot`` is the LPF cutoff of
    the finite-difference rate derivative used to form e_dot. ``crm_l1``/``crm_l2``
    are the closed-loop reference-model feedback gain L = [l1; l2] on the measured
    output error (x - xm); 0/0 = open-loop RM (default, parity with ADR-0007), >0
    pulls the reference toward the plant to suppress adaptation transients. The
    Lyapunov Pe/Pedot are recomputed for the CRM error dynamics. ``ref_model_type``
    mirrors the firmware ``mrac_flags.ref_model_type`` switch (CMD 0x13): pass 0/1/2
    to force passthrough/1st/2nd order on the axis; ``None`` keeps the axis' firmware
    default order (roll/pitch=2nd, yaw=1st). Pass 0 to reproduce the as-flown
    power-on default (``DEFAULT_REF_MODEL_TYPE = 0``).
    """
    axis = scenario.axis
    plant = scenario.make_plant(dt)
    ref = ReferenceModel.for_axis(axis, dt, q1=q1, q2=q2,
                                  ref_model_type=ref_model_type,
                                  l1=crm_l1, l2=crm_l2)
    pid = RatePID(RatePIDConfig.for_axis(axis))
    flags = flags if flags is not None else AdaptiveFlags()
    config = config if config is not None else AxisAdaptiveConfig.for_axis(axis)
    state_space = ref.kind is RefType.SECOND_ORDER
    law = AdaptiveLaw(config, flags, dt=dt, state_space=state_space, wc_edot=wc_edot)
    loop = ControlLoop(ref=ref, pid=pid, law=law, plant=plant, axis=axis,
                       injection=injection)
    n = int(round(scenario.duration / dt))

    log = {k: np.empty(n) for k in _COLS}
    theta_hist = np.empty((n, law.n))

    x = 0.0  # rad/s; lagged one tick by the plant seam
    for k in range(n):
        t = k * dt
        r = scenario.setpoint(t)
        d = scenario.disturbance(t)
        rec = loop.tick(x, r, d)
        x = rec["x"]
        log["t"][k], log["r"][k], log["d"][k] = t, r, d
        log["xm"][k], log["x"][k], log["e"][k] = rec["xm"], x, rec["e"]
        log["u_nom"][k], log["u_ad"][k], log["u"][k] = rec["u_nom"], rec["u_ad"], rec["u"]
        log["U"][k], log["wnorm"][k], log["edot"][k] = rec["U"], rec["wnorm"], rec["edot"]
        theta_hist[k] = rec["theta"]

    metrics = metrics_mod.compute(
        log, theta_hist, dt,
        umax=pid.cfg.UMax,
        what_limit=config.What_limit, what_tol=config.What_tol,
        what_lower=config.What_lower_limit,
        e_deadzone=config.e_deadzone if flags.deadzone_on else None,
        e_freeze=config.e_freeze if flags.hard_freeze_on else None)
    result = {"scenario": scenario.name, "axis": axis, "injection": injection,
              "dt": dt, "ref_model_type": int(ref.kind), "log": log,
              "theta": theta_hist, "metrics": metrics}

    if write_artifacts:
        result["outdir"] = str(_write(scenario, result, runs_dir))
    return result


def _write(scenario, result: dict, runs_dir: Path | None) -> Path:
    base = runs_dir if runs_dir is not None else _RUNS_DIR
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = Path(base) / f"{ts}_{scenario.name}"
    (out / "plots").mkdir(parents=True, exist_ok=True)
    log, metrics = result["log"], result["metrics"]

    # data.csv
    with open(out / "data.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(_COLS)
        for i in range(len(log["t"])):
            w.writerow([f"{log[c][i]:.6g}" for c in _COLS])

    # metrics.json
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2))

    _plots(out / "plots", result)
    _report(out, scenario, result)
    return out


def _plots(pdir: Path, result: dict) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    log, theta = result["log"], result["theta"]
    t = log["t"]

    fig, ax = plt.subplots()
    ax.plot(t, log["r"], "k--", lw=1, label="r (cmd)")
    ax.plot(t, log["xm"], "C0", lw=1.5, label="xm (reference)")
    ax.plot(t, log["x"], "C3", lw=1.2, label="x (plant)")
    ax.set(xlabel="t [s]", ylabel="rate [rad/s]",
           title=f"{result['scenario']} -- tracking")
    ax.legend(); ax.grid(True, alpha=0.3)
    fig.savefig(pdir / "tracking.png", dpi=110, bbox_inches="tight"); plt.close(fig)

    fig, ax = plt.subplots()
    ax.plot(t, log["e"], "C1", label="e = x - xm")
    ax.plot(t, log["edot"], "C2", lw=0.8, label="e_dot (filtered)")
    ax.set(xlabel="t [s]", ylabel="error [rad/s, rad/s^2]", title="tracking error")
    ax.legend(); ax.grid(True, alpha=0.3)
    fig.savefig(pdir / "error.png", dpi=110, bbox_inches="tight"); plt.close(fig)

    fig, ax = plt.subplots()
    ax.plot(t, log["u_nom"], "C0", label="u_nom (PID)")
    ax.plot(t, log["u_ad"], "C3", label="u_ad (MRAC)")
    ax.plot(t, log["u"], "k", lw=0.8, label="u (total)")
    if np.any(log["d"] != 0.0):
        ax.plot(t, log["d"], "C4", lw=0.8, ls=":", label="disturbance")
    ax.set(xlabel="t [s]", ylabel="control [Nm]", title="control effort")
    ax.legend(); ax.grid(True, alpha=0.3)
    fig.savefig(pdir / "control.png", dpi=110, bbox_inches="tight"); plt.close(fig)

    fig, ax = plt.subplots()
    labels = ["bias", "x", "x*tanh", "cross", "u_nom", "xm"]
    for j in range(theta.shape[1]):
        ax.plot(t, theta[:, j], label=labels[j] if j < len(labels) else f"w{j}")
    ax.plot(t, log["wnorm"], "k--", lw=1.2, label="||Theta||")
    ax.set(xlabel="t [s]", ylabel="weight", title="adaptive weights")
    ax.legend(fontsize=7); ax.grid(True, alpha=0.3)
    fig.savefig(pdir / "weights.png", dpi=110, bbox_inches="tight"); plt.close(fig)


def _fmt(v) -> str:
    if v is None:
        return "n/a"
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, float):
        return f"{v:.4g}"
    if isinstance(v, list):
        return "[" + ", ".join(f"{x:.3g}" if isinstance(x, float) else str(x)
                               for x in v) + "]"
    return str(v)


def _report(out: Path, scenario, result: dict) -> None:
    m = result["metrics"]
    rt = {0: "passthrough", 1: "first-order", 2: "second-order"}.get(
        result.get("ref_model_type"), "?")

    def group(title, keys):
        rows = [f"| {k} | {_fmt(m[k])} |" for k in keys if k in m]
        if not rows:
            return []
        return [f"### {title}", "", "| metric | value |", "|---|---|", *rows, ""]

    lines = [
        f"# Sim run -- {scenario.name}", "",
        f"- **Axis**: {scenario.axis}",
        f"- **Description**: {scenario.description}",
        f"- **Reference model**: {rt} (type {result.get('ref_model_type')})",
        f"- **MRAC injection**: {'ON' if result['injection'] else 'OFF (shadow)'}",
        f"- **dt**: {result['dt']} s ({1 / result['dt']:.0f} Hz)",
        f"- **Stable**: **{_fmt(m.get('stable'))}**", "",
        "## Metrics", "",
        *group("Tracking", ["rmse_track", "max_abs_err", "track_iae", "track_ise",
                            "track_itae", "track_ss_abs_err", "track_rmse_vs_cmd",
                            "track_settling_time", "track_peak_overshoot_pct"]),
        *group("Control effort", ["ctrl_u_rms", "ctrl_u_nom_rms", "ctrl_u_ad_rms",
                                  "ctrl_max_abs_u", "ctrl_max_abs_u_ad",
                                  "ctrl_mrac_footprint", "ctrl_u_rate_max",
                                  "ctrl_sat_fraction"]),
        *group("Adaptation", ["final_weight_norm", "max_weight_norm",
                              "adapt_weight_rate_mean", "adapt_active_fraction",
                              "adapt_freeze_fraction", "adapt_any_upper_sat",
                              "adapt_theta_final", "adapt_upper_sat",
                              "adapt_lower_pinned"]),
        *group("Robustness", ["max_abs_rate", "max_abs_xm", "robust_diverged",
                              "robust_err_zero_crossings", "robust_edot_rms"]),
        *group("Disturbance response", ["dist_onset_t", "dist_peak_dev",
                                        "dist_recovery_time"]),
        "## Plots", "",
        "![tracking](plots/tracking.png)",
        "![error](plots/error.png)",
        "![control](plots/control.png)",
        "![weights](plots/weights.png)", "",
    ]
    (out / "report.md").write_text("\n".join(lines))


if __name__ == "__main__":  # pragma: no cover
    import sys
    from sim import scenarios

    name = sys.argv[1] if len(sys.argv) > 1 else "step_roll"
    sc = scenarios.ALL[name]()
    res = run(sc)
    print(f"{name}: {json.dumps(res['metrics'], indent=2)}")
    print(f"artifacts -> {res['outdir']}")
