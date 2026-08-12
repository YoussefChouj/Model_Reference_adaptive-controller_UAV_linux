"""Engine-agnostic reproducibility receipts (ADR-0012 D7).

One manifest per run: scenario, seed, shas, timing, and the plant that
produced the trajectory. No external binary is invoked (the Gazebo
version capture was removed when Gazebo was retired — ADR-0012 D1).

Schema version 1.1 (sim-arch-04): the full schema lives in
``sim.manifest_schema.ManifestPayload``; this module is the thin writer.
"""
from __future__ import annotations

import json
import os
import platform as platform_module
import sys
from pathlib import Path
from typing import Any

from sim.manifest_schema import ManifestPayload, MANIFEST_SCHEMA_VERSION
from sim.scenarios_yaml import Scenario, scenario_to_dict


def write_manifest(
    outdir: str | Path,
    payload: ManifestPayload | None = None,
    *,
    # backward-compat kwargs — accepted for any call site that has not yet
    # migrated to the ManifestPayload API.  Do NOT add new kwargs here.
    scenario: Scenario | dict | None = None,
    seed: int | None = None,
    git_sha: str | None = None,
    sim_sha: str | None = None,
    urdf_sha: str | None = None,
    wall_time_s: float | None = None,
    sim_time_s: float | None = None,
    exit_reason: str | None = None,
    machine: Any | None = None,
    plant_name: str = "identified",
    spawn_z: float | None = None,
    prior: dict | None = None,
) -> dict:
    """Write ``manifest.json`` and plain-text receipt sidecars.

    Two call patterns are supported:

    **New (preferred)** — pass a single ``ManifestPayload``::

        write_manifest(outdir, payload=my_payload)

    **Legacy** — pass explicit keyword arguments::

        write_manifest(outdir, scenario=..., seed=..., ...)

    When called with ``payload=``, the kwargs are ignored.  When called with
    kwargs, a ``ManifestPayload`` is built internally and serialised, preserving
    full backward compatibility with existing call sites
    (``test_manifest.py``, ``test_priors_recovery.py``).

    The ``prior`` kwarg (legacy) is converted into a
    ``ManifestPayload`` field and emitted as the ``"prior"`` block in the
    manifest, mirroring the pre-1.1 behaviour.
    """
    directory = Path(outdir)
    directory.mkdir(parents=True, exist_ok=True)

    if payload is None:
        scenario_data = (
            scenario_to_dict(scenario) if isinstance(scenario, Scenario)
            else dict(scenario) if scenario is not None
            else {}
        )
        payload = ManifestPayload(
            scenario=scenario_data,
            seed=int(seed) if seed is not None else 0,
            git_sha=str(git_sha) if git_sha is not None else "",
            sim_sha=str(sim_sha) if sim_sha is not None else "",
            urdf_sha=str(urdf_sha) if urdf_sha is not None else "",
            wall_time_s=float(wall_time_s) if wall_time_s is not None else 0.0,
            sim_time_s=float(sim_time_s) if sim_time_s is not None else 0.0,
            exit_reason=str(exit_reason) if exit_reason is not None else "unknown",
            machine=machine,
            plant_name=str(plant_name),
            spawn_z=float(spawn_z) if spawn_z is not None else None,
        )
        # Build the dict with legacy top-level extras before adding prior.
        d = payload.to_dict()
        d["python_version"] = sys.version
        d["platform"] = platform_module.platform()
        d["cpu_count"] = os.cpu_count()
        if prior is not None:
            d["prior"] = prior
        d["schema_version"] = MANIFEST_SCHEMA_VERSION
        return _write_manifest_dict(directory, d)

    return _write_manifest_payload(directory, payload)


def _write_manifest_payload(directory: Path, payload: ManifestPayload) -> dict:
    """Serialise a ``ManifestPayload`` to disk and return the dict."""
    payload_dict = payload.to_dict()
    return _write_manifest_dict(directory, payload_dict)


def _write_manifest_dict(directory: Path, manifest: dict) -> dict:
    """Write the manifest dict to disk (shared by both code paths)."""
    (directory / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    # Sidecars preserved verbatim for downstream grep-compatibility.
    if "git_sha" in manifest:
        (directory / "git_sha.txt").write_text(
            str(manifest["git_sha"]) + "\n", encoding="utf-8")
    if "urdf_sha" in manifest:
        (directory / "urdf_sha.txt").write_text(
            str(manifest["urdf_sha"]) + "\n", encoding="utf-8")
    if "sim_sha" in manifest:
        (directory / "sim_sha.txt").write_text(
            str(manifest["sim_sha"]) + "\n", encoding="utf-8")
    if "seed" in manifest:
        (directory / "seed.txt").write_text(
            str(manifest["seed"]) + "\n", encoding="utf-8")
    return manifest


__all__ = ["write_manifest", "ManifestPayload", "MANIFEST_SCHEMA_VERSION"]
