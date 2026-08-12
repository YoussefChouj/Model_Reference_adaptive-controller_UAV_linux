"""Smoke tests for the five sweep families (sim-arch-03).

Each test runs one sweep on a minimal scenario (dt=0.005, duration=0.5)
and asserts the SweepResult has the expected shape.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from sim import scenarios
from sim.plant import IdentifiedPlant, CANONICAL_MODELS
from sim.sweeps import bias_deadzone, lyapunov_q, crm_delay, paired_envelope, sensitivity


def _minimal_factory():
    """IdentifiedPlant.canonical, dt=0.005, duration=0.5."""
    axis = "roll"
    plant_factory = lambda dt: IdentifiedPlant(dt, {axis: CANONICAL_MODELS[axis]})
    return replace(scenarios.step(axis, amp_dps=30.0),
                   duration=0.5,
                   plant_factory=plant_factory)


def _minimal_factory_inertia():
    """Inertia-offset variant for the second sweep family."""
    return scenarios.inertia_offset("roll", factor=0.6)


class TestBiasDeadzoneSweep:
    def test_runs_and_returns_result(self):
        result = bias_deadzone.run_sweep("roll", _minimal_factory)
        assert result.family == "bias_deadzone"
        assert result.axis == "roll"
        assert len(result.rows) == 4
        for row in result.rows:
            assert "rmse_track" in row.metrics
            assert "final_weight_norm" in row.metrics


class TestLyapunovQSweep:
    def test_runs_and_returns_result(self):
        result = lyapunov_q.run_sweep("roll", _minimal_factory_inertia)
        assert result.family == "lyapunov_q"
        assert result.axis == "roll"
        assert len(result.rows) == 4
        for row in result.rows:
            assert "rmse_track" in row.metrics


class TestCrmDelaySweep:
    def test_runs_and_returns_result(self):
        result = crm_delay.run_sweep("roll")
        assert result.family == "crm_delay"
        assert result.axis == "roll"
        assert len(result.rows) == 4 * 12  # l1_vals × delays_ms
        for row in result.rows:
            assert "rmse_track" in row.metrics
            assert "verdict" in row.metrics
            assert row.metrics["verdict"] in ("ok", "DEGRADED", "UNSTABLE")


class TestPairedEnvelopeSweep:
    def test_runs_and_returns_result(self):
        result = paired_envelope.run_sweep("roll", _minimal_factory)
        assert result.family == "paired_envelope"
        assert result.axis == "roll"
        assert len(result.rows) == 3  # learning, deployment, deployment+thetaLearn
        labels = {row.label for row in result.rows}
        assert labels == {
            "learning_envelope",
            "deployment_envelope",
            "deployment_thetaLearn",
        }
        for row in result.rows:
            assert "rmse_track" in row.metrics


class TestSensitivitySweep:
    def test_runs_and_returns_result(self):
        result = sensitivity.run_sweep("roll", _minimal_factory)
        assert result.family == "sensitivity"
        assert result.axis == "roll"
        # 5 deadzone + 4 What_limit + 4 Gamma = 13 rows
        assert len(result.rows) == 13
        for row in result.rows:
            assert "rmse_track" in row.metrics
