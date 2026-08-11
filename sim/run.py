"""Closed-loop runner: wires plant + reference model + baseline PID + MRAC.

One tick is delegated to sim.loop.ControlLoop (the wiring seam, PARITY:
API/mrac.c:424-485). This module owns the simulation clock, the log arrays, the
metrics call (sim.metrics), and the per-run artifact folder.

Each run writes sim/runs/<ts>_<scenario>/{plots/, data.csv, metrics.json, report.md}
(ADR-0006 D7). Pass write_artifacts=False for a pure in-memory run (tests).

ADR-0011 Phases 3 & 4: AccBiasTrim and GyroBiasHotFsm step every tick from the
main loop. AccBiasTrim gates on flight_phase_flying and elapsed_t > 0.3;
GyroBiasHotFsm gates internally (flying + rc_active + stillness + translational).
Both require the scenario to expose a calibrator interface (get_accel_mg,
get_gyro_rads, flight_phase_flying, rc_active) — existing scenarios return
None and the calibrators idle.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np

from sim import metrics as metrics_mod
from sim.adaptive_law import AdaptiveFlags, AdaptiveLaw, AxisAdaptiveConfig
from sim.baseline import RatePID, RatePIDConfig
from sim.calibrator import AccBiasTrim, GyroBiasHotFsm
from sim.loop import ControlLoop
from sim.reference_model import ReferenceModel, RefType

# Calibrator result dict appended to run() return value
_CAL_KEYS = [
    "acc_trim_b_a",   # last b_a tuple, mg
    "acc_trim_settled",
    "gyro_hot_b_g",   # last b_g tuple, rad/s
    "gyro_hot_state",
    "gyro_hot_rejected",
]

_RUNS_DIR = Path(__file__).resolve().parent / "runs"

# log columns, in CSV order
_COLS = ["t", "r", "d", "xm", "x", "e", "u_nom", "u_ad", "u", "U", "wnorm", "edot"]
# Optional calibrator columns (NaN for non-calibrator runs)
_CAL_COLS = ["b_a_x", "b_a_y", "b_a_z", "b_g_x", "b_g_y", "b_g_z",
             "gyro_state", "gyro_rejected"]


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

    ADR-0011 Phases 3 & 4: AccBiasTrim is updated every tick when the scenario
    plant exposes ``get_accel_mg()`` and ``is_flying`` is True + elapsed_t > 0.3.
    GyroBiasHotFsm is updated every tick via ``get_gyro_rads()`` and ``is_flying``.
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

    # ADR-0011 Phase 3 + 4 calibrators (idle when plant has no sensor interface)
    acc_trim = AccBiasTrim()
    gyro_hot = GyroBiasHotFsm()

    _has_cal = hasattr(plant, "get_accel_mg") and hasattr(plant, "get_gyro_rads")

    n = int(round(scenario.duration / dt))

    log = {k: np.empty(n) for k in _COLS}
    theta_hist = np.empty((n, law.n))

    # Calibrator telemetry log (flat arrays for CSV export)
    cal_log = {
        "b_a_x": np.empty(n), "b_a_y": np.empty(n), "b_a_z": np.empty(n),
        "b_g_x": np.empty(n), "b_g_y": np.empty(n), "b_g_z": np.empty(n),
        "gyro_state": np.empty(n, dtype=int), "gyro_rejected": np.empty(n, dtype=bool),
    }

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

        # ADR-0011 Phase 3 + 4: calibrator step every tick (once per tick at 200 Hz)
        if _has_cal:
            g_ref = (0.0, 0.0, 1000.0)  # mg, world gravity
            g_meas = plant.get_accel_mg()
            gyro_rads = plant.get_gyro_rads()

            # Phase 3 — AccBiasTrim: gate matches ADR-0011 cold-cal → CAL_AIRBORNE
            # transition.  The firmware gates on: flight_phase_flying + sticks-centred
            # + altitude > 0.5 m + ~0.5 s.  Approximate as:
            #   - flying condition: |r| < 0.1 rad/s (hover / no stick demand)
            #   - elapsed_t > 2.0 s: covers both cold-cal (0-2 s) and take-off
            #     transient (2-3 s); AccBiasTrim only starts at tick 600 = 3.0 s.
            flying = abs(r) < 0.1
            if flying and t > 2.0:
                acc_trim.update(g_ref, g_meas)

            # Phase 4 — GyroBiasHotFsm: flies, RC idle, stillness+trans guard
            # (internal guards; no extra time gate needed — FSM only accumulates
            # when conditions are met, and will complete at tick 499 = 2.495 s)
            gyro_res = gyro_hot.update(gyro_rads, (g_meas[0], g_meas[1], 0.0),
                                       flying, rc_active=False)

            cal_log["b_a_x"][k] = acc_trim.b_a[0]
            cal_log["b_a_y"][k] = acc_trim.b_a[1]
            cal_log["b_a_z"][k] = acc_trim.b_a[2]
            cal_log["b_g_x"][k] = gyro_hot.b_g[0]
            cal_log["b_g_y"][k] = gyro_hot.b_g[1]
            cal_log["b_g_z"][k] = gyro_hot.b_g[2]
            cal_log["gyro_state"][k] = gyro_res["state"]
            cal_log["gyro_rejected"][k] = gyro_res["rejected"]
        else:
            for kk in ("b_a_x", "b_a_y", "b_a_z", "b_g_x", "b_g_y", "b_g_z"):
                cal_log[kk][k] = float("nan")
            cal_log["gyro_state"][k] = -1
            cal_log["gyro_rejected"][k] = False

    metrics = metrics_mod.compute(
        log, theta_hist, dt,
        umax=pid.cfg.UMax,
        what_limit=config.What_limit, what_tol=config.What_tol,
        what_lower=config.What_lower_limit,
        e_deadzone=config.e_deadzone if flags.deadzone_on else None,
        e_freeze=config.e_freeze if flags.hard_freeze_on else None)

    # spec-11: record final weights so the same config can be replayed
    # under the deployment envelope (paired learn/deploy experiment).
    # Write to the config object so callers get the weights without
    # pulling them out of the result dict.
    config.theta_final = theta_hist[-1].copy()

    result = {"scenario": scenario.name, "axis": axis, "injection": injection,
              "dt": dt, "ref_model_type": int(ref.kind),
              "envelope": config.envelope,   # spec-11: which envelope produced this run
              "log": log,
              "theta": theta_hist, "metrics": metrics,
              "acc_trim_b_a": acc_trim.b_a,
              "acc_trim_settled": acc_trim.settled,
              "gyro_hot_b_g": gyro_hot.b_g,
              "gyro_hot_state": int(cal_log["gyro_state"][-1]) if _has_cal else -1,
              "gyro_hot_rejected": bool(cal_log["gyro_rejected"][-1]) if _has_cal else False,
              "_cal_log": cal_log if _has_cal else None}

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
        w.writerow(_COLS + _CAL_COLS)
        for i in range(len(log["t"])):
            row = [f"{log[c][i]:.6g}" for c in _COLS]
            if result.get("_cal_log") is not None:
                cl = result["_cal_log"]
                row += [f"{float(cl[c][i]):.6g}" if np.isfinite(cl[c][i]) else "nan"
                        for c in _CAL_COLS]
            else:
                row += ["nan"] * len(_CAL_COLS)
            w.writerow(row)

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
        f"- **Adaptive envelope**: {result.get('envelope', 'unknown')} (spec-11)",
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
    if res.get("_cal_log") is not None:
        print(f"acc_trim: b_a={res['acc_trim_b_a']}, settled={res['acc_trim_settled']}")
        print(f"gyro_hot: b_g={res['gyro_hot_b_g']}, state={res['gyro_hot_state']}")
    print(f"artifacts -> {res.get('outdir', 'N/A')}")
