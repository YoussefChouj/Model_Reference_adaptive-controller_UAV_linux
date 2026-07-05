"""Lyapunov drive signal ``s = e_v^T P B`` — the one scalar that differs between
adaptive-law variants.

The weight update is identical across laws (``grad = -s * Phi / denom``); only how
the drive ``s`` is formed changes. Isolating it here turns "which Lyapunov drive"
into a real seam: a future law (a closed-loop reference-model term, a set-theoretic
barrier weighting, ...) becomes a new Drive adapter rather than another branch
inside ``AdaptiveLaw.update``. Two adapters today (scalar + state-space) = a real
seam, not a hypothetical one.

All drives share one interface so the caller passes the same arguments regardless:
  * ``PBe``  — the (tanh-saturated) tracking error e that enters the drive.
  * ``P``    — the scalar heuristic gain 1/(2*wn) (ADR-0003).
  * ``e_dot``— filtered rate-derivative tracking error (ADR-0007).
  * ``Pe``/``Pedot`` — the 2nd column of the Lyapunov matrix P (ADR-0007).
"""
from __future__ import annotations

from typing import Protocol


class Drive(Protocol):
    """Maps the error state to the Lyapunov drive scalar ``s``."""

    def __call__(self, *, PBe: float, P: float, e_dot: float,
                 Pe: float, Pedot: float) -> float: ...


def scalar_drive(*, PBe: float, P: float, e_dot: float,
                 Pe: float, Pedot: float) -> float:
    """ADR-0003 scalar heuristic: ``s = e * P`` (1st-order / passthrough).

    ``e_dot``/``Pe``/``Pedot`` are unused — the scalar law ignores the
    rate-derivative error state.
    """
    return PBe * P


def state_space_drive(*, PBe: float, P: float, e_dot: float,
                      Pe: float, Pedot: float) -> float:
    """ADR-0007 state-space matrix-P drive: ``s = e_v^T P B = e*Pe + e_dot*Pedot``.

    With adaptive-input direction ``B = [0; 1]`` only the 2nd column of P matters,
    so the full matrix reduces to ``(Pe, Pedot)``. ``P`` is unused here.
    """
    return PBe * Pe + e_dot * Pedot


def for_law(state_space: bool) -> Drive:
    """Select the Drive adapter (state-space matrix-P vs scalar heuristic)."""
    return state_space_drive if state_space else scalar_drive
