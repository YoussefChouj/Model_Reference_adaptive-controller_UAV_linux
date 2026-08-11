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
from sim.reference_model import ReferenceModel, RefType

# log columns, in CSV order. Must stay aligned with sim/artifact._PRIMARY_COLS.
_COLS = ["t", "r", "d", "xm", "x", "e", "u_nom", "u_ad", "u", "U", "wnorm", "edot"]

_RUNS_DIR = Path(__file__).resolve().parent / "runs"


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
              "_cal_log": cal_history}

    if write_artifacts:
        base = runs_dir if runs_dir is not None else _RUNS_DIR
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        outdir = Path(base) / f"{ts}_{scenario.name}"
        RunArtifactWriter(outdir).write(result, scenario=scenario)
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
    print(f"artifacts -> {res.get('outdir', 'N/A')}")
