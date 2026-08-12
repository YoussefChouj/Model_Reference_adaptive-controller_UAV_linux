"""One closed-loop control tick — the wiring seam.

PARITY: API/mrac.c:424-485 (MRAC_Control) + the inner PID cascade. The chain that
used to live inline in run.py now lives behind ``ControlLoop.tick`` so that:

  * the wiring (ref -> e -> PID -> regressor -> law -> plant) has one home and one
    test surface, separate from logging/artifact concerns;
  * a different arrangement (e.g. a closed-loop reference model that feeds the
    tracking error e back into the reference update) is a new ControlLoop, not an
    edit to the runner's for-loop.

``tick`` owns no state across calls except what its collaborators (ref/pid/law/plant)
hold; the runner owns the plant rate ``x`` and the log arrays. The plant returns the
*current* state before applying its input (ADR-0006 D4 seam), so the controller acts
on the previous tick's rate — a realistic one-sample sensor->actuate latency.

Authority channel (prior-06): the ``PriorInjection`` seam optionally adds
``Theta_prior.T @ Phi`` as a feedforward term to the adaptive output. The adaptive
law itself is bit-identical; the feedforward is purely additive and has its own
kill switch. ADR-0013 D6 recommends this as the first channel to enable on the
rig because it can be switched off independently of the certified law.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from sim.baseline import RAD2DEG
from sim.regressor import cross_coupling, structured_regressor

# axis command key -> firmware body-rate output key
_RATE_KEY = {"roll": "p", "pitch": "q", "yaw": "r", "z": "vz"}


@dataclass
class PriorInjection:
    """Authority channel: additive feedforward ``Theta_prior.T @ Phi``.

    The adaptive law is bit-identical; this term is purely additive and has its
    own independent kill switch (``feedforward_on``). The ramp-in prevents the
    prior's full authority from appearing instantaneously at t=0.

    When ``theta_prior`` is None the whole seam is a no-op (all outputs zero).

    Note: with the feedforward active, the adaptation learns ``theta* - Theta_prior``
    instead of ``theta*``. The two channels (authority + value) interact and must
    be analysed jointly (ADR-0013 D6).
    """
    theta_prior: Optional[np.ndarray] = None   # dimensionless Θ_prior; None = no prior
    feedforward_on: bool = False              # kill switch for the authority channel
    feedforward_ramp_s: float = 0.5            # seconds for ramp-in from 0 → 1
    feedforward_max_abs: float = 2.0           # absolute cap on |u_ff| [Nm]; 0 = no cap

    def __post_init__(self):
        if self.theta_prior is not None:
            arr = np.asarray(self.theta_prior, dtype=float)
            object.__setattr__(self, "theta_prior", arr)

    def _init_state(self, dt: float):
        """Return initial per-run state as a dict. Call once per run."""
        return {"u_ff": 0.0, "ramp_k": 0, "dt": dt}

    def compute(self, phi, state: dict) -> tuple[float, dict]:
        """Return (u_ff, updated_state).

        The state dict is mutated in-place and also returned so callers can
        retain a reference without the method needing to return two values.
        """
        if self.theta_prior is None:
            return 0.0, state

        u_ff = float(self.theta_prior @ np.asarray(phi, dtype=float))

        if not self.feedforward_on:
            # Kill switch: zero out and reset ramp
            state["u_ff"] = 0.0
            state["ramp_k"] = 0
            return 0.0, state

        # Ramp-in: ramp_k ticks at dt → multiplier from 0→1
        ramp_t = state["ramp_k"] * state["dt"]
        if ramp_t < self.feedforward_ramp_s:
            mult = ramp_t / max(self.feedforward_ramp_s, 1e-12)
        else:
            mult = 1.0
        state["ramp_k"] += 1

        u_ff *= mult

        if self.feedforward_max_abs > 0.0:
            u_ff = max(-self.feedforward_max_abs,
                        min(self.feedforward_max_abs, u_ff))

        state["u_ff"] = u_ff
        return u_ff, state


class ControlLoop:
    """Advances plant + reference model + baseline PID + MRAC by one tick."""

    def __init__(self, *, ref, pid, law, plant, axis: str,
                 injection: bool = True,
                 prior_injection: "PriorInjection | None" = None):
        self.ref = ref
        self.pid = pid
        self.law = law
        self.plant = plant
        self.axis = axis
        self.injection = injection
        self.prior_injection = prior_injection if prior_injection is not None else PriorInjection()
        self._key = _RATE_KEY[axis]
        self._pi_state: Optional[dict] = None

    def reset(self) -> None:
        """Reset per-run state (call before each new run)."""
        self._pi_state = self.prior_injection._init_state(self.law.dt)

    def tick(self, x: float, r: float, d: float) -> dict:
        """One MRAC tick. ``x`` = current plant rate, ``r`` = command, ``d`` =
        disturbance torque (Nm). Returns a record of every logged quantity plus the
        next plant rate under key ``x``."""
        xm = self.ref.step(r, x)        # x feeds the 2nd-order CRM term L*(x-xm)
        e = x - xm
        self.pid.step(r * RAD2DEG, x * RAD2DEG)
        u_nom = self.pid.u_nom()
        cross = cross_coupling(self.axis, pitch_rate=0.0, roll_rate=0.0, yaw_rate=0.0)
        phi = structured_regressor(self.axis, x=x, u_nom=u_nom, xm=xm, cross=cross)
        u_ad = self.law.update(e, self.ref.P, phi, x=x, xm_dot=self.ref.xm_dot,
                               Pe=self.ref.Pe, Pedot=self.ref.Pedot)

        # Authority channel: feedforward from Theta_prior
        u_ff, self._pi_state = self.prior_injection.compute(phi, self._pi_state)
        u_ad_total = u_ad + u_ff

        u = u_nom + (u_ad_total if self.injection else 0.0) + d
        x_next = self.plant.step({self.axis: u})[self._key]
        return {
            "xm": xm, "e": e, "u_nom": u_nom, "u_ad": u_ad, "u_ad_total": u_ad_total,
            "u_ff": u_ff, "u": u,
            "U": self.pid.U, "wnorm": float(np.linalg.norm(self.law.Theta)),
            "edot": self.law.e_dot, "theta": self.law.Theta.copy(), "x": x_next,
        }
