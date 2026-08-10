"""TDD — sim/priors.py (ADR-0014 D1-D4, ADR-0013 D5).

Pins the dimensionless prior object: stored ``theta_tilde = K * Theta`` plus
the source plant tag ``(K, p, T)``. Conversion cross-plant is the
``convert_to(target_tag)`` method; the Prior must reject unconverted
cross-plant application by construction. The :class:`RegressorVariant`
registry keeps regressor provenance tied to the prior.
"""
import numpy as np
import pytest

from sim.priors import Prior, RegressorVariant


def _default_tag():
    """Canonical airframe roll plant (docs/sysid_results.md)."""
    return (165.0, 19.8, 0.015)


def _other_tag():
    """A second plant — hypothetical Crazyflie-class, gain ~5x larger."""
    return (820.0, 19.8, 0.015)


# ----------------------------------------------------------------------
# Theta_tilde storage and basic invariants
# ----------------------------------------------------------------------
def test_theta_tilde_stored_and_round_trip():
    tag = _default_tag()
    theta_tilde = np.array([0.5, 0.1, 0.2, 0.0, 0.3, 0.4])
    p = Prior(theta_tilde=theta_tilde, plant_tag=tag,
              regressor_variant_id="default", source_scenario="step_roll")
    # Stored object is a 1-D float array.
    assert p.theta_tilde.shape == (6,)
    assert p.theta_tilde.dtype == float
    # Plant tag preserved verbatim.
    assert p.plant_tag == tag
    assert p.K == 165.0 and p.p == 19.8 and p.T == 0.015


def test_to_raw_recovers_theta_on_source_plant():
    """``Theta = theta_tilde / K_source`` (ADR-0014 D1)."""
    K = 165.0
    theta_tilde = np.array([K * 0.1, K * 0.2, K * 0.3, K * 0.0, K * 0.4, K * 0.5])
    p = Prior(theta_tilde=theta_tilde, plant_tag=(K, 19.8, 0.015),
              regressor_variant_id="default", source_scenario="step_roll")
    raw = p.to_raw()
    np.testing.assert_allclose(raw, np.array([0.1, 0.2, 0.3, 0.0, 0.4, 0.5]),
                               rtol=1e-12, atol=1e-15)


def test_prior_rejects_non_finite_theta():
    with pytest.raises(ValueError):
        Prior(theta_tilde=np.array([np.inf, 0.0, 0.0, 0.0, 0.0, 0.0]),
              plant_tag=_default_tag(), regressor_variant_id="default",
              source_scenario="step_roll")


def test_prior_rejects_bad_plant_tag():
    # Non-positive K
    with pytest.raises(ValueError):
        Prior(theta_tilde=np.zeros(6), plant_tag=(0.0, 19.8, 0.015),
              regressor_variant_id="default", source_scenario="x")
    # Negative T
    with pytest.raises(ValueError):
        Prior(theta_tilde=np.zeros(6), plant_tag=(165.0, 19.8, -0.001),
              regressor_variant_id="default", source_scenario="x")
    # Wrong arity
    with pytest.raises(ValueError):
        Prior(theta_tilde=np.zeros(6), plant_tag=(165.0, 19.8),
              regressor_variant_id="default", source_scenario="x")
    # Not a tuple
    with pytest.raises(ValueError):
        Prior(theta_tilde=np.zeros(6), plant_tag=[165.0, 19.8, 0.015],
              regressor_variant_id="default", source_scenario="x")


# ----------------------------------------------------------------------
# Plant-tag mismatch rejection
# ----------------------------------------------------------------------
def test_convert_to_records_target_tag_and_preserves_theta_tilde():
    """ADR-0014 D1: the dimensionless object is plant-invariant.

    ``convert_to`` must update ``plant_tag`` to the target but leave
    ``theta_tilde`` unchanged — deployment on the target then recovers
    ``Theta_target = theta_tilde / K_target`` which is scaled by
    ``K_source / K_target`` relative to the source ``Theta``.
    """
    src_tag = _default_tag()    # K=165
    tgt_tag = _other_tag()      # K=820
    theta_tilde = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    p_src = Prior(theta_tilde=theta_tilde, plant_tag=src_tag,
                  regressor_variant_id="default", source_scenario="step_roll")
    p_tgt = p_src.convert_to(tgt_tag)
    # Plant tag now the target.
    assert p_tgt.plant_tag == tgt_tag
    # theta_tilde is the dimensionless object — unchanged.
    np.testing.assert_array_equal(p_tgt.theta_tilde, theta_tilde)
    # Deployment on the target gives a smaller Theta (smaller authority per gain).
    np.testing.assert_allclose(p_tgt.to_raw(), theta_tilde / tgt_tag[0],
                               rtol=1e-12, atol=1e-15)


