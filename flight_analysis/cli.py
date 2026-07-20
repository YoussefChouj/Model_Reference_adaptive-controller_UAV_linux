"""Command-line interface for flight analysis."""

import argparse
import sys
from pathlib import Path
from typing import Optional

from flight_analysis import __version__


def analyze_flight(
    csv_path: str,
    output_dir: Optional[str] = None,
    frame_type: str = "quad",
    verbose: bool = False
) -> int:
    """Analyze a flight log and generate reports.

    Args:
        csv_path: Path to flight CSV file.
        output_dir: Output directory for reports.
        frame_type: Frame type ('quad', 'hex', 'custom').
        verbose: Enable verbose output.

    Returns:
        Exit code (0 for success).
    """
    from flight_analysis.core.loader import load_flight_csv
    from flight_analysis.stability.oscillation import analyze_axis_oscillation
    from flight_analysis.stability.margins import analyze_stability_margins
    from flight_analysis.correlation.param_map import (
        compute_tracking_metrics,
        compute_control_effort_metrics,
        compute_authority_metrics,
        extract_mrac_parameters
    )
    from flight_analysis.diagnostics.alerts import (
        generate_expert_alerts,
        summarize_flight_health
    )
    from flight_analysis.diagnostics.reports import (
        generate_markdown_report,
        generate_json_report,
        compute_summary_statistics
    )
    from flight_analysis.frames import get_frame

    csv_path = Path(csv_path)
    if not csv_path.exists():
        print(f"Error: File not found: {csv_path}")
        return 1

    if verbose:
        print(f"Loading flight data from {csv_path}...")

    # Load data
    data = load_flight_csv(str(csv_path))
    if not data:
        print("Error: No data loaded from CSV")
        return 1

    if verbose:
        print(f"Loaded {len(data)} signals")

    # Get frame configuration
    frame = get_frame(frame_type)
    if verbose:
        print(f"Using {frame_type} frame configuration")

    # Analyze oscillation
    if verbose:
        print("Analyzing oscillation...")

    oscillation_results = {}
    axes = ["pitch", "roll", "yaw", "z"]
    for axis in axes:
        result = analyze_axis_oscillation(data, axis)
        oscillation_results[axis] = result
        if verbose and result.get("oscillation_detected"):
            print(f"  {axis}: oscillation at {result.get('dominant_frequency_hz', 0):.1f} Hz")

    # Analyze stability
    if verbose:
        print("Analyzing stability margins...")

    stability_margins = analyze_stability_margins(data, axes)

    # Compute performance metrics
    if verbose:
        print("Computing performance metrics...")

    tracking_metrics = compute_tracking_metrics(data)
    control_metrics = compute_control_effort_metrics(data)
    authority_metrics = compute_authority_metrics(data)

    # Extract parameters
    mrac_params = extract_mrac_parameters(data)

    # Generate health summary
    health = summarize_flight_health(oscillation_results, stability_margins)

    # Generate alerts
    alerts = generate_expert_alerts(oscillation_results, stability_margins, tracking_metrics)

    if verbose:
        print(f"\nHealth Score: {health['health_score']:.0f}/100 ({health['status']})")
        print(f"Alerts: {len(alerts)}")

    # Compile results
    results = {
        "oscillation": oscillation_results,
        "stability": stability_margins,
        "performance": tracking_metrics,
        "control_effort": control_metrics,
        "authority": authority_metrics,
        "parameters": mrac_params,
        "health": health,
        "alerts": [a.to_dict() for a in alerts],
    }

    # Generate recommendations
    recommendations = []
    for alert in alerts:
        if alert.level in ["CRITICAL", "WARNING"]:
            for rec in alert.recommendations[:2]:  # Top 2 per alert
                recommendations.append(f"{alert.axis.upper()}: {rec}")
    results["recommendations"] = recommendations[:10]  # Max 10

    # Output directory
    if output_dir:
        out_dir = Path(output_dir)
    else:
        # Create output in same directory as CSV
        out_dir = csv_path.parent / f"{csv_path.stem}_analysis"

    out_dir.mkdir(parents=True, exist_ok=True)

    # Generate reports
    if verbose:
        print(f"\nGenerating reports in {out_dir}...")

    # Markdown report
    md_path = out_dir / "report.md"
    generate_markdown_report(data, results, str(md_path))
    if verbose:
        print(f"  Created: {md_path.name}")

    # JSON report
    json_path = out_dir / "analysis.json"
    generate_json_report(results, str(json_path))
    if verbose:
        print(f"  Created: {json_path.name}")

    # Summary statistics
    stats = compute_summary_statistics(data)
    print(f"\n{'='*50}")
    print("FLIGHT ANALYSIS SUMMARY")
    print(f"{'='*50}")
    print(f"Health Score: {health['health_score']:.0f}/100 ({health['status']})")
    print(f"Duration: {stats['duration_s']:.1f} seconds")
    print(f"Samples: {stats['num_samples']:,}")
    print(f"Oscillating axes: {health['oscillating_axes']}/{health['total_axes']}")
    print(f"Critical alerts: {health['critical_alerts']}")
    print(f"{'='*50}")

    if recommendations:
        print("\nTop Recommendations:")
        for i, rec in enumerate(recommendations[:5], 1):
            print(f"  {i}. {rec}")

    print(f"\nFull report: {md_path}")
    print(f"JSON data: {json_path}")

    return 0


