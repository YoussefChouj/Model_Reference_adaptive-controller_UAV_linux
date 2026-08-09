"""Scenario YAML tests for spec 4c."""
from __future__ import annotations

import yaml
import pytest

from sim.scenarios_yaml import Scenario, load_scenario, scenario_to_dict, validate_scenario


@pytest.mark.parametrize("name", ["hover", "step_roll"])
def test_load_validate_round_trip(name, tmp_path):
    scenario = load_scenario(f"scenarios/{name}.yaml")
    assert validate_scenario(scenario) == []
    path = tmp_path / f"{name}.yaml"
    path.write_text(yaml.safe_dump(scenario_to_dict(scenario)), encoding="utf-8")
    assert scenario_to_dict(load_scenario(path)) == scenario_to_dict(scenario)


def test_missing_required_field_is_clear(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("name: bad\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duration_s"):
        load_scenario(path)


def test_validation_rejects_bad_values():
    scenario = Scenario(name="", duration_s=-1.0)
    errors = validate_scenario(scenario)
    assert any("name" in error for error in errors)
    assert any("duration_s" in error for error in errors)
