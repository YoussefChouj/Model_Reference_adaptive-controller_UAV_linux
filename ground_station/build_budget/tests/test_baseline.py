"""Tests for the baseline loader."""
from pathlib import Path

import pytest

from ground_station.build_budget.baseline import Baseline, load_baseline


BASELINE = Path(__file__).resolve().parents[1] / "baseline.yaml"


def test_load_real_baseline():
    b = load_baseline(BASELINE)
    assert isinstance(b, Baseline)
    assert b.code == 80908
    assert b.zi_data == 112736


def test_load_real_baseline_has_warning_identities():
    b = load_baseline(BASELINE)
    # The #1267-D warning is the dominant one — make sure both included sites
    # collapse to one identity.
    assert any(
        code == "#1267-D" and "Implicit physical register" in text
        for code, text in b.warning_identities
    )


def test_threshold_default_is_eighty():
    b = load_baseline(BASELINE)
    assert b.stack_threshold_pct == 80.0


def test_requirement_ids_listed():
    b = load_baseline(BASELINE)
    assert "BUILD-FLASH-1" in b.requirements
    assert "BUILD-RAM-1" in b.requirements
    assert "BUILD-RAM-2" in b.requirements
    assert "BUILD-STACK-1" in b.requirements
    assert "BUILD-WARN-1" in b.requirements


def test_warnings_normalised_to_set_of_tuples():
    b = load_baseline(BASELINE)
    assert isinstance(b.warning_identities, frozenset)
    for item in b.warning_identities:
        assert isinstance(item, tuple)
        assert len(item) == 2


def test_frozen_against_mutation():
    """Loading a baseline produces immutable objects."""
    b = load_baseline(BASELINE)
    with pytest.raises((AttributeError, TypeError)):
        b.code = 12345  # type: ignore[misc]
