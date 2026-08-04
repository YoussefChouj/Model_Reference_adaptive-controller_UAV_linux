"""In-process runner test for spec 4c."""
from __future__ import annotations

import csv
import json
import math

import pytest

from sim.gazebo_bridge import BridgeState
from sim.recorder import CSVRecorder
from sim.runner import run_experiment
from sim.scenarios_yaml import Command, Scenario


class FakeGazeboBridge:
    instances = []

    def __init__(self, world_path, **kwargs):
        self.world_path = world_path
        self.step_calls = 0
        self.closed = False
        self.__class__.instances.append(self)

    def reset(self):
        self.step_calls = 0

    def step(self, motor_thrusts_N, dt):
        self.step_calls += 1
        phi = math.radians(45.0) if self.step_calls > 5 else 0.0
        return BridgeState(
            x=self.step_calls * dt,
            thrust=float(sum(motor_thrusts_N)),
            motors=tuple(float(value) for value in motor_thrusts_N),
            phi=phi,
        )

    def close(self):
        self.closed = True


def test_run_experiment_with_fake_bridge(tmp_path):
    outdir = tmp_path / "run"
    scenario = Scenario(
        name="short", duration_s=0.05, dt=0.005,
        command=Command({"z": 0.0, "roll": 0.0, "pitch": 0.0, "yaw": 0.0}),
    )
    FakeGazeboBridge.instances.clear()
    result = run_experiment(
        scenario, CSVRecorder(), output_dir=outdir, sanity=False,
        bridge_factory=FakeGazeboBridge,
    )
    assert result.exit_reason == "completed"
    assert result.outdir.exists()
    assert (outdir / "summary.json").exists()
    assert (outdir / "manifest.json").exists()
    with (outdir / "trajectory.csv").open(newline="", encoding="utf-8") as stream:
        assert len(list(csv.DictReader(stream))) == 10
    manifest = json.loads((outdir / "manifest.json").read_text(encoding="utf-8"))
    assert {"scenario", "git_sha", "sim_sha", "urdf_sha", "gz_version"} <= set(manifest)
    assert FakeGazeboBridge.instances[-1].step_calls == 10
    assert FakeGazeboBridge.instances[-1].closed


def test_run_experiment_triggers_stop_condition(tmp_path):
    outdir = tmp_path / "run_stop"
    scenario = Scenario(
        name="trip", duration_s=0.05, dt=0.005,
        command=Command({"z": 0.0, "roll": 0.0, "pitch": 0.0, "yaw": 0.0}),
        stop_conditions=[{"max_abs_phi_deg": 30}],
    )
    result = run_experiment(
        scenario, CSVRecorder(), output_dir=outdir, sanity=False,
        bridge_factory=FakeGazeboBridge,
    )
    assert result.exit_reason == "stop_condition:max_abs_phi_deg"