def test_cross_plant_with_conversion_round_trip():
    """Convert to a different plant, back to source, recover the original."""
    src_tag = _default_tag()
    tgt_tag = _other_tag()
    p_src = Prior(theta_tilde=np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0]),
                  plant_tag=src_tag, regressor_variant_id="default",
                  source_scenario="step_roll")
    p_tgt = p_src.convert_to(tgt_tag)
    p_back = p_tgt.convert_to(src_tag)
    np.testing.assert_allclose(p_back.theta_tilde, p_src.theta_tilde,
                               rtol=1e-15, atol=1e-15)
    assert p_back.plant_tag == src_tag


# ----------------------------------------------------------------------
# Variant mismatch rejection
# ----------------------------------------------------------------------
def test_unknown_variant_rejected_at_construction():
    with pytest.raises(ValueError):
        Prior(theta_tilde=np.zeros(6), plant_tag=_default_tag(),
              regressor_variant_id="not_a_real_variant",
              source_scenario="step_roll")


def test_length_mismatch_with_variant_rejected():
    # default variant is num_basis=6; a 4-vector must be rejected.
    with pytest.raises(ValueError):
        Prior(theta_tilde=np.zeros(4), plant_tag=_default_tag(),
              regressor_variant_id="default", source_scenario="step_roll")


def test_convert_to_cross_variant_rejected():
    """ADR-0014 D4: cross-variant transfer is forbidden.

    The default variant is a different ``RegressorVariant`` instance from
    any user-registered variant, so convert_to(target, target_variant_id=...)
    that switches variants raises.
    """
    # Register a transient second variant for the test, isolated to this
    # module's lifetime (the registry persists across tests, so the name
    # must be unique to avoid collisions).
    test_variant_name = "_test_alternate"
    if test_variant_name not in RegressorVariant.names():
        RegressorVariant.register(name=test_variant_name, num_basis=6)
    p = Prior(theta_tilde=np.zeros(6), plant_tag=_default_tag(),
              regressor_variant_id="default", source_scenario="x")
    with pytest.raises(ValueError):
        p.convert_to(_other_tag(), target_variant_id=test_variant_name)


# ----------------------------------------------------------------------
# RegressorVariant registry
# ----------------------------------------------------------------------
def test_registry_get_default_and_names():
    assert RegressorVariant.get("default") is RegressorVariant.DEFAULT
    assert "default" in RegressorVariant.names()


def test_registry_rejects_duplicate_name():
    with pytest.raises(ValueError):
        RegressorVariant.register(name="default", num_basis=6)  # already taken


def test_registry_unknown_raises():
    with pytest.raises(KeyError):
        RegressorVariant.get("definitely_not_a_real_variant")


# ----------------------------------------------------------------------
# Immutability
# ----------------------------------------------------------------------
def test_prior_is_frozen():
    p = Prior(theta_tilde=np.zeros(6), plant_tag=_default_tag(),
              regressor_variant_id="default", source_scenario="x")
    with pytest.raises(Exception):
        p.source_scenario = "y"   # frozen dataclass
    # Mutating the stored array's contents from outside is allowed (numpy
    # is not deep-copied) — that's the documented escape hatch and the
    # same behaviour as a typical dataclass + numpy. Just confirm the
    # dataclass field itself rejects reassignment.
    with pytest.raises(Exception):
        p.plant_tag = (1.0, 1.0, 0.0)


def test_convert_to_returns_new_prior():
    p = Prior(theta_tilde=np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0]),
              plant_tag=_default_tag(), regressor_variant_id="default",
              source_scenario="step_roll")
    p2 = p.convert_to(_other_tag())
    assert p2 is not p
    assert p.plant_tag == _default_tag()           # source unchanged
    assert p2.plant_tag == _other_tag()


def test_with_scenario_overrides_only_scenario():
    p = Prior(theta_tilde=np.zeros(6), plant_tag=_default_tag(),
              regressor_variant_id="default", source_scenario="a")
    p2 = p.with_scenario("b")
    assert p.source_scenario == "a"
    assert p2.source_scenario == "b"
    assert p.plant_tag == p2.plant_tag
    np.testing.assert_array_equal(p.theta_tilde, p2.theta_tilde)