"""TDD slice 3b — sim/adaptive_law.py.

PARITY: API/mrac.c:93-276 (MRAC_ProjectGradient + MRAC_UpdateAxis), under the
active build flags FIX_LEAKAGE_NORMALIZATION=1 and ENABLE_PERFORMANCE_RECOVERY=1.

The reference-model update (xm, P) is external (sim/reference_model.py); this
module takes the tracking error e, the scalar gain P, and the regressor Phi, and
runs the Lyapunov gradient law with projection / sigma- & e-modification /
deadzone / hard-freeze / tanh-saturation / L1 leakage / performance-recovery LPF.

Firmware quirk pinned here: What_lower_limit is never set in MRAC_Init, so the
effective lower bound is 0 — weights live in [0, What_limit]. We replicate that.
"""
import math

import numpy as np
import pytest

from sim.adaptive_law import AdaptiveLaw, AxisAdaptiveConfig, AdaptiveFlags

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


def test_zero_error_keeps_weights_zero():
    law = AdaptiveLaw(_simple_cfg(), _all_off_flags(), dt=DT, perf_recovery=False)
    u = law.update(e=0.0, P=1.0, phi=np.array([1.0, 0.2, 0.1, 0.0, 0.5, 0.3]))
    assert np.all(law.Theta == 0.0)
    assert u == 0.0


def test_golden_single_gradient_step():
    phi = np.array([1.0, 0.3, 0.1, 0.0, 0.5, 0.2])
    e, P = 0.4, 0.5
    law = AdaptiveLaw(_simple_cfg(), _all_off_flags(), dt=DT, perf_recovery=False)
    u = law.update(e=e, P=P, phi=phi)
    denom = 1.0 + float(phi @ phi)
    grad = (-e * P * phi) / denom          # PBe=e (tanh off), gamma=1, sigma=0
    expected_theta = DT * grad
    np.testing.assert_allclose(law.Theta, expected_theta, rtol=1e-12, atol=1e-15)
    assert u == pytest.approx(float(expected_theta @ phi))


def test_hard_freeze_zeros_output_and_preserves_weights():
    cfg = _simple_cfg(e_freeze=1.0)
    law = AdaptiveLaw(cfg, _all_off_flags(hard_freeze_on=True), dt=DT, perf_recovery=False)
    law.Theta = np.array([0.1, 0.0, 0.0, 0.0, 0.0, 0.0])
    snap = law.Theta.copy()
    u = law.update(e=2.0, P=1.0, phi=np.ones(6))  # |e| > e_freeze
    assert u == 0.0
    np.testing.assert_array_equal(law.Theta, snap)


def test_deadzone_blocks_adaptation_but_still_outputs():
    cfg = _simple_cfg(e_deadzone=0.5)
    law = AdaptiveLaw(cfg, _all_off_flags(deadzone_on=True), dt=DT, perf_recovery=False)
    law.Theta = np.array([0.2, 0.0, 0.0, 0.0, 0.0, 0.0])
    phi = np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    u = law.update(e=0.1, P=1.0, phi=phi)   # |e| < deadzone -> no weight change
    assert law.Theta[0] == 0.2
    assert u == pytest.approx(0.2)           # u_ad = Theta . phi still computed


def test_tanh_saturation_bounds_effective_error():
    phi = np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    cfg = _simple_cfg(e_sat=0.5)
    law = AdaptiveLaw(cfg, _all_off_flags(tanh_saturation_on=True), dt=DT, perf_recovery=False)
    law.update(e=100.0, P=1.0, phi=phi)      # huge spike
    PBe = 0.5 * math.tanh(100.0 / 0.5)       # ~0.5
    expected = DT * ((-PBe * 1.0 * phi) / (1.0 + 1.0))
    np.testing.assert_allclose(law.Theta, expected, rtol=1e-9, atol=1e-12)


def test_projection_clamps_weight_at_upper_limit():
    # band=0 hard clamp: gradient pushing past the limit is zeroed (mrac.c:112-116)
    cfg = _simple_cfg(What_limit=[0.1] + [1e9] * 5, What_tol=[0.0] * 6,
                      What_lower_limit=[0.0] * 6)
    law = AdaptiveLaw(cfg, _all_off_flags(projection_on=True), dt=DT, perf_recovery=False)
    phi = np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    # negative e -> grad positive -> drives Theta[0] up toward the limit
    for _ in range(5000):
        law.update(e=-1.0, P=1.0, phi=phi)
    assert law.Theta[0] <= 0.1 + 1e-9
    assert law.Theta[0] == pytest.approx(0.1, abs=1e-3)


def test_lower_bound_zero_prevents_negative_weights():
    # firmware parity: What_lower_limit defaults to 0 -> weights cannot go negative
    cfg = _simple_cfg(What_limit=[1e9] * 6, What_tol=[0.0] * 6,
                      What_lower_limit=[0.0] * 6)
    law = AdaptiveLaw(cfg, _all_off_flags(projection_on=True), dt=DT, perf_recovery=False)
    phi = np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    for _ in range(2000):
        law.update(e=1.0, P=1.0, phi=phi)   # grad negative, would push below 0
    assert law.Theta[0] >= -1e-9


def test_performance_recovery_is_first_order_lpf_on_u_ad():
    phi = np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    cfg = _simple_cfg(omega_u=30.0)
    law = AdaptiveLaw(cfg, _all_off_flags(adaptation_on=False), dt=DT, perf_recovery=True)
    law.Theta = np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0])  # raw_u_ad = 1.0 constant
    u_prev = 0.0
    for _ in range(10):
        u = law.update(e=0.0, P=1.0, phi=phi)
        expected = u_prev + DT * 30.0 * (1.0 - u_prev)   # mrac.c:272
        assert u == pytest.approx(expected, rel=1e-12)
        u_prev = u


def test_for_axis_matches_firmware_init_gains():
    pr = AxisAdaptiveConfig.for_axis("roll")
    assert list(pr.gamma) == [1.5, 0.2, 0.05, 0.05, 0.1, 0.1]
    assert list(pr.What_limit) == [0.15, 0.05, 0.02, 0.05, 0.20, 0.15]
    assert pr.e_freeze == 1.2 and pr.e_sat == 0.5
    yaw = AxisAdaptiveConfig.for_axis("yaw")
    assert list(yaw.gamma) == [1.0, 0.1, 0.05, 0.05, 0.1, 0.1]
    assert yaw.What_limit[0] == pytest.approx(0.15 * 0.6)
    assert np.all(np.asarray(pr.What_lower_limit) == 0.0)  # firmware never sets it
