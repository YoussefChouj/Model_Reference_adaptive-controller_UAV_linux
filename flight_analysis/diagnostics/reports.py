"""Report generation for flight analysis.

Generates comprehensive markdown and JSON reports with visualizations.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

from flight_analysis.core.loader import compute_data_quality


def compute_summary_statistics(data: Dict[str, Any]) -> Dict[str, Any]:
    """Compute summary statistics from flight data.

    Args:
        data: Loaded flight data.

    Returns:
        Summary statistics dictionary.
    """
    # Compute basic quality metrics
    quality = compute_data_quality(data)

    # Collect all time points
    all_times = set()
    for times, _ in data.values():
        all_times.update(times)

    sorted_times = sorted(all_times)
    duration = sorted_times[-1] - sorted_times[0] if len(sorted_times) > 1 else 0.0

    return {
        "duration_s": duration,
        "num_samples": quality.get("total_samples", 0),
        "num_signals": quality.get("total_signals", 0),
        "time_span_s": quality.get("time_span_s", 0.0),
        "max_gap_s": quality.get("max_gap_s", 0.0),
        "sample_rate_hz": quality.get("total_samples", 0) / max(duration, 1.0)
    }


def generate_markdown_report(
    data: Dict[str, Any],
    results: Dict[str, Any],
    output_path: str
) -> None:
    """Generate comprehensive markdown report.

    Args:
        data: Loaded flight data.
        results: Analysis results dictionary.
        output_path: Path to write the markdown report.
    """
    stats = compute_summary_statistics(data)
    oscillation = results.get("oscillation", {})
    stability = results.get("stability", {})
    performance = results.get("performance", {})

    lines = [
        "# Flight Analysis Report",
        "",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Duration:** {stats['duration_s']:.1f} seconds",
        f"**Samples:** {stats['num_samples']:,}",
        "",
        "---",
        "",
        "## Executive Summary",
        "",
    ]

    # Health assessment
    health = results.get("health", {})
    if health:
        score = health.get("health_score", 100)
        status = health.get("status", "UNKNOWN")
        lines.append(f"**Overall Status:** {status} (score: {score:.0f}/100)")
        lines.append("")

    # Oscillation summary
    oscillating = [ax for ax, r in oscillation.items()
                   if isinstance(r, dict) and r.get("oscillation_detected")]
    
    if oscillating:
        lines.append(f"⚠️ **Oscillation detected on:** {', '.join(oscillating)}")
    else:
        lines.append("✅ **No oscillation detected**")
    lines.append("")

    # Per-axis analysis
    lines.extend([
        "## Per-Axis Analysis",
        "",
        "| Axis | Oscillation | Frequency (Hz) | Damping | Phase Margin | RMSE |",
        "|------|-------------|-----------------|---------|--------------|------|",
    ])

    for axis in ["pitch", "roll", "yaw", "z"]:
        osc = oscillation.get(axis, {})
        stab = stability.get(axis, {})
        perf = performance.get(axis, {})

        if isinstance(osc, dict):
            osc_detected = "⚠️ Yes" if osc.get("oscillation_detected") else "✅ No"
            freq = f"{osc.get('dominant_frequency_hz', 0):.1f}" if osc.get('dominant_frequency_hz') else "-"
            zeta = f"{osc.get('damping_ratio', 0):.2f}" if osc.get('damping_ratio') else "-"
        else:
            osc_detected = "-"
            freq = "-"
            zeta = "-"

        pm = f"{stab.get('phase_margin_deg', 0):.0f}°" if stab.get('phase_margin_deg') else "-"
        rmse = f"{perf.get('rmse', 0):.4f}" if perf.get('rmse') else "-"

        lines.append(f"| {axis.upper()} | {osc_detected} | {freq} | {zeta} | {pm} | {rmse} |")

    lines.append("")

    # Detailed findings
    lines.extend([
        "## Detailed Findings",
        "",
    ])

    alerts = results.get("alerts", [])
    if alerts:
        lines.append("### Alerts")
        lines.append("")
        for alert in alerts:
            level = alert.get("level", "INFO")
            code = alert.get("code", "UNKNOWN")
            message = alert.get("message", "")
            axis = alert.get("axis", "")
            lines.append(f"- **[{level}]** {axis.upper()}: {message} ({code})")
        lines.append("")
    else:
        lines.append("### No Alerts")
        lines.append("")
        lines.append("All metrics within acceptable ranges.")
        lines.append("")

    # Recommendations
    lines.extend([
        "## Recommendations",
        "",
    ])

    recommendations = results.get("recommendations", [])
    if recommendations:
        for i, rec in enumerate(recommendations, 1):
            lines.append(f"{i}. {rec}")
    else:
        lines.append("No specific recommendations at this time.")
    lines.append("")

    # Technical details
    lines.extend([
        "---",
        "",
        "## Technical Details",
        "",
        "### Data Quality",
        "",
        f"- Signals recorded: {stats['num_signals']}",
        f"- Total samples: {stats['num_samples']:,}",
        f"- Estimated sample rate: {stats['sample_rate_hz']:.1f} Hz",
        f"- Maximum gap: {stats['max_gap_s']*1000:.0f} ms",
        "",
    ])

    # Write report
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")


def generate_json_report(
    results: Dict[str, Any],
    output_path: str
) -> None:
    """Generate JSON report for machine consumption.

    Args:
        results: Analysis results dictionary.
        output_path: Path to write the JSON report.
    """
    # Add metadata
    output = {
        "version": "1.0.0",
        "generated_at": datetime.now().isoformat(),
        "results": results
    }

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(
        json.dumps(output, indent=2, default=str),
        encoding="utf-8"
    )


def generate_html_report(
    data: Dict[str, Any],
    results: Dict[str, Any],
    output_path: str
) -> None:
    """Generate HTML report with embedded visualizations.

    Args:
        data: Loaded flight data.
        results: Analysis results dictionary.
        output_path: Path to write the HTML report.
    """
    # Generate markdown first
    md_path = output_path.replace(".html", "_md.md")
    generate_markdown_report(data, results, md_path)

    # Basic HTML template with the markdown embedded
    md_content = Path(md_path).read_text(encoding="utf-8")

    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Flight Analysis Report</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 20px;
        }}
        .section {{
            background: white;
            padding: 20px;
            margin-bottom: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background: #f8f9fa;
            font-weight: 600;
        }}
        .alert-critical {{
            color: #dc3545;
            font-weight: bold;
        }}
        .alert-warning {{
            color: #ffc107;
            font-weight: bold;
        }}
        .alert-info {{
            color: #17a2b8;
        }}
        .healthy {{
            color: #28a745;
        }}
        code {{
            background: #f4f4f4;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Flight Analysis Report</h1>
        <p>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>
    <div class="section">
        <pre>{md_content}</pre>
    </div>
</body>
</html>"""

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(html_template, encoding="utf-8")


