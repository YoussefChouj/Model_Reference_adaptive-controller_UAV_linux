"""Run evaluation — one place that answers "was this a good run?".

Pure: takes a finished run's log (the arrays run.py records) plus the adaptive
config context, returns a flat metrics dict. No closed loop, no plotting, no I/O —
so every metric is unit-testable against a hand-built log, and `run`, `report`, and
the experiment sweeps all read the *same* numbers.

Grouped (flat keys, prefixed) so metrics.json paints a global + detailed picture:
  track_*  tracking error vs the reference model (and vs the raw command)
  ctrl_*   control effort / actuator stress / saturation
  adapt_*  adaptation health (how hard, how long, did it hit a bound)
  robust_* stability / oscillation / derivative-noise proxies
  dist_*   disturbance response (only when a disturbance is present)
  path_*   trajectory-tracking: cross-track, along-track, position RMSE,
           control effort, saturation, attitude-rate aggressiveness
           (spec 4a)

Legacy top-level keys (rmse_track, max_abs_err, final_weight_norm, max_weight_norm,
max_abs_rate, max_abs_xm, stable) are preserved for existing callers/tests.
"""
from __future__ import annotations

from typing import Optional, Sequence

import numpy as np

_EPS = 1e-12


def _rms(a: np.ndarray) -> float:
    return float(np.sqrt(np.mean(a ** 2))) if a.size else 0.0


def _zero_crossings(a: np.ndarray) -> int:
    s = np.sign(a)
    s = s[s != 0.0]
    if s.size < 2:
        return 0
    return int(np.count_nonzero(np.diff(s) != 0))


def _settling_time(t: np.ndarray, e: np.ndarray, band: float) -> Optional[float]:
    """Last time |e| leaves ``band``, +1 sample. None if it ends outside the band."""
    viol = np.abs(e) > band
    if not viol.any():
        return float(t[0])
    last = int(np.nonzero(viol)[0][-1])
    if last >= len(t) - 1:
        return None  # still outside the band at the end -> did not settle
    return float(t[last + 1])


def compute(log: dict, theta: np.ndarray, dt: float, *,
            umax: Optional[float] = None,
            what_limit: Optional[Sequence[float]] = None,
            what_tol: Optional[Sequence[float]] = None,
            what_lower: Optional[Sequence[float]] = None,
            e_deadzone: Optional[float] = None,
            e_freeze: Optional[float] = None) -> dict:
    """Compute the full metric set from a finished run log."""
    t = np.asarray(log["t"], float)
    e = np.asarray(log["e"], float)
    x = np.asarray(log["x"], float)
    xm = np.asarray(log["xm"], float)
    r = np.asarray(log["r"], float)
    u = np.asarray(log["u"], float)
    u_nom = np.asarray(log["u_nom"], float)
    u_ad = np.asarray(log["u_ad"], float)
    U = np.asarray(log["U"], float)
    wnorm = np.asarray(log["wnorm"], float)
    n = len(t)
    tail = slice(max(0, int(0.9 * n)), n)          # last 10% = "steady state"
    ref_scale = max(float(np.max(np.abs(xm))) if n else 0.0,
                    float(np.max(np.abs(x))) if n else 0.0, _EPS)
    band = 0.05 * ref_scale                          # 5%-of-reference settling band

    finite = bool(np.all(np.isfinite(x)) and np.all(np.isfinite(wnorm)))
    stable = bool(finite and (np.max(np.abs(x)) < 1e3 if n else True))

    m: dict = {}

    # --- tracking (vs reference model, and vs raw command) ---
    m["rmse_track"] = _rms(e)
    m["max_abs_err"] = float(np.max(np.abs(e))) if n else 0.0
    m["track_iae"] = float(np.sum(np.abs(e)) * dt)
    m["track_ise"] = float(np.sum(e ** 2) * dt)
    m["track_itae"] = float(np.sum(t * np.abs(e)) * dt)
    m["track_ss_abs_err"] = float(np.mean(np.abs(e[tail]))) if n else 0.0
    m["track_rmse_vs_cmd"] = _rms(x - r)             # includes ref-model lag
    m["track_settling_time"] = _settling_time(t, e, band) if n else None
    m["track_peak_overshoot_pct"] = (
        float((np.max(np.abs(x)) - np.max(np.abs(xm))) / np.max(np.abs(xm)) * 100.0)
        if n and np.max(np.abs(xm)) > _EPS else None)

    # --- control effort / actuator stress ---
    m["ctrl_u_rms"] = _rms(u)
    m["ctrl_u_nom_rms"] = _rms(u_nom)
    m["ctrl_u_ad_rms"] = _rms(u_ad)
    m["ctrl_max_abs_u"] = float(np.max(np.abs(u))) if n else 0.0
    m["ctrl_max_abs_u_ad"] = float(np.max(np.abs(u_ad))) if n else 0.0
    m["ctrl_mrac_footprint"] = float(_rms(u_ad) / (_rms(u_nom) + _EPS))
    m["ctrl_u_rate_max"] = float(np.max(np.abs(np.diff(u))) / dt) if n > 1 else 0.0
    if umax is not None:
        m["ctrl_sat_fraction"] = float(np.mean(np.abs(U) >= umax - _EPS)) if n else 0.0

    # --- adaptation health ---
    m["final_weight_norm"] = float(wnorm[-1]) if n else 0.0
    m["max_weight_norm"] = float(np.max(wnorm)) if n else 0.0
    m["adapt_weight_rate_mean"] = (
        float(np.mean(np.abs(np.diff(wnorm))) / dt) if n > 1 else 0.0)
    if e_deadzone is not None:
        m["adapt_active_fraction"] = float(np.mean(np.abs(e) >= e_deadzone)) if n else 0.0
    if e_freeze is not None and e_freeze > 0.0:
        m["adapt_freeze_fraction"] = float(np.mean(np.abs(e) > e_freeze)) if n else 0.0
    theta = np.asarray(theta, float)
    theta_final = theta[-1] if theta.size else np.zeros(0)
    m["adapt_theta_final"] = [float(v) for v in theta_final]
    if what_limit is not None:
        lim = np.asarray(what_limit, float)
        low = np.asarray(what_lower, float) if what_lower is not None else np.zeros_like(lim)
        tol = np.asarray(what_tol, float) if what_tol is not None else np.zeros_like(lim)
        # upper saturation = the actionable case (adaptation ran out of authority);
        # lower-pinned is expected at rest under the What_lower_limit=0 quirk.
        upper_sat = np.abs(theta_final - lim) <= np.maximum(tol, _EPS)
        lower_pin = np.abs(theta_final - low) <= np.maximum(tol, _EPS)
        m["adapt_upper_sat"] = [bool(v) for v in upper_sat]
        m["adapt_lower_pinned"] = [bool(v) for v in lower_pin]
        m["adapt_any_upper_sat"] = bool(np.any(upper_sat))

    # --- robustness / stability ---
    m["stable"] = stable
    m["robust_diverged"] = bool(not finite)
    m["max_abs_rate"] = float(np.max(np.abs(x))) if n else 0.0
    m["max_abs_xm"] = float(np.max(np.abs(xm))) if n else 0.0
    m["robust_err_zero_crossings"] = _zero_crossings(e)
    if "edot" in log:
        m["robust_edot_rms"] = _rms(np.asarray(log["edot"], float))

    # --- disturbance response (only when a disturbance is actually injected) ---
    if "d" in log:
        d = np.asarray(log["d"], float)
        nz = np.nonzero(np.abs(d) > _EPS)[0]
        if nz.size:
            onset = int(nz[0])
            post = slice(onset, n)
            m["dist_onset_t"] = float(t[onset])
            m["dist_peak_dev"] = float(np.max(np.abs(e[post])))
            m["dist_recovery_time"] = _recovery_time(t, e, band, onset)

    return m


