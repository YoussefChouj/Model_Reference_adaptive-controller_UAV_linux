"""Closed-loop reference model (CRM) — the modern-MRAC step on the loop.py seam.

The CRM adds a feedback term L*(x - xm) to the 2nd-order reference model so the
reference is pulled toward the plant, shrinking the transient that excites the
adaptation. The error dynamics become A = Am - L*C, so the Lyapunov P (and thus
the drive gains Pe/Pedot) are recomputed. We verify three things:

  1. the analytic closed form for Pe/Pedot matches a numeric Lyapunov solve for
     general L (scipy is the oracle, the closed form runs in the loop / firmware);
  2. L = 0 collapses exactly to the ADR-0007 open-loop forms (no regression);
  3. on a plant-mismatch scenario, turning the CRM on reduces the tracking
     transient (peak error) — its whole reason to exist.
"""
from dataclasses import replace

import numpy as np
import pytest

from sim import scenarios
from sim.plant import CANONICAL_MODELS, IdentifiedPlant
from sim.reference_model import ReferenceModel, RefType
from sim.run import run


def _delayed_roll_step(delay_s: float):
    """Nominal-gain roll step with an explicit transport delay (robustness probe)."""
    model = replace(CANONICAL_MODELS["roll"], delay=delay_s)
    sc = scenarios.step("roll")
    return replace(sc, plant_factory=lambda dt: IdentifiedPlant(dt, {"roll": model}))


def _lyap_2nd_col(wn, zeta, q1, q2, l1, l2):
    """Numeric oracle: solve A^T P + P A = -Q and return (p12, p22)."""
    from scipy.linalg import solve_lyapunov
    A = np.array([[-l1, 1.0], [-(wn * wn + l2), -2.0 * zeta * wn]])
    Q = np.diag([q1, q2])
    P = solve_lyapunov(A.T, -Q)          # A^T P + P A = -Q
    return P[0, 1], P[1, 1]


@pytest.mark.parametrize("l1,l2", [(0.0, 0.0), (5.0, 0.0), (0.0, 300.0),
                                   (12.0, 800.0), (40.0, 0.0)])
def test_analytic_pe_pedot_match_scipy(l1, l2):
    wn, zeta, q1, q2 = 44.0, 0.8, 1.3, 0.7
    rm = ReferenceModel(RefType.SECOND_ORDER, bw=wn, zeta=zeta,
                        q1=q1, q2=q2, l1=l1, l2=l2)
    p12, p22 = _lyap_2nd_col(wn, zeta, q1, q2, l1, l2)
    assert rm.Pe == pytest.approx(p12, rel=1e-9)
    assert rm.Pedot == pytest.approx(p22, rel=1e-9)


def test_zero_L_collapses_to_adr0007():
    wn, zeta, q1, q2 = 44.0, 0.8, 1.0, 1.0
    crm = ReferenceModel(RefType.SECOND_ORDER, bw=wn, zeta=zeta, q1=q1, q2=q2)
    # ADR-0007 open-loop closed forms
    assert crm.Pe == pytest.approx(q1 / (2.0 * wn * wn))
    assert crm.Pedot == pytest.approx((q1 / (wn * wn) + q2) / (4.0 * zeta * wn))


def test_zero_L_step_matches_open_loop_reference():
    """With L=0 the CRM step must equal the open-loop step regardless of x."""
    base = ReferenceModel(RefType.SECOND_ORDER, bw=44.0, zeta=0.8)
    crm = ReferenceModel(RefType.SECOND_ORDER, bw=44.0, zeta=0.8)
    for k in range(50):
        r = 1.0 if k > 5 else 0.0
        assert crm.step(r, x=0.37 * k) == pytest.approx(base.step(r))


def test_crm_feedback_pulls_reference_toward_plant():
    """A nonzero L must make xm respond to the plant rate x (open-loop does not)."""
    open_rm = ReferenceModel(RefType.SECOND_ORDER, bw=44.0, zeta=0.8)
    crm = ReferenceModel(RefType.SECOND_ORDER, bw=44.0, zeta=0.8, l1=30.0, l2=0.0)
    for _ in range(20):
        open_rm.step(0.0)               # command 0, plant drifts to +1 rad/s
        crm.step(0.0, x=1.0)
    assert open_rm.xm == pytest.approx(0.0)
    assert crm.xm > 1e-3                 # reference has been pulled up toward x


def test_crm_reduces_transient_on_mismatch():
    """End-to-end: on inertia mismatch, CRM (L>0) lowers the peak tracking error."""
    sc = scenarios.ALL["inertia_offset_roll"]
    base = run(sc(), write_artifacts=False)
    crm = run(sc(), crm_l1=40.0, write_artifacts=False)
    assert crm["ref_model_type"] == 2
    assert crm["metrics"]["max_abs_err"] < base["metrics"]["max_abs_err"]
    assert crm["metrics"]["stable"]


def test_crm_widens_transport_delay_margin():
    """ADR-0008 'Consequences' guessed large L *narrows* the delay margin (Lavretsky).
    The sweep showed the opposite for this identified-linear + pure-delay plant: at a
    delay 3x the nominal, CRM still lowers the peak error vs the open-loop RM. Recorded
    as a spec so the directional claim isn't silently re-introduced."""
    sc = _delayed_roll_step(0.045)            # 3x the nominal 15 ms roll delay
    base = run(sc, crm_l1=0.0, write_artifacts=False)
    crm = run(sc, crm_l1=80.0, write_artifacts=False)
    assert crm["metrics"]["stable"]
    assert crm["metrics"]["max_abs_err"] < base["metrics"]["max_abs_err"]


def _rm_diverges(l1: float, dt: float, n: int = 400) -> bool:
    """Iterate the CRM reference recurrence with a fixed plant rate; report blow-up."""
    rm = ReferenceModel(RefType.SECOND_ORDER, bw=44.0, zeta=0.8, dt=dt, l1=l1)
    for _ in range(n):
        rm.step(1.0, x=0.0)                  # command 1, plant held at 0 -> e_out = -xm
    return not np.isfinite(rm.xm) or abs(rm.xm) > 1e3


def test_crm_forward_euler_bound_is_the_binding_limit():
    """The real hard limit on l1 is the reference model's forward-Euler integration,
    not a delay/robustness margin: the xm self-feedback coefficient is (1 - l1*dt), so
    the recurrence is stable only for l1*dt < 2  ->  l1 < 2/dt. This is delay-independent
    and is the clamp the firmware port must enforce (closed loop hides it: the PID/What
    clamps keep the plant rate bounded while xm itself diverges). Just below the bound
    the reference stays bounded; well above it the reference diverges."""
    dt = 0.005
    assert not _rm_diverges(0.9 * 2.0 / dt, dt)   # l1*dt = 1.8 -> bounded
    assert _rm_diverges(1.5 * 2.0 / dt, dt)       # l1*dt = 3.0 -> diverges
