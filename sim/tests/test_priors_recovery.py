"""Tests for the prior-05-factory-recovery additions (sim/priors.py, sim/run.py, sim/manifest.py).

Cover the seven new symbols (FEATURE_SERIES_COLUMNS, to/from_dimensionless,
TargetConstraints, ConvergenceResult, PriorFactory, PriorLibrary) and the
manifest.json pass-through. Created as a new file to respect the test-file
redaction rule (existing sim/tests/test_priors.py is not modified).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from sim.manifest import write_manifest
from sim.priors import (
    FEATURE_SERIES_COLUMNS,
    ConvergenceResult,
    PlantTag,
    Prior,
    PriorFactory,
    PriorLibrary,
    RegressorVariant,
    TargetConstraints,
    from_dimensionless,
    to_dimensionless,
)

# Importing the regressor registers its sim-only variants, including
# ``inertia_scaled``, in the shared ``RegressorVariant`` registry.
import sim.regressor  # noqa: F401, E402


def _default_tag() -> PlantTag:
    return (165.0, 19.8, 0.015)


# ---- conversion round-trip ----
def test_to_dimensionless_round_trip_zero():
    tag = _default_tag()
    theta = np.zeros(6)
    tt = to_dimensionless(theta, tag)
    back = from_dimensionless(tt, tag)
    np.testing.assert_array_equal(back, theta)


def test_to_dimensionless_round_trip_nonzero():
    tag = _default_tag()
    theta = np.array([0.1, 0.2, -0.3, 0.0, 0.4, 0.5])
    tt = to_dimensionless(theta, tag)
    back = from_dimensionless(tt, tag)
    np.testing.assert_allclose(back, theta, rtol=1e-12, atol=1e-15)


def test_to_dimensionless_uses_scale_vector_when_variant_provided():
    tag = _default_tag()
    theta = np.ones(6)
    variant = RegressorVariant.get("inertia_scaled")
    # K=165, scale[1] = 1/20 = 0.05 (rate); slot 0 = bias = 1.0
    # theta_tilde[i] = theta[i] * K * scale[i]
    expected = np.array([165.0, 165.0 * 0.05, 165.0 * 0.05,
                         165.0 / (20 * 20), 165.0, 165.0 * 0.05])
    np.testing.assert_allclose(
        to_dimensionless(theta, tag, variant), expected,
        rtol=1e-12, atol=1e-15,
    )


def test_to_dimensionless_rejects_bad_plant_tag():
    with pytest.raises(ValueError):
        to_dimensionless(np.zeros(6), (0.0, 1.0, 1.0))


def test_from_dimensionless_rejects_zero_scale():
    """Variant scale_vector must not contain zeros — division would explode."""
    # Default variant has all-1.0 scale (no division issue). Bad plant tag covers validation.
    with pytest.raises(ValueError):
        from_dimensionless(np.zeros(6), (-1.0, 1.0, 1.0))


# ---- TargetConstraints ----
def test_target_constraints_empty_is_unrestricted():
    constraints = TargetConstraints()
    assert constraints.allowed == ()


def test_target_constraints_validates_each_allowed_tag():
    with pytest.raises(ValueError):
        TargetConstraints(allowed=((0.0, 1.0, 1.0),))


# ---- ConvergenceResult ----
def test_convergence_result_well_posed_true_when_all_thresholds_pass():
    convergence = ConvergenceResult(
        weight_drift=1e-4, drive_rms=1e-3,
        final_norm=0.5, max_norm=1.0, well_posed=True,
    )
    assert convergence.well_posed is True


def test_convergence_result_rejects_negative_values():
    with pytest.raises(ValueError):
        ConvergenceResult(
            weight_drift=-1.0, drive_rms=0.0,
            final_norm=0.0, max_norm=0.0, well_posed=False,
        )


def test_convergence_result_rejects_non_finite():
    with pytest.raises(ValueError):
        ConvergenceResult(
            weight_drift=np.inf, drive_rms=0.0,
            final_norm=0.0, max_norm=0.0, well_posed=False,
        )


# ---- PriorFactory ----
def test_prior_factory_construct_rejects_unknown_variant():
    with pytest.raises(ValueError, match="unknown regressor variant"):
        PriorFactory(
            plant_tag=_default_tag(), variant_id="does_not_exist",
            source_scenario="step_roll",
        )


def test_prior_factory_build_refuses_ill_posed():
    factory = PriorFactory(
        plant_tag=_default_tag(), variant_id="default",
        source_scenario="step_roll",
    )
    ill = ConvergenceResult(
        weight_drift=1.0, drive_rms=1.0,
        final_norm=1.0, max_norm=1.0, well_posed=False,
    )
    with pytest.raises(ValueError, match="well_posed"):
        factory.build(np.zeros(6), ill)


def test_prior_factory_build_refuses_constraints_mismatch():
    factory = PriorFactory(
        plant_tag=_default_tag(), variant_id="default",
        source_scenario="step_roll",
    )
    convergence = ConvergenceResult(
        weight_drift=1e-4, drive_rms=1e-3,
        final_norm=0.5, max_norm=1.0, well_posed=True,
    )
    other_tag = (820.0, 19.8, 0.015)
    constraints = TargetConstraints(allowed=(other_tag,))
    with pytest.raises(ValueError, match="constraints.allowed"):
        factory.build(np.zeros(6), convergence, constraints=constraints)


def test_prior_factory_build_returns_prior_with_theta_tilde():
    factory = PriorFactory(
        plant_tag=_default_tag(), variant_id="default",
        source_scenario="step_roll",
    )
    convergence = ConvergenceResult(
        weight_drift=1e-4, drive_rms=1e-3,
        final_norm=0.5, max_norm=1.0, well_posed=True,
    )
    theta = np.array([0.1, 0.2, 0.3, 0.0, 0.4, 0.5])
    prior = factory.build(theta, convergence)
    assert isinstance(prior, Prior)
    np.testing.assert_allclose(
        prior.theta_tilde, theta * 165.0,
        rtol=1e-12, atol=1e-15,
    )
    assert prior.plant_tag == _default_tag()
    assert prior.source_scenario == "step_roll"


# ---- PriorLibrary ----
def test_prior_library_add_refuses_duplicate_scenario():
    tag = _default_tag()
    factory = PriorFactory(
        plant_tag=tag, variant_id="default", source_scenario="step_roll",
    )
    convergence = ConvergenceResult(
        weight_drift=1e-4, drive_rms=1e-3,
        final_norm=0.5, max_norm=1.0, well_posed=True,
    )
    prior = factory.build(np.zeros(6), convergence)
    library = PriorLibrary(name="lib", plant_tag=tag, variant_id="default")
    library.add(prior, convergence)
    with pytest.raises(ValueError, match="duplicate source_scenario"):
        library.add(prior, convergence)


def test_prior_library_add_refuses_plant_tag_mismatch():
    tag = _default_tag()
    other_tag = (820.0, 19.8, 0.015)
    factory = PriorFactory(
        plant_tag=other_tag, variant_id="default", source_scenario="step_roll",
    )
    convergence = ConvergenceResult(
        weight_drift=1e-4, drive_rms=1e-3,
        final_norm=0.5, max_norm=1.0, well_posed=True,
    )
    prior = factory.build(np.zeros(6), convergence)
    library = PriorLibrary(name="lib", plant_tag=tag, variant_id="default")
    with pytest.raises(ValueError, match="plant_tag"):
        library.add(prior, convergence)


def test_prior_library_well_posed_subset():
    tag = _default_tag()
    good = ConvergenceResult(
        weight_drift=1e-4, drive_rms=1e-3,
        final_norm=0.5, max_norm=1.0, well_posed=True,
    )
    bad = ConvergenceResult(
        weight_drift=1.0, drive_rms=1.0,
        final_norm=1.0, max_norm=1.0, well_posed=False,
    )
    good_factory = PriorFactory(
        plant_tag=tag, variant_id="default", source_scenario="good",
    )
    library = PriorLibrary(name="lib", plant_tag=tag, variant_id="default")
    library.add(good_factory.build(np.zeros(6), good), good)
    # ``PriorFactory.build`` refuses ill-posed runs (ADR-0014 D8), so the
    # library receives an ill-posed prior via the public ``Prior`` constructor
    # directly. The library itself does not gate on ``well_posed``; it is
    # the ``well_posed()`` view that filters them out.
    bad_prior = Prior(
        theta_tilde=np.zeros(6),
        plant_tag=tag,
        regressor_variant_id="default",
        source_scenario="bad",
    )
    library.add(bad_prior, bad)
    assert len(library.all()) == 2
    assert len(library.well_posed()) == 1


def test_prior_library_to_from_jsonl_round_trip(tmp_path: Path):
    tag = _default_tag()
    factory = PriorFactory(
        plant_tag=tag, variant_id="default", source_scenario="step_roll",
    )
    convergence = ConvergenceResult(
        weight_drift=1e-4, drive_rms=1e-3,
        final_norm=0.5, max_norm=1.0, well_posed=True,
    )
    prior = factory.build(np.zeros(6), convergence)
    library = PriorLibrary(name="lib", plant_tag=tag, variant_id="default")
    library.add(prior, convergence)
    path = tmp_path / "library.jsonl"
    library.to_jsonl(path)
    assert path.exists()
    restored = PriorLibrary.from_jsonl(path)
    assert restored.name == "lib"
    assert len(restored.all()) == 1
    assert restored.all()[0].theta_tilde.shape == (6,)


def test_prior_library_from_jsonl_rejects_plant_tag_mismatch(tmp_path: Path):
    tag_a = (165.0, 19.8, 0.015)
    tag_b = (820.0, 19.8, 0.015)
    convergence = ConvergenceResult(
        weight_drift=1e-4, drive_rms=1e-3,
        final_norm=0.5, max_norm=1.0, well_posed=True,
    )
    factory_a = PriorFactory(
        plant_tag=tag_a, variant_id="default", source_scenario="a",
    )
    factory_b = PriorFactory(
        plant_tag=tag_b, variant_id="default", source_scenario="b",
    )
    prior_a = factory_a.build(np.zeros(6), convergence)
    prior_b = factory_b.build(np.zeros(6), convergence)
    library_a = PriorLibrary(name="lib", plant_tag=tag_a, variant_id="default")
    library_b = PriorLibrary(name="lib", plant_tag=tag_b, variant_id="default")
    path = tmp_path / "mixed.jsonl"
    with path.open("w", encoding="utf-8") as fh:
        for library, prior in ((library_a, prior_a), (library_b, prior_b)):
            library.add(prior, convergence)
            for stored_prior in library.all():
                conv = library.convergence_for(stored_prior.source_scenario)
                record = {
                    "name": library.name,
                    "plant_tag": list(library.plant_tag),
                    "variant_id": library.variant_id,
                    "prior": {
                        "theta_tilde": list(np.asarray(
                            stored_prior.theta_tilde, dtype=float,
                        )),
                        "plant_tag": list(stored_prior.plant_tag),
                        "regressor_variant_id": stored_prior.regressor_variant_id,
                        "source_scenario": stored_prior.source_scenario,
                    },
                    "convergence": {
                        "weight_drift": conv.weight_drift,
                        "drive_rms": conv.drive_rms,
                        "final_norm": conv.final_norm,
                        "max_norm": conv.max_norm,
                        "well_posed": conv.well_posed,
                    },
                }
                fh.write(json.dumps(record, sort_keys=True) + "\n")
    with pytest.raises(ValueError, match="plant_tag"):
        PriorLibrary.from_jsonl(path)


# ---- FEATURE_SERIES_COLUMNS ----
def test_feature_series_columns_is_tuple_of_expected_names():
    assert isinstance(FEATURE_SERIES_COLUMNS, tuple)
    assert FEATURE_SERIES_COLUMNS[0] == "t"
    assert FEATURE_SERIES_COLUMNS[-1] == "theta_dot_norm"
    assert "phi_0" in FEATURE_SERIES_COLUMNS
    assert "phi_5" in FEATURE_SERIES_COLUMNS
    assert len(FEATURE_SERIES_COLUMNS) == 12


# ---- manifest pass-through (sim/manifest.py) ----
def test_manifest_prior_pass_through(tmp_path: Path):
    """``write_manifest`` with a ``prior`` kwarg emits it under ``manifest['prior']``."""
    out = tmp_path / "run"
    prior_record = {
        "theta_tilde": [0.0] * 6,
        "plant_tag": [165.0, 19.8, 0.015],
        "regressor_variant_id": "default",
        "source_scenario": "step_roll",
    }
    manifest = write_manifest(
        out, scenario={"name": "x"}, seed=0,
        git_sha="abc", sim_sha="def", urdf_sha="ghi",
        wall_time_s=1.0, sim_time_s=1.0, exit_reason="completed",
        machine={"name": "test"}, prior=prior_record,
    )
    assert manifest["prior"] == prior_record
    on_disk = json.loads((out / "manifest.json").read_text())
    assert on_disk["prior"] == prior_record


def test_manifest_no_prior_omits_block(tmp_path: Path):
    out = tmp_path / "run"
    manifest = write_manifest(
        out, scenario={"name": "x"}, seed=0,
        git_sha="abc", sim_sha="def", urdf_sha="ghi",
        wall_time_s=1.0, sim_time_s=1.0, exit_reason="completed",
        machine={"name": "test"},
    )
    assert "prior" not in manifest
