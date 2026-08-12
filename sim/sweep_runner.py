"""Sweep runner: structured result + artifact writer (sim-arch-03).

``SweepResult`` wraps the per-variant output. ``write_sweep_artifacts`` mirrors
``RunArtifactWriter`` from sim/artifact.py, producing:
    <outdir>/results.json
    <outdir>/summary.md
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from sim import scenarios as _sc


@dataclass
class SweepRow:
    label: str
    metrics: dict[str, Any]
    outdir: str | None = None

    def to_dict(self) -> dict:
        return {"label": self.label, "metrics": self.metrics, "outdir": self.outdir}


@dataclass
class SweepResult:
    family: str  # "bias_deadzone" | "lyapunov_q" | "crm_delay" | "paired_envelope" | "sensitivity"
    scenario: str
    axis: str
    rows: list[SweepRow] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "family": self.family,
            "scenario": self.scenario,
            "axis": self.axis,
            "metadata": self.metadata,
            "rows": [r.to_dict() for r in self.rows],
        }


def write_sweep_artifacts(outdir: str | Path, result: SweepResult) -> None:
    """Write ``results.json`` and ``summary.md`` for a completed sweep result."""
    directory = Path(outdir)
    directory.mkdir(parents=True, exist_ok=True)

    # results.json
    results_path = directory / "results.json"
    results_path.write_text(json.dumps(result.to_dict(), indent=2))

    # summary.md
    lines = [
        f"# Sweep: {result.family}",
        "",
        f"**Scenario**: {result.scenario}",
        f"**Axis**: {result.axis}",
        "",
        "| variant | " + " | ".join(
            k for k in result.rows[0].metrics
        ) + " |",
        "|" + "---|" * (len(result.rows[0].metrics) + 1),
    ]
    for row in result.rows:
        cells = [row.label] + [
            _format_val(row.metrics.get(k)) for k in result.rows[0].metrics
        ]
        lines.append("| " + " | ".join(cells) + " |")

    (directory / "summary.md").write_text("\n".join(lines))


def _format_val(v: Any) -> str:
    if isinstance(v, float):
        return f"{v:.4g}"
    return str(v)


def git_sha() -> str:
    try:
        import subprocess
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            text=True, stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "unknown"
