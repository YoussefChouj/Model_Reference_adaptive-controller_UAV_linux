"""Agent-driven Gazebo experiment runner (spec 4c).

Architecture note (2026-08-05): the pipeline uses deterministic stepped
physics instead of wall-clock / real_time_factor racing. The gz sim
process boots **paused** (no -r flag). The Python bridge drives physics
in controlled blocks via the /world/<name>/control service
(WorldControl with multi_step=N). This eliminates the free-fall race
where the model spawns at z=5 but falls to the ground in <1ms wall-clock
before the bridge can subscribe to the pose topic.

The loop is: boot paused → verify pose z≈5 → multi_step:5 → read pose →
publish wrench → repeat. No time.sleep(), no RTF dependence.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
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
from sim.sanity import (
    analytic_hover_trace as sanity_analytic_hover_trace,
    compare_analytic_to_gazebo,
    sim_vs_analytic_hover,
)
from sim.scenarios_yaml import Scenario, scenario_to_dict, validate_scenario
from sim.urdf import DEFAULT_MOTOR_GEOMETRY, airframe_to_urdf
from sim.urdf_conversion import (
    URDFConversionError,
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


def _kill_stray_gz_processes() -> None:
    """Kill any stale gz sim or transport processes from previous runs.

    gz-transport topics are host-wide. Any dangling process publishing
    to the same topic will contaminate the current run. We kill all
    gz-sim, gz-sim-server, and ruby processes (the gz CLI is a Ruby
    launcher) before each experiment run.
    """
    for pattern in ("gz-sim", "gz-sim-main", "ruby.*gz"):
        try:
            subprocess.run(
                ["pkill", "-9", "-f", pattern],
                capture_output=True, check=False,
            )
        except (OSError, subprocess.SubprocessError):
            pass


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

    X-frame sign convention (matches sim.urdf.DEFAULT_MOTOR_GEOMETRY):
        M1 = (+r, +y_motor)   front-right   CCW  (label index 0)
        M2 = (-r, +y_motor)   rear-right    CW   (label index 1)
        M3 = (-r, -y_motor)   rear-left     CW   (label index 2)
        M4 = (+r, -y_motor)   front-left    CCW  (label index 3)

    A positive ``roll`` moment about body +x is produced by motors on
    the +y side spinning faster: M1 > M2 and M4 > M3, i.e. differential
    pattern [+d, -d, -d, +d] for [M1, M2, M3, M4]? No -- that pattern
    gives equal +y and -y contributions which cancel for the X-axis
    torque. The correct pattern is [+d, +d, -d, -d]: increase the +y
    pair (M1, M2) relative to the -y pair (M3, M4). That makes the
    right side lift more than the left and the body rolls positive.
    A positive ``pitch`` about body +y comes from increasing the +x
    pair (M1, M4) relative to the -x pair (M2, M3): [+d, -d, +d, -d].
    """
    total = float(command.get("z", 0.0))
    if total == 0.0:
        total = CANONICAL_AIRFRAME.thrust_per_motor_hover * 4.0
    base = total / 4.0
    roll = float(command.get("roll", 0.0)) * 0.005
    pitch = float(command.get("pitch", 0.0)) * 0.005
    yaw = float(command.get("yaw", 0.0)) * 0.002
    geometry = DEFAULT_MOTOR_GEOMETRY
    # X-frame mixer: differential on [M1, M2, M3, M4] = [M1+M2, M1-M4,
    # M4-M3, -(M1+M2)] under the [+y, +x, -x, -y] channels.
    # roll:  +y side faster  => M1, M2 up,  M3, M4 down
    # pitch: +x side faster  => M1, M4 up,  M2, M3 down
    # yaw:   CCW reactive    => CCW motors (1, 3) boost / CW (2, 4) cut
    motors = np.array([
        base + roll + pitch + (+yaw if not geometry[0].cw else -yaw),
        base + roll - pitch + (-yaw if not geometry[1].cw else +yaw),
        base - roll - pitch + (-yaw if not geometry[2].cw else +yaw),
        base - roll + pitch + (+yaw if not geometry[3].cw else -yaw),
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
    _inject_model_plugins(model_sdf)
    # Lift the model to z=5 by writing <pose>...</pose> on the <model>
    # element itself. Empirical observation (gz-sim 10 / jetty, 2026-08):
    # <include><pose>...</pose> is silently IGNORED for a free-floating
    # URDF-derived model -- the model always starts at z=0 and the
    # collision-half-height offset (-0.024 m) makes it spawn
    # interpenetrating the ground plane. ODE then resolves the
    # penetration with a strong contact normal force that clamps roll
    # and pitch torques to zero. The structural fix is to write the
    # pose onto the model itself in the per-run SDF copy.
    _set_model_pose(model_sdf, spawn_z_m=5.0)
    return model_sdf, urdf_text


def _set_model_pose(model_sdf: Path, *, spawn_z_m: float) -> None:
    """Write a <pose>0 0 {z} 0 0 0</pose> attribute on the <model> element.

    ``gz sdf -p`` emits a clean ``<model name='jx_fly'>`` with no pose
    tag on the model itself (inner links/visuals do have <pose>). We
    inject a single <pose> child *immediately after* the <model> open
    tag. This is the simplest, framework-supported way to lift the
    model on spawn, and PosePublisher reports the *model* pose in
    world frame, which is exactly what we want.
    """
    text = model_sdf.read_text(encoding="utf-8")
    open_tag = "<model name='jx_fly'>"
    if open_tag not in text:
        raise ValueError(f"{model_sdf}: cannot locate {open_tag} for pose injection")
    # Idempotent: check if <model name='jx_fly'><pose>... already exists.
    target = f"{open_tag}<pose>"
    if target in text:
        return
    new_open = f"<model name='jx_fly'><pose>0 0 {spawn_z_m} 0 0 0</pose>"
    new_text = text.replace(open_tag, new_open, 1)
    model_sdf.write_text(new_text, encoding="utf-8")


# Model-attached plugins. PosePublisher and Imu must live INSIDE the model
# (not at the world level) because they attach to a model entity.
# ApplyLinkWrench must be world-attached -- it operates on
# /world/<name>/wrench -- so it stays in sim/worlds/jx_fly.sdf.
#
# PosePublisher defaults: when attached to a model, it publishes the
# poses of the model's *child entities* (links, visuals, etc.) relative
# to the model frame -- not the model pose in the world frame. The
# link-relative-to-model pose is by definition (0,0,0) identity, so
# subscribing to it from the bridge gave us a frozen identity-quaternion
# stream and the drone appeared not to move (2026-08-05).
#
# Setting ``publish_model_pose`` and ``publish_nested_model_pose`` true
# makes the plugin additionally publish the model pose in WORLD frame
# to the same /model/<name>/pose topic, which is what the bridge
# actually needs.
_MODEL_PLUGINS = """\
    <plugin filename="gz-sim-pose-publisher-system" name="gz::sim::systems::PosePublisher">
      <publish_model_pose>true</publish_model_pose>
      <publish_nested_model_pose>true</publish_nested_model_pose>
      <publish_link_pose>true</publish_link_pose>
    </plugin>
    <plugin filename="gz-sim-imu-system" name="gz::sim::systems::Imu"/>
"""


def _inject_model_plugins(model_sdf: Path) -> None:
    """Inject the per-model plugins into the converted SDF.

    The converted model SDF carries a single ``<model name="jx_fly">``
    element. We inject the canonical plugin block at the END of that
    element, just before the closing ``</model>``. The substitution
    matches against ``gz sdf -p`` output's single-quote attribute
    style (``<model name='jx_fly'>``) which is the canonical output
    of this toolchain on Linux.
    """
    text = model_sdf.read_text(encoding="utf-8")
    for marker in ("</model>",):
        if marker in text:
            text = text.replace(marker, _MODEL_PLUGINS + marker, 1)
            model_sdf.write_text(text, encoding="utf-8")
            return
    raise URDFConversionError(
        f"{model_sdf}: cannot inject model plugins; no </model> close tag found"
    )


def _compose_world(master_world: Path, model_sdf: Path, scenario: Scenario) -> Path:
    """Render a per-run world SDF that includes the converted model.

    ``gz sdf -p`` produces a top-level ``<sdf><model>`` document. To embed
    that into our master ``<sdf><world>`` we use a plain ``<include>`` with
    a ``<uri>`` and a ``<name>`` -- this nests the model as a child of the
    world. ``merge="true"`` is wrong here: it tries to lift the model's
    ``<link>`` children into the world root, which gz-sim rejects with
    "Merge-include for <world> does not support element of type link".
    """
    text = master_world.read_text(encoding="utf-8")
    # The model is lifted to z=5 by the model SDF itself (see
    # _set_model_pose). Earlier we used <include><pose>0 0 5 0 0 0</pose>
    # but in gz-sim 10 (jetty) the include pose is silently ignored for
    # a free-floating URDF-derived model -- the model always spawns at
    # z=0 and the collision-half-height offset (-0.024 m) makes it
    # interpenetrate the ground plane. ODE then clamps roll/pitch
    # torques to zero. Writing the pose on the <model> element itself
    # is the structural fix.
    include_block = (
        f'    <include>\n'
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


def _compose_sanity_world(master_world: Path, model_sdf: Path, scenario: Scenario) -> Path:
    """Render a *sanity-prefixed* world SDF.

    The sim-vs-analytic gate boots its own gz sim subprocess. If both
    this subprocess and the main run claim the same world name, the
    second ``gz sim`` fails with "Another world of the same name is
    running". We give the sanity world a unique ``<name>`` so both
    can coexist -- the comparison is model-frame, not world-frame, so
    the world name doesn't affect the physics.
    """
    text = master_world.read_text(encoding="utf-8")
    # Replace the canonical world name with a unique one. The model
    # still uses the scenario.name passed to the bridge, so the
    # sim-vs-analytic gate reads the same model-state it would in
    # production.
    text = re.sub(
        r'<world name="jx_fly">',
        f'<world name="sanity_{scenario.name}">',
        text, count=1,
    )
    include_block = (
        f'    <include>\n'
        f'      <uri>{model_sdf.as_posix()}</uri>\n'
        f'      <name>{scenario.name}</name>\n'
        f'    </include>\n'
    )
    closing = "  </world>\n"
    if text.count(closing) != 1:
        raise ValueError(f"{master_world} does not contain a single world close tag")
    rendered = text.replace(closing, include_block + closing)
    out = model_sdf.parent / "jx_fly_sanity_world.sdf"
    out.write_text(rendered, encoding="utf-8")
    return out


def run_experiment(
    scenario: Scenario,
    recorder: Recorder,
    *,
    output_dir: str | Path | None = None,
    sanity: bool = True,
    bridge_factory: Callable | None = None,
) -> RunResult:
    """Run one deterministic scenario and persist its trajectory receipts."""
    _kill_stray_gz_processes()
    errors = validate_scenario(scenario)
    if errors:
        raise ValueError("invalid scenario: " + "; ".join(errors))
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
    spawn_z: float | None = None
    # Sanity gate runs in its OWN gz sim subprocess (with a unique
    # world name so it doesn't conflict with the main run's world),
    # then closes cleanly before the main run starts. This keeps the
    # physics pristine for the actual recorded trajectory.
    if sanity:
        sanity_world = _compose_sanity_world(master_world, model_sdf, scenario)
        passed, comparison = sim_vs_analytic_hover(
            bridge_factory=bridge_factory,
            world_path=str(sanity_world),
            model_name=scenario.name,
        )
        if not passed:
            raise SanityGateFailed(json.dumps(comparison, sort_keys=True))
    try:
        bridge = bridge_factory(
            world_path=str(run_world),
            model_name=scenario.name,
        )
        # Verify the model spawned at the intended altitude while paused.
        # This confirms the spawn pose is correct before any free-fall can occur.
        spawn_z = bridge.verify_pose(z_expected=5.0, tolerance=0.5)
        bridge.reset()
        recorder.start(outdir)
        if mirror is not recorder:
            mirror.start(outdir)
        write_manifest(
            outdir, scenario=scenario, seed=scenario.seed, git_sha=git_sha,
            sim_sha=sim_sha, urdf_sha=urdf_sha, wall_time_s=0.0,
            sim_time_s=0.0, exit_reason="running", machine=machine,
            spawn_z=spawn_z,
        )
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
        spawn_z=spawn_z,
    )
    return RunResult(outdir, summary, manifest_data, exit_reason, trajectory_path)


__all__ = ["RunResult", "SanityGateFailed", "run_experiment"]