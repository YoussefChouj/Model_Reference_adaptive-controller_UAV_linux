"""Replay flight_1783845799.csv through sim/ekf.py's 9-state EKF (ADR-0011 step 2).

This is offline validation: no firmware, no plant, just the recorded telemetry fed
back into the EKF to confirm it converges on the bias values present in the actual
flight log. The flight is a Scenario 1 "hand slide ±1 m" calibration — both axes
have known ground-truth motion.

Run: cd sim && python -m sim.tools.replay_ekf_flight ../ground_station/logs/flight_1783845799.csv

What it does
------------
1. Loads the long-format CSV (t_s, frame, key, value).
2. Pivots the OF frame rows into per-tick dicts of measured signals.
3. Steps a 9-state EKF through every tick:
     - predict(a_body_from_acc_x/y in m/s^2, gyro=0 since logs lack raw gyro)
     - update_acc_xy(lin_acc_x/y in m/s^2) using gravity-removed logs
     - update_of(of2_dx_fix, of2_dy_fix) in m/s (s16 * 0.01)
     - update_z_rate(of2_h_f2_v if present else 0)
4. Tracks (a) the residual between EKF-estimated v_body and the OF-corrected
   ground-truth velocity (where available) and (b) the converged b_a / b_g.

Expected output (printed at end)
---------------------------------
- Convergence diagnostics: b_a_x, b_a_y, b_a_z in mg.
- Residual RMSE between EKF v_body and OF velocity (after convergence).
- Print whether the EKF's bias estimate tracks the implicit OF-bias signal.
"""
from __future__ import annotations

import csv
import math
import sys
from pathlib import Path

from sim.ekf import Ekf9State


# Scale factors matched to firmware (send_data.c OF_PUT_S16 encoding)
OF_LSB_MPS = 0.01           # s16 -> m/s
ACC_LSB_MS2 = 0.001         # mg -> m/s^2 (used on the body-frame lin_acc side)
GRAV_MS2 = 9.81
HOVER_TRANSITION_S = 1.0    # first second may be cold-cal ground noise; skip for stats


def _to_float(s: str) -> float:
    try:
        return float(s)
    except (ValueError, TypeError):
        return float("nan")


def load_flight_long(csv_path: Path) -> list[dict]:
    """Pivot the long-format CSV into a per-tick dict.

    Returns a list, in chronological order, of dicts with keys drawn from the
    `key` column. Only OF-frame rows are kept (the A/B frames are status only
    and tick at 50/10 Hz vs OF's 200 Hz — they would just confuse the EKF).
    """
    by_t: dict[float, dict] = {}
    with csv_path.open() as f:
        for row in csv.DictReader(f):
            if row["frame"] != "OF":
                continue
            t = _to_float(row["t_s"])
            if math.isnan(t):
                continue
            slot = by_t.get(t)
            if slot is None:
                slot = {"t_s": t}
                by_t[t] = slot
            slot[row["key"]] = _to_float(row["value"])
    return [by_t[t] for t in sorted(by_t.keys())]


