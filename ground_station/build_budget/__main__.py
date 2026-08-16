"""CLI:

    python -m ground_station.build_budget
        --build-log OBJ\\flash_build.log
        --project USER\\JX_FLY.uvprojx
        --baseline ground_station\\build_budget\\baseline.yaml
        [--stack-readings-csv tasks.csv]
        [--livewatch-elf OBJ\\JX_FLY.axf]
        [--stack-threshold-pct 80]
        [--output-json report.json]

Exit code: 0 on pass (or on graceful skip), 1 on any budget regression.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .gate import run as run_gate


def main(argv: list[str] | None = None) -> int:
    repo = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(
        prog="build_budget",
        description=(
            "Build-budget gate: flash, RAM, stack and warning regression.\n"
            "Reads artifacts the build already produces; never invokes the build.\n"
            "Windows-only because the upstream ARMCC linker artifacts are."
        ),
    )
    parser.add_argument(
        "--build-log", type=Path,
        default=repo / "OBJ" / "flash_build.log",
        help="Path to the UV4/ar link build log (default: OBJ/flash_build.log).",
    )
    parser.add_argument(
        "--project", type=Path,
        default=repo / "USER" / "JX_FLY.uvprojx",
        help="Path to the Keil project file (default: USER/JX_FLY.uvprojx).",
    )
    parser.add_argument(
        "--baseline", type=Path,
        default=Path(__file__).parent / "baseline.yaml",
        help="Path to the checked-in baseline YAML.",
    )
    parser.add_argument(
        "--stack-readings-csv", type=Path, default=None,
        help="CSV with task,hwm_words,alloc_words rows for the stack check.",
    )
    parser.add_argument(
        "--livewatch-elf", type=Path, default=None,
        help="firmware ELF (auto-detects firmware/build/JX_FLY.elf or OBJ/JX_FLY.axf) — enables live HWM read over the read-only probe.",
    )
    parser.add_argument(
        "--stack-threshold-pct", type=float, default=None,
        help="Override the per-task HWM threshold (default: from baseline).",
    )
    parser.add_argument(
        "--output-json", type=Path, default=None,
        help="Path to write the machine-readable JSON report.",
    )
    args = parser.parse_args(argv)

    result = run_gate(
        build_log=args.build_log,
        project_xml=args.project,
        baseline_yaml=args.baseline,
        stack_readings_csv=args.stack_readings_csv,
        stack_threshold_pct=args.stack_threshold_pct,
        livewatch_elf=args.livewatch_elf,
    )

    print(result.report())
    if args.output_json:
        Path(args.output_json).write_text(
            json.dumps(result.to_jsonable(), indent=2, default=str),
            encoding="utf-8",
        )
        print(f"[build budget] wrote {args.output_json}")

    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
