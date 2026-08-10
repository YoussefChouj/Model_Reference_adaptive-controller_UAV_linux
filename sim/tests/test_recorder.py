"""Recorder tests (engine-agnostic, ADR-0012 D7)."""
from __future__ import annotations

import csv
import json

import pytest

from sim.recorder import CSVRecorder, CSV_COLUMNS, JSONLRecorder


def _state(i):
    return {
        "x": i, "y": 0.0, "z": 0.0, "vx": 0.0, "vy": 0.0, "vz": 0.0,
        "phi": 0.0, "theta": 0.0, "psi": 0.0, "p": 0.0, "q": 0.0, "r": 0.0,
        "q0": 1.0, "q1": 0.0, "q2": 0.0, "q3": 0.0, "thrust": 12.0,
        "motors": [3.0] * 4, "command": {"z": 12.0, "roll": 0.0, "pitch": 0.0, "yaw": 0.0},
    }


@pytest.mark.parametrize("recorder_cls,filename", [
    (CSVRecorder, "trajectory.csv"), (JSONLRecorder, "trajectory.jsonl")
])
def test_recorders_round_trip_1000_records(tmp_path, recorder_cls, filename):
    recorder = recorder_cls()
    recorder.start(tmp_path)
    for i in range(1000):
        recorder.record(_state(i), i * 0.005)
    recorder.stop()
    assert recorder.summary()["n_records"] == 1000
    path = tmp_path / filename
    if filename.endswith(".csv"):
        with path.open(newline="", encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
        assert len(rows) == 1000
        assert float(rows[-1]["x"]) == 999.0
    else:
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        assert len(rows) == 1000
        assert rows[-1]["x"] == 999


def test_csv_columns_are_engine_neutral():
    """The column schema matches any Plant.step() state_dict — no
    Gazebo-specific column names (gz, sdf, gazebo, urdf)."""
    joined = " ".join(CSV_COLUMNS).lower()
    for token in ("gz", "gazebo", "sdf", "urdf"):
        assert token not in joined, f"gazebo-flavoured column {token!r} present"
    # Core state_dict keys the analytic and MuJoCo plants both emit.
    for key in ("t", "x", "y", "z", "p", "q", "r", "vz", "thrust", "m1", "m2",
                "m3", "m4"):
        assert key in CSV_COLUMNS
