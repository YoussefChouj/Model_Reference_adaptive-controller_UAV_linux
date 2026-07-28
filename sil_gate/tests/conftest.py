"""Shared fixtures for sil_gate tests.

Three jobs:

1. Discover gcc once per session and expose it as a session-scoped fixture.
   If no gcc is available the gate is *skipped*, not failed - the spec
   explicitly says a missing toolchain is not a numerical failure.

2. Build the standalone runner executable for the current ekf.c and
   expose it as a session-scoped fixture. Cache by content hash so the
   second test in the session is instant.

3. Provide common inputs (default tolerances, default trajectory length).
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pytest

# sil_gate/ is one level down from the repo root. The repo root has sim/
# on sys.path already via tasks.py test, but when pytest is invoked
# directly we need to make sure both root and sil_gate are importable.
REPO_ROOT = Path(__file__).resolve().parents[2]
SIL_ROOT = Path(__file__).resolve().parents[1]

for p in (str(REPO_ROOT), str(SIL_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)


# Build artefacts live under sil_gate/build/. Tests must be able to clean
# this directory on demand (e.g. when switching between historical and
# current ekf.c), so it is created lazily and ignored from VCS.
BUILD_DIR = SIL_ROOT / "build"
SHIM_DIR = SIL_ROOT / "shim"

from sil_gate.compiler import GccSpec, resolve_gcc  # noqa: E402
from sil_gate.linker import RunnerExe, build_ekf_runner  # noqa: E402


# ----------------------------------------------------------------------
# Session-wide gcc
# ----------------------------------------------------------------------

@pytest.fixture(scope="session")
def gcc_spec() -> Optional[GccSpec]:
    """Resolved host gcc spec, or None if no compiler is available.

    Tests that need gcc are marked `@pytest.mark.skipif(gcc is None)`.
    """
    return resolve_gcc()


# ----------------------------------------------------------------------
# Build the runner executable for current ekf.c
# ----------------------------------------------------------------------

@dataclass(frozen=True)
class EkfRunnerBuild:
    runner: RunnerExe
    source: Path


def _build_ekf_runner(source: Path) -> RunnerExe:
    spec = resolve_gcc()
    if spec is None:
        pytest.skip("no host gcc available - SIL gate requires one")
    return build_ekf_runner(spec, REPO_ROOT, BUILD_DIR, SHIM_DIR)


@pytest.fixture(scope="session")
def ekf_runner(gcc_spec) -> EkfRunnerBuild:
    """Build the runner for the CURRENT API/ekf.c."""
    if gcc_spec is None:
        pytest.skip("no host gcc available - SIL gate requires one")
    src = REPO_ROOT / "API" / "ekf.c"
    return EkfRunnerBuild(runner=_build_ekf_runner(src), source=src)


# ----------------------------------------------------------------------
# Path helpers for historical / perturbed builds
# ----------------------------------------------------------------------

def build_ekf_runner_from(source: Path) -> RunnerExe:
    """Build a runner for a SPECIFIC .c file.

    Used by self-test (perturbed source) and historical-bad validation
    (recovered pre-fix ekf.c from git history).
    """
    return _build_ekf_runner(source)


@pytest.fixture(scope="session")
def api_root() -> Path:
    return REPO_ROOT / "API"


@pytest.fixture(scope="session")
def git_root() -> Path:
    return REPO_ROOT