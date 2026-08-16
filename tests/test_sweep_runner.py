"""Tests for ground_station.sweep_runner."""
from __future__ import annotations

import asyncio
import csv
import tempfile
from pathlib import Path

import numpy as np
import pytest

from ground_station.sweep_runner import (
    ParamRange,
    ObservableSpec,
    SweepConfig,
    SweepRunner,
    _sobol_samples,
    _sample_schedule,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

class StubTransport:
    """Minimal transport stub: records set_param calls and returns configured values.

    - set_param: records calls.
    - get_telemetry_snapshot: returns the telemetry observable value.
    - livewatch_read: returns values from a caller-supplied dict so tests can
      independently control what the sweep reads as observable vs. what the
      cancel-revert path reads as the initial param value.
    """

    def __init__(
        self,
        observable_value: float = 0.5,
        livewatch_returns: dict[str, float] | None = None,
    ):
        self._observable_value = float(observable_value)
        self._livewatch_returns = dict(livewatch_returns or {})
        self.set_param_calls: list[tuple[str, float]] = []
        self._telemetry: dict[str, float] = {"tracking_rmse": float(observable_value)}

    def set_param(self, name: str, value: float) -> None:
        self.set_param_calls.append((name, float(value)))

    def get_telemetry_snapshot(self):
        return [{}, self._telemetry]

    def livewatch_read(self, names):
        # Return caller-supplied values; fallback to observable_value for unknown names.
        return {n: self._livewatch_returns.get(n, self._observable_value) for n in names}


# ---------------------------------------------------------------------------
# Sobol schedule
# ---------------------------------------------------------------------------

def test_sobol_schedule_covers_range():
    """128 Sobol samples (power of 2) should span [0, 1] with min <= 0.05, max >= 0.45."""
    config = SweepConfig(
        params=[ParamRange(name="x", lo=0.0, hi=1.0)],
        observable=ObservableSpec(source="telemetry", name="tracking_rmse"),
        schedule="sobol",
        optimizer="none",
        n_samples=128,
    )
    normalised = _sample_schedule(config, 128)
    assert normalised.shape == (128, 1)
    assert float(normalised.min()) <= 0.05, "Sobol min should be <= 0.05"
    assert float(normalised.max()) >= 0.45, "Sobol max should be >= 0.45"


def test_sobol_seed_reproducible():
    """Same config must produce identical first 10 samples."""
    cfg = SweepConfig(
        params=[ParamRange(name="x", lo=0.0, hi=1.0)],
        observable=ObservableSpec(source="telemetry", name="tracking_rmse"),
        schedule="sobol",
        optimizer="none",
        n_samples=10,
    )
    a = _sample_schedule(cfg, 10)
    b = _sample_schedule(cfg, 10)
    # scramble=True with same seed produces identical output.
    assert np.allclose(a[:10], b[:10]), "Sobol must be reproducible with same seed"


# ---------------------------------------------------------------------------
# One-shot iteration — CSV written at output_dir/<run_id>/samples.csv
# ---------------------------------------------------------------------------

def test_one_iteration_writes_csv():
    """A single-iteration sweep should produce samples.csv under the run_id subdirectory."""
    with tempfile.TemporaryDirectory() as tmp:
        config = SweepConfig(
            params=[ParamRange(name="p1", lo=0.0, hi=1.0)],
            observable=ObservableSpec(source="telemetry", name="tracking_rmse"),
            schedule="sobol",
            optimizer="none",
            n_samples=1,
            settling_time_s=0.01,
            output_dir=tmp,
        )
        transport = StubTransport(observable_value=1.23)
        runner = SweepRunner(config, transport)
        asyncio.run(runner.run())

        # Runner writes to output_dir/<run_id>/samples.csv
        csv_path = Path(tmp) / runner._run_id / "samples.csv"
        assert csv_path.exists(), "samples.csv must be written after one iteration"
        with open(csv_path) as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 1, "CSV must have exactly 1 data row"
        assert "tracking_rmse" in rows[0], "observable column must be present"


# ---------------------------------------------------------------------------
# Observable reading
# ---------------------------------------------------------------------------

def test_observable_read_via_livewatch():
    """A sweep configured for livewatch source should read via livewatch_read."""
    with tempfile.TemporaryDirectory() as tmp:
        config = SweepConfig(
            params=[ParamRange(name="x", lo=0.0, hi=1.0)],
            observable=ObservableSpec(source="livewatch", name="mrac.pitch.e"),
            schedule="sobol",
            optimizer="none",
            n_samples=1,
            settling_time_s=0.01,
            output_dir=tmp,
        )
        transport = StubTransport(
            observable_value=0.5,
            livewatch_returns={"mrac.pitch.e": 99.0},
        )
        runner = SweepRunner(config, transport)
        asyncio.run(runner.run())

        csv_path = Path(tmp) / runner._run_id / "samples.csv"
        with open(csv_path) as f:
            rows = list(csv.DictReader(f))
        assert float(rows[0]["mrac.pitch.e"]) == 99.0, (
            "observable value from livewatch_read must be recorded"
        )


# ---------------------------------------------------------------------------
# Bayesian GP proposals
# ---------------------------------------------------------------------------

def test_bayesian_proposes_next():
    """After warm-start, all GP proposals must lie within the parameter bounds.

    Skipped if scikit-optimize is not installed.
    """
    try:
        from skopt import Optimizer  # noqa: F401
    except ImportError:
        pytest.skip("scikit-optimize not installed")

    with tempfile.TemporaryDirectory() as tmp:
        config = SweepConfig(
            params=[ParamRange(name="x", lo=0.0, hi=1.0)],
            observable=ObservableSpec(source="telemetry", name="tracking_rmse"),
            schedule="sobol",
            optimizer="bayesian",
            n_samples=20,
            settling_time_s=0.01,
            output_dir=tmp,
        )
        transport = StubTransport(observable_value=0.1)
        runner = SweepRunner(config, transport)
        asyncio.run(runner.run())

        assert len(runner._samples) == 20, "should run all 20 samples"
        xs = [s["x"] for s in runner._samples]
        assert all(0.0 <= x <= 1.0 for x in xs), "all proposals must stay in bounds"


# ---------------------------------------------------------------------------
# Cancel / revert
# ---------------------------------------------------------------------------

def test_cancel_reverts_params():
    """After cancel(), the revert call must restore the param to its initial value.
    The stub's livewatch_returns controls what _read_param_current_value sees."""
    with tempfile.TemporaryDirectory() as tmp:
        config = SweepConfig(
            params=[ParamRange(name="x", lo=0.0, hi=1.0)],
            observable=ObservableSpec(source="telemetry", name="tracking_rmse"),
            schedule="sobol",
            optimizer="none",
            n_samples=5,
            settling_time_s=5.0,
            output_dir=tmp,
        )
        # livewatch_returns controls what livewatch_read returns when called
        # by _read_param_current_value during cancel().
        transport = StubTransport(
            observable_value=0.5,
            livewatch_returns={"x": 42.0},   # initial param value for revert
        )
        runner = SweepRunner(config, transport)

        async def _run_cancel():
            task = asyncio.create_task(runner.run())
            await asyncio.sleep(0.05)   # cancel mid-first-iteration
            runner.cancel()
            await task

        asyncio.run(_run_cancel())

        # Revert is the last set_param call and must restore 42.0.
        last_name, last_val = transport.set_param_calls[-1]
        assert last_name == "x", "last call should be on swept param"
        assert last_val == pytest.approx(42.0), (
            f"cancel must revert to initial param value 42.0, got {last_val}"
        )