def generate_comparison_report(
    flight_results: Dict[str, Dict[str, Any]],
    output_path: str
) -> None:
    """Generate comparison report for multiple flights.

    Args:
        flight_results: Dictionary of flight_id -> results.
        output_path: Path to write the comparison report.
    """
    lines = [
        "# Flight Comparison Report",
        "",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Flights compared:** {len(flight_results)}",
        "",
        "---",
        "",
        "## Summary Comparison",
        "",
        "| Flight | Health Score | Oscillating Axes | Avg RMSE |",
        "|--------|--------------|------------------|----------|",
    ]

    for flight_id, results in flight_results.items():
        health = results.get("health", {})
        score = health.get("health_score", "-")
        oscillating = results.get("oscillating_axes", "-")
        
        # Compute average RMSE
        perf = results.get("performance", {})
        rmses = [m.get("rmse", 0) for m in perf.values() if isinstance(m, dict)]
        avg_rmse = sum(rmses) / len(rmses) if rmses else 0

        lines.append(f"| {flight_id} | {score:.0f} | {oscillating} | {avg_rmse:.4f} |")

    lines.append("")

    # Parameter changes
    lines.extend([
        "## Analysis",
        "",
        "This report compares key metrics across multiple flights.",
        "Use this to track tuning changes and their effects on performance.",
        "",
    ])

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text("\n".join(lines), encoding="utf-8")
