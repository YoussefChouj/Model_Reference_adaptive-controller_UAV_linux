"""TDD — RegressorVariant + BasisDeclaration seam (ADR-0014 D3/D4).

Covers:
- RegressorVariant registry lifecycle (create, register, get, all, frozen)
- BasisDeclaration fields including normalise_via
- set_basis_declarations wiring for RegressorVariant.DEFAULT
- structured_regressor cross-variant seam: variant name mismatch raises
- scale_vector and has_trivial_normalise properties
- to_phi classmethod (in RegressorVariant; called by structured_regressor)
"""
import numpy as np
import pytest

from sim.priors import BasisDeclaration, Prior, RegressorVariant
from sim.regressor import (BASIS_DEFAULT, BASIS_INERTIA_SCALED,
                           structured_regressor)


# ------------------------------------------------------------------
# BasisDeclaration
# ------------------------------------------------------------------
def test_basis_declaration_fields():
    b = BasisDeclaration(
        name="rate",
        input="x",
        dimension="rad/s",
        normalise=20.0,
        normalise_via="e_sat",
    )
    assert b.name == "rate"
    assert b.input == "x"
    assert b.dimension == "rad/s"
    assert b.normalise == 20.0
    assert b.normalise_via == "e_sat"


def test_basis_declaration_normalise_via_defaults_none():
    b = BasisDeclaration(name="bias", input="const", dimension="1", normalise=1.0)
    assert b.normalise_via is None


# ------------------------------------------------------------------
# Registry lifecycle
# ------------------------------------------------------------------
def test_registry_all_includes_default_and_inertia_scaled():
    names = RegressorVariant.all()
    assert "default" in names
    assert "inertia_scaled" in names


def test_registry_get_returns_correct_instance():
    v = RegressorVariant.get("default")
    assert v.name == "default"
    assert v.num_basis == 6


def test_registry_frozen_rejects_duplicate():
    with pytest.raises(ValueError, match="already registered"):
        RegressorVariant.register(name="default", num_basis=6)


def test_registry_unknown_raises_keyerror():
    with pytest.raises(KeyError, match="unknown RegressorVariant"):
        RegressorVariant.get("nonexistent")


def test_registry_register_with_declarations():
    decls = (
        BasisDeclaration(name="bias", input="const", dimension="1", normalise=1.0),
        BasisDeclaration(name="rate", input="x", dimension="rad/s", normalise=10.0),
    )
    # Use a unique name to avoid polluting the global registry.
    name = "_test_reg_with_decls"
    v = RegressorVariant.register(name=name, num_basis=2, basis_declarations=decls)
    assert v.basis_declarations == decls
    assert v.num_basis == 2


# ------------------------------------------------------------------
# DEFAULT wiring
# ------------------------------------------------------------------
def test_default_basis_declarations_is_basis_default():
    """RegressorVariant.DEFAULT carries BASIS_DEFAULT (ADR-0014 D3)."""
    assert RegressorVariant.DEFAULT.basis_declarations == BASIS_DEFAULT
    assert len(RegressorVariant.DEFAULT.basis_declarations) == 6


def test_default_trivial_normalise():
    assert RegressorVariant.DEFAULT.has_trivial_normalise is True
    for b in RegressorVariant.DEFAULT.basis_declarations:
        assert b.normalise == 1.0


def test_inertia_scaled_nontrivial_normalise():
    v = RegressorVariant.get("inertia_scaled")
    assert v.has_trivial_normalise is False
    assert v.basis_declarations == BASIS_INERTIA_SCALED


def test_scale_vector_default_is_ones():
    sv = RegressorVariant.DEFAULT.scale_vector
    np.testing.assert_allclose(sv, np.ones(6), atol=1e-15)


def test_scale_vector_inertia_scaled():
    v = RegressorVariant.get("inertia_scaled")
    sv = v.scale_vector
    # bias (1.0), rate (1/20), drag (1/20), cross (1/400), u_nom (1.0), xm (1/20)
    expected = np.array([1.0, 0.05, 0.05, 0.0025, 1.0, 0.05])
    np.testing.assert_allclose(sv, expected, atol=1e-15)


def test_set_basis_declarations_overwrites_empty():
    """set_basis_declarations attaches BASIS_DEFAULT to the pre-created DEFAULT."""
    # The default already has declarations (wired at import); this tests the
    # overwrite-guard path by confirming a second call raises.
    with pytest.raises(ValueError, match="cannot overwrite"):
        RegressorVariant.set_basis_declarations("default", BASIS_DEFAULT)


