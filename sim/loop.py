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
"""
from __future__ import annotations

import numpy as np

from sim.baseline import RAD2DEG
from sim.regressor import cross_coupling, structured_regressor

# axis command key -> firmware body-rate output key
_RATE_KEY = {"roll": "p", "pitch": "q", "yaw": "r", "z": "vz"}


class ControlLoop:
    """Advances plant + reference model + baseline PID + MRAC by one tick."""

    def __init__(self, *, ref, pid, law, plant, axis: str,
                 injection: bool = True):
        self.ref = ref
        self.pid = pid
        self.law = law
        self.plant = plant
        self.axis = axis
        self.injection = injection
        self._key = _RATE_KEY[axis]

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
        u = u_nom + (u_ad if self.injection else 0.0) + d
        x_next = self.plant.step({self.axis: u})[self._key]
        return {
            "xm": xm, "e": e, "u_nom": u_nom, "u_ad": u_ad, "u": u,
            "U": self.pid.U, "wnorm": float(np.linalg.norm(self.law.Theta)),
            "edot": self.law.e_dot, "theta": self.law.Theta.copy(), "x": x_next,
        }
