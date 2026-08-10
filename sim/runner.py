"""Engine-agnostic scenario runner (ADR-0012 D7).

The Gazebo-era runner (spec 4c) booted a ``gz sim`` subprocess, drove
physics via ``WorldControl``, and recorded a 6-DOF trace. ADR-0012 D1
retired Gazebo; D7 keeps the agent-facing run surface engine-agnostic.
This module is the result: a generic :class:`Runner` that holds any
:class:`Plant` instance and drives the closed-loop tick at ``dt``. The
runner does not know which physics engine produced the plant -- it
reads ``state_dict`` from ``plant.step(u_dict)`` and writes the standard
artifact folder (``trajectory.csv``, ``manifest.json``, ``summary.json``,
``config.yaml``).

The :class:`Plant` seam is the contract (ADR-0006 D3/D6). The runner
owns the simulation clock, the recorder, and the manifest receipts;
the plant owns the physics. A future closed-loop reference model
(``sim.loop.ControlLoop``) drops in by replacing the inline
``plant.step`` call with ``loop.tick`` at one site.

The Gazebo-era entry point was :func:`run_experiment` with a
``bridge_factory`` kwarg. That surface is gone with the bridge -- the
new entry point is :meth:`Runner.run` with a ``plant_factory`` kwarg
that returns a freshly reset :class:`Plant`. The :class:`Recorder`
argument is unchanged.
"""
from __future__ import annotations

import hashlib
import json
import platform
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import numpy as np
import yaml

from sim.aggregator import aggregate
from sim.manifest import write_manifest
from sim.recorder import CSVRecorder, Recorder
from sim.scenarios_yaml import Scenario, scenario_to_dict, validate_scenario


@dataclass(frozen=True)
class RunResult:
    """Paths and receipts produced by a completed experiment."""

    outdir: Path
    summary: dict
    manifest: dict
    exit_reason: str
    trajectory_path: Path


def _sha256(data: bytes | str) -> str:
    payload = data.encode("utf-8") if isinstance(data, str) else data
    return hashlib.sha256(payload).hexdigest()


def _git_sha() -> str:
    import subprocess
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True,
            timeout=10.0, check=False,
        )
        return result.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _default_outdir(scenario: Scenario) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path("runs") / f"{scenario.name}_{scenario.seed}_{timestamp}"


def _command_at(scenario: Scenario, t: float) -> dict[str, float]:
    """Project the scenario's command + disturbances at simulation time ``t``."""
    command = scenario.command(t) if callable(scenario.command) else dict(scenario.command)
    for disturbance in scenario.disturbances:
        if t >= float(disturbance["start_s"]):
            axis = str(disturbance["axis"])
            command[axis] = command.get(axis, 0.0) + float(disturbance["magnitude"])
    return command


def _stop_reason(scenario: Scenario, state: dict) -> str | None:
    for predicate in scenario.stop_conditions:
        name, limit = next(iter(predicate.items()))
        if name == "max_abs_phi_deg" and abs(np.degrees(float(state.get("phi", 0.0)))) > float(limit):
            return f"stop_condition:{name}"
        if name == "min_z_m" and float(state.get("z", 0.0)) < float(limit):
            return f"stop_condition:{name}"
    return None


