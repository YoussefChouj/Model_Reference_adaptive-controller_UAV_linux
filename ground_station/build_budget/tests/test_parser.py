"""Tests for the build-log parser.

Assertions are on :class:`BuildReport`'s fields, never on parser internals —
that's what the spec calls for ("assert on the gate's verdict and reported
figures, never on parsing internals").
"""
from pathlib import Path

import pytest

from ground_station.build_budget.parser import (
    BuildReport,
    parse_build_log,
    parse_build_log_text,
    BuildLogParseError,
    Warning,
    diff_warnings,
)


BUILD_OK   = Path(__file__).parent / "sample_artifacts" / "build_ok.log"
REGRESSED  = Path(__file__).parent / "sample_artifacts" / "build_regressed.log"


def _ok_report() -> BuildReport:
    return parse_build_log(BUILD_OK)


def test_extracts_program_size_line():
    r = _ok_report()
    assert r.code == 80908
    assert r.ro_data == 1492
    assert r.rw_data == 2384
    assert r.zi_data == 112736


def test_error_count_is_zero_on_clean_build():
    r = _ok_report()
    assert r.error_count == 0


def test_warning_inventory_collapses_to_unique_identities():
    """The #1267-D warning fires twice (lines 294 and 314) but has one identity."""
    r = _ok_report()
    # 8 reported warnings, but only the unique (code, text) pairs matter.
    assert len(r.warnings) == 8
    assert len(r.warning_set) == 5   # unique identity pairs


def test_each_warning_knows_its_diagnostic_code():
    r = _ok_report()
    codes = sorted({w.code for w in r.warnings})
    assert codes == ["1", "1267", "177", "186"]


def test_warning_identity_drops_line_number():
    w1 = Warning(code="1267", severity="D", file="x.h", text="Implicit physical register R0 should be defined as a variable")
    w2 = Warning(code="1267", severity="D", file="x.h", text="Implicit physical register R0 should be defined as a variable")
    w2_at_50 = Warning(code="1267", severity="D", file="x.h", text="implicit physical register R0 should be defined as a variable")
    # Same code + same text -> same identity.
    assert w1.identity() == w2.identity()
    # Text normalised only by strip+ends, not by case.
    assert w1.identity() != w2_at_50.identity()


def test_diff_warnings_returns_added_and_removed_sets():
    ok = _ok_report()
    regressed = parse_build_log(REGRESSED)
    # regressed.log has ONE new warning (#174-D); same old warnings as build_ok.
    added, removed = diff_warnings(regressed, ok.warning_set)
    assert ("#174-D", "expression has no effect") in added
    assert not removed


def test_pure_line_shift_is_not_a_new_warning():
    """The #1267-D warning changes only its line number; that's not a new identity."""
    text_a = (
        "..\\foo.h(294): warning:  #1267-D: Implicit physical register R0 should be defined as a variable\n"
        "Program Size: Code=1 RO-data=1 RW-data=1 ZI-data=1\n"
    )
    text_b = (
        "..\\foo.h(295): warning:  #1267-D: Implicit physical register R0 should be defined as a variable\n"
        "Program Size: Code=1 RO-data=1 RW-data=1 ZI-data=1\n"
    )
    a = parse_build_log_text(text_a)
    b = parse_build_log_text(text_b)
    assert a.warning_set == b.warning_set


def test_remove_one_add_one_is_regression_not_unchanged():
    """Build that removes one warning and adds a different one is a regression."""
    base_text = (
        "..\\foo.h(10): warning:  #177-D: function \"a\" was declared but never referenced\n"
        "Program Size: Code=1 RO-data=1 RW-data=1 ZI-data=1\n"
        '"..\\OBJ\\JX_FLY.axf" - 0 Error(s), 1 Warning(s).\n'
    )
    current_text = (
        "..\\foo.h(10): warning:  #174-D: expression has no effect\n"
        "Program Size: Code=1 RO-data=1 RW-data=1 ZI-data=1\n"
        '"..\\OBJ\\JX_FLY.axf" - 0 Error(s), 1 Warning(s).\n'
    )
    base = parse_build_log_text(base_text).warning_set
    current = parse_build_log_text(current_text)
    added, removed = diff_warnings(current, base)
    assert added and removed
    assert ("#174-D", "expression has no effect") in added
    assert any("\"a\"" in t for _, t in removed)


def test_malformed_log_raises():
    """A log without a Program Size line is a parse failure (not silent zero)."""
    with pytest.raises(BuildLogParseError, match="Program Size"):
        parse_build_log_text("garbage\nmore garbage\n")


def test_blank_log_raises():
    with pytest.raises(BuildLogParseError):
        parse_build_log_text("")


def test_regressed_log_records_new_warning_identity():
    r = parse_build_log(REGRESSED)
    # Code grew (80908 -> 82000) and ZI-data grew (112736 -> 125000).
    assert r.code == 82000
    assert r.zi_data == 125000
    # New warning identity present.
    assert ("#174-D", "expression has no effect") in r.warning_set
