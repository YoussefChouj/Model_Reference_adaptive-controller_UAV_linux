"""Controller parameter extraction from flight telemetry.

Extracts MRAC weights, PID gains, and adaptation rates from
telemetry data for correlation analysis.
"""

from __future__ import annotations

import numpy as np
from typing import Dict, Optional, Tuple, Any, List

from flight_analysis.core.loader import get_signal


def extract_mrac_parameters(
    data: Dict[str, Tuple[List[float], List[float]]]
) -> Dict[str, Dict[str, List[float]]]:
    """Extract MRAC adaptive parameters.

    Args:
        data: Loaded flight data.

    Returns:
        Dictionary of MRAC parameters per axis.
    """
    params: Dict[str, Dict[str, List[float]]] = {}

    axes = ["pitch", "roll", "yaw", "z"]
    num_weights = 6

    for axis in axes:
        axis_params: Dict[str, List[float]] = {}
        
        # Extract theta weights
        for i in range(num_weights):
            theta_tuple = get_signal(data, f"mrac.{axis}.theta_{i}")
            if theta_tuple[0] is None:
                theta_tuple = get_signal(data, f"mrac_{axis}_theta_{i}")
            
            if theta_tuple[0] is not None:
                axis_params[f"theta_{i}"] = theta_tuple[1]
        
        # Extract adaptive signals
        for key in ["u_ad", "u_nom", "e", "xm"]:
            signal_tuple = get_signal(data, f"mrac.{axis}.{key}")
            if signal_tuple[0] is None:
                signal_tuple = get_signal(data, f"mrac_{axis}_{key}")
            
            if signal_tuple[0] is not None:
                axis_params[key] = signal_tuple[1]
        
        if axis_params:
            params[axis] = axis_params

    return params


def extract_pid_signals(
    data: Dict[str, Tuple[List[float], List[float]]]
) -> Dict[str, Dict[str, Tuple[List[float], List[float]]]]:
    """Extract PID loop signals.

    Args:
        data: Loaded flight data.

    Returns:
        Dictionary of PID signals per loop.
    """
    signals: Dict[str, Dict[str, Tuple[List[float], List[float]]]] = {}

    loops = [
        "pitch", "roll", "yaw", "z_pos",
        "locx", "locy", "locxs", "locys",
        "gyrox", "gyroy", "gyroz", "z_rate"
    ]

    for loop in loops:
        loop_signals: Dict[str, Tuple[List[float], List[float]]] = {}
        
        for key in ["Des", "FB", "U"]:
            sig_tuple = get_signal(data, f"pid.{loop}.{key}")
            if sig_tuple[0] is not None:
                loop_signals[key] = sig_tuple
        
        if loop_signals:
            signals[loop] = loop_signals

    return signals


