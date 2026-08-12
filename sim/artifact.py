"""Run artifact writer — extracted from sim/run.py (sim-arch-02).

Owns the per-run artifact folder:

    <outdir>/plots/{tracking,error,control,weights}.png
    <outdir>/data.csv
    <outdir>/metrics.json
    <outdir>/report.md

This module is the **headless-safe** home for matplotlib: it sets
``matplotlib.use("Agg")`` inside ``_write_plots`` *before* importing pyplot,
so the runner (``sim.run``) can stay matplotlib-free.

Split out from the closed-loop runner because the runner's job is the loop +
log + tick + metrics story. The artifact writer is a separate object the runner
calls when ``write_artifacts=True``; ADR-0006 D7.

The CSV column order, plot filenames, DPI, and ``bbox_inches`` are preserved
exactly to keep ``sim/tests/test_run.py::test_artifacts_written`` green and to
preserve the byte-identical visual diffs that prior-11 / sim-arch-01 / sim-arch-09
analyses rely on.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np


# Column order MUST stay aligned with sim/run.py:46-49. The runner logs the
# primary columns; the calibrator columns are appended here.
_PRIMARY_COLS = ["t", "r", "d", "xm", "x", "e", "u_nom", "u_ad", "u", "U", "wnorm", "edot"]
_CAL_COLS = ["b_a_x", "b_a_y", "b_a_z", "b_g_x", "b_g_y", "b_g_z",
             "gyro_state", "gyro_rejected"]


class RunArtifactWriter:
    """Writes the per-run artifact folder (CSV + metrics + plots + report).

    Constructor creates the ``plots/`` subdirectory under ``outdir``. Call
    ``write(result, scenario=scenario)`` once ``run()`` has finished.
    """

    def __init__(self, outdir: Path) -> None:
        self.outdir = Path(outdir)
        (self.outdir / "plots").mkdir(parents=True, exist_ok=True)

    def write(self, result: dict, *, scenario,
              manifest_payload=None) -> None:
        """Write CSV, metrics.json, plots, and report.md.

        ``manifest_payload`` is an optional ``ManifestPayload`` instance.  When
        supplied, the report header reads ``payload.envelope`` instead of
        ``result.get("envelope", "deployment")`` so the report is always
        consistent with the manifest schema.
        """
        self._write_csv(result)
        self._write_metrics_json(result)
        self._write_plots(result)
        self._write_report(result, scenario, manifest_payload)

    # ------------------------------------------------------------------
    # CSV
    # ------------------------------------------------------------------
    def _write_csv(self, result: dict) -> None:
        log = result["log"]
        with open(self.outdir / "data.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(_PRIMARY_COLS + _CAL_COLS)
            for i in range(len(log["t"])):
                row = [f"{log[c][i]:.6g}" for c in _PRIMARY_COLS]
                if result.get("_cal_log") is not None:
                    cl = result["_cal_log"]
                    row += [f"{float(cl[c][i]):.6g}" if np.isfinite(cl[c][i]) else "nan"
                            for c in _CAL_COLS]
                else:
                    row += ["nan"] * len(_CAL_COLS)
                w.writerow(row)

    # ------------------------------------------------------------------
    # metrics.json
    # ------------------------------------------------------------------
    def _write_metrics_json(self, result: dict) -> None:
        (self.outdir / "metrics.json").write_text(json.dumps(result["metrics"], indent=2))

    # ------------------------------------------------------------------
    # plots
    # ------------------------------------------------------------------
    def _write_plots(self, result: dict) -> None:
        # Set the headless backend BEFORE importing pyplot so this works on a
        # headless Linux box without a DISPLAY.
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        pdir = self.outdir / "plots"
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

    # ------------------------------------------------------------------
    # report.md
    # ------------------------------------------------------------------
    def _write_report(self, result: dict, scenario,
                       manifest_payload=None) -> None:
        lines = self._build_report_lines(result, scenario, manifest_payload)
        (self.outdir / "report.md").write_text("\n".join(lines))

    @staticmethod
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

    @classmethod
    def _build_report_lines(cls, result: dict, scenario,
                            manifest_payload=None) -> list[str]:
        m = result["metrics"]
        rt = {0: "passthrough", 1: "first-order", 2: "second-order"}.get(
            result.get("ref_model_type"), "?")

        def group(title, keys):
            rows = [f"| {k} | {cls._fmt(m[k])} |" for k in keys if k in m]
            if not rows:
                return []
            return [f"### {title}", "", "| metric | value |", "|---|---|", *rows, ""]

        # Read envelope from ManifestPayload if provided; fall back to result;
        # the deployment envelope is the default, not "unknown".
        if manifest_payload is not None:
            envelope_str = manifest_payload.envelope or "deployment"
        else:
            envelope_str = result.get("envelope", "deployment")

        return [
            f"# Sim run -- {scenario.name}", "",
            f"- **Axis**: {scenario.axis}",
            f"- **Description**: {scenario.description}",
            f"- **Reference model**: {rt} (type {result.get('ref_model_type')})",
            f"- **Adaptive envelope**: {envelope_str} (spec-11 / sim-arch-04)",
            f"- **MRAC injection**: {'ON' if result['injection'] else 'OFF (shadow)'}",
            f"- **dt**: {result['dt']} s ({1 / result['dt']:.0f} Hz)",
            f"- **Stable**: **{cls._fmt(m.get('stable'))}**", "",
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
