"""Tests for expert diagnostics and report generation."""

import pytest
import numpy as np
from pathlib import Path


class TestDiagnostics:
    """Test suite for expert diagnostics."""

    @pytest.fixture
    def real_flight_csv(self):
        root = Path(__file__).parent.parent.parent
        return root / "ground_station" / "logs" / "flight_1784538359.csv"

    def test_alert_generation(self, real_flight_csv):
        """Test expert alert generation."""
        if not real_flight_csv.exists():
            pytest.skip(f"Real flight log not found: {real_flight_csv}")
        
        from flight_analysis.core.loader import load_flight_csv
        from flight_analysis.stability.oscillation import analyze_axis_oscillation
        from flight_analysis.diagnostics.alerts import generate_expert_alerts
        
        data = load_flight_csv(str(real_flight_csv))
        
        # Analyze oscillation for each axis
        oscillation_results = {}
        for axis in ["pitch", "roll", "yaw", "z"]:
            result = analyze_axis_oscillation(data, axis)
            oscillation_results[axis] = result
        
        # Generate alerts
        alerts = generate_expert_alerts(oscillation_results)
        
        assert alerts is not None
        assert isinstance(alerts, list)

    def test_diagnosis_classification(self):
        """Test diagnosis classification."""
        from flight_analysis.diagnostics.alerts import classify_diagnosis
        
        # Test oscillation case
        diagnosis = classify_diagnosis(
            oscillation_detected=True,
            frequency=15.0,
            damping_ratio=0.05,
            oscillation_index=0.8
        )
        
        assert diagnosis is not None
        assert diagnosis["category"] in ["oscillation", "stability", "performance", "mechanical"]

    def test_recommendation_generation(self):
        """Test tuning recommendation generation."""
        from flight_analysis.diagnostics.alerts import generate_tuning_recommendations
        
        alerts = [
            {"level": "CRITICAL", "code": "HIGH_FREQ_OSC", "axis": "pitch"},
            {"level": "WARNING", "code": "LOW_DAMPING", "axis": "roll"},
        ]
        
        recs = generate_tuning_recommendations(alerts)
        
        assert recs is not None
        assert len(recs) > 0
        assert isinstance(recs[0], str)


class TestReportGeneration:
    """Test suite for report generation."""

    @pytest.fixture
    def real_flight_csv(self):
        root = Path(__file__).parent.parent.parent
        return root / "ground_station" / "logs" / "flight_1784538359.csv"

    def test_markdown_report_generation(self, real_flight_csv, tmp_path):
        """Test markdown report generation."""
        if not real_flight_csv.exists():
            pytest.skip(f"Real flight log not found: {real_flight_csv}")
        
        from flight_analysis.core.loader import load_flight_csv
        from flight_analysis.diagnostics.reports import generate_markdown_report
        
        data = load_flight_csv(str(real_flight_csv))
        
        # Create analysis results
        results = {
            "oscillation": {
                "pitch": {"oscillation_detected": True, "oscillation_index": 0.5}
            },
            "stability": {
                "pitch": {"phase_margin_deg": 45.0}
            },
            "performance": {
                "pitch": {"rmse": 0.05}
            }
        }
        
        report_path = tmp_path / "report.md"
        generate_markdown_report(data, results, str(report_path))
        
        assert report_path.exists()
        content = report_path.read_text(encoding="utf-8")
        assert "pitch" in content.lower()
        assert len(content) > 100

    def test_json_report_generation(self, real_flight_csv, tmp_path):
        """Test JSON report generation."""
        if not real_flight_csv.exists():
            pytest.skip(f"Real flight log not found: {real_flight_csv}")
        
        from flight_analysis.diagnostics.reports import generate_json_report
        
        results = {
            "flight_id": "test_flight",
            "oscillation": {"pitch": {"oscillation_detected": True}},
            "metrics": {"rmse": 0.05}
        }
        
        report_path = tmp_path / "report.json"
        generate_json_report(results, str(report_path))
        
        assert report_path.exists()

    def test_summary_statistics(self, real_flight_csv):
        """Test summary statistics computation."""
        if not real_flight_csv.exists():
            pytest.skip(f"Real flight log not found: {real_flight_csv}")
        
        from flight_analysis.core.loader import load_flight_csv
        from flight_analysis.diagnostics.reports import compute_summary_statistics
        
        data = load_flight_csv(str(real_flight_csv))
        stats = compute_summary_statistics(data)
        
        assert stats is not None
        assert "duration_s" in stats
        assert "num_samples" in stats
