"""Agent-driven Gazebo experiment runner (spec 4c)."""
from __future__ import annotations

import hashlib
import json
import platform
import shutil
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import numpy as np
import yaml

from sim.aggregator import aggregate
from sim.manifest import write_manifest
from sim.plant import CANONICAL_AIRFRAME
from sim.recorder import CSVRecorder, Recorder
from sim.sanity import sim_vs_analytic_hover
from sim.scenarios_yaml import Scenario, scenario_to_dict, validate_scenario
from sim.urdf import DEFAULT_MOTOR_GEOMETRY, airframe_to_urdf
from sim.urdf_conversion import (
    convert_urdf_to_sdf,
    model_sdf_path,
    urdf_artifact_path,
)


class SanityGateFailed(RuntimeError):
    """Raised when Gazebo diverges from the analytic hover reference."""


@dataclass(frozen=True)
class RunResult:
    """Paths and receipts produced by a completed experiment."""

    outdir: Path
    summary: dict
    manifest: dict
    exit_reason: str
    trajectory_path: Path


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git_sha() -> str:
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


def _motor_thrusts(command: dict[str, float]) -> np.ndarray:
    """Translate the four-axis rate command into per-motor thrust (N).

    The translation here is a calibration placeholder: it converts
    roll/pitch/yaw body-rate commands to differential thrust using a
    constant gain (0.005 N per rad/s for roll/pitch, 0.002 N per rad/s
    for yaw). The same gain is used by the analytic plant's
    RigidBodyPlant differential model, so the analytic/Gazebo
    cross-check at hover-trim remains apples-to-apples.

    The wrench translator in GazeboBridge.send_motor_thrust applies the
    actual per-link force and reaction torque at the link's body-frame
    position, so this function does not need to encode body geometry.
    """
    total = float(command.get("z", 0.0))
    if total == 0.0:
        total = CANONICAL_AIRFRAME.thrust_per_motor_hover * 4.0
    base = total / 4.0
    roll = float(command.get("roll", 0.0)) * 0.005
    pitch = float(command.get("pitch", 0.0)) * 0.005
    yaw = float(command.get("yaw", 0.0)) * 0.002
    geometry = DEFAULT_MOTOR_GEOMETRY
    motors = np.array([
        base + roll - pitch + (-yaw if not geometry[0].cw else yaw),
        base - roll - pitch + (-yaw if not geometry[1].cw else yaw),
        base - roll + pitch + (-yaw if not geometry[2].cw else yaw),
        base + roll + pitch + (-yaw if not geometry[3].cw else yaw),
    ])
    return np.maximum(motors, 0.0)


def _command_at(scenario: Scenario, t: float) -> dict[str, float]:
    command = scenario.command(t)
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


def _prepare_artifacts(outdir: Path, scenario: Scenario) -> tuple[Path, str]:
    """Materialise the URDF and converted SDF for this run."""
    artifacts = outdir / "_artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    urdf_target = urdf_artifact_path(outdir)
    urdf_text = airframe_to_urdf(CANONICAL_AIRFRAME)
    urdf_target.write_text(urdf_text, encoding="utf-8")
    model_sdf = model_sdf_path(outdir)
    use_gz = shutil.which("gz") is not None
    convert_urdf_to_sdf(urdf_target, model_sdf, use_gz_binary=use_gz)
    return model_sdf, urdf_text


def _compose_world(master_world: Path, model_sdf: Path, scenario: Scenario) -> Path:
    """Render a per-run world SDF that includes the converted model."""
    text = master_world.read_text(encoding="utf-8")
    include_block = (
        f'    <include merge="true">\n'
        f'      <uri>{model_sdf.as_posix()}</uri>\n'
        f'      <name>{scenario.name}</name>\n'
        f'    </include>\n'
    )
    closing = "  </world>\n"
    if text.count(closing) != 1:
        raise ValueError(f"{master_world} does not contain a single world close tag")
    rendered = text.replace(closing, include_block + closing)
    rendered_world = model_sdf.parent / "jx_fly_run_world.sdf"
    rendered_world.write_text(rendered, encoding="utf-8")
    return rendered_world


