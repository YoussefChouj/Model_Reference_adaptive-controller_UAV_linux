"""Standalone executable runner for the SIL gate.

The gate compiles a tiny C harness (sil_gate/runner_main.c + API/ekf.c or
API/mrac.c) into a standalone executable and drives it as a subprocess.
This avoids the cross-architecture DLL hell: the host Python may be 64-bit
while the only available gcc is 32-bit mingw (Windows reality), and a
32-bit DLL cannot be loaded into a 64-bit process. An executable can be
subprocess.run() regardless of bitness.

Wire protocol (CSV-on-stdin/stdout, kept deliberately simple):

  Header line: "EKF9 v1"        # identifies the runner build
  Then N records of 6 floats:   # one per tick
    dt,a_body_x,a_body_y,a_body_z,of_x,of_y,z_rate
  End: "END"

  Runner emits:
    Header:  "EKF9 v1"
    N records of 12 floats:
      x[0..8], nis, k_last[0..2]
    Footer:  "END"

If a build emits more than the documented columns, the gate ignores the
extras (forward-compat). If it emits fewer, the gate fails loudly.

This module does NOT do numerical comparison; that lives in runner.py.
"""
from __future__ import annotations

import csv
import io
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence

import numpy as np

from sil_gate.compiler import GccSpec, compile_executable


# ----------------------------------------------------------------------
# Build the runner executable
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class RunnerExe:
    path: Path
    module: str  # "ekf9" | (future: "mrac") — used to pick the runner_main.c source


def build_ekf_runner(
    spec: GccSpec,
    repo_root: Path,
    build_dir: Path,
    shim_dir: Path,
) -> RunnerExe:
    """Compile sil_gate/runner_main.c + API/ekf.c into a standalone .exe.

    The runner_main.c source is shared by every module - it reads the module
    name from the header line on stdin ("EKF9 v1") and dispatches to the
    module-specific entry points. So the build only varies by which
    firmware source is included.

    Include dirs:
      - shim_dir  : sil_gate/shim/* (test-only stm32f4xx.h + transitive)
      - repo_root/API : so `#include "ekf.h"` resolves in the runner

    The repo root itself is NOT added as an include dir - that would
    accidentally pick up Global_file/ headers instead of the shims.
    """
    runner_src = repo_root / "sil_gate" / "runner_main.c"
    ekf_src = repo_root / "API" / "ekf.c"
    out_path = build_dir / f"sil_runner_ekf{_exe_suffix()}"
    so = compile_executable(
        spec,
        source=runner_src,
        out_path=out_path,
        include_dirs=(shim_dir, repo_root / "API"),
        extra_sources=(ekf_src,),
        extra_cflags=("-Wno-unused-but-set-variable",),
    )
    return RunnerExe(path=so, module="ekf9")


def build_mrac_sigma_prior_runner(
    spec: GccSpec,
    repo_root: Path,
    build_dir: Path,
    shim_dir: Path,
) -> Path:
    """Compile API/tests/test_mrac_sigma_prior.c + API/mrac.c + API/mrac_math.c
    into a standalone host-test runner.

    The runner is a pure host harness: it does not consume the wire protocol
    of run_ekf_subprocess. It runs to completion, prints its result lines,
    and exits. The sil_gate pytest case reads stdout and counts
    "FAIL"/"failure(s)" substrings. Returns the .exe path.

    Defined: -DMRAC_ENABLE_SIGMA_PRIOR=1 so the opt-in branch is reachable.
    """
    runner_src = repo_root / "API" / "tests" / "test_mrac_sigma_prior.c"
    mrac_src = repo_root / "API" / "mrac.c"
    mrac_math_src = repo_root / "API" / "mrac_math.c"
    out_path = build_dir / f"sil_runner_mrac_sigma_prior{_exe_suffix()}"
    return compile_executable(
        spec,
        source=runner_src,
        out_path=out_path,
        include_dirs=(shim_dir, repo_root / "API"),
        extra_sources=(mrac_src, mrac_math_src),
        extra_cflags=(
            "-DMRAC_ENABLE_SIGMA_PRIOR=1",
            "-Wno-unused-but-set-variable",
        ),
    )


def _exe_suffix() -> str:
    import sys
    return ".exe" if sys.platform == "win32" else ""


# ----------------------------------------------------------------------
# Drive the subprocess
# ----------------------------------------------------------------------
def run_ekf_subprocess(
    runner: RunnerExe,
    dt: float,
    a_body: Sequence[tuple],
    of_xy: Sequence[tuple],
    z_rate: Sequence[float],
    timeout_s: float = 60.0,
) -> "EKF9Run":
    """Drive the runner with a per-tick trajectory, return parsed results."""
    if not (len(a_body) == len(of_xy) == len(z_rate)):
        raise ValueError("a_body / of_xy / z_rate must have equal length")
    n = len(a_body)

    # Build stdin payload. Module name is uppercased because the C runner
    # uses strncmp(..., "EKF9", 4) which is case-sensitive; the module
    # field in RunnerExe is lowercase for Python naming consistency.
    sin = io.StringIO()
    sin.write(f"{runner.module.upper()} v1\n")
    sin.write(f"{n}\n")
    for k in range(n):
        a = a_body[k]
        o = of_xy[k]
        z = z_rate[k]
        sin.write(f"{dt:.9e},{a[0]:.9e},{a[1]:.9e},{a[2]:.9e},{o[0]:.9e},{o[1]:.9e},{z:.9e}\n")
    sin.write("END\n")
    payload = sin.getvalue()

    proc = subprocess.run(
        [str(runner.path)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=timeout_s,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"runner exited {proc.returncode}: stderr:\n{proc.stderr}"
        )

    # Parse stdout
    sout = proc.stdout
    lines = sout.strip().splitlines()
    if not lines or not lines[0].startswith("EKF9 v1"):
        raise RuntimeError(
            f"runner produced unexpected header: {lines[:1] if lines else '<empty>'}\n"
            f"stderr: {proc.stderr}"
        )
    # Find END marker
    try:
        end_idx = next(i for i, ln in enumerate(lines) if ln.strip() == "END")
    except StopIteration:
        raise RuntimeError(f"runner missing END marker; stdout:\n{sout}")
    record_lines = lines[1:end_idx]
    if len(record_lines) != n:
        raise RuntimeError(
            f"runner emitted {len(record_lines)} records for {n} ticks"
        )

    xs = np.zeros((n, 9), dtype=np.float64)
    niss = np.zeros(n, dtype=np.float64)
    klasts = np.zeros((n, 3), dtype=np.float64)
    for k, ln in enumerate(record_lines):
        parts = [float(v) for v in ln.split(",")]
        if len(parts) < 13:
            raise RuntimeError(
                f"runner record too short ({len(parts)} cols): {ln}"
            )
        xs[k] = parts[0:9]
        niss[k] = parts[9]
        klasts[k] = parts[10:13]
    return EKF9Run(x=xs, nis=niss, k_last=klasts)


@dataclass
class EKF9Run:
    x: np.ndarray          # (n, 9)
    nis: np.ndarray        # (n,)
    k_last: np.ndarray     # (n, 3)


def system() -> str:
    """Exposed for tests that need to branch on host OS (e.g. extension)."""
    import sys
    return sys.platform