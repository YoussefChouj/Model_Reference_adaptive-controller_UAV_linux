"""Tests for the flight-log replay tool (spec 4a).

Uses synthetic long-format CSVs to exercise the replay path so the
test does not depend on a specific real flight log (the 18 cited logs
exist but are not committed to the test suite). The tool is asserted
to:
  - report fidelity numbers (RMSE) for available signals
  - gracefully handle missing signals (NaN fidelity, gaps still listed)
  - write a JSON sidecar with fidelity + named modelling gaps
"""
import csv
import json
from pathlib import Path

import pytest

from sim.tools.replay_flight_plant import load_flight_long, replay


def _write_flight_csv(path: Path, n_ticks: int = 200,
                      include_gyro: bool = True,
                      include_imu_att: bool = True,
                      include_z: bool = True) -> None:
    """Write a synthetic long-format flight CSV with the keys replay
    needs."""
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["t_s", "frame", "key", "value"])
        for k in range(n_ticks):
            t = k * 0.005
            # u_nom + u_ad for each axis (A frame)
            w.writerow([f"{t:.4f}", "A", "mrac.roll.u_nom", "0.001"])
            w.writerow([f"{t:.4f}", "A", "mrac.roll.u_ad", "0.0"])
            w.writerow([f"{t:.4f}", "A", "mrac.pitch.u_nom", "0.001"])
            w.writerow([f"{t:.4f}", "A", "mrac.pitch.u_ad", "0.0"])
            w.writerow([f"{t:.4f}", "A", "mrac.yaw.u_nom", "0.0"])
            w.writerow([f"{t:.4f}", "A", "mrac.yaw.u_ad", "0.0"])
            if include_z:
                w.writerow([f"{t:.4f}", "A", "mrac.z.u_nom", "12.71"])
                w.writerow([f"{t:.4f}", "A", "mrac.z.u_ad", "0.0"])
            if include_gyro:
                w.writerow([f"{t:.4f}", "OF", "Gyro_X_Real", "0.001"])
                w.writerow([f"{t:.4f}", "OF", "Gyro_Y_Real", "0.001"])
                w.writerow([f"{t:.4f}", "OF", "Gyro_Z_Real", "0.0"])
            if include_imu_att:
                w.writerow([f"{t:.4f}", "OF", "imu_data.rol", "0.0"])
                w.writerow([f"{t:.4f}", "OF", "imu_data.pit", "0.0"])
                # yaw intentionally omitted (documented unusable)


def test_load_flight_long_returns_per_tick_dicts(tmp_path: Path):
    """load_flight_long pivots the long CSV into per-tick dicts."""
    csv_path = tmp_path / "flight.csv"
    _write_flight_csv(csv_path, n_ticks=10)
    ticks = load_flight_long(csv_path)
    assert len(ticks) == 10
    # Each tick has keys from A and OF frames.
    assert "A.mrac.roll.u_nom" in ticks[0]
    assert "OF.Gyro_X_Real" in ticks[0]


def test_replay_returns_fidelity_and_gaps(tmp_path: Path):
    """replay writes a JSON sidecar with fidelity + modelling gaps."""
    csv_path = tmp_path / "flight.csv"
    _write_flight_csv(csv_path, n_ticks=200)
    res = replay(csv_path)
    assert "fidelity" in res
    assert "modelling_gaps" in res
    assert len(res["modelling_gaps"]) >= 5
    assert "out_json" in res
    out = Path(res["out_json"])
    assert out.exists()
    loaded = json.loads(out.read_text())
    assert "fidelity" in loaded
    # At least one RMSE should be finite (we wrote recorded gyro).
    assert loaded["fidelity"]["rmse_p_rads"] is not None


def test_replay_handles_missing_signals(tmp_path: Path):
    """Missing gyro/IMU columns -> fidelity NaN, gaps still listed."""
    csv_path = tmp_path / "flight_no_gyro.csv"
    _write_flight_csv(csv_path, n_ticks=50, include_gyro=False,
                      include_imu_att=False, include_z=False)
    res = replay(csv_path)
    assert "fidelity" in res
    assert "modelling_gaps" in res
    # RMSE columns should be NaN when no recorded signals.
    import math
    assert math.isnan(res["fidelity"]["rmse_p_rads"])
    # Sidecar still written.
    assert Path(res["out_json"]).exists()


def test_replay_rejects_too_few_ticks(tmp_path: Path):
    """Less than 2 ticks -> error reported, no crash."""
    csv_path = tmp_path / "tiny.csv"
    csv_path.write_text("t_s,frame,key,value\n0.0000,A,mrac.roll.u_nom,0.0\n")
    res = replay(csv_path, write_json=False)
    assert "error" in res