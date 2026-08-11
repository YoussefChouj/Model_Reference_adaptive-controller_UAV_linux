"""Structured regressor Phi(x) — PARITY: API/mrac.c:65-91 (MRAC_GenerateStructuredBasis).

Hand-ported (grill Option A) under the active firmware flags
USE_STRUCTURED_UNCERTAINTY=1 + INCLUDE_CONTROL_IN_REGRESSOR=1 => MAX_NUM_BASIS=6.
The golden-vector test (tests/test_regressor.py) pins these formulas; if mrac.c
drifts, that test fails. Keep this file and mrac.c:65-91 in lockstep.

Six terms: [bias, x, x*tanh x, cross_coupling, u_nom, xm], where the cross slot
is the gyroscopic coupling for pitch/roll and deliberately 0 for yaw/z (u_nom
already occupies slot 4, so a non-zero slot 3 would be collinear and drift).

ADR-0014 D3 promotes each basis function from a hand-derived slot to a
declared object carrying (input, dimension, normalise, normalise_via). The current
six-slot regressor is the pinned baseline (``BASIS_DEFAULT``); new variants
register their own basis lists via :class:`RegressorVariant`.

The module initialises ``RegressorVariant.DEFAULT`` with ``BASIS_DEFAULT`` after
both are defined (avoids circular import). ``RegressorVariant`` is defined in
``sim.priors`` and re-exported here for convenience.
"""
from __future__ import annotations

import math
from typing import Sequence

import numpy as np

from sim.priors import BasisDeclaration, RegressorVariant

NUM_BASIS = 6  # MAX_NUM_BASIS with STRUCTURED + INCLUDE_CONTROL (mrac.h:80-96)

# axes whose slot-3 carries gyroscopic cross-coupling (others keep it empty)
_CROSS_AXES = ("pitch", "roll")


# Pinned firmware baseline (mrac.c:65-91). Slot order is load-bearing — the
# golden-vector test in tests/test_regressor.py and the parity test against
# MRAC_GenerateStructuredBasis both index by position. Do not reorder.
#
# normalise_via is informational (ADR-0014 D3 open question: which reference
# scale to use at run time). The normalised value is stored here as `normalise`.
# For the "default" variant all normalise=1.0 so no rescaling is applied.
BASIS_DEFAULT: tuple[BasisDeclaration, ...] = (
    BasisDeclaration(name="bias", input="const", dimension="1", normalise=1.0,
                    normalise_via=None),
    BasisDeclaration(name="rate", input="x", dimension="rad/s", normalise=1.0,
                    normalise_via="e_sat"),
    BasisDeclaration(name="drag", input="x", dimension="1", normalise=1.0,
                    normalise_via="e_sat"),
    BasisDeclaration(name="cross", input="cross", dimension="rad^2/s^2",
                    normalise=1.0, normalise_via=None),
    BasisDeclaration(name="u_nom", input="u_nom", dimension="Nm", normalise=1.0,
                    normalise_via="u_max"),
    BasisDeclaration(name="xm", input="xm", dimension="rad/s", normalise=1.0,
                    normalise_via="e_sat"),
)
assert len(BASIS_DEFAULT) == NUM_BASIS

# Attach declarations to the pre-created DEFAULT singleton.
RegressorVariant.set_basis_declarations("default", BASIS_DEFAULT)


def _apply_variant_scale(
    phi: np.ndarray,
    declarations: Sequence[BasisDeclaration],
) -> np.ndarray:
    """Rescale a regressor vector against each basis's normalise scale.

    Slot ``i`` is multiplied by ``1.0 / declarations[i].normalise`` so a unit
    magnitude at the declared characteristic scale maps to ``1.0`` in the
    dimensionless space. When all normalise are ``1.0`` this is the identity,
    preserving bit-identical parity with the firmware baseline.
    """
    out = np.empty_like(phi)
    for i, b in enumerate(declarations):
        if b.normalise == 1.0:
            out[i] = phi[i]
        else:
            out[i] = phi[i] / b.normalise
    return out


