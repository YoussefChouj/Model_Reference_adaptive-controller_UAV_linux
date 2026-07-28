"""Canonical task runner. One command per operation, identical in PowerShell and Git Bash.

  python tasks.py doctor       # check the environment before anything else
  python tasks.py test         # full suite
  python tasks.py test sim     # one lane
  python tasks.py budget       # build-budget gate (flash / RAM / stack / warnings)
  python tasks.py verify       # ELF-vs-flash check (needs the SWD probe)

`make` is not installed on this machine (only `mingw32-make`), and the two shells disagree on
syntax, so the runner is plain Python -- the one interpreter that is always present. Every
subprocess is launched with VENV_PY, never a bare `python`, so a task cannot land on the wrong
interpreter no matter which shell or activation state it was started from.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
VENV_PY = ROOT / ".venv" / "Scripts" / "python.exe"

LANES = {
    "livewatch": "ground_station/livewatch/tests",
    "gui": "ground_station/gui/tests",
    "sim": "sim/tests",
    "flight": "flight_analysis/tests",
    "sil": "sil_gate/tests",
}

# Import-time cost of the heavy scientific stack makes these worth knowing before you wait.
REQUIRED_PKGS = ["pyocd", "serial", "numpy", "scipy", "pytest", "yaml", "matplotlib"]


def run(*args: str, check: bool = True) -> int:
    """Run a command under the venv interpreter, streaming output."""
    print(f"$ {' '.join(str(a) for a in args)}", flush=True)
    rc = subprocess.call([str(a) for a in args], cwd=ROOT)
    if rc != 0 and check:
        sys.exit(rc)
    return rc


def py(*args: str, check: bool = True) -> int:
    return run(VENV_PY, *args, check=check)


def task_doctor(argv: list[str]) -> int:
    """Report machine state. Run this first in a fresh session -- it answers the questions
    that otherwise get re-derived wrongly (which Python? which packages? is git going to
    hang? is the probe free?)."""
    ok = True

    print("== interpreter ==")
    if not VENV_PY.exists():
        print(f"  FAIL  no venv at {VENV_PY}")
        print("        create it: py -3.13 -m venv .venv")
        return 1
    out = subprocess.check_output(
        [str(VENV_PY), "-c", "import sys; print(sys.version.split()[0])"], text=True
    ).strip()
    print(f"  ok    {VENV_PY}  (Python {out})")
    if Path(sys.executable).resolve() != VENV_PY.resolve():
        print(f"  note  you invoked this with {sys.executable}")
        print("        harmless -- tasks always re-launch under the venv interpreter")

    print("== packages ==")
    missing = [
        p for p in REQUIRED_PKGS
        if subprocess.call(
            [str(VENV_PY), "-c", f"import {p}"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        ) != 0
    ]
    if missing:
        ok = False
        print(f"  FAIL  missing: {', '.join(missing)}")
        print("        python tasks.py install")
    else:
        print(f"  ok    all {len(REQUIRED_PKGS)} present -- do NOT pip install anything")

    print("== git ==")
    pager = subprocess.run(
        ["git", "config", "--get", "core.pager"],
        cwd=ROOT, capture_output=True, text=True,
    ).stdout.strip()
    if pager == "cat":
        print("  ok    core.pager=cat (git log/diff will not hang)")
    else:
        ok = False
        print(f"  WARN  core.pager={pager or '<unset>'} -- git log/diff may block until timeout")
        print("        git config core.pager cat   (or always use `git --no-pager`)")

    print("== probe ==")
    if shutil.which("pyocd") or (ROOT / ".venv" / "Scripts" / "pyocd.exe").exists():
        rc = subprocess.call(
            [str(VENV_PY), "-m", "pyocd", "list"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        if rc == 0:
            print("  ok    pyocd responds -- see hardware-safety.mdc before any live read")
        else:
            # Not a failure: the probe is optional for everything except `verify`.
            print("  note  no probe enumerated (unplugged, or uVision holds the session)")
            print("        this blocks `verify` only -- tests and code work are unaffected")
    print()
    print("READY" if ok else "ISSUES ABOVE -- fix before starting")
    return 0 if ok else 1


def task_test(argv: list[str]) -> int:
    """Full suite, or one lane: test [livewatch|gui|sim|flight]"""
    if argv:
        unknown = [a for a in argv if a not in LANES]
        if unknown:
            print(f"unknown lane(s): {', '.join(unknown)}")
            print(f"available: {', '.join(LANES)}")
            return 1
        paths = [LANES[a] for a in argv]
    else:
        paths = list(LANES.values())
    return py("-m", "pytest", "-q", *paths, check=False)


def task_verify(argv: list[str]) -> int:
    """ELF-vs-flash check. MANDATORY before trusting any live read. Needs the SWD probe."""
    return py("-m", "ground_station.livewatch", "verify", *argv, check=False)


def task_install(argv: list[str]) -> int:
    """Install pinned dependencies into the venv. Not needed unless doctor says so."""
    return py("-m", "pip", "install", "-r", "requirements.txt", check=False)


def task_freeze(argv: list[str]) -> int:
    """Regenerate requirements.txt after a deliberate dependency change."""
    out = subprocess.check_output([str(VENV_PY), "-m", "pip", "freeze"], text=True)
    (ROOT / "requirements.txt").write_text(out, encoding="utf-8")
    print(f"wrote requirements.txt ({len(out.splitlines())} packages)")
    return 0


def task_graph(argv: list[str]) -> int:
    """Rebuild the graphify code graph after editing source."""
    return py(
        "-c",
        "from graphify.watch import _rebuild_code; from pathlib import Path; "
        "_rebuild_code(Path('.'))",
        check=False,
    )


def task_budget(argv: list[str]) -> int:
    """Run the build-budget gate. Reads OBJ artifacts; never invokes the build."""
    return py("-m", "ground_station.build_budget", *argv, check=False)


TASKS = {
    "doctor": task_doctor,
    "test": task_test,
    "verify": task_verify,
    "install": task_install,
    "freeze": task_freeze,
    "graph": task_graph,
    "budget": task_budget,
}


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print(__doc__.strip())
        print("\nTasks:")
        for name, fn in TASKS.items():
            summary = (fn.__doc__ or "").strip().splitlines()[0]
            print(f"  {name:9s} {summary}")
        print(f"\nTest lanes: {', '.join(LANES)}")
        return 0
    name, *rest = sys.argv[1:]
    if name not in TASKS:
        print(f"unknown task: {name}\navailable: {', '.join(TASKS)}")
        return 1
    return TASKS[name](rest)


if __name__ == "__main__":
    sys.exit(main())
