"""Flight-log validation of the analytic 6-DOF plant (spec 4a).

This is the gate for the MBD track: it replaces SIL (no firmware twin
of the 6-DOF plant exists) by replaying the **actual recorded control
inputs** from a real flight log through the analytic plant and
comparing the predicted motion against the recorded motion.

Workflow:
  1. Load a long-format flight CSV (``t_s, frame, key, value``).
  2. Extract the per-tick control inputs the firmware commanded:
     ``mrac.{roll,pitch,yaw,z}.u_nom`` (PID) + ``mrac.{...}.u_ad``
     (adaptation). Sum to recover the firmware u dict.
  3. Step the analytic plant with those commands at the same dt the
     log was sampled at (default 5 ms = 200 Hz).
  4. Compare the predicted motion against the recorded
     ``gyrox/y/z`` (body rates, rad/s) and ``imu_data.rol/pit/yaw``
     (Euler, deg) where present. ``imu_data.yaw`` is documented as
     UNUSABLE (constant 2.45 deg/s drift with the drone still), so it
     is excluded from the comparison.
  5. Report fidelity numbers + write a per-run JSON sidecar next to
     the input CSV.

This is *not* a thesis-validation claim. It is the model-fidelity
check the spec requires: how well the analytic plant predicts real
motion under real commands, and how much of the gap is explained by
named modelling gaps (aerodynamic drag, ground effect, prop wash,
battery sag, frame flex).

Usage:
    python -m sim.tools.replay_flight_plant logs/flight_XXX.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

import numpy as np

from sim.plant import CANONICAL_AIRFRAME, RigidBodyPlant


# mrac.z.u_nom is **thrust** in firmware u-units (N, after the
# mrac_to_mixer_Z inverse). The MRAC's z channel carries the position
# loop's thrust demand. Without a recorded position-loop output, we
# assume hover thrust = m*g for the duration of the replay.
DEFAULT_HOVER_THRUST_N = CANONICAL_AIRFRAME.mass * 9.80665


def _to_float(s: str) -> float:
    try:
        return float(s)
    except (ValueError, TypeError):
        return float("nan")


def load_flight_long(csv_path: Path) -> list[dict]:
    """Load a long-format flight CSV; return per-tick dict (one per OF row).

    Long format: ``t_s, frame, key, value``. We keep every row; the
    A and B frames have rate-loop telemetry (mrac.roll.e, u_nom, u_ad),
    the OF frame has imu_data / gyro readings. A single "tick" is the
    union of all keys observed at a given t_s.
    """
    by_t: dict[float, dict] = {}
    with csv_path.open() as f:
        for row in csv.DictReader(f):
            t = _to_float(row["t_s"])
            if math.isnan(t):
                continue
            slot = by_t.get(t)
            if slot is None:
                slot = {"t_s": t}
                by_t[t] = slot
            slot[f"{row['frame']}.{row['key']}"] = _to_float(row["value"])
    return [by_t[t] for t in sorted(by_t.keys())]


def _firmware_u(tick: dict, axis: str) -> float:
    """Sum u_nom + u_ad for one axis from a flight-log tick.

    Falls back to 0 if the log does not record this axis (e.g. logs
    before the z channel was wired).
    """
    nom = tick.get(f"A.mrac.{axis}.u_nom", 0.0)
    ad = tick.get(f"A.mrac.{axis}.u_ad", 0.0)
    if math.isnan(nom):
        nom = 0.0
    if math.isnan(ad):
        ad = 0.0
    return nom + ad


def replay(csv_path: Path, *, dt: float = 0.005,
           write_json: bool = True) -> dict:
    """Replay ``csv_path`` through the analytic 6-DOF plant.

    Returns a dict with ``fidelity`` numbers (RMSE / max-abs of
    predicted vs recorded), ``gaps`` listing the named modelling
    gaps, and the ``out_json`` path if ``write_json``.
    """
    ticks = load_flight_long(csv_path)
    if len(ticks) < 2:
        return {"error": "too few ticks", "n_ticks": len(ticks)}
    # Build the plant.
    plant = RigidBodyPlant(dt=dt, airframe=CANONICAL_AIRFRAME)
    plant.reset()
    # Time series for fidelity analysis.
    n = len(ticks)
    pred_p = np.empty(n)
    pred_q = np.empty(n)
    pred_r = np.empty(n)
    rec_p = np.empty(n)
    rec_q = np.empty(n)
    rec_r = np.empty(n)
    rec_rol_deg = np.empty(n)
    rec_pit_deg = np.empty(n)
    pred_phi_deg = np.empty(n)
    pred_theta_deg = np.empty(n)
    t_log = np.empty(n)
    for k, tick in enumerate(ticks):
        u_roll = _firmware_u(tick, "roll")
        u_pitch = _firmware_u(tick, "pitch")
        u_yaw = _firmware_u(tick, "yaw")
        # Z channel: prefer recorded u_nom (post position-loop), fall
        # back to hover thrust.
        z_nom = tick.get("A.mrac.z.u_nom", float("nan"))
        z_ad = tick.get("A.mrac.z.u_ad", 0.0)
        if math.isnan(z_nom) or z_nom == 0.0:
            u_z = DEFAULT_HOVER_THRUST_N
        else:
            u_z = z_nom + (z_ad if not math.isnan(z_ad) else 0.0)
        state = plant.step({
            "roll": u_roll, "pitch": u_pitch, "yaw": u_yaw, "z": u_z,
        })
        pred_p[k] = state["p"]
        pred_q[k] = state["q"]
        pred_r[k] = state["r"]
        pred_phi_deg[k] = math.degrees(state["phi"])
        pred_theta_deg[k] = math.degrees(state["theta"])
        # Recorded signals (gyro_*_Real is rad/s — verified in CLAUDE.md).
        rec_p[k] = tick.get("OF.Gyro_X_Real", float("nan"))
        rec_q[k] = tick.get("OF.Gyro_Y_Real", float("nan"))
        rec_r[k] = tick.get("OF.Gyro_Z_Real", float("nan"))
        rec_rol_deg[k] = tick.get("OF.imu_data.rol", float("nan"))
        rec_pit_deg[k] = tick.get("OF.imu_data.pit", float("nan"))
        t_log[k] = tick["t_s"]
    # Fidelity: compare predicted body rates to recorded gyro. Use
    # only the indices where the recorded signal is finite.
    def _rmse(pred: np.ndarray, rec: np.ndarray) -> tuple[float, int]:
        mask = np.isfinite(rec)
        if not mask.any():
            return float("nan"), 0
        d = pred[mask] - rec[mask]
        return float(np.sqrt(np.mean(d ** 2))), int(mask.sum())

    rmse_p, n_p = _rmse(pred_p, rec_p)
    rmse_q, n_q = _rmse(pred_q, rec_q)
    rmse_r, n_r = _rmse(pred_r, rec_r)
    rmse_phi, n_phi = _rmse(pred_phi_deg, rec_rol_deg)
    rmse_theta, n_theta = _rmse(pred_theta_deg, rec_pit_deg)
    fidelity = {
        "n_ticks": int(n),
        "t_start_s": float(t_log[0]),
        "t_end_s": float(t_log[-1]),
        "rmse_p_rads": rmse_p, "n_p": n_p,
        "rmse_q_rads": rmse_q, "n_q": n_q,
        "rmse_r_rads": rmse_r, "n_r": n_r,
        "rmse_phi_deg": rmse_phi, "n_phi": n_phi,
        "rmse_theta_deg": rmse_theta, "n_theta": n_theta,
    }
    # Named modelling gaps (spec 4a — must be in every report).
    gaps = [
        "Aerodynamic drag (body-frame linear + rotational)",
        "Ground effect (altitude-dependent thrust bias)",
        "Prop wash / inflow downwash on attitude loops",
        "Battery sag (voltage-dependent motor RPM)",
        "Frame flex (motor-to-CG arm compliance under load)",
        "Sensor noise and bias (gyro/accel)",
        "Motor/ESC non-linearity beyond 1st-order LPF",
        "Wind / external disturbance",
    ]
    result = {
        "csv_path": str(csv_path),
        "airframe": {
            "mass": CANONICAL_AIRFRAME.mass,
            "Ixx": CANONICAL_AIRFRAME.Ixx,
            "Iyy": CANONICAL_AIRFRAME.Iyy,
            "Izz": CANONICAL_AIRFRAME.Izz,
        },
        "fidelity": fidelity,
        "modelling_gaps": gaps,
        "note": (
            "imu_data.yaw is unusable (constant 2.45 deg/s drift with the "
            "drone still; CLAUDE.md); yaw fidelity is therefore not reported."
        ),
    }
    if write_json:
        out = csv_path.with_suffix(csv_path.suffix + ".replay.json")
        out.write_text(json.dumps(result, indent=2))
        result["out_json"] = str(out)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Replay a flight log through the analytic 6-DOF plant.")
    parser.add_argument("csv", type=Path, help="Long-format flight CSV.")
    parser.add_argument("--dt", type=float, default=0.005,
                        help="Plant integration step (s). Default 5 ms.")
    parser.add_argument("--no-write", action="store_true",
                        help="Skip writing the JSON sidecar.")
    args = parser.parse_args(argv)
    res = replay(args.csv, dt=args.dt, write_json=not args.no_write)
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())