def structured_regressor(axis: str, *, x: float, u_nom: float, xm: float,
                         cross: float = 0.0,
                         variant: RegressorVariant | None = None,
                         ) -> np.ndarray:
    """Build the 6-element Phi for one axis, mirroring mrac.c:65-91.

    ``cross`` is used only for pitch/roll; it is ignored for yaw/z (slot 3 = 0).
    ``variant`` selects a declared regressor variant (ADR-0014 D4). The default
    is the pinned firmware baseline; variants with non-trivial normalisation scales
    produce rescaled outputs that are sim-only until promoted with a parity test.
    """
    phi = np.empty(NUM_BASIS)
    phi[0] = 1.0                 # bias
    phi[1] = x                   # damping
    phi[2] = x * math.tanh(x)    # bounded nonlinear drag
    phi[3] = cross if axis in _CROSS_AXES else 0.0
    phi[4] = u_nom               # control scaling
    phi[5] = xm                  # reference feedforward
    if variant is None:
        return phi
    # "default" has trivial normalisation (all 1.0) — fast path.
    if variant.name == "default":
        return phi
    # Apply the variant's per-slot normalisation scale.
    return _apply_variant_scale(phi, variant.basis_declarations)


def cross_coupling(axis: str, *, pitch_rate: float, roll_rate: float,
                   yaw_rate: float) -> float:
    """Gyroscopic cross term for an axis (mrac.c:445-446).

    Firmware aliases p=pitch, q=roll, r=yaw; cross_pitch=q*r, cross_roll=p*r.
    """
    if axis == "pitch":
        return roll_rate * yaw_rate
    if axis == "roll":
        return pitch_rate * yaw_rate
    return 0.0  # yaw, z


# ---------------------------------------------------------------------------
# ADR-0014 D3 example variant: "inertia_scaled"
#
# Demonstrates the per-basis declaration seam end-to-end. The dimensionless
# rescale uses a characteristic rate ``ref_eff`` (rad/s) to pull the rate
# and reference slots toward O(1). Sim-only — no firmware parity test.
# ---------------------------------------------------------------------------
_INERTIA_SCALED_REF = 20.0  # rad/s, rough closed-loop inner-rate bandwidth

BASIS_INERTIA_SCALED: tuple[BasisDeclaration, ...] = (
    BasisDeclaration(name="bias", input="const", dimension="1", normalise=1.0,
                    normalise_via=None),
    BasisDeclaration(name="rate", input="x", dimension="rad/s",
                    normalise=_INERTIA_SCALED_REF,
                    normalise_via="e_sat"),
    BasisDeclaration(name="drag", input="x", dimension="1",
                    normalise=_INERTIA_SCALED_REF,
                    normalise_via="e_sat"),
    BasisDeclaration(name="cross", input="cross", dimension="rad^2/s^2",
                    normalise=_INERTIA_SCALED_REF * _INERTIA_SCALED_REF,
                    normalise_via=None),
    BasisDeclaration(name="u_nom", input="u_nom", dimension="Nm", normalise=1.0,
                    normalise_via="u_max"),
    BasisDeclaration(name="xm", input="xm", dimension="rad/s",
                    normalise=_INERTIA_SCALED_REF,
                    normalise_via="e_sat"),
)

# Register the inertia-scaled variant with its declarations.
RegressorVariant.register(name="inertia_scaled",
                          num_basis=len(BASIS_INERTIA_SCALED),
                          basis_declarations=BASIS_INERTIA_SCALED)


def regressor_inertia_scaled(axis: str, *, x: float, u_nom: float,
                             xm: float, cross: float = 0.0,
                             ref_eff: float = _INERTIA_SCALED_REF) -> np.ndarray:
    """Affine-rescaled variant (ADR-0014 D3 example).

    Slot 1, 2, 3, 5 are rescaled by ``ref_eff`` so a typical 20 rad/s
    response maps to slot magnitudes near 1. Sim-only.
    """
    variant = RegressorVariant.get("inertia_scaled")
    return structured_regressor(axis, x=x, u_nom=u_nom, xm=xm,
                                cross=cross, variant=variant)
