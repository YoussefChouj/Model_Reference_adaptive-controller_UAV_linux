"""Parameter-performance sensitivity analysis.

Computes correlations between controller parameters and performance metrics.
"""

from __future__ import annotations

import numpy as np
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class SensitivityResult:
    """Result of parameter sensitivity analysis."""
    parameter: str
    axis: str
    pearson_r: float
    p_value: float
    interpretation: str  # 'positive', 'negative', 'neutral'


def compute_parameter_sensitivity(
    data: Dict[str, Any],
    params: Dict[str, Dict[str, List[float]]],
    performance_metric: str = "rmse"
) -> Dict[str, List[SensitivityResult]]:
    """Compute parameter sensitivity for each axis.

    Analyzes how changes in MRAC/PID parameters correlate with
    performance metrics.

    Args:
        data: Loaded flight data.
        params: Dictionary of parameters (e.g., gamma values per axis).
        performance_metric: Metric to analyze sensitivity against.

    Returns:
        Dictionary of sensitivity results per axis.
    """
    results: Dict[str, List[SensitivityResult]] = {}

    # Extract performance metrics
    from flight_analysis.correlation.param_map import compute_tracking_metrics
    metrics = compute_tracking_metrics(data)

    for axis in ["pitch", "roll", "yaw", "z_pos"]:
        axis_results: List[SensitivityResult] = []

        # Get performance for this axis
        perf = metrics.get(axis, {})
        if not perf:
            continue

        perf_value = perf.get(performance_metric, 0)

        # Analyze sensitivity to gamma values
        gamma_values = params.get("gamma", {}).get(axis, [])
        for i, gamma_i in enumerate(gamma_values):
            # For single-flight analysis, we can't compute sensitivity
            # without multiple flights with different gamma values
            # Instead, we compute the theoretical sensitivity
            sensitivity = SensitivityResult(
                parameter=f"gamma_{i}",
                axis=axis,
                pearson_r=0.0,  # N/A for single flight
                p_value=1.0,
                interpretation="needs_multi_flight_data"
            )
            axis_results.append(sensitivity)

        # Analyze sensitivity to MRAC weight norms
        from flight_analysis.correlation.param_map import extract_mrac_parameters
        mrac_params = extract_mrac_parameters(data)
        
        if axis in mrac_params:
            theta_values = mrac_params[axis]
            
            # Compute weight norm
            if theta_values:
                # Get theta_0 for bias analysis
                theta_0 = theta_values.get("theta_0", [])
                if len(theta_0) > 0:
                    theta_norm = np.linalg.norm([
                        theta_values.get(f"theta_{i}", [0])[0] 
                        for i in range(6)
                    ])
                    
                    sensitivity = SensitivityResult(
                        parameter="weight_norm",
                        axis=axis,
                        pearson_r=0.0,
                        p_value=1.0,
                        interpretation="static_single_flight"
                    )
                    axis_results.append(sensitivity)

        results[axis] = axis_results

    return results


def rank_performance(
    flight_metrics: Dict[str, Dict[str, float]],
    weights: Dict[str, float] = None
) -> List[Dict[str, Any]]:
    """Rank flights by overall performance.

    Args:
        flight_metrics: Dictionary of flight_id -> metrics dict.
        weights: Optional weights for each metric.

    Returns:
        List of flights sorted by score (best first).
    """
    if weights is None:
        # Default weights for different metrics
        weights = {
            "rmse": 0.4,
            "oscillation_index": 0.3,
            "peak_error": 0.2,
            "settling_time": 0.1
        }

    ranked = []

    for flight_id, metrics in flight_metrics.items():
        score = 0.0
        total_weight = 0.0

        for metric, weight in weights.items():
            if metric in metrics:
                value = metrics[metric]
                # Normalize: lower is better, so invert
                if value > 0:
                    # Use inverse for minimization
                    normalized = 1.0 / (1.0 + value)
                else:
                    normalized = 1.0
                
                score += weight * normalized
                total_weight += weight

        if total_weight > 0:
            score /= total_weight

        ranked.append({
            "flight_id": flight_id,
            "score": score,
            "metrics": metrics
        })

    # Sort by score descending
    ranked.sort(key=lambda x: x["score"], reverse=True)

    return ranked


