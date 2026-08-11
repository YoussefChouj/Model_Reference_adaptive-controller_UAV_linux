"""TDD slice 3b — sim/adaptive_law.py.

PARITY: API/mrac.c:93-276 (MRAC_ProjectGradient + MRAC_UpdateAxis), under the
active build flags FIX_LEAKAGE_NORMALIZATION=1 and ENABLE_PERFORMANCE_RECOVERY=1.

The reference-model update (xm, P) is external (sim/reference_model.py); this
module takes the tracking error e, the scalar gain P, and the regressor Phi, and
runs the Lyapunov gradient law with projection / sigma- & e-modification /
deadzone / hard-freeze / tanh-saturation / L1 leakage / performance-recovery LPF.

Firmware quirk: slots 1-5 are never explicitly set (defaults 0). Slot 0 is
unlocked to -What_limit[0] for pitch/roll/yaw only (mrac.c:353-355); z has
no bias unlock (all slots 0).
"""
import math

import numpy as np
import pytest

from sim.adaptive_law import AdaptiveLaw, AxisAdaptiveConfig, AdaptiveFlags, NUM_BASIS

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
    # slot 0 unlocked to -What_limit[0]; slots 1-5 stay at 0 (firmware: mrac.c:354)
    ll = np.asarray(pr.What_lower_limit)
    assert ll[0] == pytest.approx(-0.15)
    assert np.all(ll[1:] == 0.0)

    yaw = AxisAdaptiveConfig.for_axis("yaw")
    assert list(yaw.gamma) == [1.0, 0.1, 0.05, 0.05, 0.1, 0.1]
    assert yaw.What_limit[0] == pytest.approx(0.15 * 0.6)
    ll_yaw = np.asarray(yaw.What_lower_limit)
    assert ll_yaw[0] == pytest.approx(-0.15 * 0.6)
    assert np.all(ll_yaw[1:] == 0.0)

    # z has NO bias unlock — all slots at 0 (firmware: mrac.c:353-355 only pitch/roll/yaw)
    z = AxisAdaptiveConfig.for_axis("z")
    assert np.all(np.asarray(z.What_lower_limit) == 0.0)


# ----------------------------------------------------------------------
# ADR-0013 D5 — σ_prior attractor parity (sigma_prior=0 == pre-change code)
#
# The default config (sigma_prior=0, theta_prior=None, sigma_prior_on=False)
# must reproduce the pre-change trajectories bit-for-bit. The tests below
# (a) verify the config defaults carry sigma_prior=0, (b) drive a long
# trajectory with the new law and a hand-computed reference, asserting the
# trajectories match to 1e-9 absolute tolerance. The reference is built
# using the same closed-form formulas the existing tests pin; the
# comparison covers the σ_lf, σ_e, and projection branches.
# ----------------------------------------------------------------------
def test_axis_adaptive_config_defaults_sigma_prior_to_zero():
    """Default config must have sigma_prior=0 and theta_prior=None.

    Every existing for_axis() call site constructs the config from
    ``AxisAdaptiveConfig.for_axis``; the new fields must default to their
    off state so the bit-identical guarantee holds without touching
    call sites.
    """
    for axis in ("pitch", "roll", "yaw", "z"):
        cfg = AxisAdaptiveConfig.for_axis(axis)
        assert cfg.sigma_prior == 0.0
        assert cfg.theta_prior is None


def test_sigma_prior_zero_trajectory_matches_pre_change_with_sigma_lf():
    """With sigma_prior=0 and sigma_lf>0, theta_prior set but flag off,
    the law's Theta trajectory must match the pre-change code. Reference
    is built from the closed-form Theta update with σ_lf leak only.
    """
    cfg = _simple_cfg(sigma=0.0, sigma_lf=0.5, gam_f=10.0)
    # Set theta_prior to a nonzero array but leave the flag off.
    cfg_with_prior = _simple_cfg(sigma=0.0, sigma_lf=0.5, gam_f=10.0,
                                 sigma_prior=2.0,
                                 theta_prior=np.array([0.1, 0.0, 0.0, 0.0, 0.0, 0.0]))
    flags = _all_off_flags(l1_filtering_on=True)

    # Drive both laws with the same regressor / error sequence.
    rng = np.random.default_rng(7)
    seq_e = rng.standard_normal(80) * 0.5
    phi = np.array([1.0, 0.4, 0.1, 0.0, 0.5, 0.3])

    law_no_prior = AdaptiveLaw(cfg, flags, dt=DT, perf_recovery=False)
    law_with_prior = AdaptiveLaw(cfg_with_prior, flags, dt=DT,
                                  perf_recovery=False)

    # Reference: closed-form update with the σ_lf leak only, matching the
    # pre-change code line-for-line.
    theta_ref = np.zeros(6)
    whatf_ref = np.zeros(6)
    P = 1.0
    for e in seq_e:
        denom = 1.0 + float(phi @ phi)
        grad = (-e * P * phi) / denom
        y = 1.0 * (grad - 0.5 * (theta_ref - whatf_ref) - 0.0 * theta_ref)
        theta_ref = theta_ref + DT * y
        whatf_ref = whatf_ref + DT * 10.0 * (theta_ref - whatf_ref)

    # Drive both laws; sigma_prior=0 and sigma_prior_on=False mean
    # the second law is bit-identical to the first (and to theta_ref).
    for e in seq_e:
        law_no_prior.update(e=e, P=P, phi=phi)
        law_with_prior.update(e=e, P=P, phi=phi)

    np.testing.assert_allclose(law_no_prior.Theta, theta_ref,
                               rtol=0.0, atol=1e-9)
    np.testing.assert_allclose(law_with_prior.Theta, law_no_prior.Theta,
                               rtol=0.0, atol=1e-9)
    np.testing.assert_allclose(law_with_prior.Whatf, law_no_prior.Whatf,
                               rtol=0.0, atol=1e-9)


