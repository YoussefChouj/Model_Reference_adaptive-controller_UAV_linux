"""SIL gate tests - host-compiled ekf.c ↔ sim/ekf.py equivalence.

These tests are the gate's *primary* deliverable. They run the compiled
ekf.c and sim/ekf.py on identical inputs over a 2000-tick trajectory at
200 Hz and assert the trajectories agree within documented tolerances.

If any of these fail, it is a finding about the firmware ↔ model
relationship - see sil_gate/DEVIATIONS.md for documented intentional
differences.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from sil_gate.linker import run_ekf_subprocess
from sil_gate.runner import (
    DEFAULT_ABS_TOL,
    DEFAULT_GROWTH_TOL_PER_S,
    DEFAULT_REL_TOL,
    compare_trajectories,
    format_failure,
    run_firmware,
    run_sim,
    trajectory_constant_with_noise,
    trajectory_random_walk,
)


# ----------------------------------------------------------------------
# Trajectory: deterministic constant acceleration (no measurement noise)
# ----------------------------------------------------------------------
# The simplest possible case: zero measurement noise, constant body
# acceleration. Both implementations must follow the same Euler step.
# This is the smoke test - if THIS fails, the gate itself is wrong.

def test_ekf_constant_accel_clean(ekf_runner):
    """2000-tick constant-acceleration trajectory, zero noise."""
    traj = trajectory_constant_with_noise(
        n_ticks=2000,
        dt=0.005,                         # 200 Hz, matches MRAC_DT
        a_body=(0.05, -0.03, 0.02),       # 5/3/2 cm/s^2
        gyro=(0.0, 0.0, 0.0),
        seed=0,
    )

    sim = run_sim(traj)
    fw = run_firmware(ekf_runner.runner, traj)

    result = compare_trajectories(sim, fw, dt=0.005)
    if not result.passed:
        pytest.fail(format_failure("constant_accel_clean", result))


# ----------------------------------------------------------------------
# Trajectory: OF measurement noise (the realistic case)
# ----------------------------------------------------------------------

def test_ekf_with_of_measurement_noise(ekf_runner):
    """Constant accel + Gaussian OF noise - drives the Kalman gain."""
    traj = trajectory_constant_with_noise(
        n_ticks=2000,
        dt=0.005,
        a_body=(0.1, -0.05, 0.02),
        gyro=(0.0, 0.0, 0.0),
        seed=42,
        of_noise_std=0.01,   # 1 cm/s standard deviation
    )

    sim = run_sim(traj)
    fw = run_firmware(ekf_runner.runner, traj)

    result = compare_trajectories(sim, fw, dt=0.005)
    if not result.passed:
        pytest.fail(format_failure("constant_accel_of_noise", result))


def test_ekf_random_walk_excitation(ekf_runner):
    """Random-walk a_body/gyro to exercise the covariance propagation.

    This trajectory is harder on the predict step than constant-accel,
    and stresses the F-cross-term fix that the historical-bad ekf.c
    was missing (it pinned b_a forever).
    """
    traj = trajectory_random_walk(
        n_ticks=2000,
        dt=0.005,
        seed=7,
        a_body_scale=0.5,
        gyro_scale=0.3,
    )

    sim = run_sim(traj)
    fw = run_firmware(ekf_runner.runner, traj)

    result = compare_trajectories(sim, fw, dt=0.005)
    if not result.passed:
        pytest.fail(format_failure("random_walk", result))


# ----------------------------------------------------------------------
# NIS bounds - sanity that NIS does not diverge
# ----------------------------------------------------------------------

def test_ekf_nis_stays_finite(ekf_runner):
    """NIS must remain finite across 2000 ticks of random-walk excitation."""
    traj = trajectory_random_walk(n_ticks=2000, dt=0.005, seed=1)
    fw = run_firmware(ekf_runner.runner, traj)
    for i in range(len(fw.nis)):
        assert math.isfinite(float(fw.nis[i])), \
            f"NIS not finite at tick {i}: {fw.nis[i]}"
        assert float(fw.nis[i]) >= 0.0, \
            f"NIS negative at tick {i}: {fw.nis[i]}"


def test_ekf_x_stays_finite(ekf_runner):
    """State vector must remain finite across a random-walk trajectory.

    This is a structural sanity: if the predict or update produces a NaN,
    the EKF is in a degenerate state and the comparison contract is moot.
    """
    traj = trajectory_random_walk(n_ticks=2000, dt=0.005, seed=2)
    fw = run_firmware(ekf_runner.runner, traj)
    for i in range(fw.x.shape[0]):
        row = fw.x[i]
        assert np.all(np.isfinite(row)), \
            f"x not finite at tick {i}: {row}"