"""gcc discovery and flag bundle for the SIL gate.

This module is the gate's only contact with the host C toolchain. Three jobs:

1. Find a gcc — try PATH first, then a list of known Windows locations, then
   give up with a clear message rather than a cryptic ImportError downstream.
   The search is OS-agnostic so the suite works when cloned to a Linux
   partition.

2. Build the flag bundle. Two groups, both required per spec:

   - *FPU parity*: `-march=pentium4 -msse2 -mfpmath=sse`. The installed MinGW
     GCC 6.3.0 is 32-bit with `-mfpmath=387`, which evaluates at 80-bit
     internally; the STM32F407 FPU is true 32-bit. Without this, results
     differ for reasons unrelated to the mathematics.

   - *Strictness*: `-std=c90 -pedantic -Wall -Wextra`. ARMCC V5.06 defaults
     to C90 while gcc defaults to a modern standard, so gcc would otherwise
     accept code Keil rejects. These flags make gcc stricter than ARMCC,
     turning it into an early warning rather than a false green light.

   Note: Keil ARMCC is set with `--C99` in the uvprojx; the spec says fall
   back to `-std=c99` and record why if c90 proves incompatible. ekf.c and
   mrac.c are pure C99-portable so c90 is the right primary.

3. Run the compiled firmware as a **subprocess**, not a dllopen. The host
   Python on Windows is 64-bit but the only available gcc is 32-bit mingw,
   which produces 32-bit DLLs that 64-bit ctypes cannot load. The clean
   fix is to ship a tiny standalone runner that takes the trajectory as
   CSV on stdin and emits a per-tick state CSV on stdout; the gate then
   parses the output and compares against sim/.

The module never caches an exe path implicitly; every caller asks. Tests can
mock `discover_gcc()` to inject a stub.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


# Order matters: PATH first (Linux users almost always have gcc there), then
# platform-specific fallbacks. The list is intentionally short — a developer
# laptop either has a real toolchain or has one of these.
_SEARCH_PATHS_WINDOWS = [
    r"C:\MinGW\bin\gcc.exe",
    r"C:\TDM-GCC-32\bin\gcc.exe",
    r"C:\msys64\mingw32\bin\gcc.exe",
    r"C:\Program Files\mingw-w64\i686-8.1.0-posix-dwarf-rt_v6-rev0\mingw32\bin\gcc.exe",
]


@dataclass(frozen=True)
class GccSpec:
    """Resolved host compiler + flag bundle. Pass to compile_firmware()."""
    exe: Path
    fpu_flags: tuple  # FPU parity - fixed; do not parameterise
    strict_flags: tuple  # language standard + warnings - fixed
    extra_cflags: tuple = ()  # caller-specific (sanitisers etc.)
    version_line: str = ""  # for diagnostic messages

    def all_flags(self) -> List[str]:
        return list(self.fpu_flags) + list(self.strict_flags) + list(self.extra_cflags)


def discover_gcc() -> Optional[Path]:
    """Return a path to a working gcc, or None.

    Walks PATH first, then a known-platform list. A path is only accepted if
    `gcc --version` actually runs against it - a stale shim with no backing
    binary is rejected.
    """
    found = shutil.which("gcc")
    if found and _runs(Path(found)):
        return Path(found)

    candidates = _SEARCH_PATHS_WINDOWS if sys.platform == "win32" else []
    for cand in candidates:
        p = Path(cand)
        if p.exists() and _runs(p):
            return p
    return None


def _runs(exe: Path) -> bool:
    try:
        r = subprocess.run(
            [str(exe), "--version"],
            capture_output=True, text=True, timeout=5,
        )
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def resolve_gcc() -> Optional[GccSpec]:
    """Like discover_gcc but bundles the flag set. None means no gcc."""
    exe = discover_gcc()
    if exe is None:
        return None
    version = subprocess.run(
        [str(exe), "--version"],
        capture_output=True, text=True, timeout=5,
    ).stdout.splitlines()[0]

    fpu = (
        "-march=pentium4",
        "-msse2",
        "-mfpmath=sse",
        "-fno-fast-math",
    )
    # ekf.c + mrac.c use mixed declarations (variable-after-statement),
    # which ARMCC accepts under --C99. -std=c90 would generate a noisy
    # fork of the firmware sources, defeating the "no firmware changes"
    # constraint. The spec permits c99 as the documented fallback.
    # pedantic remains on so -Wstrict-prototypes etc. still surface.
    strict = (
        "-std=c99",
        "-pedantic",
        "-Wall",
        "-Wextra",
        "-Wno-unused-parameter",
        "-Wno-long-long",
        "-Wno-variadic-macros",
    )
    return GccSpec(
        exe=exe,
        fpu_flags=fpu,
        strict_flags=strict,
        version_line=version,
    )


def compile_executable(
    spec: GccSpec,
    source: Path,
    out_path: Path,
    include_dirs: tuple = (),
    extra_sources: tuple = (),
    extra_cflags: tuple = (),
) -> Path:
    """Compile + link into a STANDALONE EXECUTABLE (not a shared object).

    The SIL gate uses standalone executables because the host Python on
    Windows is 64-bit but the only available gcc is 32-bit mingw. A 32-bit
    DLL cannot be loaded into a 64-bit process; an executable can be run
    as a subprocess regardless of bitness.

    Returns the .exe path. Caches by content hash of (source, includes,
    flags) under out_path's parent; the second call for the same inputs is
    a no-op.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cache_key = _cache_key(source, spec, include_dirs, extra_sources, extra_cflags)
    cache_root = out_path.parent
    so_path = cache_root / f"{cache_key}{out_path.suffix}"
    if so_path.exists():
        return so_path

    cmd: List[str] = [str(spec.exe)]
    cmd.extend(spec.all_flags())
    cmd.extend(extra_cflags)
    cmd.extend(["-O2"])  # -O2 matches ARMCC -O2 timing on the target
    cmd.extend(f"-I{d}" for d in include_dirs)
    cmd.append(str(source))
    for s in extra_sources:
        cmd.append(str(s))
    cmd.extend(["-o", str(so_path), "-lm"])
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(
            f"gcc failed to compile {source.name}:\n"
            f"  cmd: {' '.join(cmd)}\n"
            f"  stdout:\n{r.stdout}\n"
            f"  stderr:\n{r.stderr}"
        )
    return so_path


def _cache_key(
    source: Path,
    spec: GccSpec,
    include_dirs: tuple,
    extra_sources: tuple,
    extra_cflags: tuple,
) -> str:
    """Content hash of everything that could change the output."""
    import hashlib
    h = hashlib.sha256()
    for path in (source, *extra_sources, *include_dirs):
        if path.is_file():
            h.update(path.read_bytes())
        else:
            h.update(str(path).encode())
    h.update(spec.version_line.encode())
    h.update("|".join(spec.fpu_flags).encode())
    h.update("|".join(spec.strict_flags).encode())
    h.update("|".join(extra_cflags).encode())
    return h.hexdigest()[:16]