"""Oscillation detection and stability analysis.

Uses spectral analysis, autocorrelation, and envelope methods to detect
and characterize oscillations in flight data.
"""

from __future__ import annotations

import numpy as np
from scipy import signal as scipy_signal
from scipy.interpolate import interp1d
from typing import Dict, Optional, Tuple, Any

from flight_analysis.core.loader import get_signal


def detect_dominant_frequency(
    t: np.ndarray,
    v: np.ndarray,
    fs: float = 100.0,
    nperseg: int = 256
) -> Tuple[float, np.ndarray]:
    """Detect dominant frequency using Welch's PSD estimate.

    Args:
        t: Time vector.
        v: Signal values.
        fs: Sample rate in Hz.
        nperseg: FFT segment length.

    Returns:
        (dominant_frequency_hz, psd_frequencies) tuple.
    """
    if len(v) < nperseg:
        return 0.0, np.array([])

    v = np.asarray(v, dtype=np.float64)
    v = v - np.mean(v)  # Remove DC

    f, Pxx = scipy_signal.welch(v, fs=fs, nperseg=min(nperseg, len(v)))

    # Exclude DC component
    if len(Pxx) > 1:
        max_idx = np.argmax(Pxx[1:]) + 1
    else:
        max_idx = 0

    dominant_freq = float(f[max_idx]) if max_idx < len(f) else 0.0
    return dominant_freq, f


def compute_zero_crossing_rate(
    t: np.ndarray,
    v: np.ndarray,
    threshold: float = 0.0
) -> float:
    """Compute zero-crossing rate (crossings per second).

    Args:
        t: Time vector.
        v: Signal values.
        threshold: Threshold for zero crossing detection.

    Returns:
        Zero-crossings per second.
    """
    if len(v) < 2:
        return 0.0

    v = np.asarray(v)
    duration = float(t[-1] - t[0])

    if duration <= 0:
        return 0.0

    # Sign changes relative to threshold
    above = v > threshold
    crossings = np.sum(np.diff(above.astype(int)) != 0)

    return float(crossings) / duration


