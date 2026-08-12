"""CMake + arm-none-eabi-gcc build wrapper.

Mirrors the Windows Keil UV4 path but produces the same ELF/hex/bin outputs.
The firmware tree (API/, BSP/, TASK/, etc.) lives in the repo root; CMake
globs sources from there — no files are copied or moved.

Expected artifacts:
    firmware/build/JX_FLY.elf
    firmware/build/JX_FLY.hex    ← flash target
    firmware/build/JX_FLY.bin
    firmware/build/JX_FLY.map    ← linker map
"""
from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[2]   # repo root
_FIRMWARE_DIR = _ROOT / "firmware"
_BUILD_DIR = _FIRMWARE_DIR / "build"
_ELF = _BUILD_DIR / "JX_FLY.elf"
_HEX = _BUILD_DIR / "JX_FLY.hex"


@dataclass
class BuildResult:
    ok: bool
    elapsed_s: float
    stdout: str
    stderr: str
    elf_bytes: int
    error: str = ""

    def report(self) -> str:
        if self.ok:
            return (
                f"[build] ok  {self.elf_bytes} bytes  ({self.elapsed_s:.1f}s)"
                f"\n{self.stdout[-500:]}"
            )
        return (
            f"[build] FAIL ({self.elapsed_s:.1f}s)\n"
            f"stdout:\n{self.stdout[-1000:]}\n"
            f"stderr:\n{self.stderr[-1000:]}\n"
            f"error:\n{self.error}"
        )


def _env() -> dict:
    """Environment with the arm-none-eabi toolchain on PATH.

    Searches several common install locations: PATH itself, the ARM GNU
    Toolchain tarball default, the user's local prefix, and the apt-prefix
    symlink location. Returns the env unchanged if gcc is already findable.
    """
    import os
    import shutil

    env = dict(os.environ)
    if shutil.which("arm-none-eabi-gcc", path=env.get("PATH")):
        return env

    home = Path.home()
    candidates = [
        home / ".local" / "arm-toolchain" / "bin",                              # setup_linux_toolchain.sh
        home / "opt" / "arm-gnu-toolchain-14.2.rel1-x86_64-arm-none-eabi" / "bin",  # ARM GNU tarball
        Path("/opt/arm-gnu-toolchain-14.2.rel1-x86_64-arm-none-eabi/bin"),     # system-wide tarball
        Path("/usr/bin"),                                                       # apt: gcc-arm-none-eabi
    ]
    for d in candidates:
        if (d / "arm-none-eabi-gcc").exists():
            env["PATH"] = f"{d}:{env.get('PATH', '')}"
            return env
    return env


def _run_cmake(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        env=_env(),
    )


def configure(cmake_flags: str = "") -> BuildResult:
    """Run cmake -B firmware/build -S firmware [cmake_flags]."""
    import time
    t0 = time.monotonic()

    cmd = ["cmake",
           "-B", str(_BUILD_DIR),
           "-S", str(_FIRMWARE_DIR),
           "-DCMAKE_TOOLCHAIN_FILE=cmake/arm-none-eabi-gcc.toolchain.cmake"]
    if cmake_flags:
        cmd.extend(cmake_flags.split())

    proc = _run_cmake(cmd, cwd=_ROOT)
    elapsed = time.monotonic() - t0

    if proc.returncode != 0:
        return BuildResult(
            ok=False, elapsed_s=elapsed,
            stdout=proc.stdout, stderr=proc.stderr,
            elf_bytes=0, error=f"cmake configure failed (rc={proc.returncode})",
        )

    return BuildResult(
        ok=True, elapsed_s=elapsed,
        stdout=proc.stdout, stderr=proc.stderr,
        elf_bytes=0,
    )


def build(jobs: int | None = None) -> BuildResult:
    """Run cmake --build firmware/build [--parallel N].

    Args:
        jobs: Number of parallel jobs. None = auto (cmake default).
    """
    import time
    t0 = time.monotonic()

    cmd = ["cmake", "--build", str(_BUILD_DIR)]
    if jobs:
        cmd.extend(["--parallel", str(jobs)])

    proc = _run_cmake(cmd, cwd=_ROOT)
    elapsed = time.monotonic() - t0

    elf_bytes = _ELF.stat().st_size if _ELF.exists() else 0

    if proc.returncode != 0:
        return BuildResult(
            ok=False, elapsed_s=elapsed,
            stdout=proc.stdout, stderr=proc.stderr,
            elf_bytes=elf_bytes,
            error=f"cmake --build failed (rc={proc.returncode})",
        )

    return BuildResult(
        ok=True, elapsed_s=elapsed,
        stdout=proc.stdout, stderr=proc.stderr,
        elf_bytes=elf_bytes,
    )


def all(jobs: int | None = None) -> BuildResult:
    """Configure then build. Convenience wrapper."""
    cfg = configure()
    if not cfg.ok:
        return cfg
    return build(jobs=jobs)


def artifact_paths() -> dict[str, Path]:
    """Return the paths of all build artifacts."""
    return {
        "elf": _ELF,
        "hex": _HEX,
        "bin": _BUILD_DIR / "JX_FLY.bin",
        "map": _BUILD_DIR / "JX_FLY.map",
    }
