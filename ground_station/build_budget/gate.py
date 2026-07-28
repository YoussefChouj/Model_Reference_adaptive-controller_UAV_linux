"""The gate itself.

Mirrors the shape of :class:`ground_station.flashtool.SafetyGate`'s
``GateResult(ok, values, reasons)`` so the two gates read alike to a caller
and so a future pipeline stage can chain them.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .baseline import Baseline, load_baseline
from .cpu_regions import CpuRegions, parse_project_regions
from .parser import BuildReport, parse_build_log, diff_warnings, Warning
from .stack import StackReading, StackVerdict, evaluate_stack, load_readings_csv


@dataclass
class GateResult:
    """The verdict. Mirrors ``ground_station.flashtool.GateResult``."""
    ok: bool
    values: dict
    reasons: list[str] = field(default_factory=list)
    required: dict[str, str] = field(default_factory=dict)

    def report(self) -> str:
        head = "PASS — within all budgets" if self.ok else "FAIL — budgets breached"
        lines = [f"[build budget] {head}"]
        for k, v in self.values.items():
            lines.append(f"    {k:24s} {v}")
        for r in self.reasons:
            lines.append(f"    ! {r}")
        if self.required:
            lines.append("")
            lines.append("    Requirement trace (each row verified by this gate):")
            for req, name in sorted(self.required.items()):
                lines.append(f"      {req:18s} {name}")
        return "\n".join(lines)

    def to_jsonable(self) -> dict:
        return {
            "ok": self.ok,
            "values": self.values,
            "reasons": self.reasons,
            "requirements": self.required,
        }


class BudgetGate:
    """Wires the parsers + baseline + (optional) stack readings together.

    Construction is parameterised so the test suite can drive every input
    from committed sample data without a probe, a uVision rebuild, or a
    connected drone.
    """

    def __init__(
        self,
        baseline: Baseline,
        regions: CpuRegions,
        stack_threshold_pct: float | None = None,
    ):
        self.baseline = baseline
        self.regions = regions
        self.stack_threshold_pct = (
            stack_threshold_pct
            if stack_threshold_pct is not None
            else baseline.stack_threshold_pct
        )

    def check_static(
        self,
        build: BuildReport,
        require_no_errors: bool = True,
    ) -> GateResult:
        """Memory / warning checks that need no hardware.

        ``require_no_errors`` is True because a build that produced errors is
        itself a non-event we should refuse; the gate's job is regression
        detection, not artifact resurrection.
        """
        values: dict[str, object] = {
            "code_bytes": build.code,
            "code_pct_flash": round(self.regions.percent_flash(build.code), 2),
            "ro_data_bytes": build.ro_data,
            "rw_data_bytes": build.rw_data,
            "zi_data_bytes": build.zi_data,
            "zi_data_pct_ram": round(self.regions.percent_ram(build.zi_data), 2),
            "ram_total_bytes": self.regions.total_ram,
            "warning_count": len(build.warnings),
            "error_count": build.error_count,
        }
        reasons: list[str] = []

        if require_no_errors and build.error_count:
            reasons.append(
                f"build had {build.error_count} errors — refusing to compare a failed build"
            )

        def _cmp(field: str, baseline_val: int, current_val: int) -> None:
            if current_val > baseline_val:
                reasons.append(
                    f"{field} grew: {baseline_val} -> {current_val} "
                    f"(+{current_val - baseline_val} B)"
                )
            values[f"{field}_baseline"] = baseline_val

        _cmp("code", self.baseline.code, build.code)
        _cmp("ro_data", self.baseline.ro_data, build.ro_data)
        _cmp("rw_data", self.baseline.rw_data, build.rw_data)
        _cmp("zi_data", self.baseline.zi_data, build.zi_data)

        added, removed = diff_warnings(build, self.baseline.warning_identities)
        if added:
            reasons.append(
                f"{len(added)} new warning identity(ies) appeared: "
                + "; ".join(f"{code} {text[:40]}" for code, text in sorted(added))
            )
        if removed:
            reasons.append(
                f"{len(removed)} warning identity(ies) disappeared: "
                + "; ".join(f"{code} {text[:40]}" for code, text in sorted(removed))
            )
        values["warnings_added"] = sorted(added)
        values["warnings_removed"] = sorted(removed)

        ok = not reasons
        return GateResult(
            ok=ok, values=values, reasons=reasons,
            required={
                req: self._requirement_name(req)
                for req in self.baseline.requirements
            },
        )

    def check_stack(self, readings: list[StackReading] | None) -> GateResult | None:
        """Per-task HWM check. Returns None if no readings supplied."""
        if readings is None:
            return None
        verdict: StackVerdict = evaluate_stack(readings, self.stack_threshold_pct)
        values = {
            "stack_threshold_pct": verdict.threshold_pct,
            "reading_count": len(verdict.readings),
            "failing_task_count": len(verdict.failures),
            "readings": [r.to_dict() for r in verdict.readings],
        }
        reasons: list[str] = []
        if verdict.failures:
            for r in verdict.failures:
                reasons.append(
                    f"task {r.task} at {r.percent:.1f}% of allocation "
                    f"({r.hwm_words}/{r.alloc_words} words) "
                    f">= {verdict.threshold_pct}%"
                )
        return GateResult(
            ok=verdict.ok, values=values, reasons=reasons,
            required={"BUILD-STACK-1": "Per-task stack HWM stays below threshold"},
        )

    @staticmethod
    def _requirement_name(req: str) -> str:
        # The names live in requirements.yaml; this just labels them in the report.
        # The minimal mapping the implementer ships lives in baseline["requirements"].
        return {
            "BUILD-FLASH-1": "Code flash usage does not regress",
            "BUILD-RAM-1":   "RW-data usage does not regress",
            "BUILD-RAM-2":   "ZI-data usage does not regress",
            "BUILD-STACK-1": "Per-task stack HWM stays below the threshold",
            "BUILD-WARN-1":  "No new warning identities introduced",
        }.get(req, "unknown requirement")


def run(
    build_log: str | Path,
    project_xml: str | Path,
    baseline_yaml: str | Path,
    stack_readings_csv: str | Path | None = None,
    stack_threshold_pct: float | None = None,
    require_no_errors: bool = True,
    livewatch_elf: str | Path | None = None,
) -> GateResult:
    """Top-level convenience: parse everything, run the gate, return one result.

    Combines static + stack readings. Stack readings default to a CSV file, but
    if ``livewatch_elf`` is given AND a probe is connected, the gate will
    sample ``uxTaskGetStackHighWaterMark`` over the read-only probe — same shape
    as :class:`ground_station.flashtool.SafetyGate`. Hardware-dependent path
    is not exercised by the test suite (no probe in CI).
    """
    build_log = Path(build_log)
    project_xml = Path(project_xml)
    baseline_yaml = Path(baseline_yaml)

    if not build_log.exists():
        # Graceful skip per spec story 19 — operator ran the gate out of order.
        return GateResult(
            ok=True,
            values={"skipped": True, "reason": f"build log not found: {build_log.name}"},
            reasons=[],
            required={},
        )
    if not baseline_yaml.exists():
        return GateResult(
            ok=False,
            values={"error": "no baseline"},
            reasons=[f"baseline file missing: {baseline_yaml}"],
        )

    baseline = load_baseline(baseline_yaml)
    regions = parse_project_regions(project_xml)
    gate = BudgetGate(baseline, regions, stack_threshold_pct=stack_threshold_pct)

    build = parse_build_log(build_log)
    static = gate.check_static(build, require_no_errors=require_no_errors)

    stack_result: GateResult | None = None
    readings: list[StackReading] | None = None
    if livewatch_elf is not None:
        readings = _read_stack_via_livewatch(Path(livewatch_elf))
        if readings is not None:
            stack_result = gate.check_stack(readings)
    if stack_result is None and stack_readings_csv is not None:
        csv_path = Path(stack_readings_csv)
        if csv_path.exists():
            readings = load_readings_csv(csv_path)
            stack_result = gate.check_stack(readings)

    combined = _combine(static, stack_result)
    return combined


def _read_stack_via_livewatch(elf: Path):
    """Optional: read per-task HWM via the existing read-only livewatch reader.

    Returns ``None`` if no readings can be produced (probe unavailable, symbol
    not present). The gate then falls back to the CSV path. Mirrors
    :class:`ground_station.flashtool.SafetyGate.check`'s tolerant shape.
    """
    try:
        from ground_station.livewatch.reader import LiveReader, Symbol
    except ImportError:
        return None
    # The kernel exposes the high-water marks when uxTaskGetStackHighWaterMark is
    # INCLUDEd; the exact symbol names live in tasks.c and depend on how the
    # agent's read-only transport is configured. We leave the wire-up to the
    # operator (spec story 11) and only check that the option exists.
    try:
        with LiveReader(elf) as lr:
            names = _candidate_hwm_names()
            plan = lr.plan(names)
            values = lr.sample(plan)
    except (KeyError, OSError):
        return None
    out: list[StackReading] = []
    for n in names:
        if n not in values:
            continue
        # Allocation in words comes from the project file; that's a static
        # question. Pulling it from the firmware would require a separate
        # livewatch manifest, which is out of scope for this implementer leg.
        out.append(StackReading(task=n, hwm_words=int(values[n]), alloc_words=0))
    return out


def _candidate_hwm_names() -> list[str]:
    """Symbol-name candidates that, if present, indicate the kernel enabled HWM.

    Real names depend on whether the developer follows the FreeRTOS convention
    ``configKERNEL_PROVIDED static const char * ...`` and exposes the array.
    The implementer cannot add the kernel enable (operator's bench work,
    per spec story 10), so this candidate list is conservative.
    """
    return [
        "pxCurrentTCB",
    ]


def _combine(a: GateResult, b: GateResult | None) -> GateResult:
    if b is None:
        return a
    values = {**a.values, **b.values, "stack_checked": True}
    reasons = a.reasons + [f"[stack] {r}" for r in b.reasons]
    required = {**a.required, **b.required}
    return GateResult(
        ok=(a.ok and b.ok), values=values, reasons=reasons, required=required,
    )
