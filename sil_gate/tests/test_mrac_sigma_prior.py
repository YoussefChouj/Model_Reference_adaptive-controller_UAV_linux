"""Host-test runner for the sigma-prior opt-in (prior-D / ADR-0013 D5).

Drives the standalone executable produced by `sil_gate.linker.build_mrac_sigma_prior_runner`
and asserts every one of the four spec'd tests passes:

  T1: sigma_prior = 0 reproduces baseline (no behavioural drift)
  T2: sigma_prior large converges to Theta_prior
  T3: Theta_prior = 0 reproduces baseline sigma-mod (term vanishes)
  T4: Projection intact under large prior (Lyapunov contract)

A deliberately-perturbed copy of mrac.c (T_drop_prior_term) makes the
runner fail loudly; this is the self-test that proves the host test is
actually checking the prior-attractor wiring and not just re-deriving
silently. If T_drop_prior_term passes, the gate is not sensitive enough
to be useful.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from sil_gate.compiler import compile_executable, resolve_gcc
from sil_gate.linker import build_mrac_sigma_prior_runner


SIL_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[2]
BUILD_DIR = SIL_ROOT / "build"
SHIM_DIR = SIL_ROOT / "shim"


# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------

@pytest.fixture(scope="session")
def mrac_sigma_prior_runner(gcc_spec):
    """Build the standalone test_mrac_sigma_prior.c + mrac.c runner.

    Skips if no gcc is available.
    """
    if gcc_spec is None:
        pytest.skip("no host gcc available - SIL gate requires one")
    return build_mrac_sigma_prior_runner(
        resolve_gcc(), REPO_ROOT, BUILD_DIR, SHIM_DIR,
    )


def _exe_suffix() -> str:
    import sys
    return ".exe" if sys.platform == "win32" else ""


def _run(runner: Path) -> str:
    """Execute the host-test runner and return stdout."""
    proc = subprocess.run(
        [str(runner)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    return proc.stdout + (("\n[stderr]\n" + proc.stderr) if proc.stderr else "")


# ----------------------------------------------------------------------
# The four spec'd tests
# ----------------------------------------------------------------------

def test_sigma_prior_zero_reproduces_baseline(mrac_sigma_prior_runner):
    """sigma_prior=0 must keep the baseline gradient (term is identically 0)."""
    out = _run(mrac_sigma_prior_runner)
    assert "T1 pitch.Theta[0] > 0" not in out or "FAIL  T1 pitch.Theta[0] > 0" not in out, (
        "T1 failed — sigma_prior=0 should still let adaptation run.\n"
        + out
    )
    assert "FAIL" not in out, (
        "mrac_sigma_prior test runner reported FAILs:\n" + out
    )
    assert "0 failure(s)" in out, (
        "mrac_sigma_prior test runner reported failures:\n" + out
    )


def test_sigma_prior_large_converges_to_prior(mrac_sigma_prior_runner):
    """sigma_prior large + non-zero prior must pull Theta toward Theta_prior."""
    out = _run(mrac_sigma_prior_runner)
    assert "FAIL  T2" not in out, (
        "T2 failed — sigma_prior large did not converge to Theta_prior.\n"
        + out
    )


def test_theta_prior_zero_reproduces_sigma_mod(mrac_sigma_prior_runner):
    """sigma_prior > 0 + Theta_prior = 0 must reduce to a stronger sigma-mod."""
    out = _run(mrac_sigma_prior_runner)
    assert "FAIL  T3" not in out, (
        "T3 failed — sigma_prior > 0 with Theta_prior = 0 should reduce to a "
        "stronger sigma-mod (baseline + extra leakage), but it did not behave.\n"
        + out
    )


def test_projection_intact_under_large_prior(mrac_sigma_prior_runner):
    """A large prior outside What_limit must NOT violate the projection operator.

    This is the Lyapunov contract: the prior-attractor term is gradient-style,
    so the existing projection bounds |Theta| regardless of the source.
    """
    out = _run(mrac_sigma_prior_runner)
    assert "FAIL  T4" not in out, (
        "T4 failed — projection operator must bound |Theta| even when the "
        "prior is set far outside What_limit.\n"
        + out
    )


# ----------------------------------------------------------------------
# Self-test: prove the gate is actually checking the new wiring
# ----------------------------------------------------------------------

def _build_with_patch(patched_mrac_text: str, tmpdir: Path) -> Path:
    """Compile mrac.c + the test harness with the patched mrac.c in place.

    The patched source REPLACES the real mrac.c in the build. This is how
    the sil_gate generalises to "did you actually change the new term".
    """
    tmpdir.mkdir(parents=True, exist_ok=True)
    patched = tmpdir / "mrac_patched.c"
    patched.write_text(patched_mrac_text, encoding="utf-8")
    math_src = REPO_ROOT / "API" / "mrac_math.c"
    out_path = tmpdir / f"sil_runner_mrac_patched{_exe_suffix()}"
    return compile_executable(
        resolve_gcc(),
        source=REPO_ROOT / "API" / "tests" / "test_mrac_sigma_prior.c",
        out_path=out_path,
        include_dirs=(SHIM_DIR, REPO_ROOT / "API"),
        extra_sources=(patched, math_src),
        extra_cflags=(
            "-DMRAC_ENABLE_SIGMA_PRIOR=1",
            "-Wno-unused-but-set-variable",
        ),
    )


def test_self_test_drop_prior_term(tmp_path, gcc_spec):
    """Drop the sigma_prior*(Theta - Theta_prior) fold. The gate must catch it.

    The patch: replace the entire prior-attractor LINE (including its
    leading whitespace and trailing newline) with an empty string. The
    fold now lives inside the grad accumulation loop (it is subtracted from
    grad before projection), so the line is a complete statement:
    `grad[i] -= sigma_prior * (state->Theta[i] - Theta_prior[axis_id][i]);`
    Dropping the whole line leaves the `for { ... }` loop body empty, which
    is syntactically valid, and the prior term is gone entirely.
    """
    if gcc_spec is None:
        pytest.skip("no host gcc available - SIL gate requires one")

    src = (REPO_ROOT / "API" / "mrac.c").read_text(encoding="utf-8")
    # The prior-attractor fold is one line inside the grad-accumulation
    # loop in the #ifdef MRAC_ENABLE_SIGMA_PRIOR block. Drop the WHOLE LINE
    # so the loop body stays syntactically valid (empty).
    needle_line = (
        "                grad[i] -= sigma_prior * (state->Theta[i] - Theta_prior[axis_id][i]);\n"
    )
    assert needle_line in src, "expected opt-in prior fold in API/mrac.c"
    patched = src.replace(needle_line, "")
    assert patched != src, "patch did not apply"
    assert "sigma_prior * (state->Theta[i] - Theta_prior[axis_id][i])" not in patched, (
        "patch left residual occurrences"
    )

    runner = _build_with_patch(patched, tmp_path / "build_drop_prior")
    out = _run(runner)
    # T2 must fail: with the term gone, sigma_prior=50 does not pull
    # Theta toward the prior, so |Theta - prior| >> 0.01.
    assert "FAIL  T2" in out, (
        "T2 must fail when the prior-attractor term is dropped. If T2 "
        "passes, the test is not exercising the new wiring.\n"
        + out
    )