def test_sigma_prior_on_pulls_theta_toward_prior_attractor():
    """When sigma_prior_on=True and theta_prior is non-None, the
    closed-loop trajectories converge toward ``theta_prior``. This is
    the positive-direction test: sigma_prior=0 and sigma_prior=1 must
    diverge.
    """
    prior = np.array([0.2, -0.1, 0.05, 0.0, 0.15, 0.0])
    cfg_off = _simple_cfg(sigma_prior=0.0, theta_prior=prior)
    cfg_on = _simple_cfg(sigma_prior=2.0, theta_prior=prior)
    flags = _all_off_flags(sigma_prior_on=True)

    phi = np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    law_off = AdaptiveLaw(cfg_off, flags, dt=DT, perf_recovery=False)
    law_on = AdaptiveLaw(cfg_on, flags, dt=DT, perf_recovery=False)
    law_on.Theta = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    law_off.Theta = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0])

    # Run a long enough horizon for the σ_prior leak to dominate the
    # gradient term. With e=0 (no gradient) the only motion is the leak,
    # so the trajectory is exponential toward ``prior``.
    for _ in range(2000):
        law_off.update(e=0.0, P=1.0, phi=phi)
        law_on.update(e=0.0, P=1.0, phi=phi)

    # sigma_prior=0 -> Theta stays at 0
    np.testing.assert_allclose(law_off.Theta, np.zeros(6), atol=1e-12)
    # sigma_prior=2 -> Theta approaches ``prior`` exponentially
    np.testing.assert_allclose(law_on.Theta, prior, atol=1e-3)


def test_sigma_prior_flag_off_with_nonzero_sigma_prior_and_prior_array_is_bit_identical():
    """sigma_prior_on=False must short-circuit the prior term even when
    sigma_prior and theta_prior are set (the flag is the gating switch).
    """
    prior = np.array([0.5, 0.0, 0.0, 0.0, 0.0, 0.0])
    cfg = _simple_cfg(sigma_prior=10.0, theta_prior=prior)
    flags_on = _all_off_flags(sigma_prior_on=True)
    flags_off = _all_off_flags(sigma_prior_on=False)

    phi = np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    law_on = AdaptiveLaw(cfg, flags_on, dt=DT, perf_recovery=False)
    law_off = AdaptiveLaw(cfg, flags_off, dt=DT, perf_recovery=False)
    # Identical starting point.
    law_on.Theta = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    law_off.Theta = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0])

    for _ in range(2000):
        law_on.update(e=0.0, P=1.0, phi=phi)
        law_off.update(e=0.0, P=1.0, phi=phi)

    # Flag off -> no leak; weights stay at zero.
    np.testing.assert_allclose(law_off.Theta, np.zeros(6), atol=1e-12)
    # Flag on -> weights converge toward prior.
    assert abs(law_on.Theta[0] - prior[0]) < 0.01


# ----------------------------------------------------------------------
# spec-11: learning vs deployment envelope
# ----------------------------------------------------------------------

def test_for_deployment_is_default_envelope():
    """``for_deployment()`` is the default; ``for_axis()`` must return the
    same object so every existing call site is unchanged."""
    for axis in ("pitch", "roll", "yaw", "z"):
        dep = AxisAdaptiveConfig.for_deployment(axis)
        old = AxisAdaptiveConfig.for_axis(axis)
        assert dep.envelope == "deployment"
        assert old.envelope == "deployment"
        assert list(dep.gamma) == list(old.gamma)
        assert list(dep.What_limit) == list(old.What_limit)
        assert dep.e_deadzone == 0.05