def compute_cross_axis_correlation(
    data: Dict[str, Any]
) -> Dict[str, Dict[str, float]]:
    """Compute correlation between axes.

    Useful for identifying cross-coupling issues.

    Args:
        data: Loaded flight data.

    Returns:
        Dictionary of correlation coefficients between axes.
    """
    from flight_analysis.correlation.param_map import extract_mrac_parameters

    mrac_params = extract_mrac_parameters(data)
    correlations: Dict[str, Dict[str, float]] = {}

    axes = ["pitch", "roll", "yaw", "z"]

    for i, ax1 in enumerate(axes):
        correlations[ax1] = {}
        
        if ax1 not in mrac_params:
            continue

        # Get error signals
        e1_tuple = mrac_params[ax1].get("e")
        if not e1_tuple:
            continue

        t1 = np.array(e1_tuple) if isinstance(e1_tuple, list) else np.array(e1_tuple[0]) if e1_tuple else None
        v1 = np.array(e1_tuple) if not isinstance(e1_tuple, tuple) else np.array(e1_tuple[1]) if len(e1_tuple) > 1 else None

        if t1 is None or v1 is None:
            continue

        for j, ax2 in enumerate(axes):
            if i >= j:
                continue

            if ax2 not in mrac_params:
                continue

            e2_tuple = mrac_params[ax2].get("e")
            if not e2_tuple:
                continue

            t2 = np.array(e2_tuple) if isinstance(e2_tuple, list) else np.array(e2_tuple[0]) if e2_tuple else None
            v2 = np.array(e2_tuple) if not isinstance(e2_tuple, tuple) else np.array(e2_tuple[1]) if len(e2_tuple) > 1 else None

            if t2 is None or v2 is None:
                continue

            # Interpolate to common time base
            v2_interp = np.interp(t1, t2, v2)

            # Compute correlation
            if len(v1) > 10 and len(v2_interp) > 10:
                corr = float(np.corrcoef(v1[:len(v2_interp)], v2_interp[:len(v1)])[0, 1])
                if np.isnan(corr):
                    corr = 0.0
                correlations[ax1][ax2] = corr

    return correlations


def generate_tuning_recommendations(
    oscillation_results: Dict[str, Any],
    stability_margins: Dict[str, Any],
    performance_metrics: Dict[str, Dict[str, float]]
) -> List[str]:
    """Generate expert tuning recommendations.

    Args:
        oscillation_results: Results from oscillation analysis.
        stability_margins: Stability margin analysis results.
        performance_metrics: Tracking and control effort metrics.

    Returns:
        List of recommendation strings.
    """
    recommendations: List[str] = []

    for axis, osc in oscillation_results.items():
        if not osc.get("oscillation_detected"):
            continue

        oi = osc.get("oscillation_index", 0)
        freq = osc.get("dominant_frequency_hz", 0)
        severity = osc.get("severity", "minor")

        # Get stability info
        margin = stability_margins.get(axis, {})
        pm = margin.get("phase_margin_deg", 60)

        if severity == "critical":
            if freq > 10:
                recommendations.append(
                    f"{axis.upper()}: CRITICAL high-frequency oscillation ({freq:.1f} Hz). "
                    f"Reduce Kp/gamma significantly or increase derivative damping."
                )
            elif pm < 30:
                recommendations.append(
                    f"{axis.upper()}: CRITICAL low phase margin ({pm:.1f} deg). "
                    f"Reduce proportional gain to improve stability."
                )
        elif severity == "warning":
            if freq > 5:
                recommendations.append(
                    f"{axis.upper()}: WARNING moderate oscillation ({freq:.1f} Hz, OI={oi:.2f}). "
                    f"Consider reducing adaptation rate gamma or adding L1 filter."
                )
            else:
                recommendations.append(
                    f"{axis.upper()}: WARNING oscillation detected (OI={oi:.2f}). "
                    f"Check for mechanical issues or tuning mismatch."
                )

        # Check for low authority
        auth = oscillation_results.get(axis, {}).get("control_effort_oscillation_index", 0)
        if auth > 0.5:
            recommendations.append(
                f"{axis.upper()}: High control effort oscillation suggests controller "
                f"is fighting oscillation. Consider increasing damping or reducing aggressive maneuvers."
            )

    # Check performance metrics
    for loop, metrics in performance_metrics.items():
        rmse = metrics.get("rmse", float('inf'))
        if rmse > 1.0:
            recommendations.append(
                f"{loop.upper()}: High tracking error (RMSE={rmse:.2f}). "
                f"May need gain increase or adaptation tuning."
            )

    if not recommendations:
        recommendations.append("All metrics within acceptable ranges. No immediate tuning changes recommended.")

    return recommendations