def run_experiment(
    scenario: Scenario,
    recorder: Recorder,
    *,
    output_dir: str | Path | None = None,
    sanity: bool = True,
    bridge_factory: Callable | None = None,
) -> RunResult:
    """Run one deterministic scenario and persist its trajectory receipts."""
    errors = validate_scenario(scenario)
    if errors:
        raise ValueError("invalid scenario: " + "; ".join(errors))
    if sanity:
        passed, comparison = sim_vs_analytic_hover(
            bridge_factory=bridge_factory,
        )
        if not passed:
            raise SanityGateFailed(json.dumps(comparison, sort_keys=True))

    outdir = Path(output_dir) if output_dir is not None else _default_outdir(scenario)
    if outdir.exists():
        raise FileExistsError(f"refusing to overwrite existing run directory: {outdir}")
    outdir.mkdir(parents=True)
    (outdir / "config.yaml").write_text(
        yaml.safe_dump(scenario_to_dict(scenario), sort_keys=False), encoding="utf-8"
    )

    model_sdf, urdf_text = _prepare_artifacts(outdir, scenario)
    master_world = Path("sim/worlds/jx_fly.sdf")
    run_world = _compose_world(master_world, model_sdf, scenario)
    git_sha = _git_sha()
    urdf_sha = _sha256(urdf_text.encode("utf-8"))
    sim_sha = _sha256(master_world.read_bytes())
    machine = {"node": platform.node(), "processor": platform.processor(), "machine": platform.machine()}

    if bridge_factory is None:
        from sim.gazebo_bridge import GazeboBridge
        bridge_factory = GazeboBridge
    bridge = None
    mirror = recorder if isinstance(recorder, CSVRecorder) else CSVRecorder()
    if mirror is not recorder:
        mirror.path = outdir / "trajectory.csv"
    started = time.monotonic()
    exit_reason = "completed"
    sim_time_s = 0.0
    try:
        bridge = bridge_factory(world_path=str(run_world))
        recorder.start(outdir)
        if mirror is not recorder:
            mirror.start(outdir)
        write_manifest(
            outdir, scenario=scenario, seed=scenario.seed, git_sha=git_sha,
            sim_sha=sim_sha, urdf_sha=urdf_sha, wall_time_s=0.0,
            sim_time_s=0.0, exit_reason="running", machine=machine,
        )
        bridge.reset()
        for tick in range(int(scenario.duration_s / scenario.dt)):
            t = tick * scenario.dt
            command = _command_at(scenario, t)
            state = bridge.step(_motor_thrusts(command), scenario.dt)
            state_dict = state.as_state_dict()
            state_dict["command"] = command
            recorder.record(state_dict, t)
            if mirror is not recorder:
                mirror.record(state_dict, t)
            sim_time_s = (tick + 1) * scenario.dt
            reason = _stop_reason(scenario, state_dict)
            if reason is not None:
                exit_reason = reason
                break
    finally:
        recorder.stop()
        if mirror is not recorder:
            mirror.stop()
        if bridge is not None:
            bridge.close()

    trajectory_path = outdir / "trajectory.csv"
    summary = aggregate(trajectory_path)
    summary["exit_reason"] = exit_reason
    (outdir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    manifest_data = write_manifest(
        outdir, scenario=scenario, seed=scenario.seed, git_sha=git_sha,
        sim_sha=sim_sha, urdf_sha=urdf_sha,
        wall_time_s=time.monotonic() - started, sim_time_s=sim_time_s,
        exit_reason=exit_reason, machine=machine,
    )
    return RunResult(outdir, summary, manifest_data, exit_reason, trajectory_path)


__all__ = ["RunResult", "SanityGateFailed", "run_experiment"]