# ------------------------------------------------------------------
# structured_regressor — variant seam
# ------------------------------------------------------------------
def test_default_variant_bit_identical_to_no_variant():
    """structured_regressor(variant=DEFAULT) == no variant argument."""
    phi_no_var = structured_regressor(
        "pitch", x=0.4, u_nom=-0.6, xm=0.25, cross=0.1
    )
    phi_var = structured_regressor(
        "pitch", x=0.4, u_nom=-0.6, xm=0.25, cross=0.1,
        variant=RegressorVariant.DEFAULT,
    )
    np.testing.assert_allclose(phi_var, phi_no_var, atol=1e-15)


def test_inertia_scaled_rescales_rate_and_xm_slots():
    """inertia_scaled divides slots 1,2,3,5 by ref_eff (20.0)."""
    v = RegressorVariant.get("inertia_scaled")
    phi_raw = structured_regressor(
        "yaw", x=1.0, u_nom=0.5, xm=0.8, cross=0.0
    )
    phi_scaled = structured_regressor(
        "yaw", x=1.0, u_nom=0.5, xm=0.8, cross=0.0,
        variant=v,
    )
    ref = 20.0
    # Slot 0 (bias): unchanged
    assert phi_scaled[0] == phi_raw[0] == 1.0
    # Slot 1 (rate): x / ref
    np.testing.assert_allclose(phi_scaled[1], 1.0 / ref, atol=1e-15)
    # Slot 2 (drag): x*tanh(x) / ref
    np.testing.assert_allclose(phi_scaled[2], (1.0 * np.tanh(1.0)) / ref, atol=1e-15)
    # Slot 3 (cross): unchanged for yaw
    assert phi_scaled[3] == phi_raw[3] == 0.0
    # Slot 4 (u_nom): unchanged
    assert phi_scaled[4] == phi_raw[4] == 0.5
    # Slot 5 (xm): xm / ref
    np.testing.assert_allclose(phi_scaled[5], 0.8 / ref, atol=1e-15)


def test_cross_variant_seam_pitch_roll():
    """inertia_scaled cross term is rescaled for pitch/roll."""
    v = RegressorVariant.get("inertia_scaled")
    cross = 0.08
    phi_raw = structured_regressor(
        "pitch", x=0.3, u_nom=0.2, xm=0.1, cross=cross
    )
    phi_scaled = structured_regressor(
        "pitch", x=0.3, u_nom=0.2, xm=0.1, cross=cross,
        variant=v,
    )
    ref = 20.0
    np.testing.assert_allclose(phi_scaled[3], cross / (ref * ref), atol=1e-15)


# ------------------------------------------------------------------
# cross-variant prior rejection (ADR-0014 D4)
# ------------------------------------------------------------------
def test_prior_construction_unknown_variant_raises():
    """Prior construction rejects an unregistered variant id."""
    with pytest.raises(ValueError, match="unknown regressor variant"):
        Prior(theta_tilde=np.zeros(6), plant_tag=(165.0, 19.8, 0.015),
              regressor_variant_id="not_a_real_variant", source_scenario="x")

# Prior.convert_to cross-variant is already tested in test_priors.py;
# we add a focused seam test here.


def test_convert_to_cross_variant_raises():
    """ADR-0014 D4: convert_to(target_variant=...) that switches variant raises."""
    from sim.priors import Prior
    p = Prior(theta_tilde=np.zeros(6), plant_tag=(165.0, 19.8, 0.015),
              regressor_variant_id="default", source_scenario="x")
    with pytest.raises(ValueError, match="cross-variant prior transfer is forbidden"):
        p.convert_to((820.0, 19.8, 0.015), target_variant_id="inertia_scaled")


# ------------------------------------------------------------------
# BasisDeclaration normalise_via informational field
# ------------------------------------------------------------------
def test_basis_default_normalise_via():
    """BASIS_DEFAULT slots carry informational normalise_via values."""
    names_and_via = {b.name: b.normalise_via for b in BASIS_DEFAULT}
    assert names_and_via["bias"] is None
    assert names_and_via["rate"] == "e_sat"
    assert names_and_via["u_nom"] == "u_max"


def test_basis_inertia_scaled_normalise_via():
    """BASIS_INERTIA_SCALED uses the same normalise_via references."""
    names_and_via = {b.name: b.normalise_via for b in BASIS_INERTIA_SCALED}
    assert names_and_via["rate"] == "e_sat"
    assert names_and_via["u_nom"] == "u_max"
