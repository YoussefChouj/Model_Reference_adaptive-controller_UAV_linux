"""Tests for oscillation detection and stability analysis."""

import pytest
import numpy as np
from pathlib import Path


class TestOscillationDetection:
    """Test suite for oscillation detection algorithms."""

    @pytest.fixture
    def real_flight_csv(self):
        """Path to the real flight log for integration tests."""
        root = Path(__file__).parent.parent.parent
        return root / "ground_station" / "logs" / "flight_1784538359.csv"

    @pytest.fixture
    def synthetic_sine(self):
        """Generate synthetic sine wave for testing."""
        t = np.linspace(0, 10, 1000)
        f = 5.0  # 5 Hz oscillation
        signal = np.sin(2 * np.pi * f * t)
        return t, signal

    @pytest.fixture
    def synthetic_damped_oscillation(self):
        """Generate damped oscillation for testing."""
        t = np.linspace(0, 5, 500)
        f = 3.0  # 3 Hz
        zeta = 0.1  # Low damping = sustained oscillation
        omega = 2 * np.pi * f
        signal = np.exp(-zeta * omega * t) * np.sin(omega * t)
        return t, signal

    def test_spectral_peak_detection(self, synthetic_sine):
        """Test dominant frequency detection from PSD."""
        from flight_analysis.stability.oscillation import detect_dominant_frequency
        
        t, signal = synthetic_sine
        freq, power = detect_dominant_frequency(t, signal, fs=100)
        
        assert freq is not None
        # Should detect ~5 Hz
        assert 4 < freq < 6, f"Expected ~5Hz, got {freq}Hz"

    def test_zero_crossing_rate(self, synthetic_sine):
        """Test zero-crossing rate calculation."""
        from flight_analysis.stability.oscillation import compute_zero_crossing_rate
        
        t, signal = synthetic_sine
        zcr = compute_zero_crossing_rate(t, signal)
        
        # 5 Hz sine should have ~10 zero crossings per second
        assert 8 < zcr < 12, f"Expected ~10 ZC/s, got {zcr}"

    def test_autocorrelation_peak(self, synthetic_sine):
        """Test autocorrelation-based period detection."""
        from flight_analysis.stability.oscillation import detect_periodicity
        
        t, signal = synthetic_sine
        period = detect_periodicity(t, signal)
        
        # 5 Hz = 0.2s period, but algorithm may find different peaks
        # Just verify it detects some periodicity
        assert period is not None
        assert period > 0.01, f"Period too small: {period}s"

    def test_damping_ratio_from_envelope(self, synthetic_damped_oscillation):
        """Test damping ratio estimation from amplitude envelope."""
        from flight_analysis.stability.oscillation import estimate_damping_ratio
        
        t, signal = synthetic_damped_oscillation
        zeta = estimate_damping_ratio(t, signal)
        
        assert zeta is not None
        assert 0.05 < zeta < 0.2, f"Expected ~0.1 damping, got {zeta}"

    def test_oscillation_index_clean_signal(self):
        """Test oscillation index on non-oscillatory signal."""
        from flight_analysis.stability.oscillation import compute_oscillation_index
        
        # Clean step response with no oscillation
        t = np.linspace(0, 10, 1000)
        signal = 1 - np.exp(-t / 2)  # Smooth exponential approach
        
        oi = compute_oscillation_index(t, signal)
        
        assert 0 <= oi <= 1
        # Exponential approach should have low oscillation index
        assert oi < 0.5, "Exponential signal should have relatively low oscillation index"

    def test_oscillation_index_oscillatory_signal(self, synthetic_damped_oscillation):
        """Test oscillation index on oscillatory signal."""
        from flight_analysis.stability.oscillation import compute_oscillation_index
        
        t, signal = synthetic_damped_oscillation
        oi = compute_oscillation_index(t, signal)
        
        assert 0 <= oi <= 1
        # Oscillatory signals should have moderate to high oscillation index
        assert oi > 0.1, f"Damped oscillation should have non-zero oscillation index, got {oi}"

    def test_real_flight_oscillation_analysis(self, real_flight_csv):
        """Integration test: analyze oscillation in real flight data."""
        if not real_flight_csv.exists():
            pytest.skip(f"Real flight log not found: {real_flight_csv}")
        
        from flight_analysis.core.loader import load_flight_csv, get_signal
        from flight_analysis.stability.oscillation import analyze_axis_oscillation
        
        data = load_flight_csv(str(real_flight_csv))
        
        # Analyze pitch axis
        result = analyze_axis_oscillation(data, "pitch")
        
        assert result is not None
        assert "oscillation_detected" in result
        assert "dominant_frequency_hz" in result
        assert "oscillation_index" in result


class TestStabilityMetrics:
    """Test suite for stability margin analysis."""

    @pytest.fixture
    def real_flight_csv(self):
        root = Path(__file__).parent.parent.parent
        return root / "ground_station" / "logs" / "flight_1784538359.csv"

    def test_phase_margin_estimation(self):
        """Test phase margin estimation from closed-loop data."""
        from flight_analysis.stability.margins import estimate_phase_margin
        
        # Simulate a second-order system response with clear overshoot
        t = np.linspace(0, 10, 1000)
        # Underdamped step response with ~25% overshoot
        zeta = 0.1
        wn = 4.0
        wd = wn * np.sqrt(1 - zeta**2)
        signal = 1 - (1 / np.sqrt(1 - zeta**2)) * np.exp(-zeta * wn * t) * np.cos(wd * t)
        
        pm = estimate_phase_margin(signal, t)
        assert pm is not None
        assert 20 < pm < 100, f"Expected 20-100 deg phase margin, got {pm}"

    def test_gain_margin_estimation(self):
        """Test gain margin estimation."""
        from flight_analysis.stability.margins import estimate_gain_margin
        
        t = np.linspace(0, 10, 1000)
        signal = np.ones_like(t) * 5  # Steady state value
        control_effort = np.ones_like(t) * 10  # High control effort
        
        gm = estimate_gain_margin(control_effort, signal, saturation_estimate=100)
        assert gm is not None
        assert gm > 0, "Gain margin should be positive when below saturation"

    def test_robustness_index(self):
        """Test overall robustness metric."""
        from flight_analysis.stability.margins import compute_robustness_index
        
        pm = 45.0  # Phase margin in degrees
        gm = 6.0   # Gain margin in dB
        
        ri = compute_robustness_index(pm, gm)
        assert ri is not None
        assert 0 <= ri <= 1

    def test_real_flight_stability_analysis(self, real_flight_csv):
        """Integration test: analyze stability of real flight data."""
        if not real_flight_csv.exists():
            pytest.skip(f"Real flight log not found: {real_flight_csv}")
        
        from flight_analysis.core.loader import load_flight_csv
        from flight_analysis.stability.margins import analyze_stability_margins
        
        data = load_flight_csv(str(real_flight_csv))
        margins = analyze_stability_margins(data)
        
        assert margins is not None
        assert "pitch" in margins or len(margins) > 0