class Runner:
    """Generic engine-agnostic runner: holds a :class:`Plant`, drives its step.

    Parameters
    ----------
    scenario
        A :class:`sim.scenarios_yaml.Scenario` declaring duration / dt /
        command / disturbances / stop conditions / seed. The same
        dataclass the YAML loader returns; this runner adds no fields.
    recorder
        A :class:`sim.recorder.Recorder` protocol implementation.
        Defaults to :class:`sim.recorder.CSVRecorder` if omitted.
    plant_factory
        Callable that returns a freshly constructed :class:`Plant`. The
        runner calls ``plant_factory()`` once per ``run()`` so the plant
        is deterministic across runs of the same scenario. Pass
        ``plant_factory=IdentifiedPlant.canonical`` for the documented
        Phase-1 plant, or ``plant_factory=lambda: MujocoPlant(...)``
        once the parallel session lands.
    """

    def __init__(
        self,
        scenario: Scenario,
        recorder: Recorder | None = None,
        *,
        plant_factory: Callable[[], "Plant"] | None = None,
    ) -> None:
        errors = validate_scenario(scenario)
        if errors:
            raise ValueError("invalid scenario: " + "; ".join(errors))
        self.scenario = scenario
        self.recorder = recorder if recorder is not None else CSVRecorder()
        # Late import: keeps the Plant ABC available without forcing a
        # concrete plant backend at import time (mirrors ADR-0006 D6).
        from sim.plant import Plant as _Plant
        self._Plant = _Plant
        if plant_factory is None:
            from sim.plant import IdentifiedPlant
            dt = scenario.dt
            plant_factory = lambda: IdentifiedPlant.canonical(dt)  # noqa: E731
        self._plant_factory = plant_factory

    def run(self, *, output_dir: str | Path | None = None) -> RunResult:
        """Execute ``scenario`` against a fresh plant and write the artifacts."""
        scenario = self.scenario
        outdir = Path(output_dir) if output_dir is not None else _default_outdir(scenario)
        if outdir.exists():
            raise FileExistsError(f"refusing to overwrite existing run directory: {outdir}")
        outdir.mkdir(parents=True)
        (outdir / "config.yaml").write_text(
            yaml.safe_dump(scenario_to_dict(scenario), sort_keys=False), encoding="utf-8"
        )

        plant = self._plant_factory()
        plant.reset()
        # ``sim_sha`` is now a hash of the plant factory's source: this
        # is what makes the run reproducible across engines. We capture
        # the module-level source via inspect; if that fails (e.g.
        # lambda), we fall back to the scenario seed which is a stable
        # but weaker proxy.
        try:
            import inspect
            src = inspect.getsource(self._plant_factory)
        except (OSError, TypeError):
            src = f"seed={scenario.seed}"
        git_sha = _git_sha()
        sim_sha = _sha256(src)
        machine = {"node": platform.node(), "processor": platform.processor(), "machine": platform.machine()}

        mirror = self.recorder if isinstance(self.recorder, CSVRecorder) else CSVRecorder()
        if mirror is not self.recorder:
            mirror.path = outdir / "trajectory.csv"
        started = time.monotonic()
        exit_reason = "completed"
        sim_time_s = 0.0

        try:
            self.recorder.start(outdir)
            if mirror is not self.recorder:
                mirror.start(outdir)
            write_manifest(
                outdir, scenario=scenario, seed=scenario.seed, git_sha=git_sha,
                sim_sha=sim_sha, urdf_sha=_sha256(scenario.name),
                wall_time_s=0.0, sim_time_s=0.0,
                exit_reason="running", machine=machine, spawn_z=None,
            )
            for tick in range(int(scenario.duration_s / scenario.dt)):
                t = tick * scenario.dt
                command = _command_at(scenario, t)
                state = plant.step(command)
                state_dict = dict(state)
                state_dict["command"] = command
                self.recorder.record(state_dict, t)
                if mirror is not self.recorder:
                    mirror.record(state_dict, t)
                sim_time_s = (tick + 1) * scenario.dt
                reason = _stop_reason(scenario, state_dict)
                if reason is not None:
                    exit_reason = reason
                    break
        finally:
            self.recorder.stop()
            if mirror is not self.recorder:
                mirror.stop()

        trajectory_path = outdir / "trajectory.csv"
        summary = aggregate(trajectory_path)
        summary["exit_reason"] = exit_reason
        (outdir / "summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        manifest_data = write_manifest(
            outdir, scenario=scenario, seed=scenario.seed, git_sha=git_sha,
            sim_sha=sim_sha, urdf_sha=_sha256(scenario.name),
            wall_time_s=time.monotonic() - started, sim_time_s=sim_time_s,
            exit_reason=exit_reason, machine=machine, spawn_z=None,
        )
        return RunResult(outdir, summary, manifest_data, exit_reason, trajectory_path)


__all__ = ["Runner", "RunResult"]


if __name__ == "__main__":  # pragma: no cover
    import argparse
    import json
    import sys

    from sim.scenarios_yaml import Command, Scenario

    parser = argparse.ArgumentParser(
        prog="python -m sim.runner",
        description=(
            "Engine-agnostic scenario runner (ADR-0012 D7). Holds a Plant "
            "instance and drives a closed-loop tick at dt. Defaults to the "
            "canonical IdentifiedPlant; pass --plant-factory to swap backends."
        ),
    )
    parser.add_argument("--name", default="cli", help="Scenario name (free-form)")
    parser.add_argument("--duration-s", type=float, default=0.05)
    parser.add_argument("--dt", type=float, default=0.005)
    parser.add_argument("--output-dir", default=None,
                        help="Output directory (default: sim/runs/<name>_<seed>_<ts>)")
    parser.add_argument("--z", type=float, default=0.0, help="Z-axis command")
    parser.add_argument("--roll", type=float, default=0.0, help="Roll command (rad/s)")
    parser.add_argument("--pitch", type=float, default=0.0, help="Pitch command (rad/s)")
    parser.add_argument("--yaw", type=float, default=0.0, help="Yaw command (rad/s)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--plant-factory", default=None,
                        help="Dotted path 'pkg.module:callable' that returns a Plant")
    args = parser.parse_args()

    plant_factory = None
    if args.plant_factory:
        module_path, _, attr = args.plant_factory.partition(":")
        import importlib
        module = importlib.import_module(module_path)
        plant_factory = getattr(module, attr) if attr else module

    scenario = Scenario(
        name=args.name, duration_s=args.duration_s, dt=args.dt, seed=args.seed,
        command=Command({"z": args.z, "roll": args.roll,
                         "pitch": args.pitch, "yaw": args.yaw}),
    )
    runner = Runner(scenario, plant_factory=plant_factory)
    result = runner.run(output_dir=args.output_dir)
    print(json.dumps({
        "outdir": str(result.outdir),
        "exit_reason": result.exit_reason,
        "summary": result.summary,
    }, indent=2))
    sys.exit(0)
