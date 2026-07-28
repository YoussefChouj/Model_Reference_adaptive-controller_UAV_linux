"""End-to-end gate tests with injected readings + committed sample artifacts.

Assertions stay on :class:`GateResult`'s verdict and reported fields. Tests
never invoke a real build or read a probe.
"""
from pathlib import Path

import pytest

from ground_station.build_budget.baseline import load_baseline
from ground_station.build_budget.cpu_regions import parse_project_regions
from ground_station.build_budget.gate import BudgetGate, GateResult, run
from ground_station.build_budget.parser import parse_build_log
from ground_station.build_budget.stack import StackReading


SAMPLES = Path(__file__).parent / "sample_artifacts"
BUILD_OK  = SAMPLES / "build_ok.log"
REGRESSED = SAMPLES / "build_regressed.log"
PROJECT   = SAMPLES / "JX_FLY_cpu.xml"


def _gate_with_baseline(threshold: float = 80.0) -> BudgetGate:
    baseline = load_baseline(BASELINE_PATH := Path(__file__).resolve().parents[1] / "baseline.yaml")
    regions = parse_project_regions(PROJECT)
    return BudgetGate(baseline, regions, stack_threshold_pct=threshold)


def test_passes_against_baseline_build_log():
    gate = _gate_with_baseline()
    r = gate.check_static(parse_build_log(BUILD_OK))
    assert r.ok
    assert "FAIL" not in r.report()


def test_regression_log_fails_on_code_size():
    gate = _gate_with_baseline()
    r = gate.check_static(parse_build_log(REGRESSED))
    assert not r.ok
    assert any("code" in x for x in r.reasons)


def test_regression_log_fails_on_zi_data():
    gate = _gate_with_baseline()
    r = gate.check_static(parse_build_log(REGRESSED))
    assert any("zi_data" in x for x in r.reasons)


def test_regression_log_fails_on_new_warning():
    gate = _gate_with_baseline()
    r = gate.check_static(parse_build_log(REGRESSED))
    assert any("new warning" in x.lower() for x in r.reasons)


def test_removed_warning_reports_loud():
    """A build that loses a warning does not silently mask the dedup count."""
    text = (
        "..\\foo.h(10): warning:  #1267-D: Implicit physical register R0 should be defined as a variable\n"
        "Program Size: Code=80000 RO-data=1492 RW-data=2384 ZI-data=110000\n"
        '"..\\OBJ\\JX_FLY.axf" - 0 Error(s), 1 Warning(s).\n'
    )
    from ground_station.build_budget.parser import parse_build_log_text
    gate = _gate_with_baseline()
    r = gate.check_static(parse_build_log_text(text))
    # No regression on sizes (below baseline) but a warning vanished:
    assert any("disappeared" in x.lower() for x in r.reasons)


def test_stack_pass_under_threshold():
    gate = _gate_with_baseline()
    r = gate.check_stack([StackReading("Send_Task", 90, 130)])
    assert r is not None
    assert r.ok


def test_stack_fail_above_threshold():
    gate = _gate_with_baseline()
    r = gate.check_stack([StackReading("Send_Task", 100, 100)])
    assert r is not None
    assert not r.ok
    assert any("Send_Task" in x for x in r.reasons)


def test_gate_run_skips_cleanly_when_build_log_absent(tmp_path: Path):
    """Spec story 19: missing build log is a graceful skip, not an error."""
    fake_log = tmp_path / "does_not_exist.log"
    r = run(
        build_log=fake_log,
        project_xml=PROJECT,
        baseline_yaml=Path(__file__).resolve().parents[1] / "baseline.yaml",
    )
    assert r.ok
    assert "skipped" in r.values


def test_gate_run_fails_when_regressed_build_log(tmp_path: Path):
    """End-to-end with the regressed log; gate must fail non-zero."""
    # Use a copy of REGRESSED in tmp_path so the run does not depend on
    # `run`'s default log path.
    from shutil import copy2
    log_copy = tmp_path / "regressed.log"
    copy2(REGRESSED, log_copy)
    r = run(
        build_log=log_copy,
        project_xml=PROJECT,
        baseline_yaml=Path(__file__).resolve().parents[1] / "baseline.yaml",
    )
    assert not r.ok


def test_gate_run_passes_on_baseline_build():
    from shutil import copy2
    log_copy = Path(__file__).parent / "_tmp_ok.log"
    copy2(BUILD_OK, log_copy)
    try:
        r = run(
            build_log=log_copy,
            project_xml=PROJECT,
            baseline_yaml=Path(__file__).resolve().parents[1] / "baseline.yaml",
        )
        assert r.ok
    finally:
        log_copy.unlink(missing_ok=True)


def test_gate_run_rejects_missing_baseline(tmp_path: Path):
    """No baseline file = hard failure (not a skip), because the gate cannot
    guarantee anything without one."""
    r = run(
        build_log=BUILD_OK,
        project_xml=PROJECT,
        baseline_yaml=tmp_path / "no-such-baseline.yaml",
    )
    assert not r.ok
    assert "baseline" in str(r.values.get("error", ""))


def test_report_includes_requirement_trace():
    gate = _gate_with_baseline()
    r = gate.check_static(parse_build_log(BUILD_OK))
    text = r.report()
    assert "BUILD-FLASH-1" in text
    assert "BUILD-RAM-2" in text


def test_stack_check_returns_none_when_no_readings():
    gate = _gate_with_baseline()
    assert gate.check_stack(None) is None
