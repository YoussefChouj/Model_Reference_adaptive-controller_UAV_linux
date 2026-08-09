"""TDD slice 1 — sim/plant.py.

Pins the identified rate plants (docs/sysid_results.md) and the Plant seam
(ADR-0006 D3/D4). The plant boundary is the inner rate loop: command in,
body rate out. Units of the command match the firmware u (u_nom + u_ad),
NOT SI Nm — the identified K folds in torque effectiveness and 1/J, so this
is what gives byte-for-byte parity with mrac.c.
"""
import numpy as np
import pytest

from sim.plant import AxisModel, GazeboPlant, IdentifiedPlant, Plant

DT = 0.005  # 200 Hz, matches MRAC_DT (ADR-0006 D1)


def test_gazebo_plant_is_a_plant_and_is_unimplemented():
    """GazeboPlant is a Plant. On a host without gz, step raises with a
    message that names the spec. On a Linux box with gz-jetty installed,
    the probe returns available=True and step() takes the bridge path
    (lazily starting the gz sim). The unavailable-path message is
    exercised by the matching tests in test_seams.py."""
    p = GazeboPlant()
    assert isinstance(p, Plant)
    avail, _ = GazeboPlant.is_available()
    if not avail:
        with pytest.raises(NotImplementedError):
            p.step({"roll": 0.0})
    # On a host with gz available, step() takes the bridge path; the
    # bridge-startup is tested separately by the spec 4b integration
    # tests on the Linux partition.


def test_step_returns_only_configured_axis_rates():
    # roll->p, pitch->q, yaw->r (firmware body-rate names)
    plant = IdentifiedPlant(
        DT, {"roll": AxisModel(K=165.0, pole=19.8, delay=0.015),
             "yaw": AxisModel(K=37.0, pole=None, delay=0.0)}
    )
    out = plant.step({"roll": 0.0, "yaw": 0.0})
    assert set(out) == {"p", "r"}


def test_yaw_pure_integrator_matches_closed_form():
    # G_yaw(s) = K/s, rel-degree 1, no pole/delay. ZOH integrator:
    # r[n] = K * dt * sum_{i<n} u[i]; y returned BEFORE the state update.
    K = 37.0
    plant = IdentifiedPlant(DT, {"yaw": AxisModel(K=K, pole=None, delay=0.0)})
    rng = np.random.default_rng(0)
    u = rng.standard_normal(200)
    got = np.array([plant.step({"yaw": float(ui)})["r"] for ui in u])
    expected = K * DT * np.concatenate(([0.0], np.cumsum(u)[:-1]))
    np.testing.assert_allclose(got, expected, rtol=1e-9, atol=1e-12)


def test_roll_asymptotic_rate_slope_equals_K():
    # G_roll(s) = K/(s(1+s/p)) -> integrator + lag; under a unit step the
    # body-rate ramps with asymptotic slope K*U (here U=1), transient ~1/p.
    K, p = 165.0, 19.8
    plant = IdentifiedPlant(DT, {"roll": AxisModel(K=K, pole=p, delay=0.0)})
    r = np.array([plant.step({"roll": 1.0})["p"] for _ in range(600)])  # 3 s
    slope = (r[-1] - r[-51]) / (50 * DT)
    assert slope == pytest.approx(K, rel=0.01)


def test_transport_delay_shifts_output_by_N_samples():
    # T=15 ms at 200 Hz -> N=3. LTI: delaying the input by N delays the
    # output by N (zero initial state). The delay is NOT cosmetic (ADR D4).
    params = dict(K=165.0, pole=19.8)
    delayed = IdentifiedPlant(DT, {"roll": AxisModel(delay=0.015, **params)})
    undelayed = IdentifiedPlant(DT, {"roll": AxisModel(delay=0.0, **params)})
    rng = np.random.default_rng(1)
    u = rng.standard_normal(100)
    d = np.array([delayed.step({"roll": float(x)})["p"] for x in u])
    n = np.array([undelayed.step({"roll": float(x)})["p"] for x in u])
    N = 3
    assert np.allclose(d[:N], 0.0)
    np.testing.assert_allclose(d[N:], n[:-N], rtol=1e-9, atol=1e-12)


def test_reset_restores_deterministic_initial_state():
    plant = IdentifiedPlant(DT, {"roll": AxisModel(K=165.0, pole=19.8, delay=0.015)})
    first = [plant.step({"roll": 1.0})["p"] for _ in range(20)]
    plant.reset()
    second = [plant.step({"roll": 1.0})["p"] for _ in range(20)]
    assert first == second
