"""Expert-level diagnostic alerts for flight analysis.

Generates actionable alerts based on oscillation, stability, and performance data.
"""

from __future__ import annotations

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum


class AlertLevel(Enum):
    """Alert severity levels."""
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass
class DiagnosticAlert:
    """A diagnostic alert with context."""
    level: str
    code: str
    axis: str
    message: str
    details: Dict[str, Any]
    recommendations: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "level": self.level,
            "code": self.code,
            "axis": self.axis,
            "message": self.message,
            "details": self.details,
            "recommendations": self.recommendations
        }


def classify_diagnosis(
    oscillation_detected: bool,
    frequency: float = 0.0,
    damping_ratio: float = 1.0,
    oscillation_index: float = 0.0,
    tracking_rmse: float = 0.0,
    phase_margin: float = 60.0
) -> Dict[str, Any]:
    """Classify the primary diagnosis category.

    Args:
        oscillation_detected: Whether oscillation was detected.
        frequency: Dominant oscillation frequency (Hz).
        damping_ratio: Estimated damping ratio.
        oscillation_index: Computed oscillation index (0-1).
        tracking_rmse: Root mean square error.
        phase_margin: Phase margin (degrees).

    Returns:
        Classification result with category and confidence.
    """
    # Determine primary category
    if oscillation_detected and oscillation_index > 0.4:
        if frequency > 10:
            category = "oscillation"
            subcategory = "high_freq_chatter"
            confidence = 0.9
        elif damping_ratio < 0.1:
            category = "oscillation"
            subcategory = "poor_damping"
            confidence = 0.85
        else:
            category = "oscillation"
            subcategory = "moderate"
            confidence = 0.7
    elif phase_margin < 30:
        category = "stability"
        subcategory = "low_phase_margin"
        confidence = 0.8
    elif tracking_rmse > 1.0:
        category = "performance"
        subcategory = "poor_tracking"
        confidence = 0.75
    else:
        category = "nominal"
        subcategory = "healthy"
        confidence = 0.95

    return {
        "category": category,
        "subcategory": subcategory,
        "confidence": confidence
    }


def generate_expert_alerts(
    oscillation_results: Dict[str, Dict[str, Any]],
    stability_margins: Dict[str, Dict[str, Any]] = None,
    performance_metrics: Dict[str, Dict[str, float]] = None
) -> List[DiagnosticAlert]:
    """Generate expert-level diagnostic alerts.

    Args:
        oscillation_results: Oscillation analysis results per axis.
        stability_margins: Stability margin results per axis.
        performance_metrics: Performance metrics per axis.

    Returns:
        List of diagnostic alerts.
    """
    if stability_margins is None:
        stability_margins = {}
    if performance_metrics is None:
        performance_metrics = {}

    alerts: List[DiagnosticAlert] = []

    # Analyze each axis
    for axis, osc_data in oscillation_results.items():
        if not osc_data:
            continue

        severity = osc_data.get("severity", "minor")
        oi = osc_data.get("oscillation_index", 0)
        freq = osc_data.get("dominant_frequency_hz", 0)
        zeta = osc_data.get("damping_ratio")

        recommendations = []

        # High-frequency oscillation (oscillation > 10 Hz)
        if freq > 10 and severity in ["warning", "critical"]:
            recommendations.append("Reduce high-frequency gain (Kp) in rate loop")
            recommendations.append("Increase L1 filter cutoff frequency")
            recommendations.append("Check for sensor noise or vibrations")

            alerts.append(DiagnosticAlert(
                level="CRITICAL" if freq > 15 else "WARNING",
                code="HIGH_FREQ_CHATTER",
                axis=axis,
                message=f"High-frequency oscillation detected at {freq:.1f} Hz",
                details={
                    "frequency_hz": freq,
                    "oscillation_index": oi,
                    "severity": severity
                },
                recommendations=recommendations
            ))

        # Poor damping (zeta < 0.1)
        elif zeta is not None and zeta < 0.1 and severity != "minor":
            recommendations.append("Increase derivative gain (Kd) to improve damping")
            recommendations.append("Reduce proportional gain (Kp)")
            recommendations.append("Consider adding notch filter if structural resonance")

            alerts.append(DiagnosticAlert(
                level="WARNING",
                code="POOR_DAMPING",
                axis=axis,
                message=f"Poor damping detected (ζ={zeta:.2f})",
                details={
                    "damping_ratio": zeta,
                    "oscillation_index": oi
                },
                recommendations=recommendations
            ))

        # Controller fighting oscillation
        if osc_data.get("controller_reacting", False):
            recommendations.append("MRAC is reacting to oscillation")
            recommendations.append("Check if oscillation is mechanical or control-related")

            alerts.append(DiagnosticAlert(
                level="INFO",
                code="CONTROLLER_REACTING",
                axis=axis,
                message="Controller actively compensating for oscillation",
                details={"frequency_hz": freq},
                recommendations=recommendations
            ))

        # Stability margin warnings
        margin = stability_margins.get(axis, {})
        pm = margin.get("phase_margin_deg", 60)

        if pm is not None and pm < 45:
            alerts.append(DiagnosticAlert(
                level="WARNING" if pm > 30 else "CRITICAL",
                code="LOW_PHASE_MARGIN",
                axis=axis,
                message=f"Phase margin is low ({pm:.1f}°)",
                details={
                    "phase_margin_deg": pm,
                    "typical_range": "45-70 degrees"
                },
                recommendations=[
                    "Reduce proportional gain",
                    "Increase derivative action",
                    "Check for time delays in the loop"
                ]
            ))

        # Performance warnings
        perf = performance_metrics.get(axis, {})
        rmse = perf.get("rmse", 0)

        if rmse > 0.5:
            alerts.append(DiagnosticAlert(
                level="WARNING",
                code="POOR_TRACKING",
                axis=axis,
                message=f"High tracking error (RMSE={rmse:.3f})",
                details={"rmse": rmse},
                recommendations=[
                    "Increase controller gains",
                    "Check for disturbances or wind",
                    "Verify reference model matches plant"
                ]
            ))

    return alerts


