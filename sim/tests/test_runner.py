"""Generic Runner test: drives a stub ``Plant`` through the runner seam.

The Gazebo-era test used a ``FakeGazeboBridge`` and asserted the
bridge-step count. ADR-0012 D7 retired Gazebo; this test now drives
the engine-agnostic :class:`sim.runner.Runner` against a
:class:`sim.plant.Plant` subclass. The stub is a Plant (not a bridge)
because that is the seam the runner now holds.
"""
from __future__ import annotations

import csv
import json
import math

import pytest

from sim.plant import Plant
from sim.recorder import CSVRecorder
from sim.runner import Runner
from sim.scenarios_yaml import Command, Scenario


class _StubPlant(Plant):
    """Deterministic stand-in for any 6-DOF ``Plant`` backend.

    Records every call so the test can assert the runner drove the
    contract (``step`` + ``reset``) the correct number of times.
    Returns a fixed-rate body state with motors and command echo so the
    recorder's expected CSV columns are populated.
    """

    instances: list["_StubPlant"] = []

    def __init__(self) -> None:
        cls = type(self)
        self.reset_calls = 0
        self.step_calls = 0
        cls.instances.append(self)

    def reset(self) -> None:
        self.reset_calls += 1
        self.step_calls = 0

    def step(self, u: dict) -> dict:
        self.step_calls += 1
        phi = math.radians(45.0) if self.step_calls > 5 else 0.0
        return {
            "x": 0.0, "y": 0.0, "z": 5.0,
            "vx": 0.0, "vy": 0.0, "vz": 0.0,
            "phi": phi, "theta": 0.0, "psi": 0.0,
            "p": 0.0, "q": 0.0, "r": 0.0,
            "q0": 1.0, "q1": 0.0, "q2": 0.0, "q3": 0.0,
            "thrust": 0.0,
            "motors": (0.0, 0.0, 0.0, 0.0),
        }


@pytest.fixture(autouse=True)
def _clear_stubs():
    _StubPlant.instances.clear()
    yield
    _StubPlant.instances.clear()


def _make_runner(scenario: Scenario) -> Runner:
    return Runner(scenario, CSVRecorder(), plant_factory=_StubPlant)


def test_runner_drives_stub_plant(tmp_path):
    outdir = tmp_path / "run"
    scenario = Scenario(
        name="short", duration_s=0.05, dt=0.005,
        command=Command({"z": 0.0, "roll": 0.0, "pitch": 0.0, "yaw": 0.0}),
    )
    runner = _make_runner(scenario)
    result = runner.run(output_dir=outdir)
    assert result.exit_reason == "completed"
    assert result.outdir.exists()
    assert (outdir / "summary.json").exists()
    assert (outdir / "manifest.json").exists()
    with (outdir / "trajectory.csv").open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 10
    manifest = json.loads((outdir / "manifest.json").read_text(encoding="utf-8"))
    assert {"scenario", "git_sha", "sim_sha", "urdf_sha"} <= set(manifest)
    # The runner constructed exactly one plant and drove it for the
    # full duration; the stub recorded step_calls == duration / dt.
    assert len(_StubPlant.instances) == 1
    stub = _StubPlant.instances[-1]
    assert stub.reset_calls == 1
    assert stub.step_calls == 10


def test_runner_triggers_stop_condition(tmp_path):
    outdir = tmp_path / "run_stop"
    scenario = Scenario(
        name="trip", duration_s=0.05, dt=0.005,
        command=Command({"z": 0.0, "roll": 0.0, "pitch": 0.0, "yaw": 0.0}),
        stop_conditions=[{"max_abs_phi_deg": 30}],
    )
    runner = _make_runner(scenario)
    result = runner.run(output_dir=outdir)
    assert result.exit_reason == "stop_condition:max_abs_phi_deg"


def test_runner_refuses_overwrite(tmp_path):
    outdir = tmp_path / "run"
    outdir.mkdir()
    scenario = Scenario(
        name="short", duration_s=0.005, dt=0.005,
        command=Command({"z": 0.0, "roll": 0.0, "pitch": 0.0, "yaw": 0.0}),
    )
    runner = _make_runner(scenario)
    with pytest.raises(FileExistsError):
        runner.run(output_dir=outdir)
