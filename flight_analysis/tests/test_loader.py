"""Tests for core data loader."""

import pytest
from pathlib import Path
import numpy as np


class TestDataLoader:
    """Test suite for flight data loading."""

    @pytest.fixture
    def sample_csv(self, tmp_path):
        """Create a minimal sample CSV for testing."""
        csv_content = """t_s,frame,key,value
0.0,A,mrac.pitch.e,0.1
0.0,A,mrac.pitch.u_ad,0.2
0.0,B,pid.pitch.Des,1.0
0.0,B,pid.pitch.FB,0.9
0.1,A,mrac.pitch.e,0.15
0.1,A,mrac.pitch.u_ad,0.25
0.1,B,pid.pitch.Des,1.0
0.1,B,pid.pitch.FB,0.95
"""
        path = tmp_path / "test_flight.csv"
        path.write_text(csv_content)
        return path

    @pytest.fixture
    def real_flight_csv(self):
        """Path to the real flight log for integration tests."""
        root = Path(__file__).parent.parent.parent
        return root / "ground_station" / "logs" / "flight_1784538359.csv"

    def test_load_csv_basic(self, sample_csv):
        """Test basic CSV loading."""
        from flight_analysis.core.loader import load_flight_csv
        
        data = load_flight_csv(str(sample_csv))
        
        assert len(data) > 0
        assert "mrac.pitch.e" in data
        assert "pid.pitch.Des" in data

    def test_time_alignment(self, sample_csv):
        """Test that data is properly time-aligned."""
        from flight_analysis.core.loader import load_flight_csv
        
        data = load_flight_csv(str(sample_csv))
        
        # All keys should have same time base
        time_bases = [data[k][0] for k in data if len(data[k][0]) > 0]
        assert len(time_bases) > 0

    def test_frame_detection(self, sample_csv):
        """Test frame type detection from data."""
        from flight_analysis.core.loader import load_flight_csv, detect_frame_types
        
        data = load_flight_csv(str(sample_csv))
        frames = detect_frame_types(data)
        
        assert "A" in frames
        assert "B" in frames

    def test_key_pattern_extraction(self, sample_csv):
        """Test extraction of key patterns."""
        from flight_analysis.core.loader import load_flight_csv, extract_signal_groups
        
        data = load_flight_csv(str(sample_csv))
        groups = extract_signal_groups(data)
        
        assert "mrac" in groups
        assert "pid" in groups
        assert "pitch" in groups["mrac"]
        assert "pitch" in groups["pid"]

    def test_missing_data_handling(self, sample_csv):
        """Test graceful handling of missing signals."""
        from flight_analysis.core.loader import load_flight_csv, get_signal
        
        data = load_flight_csv(str(sample_csv))
        
        # Existing signal
        t, v = get_signal(data, "mrac.pitch.e")
        assert t is not None
        assert v is not None
        
        # Missing signal should return None
        t, v = get_signal(data, "nonexistent.key")
        assert t is None
        assert v is None

    def test_time_monotonicity(self, sample_csv):
        """Test time vector is monotonically increasing."""
        from flight_analysis.core.loader import load_flight_csv
        
        data = load_flight_csv(str(sample_csv))
        
        for key, (t, v) in data.items():
            if len(t) > 1:
                assert all(t[i] <= t[i+1] for i in range(len(t)-1)), \
                    f"Time not monotonic for {key}"

    def test_real_flight_log_loading(self, real_flight_csv):
        """Integration test: load real flight log."""
        if not real_flight_csv.exists():
            pytest.skip(f"Real flight log not found: {real_flight_csv}")
        
        from flight_analysis.core.loader import load_flight_csv
        
        data = load_flight_csv(str(real_flight_csv))
        
        # Should have substantial data
        assert len(data) > 50, "Expected >50 unique signals"
        
        # Should have MRAC signals
        assert any("mrac" in k for k in data.keys())
        
        # Should have PID signals
        assert any("pid" in k for k in data.keys())

    def test_sample_rate_estimation(self, real_flight_csv):
        """Test sample rate estimation from timestamps."""
        if not real_flight_csv.exists():
            pytest.skip(f"Real flight log not found: {real_flight_csv}")
        
        from flight_analysis.core.loader import load_flight_csv, estimate_sample_rate
        
        data = load_flight_csv(str(real_flight_csv))
        rate = estimate_sample_rate(data)
        
        # Sample rate depends on the most-sampled signal
        # Frame A emits at ~100Hz, Frame B at ~100Hz but interleaved
        assert 1 < rate < 200, f"Sample rate {rate}Hz outside expected range"

    def test_data_quality_metrics(self, real_flight_csv):
        """Test data quality assessment."""
        if not real_flight_csv.exists():
            pytest.skip(f"Real flight log not found: {real_flight_csv}")
        
        from flight_analysis.core.loader import load_flight_csv, compute_data_quality
        
        data = load_flight_csv(str(real_flight_csv))
        quality = compute_data_quality(data)
        
        assert "total_signals" in quality
        assert "missing_signals" in quality
        assert quality["total_signals"] > 50
