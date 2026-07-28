"""Trajectory runner — drives the 6-DOF plant + outer loops along a
predefined trajectory (spec 4a).

This is the closed-loop runner for the *trajectory* lane. The existing
``sim.run.run`` runner is the rate-loop runner; it operates on a
``Scenario`` that drives a single axis with a rate setpoint. Trajectory
runs need:

  * the full 6-DOF plant (``RigidBodyPlant``)
  * the outer loops (``OuterLoop``) to convert position/attitude targets
    into per-axis rate + thrust commands
  * a dense waypoint sequence (from ``sim.trajectories``)

The output schema matches ``sim.run.run`` as closely as possible: a
``log`` dict with the same keys (so existing metrics + plots work),
plus path-tracking keys (``x_target``, ``y_target``, ``z_target``,
``yaw_target``, ``x_err``, ``y_err``, ``z_err``, ``cross_track_err``,
``along_track_err``) consumed by ``metrics.compute_path``.

The runner is intentionally simple — it is the *environment*, not the
thesis controller. A bespoke trajectory-tracking controller plugs in
by replacing ``OuterLoop`` with the new design; this runner stays as
the comparison baseline.
"""
from __future__ import annotations

import csv
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np

from sim.outer_loops import OuterLoop
from sim.plant import CANONICAL_AIRFRAME, Plant, RigidBodyPlant
from sim.trajectories import Trajectory

_RUNS_DIR = Path(__file__).resolve().parent / "runs"


def _lerp_waypoint(traj: Trajectory, t: float) -> np.ndarray:
    """Index the trajectory at time ``t``; linear interp between samples."""
    wp = traj.waypoints
    if t <= 0.0:
        return wp[0].copy()
    if t >= traj.duration:
        return wp[-1].copy()
    idx = int(np.searchsorted(wp[:, 0], t, side="right")) - 1
    idx = max(0, min(idx, wp.shape[0] - 2))
    a, b = wp[idx], wp[idx + 1]
    span = b[0] - a[0]
    s = (t - a[0]) / span if span > 0 else 0.0
    return a * (1.0 - s) + b * s


def _cross_track(traj: Trajectory, x: float, y: float) -> tuple[float, int]:
    """Closest-point projection of (x,y) onto the trajectory polyline.

    Returns ``(cross_track_err_m, nearest_segment_index)``. The
    ``along_track_err`` for the calling tick is computed by
    ``_along_track_arc`` (arc length between the trajectory target
    at time t and the projected point).
    """
    wp = traj.waypoints
    pts = wp[:, 1:3]                    # (N, 2)
    seg = pts[1:] - pts[:-1]            # (N-1, 2)
    v = seg
    denom = np.sum(v * v, axis=1)
    px = np.array([x, y])
    p0 = pts[:-1]
    t_param = np.sum((px - p0) * v, axis=1) / np.where(denom > 0, denom, 1.0)
    t_clamped = np.clip(t_param, 0.0, 1.0)
    proj = p0 + t_clamped[:, None] * v
    diff = proj - px
    dist = np.linalg.norm(diff, axis=1)
    k = int(np.argmin(dist))
    return float(dist[k]), k


def _along_track_arc(traj: Trajectory, idx_target: int, idx_proj: int) -> float:
    """Signed arc-length between trajectory sample ``idx_target`` and
    the projected point at ``idx_proj``."""
    wp = traj.waypoints
    seg_len = np.linalg.norm(np.diff(wp[:, 1:3], axis=0), axis=1)
    if idx_proj >= idx_target:
        return float(np.sum(seg_len[idx_target:idx_proj]))
    return -float(np.sum(seg_len[idx_proj:idx_target]))


def _state_dict_from_plant(plant: RigidBodyPlant) -> dict:
    """Snapshot the plant's current state into a dict the outer loop reads."""
    w, x, y, z = plant.q
    phi = math.atan2(2.0 * (w * x + y * z),
                     1.0 - 2.0 * (x * x + y * y))
    sth = max(-1.0, min(1.0, 2.0 * (w * y - x * z)))
    theta = math.asin(sth)
    psi = math.atan2(2.0 * (w * z + x * y),
                     1.0 - 2.0 * (y * y + z * z))
    return {
        "x": plant.x, "y": plant.y, "z": plant.z,
        "vx": plant.vx, "vy": plant.vy, "vz": plant.vz,
        "phi": phi, "theta": theta, "psi": psi,
        "p": plant.p, "q": plant.q_rate, "r": plant.r,
    }


