"""Deterministic post-hoc trajectory aggregation (spec 4c)."""
from __future__ import annotations

import csv
import math
from pathlib import Path


def aggregate(trajectory_csv_path: str | Path) -> dict:
    """Compute stable summary statistics from a trajectory CSV."""
    sums = {"position_sq": 0.0, "rate_sq": 0.0, "thrust": 0.0}
    max_attitude = 0.0
    max_thrust = 0.0
    first_t: float | None = None
    last_t: float | None = None
    n_samples = 0
    with Path(trajectory_csv_path).open("r", encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            t = float(row["t"])
            x, y, z = float(row["x"]), float(row["y"]), float(row["z"])
            phi = float(row["phi"])
            theta = float(row["theta"])
            psi = float(row["psi"])
            p, q, r = float(row["p"]), float(row["q"]), float(row["r"])
            thrust = float(row["thrust"])
            if first_t is None:
                first_t = t
            last_t = t
            sums["position_sq"] += x * x + y * y + z * z
            sums["rate_sq"] += p * p + q * q + r * r
            sums["thrust"] += thrust
            max_attitude = max(max_attitude, abs(phi), abs(theta), abs(psi))
            max_thrust = max(max_thrust, thrust)
            n_samples += 1
    if n_samples == 0:
        return {
            "rmse_position": 0.0, "max_abs_attitude_deg": 0.0,
            "rms_body_rate_rads": 0.0, "thrust_mean_n": 0.0,
            "thrust_max_n": 0.0, "duration_s": 0.0, "n_samples": 0,
        }
    return {
        "rmse_position": math.sqrt(sums["position_sq"] / n_samples),
        "max_abs_attitude_deg": math.degrees(max_attitude),
        "rms_body_rate_rads": math.sqrt(sums["rate_sq"] / n_samples),
        "thrust_mean_n": sums["thrust"] / n_samples,
        "thrust_max_n": max_thrust,
        "duration_s": float(last_t - first_t) if first_t is not None and last_t is not None else 0.0,
        "n_samples": n_samples,
    }


__all__ = ["aggregate"]