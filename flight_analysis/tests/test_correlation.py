"""Tests for parameter-performance correlation engine."""

import pytest
import numpy as np
from pathlib import Path


class TestParameterExtraction:
    """Test suite for controller parameter extraction."""

    @pytest.fixture
    def real_flight_csv(self):
        root = Path(__file__).parent.parent.parent
        return root / "ground_station" / "logs" / "flight_1784538359.csv"

    def test_mrac_weights_extraction(self, real_flight_csv):
        """Test MRAC adaptive weights extraction."""
        if not real_flight_csv.exists():
            pytest.skip(f"Real flight log not found: {real_flight_csv}")
        
        from flight_analysis.core.loader import load_flight_csv
        from flight_analysis.correlation.param_map import extract_mrac_parameters
        
        data = load_flight_csv(str(real_flight_csv))
        params = extract_mrac_parameters(data)
        
        assert params is not None
        assert "pitch" in params or "roll" in params
        # Should have theta weights
        for axis_params in params.values():
            assert "theta" in axis_params or len(axis_params) > 0

    def test_pid_signals_extraction(self, real_flight_csv):
        """Test PID loop signal extraction."""
        if not real_flight_csv.exists():
            pytest.skip(f"Real flight log not found: {real_flight_csv}")
        
        from flight_analysis.core.loader import load_flight_csv
        from flight_analysis.correlation.param_map import extract_pid_signals
        
        data = load_flight_csv(str(real_flight_csv))
        signals = extract_pid_signals(data)
        
        assert signals is not None
        assert "pitch" in signals or "roll" in signals

    def test_adaptation_rate_estimation(self, real_flight_csv):
        """Test MRAC adaptation rate estimation."""
        if not real_flight_csv.exists():
            pytest.skip(f"Real flight log not found: {real_flight_csv}")
        
        from flight_analysis.core.loader import load_flight_csv
        from flight_analysis.correlation.param_map import estimate_adaptation_rates
        
        data = load_flight_csv(str(real_flight_csv))
        rates = estimate_adaptation_rates(data)
        
        assert rates is not None
        # Should have rates for each axis
        for axis, axis_rates in rates.items():
            assert len(axis_rates) > 0


class TestPerformanceMetrics:
    """Test suite for performance metrics computation."""

    @pytest.fixture
    def real_flight_csv(self):
        root = Path(__file__).parent.parent.parent
        return root / "ground_station" / "logs" / "flight_1784538359.csv"

    def test_tracking_rmse(self, real_flight_csv):
        """Test RMSE computation for tracking."""
        if not real_flight_csv.exists():
            pytest.skip(f"Real flight log not found: {real_flight_csv}")
        
        from flight_analysis.core.loader import load_flight_csv
        from flight_analysis.correlation.param_map import compute_tracking_metrics
        
        data = load_flight_csv(str(real_flight_csv))
        metrics = compute_tracking_metrics(data)
        
        assert metrics is not None
        assert len(metrics) > 0

    def test_control_effort_metrics(self, real_flight_csv):
        """Test control effort metrics."""
        if not real_flight_csv.exists():
            pytest.skip(f"Real flight log not found: {real_flight_csv}")
        
        from flight_analysis.core.loader import load_flight_csv
        from flight_analysis.correlation.param_map import compute_control_effort_metrics
        
        data = load_flight_csv(str(real_flight_csv))
        effort = compute_control_effort_metrics(data)
        
        assert effort is not None
        # Should have metrics per axis
        for axis, axis_effort in effort.items():
            assert "rms" in axis_effort or "peak" in axis_effort


class TestCorrelationAnalysis:
    """Test suite for parameter-performance correlation."""

    @pytest.fixture
    def real_flight_csv(self):
        root = Path(__file__).parent.parent.parent
        return root / "ground_station" / "logs" / "flight_1784538359.csv"

    def test_sensitivity_computation(self, real_flight_csv):
        """Test parameter sensitivity analysis."""
        if not real_flight_csv.exists():
            pytest.skip(f"Real flight log not found: {real_flight_csv}")
        
        from flight_analysis.core.loader import load_flight_csv
        from flight_analysis.correlation.sensitivity import compute_parameter_sensitivity
        
        data = load_flight_csv(str(real_flight_csv))
        params = {"gamma": {"pitch": [0.5, 3.3, 1.0, 2.0, 0.1, 1.0]}}
        sensitivity = compute_parameter_sensitivity(data, params)
        
        assert sensitivity is not None
        assert "pitch" in sensitivity

    def test_performance_ranking(self):
        """Test performance ranking from metrics."""
        from flight_analysis.correlation.sensitivity import rank_performance
        
        metrics = {
            "flight_1": {"rmse": 0.05, "oscillation_index": 0.2},
            "flight_2": {"rmse": 0.1, "oscillation_index": 0.5},
            "flight_3": {"rmse": 0.03, "oscillation_index": 0.1},
        }
        
        ranking = rank_performance(metrics)
        
        assert ranking is not None
        assert len(ranking) == 3
        # Best (lowest RMSE) should be flight_3
        assert ranking[0]["flight_id"] == "flight_3"
