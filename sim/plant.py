"""Plant models behind a common seam (ADR-0006 D3/D4).

The plant boundary is the inner *rate* loop: a per-axis command goes in,
a body rate comes out. Outer position/attitude loops live in baseline.py,
never here. The controller and adaptive law must not know which plant is
behind ``step`` — that is what lets us swap identified-linear -> 6-DOF ->
Gazebo as a one-file change.

Phase-1 plant = the identified models in docs/sysid_results.md:
    G(s) = K / (s*(1 + s/p)) * e^(-sT)      roll/pitch  (rel-degree 2 + delay)
    G(s) = K / s                            yaw         (pure integrator)

Command units are the firmware u (u_nom + u_ad), not SI Nm: the identified K
folds in torque effectiveness and 1/J, so feeding the same command the
firmware computes reproduces the same rate (parity).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

import numpy as np
from scipy.signal import cont2discrete

# axis command key -> firmware body-rate output key
_RATE_KEY = {"roll": "p", "pitch": "q", "yaw": "r", "z": "vz"}


@dataclass(frozen=True)
class AxisModel:
    """Identified per-axis rate plant ``K/(s(1+s/p))*e^{-sT}``.

    ``pole=None`` selects the pure-integrator ``K/s`` realisation (yaw).
    ``delay`` is the transport delay T in seconds (0 = no delay).
    """
    K: float
    pole: Optional[float] = None
    delay: float = 0.0


# Single source of truth for the identified per-axis rate plants
# (docs/sysid_results.md best estimates, 2026-06-18). IdentifiedPlant.canonical and
# scenarios.py both read this, so the numbers live in exactly one place.
CANONICAL_MODELS: dict[str, AxisModel] = {
    "roll": AxisModel(K=165.0, pole=19.8, delay=0.015),
    "pitch": AxisModel(K=185.0, pole=16.3, delay=0.012),
    "yaw": AxisModel(K=37.0, pole=None, delay=0.0),
}


class Plant(ABC):
    """Common rate-loop seam: ``step(u_dict) -> state_dict``."""

    @abstractmethod
    def step(self, u: dict) -> dict:
        """Advance one controller tick; return body-rate state dict."""

    @abstractmethod
    def reset(self) -> None:
        """Restore deterministic initial state."""


class _AxisSim:
    """Single-axis discrete state-space + integer transport-delay buffer."""

    def __init__(self, model: AxisModel, dt: float):
        self.dt = dt
        if model.pole is None:
            # K/s : Ad=1, Bd=dt, C=K  (ZOH of an integrator)
            A = np.array([[0.0]])
            B = np.array([[1.0]])
            C = np.array([[model.K]])
        else:
            # K/(s(1+s/p)) = K*p / (s^2 + p s); controllable canonical form
            Kp = model.K * model.pole
            A = np.array([[0.0, 1.0], [0.0, -model.pole]])
            B = np.array([[0.0], [1.0]])
            C = np.array([[Kp, 0.0]])
        D = np.zeros((1, 1))
        Ad, Bd, Cd, _, _ = cont2discrete((A, B, C, D), dt, method="zoh")
        self.Ad, self.Bd, self.Cd = Ad, Bd, Cd
        # N = round(T/dt) integer-sample delay (ADR-0006 D4)
        self.N = int(round(model.delay / dt))
        self.reset()

    def reset(self) -> None:
        self.x = np.zeros((self.Ad.shape[0], 1))
        self.buf = [0.0] * self.N  # FIFO of pending inputs

    def step(self, u: float) -> float:
        # output reflects current state (y = C x), then state advances
        y = float((self.Cd @ self.x).item())
        if self.N:
            self.buf.append(u)
            u_eff = self.buf.pop(0)
        else:
            u_eff = u
        self.x = self.Ad @ self.x + self.Bd * u_eff
        return y


class IdentifiedPlant(Plant):
    """Per-axis identified linear rate plants (docs/sysid_results.md)."""

    def __init__(self, dt: float, axes: dict[str, AxisModel]):
        unknown = set(axes) - _RATE_KEY.keys()
        if unknown:
            raise ValueError(f"unknown axes: {sorted(unknown)}")
        self.dt = dt
        self._sims = {ax: _AxisSim(m, dt) for ax, m in axes.items()}

    def step(self, u: dict) -> dict:
        return {
            _RATE_KEY[ax]: sim.step(float(u.get(ax, 0.0)))
            for ax, sim in self._sims.items()
        }

    def reset(self) -> None:
        for sim in self._sims.values():
            sim.reset()

    @classmethod
    def canonical(cls, dt: float) -> "IdentifiedPlant":
        """The documented roll/pitch/yaw best estimates (CANONICAL_MODELS)."""
        return cls(dt, dict(CANONICAL_MODELS))


class GazeboPlant(Plant):
    """Reserved 6-DOF / Gazebo seam (ADR-0006 D6). Bring-up is a later
    session on the dual-boot Linux partition; the contract is fixed now."""

    def step(self, u: dict) -> dict:
        raise NotImplementedError("GazeboPlant: bring-up deferred (ADR-0006 D6)")

    def reset(self) -> None:
        raise NotImplementedError("GazeboPlant: bring-up deferred (ADR-0006 D6)")