def detect_periodicity(
    t: np.ndarray,
    v: np.ndarray,
    max_lag: float = 2.0
) -> Optional[float]:
    """Detect periodicity using autocorrelation.

    Args:
        t: Time vector.
        v: Signal values.
        max_lag: Maximum lag to search in seconds.

    Returns:
        Detected period in seconds, or None if no clear periodicity.
    """
    if len(v) < 10:
        return None

    v = np.asarray(v, dtype=np.float64)
    v = v - np.mean(v)

    # Interpolate to uniform grid
    dt = float(np.median(np.diff(t)))
    n_uniform = int((t[-1] - t[0]) / dt) + 1
    t_uniform = np.linspace(t[0], t[-1], n_uniform)
    v_interp = np.interp(t_uniform, t, v)

    # Compute autocorrelation
    n = len(v_interp)
    max_lag_samples = min(int(max_lag / dt), n // 2)

    autocorr = np.correlate(v_interp[:n//2], v_interp[:n//2], mode='full')
    autocorr = autocorr[n//2 - 1:n//2 + max_lag_samples]

    if len(autocorr) < 2:
        return None

    autocorr = autocorr / (autocorr[0] + 1e-10)

    # Find first significant peak after lag 0
    autocorr_smooth = np.convolve(autocorr, np.ones(5)/5, mode='same')

    # Look for peaks
    peaks = []
    for i in range(2, len(autocorr_smooth) - 1):
        if autocorr_smooth[i] > autocorr_smooth[i-1] and autocorr_smooth[i] > autocorr_smooth[i+1]:
            if autocorr_smooth[i] > 0.2:  # Threshold for significance
                peaks.append(i)

    if peaks:
        # Return period of first significant peak
        first_peak = peaks[0]
        period = first_peak * dt
        return float(period)

    return None


def estimate_damping_ratio(
    t: np.ndarray,
    v: np.ndarray,
    method: str = "envelope"
) -> Optional[float]:
    """Estimate damping ratio from damped oscillation.

    Args:
        t: Time vector.
        v: Signal values.
        method: 'envelope' or 'logdec'.

    Returns:
        Estimated damping ratio (zeta).
    """
    if len(v) < 20:
        return None

    v = np.asarray(v, dtype=np.float64)

    # Find peaks and troughs
    peaks_idx, _ = scipy_signal.find_peaks(v)
    troughs_idx, _ = scipy_signal.find_peaks(-v)

    if len(peaks_idx) < 2 and len(troughs_idx) < 2:
        return None

    # Combine and sort all extrema
    extrema = np.concatenate([peaks_idx, troughs_idx])
    extrema = np.sort(extrema)

    if len(extrema) < 2:
        return None

    # Compute peak-to-peak amplitudes
    amplitudes = np.abs(v[extrema[1:]] - v[extrema[:-1]])

    if len(amplitudes) < 2:
        return None

    # Logarithmic decrement method
    # zeta = 1 / sqrt(1 + (2*pi / ln(ratio))^2)
    # where ratio = a_i / a_(i+1)

    ratios = amplitudes[:-1] / (amplitudes[1:] + 1e-10)
    ratios = ratios[np.isfinite(ratios) & (ratios > 0)]

    if len(ratios) == 0:
        return None

    mean_ratio = np.mean(ratios)

    if mean_ratio <= 1.0:
        return None

    ln_ratio = np.log(mean_ratio)

    if abs(ln_ratio) < 1e-6:
        return 0.0  # Undamped

    # Logarithmic decrement: delta = ln(a_i/a_{i+1})
    # For light damping: zeta ≈ delta / sqrt(4*pi^2 + delta^2)
    delta = ln_ratio

    # More robust formula for any damping
    # Using the relation between successive peaks
    zeta = abs(delta) / (2 * np.pi)

    # Clamp to reasonable range
    zeta = np.clip(zeta, 0.001, 0.999)

    return float(zeta)


def compute_oscillation_index(
    t: np.ndarray,
    v: np.ndarray,
    threshold_percentile: float = 90.0
) -> float:
    """Compute oscillation index (0-1 scale).

    Combines multiple oscillation indicators into a single metric.

    Args:
        t: Time vector.
        v: Signal values.
        threshold_percentile: Percentile for activity threshold.

    Returns:
        Oscillation index between 0 (no oscillation) and 1 (strong oscillation).
    """
    if len(v) < 10:
        return 0.0

    v = np.asarray(v, dtype=np.float64)
    v = v - np.mean(v)

    # Normalize
    std = np.std(v)
    if std < 1e-10:
        return 0.0
    v_norm = v / std

    # 1. Zero-crossing rate component
    zcr = compute_zero_crossing_rate(t, v_norm)
    # Typical oscillation might have 2-20 ZC/s depending on frequency
    zcr_component = np.clip(zcr / 15.0, 0, 1)

    # 2. Autocorrelation at quarter-period lag
    dt = float(np.median(np.diff(t)))
    quarter_lag = max(1, int(0.25 / dt))

    if len(v_norm) > quarter_lag * 2:
        autocorr = np.corrcoef(v_norm[:-quarter_lag], v_norm[quarter_lag:])[0, 1]
        autocorr = 0.0 if np.isnan(autocorr) else autocorr
        # Oscillatory signals have negative autocorrelation at quarter period
        autocorr_component = np.clip(abs(autocorr), 0, 1)
    else:
        autocorr_component = 0.0

    # 3. High-frequency content (from derivative)
    dv = np.diff(v_norm)
    dv = dv / (np.std(dv) + 1e-10)
    hf_power = np.mean(dv**2)
    hf_component = np.clip(hf_power / 10.0, 0, 1)

    # 4. Oscillation in control effort variance
    # Check if signal has sustained oscillation pattern
    window = min(len(v_norm) // 4, 100)
    if window > 10:
        rolling_var = np.array([
            np.var(v_norm[i:i+window])
            for i in range(0, len(v_norm) - window, window // 2)
        ])
        var_stability = 1.0 - np.clip(np.std(rolling_var) / (np.mean(rolling_var) + 1e-10), 0, 1)
    else:
        var_stability = 0.5

    # Combine components
    # Weights: ZCR (40%), Autocorr (30%), HF content (20%), Var stability (10%)
    oi = (0.4 * zcr_component +
          0.3 * autocorr_component +
          0.2 * hf_component +
          0.1 * var_stability)

    return float(np.clip(oi, 0.0, 1.0))


def analyze_axis_oscillation(
    data: Dict[str, Tuple[list, list]],
    axis: str,
    fs: float = 100.0
) -> Dict[str, Any]:
    """Comprehensive oscillation analysis for a single axis.

    Args:
        data: Loaded flight data dictionary.
        axis: Axis name ('pitch', 'roll', 'yaw', 'z').
        fs: Estimated sample rate.

    Returns:
        Dictionary with oscillation analysis results.
    """
    result: Dict[str, Any] = {
        "axis": axis,
        "oscillation_detected": False,
        "confidence": 0.0,
    }

    # Get error signal (primary oscillation indicator)
    e_tuple = get_signal(data, f"mrac.{axis}.e")
    if e_tuple[0] is None:
        e_tuple = get_signal(data, f"mrac_{axis}_e")

    # Get control effort (for secondary indicators)
    uad_tuple = get_signal(data, f"mrac.{axis}.u_ad")
    if uad_tuple[0] is None:
        uad_tuple = get_signal(data, f"mrac_{axis}_u_ad")

    # Also check rate loop error
    rate_axis = "gyrox" if axis == "roll" else ("gyroy" if axis == "pitch" else f"gyro{axis}")
    rate_e_tuple = get_signal(data, f"pid.{rate_axis}.Des")
    if rate_e_tuple[0] is not None:
        rate_fb_tuple = get_signal(data, f"pid.{rate_axis}.FB")
        if rate_fb_tuple[0] is not None:
            t = np.array(rate_e_tuple[0])
            fb = np.array(rate_fb_tuple[1])
            des = np.interp(t, rate_e_tuple[0], rate_e_tuple[1])
            rate_error = fb - des
            # Use rate error if error signal not available
            if e_tuple[0] is None:
                e_tuple = (list(t), list(rate_error))

    # Analyze primary error signal
    if e_tuple[0] is not None and len(e_tuple[0]) > 50:
        t = np.array(e_tuple[0])
        e = np.array(e_tuple[1])

        # Compute oscillation index
        oi = compute_oscillation_index(t, e)
        result["oscillation_index"] = oi

        # Detect dominant frequency
        dom_freq, _ = detect_dominant_frequency(t, e, fs=fs)
        result["dominant_frequency_hz"] = dom_freq

        # Detect periodicity
        period = detect_periodicity(t, e)
        result["period_s"] = period

        # Estimate damping (if we have enough oscillation cycles)
        zeta = estimate_damping_ratio(t, e)
        result["damping_ratio"] = zeta

        # Zero crossing rate
        zcr = compute_zero_crossing_rate(t, e)
        result["zero_crossing_rate_hz"] = zcr

        # Determine if oscillation is present
        # Criteria: High oscillation index OR clear periodicity with significant amplitude
        amplitude = float(np.ptp(e))
        oscillation_detected = (
            oi > 0.4 or
            (period is not None and 0.05 < period < 1.0 and oi > 0.2 and amplitude > 0.1)
        )

        result["oscillation_detected"] = oscillation_detected
        result["oscillation_amplitude"] = amplitude

        # Confidence based on data quality and signal strength
        confidence = min(1.0, oi * 1.5)
        if amplitude < 0.01:
            confidence *= 0.5  # Low amplitude = lower confidence
        result["confidence"] = confidence

    # Analyze control effort if available
    if uad_tuple[0] is not None and len(uad_tuple[0]) > 50:
        t_u = np.array(uad_tuple[0])
        u_ad = np.array(uad_tuple[1])

        # Check for high-frequency content in control effort
        # This indicates the controller is fighting oscillation
        u_oi = compute_oscillation_index(t_u, u_ad)
        result["control_effort_oscillation_index"] = u_oi

        u_dom_freq, _ = detect_dominant_frequency(t_u, u_ad, fs=fs)
        result["control_effort_dominant_freq_hz"] = u_dom_freq

        # If control effort oscillates at same frequency as error, controller is reacting
        if "dominant_frequency_hz" in result and u_dom_freq > 0:
            freq_match = abs(result["dominant_frequency_hz"] - u_dom_freq) < 1.0
            result["controller_reacting"] = freq_match

    # Severity classification
    if result["oscillation_detected"]:
        oi = result.get("oscillation_index", 0)
        freq = result.get("dominant_frequency_hz", 0)
        zeta = result.get("damping_ratio")

        if oi > 0.7 or (freq > 10 and zeta is not None and zeta < 0.1):
            result["severity"] = "critical"
        elif oi > 0.5 or freq > 8:
            result["severity"] = "warning"
        else:
            result["severity"] = "minor"

    return result
