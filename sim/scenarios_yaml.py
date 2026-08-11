"""YAML experiment scenarios for the plant-agnostic runner."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


# Plants default attitude/rates/velocities from the Airframe (level, at
# rest, at source-condition), so only the position + motor pre-load are
# declarable. ADR-0012 D7: the analytic and MuJoCo plants own these defaults.
_INITIAL_KEYS = {
    "x", "y", "z", "motor_thrust",
}
_COMMAND_KEYS = {"z", "roll", "pitch", "yaw"}
_STOP_KEYS = {"max_abs_phi_deg", "min_z_m"}
# Magnitude fields that accept an ADR-0014 D5 relative ``{value, unit}`` spec
# (e.g. a disturbance declared as a fraction of ``u_max``).
_RELATIVE_KEYS = {"magnitude"}


class MagnitudeSpec:
    """A magnitude that is either absolute or a fraction of a reference scale.

    ADR-0014 D5 relative parameterisation: scenarios are declared in relative
    magnitudes (fractions of ``u_max`` torque authority, ``J`` inertia, etc.)
    so the same scenario transfers across airframes/binaries without
    re-tuning. Two accepted forms:

      * a plain number -> absolute magnitude (unit-less torque/force/N).
      * a mapping ``{"value": 0.1, "unit": "u_max"}`` -> resolved to
        ``value * reference`` by :meth:`resolve`; ``unit="absolute"`` keeps
        the value unchanged (explicit absolute).

    ``unit`` is one of ``"absolute"`` or ``"u_max"``; unknown units are a
    clear error rather than a silent kwarg.
    """

    __slots__ = ("value", "unit")

    def __init__(self, raw: Any):
        if isinstance(raw, (int, float)):
            self.value = float(raw)
            self.unit = "absolute"
            return
        if isinstance(raw, dict):
            try:
                self.value = float(raw["value"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(
                    f"MagnitudeSpec requires a numeric 'value', got {raw!r}"
                ) from exc
            self.unit = str(raw.get("unit", "absolute"))
            if self.unit not in ("absolute", "u_max"):
                raise ValueError(
                    f"unknown MagnitudeSpec unit {self.unit!r}; use "
                    f"'absolute' or 'u_max'"
                )
            return
        raise ValueError(
            f"MagnitudeSpec must be a number or {{value, unit}} mapping, "
            f"got {raw!r}"
        )

    @property
    def is_relative(self) -> bool:
        return self.unit != "absolute"

    def resolve(self, reference: float) -> float:
        """Return the absolute magnitude for reference scale ``reference``.

        ``reference`` is e.g. ``u_max`` (the axis torque authority); a
        relative spec resolves to ``value * reference``. Absolute specs
        return ``value`` unchanged.
        """
        return self.value * reference if self.is_relative else self.value

    def to_yaml(self) -> Any:
        """Return a YAML-safe form (number for absolute, mapping for relative)."""
        return {"value": self.value, "unit": self.unit} if self.is_relative else self.value


class Command(dict[str, Any]):
    """Command mapping that can also be evaluated at simulation time."""

    def __call__(self, t: float) -> dict[str, float]:
        values: dict[str, float] = {}
        for axis in _COMMAND_KEYS:
            raw = self.get(axis, 0.0)
            if isinstance(raw, dict):
                start_s = float(raw.get("start_s", 0.0))
                values[axis] = float(raw.get("value", 0.0)) if t >= start_s else 0.0
            else:
                values[axis] = float(raw)
        return values


@dataclass
class Scenario:
    """Declarative inputs for one deterministic experiment."""

    name: str
    duration_s: float
    dt: float = 0.005
    initial_state: dict[str, Any] = field(default_factory=dict)
    command: Command = field(default_factory=Command)
    disturbances: list[dict[str, Any]] = field(default_factory=list)
    stop_conditions: list[dict[str, float]] = field(default_factory=list)
    seed: int = 42


def _require(data: dict[str, Any], key: str, path: Path) -> Any:
    if key not in data:
        raise ValueError(f"scenario {path} is missing required field {key!r}")
    return data[key]


def load_scenario(path: str | Path) -> Scenario:
    """Load a scenario YAML file and raise clearly on malformed input."""
    scenario_path = Path(path)
    with scenario_path.open("r", encoding="utf-8") as stream:
        data = yaml.safe_load(stream)
    if not isinstance(data, dict):
        raise ValueError(f"scenario {scenario_path} must contain a YAML mapping")
    scenario = Scenario(
        name=_require(data, "name", scenario_path),
        duration_s=_require(data, "duration_s", scenario_path),
        dt=data.get("dt", 0.005),
        initial_state=data.get("initial_state") or {},
        command=Command(data.get("command") or {}),
        disturbances=data.get("disturbances") or [],
        stop_conditions=data.get("stop_conditions") or [],
        seed=data.get("seed", 42),
    )
    errors = validate_scenario(scenario)
    if errors:
        raise ValueError(f"invalid scenario {scenario_path}: " + "; ".join(errors))
    return scenario


def validate_scenario(scenario: Scenario) -> list[str]:
    """Return validation errors; an empty list means the scenario is valid."""
    errors: list[str] = []
    if not isinstance(scenario.name, str) or not scenario.name.strip():
        errors.append("name must be a non-empty string")
    if not isinstance(scenario.duration_s, (int, float)) or scenario.duration_s <= 0:
        errors.append("duration_s must be greater than zero")
    if not isinstance(scenario.dt, (int, float)) or scenario.dt <= 0:
        errors.append("dt must be greater than zero")
    if not isinstance(scenario.seed, int):
        errors.append("seed must be an integer")
    if not isinstance(scenario.initial_state, dict):
        errors.append("initial_state must be a mapping")
    else:
        unknown = set(scenario.initial_state) - _INITIAL_KEYS
        if unknown:
            errors.append(f"initial_state has unknown fields: {sorted(unknown)}")
        motors = scenario.initial_state.get("motor_thrust")
        if motors is not None and (not isinstance(motors, list) or len(motors) != 4):
            errors.append("initial_state.motor_thrust must contain four values")
    if not isinstance(scenario.command, dict):
        errors.append("command must be a mapping")
    else:
        unknown = set(scenario.command) - _COMMAND_KEYS
        if unknown:
            errors.append(f"command has unknown fields: {sorted(unknown)}")
        for axis, raw in scenario.command.items():
            try:
                if isinstance(raw, dict):
                    float(raw["value"])
                    float(raw.get("start_s", 0.0))
                else:
                    float(raw)
            except (KeyError, TypeError, ValueError):
                errors.append(f"command.{axis} must be numeric or a value/start_s mapping")
    if not isinstance(scenario.disturbances, list):
        errors.append("disturbances must be a list")
    else:
        for index, item in enumerate(scenario.disturbances):
            if not isinstance(item, dict) or not {"start_s", "axis", "magnitude"} <= set(item):
                errors.append(f"disturbances[{index}] requires start_s, axis, and magnitude")
            elif item["axis"] not in _COMMAND_KEYS:
                errors.append(f"disturbances[{index}].axis must be one of {sorted(_COMMAND_KEYS)}")
            else:
                try:
                    MagnitudeSpec(item["magnitude"])
                except ValueError as exc:
                    errors.append(f"disturbances[{index}].magnitude: {exc}")
    if not isinstance(scenario.stop_conditions, list):
        errors.append("stop_conditions must be a list")
    else:
        for index, predicate in enumerate(scenario.stop_conditions):
            if not isinstance(predicate, dict) or len(predicate) != 1:
                errors.append(f"stop_conditions[{index}] must be a one-key mapping")
            elif next(iter(predicate)) not in _STOP_KEYS:
                errors.append(f"stop_conditions[{index}] has an unsupported predicate")
    return errors


def scenario_to_dict(scenario: Scenario) -> dict[str, Any]:
    """Return a YAML-safe dictionary preserving the scenario fields."""
    disturbances = []
    for item in scenario.disturbances:
        row = dict(item)
        if "magnitude" in row:
            row["magnitude"] = MagnitudeSpec(row["magnitude"]).to_yaml()
        disturbances.append(row)
    return {
        "name": scenario.name,
        "duration_s": float(scenario.duration_s),
        "dt": float(scenario.dt),
        "initial_state": dict(scenario.initial_state),
        "command": dict(scenario.command),
        "disturbances": disturbances,
        "stop_conditions": [dict(item) for item in scenario.stop_conditions],
        "seed": scenario.seed,
    }


__all__ = ["Command", "Scenario", "load_scenario", "scenario_to_dict", "validate_scenario"]
