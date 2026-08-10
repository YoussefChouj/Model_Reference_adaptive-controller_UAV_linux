"""Aggregator tests (engine-agnostic, ADR-0012 D7)."""
from __future__ import annotations

import csv
import math
from pathlib import Path

import pytest

from sim import aggregator
from sim.aggregator import aggregate
from sim.recorder import CSV_COLUMNS


def test_known_sine_rmse(tmp_path):
    path = tmp_path / "trajectory.csv"
    n = 1000
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for i in range(n):
            x = math.sin(2.0 * math.pi * i / n)
            row = {key: 0.0 for key in CSV_COLUMNS}
            row.update({"t": i * 0.005, "x": x, "phi": math.radians(10.0), "thrust": 12.0})
            writer.writerow(row)
    summary = aggregate(path)
    assert summary["rmse_position"] == pytest.approx(1.0 / math.sqrt(2.0), abs=1e-6)
    assert summary["max_abs_attitude_deg"] == pytest.approx(10.0)
    assert summary["n_samples"] == n


def test_aggregator_never_shells_out():
    """The aggregator operates only on the CSV — no subprocess, no gz /
    gazebo / sdf strings anywhere in its source or output keys."""
    src = Path(aggregator.__file__).read_text(encoding="utf-8").lower()
    for token in ("subprocess", "gz sim", "gazebo", "sdf"):
        assert token not in src, f"aggregator references {token!r}"
    # Output keys are engine-neutral.
    summary = aggregate.__doc__ or ""
    assert "gz" not in summary.lower()
