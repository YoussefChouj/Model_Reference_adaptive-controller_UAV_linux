"""Reproducibility receipts for Gazebo experiments (spec 4c)."""
from __future__ import annotations

import json
import os
import platform as platform_module
import subprocess
import sys
from pathlib import Path
from typing import Any

from sim.scenarios_yaml import Scenario, scenario_to_dict

_GZ_VERSION: str | None = None
_GZ_VERSION_CAPTURED: bool = False


def _capture_gz_version() -> str:
    """Capture ``gz sim --version`` exactly once per process.

    If the first call fails the cached value stays ``"unavailable"``
    so subsequent calls never re-shell out. ``reset`` allows the
    orchestrator to force a retry after installing Gazebo.
    """
    global _GZ_VERSION, _GZ_VERSION_CAPTURED
    if _GZ_VERSION_CAPTURED:
        return _GZ_VERSION or "unknown"
    try:
        completed = subprocess.run(
            ["gz", "sim", "--version"], capture_output=True, text=True,
            timeout=10.0, check=False,
        )
        _GZ_VERSION = (completed.stdout + completed.stderr).strip() or "unknown"
    except (OSError, subprocess.SubprocessError) as exc:
        _GZ_VERSION = f"unavailable: {exc}"
    _GZ_VERSION_CAPTURED = True
    return _GZ_VERSION


def reset_gz_version_cache() -> None:
    """Force the next ``_capture_gz_version`` call to re-shell out."""
    global _GZ_VERSION, _GZ_VERSION_CAPTURED
    _GZ_VERSION = None
    _GZ_VERSION_CAPTURED = False


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
        "python_version": sys.version,
        "platform": platform_module.platform(),
        "cpu_count": os.cpu_count(),
        "gz_version": _capture_gz_version(),
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


__all__ = ["write_manifest", "reset_gz_version_cache"]