def compare_flights(
    flight_paths: list,
    output_path: Optional[str] = None
) -> int:
    """Compare multiple flight logs.

    Args:
        flight_paths: List of flight CSV paths.
        output_path: Output path for comparison report.

    Returns:
        Exit code (0 for success).
    """
    from flight_analysis.core.loader import load_flight_csv
    from flight_analysis.stability.oscillation import analyze_axis_oscillation
    from flight_analysis.diagnostics.reports import generate_comparison_report

    flight_results = {}

    for path in flight_paths:
        path = Path(path)
        if not path.exists():
            print(f"Warning: Skipping {path} (not found)")
            continue

        print(f"Analyzing {path.name}...")
        data = load_flight_csv(str(path))

        oscillation_results = {}
        for axis in ["pitch", "roll", "yaw", "z"]:
            oscillation_results[axis] = analyze_axis_oscillation(data, axis)

        flight_results[path.stem] = {
            "oscillation": oscillation_results,
            "oscillating_axes": sum(
                1 for r in oscillation_results.values()
                if r.get("oscillation_detected")
            )
        }

    if output_path:
        generate_comparison_report(flight_results, output_path)
        print(f"\nComparison report: {output_path}")

    return 0


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Flight Analysis Framework - UAV telemetry analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s analyze ground_station/logs/flight_1784538359.csv
  %(prog)s analyze flight.csv --frame quad --verbose
  %(prog)s compare flight1.csv flight2.csv --output comparison.md
        """
    )

    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze a flight log")
    analyze_parser.add_argument("csv", help="Path to flight CSV file")
    analyze_parser.add_argument("-o", "--output", help="Output directory")
    analyze_parser.add_argument("-f", "--frame", default="quad",
                              choices=["quad", "hex", "custom"],
                              help="Frame type (default: quad)")
    analyze_parser.add_argument("-v", "--verbose", action="store_true",
                              help="Verbose output")

    # Compare command
    compare_parser = subparsers.add_parser("compare", help="Compare multiple flights")
    compare_parser.add_argument("flights", nargs="+", help="Flight CSV files")
    compare_parser.add_argument("-o", "--output", help="Output report path")

    args = parser.parse_args()

    if args.command == "analyze":
        return analyze_flight(
            args.csv,
            output_dir=args.output,
            frame_type=args.frame,
            verbose=args.verbose
        )
    elif args.command == "compare":
        return compare_flights(args.flights, output_path=args.output)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
