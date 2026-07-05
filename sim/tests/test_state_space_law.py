"""TDD slice 5 -- 2nd-order matrix-P state-space adaptive law (ADR-0007).

For ref_model_type=2 the firmware/sim no longer use the scalar heuristic P=1/(2*wn);
they use the full Lyapunov matrix P (solving Am^T P + P Am = -Q). With adaptive input
direction B=[0;1] only the 2nd column of P enters: the drive is

    s = e_v^T P B = e*Pe + e_dot*Pedot,   Pe = p12,  Pedot = p22,

with e_dot the LPF'd finite-difference rate-derivative error. These pins guard the
closed-form P (vs the scipy calculator), the q1=wn identity (matches the old scalar
e-gain), the e_dot estimator, and a golden state-space gradient step.
"""
import numpy as np
import pytest

from sim.adaptive_law import AdaptiveLaw, AxisAdaptiveConfig, AdaptiveFlags
from sim.reference_model import ReferenceModel, RefType

DT = 0.005


def _all_off_flags(**kw):
    base = dict(adaptation_on=True, projection_on=False, deadzone_on=False,
                hard_freeze_on=False, tanh_saturation_on=False,
                e_modification_on=False, l1_filtering_on=False)
    base.update(kw)
    return AdaptiveFlags(**base)


def _simple_cfg(**kw):
    base = dict(gamma=[1.0] * 6, sigma=0.0, sigma_lf=0.0, gam_f=0.0, omega_u=0.0,
                What_limit=[1e9] * 6, What_tol=[0.0] * 6, What_lower_limit=[-1e9] * 6,
                e_deadzone=0.0, e_freeze=0.0, e_sat=0.0, k_e=0.0)
    base.update(kw)
    return AxisAdaptiveConfig(**base)


def test_closed_form_P_matches_scipy_calculator():
    # the runtime closed form (Pe,Pedot) must equal the design-time scipy solve
    from scipy.linalg import solve_continuous_lyapunov
    wn, zeta, q1, q2 = 44.1, 0.8, 1.0, 1.0
    Am = np.array([[0.0, 1.0], [-wn * wn, -2.0 * zeta * wn]])
    P = solve_continuous_lyapunov(Am.T, -np.diag([q1, q2]))
    rm = ReferenceModel(RefType.SECOND_ORDER, bw=wn, zeta=zeta, dt=DT, q1=q1, q2=q2)
    assert rm.Pe == pytest.approx(P[0, 1], rel=1e-9)
    assert rm.Pedot == pytest.approx(P[1, 1], rel=1e-9)


def test_q1_equals_wn_recovers_scalar_e_channel_gain():
    # Pe = q1/(2*wn^2); with q1 = wn this is 1/(2*wn) == the old scalar P
    wn = 44.0
    rm = ReferenceModel(RefType.SECOND_ORDER, bw=wn, zeta=0.8, dt=DT, q1=wn, q2=1.0)
    assert rm.Pe == pytest.approx(1.0 / (2.0 * wn), rel=1e-12)
    assert rm.P == pytest.approx(1.0 / (2.0 * wn), rel=1e-12)


def test_first_order_axis_has_no_matrix_gains():
    rm = ReferenceModel.for_axis("yaw", dt=DT)
    assert rm.Pe == 0.0 and rm.Pedot == 0.0


def test_edot_filter_tracks_a_constant_rate_slope():
    # feed a constant angular acceleration (x ramps linearly) -> e_dot -> slope
    law = AdaptiveLaw(_simple_cfg(), _all_off_flags(adaptation_on=False), dt=DT,
                      perf_recovery=False, state_space=True, wc_edot=80.0)
    phi = np.zeros(6)
    slope = 3.0  # rad/s^2
    x = 0.0
    for _ in range(2000):  # 10 s, well past the 80 rad/s filter settling
        x += slope * DT
        law.update(e=0.0, P=0.0, phi=phi, x=x, xm_dot=0.0, Pe=0.0, Pedot=0.0)
    assert law.e_dot == pytest.approx(slope, abs=1e-2)


def test_golden_state_space_gradient_step():
    phi = np.array([1.0, 0.3, 0.1, 0.0, 0.5, 0.2])
    e, Pe, Pedot, wc, x0 = 0.4, 2.6e-4, 7.1e-3, 30.0, 0.6
    law = AdaptiveLaw(_simple_cfg(), _all_off_flags(), dt=DT, perf_recovery=False,
                      state_space=True, wc_edot=wc)
    law.update(e=e, P=0.0, phi=phi, x=x0, xm_dot=0.0, Pe=Pe, Pedot=Pedot)
    # first tick: xdot_f = dt*wc*(x0/dt) = wc*x0 -> e_dot = wc*x0
    e_dot = wc * x0
    s = e * Pe + e_dot * Pedot
    denom = 1.0 + float(phi @ phi)
    expected = DT * ((-s * phi) / denom)
    np.testing.assert_allclose(law.Theta, expected, rtol=1e-12, atol=1e-15)


def test_state_space_drives_weights_on_inertia_offset():
    # a gain-mismatch step must move the weights off zero through the matrix-P drive
    from sim import scenarios
    from sim.run import run
    res = run(scenarios.inertia_offset("roll", factor=0.5), q1=44.0,
              write_artifacts=False)
    assert res["metrics"]["final_weight_norm"] > 0.0
    assert res["metrics"]["stable"]
