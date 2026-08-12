"""Manifest tests (engine-agnostic, ADR-0012 D7).

The manifest must never shell out to an external binary (the Gazebo
version capture was removed). It records the plant name instead.

sim-arch-04: tests extended to cover ManifestPayload (schema 1.1).
"""
from __future__ import annotations

import json

from sim.manifest import write_manifest
from sim.manifest_schema import MANIFEST_SCHEMA_VERSION, ManifestPayload
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


# ---------------------------------------------------------------------------
# sim-arch-04: ManifestPayload (schema 1.1) tests
# ---------------------------------------------------------------------------

def test_manifest_schema_version_is_1_1(tmp_path):
    """Every manifest must carry schema_version = '1.1'."""
    payload = ManifestPayload(
        scenario={"name": "t"}, seed=1,
        git_sha="x", sim_sha="x", urdf_sha="x",
        wall_time_s=0.0, sim_time_s=0.0,
        exit_reason="ok", machine=None,
    )
    d = payload.to_dict()
    assert d.get("schema_version") == "1.1"
    assert MANIFEST_SCHEMA_VERSION == "1.1"
    write_manifest(tmp_path, payload=payload)
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest.get("schema_version") == "1.1"


def test_manifest_payload_omits_none_fields(tmp_path):
    """Fields with None value are omitted from the JSON, not emitted as null."""
    payload = ManifestPayload(
        scenario={"name": "t"}, seed=1,
        git_sha="x", sim_sha="x", urdf_sha="x",
        wall_time_s=0.0, sim_time_s=0.0,
        exit_reason="ok", machine=None,
        # all optional fields explicitly None
        spawn_z=None,
        envelope=None,
        regressor_variant_id=None,
        theta_tilde_raw=None,
        plant_tag=None,
        convergence=None,
        target_valid=None,
    )
    write_manifest(tmp_path, payload=payload)
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    for key in ("spawn_z", "envelope", "regressor_variant_id",
                "theta_tilde_raw", "plant_tag", "convergence", "target_valid"):
        assert key not in manifest, f"{key} should be omitted but is present: {manifest.get(key)}"


def test_manifest_payload_roundtrip_from_run_result_all_fields(tmp_path):
    """Every optional field round-trips through from_run_result -> to_dict."""
    result = {
        "scenario_dict": {"name": "step_roll", "axis": "roll"},
        "seed": 99,
        "git_sha": "abc000",
        "sim_sha": "sim000",
        "urdf_sha": "urdf000",
        "wall_time_s": 3.5,
        "sim_time_s": 3.0,
        "exit_reason": "completed",
        "machine": {"name": "ci"},
        "plant_name": "identified",
        "spawn_z": 1.5,
        "envelope": "deployment",
        "regressor_variant_id": "v3",
        "theta_tilde_raw": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6],
        "plant_tag": [1.5, -2.0, 0.05],          # list — converted to tuple
        "convergence": {
            "weight_drift": 1e-4,
            "drive_rms": 5e-3,
            "final_norm": 0.8,
            "max_norm": 1.2,
            "well_posed": True,
        },
        "target_valid": True,
    }
    payload = ManifestPayload.from_run_result(result)
    d = payload.to_dict()

    assert d["schema_version"] == "1.1"
    assert d["envelope"] == "deployment"
    assert d["regressor_variant_id"] == "v3"
    assert d["theta_tilde_raw"] == [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]
    assert d["plant_tag"] == (1.5, -2.0, 0.05)   # python tuple in-memory
    assert d["convergence"] == result["convergence"]
    assert d["target_valid"] is True
    assert d["spawn_z"] == 1.5
    # round-trip: re-serialise through write_manifest and verify the JSON
    write_manifest(tmp_path, payload=payload)
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    # JSON has no tuple type; plant_tag serialises as a JSON array
    assert manifest["plant_tag"] == [1.5, -2.0, 0.05]
    # compare all other fields (plant_tag stripped — different types in dict vs JSON)
    d_cmp = {k: v for k, v in d.items() if k != "plant_tag"}
    m_cmp = {k: v for k, v in manifest.items() if k != "plant_tag"}
    assert d_cmp == m_cmp


def test_manifest_payload_envelope_learning(tmp_path):
    """Learning envelope is stored and round-trips."""
    result = {
        "scenario_dict": {"name": "t"},
        "seed": 1, "git_sha": "x", "sim_sha": "x", "urdf_sha": "x",
        "wall_time_s": 0.0, "sim_time_s": 0.0,
        "exit_reason": "ok", "machine": None,
        "envelope": "learning",
    }
    payload = ManifestPayload.from_run_result(result)
    d = payload.to_dict()
    assert d["envelope"] == "learning"
    write_manifest(tmp_path, payload=payload)
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["envelope"] == "learning"


def test_manifest_payload_target_valid_false(tmp_path):
    """target_valid=False is stored and round-trips."""
    result = {
        "scenario_dict": {"name": "t"},
        "seed": 1, "git_sha": "x", "sim_sha": "x", "urdf_sha": "x",
        "wall_time_s": 0.0, "sim_time_s": 0.0,
        "exit_reason": "ok", "machine": None,
        "target_valid": False,
    }
    payload = ManifestPayload.from_run_result(result)
    d = payload.to_dict()
    assert d["target_valid"] is False
    write_manifest(tmp_path, payload=payload)
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["target_valid"] is False


def test_manifest_payload_plant_tag_tuple_not_list(tmp_path):
    """plant_tag arrives as list, must serialise as tuple."""
    result = {
        "scenario_dict": {"name": "t"},
        "seed": 1, "git_sha": "x", "sim_sha": "x", "urdf_sha": "x",
        "wall_time_s": 0.0, "sim_time_s": 0.0,
        "exit_reason": "ok", "machine": None,
        "plant_tag": [2.0, -3.0, 0.04],
    }
    payload = ManifestPayload.from_run_result(result)
    assert payload.plant_tag == (2.0, -3.0, 0.04)
    d = payload.to_dict()
    assert isinstance(d["plant_tag"], tuple)
    assert d["plant_tag"] == (2.0, -3.0, 0.04)


def test_manifest_payload_prior_kwarg_backward_compat(tmp_path):
    """Legacy prior= kwarg is still emitted as a 'prior' block in the JSON."""
    write_manifest(
        tmp_path,
        scenario=Scenario("t", 1.0), seed=7,
        git_sha="abc", sim_sha="s", urdf_sha="u",
        wall_time_s=0.0, sim_time_s=0.0,
        exit_reason="ok", machine=None,
        prior={"theta_tilde": [0.01, 0.02]},
    )
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert "prior" in manifest
    assert manifest["prior"] == {"theta_tilde": [0.01, 0.02]}


def test_manifest_payload_from_run_result_minimal_result(tmp_path):
    """A result dict with only the required fields still builds a valid payload."""
    result = {
        "scenario_dict": {"name": "minimal"},
        "seed": 5,
        "git_sha": "a", "sim_sha": "b", "urdf_sha": "c",
        "wall_time_s": 1.0, "sim_time_s": 1.0,
        "exit_reason": "ok", "machine": None,
    }
    payload = ManifestPayload.from_run_result(result)
    d = payload.to_dict()
    assert d["scenario"] == {"name": "minimal"}
    assert d["seed"] == 5
    assert "envelope" not in d
    assert "theta_tilde_raw" not in d
    assert "schema_version" in d
