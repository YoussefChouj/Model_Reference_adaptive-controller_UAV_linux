"""Stability margin analysis.

Estimates phase and gain margins from flight telemetry data.
"""

from __future__ import annotations

import numpy as np
from scipy import signal as scipy_signal
from typing import Dict, Optional, Tuple, Any

from flight_analysis.core.loader import get_signal


def estimate_phase_margin(
    response: np.ndarray,
    time: np.ndarray,
    target_band: float = 0.02
) -> Optional[float]:
    """Estimate phase margin from step response.

    Phase margin is estimated from the closed-loop step response
    using the relationship between overshoot and phase margin.

    For a second-order system:
        PM ≈ 100 * Mp - 50  (approximation valid for 0 < Mp < 0.75)

    Args:
        response: Step response signal.
        time: Time vector.
        target_band: 2% settling band (default).

    Returns:
        Estimated phase margin in degrees.
    """
    if len(response) < 10 or len(time) < 2:
        return None

    # Normalize to steady-state value
    tail_size = max(1, len(response) // 10)
    steady_state = float(np.mean(response[-tail_size:]))
    if abs(steady_state) < 1e-10:
        return None

    response_norm = response / steady_state

    # Find overshoot
    overshoot_idx = np.argmax(response_norm)
    overshoot = float(response_norm[overshoot_idx]) - 1.0

    if overshoot < 0:
        # No overshoot - system is overdamped or critically damped
        Ts = find_settling_time(time, response_norm, target_band)
        if Ts is None:
            return 60.0  # Default for well-damped systems
        # Assume natural frequency based on settling time
        wn_approx = 4.0 / Ts
        PM = min(90.0, 100.0 / (Ts * wn_approx + 1))
        return float(PM)

    # Calculate PM from overshoot using standard approximation
    if overshoot > 0.75:
        return 30.0  # Very underdamped

    zeta = -np.log(overshoot) / np.sqrt(np.pi**2 + np.log(overshoot)**2)

    # Phase margin formula
    if zeta >= 1.0:
        PM = 90.0
    else:
        numerator = 2 * zeta
        denominator = np.sqrt(-2 * zeta**2 + np.sqrt(1 + 4 * zeta**4))
        PM = np.arctan(numerator / denominator) * 180 / np.pi

    return float(np.clip(PM, 10.0, 120.0))


def estimate_gain_margin(
    control_signal: np.ndarray,
    error_signal: np.ndarray,
    saturation_estimate: float = 1.0
) -> Optional[float]:
    """Estimate gain margin from control effort saturation.

    Gain margin is estimated by comparing the control effort
    to an estimated saturation limit.

    Args:
        control_signal: Control effort (PID output).
        error_signal: Tracking error signal.
        saturation_estimate: Estimated saturation level.

    Returns:
        Gain margin in dB.
    """
    if len(control_signal) < 10:
        return None

    u = np.asarray(control_signal)

    # Find peak control effort
    u_peak = float(np.max(np.abs(u)))

    if u_peak < 1e-10:
        return None

    # Estimate margin to saturation
    margin = saturation_estimate / u_peak

    # Convert to dB
    gm_db = 20 * np.log10(margin)

    return float(np.clip(gm_db, -20.0, 40.0))


def compute_robustness_index(
    phase_margin_deg: float,
    gain_margin_db: float
) -> float:
    """Compute combined robustness index from margins.

    Args:
        phase_margin_deg: Phase margin in degrees.
        gain_margin_db: Gain margin in dB.

    Returns:
        Robustness index between 0 (unstable) and 1 (very robust).
    """
    # Normalize phase margin (typical range: 30-90 deg)
    pm_norm = np.clip((phase_margin_deg - 15) / 60, 0, 1)

    # Normalize gain margin (typical range: 6-20 dB)
    gm_norm = np.clip((gain_margin_db - 3) / 15, 0, 1)

    # Combined index (geometric mean for balanced robustness)
    ri = np.sqrt(pm_norm * gm_norm)

    return float(ri)


def find_settling_time(
    time: np.ndarray,
    response: np.ndarray,
    band: float = 0.02
) -> Optional[float]:
    """Find settling time (time to enter and stay within band).

    Args:
        time: Time vector.
        response: Response signal.
        band: Settling band (fraction of steady-state).

    Returns:
        Settling time in seconds, or None if never settles.
    """
    if len(time) < 2 or len(response) < 2:
        return None

    tail_size = max(1, len(response) // 10)
    steady_state = float(np.mean(response[-tail_size:]))
    if abs(steady_state) < 1e-10:
        return None

    response_norm = response / steady_state

    # Find where response enters and stays within band
    in_band = np.abs(response_norm - 1.0) <= band

    # Work backwards from end
    for i in range(len(in_band) - 1, -1, -1):
        if not in_band[i]:
            # Found point that left band
            if i < len(time) - 1:
                return float(time[i + 1])
            return None

    # Never left band
    return float(time[0])


def estimate_crossover_frequency(
    error: np.ndarray,
    control: np.ndarray,
    time: np.ndarray
) -> Optional[float]:
    """Estimate crossover frequency from closed-loop data.

    The crossover frequency (wc) is where the loop gain equals 1 (0 dB).

    Args:
        error: Tracking error signal.
        control: Control effort signal.
        time: Time vector.

    Returns:
        Estimated crossover frequency in Hz.
    """
    if len(error) < 50 or len(control) < 50:
        return None

    e = np.asarray(error)
    u = np.asarray(control)

    # Estimate loop gain as u/e (simplified Bode analysis)
    loop_gain = np.zeros_like(u)
    nonzero = np.abs(e) > 1e-6
    loop_gain[nonzero] = u[nonzero] / e[nonzero]

    # Smooth the estimate
    window = min(51, len(loop_gain) // 10)
    if window < 5:
        window = 5
    if window % 2 == 0:
        window += 1

    loop_gain_smooth = np.convolve(loop_gain, np.ones(window)/window, mode='same')

    # Find where |loop_gain| ≈ 1
    mag = np.abs(loop_gain_smooth)
    mag_1_idx = np.argmin(np.abs(mag - 1.0))

    if len(time) > 1:
        dt = float(np.median(np.diff(time)))
        if dt > 0:
            # Rough frequency estimate (this is simplified)
            wc = 1.0 / (dt * (mag_1_idx + 1))
            return float(np.clip(wc, 0.1, 50.0))

    return None


def analyze_stability_margins(
    data: Dict[str, Tuple[list, list]],
    axes: list = None
) -> Dict[str, Dict[str, Any]]:
    """Analyze stability margins for all axes.

    Args:
        data: Loaded flight data.
        axes: List of axes to analyze ('pitch', 'roll', 'yaw', 'z').

    Returns:
        Dictionary of margin results per axis.
    """
    if axes is None:
        axes = ['pitch', 'roll', 'yaw', 'z']

    results: Dict[str, Dict[str, Any]] = {}

    for axis in axes:
        axis_result: Dict[str, Any] = {
            "axis": axis,
            "phase_margin_deg": None,
            "gain_margin_db": None,
            "robustness_index": None,
        }

        # Get rate loop signals for margin estimation
        rate_loop = "gyrox" if axis == "roll" else ("gyroy" if axis == "pitch" else f"gyro{axis}")

        des_tuple = get_signal(data, f"pid.{rate_loop}.Des")
        fb_tuple = get_signal(data, f"pid.{rate_loop}.FB")
        u_tuple = get_signal(data, f"pid.{rate_loop}.U")

        if des_tuple[0] is not None and fb_tuple[0] is not None:
            t = np.array(des_tuple[0])
            fb = np.array(fb_tuple[1])
            des = np.interp(t, des_tuple[0], des_tuple[1])

            # Error = feedback - desired for negative feedback
            error = fb - des

            # Estimate phase margin from response
            pm = estimate_phase_margin(fb, t)
            axis_result["phase_margin_deg"] = pm

            # Estimate gain margin from control effort
            if u_tuple[0] is not None:
                u_interp = np.interp(t, u_tuple[0], u_tuple[1])
                gm = estimate_gain_margin(u_interp, error)
                axis_result["gain_margin_db"] = gm

            # Compute robustness
            if pm is not None and axis_result["gain_margin_db"] is not None:
                ri = compute_robustness_index(pm, axis_result["gain_margin_db"])
                axis_result["robustness_index"] = ri

        results[axis] = axis_result

    return results
