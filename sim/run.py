"""Closed-loop runner: wires plant + reference model + baseline PID + MRAC.

One tick is delegated to sim.loop.ControlLoop (the wiring seam, PARITY:
API/mrac.c:424-485). This module owns the simulation clock, the log arrays,
the metrics call (sim.metrics), and dispatches artifact writing to
``sim.artifact.RunArtifactWriter`` when ``write_artifacts=True``.

ADR-0011 Phases 3 & 4: ``CalibratorStep`` (sim/calibrator_step.py) owns the
per-tick calibrator wiring. ``run()`` simply calls ``cal.tick(...)`` every
iteration; the step handles ``_has_cal``, the flying + ``t > 2.0`` gate, and
the gyro FSM internals.

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
from sim.artifact import RunArtifactWriter
from sim.baseline import RatePID, RatePIDConfig
from sim.calibrator_step import CalibratorStep
from sim.loop import ControlLoop
from sim.plant import CANONICAL_MODELS
from sim.priors import (
    ConvergenceResult,
    FEATURE_SERIES_COLUMNS,
    PriorFactory,
    RegressorVariant,
    to_dimensionless,
)
from sim.regressor import structured_regressor
from sim.reference_model import ReferenceModel, RefType

# log columns, in CSV order. Must stay aligned with sim/artifact._PRIMARY_COLS.
_COLS = ["t", "r", "d", "xm", "x", "e", "u_nom", "u_ad", "u", "U", "wnorm", "edot"]

_RUNS_DIR = Path(__file__).resolve().parent / "runs"

# prior-05 fitting window: 1 s at 200 Hz = 200 samples; 50-tick lag = 0.25 s.
_DRIFT_WINDOW_S = 1.0
_DRIFT_LAG_TICKS = 50
_DRIFT_MIN_SAMPLES = _DRIFT_LAG_TICKS + 1
_DRIFT_MAX = 1e-3
_DRIVE_RMS_MAX = 1e-2
_FINAL_NORM_MAX_MULT = 2.0


def _plant_tag_for_axis(axis: str) -> tuple:
    """Resolve the identified (K, p, T) for the axis (CANONICAL_MODELS)."""
    model = CANONICAL_MODELS[axis]
    return (float(model.K), model.pole, float(model.delay))


def _build_convergence(theta_hist: np.ndarray, e_series: np.ndarray,
                       edot_series: np.ndarray, dt: float,
                       law, _scenario: str) -> ConvergenceResult:
    """Compute the four convergence metrics from a closed-loop run.

    ``weight_drift`` follows the spec formula (ADR-0014 D8):
    ``mean(||Theta[k] - Theta[k - LAG]||)`` over the last 1 s window
    with LAG = 50 ticks (0.25 s at 200 Hz). Vector differences, not
    scalar-norm differences — trajectories with constant norm but
    rotating direction report zero drift only when the direction is
    truly frozen, which is the point of the spec.

    ``drive_rms`` uses a second-order-aware proxy: ``s`` is
    ``e * Pe + e_dot * Pedot`` for the 2nd-order law, and reduces to
    ``e * Pe`` for 1st-order. The recorded ``e`` and ``edot`` series
    are the surface signals; the proxy
    ``sqrt(e^2 + (e_dot * tau_eff)^2)`` with ``tau_eff = 1/wc_edot``
    captures the second-order case (e=0, e_dot≠0 ⇒ s≠0 ⇒ drive_rms≠0)
    while reducing to ``|e|`` for 1st-order. Thresholded by ADR-0014 D8.
    Units: ||Theta|| is dimensionless, drive_rms is in rad/s.
    """
    if theta_hist.size == 0:
        return ConvergenceResult(0.0, 0.0, 0.0, 0.0, well_posed=False)
    norms = np.linalg.norm(theta_hist, axis=1)
    final_norm = float(norms[-1])
    max_norm = float(np.max(norms))
    last = max(int(_DRIFT_WINDOW_S / dt), 1)
    # Vector-lag difference: ||theta_hist[k] - theta_hist[k-50]|| for each
    # k in the trailing 1 s. Floor to 0.0 when there isn't enough history.
    if (theta_hist.shape[0] < _DRIFT_MIN_SAMPLES
            or norms.shape[0] < _DRIFT_MIN_SAMPLES):
        weight_drift = 0.0
    else:
        # Clamp the window so a short run does not walk off the start.
        end_k = theta_hist.shape[0]
        start_k = max(end_k - last, _DRIFT_LAG_TICKS)
        # Vector differences with LAG_TICKS offset.
        diffs = (theta_hist[start_k:end_k]
                 - theta_hist[start_k - _DRIFT_LAG_TICKS:end_k - _DRIFT_LAG_TICKS])
        weight_drift = float(np.mean(np.linalg.norm(diffs, axis=1)))
    # Second-order-aware drive proxy. tau_eff = 1/wc_edot (the e_dot LPF cutoff)
    # rescales e_dot so it sits in the same order of magnitude as e. For 1st-order
    # law e_dot is small in steady state, so the proxy reduces to ~|e|.
    tau_eff = 1.0 / float(getattr(law, "wc_edot", 30.0))
    e_tail = np.asarray(e_series[-last:], dtype=float)
    edot_tail = np.asarray(edot_series[-last:], dtype=float)
    if e_tail.size == 0:
        drive_rms = 0.0
    else:
        # Broadcast-friendly shape when edot_tail is empty: zero it.
        if edot_tail.size != e_tail.size:
            edot_tail = np.zeros_like(e_tail)
        s_proxy = np.sqrt(e_tail * e_tail + (edot_tail * tau_eff) ** 2)
        drive_rms = float(np.sqrt(np.mean(s_proxy ** 2)))
    well_posed = (weight_drift < _DRIFT_MAX
                  and drive_rms < _DRIVE_RMS_MAX
                  and final_norm < _FINAL_NORM_MAX_MULT * max(max_norm, 1e-12))
    return ConvergenceResult(
        weight_drift=weight_drift,
        drive_rms=drive_rms,
        final_norm=final_norm,
        max_norm=max_norm,
        well_posed=well_posed,
    )


def _convergence_to_dict(conv: ConvergenceResult) -> dict:
    return {
        "weight_drift": conv.weight_drift,
        "drive_rms": conv.drive_rms,
        "final_norm": conv.final_norm,
        "max_norm": conv.max_norm,
        "well_posed": conv.well_posed,
    }


def _write_features_csv(outdir: Path, log: dict, theta_hist: np.ndarray,
                        dt: float, axis: str) -> Path:
    """Write the per-tick ``features.csv`` (FEATURE_SERIES_COLUMNS).

    Phi is recomputed per tick from the recorded (x, u_nom, xm) using
    ``structured_regressor``; ``theta_dot_norm`` is the finite-difference
    norm of consecutive Theta rows (last value 0 when the buffer has one
    row). Cross-coupling for pitch/roll would require 6-DOF state, not
    available here; ``cross=0.0`` keeps the slot in line with the rest of
    the sim/plant is 3-state-only in this scope.
    """
    path = Path(outdir) / "features.csv"
    n = log["t"].shape[0]
    features = np.empty((n, len(FEATURE_SERIES_COLUMNS)), dtype=float)
    for k in range(n):
        phi = structured_regressor(axis, x=float(log["x"][k]),
                                   u_nom=float(log["u_nom"][k]),
                                   xm=float(log["xm"][k]))
        features[k, 0] = float(log["t"][k])
        features[k, 1] = float(log["x"][k])
        features[k, 2] = float(log["u_nom"][k])
        features[k, 3] = float(log["xm"][k])
        features[k, 4] = float(log["e"][k])
        features[k, 5:11] = phi
        if k == 0:
            features[k, 11] = 0.0
        else:
            features[k, 11] = float(np.linalg.norm(
                theta_hist[k] - theta_hist[k - 1])) / dt
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(FEATURE_SERIES_COLUMNS)
        for row in features:
            writer.writerow([f"{v:.6g}" for v in row])
    return path


def _build_prior_record(*, factory: PriorFactory, theta: np.ndarray,
                        convergence: ConvergenceResult):
    """Build a Prior iff ``convergence.well_posed``; return ``None`` otherwise."""
    if not convergence.well_posed:
        return None
    try:
        prior = factory.build(theta, convergence)
    except ValueError:
        return None
    return {
        "theta_tilde": np.asarray(prior.theta_tilde, dtype=float).tolist(),
        "plant_tag": list(prior.plant_tag),
        "regressor_variant_id": prior.regressor_variant_id,
        "source_scenario": prior.source_scenario,
    }


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

    ADR-0011 Phases 3 & 4: see ``sim.calibrator_step`` for the per-tick wiring.
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
    cal = CalibratorStep(plant, dt)

    n = int(round(scenario.duration / dt))
    log = {k: np.empty(n) for k in _COLS}
    theta_hist = np.empty((n, law.n))
    cal_history = cal.history(n)  # pre-allocate; None when plant has no sensor IF

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
        cal.tick(t=t, r=r, g_ref=(0.0, 0.0, 1000.0),
                 g_meas=plant.get_accel_mg() if cal.has_cal else (0.0, 0.0, 0.0),
                 gyro_rads=plant.get_gyro_rads() if cal.has_cal else (0.0, 0.0, 0.0),
                 rc_active=False)

    metrics = metrics_mod.compute(
        log, theta_hist, dt,
        umax=pid.cfg.UMax,
        what_limit=config.What_limit, what_tol=config.What_tol,
        what_lower=config.What_lower_limit,
        e_deadzone=config.e_deadzone if flags.deadzone_on else None,
        e_freeze=config.e_freeze if flags.hard_freeze_on else None)

    # spec-11: record final weights so the same config can be replayed
    # under the deployment envelope (paired learn/deploy experiment).
    config.theta_final = theta_hist[-1].copy()

    snap = cal.snapshot()
    conv = _build_convergence(theta_hist, log["e"], log["edot"], dt, law,
                              scenario.name)
    plant_tag = _plant_tag_for_axis(axis)
    variant_id = "default"
    theta_tilde = to_dimensionless(
        theta_hist[-1], plant_tag, RegressorVariant.get(variant_id))
    result = {"scenario": scenario.name, "axis": axis, "injection": injection,
              "dt": dt, "ref_model_type": int(ref.kind),
              "envelope": config.envelope,   # spec-11: which envelope produced this run
              "log": log,
              "theta": theta_hist, "metrics": metrics,
              "acc_trim_b_a": snap["b_a"],
              "acc_trim_settled": snap["acc_trim_settled"],
              "gyro_hot_b_g": snap["b_g"],
              "gyro_hot_state": snap["gyro_state"],
              "gyro_hot_rejected": snap["gyro_rejected"],
              # spec-11 + prior-05: prior factory inputs land on the result dict
              # so the artifact writer (sim/artifact.py) records them.
              "plant_tag": list(plant_tag),
              "regressor_variant_id": variant_id,
              "theta_tilde_raw": theta_tilde.tolist(),
              "convergence": _convergence_to_dict(conv),
              "target_valid": bool(conv.well_posed),
              "prior": _build_prior_record(
                  factory=PriorFactory(
                      plant_tag=plant_tag,
                      variant_id=variant_id,
                      source_scenario=scenario.name),
                  theta=theta_hist[-1],
                  convergence=conv),
              "_cal_log": cal_history,
              # manifest: sim-arch-04 schema consolidation
              "scenario_dict": {"name": scenario.name},
              "git_sha": "unknown",   # filled by write_manifest caller
              "sim_sha": "unknown",
              "urdf_sha": "unknown",
              "wall_time_s": 0.0,
              "sim_time_s": 0.0,
              "exit_reason": "completed",
              "machine": None,
              "spawn_z": None,
              "plant_name": "identified",
              }

    if write_artifacts:
        base = runs_dir if runs_dir is not None else _RUNS_DIR
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        outdir = Path(base) / f"{ts}_{scenario.name}"
        from sim.manifest_schema import ManifestPayload
        payload = ManifestPayload.from_run_result(result)
        from sim.manifest import write_manifest
        write_manifest(outdir, payload=payload)
        RunArtifactWriter(outdir).write(result, scenario=scenario,
                                        manifest_payload=payload)
        # Per-tick features.csv (FEATURE_SERIES_COLUMNS, ADR-0014 D3).
        _write_features_csv(outdir, log, theta_hist, dt, axis)
        result["outdir"] = str(outdir)
    return result


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
    print(f"prior: well_posed={res['convergence']['well_posed']}, "
          f"weight_drift={res['convergence']['weight_drift']:.3g}, "
          f"drive_rms={res['convergence']['drive_rms']:.3g}")
    print(f"artifacts -> {res.get('outdir', 'N/A')}")
