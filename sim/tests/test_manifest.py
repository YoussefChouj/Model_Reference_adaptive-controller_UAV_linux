"""Manifest tests for spec 4c."""
from __future__ import annotations

import json

from sim.manifest import write_manifest
from sim.scenarios_yaml import Scenario


def test_manifest_and_sidecars(tmp_path):
    write_manifest(
        tmp_path, scenario=Scenario("test", 1.0), seed=42,
        git_sha="abc123", sim_sha="sim123", urdf_sha="urdf123",
        wall_time_s=1.2, sim_time_s=1.0, exit_reason="completed",
        machine={"name": "test"},
    )
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    required = {
        "scenario", "seed", "git_sha", "sim_sha", "urdf_sha", "wall_time_s",
        "sim_time_s", "exit_reason", "machine", "python_version", "platform",
        "cpu_count", "gz_version",
    }
    assert required <= set(manifest)
    for name in ("git_sha.txt", "seed.txt", "urdf_sha.txt"):
        assert (tmp_path / name).read_text(encoding="utf-8").strip()