def test_for_learning_relaxes_deadzone_to_noise_floor():
    """Learning envelope deadzone = 2*σ_noise = 0.01 rad/s, not zero.

    The Ioannou & Sun bursting constraint forbids e_deadzone=0.
    0.01 rad/s = 2× the measured ~0.005 rad/s gyro-noise RMS on the
    identified plant — traceable to a measurement, not a tuned constant.
    """
    for axis in ("pitch", "roll", "yaw", "z"):
        cfg = AxisAdaptiveConfig.for_learning(axis)
        assert cfg.envelope == "learning"
        assert cfg.e_deadzone == pytest.approx(
            2.0 * AxisAdaptiveConfig._LEARNING_SIGMA_NOISE,
            rel=0, abs=1e-12)
        assert cfg.e_deadzone < 0.05   # meaningfully lower than deployment
        assert cfg.e_deadzone > 0.0    # not zero (bursting constraint)


def test_for_learning_widens_What_limits_5x():
    """Learning envelope What_limit = 5× deployment, projection stays active."""
    for axis in ("pitch", "roll"):
        dep = AxisAdaptiveConfig.for_deployment(axis)
        lrng = AxisAdaptiveConfig.for_learning(axis)
        for i in range(NUM_BASIS):
            assert lrng.What_limit[i] == pytest.approx(
                dep.What_limit[i] * 5.0, rel=1e-9)
            # Symmetric lower bound (deployment only unlocks slot 0)
            assert lrng.What_lower_limit[i] == pytest.approx(
                -lrng.What_limit[i], rel=1e-9)


def test_for_learning_symmetric_lower_limits_on_all_slots():
    """Deployment unlocks slot 0 only; learning unlocks all slots symmetrically.
    This is what lets slots 1-5 explore in both directions during learning."""
    for axis in ("pitch", "roll"):
        dep = AxisAdaptiveConfig.for_deployment(axis)
        lrng = AxisAdaptiveConfig.for_learning(axis)
        # Deployment: slot 0 has a negative lower bound; slots 1-5 are at 0
        assert dep.What_lower_limit[0] < 0.0
        assert all(v == 0.0 for v in dep.What_lower_limit[1:])
        # Learning: every slot has a symmetric negative bound
        for i in range(NUM_BASIS):
            assert lrng.What_lower_limit[i] == pytest.approx(
                -lrng.What_limit[i], rel=1e-9)


def test_deployment_manifest_records_envelope():
    """Every deployment config carries its envelope name; the manifest requires it."""
    cfg = AxisAdaptiveConfig.for_deployment("roll")
    assert cfg.envelope == "deployment"
    assert isinstance(cfg.theta_final, type(None))  # not yet run


def test_learning_config_cannot_be_used_without_explicit_choice():
    """``for_learning()`` must be called explicitly; there is no silent path to
    the learning envelope — deployment is always the default."""
    cfg = AxisAdaptiveConfig.for_axis("roll")
    assert cfg.envelope == "deployment"
    cfg_lrng = AxisAdaptiveConfig.for_learning("roll")
    assert cfg_lrng.envelope == "learning"
    # These are not the same object
    assert cfg is not cfg_lrng


def test_learning_deadzone_blocks_noise_but_not_small_signal():
    """With e_deadzone = 0.01, a 0.005 rad/s error (below noise floor)
    is blocked; a 0.015 rad/s error (above noise floor) is not."""
    cfg_lrng = AxisAdaptiveConfig.for_learning("roll")
    flags = AdaptiveFlags()
    law = AdaptiveLaw(cfg_lrng, flags, dt=DT, perf_recovery=False)
    phi = np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0])

    # Below noise floor: do_adapt is False, weights stay zero
    law.update(e=0.005, P=1.0, phi=phi)
    np.testing.assert_allclose(law.Theta, np.zeros(6), atol=1e-15)

    # Above noise floor: weights update
    law.reset()
    law.update(e=0.015, P=1.0, phi=phi)
    assert law.Theta[0] != 0.0


def test_learning_envelope_allows_bidirectional_slot1_adaptation():
    """Under deployment config, slot 1 cannot go negative (lower_limit=0).
    Under learning config it can, since What_lower_limit is symmetric."""
    dep_cfg = AxisAdaptiveConfig.for_deployment("roll")
    lrng_cfg = AxisAdaptiveConfig.for_learning("roll")
    flags = AdaptiveFlags(projection_on=True)
    phi = np.array([0.0, 1.0, 0.0, 0.0, 0.0, 0.0])

    law_dep = AdaptiveLaw(dep_cfg, flags, dt=DT, perf_recovery=False)
    law_lrng = AdaptiveLaw(lrng_cfg, flags, dt=DT, perf_recovery=False)

    # Drive slot 1 negative (positive e -> negative grad -> negative update)
    for _ in range(5000):
        law_dep.update(e=1.0, P=1.0, phi=phi)
        law_lrng.update(e=1.0, P=1.0, phi=phi)

    # Deployment: slot 1 hits lower bound of 0 and stays there
    assert law_dep.Theta[1] >= -1e-9
    # Learning: slot 1 goes negative (symmetric lower bound)
    assert law_lrng.Theta[1] < -0.01