def generate_tuning_recommendations(alerts: List[Dict[str, Any]]) -> List[str]:
    """Generate tuning recommendations from alerts.

    Args:
        alerts: List of alert dictionaries.

    Returns:
        Prioritized list of recommendations.
    """
    recommendations: List[str] = []
    critical_count = sum(1 for a in alerts if a.get("level") == "CRITICAL")
    warning_count = sum(1 for a in alerts if a.get("level") == "WARNING")

    # Overall assessment
    if critical_count > 0:
        recommendations.append(
            f"⚠️ {critical_count} CRITICAL issue(s) detected - address immediately"
        )
    elif warning_count > 0:
        recommendations.append(
            f"⚡ {warning_count} WARNING(s) detected - review recommended"
        )
    else:
        recommendations.append("✅ Flight appears healthy - no critical issues")

    # Group by axis
    axes_with_issues = set(a.get("axis") for a in alerts if a.get("axis"))
    for axis in axes_with_issues:
        axis_alerts = [a for a in alerts if a.get("axis") == axis]
        
        if any(a.get("code") == "HIGH_FREQ_CHATTER" for a in axis_alerts):
            recommendations.append(
                f"{axis.upper()}: High-frequency oscillation - reduce Kp or increase L1 filter"
            )
        
        if any(a.get("code") == "POOR_DAMPING" for a in axis_alerts):
            recommendations.append(
                f"{axis.upper()}: Poor damping - increase Kd or reduce Kp"
            )
        
        if any(a.get("code") == "LOW_PHASE_MARGIN" for a in axis_alerts):
            recommendations.append(
                f"{axis.upper()}: Low phase margin - retune for more stability"
            )

    return recommendations


def summarize_flight_health(
    oscillation_results: Dict[str, Dict[str, Any]],
    stability_margins: Dict[str, Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Summarize overall flight health.

    Args:
        oscillation_results: Oscillation analysis results.
        stability_margins: Stability margin results.

    Returns:
        Health summary dictionary.
    """
    if stability_margins is None:
        stability_margins = {}

    total_axes = len(oscillation_results)
    oscillating_axes = sum(
        1 for r in oscillation_results.values()
        if r and r.get("oscillation_detected", False)
    )

    critical_alerts = sum(
        1 for r in oscillation_results.values()
        if r and r.get("severity") == "critical"
    )

    avg_oi = 0.0
    if oscillation_results:
        oi_values = [
            r.get("oscillation_index", 0)
            for r in oscillation_results.values()
            if r
        ]
        if oi_values:
            avg_oi = sum(oi_values) / len(oi_values)

    # Compute health score (0-100)
    health_score = 100.0
    health_score -= oscillating_axes * 10
    health_score -= critical_alerts * 20
    health_score -= avg_oi * 30
    health_score = max(0.0, min(100.0, health_score))

    # Determine status
    if health_score >= 80:
        status = "HEALTHY"
        color = "green"
    elif health_score >= 60:
        status = "CAUTION"
        color = "yellow"
    elif health_score >= 40:
        status = "WARNING"
        color = "orange"
    else:
        status = "CRITICAL"
        color = "red"

    return {
        "health_score": health_score,
        "status": status,
        "color": color,
        "total_axes": total_axes,
        "oscillating_axes": oscillating_axes,
        "critical_alerts": critical_alerts,
        "average_oscillation_index": avg_oi
    }
