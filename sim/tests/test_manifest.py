"""Manifest tests (engine-agnostic, ADR-0012 D7).

The manifest must never shell out to an external binary (the Gazebo
version capture was removed). It records the plant name instead.
"""
from __future__ import annotations

import json

from sim.manifest import write_manifest
from sim.scenarios_yaml import Scenario


def test_manifest_and_sidecars(tmp_path):
    write_manifest(
        tmp_path, scenario=Scenario("test", 1.0), seed=42,
        git_sha="abc123", sim_sha="sim123", urdf_sha="urdf123",
        wall_time_s=1.2, sim_time_s=1.0, exit_reason="completed",
        machine={"name": "test"}, plant_name="mujoco",
    )
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    required = {
        "scenario", "seed", "git_sha", "sim_sha", "urdf_sha", "wall_time_s",
        "sim_time_s", "exit_reason", "machine", "plant_name", "python_version",
        "platform", "cpu_count",
    }
    assert required <= set(manifest)
    assert manifest["plant_name"] == "mujoco"
    # No gazebo trace in any serialised value.
    assert "gz" not in json.dumps(manifest).lower()
    for name in ("git_sha.txt", "seed.txt", "urdf_sha.txt"):
        assert (tmp_path / name).read_text(encoding="utf-8").strip()