def run_trajectory(trajectory: Trajectory, *,
                   dt: float = 0.005,
                   plant: Plant | None = None,
                   outer: OuterLoop | None = None,
                   initial_state: Optional[dict] = None,
                   write_artifacts: bool = True,
                   runs_dir: Path | None = None,
                   tag: str = "") -> dict:
    """Drive the analytic 6-DOF plant along ``trajectory``.

    Returns a dict with ``log`` (compatible with sim.metrics.compute and
    sim.metrics.compute_path), ``scenario`` name, ``outdir`` if
    artifacts were written, and ``trajectory`` itself.
    """
    # 1. Plant + outer loop.
    if plant is None:
        plant = RigidBodyPlant(dt=dt, airframe=CANONICAL_AIRFRAME,
                               initial_state=initial_state)
    else:
        plant.reset(initial_state)
    if outer is None:
        outer = OuterLoop(dt=dt, mass=CANONICAL_AIRFRAME.mass,
                          gravity=9.80665)
    outer.reset()
    # 2. Log arrays.
    n = int(round(trajectory.duration / dt)) + 1
    log: dict = {
        "t": np.empty(n),
        # target trajectory at this tick (for path metrics)
        "x_target": np.empty(n), "y_target": np.empty(n), "z_target": np.empty(n),
        "yaw_target": np.empty(n),
        # realised plant state
        "x": np.empty(n), "y": np.empty(n), "z": np.empty(n),
        "vx": np.empty(n), "vy": np.empty(n), "vz": np.empty(n),
        "phi": np.empty(n), "theta": np.empty(n), "psi": np.empty(n),
        "p": np.empty(n), "q": np.empty(n), "r": np.empty(n),
        "thrust": np.empty(n),
        # per-axis commands issued (firmware u-units)
        "roll_cmd": np.empty(n), "pitch_cmd": np.empty(n),
        "yaw_cmd": np.empty(n), "z_cmd": np.empty(n),
        # raw tracking errors
        "x_err": np.empty(n), "y_err": np.empty(n), "z_err": np.empty(n),
        "cross_track_err": np.empty(n),
        "along_track_err": np.empty(n),
    }
    # 3. Loop. Read pre-step state, compute outer-loop command, advance.
    for k in range(n):
        t = k * dt
        # Read pre-step state.
        state = _state_dict_from_plant(plant)  # type: ignore[arg-type]
        wp = _lerp_waypoint(trajectory, t)
        target = {"x": float(wp[1]), "y": float(wp[2]),
                  "z": float(wp[3]), "yaw": float(wp[4])}
        # Outer loop -> per-axis command (rate + thrust).
        u = outer.tick(state, target)
        # Step plant. Plant returns post-step state.
        state_next = plant.step(u)
        # Log.
        log["t"][k] = t
        log["x_target"][k] = target["x"]
        log["y_target"][k] = target["y"]
        log["z_target"][k] = target["z"]
        log["yaw_target"][k] = target["yaw"]
        log["x"][k] = state_next["x"]
        log["y"][k] = state_next["y"]
        log["z"][k] = state_next["z"]
        log["vx"][k] = state_next["vx"]
        log["vy"][k] = state_next["vy"]
        log["vz"][k] = state_next["vz"]
        log["phi"][k] = state_next["phi"]
        log["theta"][k] = state_next["theta"]
        log["psi"][k] = state_next["psi"]
        log["p"][k] = state_next["p"]
        log["q"][k] = state_next["q"]
        log["r"][k] = state_next["r"]
        log["thrust"][k] = state_next["thrust"]
        log["roll_cmd"][k] = u["roll"]
        log["pitch_cmd"][k] = u["pitch"]
        log["yaw_cmd"][k] = u["yaw"]
        log["z_cmd"][k] = u["z"]
        log["x_err"][k] = target["x"] - state_next["x"]
        log["y_err"][k] = target["y"] - state_next["y"]
        log["z_err"][k] = target["z"] - state_next["z"]
        # Path projection (XY).
        ct, k_proj = _cross_track(trajectory, state_next["x"], state_next["y"])
        log["cross_track_err"][k] = ct
        idx_t = max(0, min(int(round(t / dt)), trajectory.n - 1))
        log["along_track_err"][k] = _along_track_arc(trajectory, idx_t, k_proj)
    result = {
        "scenario": trajectory.name,
        "axis": "trajectory",
        "dt": dt,
        "log": log,
        "metrics": {},     # filled by caller
        "trajectory": trajectory,
    }
    if write_artifacts:
        result["outdir"] = str(_write_traj(trajectory, result, runs_dir, tag))
    return result


