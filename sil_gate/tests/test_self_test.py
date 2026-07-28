"""Self-test of the SIL gate.

A gate that has never failed is not evidence it works. These tests
deliberately break the firmware source and assert the gate reports the
break, in three flavours:

  1. test_self_test_sign_flip    - flip a sign in the state update
  2. test_self_test_drop_term    - drop a covariance cross-term (the
                                   exact historical defect)
  3. test_self_test_predict_bias - introduce a constant bias into predict

Each test copies API/ekf.c to a temporary file, applies a targeted patch,
rebuilds the runner, and asserts the gate now fails. If any of these
passes, the gate is not sensitive enough to be useful.

The patches are local to the test (in a tmp directory) and the original
API/ekf.c is never touched.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from sil_gate.compiler import resolve_gcc
from sil_gate.runner import (
    trajectory_constant_with_noise,
    run_sim,
    run_firmware,
    compare_trajectories,
    format_failure,
)


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def _build_with_patch(source_text: str, tmpdir: Path) -> Path:
    """Write a perturbed ekf.c to tmpdir and build a runner from it.

    Returns the runner exe path. Raises pytest.skip if no gcc.
    """
    tmpdir.mkdir(parents=True, exist_ok=True)
    patched = tmpdir / "ekf_patched.c"
    patched.write_text(source_text, encoding="utf-8")

    spec = resolve_gcc()
    if spec is None:
        pytest.skip("no host gcc available - SIL gate requires one")

    # Custom build: the patched .c replaces the API/ekf.c as an extra
    # source, while runner_main.c stays as the primary. This is how the
    # gate generalises to any firmware module.
    from sil_gate.compiler import compile_executable
    runner_src = Path("sil_gate/runner_main.c")
    out_path = tmpdir / f"sil_runner_patched{_exe_suffix()}"
    return compile_executable(
        spec,
        source=runner_src,
        out_path=out_path,
        include_dirs=(Path("sil_gate/shim"), Path("API")),
        extra_sources=(patched,),
        extra_cflags=("-Wno-unused-but-set-variable",),
    )


def _exe_suffix() -> str:
    import sys
    return ".exe" if sys.platform == "win32" else ""


def _copy_ekf_to(tmpdir: Path) -> Path:
    """Copy the real API/ekf.c to tmpdir unchanged, return the path."""
    src = Path("API/ekf.c").resolve()
    dst = tmpdir / "ekf_orig.c"
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return dst


# ----------------------------------------------------------------------
# Self-tests
# ----------------------------------------------------------------------

def test_self_test_sign_flip_in_predict(tmp_path, ekf_runner):
    """Flip a sign in the predict step. Gate must catch it.

    The patch: `e->x[0] += (a_body_x - e->x[3]) * dt` -> with a minus sign.
    A sign flip on the state update is exactly the kind of defect that
    would compound to huge divergence over 2000 ticks (the historical
    optical-flow defect was a sign inversion - see the spec preamble).

    Trajectory uses OF measurement noise so the Kalman update has work to
    do; otherwise the predict-step sign flip is masked by the perfect
    inverse-update and never surfaces.
    """
    src = Path("API/ekf.c").resolve()
    text = src.read_text(encoding="utf-8")
    # Apply the flip. The pattern is unique in ekf.c.
    patched = text.replace(
        "e->x[0] += (a_body_x - e->x[3]) * dt;",
        "e->x[0] += -(a_body_x - e->x[3]) * dt;",
        1,
    )
    assert patched != text, "patch did not apply"

    runner = _build_with_patch(patched, tmp_path / "build_signflip")

    traj = trajectory_constant_with_noise(
        n_ticks=2000,
        dt=0.005,
        a_body=(0.05, -0.03, 0.02),
        gyro=(0.0, 0.0, 0.0),
        seed=0,
        of_noise_std=0.02,  # 2 cm/s noise - drives the Kalman gain
    )
    sim = run_sim(traj)
    fw = run_firmware(runner, traj)
    result = compare_trajectories(sim, fw, dt=0.005)
    assert not result.passed, (
        "sign flip in predict must be caught by the gate, but it passed. "
        "Either the gate is too loose, or the patch was not applied.\n"
        + format_failure("self_test_sign_flip", result)
    )


def test_self_test_drop_cross_term_in_predict(tmp_path, ekf_runner):
    """Drop the F-cross-terms that build the v-b_a covariance.

    This is EXACTLY the historical defect #1 the spec calls out. The
    patched predict step omits the `NP + PNT + NPNT` accumulation and
    falls back to the simple diagonal-only approximation that was in
    place before the 2026-07-26 fix. With this patch, the bias state
    never updates because the Kalman gain columns 3..5 are zero.

    Trajectory uses OF noise so the Kalman update actually exercises the
    K[3..5, 0] path; without noise the OF innovation is zero and the
    b_a update is never invoked.
    """
    src = Path("API/ekf.c").resolve()
    text = src.read_text(encoding="utf-8")
    # Drop the three cross-term accumulation loops by removing the block.
    needle_start = "/* N P : rows 0..2, all cols."
    needle_end = "}\n\n        /* + Q : Q_v scaled by dt^2"
    i = text.find(needle_start)
    j = text.find(needle_end, i)
    assert i > 0 and j > i, "could not locate cross-term block"
    patched = text[:i] + text[j:]
    assert patched.count("{") == patched.count("}"), "patch broke brace balance"

    runner = _build_with_patch(patched, tmp_path / "build_dropterm")

    traj = trajectory_constant_with_noise(
        n_ticks=2000,
        dt=0.005,
        a_body=(0.05, -0.03, 0.02),
        gyro=(0.0, 0.0, 0.0),
        seed=0,
        of_noise_std=0.05,   # 5 cm/s noise - larger so the bias update has signal
    )
    sim = run_sim(traj)
    fw = run_firmware(runner, traj)
    result = compare_trajectories(sim, fw, dt=0.005)
    assert not result.passed, (
        "dropped cross-term in predict must be caught; gate passed. "
        "This is the exact historical defect #1.\n"
        + format_failure("self_test_drop_cross_term", result)
    )


def test_self_test_constant_bias_in_predict(tmp_path, ekf_runner):
    """Add a constant bias term to the predict step on the Z axis.

    A +0.5 m/s^2 bias on z (50x larger than a_body_z = 0.02, so the
    magnitude is unmissable). After 2000 ticks the integrated bias is
    5 m/s - well above any compiler-noise floor on the state vector.

    The Z axis is chosen because:
      - x/y use the OF measurement which would partially correct
      - the z-rate update is much weaker (R_z=0.04 vs R_of=6e-4), so the
        bias correction is slower and the divergence is more visible
    """
    src = Path("API/ekf.c").resolve()
    text = src.read_text(encoding="utf-8")
    needle = "e->x[2] += (a_body_z - e->x[5]) * dt;"
    patched = text.replace(
        needle,
        "e->x[2] += (a_body_z - e->x[5]) * dt + 0.5f;",
        1,
    )
    assert patched != text, "patch did not apply"

    runner = _build_with_patch(patched, tmp_path / "build_bias")

    traj = trajectory_constant_with_noise(
        n_ticks=2000,
        dt=0.005,
        a_body=(0.0, 0.0, 0.0),
        gyro=(0.0, 0.0, 0.0),
        seed=0,
        of_noise_std=0.0,
        z_rate_meas=0.0,
        z_rate_noise_std=0.2,
    )
    sim = run_sim(traj)
    fw = run_firmware(runner, traj)
    result = compare_trajectories(sim, fw, dt=0.005)
    assert not result.passed, (
        "+0.5 m/s^2 bias in predict must be caught; gate passed.\n"
        + format_failure("self_test_predict_bias", result)
    )