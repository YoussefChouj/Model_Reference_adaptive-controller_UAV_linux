"""Build-budget gate.

Sibling stage of :mod:`ground_station.flashtool`. Parses the artifacts a build
already produces — the UV4/armlink build log and ``OBJ/JX_FLY.map`` — to
record flash / RAM / warning usage, compare them against a checked-in baseline
in ``baseline.yaml``, and optionally read per-task stack high-water marks over
the existing read-only :mod:`ground_station.livewatch` probe.

The gate never writes the baseline. Raising a budget is a deliberate, reviewed
edit to that file. The gate can be re-run against any stored log; it does not
invoke the build.

Public CLI:

    python -m ground_station.build_budget --build-log OBJ\\flash_build.log \\
        --baseline baseline.yaml --stack-readings-csv tasks.csv
"""
from __future__ import annotations

from .gate import GateResult, BudgetGate, run
from .parser import parse_build_log, Warning
from .baseline import Baseline

__all__ = ["GateResult", "BudgetGate", "run", "parse_build_log", "Warning", "Baseline"]