def _write_traj(traj: Trajectory, result: dict, runs_dir: Path | None,
                tag: str) -> Path:
    base = runs_dir if runs_dir is not None else _RUNS_DIR
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = f"_{tag}" if tag else ""
    out = Path(base) / f"{ts}_{traj.name}{suffix}"
    (out / "plots").mkdir(parents=True, exist_ok=True)
    log = result["log"]
    cols = ["t", "x_target", "y_target", "z_target", "yaw_target",
            "x", "y", "z", "vx", "vy", "vz",
            "phi", "theta", "psi", "p", "q", "r", "thrust",
            "roll_cmd", "pitch_cmd", "yaw_cmd", "z_cmd",
            "x_err", "y_err", "z_err",
            "cross_track_err", "along_track_err"]
    with open(out / "data.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for i in range(len(log["t"])):
            w.writerow([f"{log[c][i]:.6g}" for c in cols])
    (out / "metrics.json").write_text(json.dumps(result.get("metrics", {}),
                                                 indent=2))
    _traj_plots(out / "plots", result)
    return out


def _traj_plots(pdir: Path, result: dict) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    log = result["log"]
    # XY path
    fig, ax = plt.subplots()
    ax.plot(log["x_target"], log["y_target"], "k--", lw=1, label="target")
    ax.plot(log["x"], log["y"], "C0", lw=1.5, label="actual")
    ax.set(xlabel="x [m]", ylabel="y [m]", title=f"{result['scenario']} -- XY path")
    ax.legend(); ax.grid(True, alpha=0.3)
    fig.savefig(pdir / "path_xy.png", dpi=110, bbox_inches="tight"); plt.close(fig)
    # Cross-track error over time
    fig, ax = plt.subplots()
    ax.plot(log["t"], log["cross_track_err"], "C3", label="cross-track error")
    ax.set(xlabel="t [s]", ylabel="cross-track [m]", title="cross-track error")
    ax.legend(); ax.grid(True, alpha=0.3)
    fig.savefig(pdir / "cross_track.png", dpi=110, bbox_inches="tight"); plt.close(fig)
    # Altitude
    fig, ax = plt.subplots()
    ax.plot(log["t"], log["z_target"], "k--", lw=1, label="z target")
    ax.plot(log["t"], log["z"], "C0", lw=1.5, label="z actual")
    ax.set(xlabel="t [s]", ylabel="z [m]", title="altitude tracking")
    ax.legend(); ax.grid(True, alpha=0.3)
    fig.savefig(pdir / "altitude.png", dpi=110, bbox_inches="tight"); plt.close(fig)
    # Attitude
    fig, ax = plt.subplots()
    ax.plot(log["t"], np.rad2deg(log["phi"]), label="phi")
    ax.plot(log["t"], np.rad2deg(log["theta"]), label="theta")
    ax.plot(log["t"], np.rad2deg(log["psi"]), label="psi")
    ax.set(xlabel="t [s]", ylabel="attitude [deg]", title="attitude")
    ax.legend(); ax.grid(True, alpha=0.3)
    fig.savefig(pdir / "attitude.png", dpi=110, bbox_inches="tight"); plt.close(fig)