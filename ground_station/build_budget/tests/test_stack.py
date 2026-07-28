"""Tests for the per-task HWM threshold logic.

Threshold logic is fed injected readings; spec story 41 says tests assert on
the verdict, not on the threshold's internal arithmetic.
"""
import pytest

from ground_station.build_budget.stack import (
    StackReading, evaluate_stack, load_readings_csv,
)
from pathlib import Path


def _r(task, hwm, alloc):
    return StackReading(task=task, hwm_words=hwm, alloc_words=alloc)


def test_below_threshold_all_pass():
    v = evaluate_stack([_r("Send_Task", 90, 130)], threshold_pct=80.0)
    # 90 / 130 = 69.2 %  -> under 80 -> pass.
    assert v.ok
    assert not v.failures


def test_at_threshold_fails():
    """Exactly 80.0 % crosses (>= 80 is the spec's threshold)."""
    v = evaluate_stack([_r("Send_Task", 80, 100)], threshold_pct=80.0)
    assert not v.ok
    assert len(v.failures) == 1
    assert v.failures[0].task == "Send_Task"


def test_one_task_over_one_under_yields_failure():
    v = evaluate_stack(
        [_r("Send_Task", 50, 100), _r("Stabilizer_Task", 90, 100)],
        threshold_pct=80.0,
    )
    assert not v.ok
    assert [f.task for f in v.failures] == ["Stabilizer_Task"]


def test_empty_readings_pass():
    v = evaluate_stack([], threshold_pct=80.0)
    assert v.ok


def test_default_threshold_is_80_percent():
    v = evaluate_stack([_r("Send_Task", 81, 100)])  # 81%, no threshold arg
    assert not v.ok
    assert v.threshold_pct == 80.0


def test_overrides_threshold_from_baseline():
    """The gate passes the per-baseline threshold through."""
    v = evaluate_stack([_r("Send_Task", 70, 100)], threshold_pct=60.0)
    assert not v.ok  # 70% > 60%


def test_zero_allocation_does_not_crash():
    """Spec story: a misconfigured manifest rows with alloc=0 must fail loud, not divide-by-zero."""
    v = evaluate_stack([_r("Send_Task", 50, 0)], threshold_pct=80.0)
    # percent is infinite, so >= 80% is True.
    assert not v.ok


def test_csv_loader_round_trip(tmp_path: Path):
    csv_path = tmp_path / "tasks.csv"
    csv_path.write_text(
        "task,hwm_words,alloc_words\n"
        "Send_Task,90,130\n"
        "Stabilizer_Task,80,100\n",
        encoding="utf-8",
    )
    rows = load_readings_csv(csv_path)
    assert [r.task for r in rows] == ["Send_Task", "Stabilizer_Task"]
    assert rows[0].percent == pytest.approx(69.23, abs=0.01)


def test_csv_loader_handles_no_header(tmp_path: Path):
    csv_path = tmp_path / "tasks.csv"
    csv_path.write_text("Send_Task,90,130\n", encoding="utf-8")
    rows = load_readings_csv(csv_path)
    assert rows[0].task == "Send_Task"


def test_csv_loader_skips_blank_lines(tmp_path: Path):
    csv_path = tmp_path / "tasks.csv"
    csv_path.write_text(
        "task,hwm_words,alloc_words\n\nSend_Task,90,130\n\n",
        encoding="utf-8",
    )
    rows = load_readings_csv(csv_path)
    assert len(rows) == 1
