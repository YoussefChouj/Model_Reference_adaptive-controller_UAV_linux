"""Engine-agnostic reproducibility receipts (ADR-0012 D7).

One manifest per run: scenario, seed, shas, timing, and the plant that
produced the trajectory. No external binary is invoked (the Gazebo
version capture was removed when Gazebo was retired — ADR-0012 D1).
"""
from __future__ import annotations

import json
import os
import platform as platform_module
import sys
from pathlib import Path
from typing import Any

from sim.scenarios_yaml import Scenario, scenario_to_dict


def write_manifest(
    outdir: str | Path,
    *,
    scenario: Scenario | dict,
    seed: int,
    git_sha: str,
    sim_sha: str,
    urdf_sha: str,
    wall_time_s: float,
    sim_time_s: float,
    exit_reason: str,
    machine: Any,
    plant_name: str = "identified",
    spawn_z: float | None = None,
) -> dict:
    """Write ``manifest.json`` and plain-text receipt sidecars."""
    directory = Path(outdir)
    directory.mkdir(parents=True, exist_ok=True)
    scenario_data = scenario_to_dict(scenario) if isinstance(scenario, Scenario) else dict(scenario)
    manifest = {
        "scenario": scenario_data,
        "seed": int(seed),
        "git_sha": str(git_sha),
        "sim_sha": str(sim_sha),
        "urdf_sha": str(urdf_sha),
        "wall_time_s": float(wall_time_s),
        "sim_time_s": float(sim_time_s),
        "exit_reason": str(exit_reason),
        "machine": machine,
        "plant_name": str(plant_name),
        "python_version": sys.version,
        "platform": platform_module.platform(),
        "cpu_count": os.cpu_count(),
        "spawn_z": float(spawn_z) if spawn_z is not None else None,
    }
    (directory / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (directory / "git_sha.txt").write_text(str(git_sha) + "\n", encoding="utf-8")
    (directory / "urdf_sha.txt").write_text(str(urdf_sha) + "\n", encoding="utf-8")
    (directory / "sim_sha.txt").write_text(str(sim_sha) + "\n", encoding="utf-8")
    (directory / "seed.txt").write_text(str(seed) + "\n", encoding="utf-8")
    return manifest


__all__ = ["write_manifest"]