def compute_path(log: dict, *, dt: float,
                 z_umax: float | None = None,
                 attitude_rate_umax: float | None = None,
                 transient_seconds: float = 1.0,
                 trajectory=None) -> dict:
    """Trajectory-tracking metrics (spec 4a path_* group).

    Computed against a trajectory-runner's log (see
    ``sim.trajectory_runner.run_trajectory``). Required log keys:

      t, x_target, y_target, z_target, x, y, z, cross_track_err,
      along_track_err, roll_cmd, pitch_cmd, yaw_cmd, z_cmd, p, q, r

    All keys are absolute scalar arrays of equal length. The metric
    set covers the spec's user stories 15-18:

      * path_rms_cross_track, path_max_cross_track      (15)
      * path_rms_along_track, path_max_abs_along_track (15)
      * path_rms_position, path_max_abs_position       (16)
      * path_ctrl_effort_rms, path_ctrl_effort_max      (16)
      * path_sat_fraction_z, path_sat_fraction_att_rate (17)
      * path_att_rate_rms, path_att_rate_max            (18)

    Plus the two additions from the prior-10 spec:
      * path_max_error  -- max over entire run of ||position_error||
      * path_transient_error -- max error over the first transient_seconds

    ``metrics.py`` stays **pure and log-only**: it does not import the
    runner or the trajectories module, so trajectory runs cannot leak
    into rate-loop metric calculation.

    Args:
        log: the trajectory run log dict
        dt: control tick interval, seconds (for duration computations)
        z_umax: optional z-command saturation threshold (N)
        attitude_rate_umax: optional attitude-rate saturation threshold (rad/s)
        transient_seconds: time window for the transient error metric (default 1.0 s)
        trajectory: optional ``Trajectory`` object; if provided and
            ``use_closed_form=True`` was passed to the runner,
            closed-form cross-track / along-track is recomputed here
            (the runner already stores them in the log; this param is
            for recomputation in post-hoc analysis). Currently unused
            but reserved for future re-projection.
    """
    m: dict = {}
    t = np.asarray(log["t"], float)
    n = len(t)
    if n == 0:
        return m
    ct = np.asarray(log["cross_track_err"], float)
    at = np.asarray(log["along_track_err"], float)
    pos_err = np.sqrt(
        (np.asarray(log["x"], float) - np.asarray(log["x_target"], float)) ** 2
        + (np.asarray(log["y"], float) - np.asarray(log["y_target"], float)) ** 2
        + (np.asarray(log["z"], float) - np.asarray(log["z_target"], float)) ** 2
    )
    m["path_n_samples"] = int(n)
    m["path_duration_s"] = float(t[-1] - t[0])
    # --- max error (entire run) ---
    m["path_max_error"] = float(np.max(pos_err))
    # --- transient error (first transient_seconds) ---
    transient_cut = float(transient_seconds)
    transient_mask = t <= transient_cut
    if np.any(transient_mask):
        m["path_transient_error"] = float(np.max(pos_err[transient_mask]))
    else:
        m["path_transient_error"] = float(np.max(pos_err))
    # --- cross-track / along-track ---
    m["path_rms_cross_track"] = float(np.sqrt(np.mean(ct ** 2)))
    m["path_max_cross_track"] = float(np.max(ct))
    m["path_mean_cross_track"] = float(np.mean(ct))
    m["path_rms_along_track"] = float(np.sqrt(np.mean(at ** 2)))
    m["path_max_abs_along_track"] = float(np.max(np.abs(at)))
    m["path_final_along_track"] = float(at[-1])
    # --- position RMSE ---
    m["path_rms_position"] = float(np.sqrt(np.mean(pos_err ** 2)))
    m["path_max_abs_position"] = float(np.max(pos_err))
    m["path_rms_xyz"] = {
        "x": float(np.sqrt(np.mean(
            (np.asarray(log["x"], float) - np.asarray(log["x_target"], float)) ** 2
        ))),
        "y": float(np.sqrt(np.mean(
            (np.asarray(log["y"], float) - np.asarray(log["y_target"], float)) ** 2
        ))),
        "z": float(np.sqrt(np.mean(
            (np.asarray(log["z"], float) - np.asarray(log["z_target"], float)) ** 2
        ))),
    }
    # --- control effort ---
    rc = np.asarray(log["roll_cmd"], float)
    pc = np.asarray(log["pitch_cmd"], float)
    yc = np.asarray(log["yaw_cmd"], float)
    zc = np.asarray(log["z_cmd"], float)
    effort = np.sqrt(rc ** 2 + pc ** 2 + yc ** 2)
    m["path_ctrl_effort_rms"] = float(np.sqrt(np.mean(effort ** 2)))
    m["path_ctrl_effort_max"] = float(np.max(effort))
    m["path_ctrl_effort_per_axis_rms"] = {
        "roll": float(np.sqrt(np.mean(rc ** 2))),
        "pitch": float(np.sqrt(np.mean(pc ** 2))),
        "yaw": float(np.sqrt(np.mean(yc ** 2))),
    }
    # --- saturation ---
    if z_umax is not None and z_umax > 0:
        m["path_sat_fraction_z"] = float(np.mean(np.abs(zc) >= z_umax))
    if attitude_rate_umax is not None and attitude_rate_umax > 0:
        rate_cmd = np.sqrt(
            np.asarray(log["p"], float) ** 2
            + np.asarray(log["q"], float) ** 2
            + np.asarray(log["r"], float) ** 2
        )
        m["path_sat_fraction_att_rate"] = float(
            np.mean(rate_cmd >= attitude_rate_umax))
    # --- attitude-rate aggressiveness (proxy for path curvature hit) ---
    pr = np.asarray(log["p"], float)
    qr = np.asarray(log["q"], float)
    rr = np.asarray(log["r"], float)
    rate_rms = np.sqrt(pr ** 2 + qr ** 2 + rr ** 2)
    m["path_att_rate_rms"] = float(np.sqrt(np.mean(rate_rms ** 2)))
    m["path_att_rate_max"] = float(np.max(rate_rms))
    m["path_att_rate_per_axis_rms"] = {
        "roll": float(np.sqrt(np.mean(pr ** 2))),
        "pitch": float(np.sqrt(np.mean(qr ** 2))),
        "yaw": float(np.sqrt(np.mean(rr ** 2))),
    }
    # Path-coverage proxy: did the drone follow the trajectory end-to-end?
    final_pos_err = float(np.sqrt(
        (log["x"][-1] - log["x_target"][-1]) ** 2
        + (log["y"][-1] - log["y_target"][-1]) ** 2
        + (log["z"][-1] - log["z_target"][-1]) ** 2
    ))
    m["path_final_position_error"] = final_pos_err
    # NOTE: adaptation-activity metrics (adapt_active_fraction, converged weights)
    # require MRAC in the trajectory loop. Deferred: wire sim/loop.py into
    # trajectory_runner when prior-06 (injection seam) is available.
    return m


def _recovery_time(t: np.ndarray, e: np.ndarray, band: float,
                   onset: int) -> Optional[float]:
    """Time from disturbance onset until |e| returns to ``band`` and stays."""
    post = np.abs(e[onset:]) > band
    if not post.any():
        return 0.0
    last = int(np.nonzero(post)[0][-1])
    if onset + last >= len(t) - 1:
        return None  # never recovered within the run
    return float(t[onset + last + 1] - t[onset])