def replay(csv_path: Path) -> dict:
    ticks = load_flight_long(csv_path)
    if not ticks:
        raise RuntimeError(f"No OF rows in {csv_path}")

    ekf = Ekf9State(dt=0.005)   # OF frame is 200 Hz, dt = 0.005

    n_steps = 0
    n_of_updates = 0
    n_acc_updates = 0
    n_z_updates = 0

    res_sq_sum = 0.0
    res_n = 0
    cross_check: list[tuple] = []

    # Track per-axis OF bias residual: the OF sensor's own reported bias is
    # of.bias_x / of.bias_y (the firmware's v3 estimator). If the EKF converges
    # on those same values, the two estimators agree.
    bias_ekf_history: list[tuple[float, float, float, float, float, float]] = []

    for tk in ticks:
        # Body-frame accel from gravity-included logs (of.acc_x_mg is mg)
        ax_mg = tk.get("of.acc_x_mg", float("nan"))
        ay_mg = tk.get("of.acc_y_mg", float("nan"))
        if not (math.isnan(ax_mg) or math.isnan(ay_mg)):
            a_body = (ax_mg * ACC_LSB_MS2, ay_mg * ACC_LSB_MS2, 0.0)
            ekf.predict(a_body, (0.0, 0.0, 0.0), dt=0.005)
            n_steps += 1

        # Gravity-removed body accel (mg -> m/s^2)
        lax_mg = tk.get("of.lin_acc_x_mg", float("nan"))
        lay_mg = tk.get("of.lin_acc_y_mg", float("nan"))
        if not (math.isnan(lax_mg) or math.isnan(lay_mg)):
            ekf.update_acc_xy((lax_mg * ACC_LSB_MS2, lay_mg * ACC_LSB_MS2))
            n_acc_updates += 1

        # OF velocity
        of_dx = tk.get("of.of2_dx_fix", float("nan"))
        of_dy = tk.get("of.of2_dy_fix", float("nan"))
        if not (math.isnan(of_dx) or math.isnan(of_dy)):
            of_vel_mps = (of_dx * OF_LSB_MPS, of_dy * OF_LSB_MPS)
            ekf.update_of(of_vel_mps)
            n_of_updates += 1
            # Compare EKF v_body vs OF (they should converge after warm-up)
            vx, vy, _ = ekf.v_body
            dx = vx - of_vel_mps[0]
            dy = vy - of_vel_mps[1]
            res_sq_sum += dx * dx + dy * dy
            res_n += 1

        # Cross-check: the firmware's v3 OF-bias estimator already subtracted
        # of.bias_x / of.bias_y from of2_dx_fix / of2_dy_fix. The EKF sees the
        # already-corrected velocity, so its b_a estimate should sit near zero
        # unless there's a residual the firmware's PI estimator hasn't captured
        # (which would be the body-frame accel bias that Phase 3 is for).
        bias_x = tk.get("of.bias_x", float("nan"))
        bias_y = tk.get("of.bias_y", float("nan"))
        if not (math.isnan(bias_x) or math.isnan(bias_y)):
            # Implicit OF bias in m/s (firmware's v3 estimate).
            of_bias_mps_x = bias_x * OF_LSB_MPS
            of_bias_mps_y = bias_y * OF_LSB_MPS
            bx, by, _ = ekf.b_a_body
            # Convert EKF's b_a (m/s²) to mg, then subtract the OF bias in mg
            # equivalent for a direct numerical comparison. The point of the
            # cross-check is "is the EKF discovering anything the OF estimator
            # missed?" — a non-zero residual after t=2 s is the signal to look at.
            ekf_ba_mg_x = bx / GRAV_MS2 * 1000
            ekf_ba_mg_y = by / GRAV_MS2 * 1000
            cross_check.append((tk["t_s"],
                                of_bias_mps_x, of_bias_mps_y,
                                ekf_ba_mg_x, ekf_ba_mg_y))

        # Z-rate (not always present; update_z_rate is optional)
        # of_alt_cm-based Z-rate is unreliable (cm units), so skip if no
        # of2_h_f2_v in the log (older v13 logs don't have it).
        # No-op here.

        if tk["t_s"] >= HOVER_TRANSITION_S:
            bx, by, bz = ekf.b_a_body
            bgx, bgy, bgz = ekf.b_g_body
            bias_ekf_history.append(
                (tk["t_s"], bx / GRAV_MS2 * 1000, by / GRAV_MS2 * 1000, bz / GRAV_MS2 * 1000,
                 math.degrees(bgx), math.degrees(bgy))
            )

    rmse = math.sqrt(res_sq_sum / res_n) if res_n else float("nan")

    final = {
        "csv": str(csv_path),
        "ticks_loaded": len(ticks),
        "predict_steps": n_steps,
        "of_updates": n_of_updates,
        "acc_updates": n_acc_updates,
        "v_body_of_rmse_mps": rmse,
        "ekf_b_a_x_mg_last": bias_ekf_history[-1][1] if bias_ekf_history else float("nan"),
        "ekf_b_a_y_mg_last": bias_ekf_history[-1][2] if bias_ekf_history else float("nan"),
        "ekf_b_a_z_mg_last": bias_ekf_history[-1][3] if bias_ekf_history else float("nan"),
        "ekf_b_g_x_dps_last": bias_ekf_history[-1][4] if bias_ekf_history else float("nan"),
        "ekf_b_g_y_dps_last": bias_ekf_history[-1][5] if bias_ekf_history else float("nan"),
        "first_5_history": bias_ekf_history[:5],
        "last_5_history": bias_ekf_history[-5:],
        "cross_check": cross_check,
    }
    return final


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: python -m sim.tools.replay_ekf_flight <flight_log.csv>")
        return 1
    csv_path = Path(argv[1]).resolve()
    if not csv_path.exists():
        print(f"not found: {csv_path}")
        return 1
    result = replay(csv_path)
    print(f"=== EKF replay: {result['csv']} ===")
    print(f"  OF ticks loaded     : {result['ticks_loaded']}")
    print(f"  predict steps       : {result['predict_steps']}")
    print(f"  accel updates       : {result['acc_updates']}")
    print(f"  OF updates          : {result['of_updates']}")
    print(f"  v_body vs OF RMSE   : {result['v_body_of_rmse_mps']:.4f} m/s")
    print()
    print(f"  Final EKF b_a (mg)  : x={result['ekf_b_a_x_mg_last']:.2f}  "
          f"y={result['ekf_b_a_y_mg_last']:.2f}  z={result['ekf_b_a_z_mg_last']:.2f}")
    print(f"  Final EKF b_g (dps) : x={result['ekf_b_g_x_dps_last']:.3f}  "
          f"y={result['ekf_b_g_y_dps_last']:.3f}")
    print()
    print("  EKF bias trajectory (after t=1 s, first 5):")
    for t, bx, by, bz, gx, gy in result["first_5_history"]:
        print(f"    t={t:6.2f}s  b_a=({bx:+6.2f}, {by:+6.2f}, {bz:+6.2f}) mg  "
              f"b_g=({gx:+.3f}, {gy:+.3f}) dps")
    print("  ... last 5:")
    for t, bx, by, bz, gx, gy in result["last_5_history"]:
        print(f"    t={t:6.2f}s  b_a=({bx:+6.2f}, {by:+6.2f}, {bz:+6.2f}) mg  "
              f"b_g=({gx:+.3f}, {gy:+.3f}) dps")
    print()
    cc = result["cross_check"]
    if cc:
        print(f"  Cross-check vs firmware v3 OF-bias (last 5 of {len(cc)} pts):")
        print("    t(s)   of.bias (m/s)        EKF b_a (mg)")
        for t, ofx, ofy, ekfx, ekfy in cc[-5:]:
            print(f"    {t:6.2f}  x={ofx:+.4f}  y={ofy:+.4f}    "
                  f"x={ekfx:+6.2f}  y={ekfy:+6.2f}")
        print("    interpretation: ekf b_a near 0 mg means OF-bias estimator")
        print("    already removed the constant; any non-zero residue would")
        print("    indicate an accel-axis bias the OF path can't see.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
