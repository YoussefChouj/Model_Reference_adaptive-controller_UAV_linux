"""Scenario YAML tests (engine-agnostic, ADR-0014 D5 relative parameterisation)."""
from __future__ import annotations

import yaml
import pytest

from sim.scenarios_yaml import (
    MagnitudeSpec,
    Scenario,
    load_scenario,
    scenario_to_dict,
    validate_scenario,
)


def _command_at(scenario: Scenario, t: float, u_max: float = 1.0) -> dict:
    """Evaluate a scenario's command + active disturbances at time t.

    Mirrors the behaviour that ``sim/runner.py`` previously provided; inlined
    here since the runner module was deleted (ADR-0012 D1).
    """
    raw = scenario.command(t) if callable(scenario.command) else dict(scenario.command)
    command: dict[str, float] = {}
    for axis, val in raw.items():
        if isinstance(val, dict):
            command[axis] = float(val.get("value", 0.0))
        else:
            command[axis] = float(val)
    for disturbance in scenario.disturbances:
        if t >= float(disturbance["start_s"]):
            axis = str(disturbance["axis"])
            mag = disturbance["magnitude"]
            resolved = MagnitudeSpec(mag).resolve(u_max)
            command[axis] = command.get(axis, 0.0) + resolved
    return command


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


# ----------------------------------------------------------------------
# ADR-0014 D5 — relative (fraction-of-u_max) parameterisation
# ----------------------------------------------------------------------
def test_magnitude_spec_absolute_is_reference_independent():
    spec = MagnitudeSpec(0.08)
    assert not spec.is_relative
    # An absolute magnitude resolves to itself regardless of the reference.
    assert spec.resolve(0.8) == pytest.approx(0.08)
    assert spec.resolve(1e9) == pytest.approx(0.08)


def test_magnitude_spec_relative_resolves_against_u_max():
    spec = MagnitudeSpec({"value": 0.1, "unit": "u_max"})
    assert spec.is_relative
    assert spec.resolve(0.8) == pytest.approx(0.08)


def test_magnitude_spec_relative_equals_absolute_within_tolerance():
    """AC2: a relative disturbance resolves to the same magnitude as the
    pre-change absolute version (within 1%)."""
    u_max = 0.8
    relative = MagnitudeSpec({"value": 0.1, "unit": "u_max"}).resolve(u_max)
    absolute = MagnitudeSpec(0.08).resolve(u_max)
    assert abs(relative - absolute) <= 0.01 * abs(absolute)


def test_magnitude_spec_rejects_unknown_unit():
    with pytest.raises(ValueError, match="unit"):
        MagnitudeSpec({"value": 0.1, "unit": "bogus"})


def test_validation_accepts_relative_disturbance_magnitude():
    scenario = Scenario(
        name="rel", duration_s=1.0,
        disturbances=[{"start_s": 0.5, "axis": "roll",
                       "magnitude": {"value": 0.1, "unit": "u_max"}}],
    )
    assert validate_scenario(scenario) == []


def test_initial_state_rejects_rate_and_attitude_keys():
    """vx/vy/vz/phi/theta/psi/p/q/r were removed from _INITIAL_KEYS — the
    plant owns those defaults (ADR-0012 D7)."""
    scenario = Scenario(name="s", duration_s=1.0,
                        initial_state={"phi": 0.0})
    assert any("initial_state" in e and "phi" in e
               for e in validate_scenario(scenario))


def test_relative_disturbance_yaml_loads_and_runs(tmp_path):
    """A YAML scenario declaring a relative (u_max-fraction) disturbance
    loads, validates, round-trips, and projects to the equivalent absolute
    torque at run time."""
    path = tmp_path / "rel.yaml"
    path.write_text(yaml.safe_dump({
        "name": "rel", "duration_s": 1.0, "dt": 0.005,
        "command": {"z": 0.0, "roll": 0.0, "pitch": 0.0, "yaw": 0.0},
        "disturbances": [{"start_s": 0.5, "axis": "roll",
                          "magnitude": {"value": 0.1, "unit": "u_max"}}],
        "stop_conditions": [{"max_abs_phi_deg": 30}],
    }), encoding="utf-8")
    scenario = load_scenario(path)
    assert validate_scenario(scenario) == []
    # Round-trips with the magnitude preserved as a relative spec.
    back = scenario_to_dict(scenario)
    assert back["disturbances"][0]["magnitude"] == {"value": 0.1, "unit": "u_max"}
    # Projects to the equivalent absolute torque with a given u_max.
    cmd = _command_at(scenario, t=0.6, u_max=0.8)
    assert cmd["roll"] == pytest.approx(0.08)