def estimate_adaptation_rates(
    data: Dict[str, Tuple[List[float], List[float]]],
    axes: List[str] = None
) -> Dict[str, Dict[str, float]]:
    """Estimate MRAC adaptation rates from weight trajectories.

    Args:
        data: Loaded flight data.
        axes: List of axes to analyze.

    Returns:
        Dictionary of estimated adaptation rates per axis.
    """
    if axes is None:
        axes = ["pitch", "roll", "yaw", "z"]

    rates: Dict[str, Dict[str, float]] = {}

    for axis in axes:
        axis_rates: Dict[str, float] = {}

        # Analyze theta_0 (bias weight) for adaptation rate
        theta_tuple = get_signal(data, f"mrac.{axis}.theta_0")
        if theta_tuple[0] is None:
            theta_tuple = get_signal(data, f"mrac_{axis}_theta_0")

        if theta_tuple[0] is not None and len(theta_tuple[0]) > 10:
            t = np.array(theta_tuple[0])
            theta = np.array(theta_tuple[1])

            # Estimate rate of change
            d_theta = np.diff(theta) / np.diff(t)
            
            # Mean absolute rate
            mean_rate = float(np.mean(np.abs(d_theta)))
            axis_rates["mean_abs_rate"] = mean_rate

            # Peak rate (indicates active adaptation)
            peak_rate = float(np.max(np.abs(d_theta)))
            axis_rates["peak_rate"] = peak_rate

            # Convergence indicator: ratio of early to late adaptation
            early = d_theta[:len(d_theta)//3]
            late = d_theta[-len(d_theta)//3:]
            if len(early) > 0 and len(late) > 0:
                ratio = np.mean(np.abs(late)) / (np.mean(np.abs(early)) + 1e-10)
                axis_rates["convergence_ratio"] = float(ratio)

        if axis_rates:
            rates[axis] = axis_rates

    return rates


def compute_tracking_metrics(
    data: Dict[str, Tuple[List[float], List[float]]]
) -> Dict[str, Dict[str, float]]:
    """Compute tracking performance metrics for all axes.

    Args:
        data: Loaded flight data.

    Returns:
        Dictionary of metrics per axis.
    """
    metrics: Dict[str, Dict[str, float]] = {}

    loops = ["pitch", "roll", "yaw", "z_pos"]

    for loop in loops:
        des_tuple = get_signal(data, f"pid.{loop}.Des")
        fb_tuple = get_signal(data, f"pid.{loop}.FB")

        if des_tuple[0] is None or fb_tuple[0] is None:
            continue

        t_des, des = des_tuple
        t_fb, fb = fb_tuple

        # Interpolate to common time base
        t = np.array(t_des)
        des_arr = np.array(des)
        fb_arr = np.interp(t, t_fb, fb)

        # Compute error
        error = fb_arr - des_arr

        # RMSE
        rmse = float(np.sqrt(np.mean(error**2)))

        # MAE
        mae = float(np.mean(np.abs(error)))

        # Peak error
        peak = float(np.max(np.abs(error)))

        # Standard deviation of error (indicates variability)
        std = float(np.std(error))

        # Compute windowed metrics for steady-state detection
        window = max(10, len(t) // 20)
        
        metrics[loop] = {
            "rmse": rmse,
            "mae": mae,
            "peak": peak,
            "std": std,
            "n_samples": len(t),
            "duration_s": float(t[-1] - t[0]) if len(t) > 1 else 0.0
        }

    return metrics


def compute_control_effort_metrics(
    data: Dict[str, Tuple[List[float], List[float]]]
) -> Dict[str, Dict[str, float]]:
    """Compute control effort metrics.

    Args:
        data: Loaded flight data.

    Returns:
        Dictionary of control effort metrics per axis.
    """
    effort: Dict[str, Dict[str, float]] = {}

    loops = ["pitch", "roll", "yaw", "gyrox", "gyroy", "gyroz"]

    for loop in loops:
        u_tuple = get_signal(data, f"pid.{loop}.U")

        if u_tuple[0] is None:
            continue

        t, u = u_tuple
        u_arr = np.array(u)

        effort[loop] = {
            "rms": float(np.sqrt(np.mean(u_arr**2))),
            "mean": float(np.mean(u_arr)),
            "peak": float(np.max(np.abs(u_arr))),
            "std": float(np.std(u_arr)),
            "n_samples": len(t)
        }

    # Also extract MRAC adaptive effort
    for axis in ["pitch", "roll", "yaw", "z"]:
        uad_tuple = get_signal(data, f"mrac.{axis}.u_ad")
        if uad_tuple[0] is None:
            uad_tuple = get_signal(data, f"mrac_{axis}_u_ad")

        if uad_tuple[0] is not None:
            t, uad = uad_tuple
            uad_arr = np.array(uad)

            effort[f"mrac_{axis}"] = {
                "rms": float(np.sqrt(np.mean(uad_arr**2))),
                "mean": float(np.mean(uad_arr)),
                "peak": float(np.max(np.abs(uad_arr))),
                "std": float(np.std(uad_arr)),
                "n_samples": len(t)
            }

    return effort


def compute_authority_metrics(
    data: Dict[str, Tuple[List[float], List[float]]]
) -> Dict[str, Dict[str, float]]:
    """Compute MRAC vs PID authority metrics.

    Args:
        data: Loaded flight data.

    Returns:
        Dictionary of authority metrics per axis.
    """
    authority: Dict[str, Dict[str, float]] = {}

    axes = ["pitch", "roll", "yaw", "z"]

    for axis in axes:
        uad_tuple = get_signal(data, f"mrac.{axis}.u_ad")
        if uad_tuple[0] is None:
            uad_tuple = get_signal(data, f"mrac_{axis}_u_ad")

        unom_tuple = get_signal(data, f"mrac.{axis}.u_nom")
        if unom_tuple[0] is None:
            unom_tuple = get_signal(data, f"mrac_{axis}_u_nom")

        if uad_tuple[0] is None or unom_tuple[0] is None:
            continue

        t_ad, uad = uad_tuple
        t_nom, unom = unom_tuple

        uad_arr = np.array(uad)
        unom_arr = np.interp(np.array(t_ad), np.array(t_nom), np.array(unom))

        # Authority ratio: |u_ad| / (|u_ad| + |u_nom|)
        total = np.abs(uad_arr) + np.abs(unom_arr) + 1e-10
        rho = np.abs(uad_arr) / total

        authority[axis] = {
            "rho_mean": float(np.mean(rho)),
            "rho_median": float(np.median(rho)),
            "rho_p95": float(np.percentile(rho, 95)),
            "rho_max": float(np.max(rho)),
            "u_ad_rms": float(np.sqrt(np.mean(uad_arr**2))),
            "u_nom_rms": float(np.sqrt(np.mean(unom_arr**2)))
        }

    return authority
