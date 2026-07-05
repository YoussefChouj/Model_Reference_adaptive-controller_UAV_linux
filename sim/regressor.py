"""Structured regressor Phi(x) — PARITY: API/mrac.c:65-91 (MRAC_GenerateStructuredBasis).

Hand-ported (grill Option A) under the active firmware flags
USE_STRUCTURED_UNCERTAINTY=1 + INCLUDE_CONTROL_IN_REGRESSOR=1 => MAX_NUM_BASIS=6.
The golden-vector test (tests/test_regressor.py) pins these formulas; if mrac.c
drifts, that test fails. Keep this file and mrac.c:65-91 in lockstep.

Six terms: [bias, x, x*tanh x, cross_coupling, u_nom, xm], where the cross slot
is the gyroscopic coupling for pitch/roll and deliberately 0 for yaw/z (u_nom
already occupies slot 4, so a non-zero slot 3 would be collinear and drift).
"""
from __future__ import annotations

import math

import numpy as np

NUM_BASIS = 6  # MAX_NUM_BASIS with STRUCTURED + INCLUDE_CONTROL (mrac.h:80-96)

# axes whose slot-3 carries gyroscopic cross-coupling (others keep it empty)
_CROSS_AXES = ("pitch", "roll")


def structured_regressor(axis: str, *, x: float, u_nom: float, xm: float,
                         cross: float = 0.0) -> np.ndarray:
    """Build the 6-element Phi for one axis, mirroring mrac.c:65-91.

    ``cross`` is used only for pitch/roll; it is ignored for yaw/z (slot 3 = 0).
    """
    phi = np.empty(NUM_BASIS)
    phi[0] = 1.0                 # bias
    phi[1] = x                   # damping
    phi[2] = x * math.tanh(x)    # bounded nonlinear drag
    phi[3] = cross if axis in _CROSS_AXES else 0.0
    phi[4] = u_nom               # control scaling
    phi[5] = xm                  # reference feedforward
    return phi


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
