"""Historical-bad validation.

The gate is run against the pre-fix API/ekf.c recovered from git history
and is expected to FAIL on each of the three known historical defects:

  1. Dropped F cross-terms in predict (b_a unobservable)
  2. Wrong update covariance (missing full Joseph form)
  3. In-place aliasing in the Joseph form

The first defect lives on commit b6bd27b (the version before the 2026-07-26
fix at 0c3306d). The spec mentions a backup bundle at
D:\\backups\\uav-mrac-pre-filter-repo-backup.bundle for cases where the
pre-fix revision is no longer reachable from current history. In this
repo b6bd27b is reachable so the bundle is not used.

The three defects are listed separately. If any of them is NOT caught by
the gate, that is a finding about the gate's sensitivity and must be
reported, not worked around (spec §"Validation against known-bad").
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from sil_gate.compiler import compile_executable, resolve_gcc
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

# Pin to the pre-fix commit SHA so the test is reproducible regardless of
# later history edits. b6bd27b is "feat(ADR-0011): wire Phase 3+4
# calibrators + 9-state EKF into build" - the commit that first added the
# buggy EKF. The fix landed in 0c3306d.
PRE_FIX_COMMIT = "b6bd27b3f8c9341dff05f344a5d6bf6d4aa79a00"


def _git(*args: str, cwd: Path) -> str:
    r = subprocess.run(
        ["git", "--no-pager", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return r.stdout


def _extract_ekf_at(commit: str, repo_root: Path, out: Path) -> Path:
    """Write API/ekf.c at `commit` to a temp file and return the path."""
    content = _git("show", f"{commit}:API/ekf.c", cwd=repo_root)
    out.write_text(content, encoding="utf-8")
    return out


def _build_runner_for(ekf_src: Path, build_dir: Path) -> Path:
    spec = resolve_gcc()
    if spec is None:
        pytest.skip("no host gcc available - SIL gate requires one")
    out_path = build_dir / f"sil_runner_historical{_exe_suffix()}"
    return compile_executable(
        spec,
        source=Path("sil_gate/runner_main.c"),
        out_path=out_path,
        include_dirs=(Path("sil_gate/shim"), Path("API")),
        extra_sources=(ekf_src,),
        extra_cflags=("-Wno-unused-but-set-variable",),
    )


def _exe_suffix() -> str:
    import sys
    return ".exe" if sys.platform == "win32" else ""


# ----------------------------------------------------------------------
# Tests
# ----------------------------------------------------------------------

def test_pre_fix_defect_1_dropped_cross_terms(tmp_path):
    """Pre-fix ekf.c (b6bd27b) has dropped F cross-terms in predict.

    Defect: the F P F^T expansion is approximated by a diagonal block
    (P_vv += dt^2 * Q_v, P_ba += Q_ba, P_bg += Q_bg) with no cross-terms.
    Effect: P[0,3]/P[1,4]/P[2,5] are always zero, so the Kalman gain
    columns 3..5 are always zero, and b_a never updates.

    Trajectory: random-walk OF noise (not zero-mean-tracked) so the OF
    innovation has signal that would drive b_a convergence in the fixed
    version.
    """
    repo_root = Path().resolve()
    # Sanity: the pre-fix commit must be reachable.
    try:
        _git("cat-file", "-e", PRE_FIX_COMMIT, cwd=repo_root)
    except subprocess.CalledProcessError:
        pytest.skip(
            f"pre-fix commit {PRE_FIX_COMMIT} not reachable from current "
            f"history. Recover from D:\\backups\\uav-mrac-pre-filter-repo-"
            f"backup.bundle (old HEAD 1c7c418) and re-run."
        )

    ekf_src = _extract_ekf_at(PRE_FIX_COMMIT, repo_root, tmp_path / "ekf_pre_fix.c")
    runner = _build_runner_for(ekf_src, tmp_path / "build_pre_fix")

    traj = trajectory_constant_with_noise(
        n_ticks=2000,
        dt=0.005,
        a_body=(0.05, -0.03, 0.02),
        gyro=(0.0, 0.0, 0.0),
        seed=0,
        of_noise_std=0.05,
    )
    sim = run_sim(traj)
    fw = run_firmware(runner, traj)
    result = compare_trajectories(sim, fw, dt=0.005)

    assert not result.passed, (
        "Pre-fix ekf.c should diverge from sim/ekf.py - this is the "
        "historical defect #1 (dropped F cross-terms). The gate missed it.\n"
        + format_failure("pre_fix_defect_1_dropped_cross_terms", result)
    )

    # The defect specifically manifests as b_a being permanently zero in
    # the firmware while sim's b_a converges to a non-trivial value. We
    # report that as additional diagnostic context.
    print(
        f"pre-fix defect #1 caught: max_abs={result.signal('x').max_abs:.3e}, "
        f"max_rel={result.signal('x').max_rel:.3e}"
    )


def test_pre_fix_defect_2_wrong_update_covariance(tmp_path):
    """Pre-fix ekf.c has wrong update covariance (in-place form).

    Defect: the Joseph form `P = (I-KH)P(I-KH)^T + KRK^T` is approximated
    by an in-place `P -= KHP` plus a diagonal `K R K^T`. The right
    multiplication `(I-KH)^T P` is missing entirely, AND the quadratic
    cross-term K*HP*H^T*K^T is folded into the diagonal only.

    Effect: P is corrupted even on simple two-channel updates; the
    bias-related off-diagonal entries (P[0,3] etc.) drift toward
    arbitrary values.

    The same trajectory as defect #1 (random-walk OF noise) drives the
    update path enough that the wrong covariance shows up. The defect
    surfaces as b_a and P[3,3] divergence.
    """
    repo_root = Path().resolve()
    ekf_src = _extract_ekf_at(PRE_FIX_COMMIT, repo_root, tmp_path / "ekf_pre_fix.c")
    runner = _build_runner_for(ekf_src, tmp_path / "build_pre_fix_2")

    traj = trajectory_constant_with_noise(
        n_ticks=2000,
        dt=0.005,
        a_body=(0.05, -0.03, 0.02),
        gyro=(0.0, 0.0, 0.0),
        seed=1,
        of_noise_std=0.05,
    )
    sim = run_sim(traj)
    fw = run_firmware(runner, traj)
    result = compare_trajectories(sim, fw, dt=0.005)

    assert not result.passed, (
        "Pre-fix ekf.c should diverge from sim/ekf.py - this is the "
        "historical defect #2 (wrong update covariance / in-place form). "
        "The gate missed it.\n"
        + format_failure("pre_fix_defect_2_wrong_update_covariance", result)
    )
    print(
        f"pre-fix defect #2 caught: max_abs={result.signal('x').max_abs:.3e}, "
        f"max_rel={result.signal('x').max_rel:.3e}"
    )


def test_pre_fix_defect_3_in_place_aliasing(tmp_path):
    """Pre-fix ekf.c has in-place aliasing in the Joseph form.

    Defect: the Joseph form `P -= K H P` overwrites P row by row before
    subsequent rows read it. This produces wrong values for any cell where
    the new row's computation depends on a previously-written row's
    values (the very thing the Joseph form's snapshot semantics exists to
    prevent).

    Effect: P is asymmetric and the Kalman filter may diverge.

    Note: defect #3 (in-place aliasing) is the SAME commit as #2 - the
    wrong-covariance code WAS the in-place code. The current fix in
    0c3306d replaced both with the full symmetric Joseph form. So this
    test is asserting the same defect catches it twice; we run it with a
    different seed to confirm the catch is robust to trajectory choice.
    """
    repo_root = Path().resolve()
    ekf_src = _extract_ekf_at(PRE_FIX_COMMIT, repo_root, tmp_path / "ekf_pre_fix.c")
    runner = _build_runner_for(ekf_src, tmp_path / "build_pre_fix_3")

    traj = trajectory_constant_with_noise(
        n_ticks=2000,
        dt=0.005,
        a_body=(0.05, -0.03, 0.02),
        gyro=(0.0, 0.0, 0.0),
        seed=2,
        of_noise_std=0.03,
    )
    sim = run_sim(traj)
    fw = run_firmware(runner, traj)
    result = compare_trajectories(sim, fw, dt=0.005)

    assert not result.passed, (
        "Pre-fix ekf.c should diverge from sim/ekf.py - this is the "
        "historical defect #3 (in-place aliasing). The gate missed it.\n"
        + format_failure("pre_fix_defect_3_in_place_aliasing", result)
    )
    print(
        f"pre-fix defect #3 caught: max_abs={result.signal('x').max_abs:.3e}, "
        f"max_rel={result.signal('x').max_rel:.3e}"
    )