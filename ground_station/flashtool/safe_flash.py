"""Safety-gated headless build + flash pipeline.

  python -m ground_station.flashtool gate     # read-only: is it safe to flash?
  python -m ground_station.flashtool build    # UV4 -b (no hardware)
  python -m ground_station.flashtool flash     # gate -> UV4 -f -> verify   (asks to confirm)
  python -m ground_station.flashtool all       # build -> gate -> flash -> verify

The gate reads the RUNNING firmware over the probe (read-only, via livewatch) and
refuses unless ARM_Status==DisArmed and no motor bench test is active. Reflash halts
and resets the core; motors are unpowered during it and boot disarmed. Over the
WIRELESS probe a dropped link mid-write can corrupt flash, so `flash`/`all` require an
explicit confirmation (--yes to bypass in trusted automation) and UV4 verifies after.
"""
from __future__ import annotations

import argparse
import contextlib
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_UV4 = Path(r"C:\Keil_v5\UV4\UV4.exe")
_PROJECT = _ROOT / "USER" / "JX_FLY.uvprojx"
_ELF = _ROOT / "OBJ" / "JX_FLY.axf"

DISARMED = 0


# ---- safety gate (read-only) -------------------------------------------

@dataclass
class GateResult:
    ok: bool
    values: dict
    reasons: list[str]

    def report(self) -> str:
        head = "SAFE to flash" if self.ok else "BLOCKED — refusing to flash"
        lines = [f"[safety gate] {head}"]
        for k, v in self.values.items():
            lines.append(f"    {k:24s} {v}")
        for r in self.reasons:
            lines.append(f"    ! {r}")
        return "\n".join(lines)


class SafetyGate:
    """Reads the running target and decides whether a flash may proceed."""

    VARS = ["DroneStatus.ARM_Status", "motor_test_active", "motor_test_id"]

    def __init__(self, elf: str | Path = _ELF):
        self.elf = Path(elf)

    def check(self) -> GateResult:
        from ground_station.livewatch.reader import LiveReader
        with LiveReader(self.elf) as lr:
            vals = lr.sample(lr.plan(self.VARS))
        reasons = []
        if vals["DroneStatus.ARM_Status"] != DISARMED:
            reasons.append(f"ARM_Status={vals['DroneStatus.ARM_Status']} (expected DisArmed=0)")
        if vals["motor_test_active"] != 0:
            reasons.append(f"motor_test_active={vals['motor_test_active']} (a motor bench test is running)")
        return GateResult(ok=not reasons, values=vals, reasons=reasons)


# ---- build / flash via UV4 ---------------------------------------------

def _kill_resident_uv4() -> None:
    """Kill any running uVision instance before a CLI build/flash.

    A resident UV4 GUI with this project open holds handles on OBJ/*.o and the
    browse .crf files. The command-line build then can't write those outputs and
    every file fails with "couldn't write file ...: Invalid argument". UV4 must be
    the sole process touching OBJ/, so we terminate it first (harmless — the GUI
    holds no unsaved firmware state; sources are saved by the editor on build).
    """
    subprocess.run(["taskkill", "/F", "/IM", "UV4.exe"],
                   capture_output=True, check=False)


def _run_uv4(flag: str, log_name: str, timeout: float) -> tuple[int, str]:
    if not _UV4.exists():
        raise FileNotFoundError(f"UV4 not found at {_UV4}")
    _kill_resident_uv4()
    # Write the build log OUTSIDE the project tree. The project path contains a
    # space ("...Six_Degrees_of_Freedom _Adaptive_controller"); UV4's arg parser
    # splits the -o value on that space even when quoted and mangles the path
    # ("...\\_Adaptive_controller\\_Adaptive_controller\\..."), so an -o inside the
    # project fails ("incorrect path") and pops the GUI. C:\\tmp has no space.
    # Do NOT pass -j0: parallel armcc jobs race on the .crf files. Exit: 0 ok,
    # 1 warnings, >=2 errors.
    log = Path(r"C:\tmp") / log_name
    log.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run([str(_UV4), flag, str(_PROJECT), "-o", str(log)],
                          timeout=timeout)
    text = log.read_text(errors="replace") if log.exists() else ""
    return proc.returncode, text


@contextlib.contextmanager
def _browse_info_disabled():
    """Temporarily set <BrowseInformation> to 0 in the project, then restore.

    Headless armcc fails to (re)open the per-file browse .crf files ("cannot open
    source input file ...crf: Invalid argument") for a subset of sources, aborting
    the build. Browse info is a uVision GUI-only convenience (go-to-definition),
    irrelevant to producing the firmware image, so we disable it just for the
    command-line build and restore the user's setting afterward (GUI keeps it on).
    """
    # Operate on raw bytes: text mode would rewrite the project's CRLF line endings
    # to LF and re-encode it, needlessly churning the file the user edits in the GUI.
    original = _PROJECT.read_bytes()
    on, off = b"<BrowseInformation>1</BrowseInformation>", b"<BrowseInformation>0</BrowseInformation>"
    if on not in original:
        yield  # already off / unexpected format; nothing to do
        return
    try:
        _PROJECT.write_bytes(original.replace(on, off, 1))
        yield
    finally:
        _PROJECT.write_bytes(original)


# Files armcc failed to write this pass, so we can delete + rebuild only those.
# Two shapes: object write ("couldn't write file '..\obj\x.o'") and browse-info
# read/append ("cannot open source input file "..\obj\x.crf"").
_FAILED_OUT = re.compile(
    r"""couldn't\ write\ file\ '\.\.[\\/]obj[\\/]([^']+)'"""
    r"""|cannot\ open\ source\ input\ file\ "\.\.[\\/]obj[\\/]([^"]+)\"""",
    re.IGNORECASE | re.VERBOSE)


def _delete_failed_outputs(text: str) -> int:
    """Delete the OBJ artifacts armcc couldn't write, forcing their recompile."""
    n = 0
    for m in _FAILED_OUT.finditer(text):
        name = m.group(1) or m.group(2)
        f = _ROOT / "OBJ" / name
        try:
            f.unlink()
            n += 1
        except OSError:
            pass
    return n


def build(rebuild: bool = False, timeout: float = 600, max_passes: int = 20,
          verbose: bool = True) -> tuple[bool, str]:
    """Headless compile+link, robust to real-time scanner races on OBJ/.

    Defender's real-time scan intermittently grabs freshly-written OBJ artifacts,
    so armcc/armlink fail a shifting subset with "Invalid argument" — and the final
    link (JX_FLY.axf, a fresh executable image RT protection scans hardest) fails
    on nearly every attempt. We disable browse info (removes the .crf failure mode)
    and retry `-b`: each pass deletes the .o files that failed (missing ones just
    recompile) and, if the link couldn't open JX_FLY.axf, deletes the stale image
    so the next link creates it fresh, with a short settle delay for the scanner to
    release the previous output. Written outputs persist, so the set shrinks and the
    build converges. Returns (ok, summary). No hardware needed.
    """
    import time
    axf = _ROOT / "OBJ" / "JX_FLY.axf"
    with _browse_info_disabled():
        last = ""
        for i in range(1, max_passes + 1):
            flag = "-r" if (rebuild and i == 1) else "-b"
            rc, text = _run_uv4(flag, "flash_build.log", timeout)
            last = text
            raced = "Invalid argument" in text
            n_obj = len(_FAILED_OUT.findall(text))
            link_failed = "JX_FLY.axf" in text and "Invalid argument" in text
            if verbose:
                print(f"    pass {i:2d}: exit={rc} obj_write_fails={n_obj} "
                      f"link_fail={link_failed}")
            if rc < 2 and not raced:
                return True, f"(pass {i}, UV4 exit {rc}) build OK — target created"
            if not raced:
                break  # a genuine compile/link error, not a scanner race — stop
            _delete_failed_outputs(text)
            if link_failed:
                try:
                    axf.unlink(missing_ok=True)  # force a fresh image next link
                except OSError:
                    pass  # scanner still holds it; next link retries anyway
            time.sleep(1.5)  # let the scanner release the outputs it grabbed
    tail = "\n".join(last.splitlines()[-12:])
    return False, f"(gave up after pass {i}, still racing)\n{tail}"


def flash(timeout: float = 300) -> tuple[bool, str]:
    """Download the built image via UV4 -f (halts/erases/programs/resets/verifies)."""
    rc, text = _run_uv4("-f", "flash_download.log", timeout)
    ok = rc < 2
    tail = "\n".join(text.splitlines()[-12:])
    return ok, f"(UV4 exit {rc})\n{tail}"


# ---- post-flash verification (read-only) -------------------------------

def verify_ekf(elf: str | Path = _ELF) -> str:
    from ground_station.livewatch.reader import LiveReader
    names = ["s_ekf.active", "s_ekf.x[0]", "s_ekf.x[3]", "s_ekf.nis"]
    with LiveReader(elf) as lr:
        row = lr.sample(lr.plan(names))
    active = row["s_ekf.active"]
    verdict = "EKF RUNNING" if active == 1 else f"EKF still gated (active={active})"
    return (f"[verify] {verdict}\n"
            f"    s_ekf.active {active}\n"
            f"    v_body.x     {row['s_ekf.x[0]']:+.5g} m/s\n"
            f"    b_a.x        {row['s_ekf.x[3]']*1000:+.3f} mg\n"
            f"    nis          {row['s_ekf.nis']:+.4g}")


# ---- CLI ---------------------------------------------------------------

def _confirm(auto_yes: bool) -> bool:
    if auto_yes:
        return True
    try:
        return input("Proceed to FLASH the running target? [type 'flash' to confirm] ").strip() == "flash"
    except EOFError:
        return False


def main(argv=None):
    p = argparse.ArgumentParser(prog="flashtool", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("cmd", choices=["gate", "build", "flash", "verify", "all"])
    p.add_argument("--rebuild", action="store_true", help="full rebuild (UV4 -r) instead of incremental")
    p.add_argument("--yes", action="store_true", help="skip the interactive flash confirmation")
    args = p.parse_args(argv)

    if args.cmd == "gate":
        print(SafetyGate().check().report())
        return

    if args.cmd == "verify":
        # Read-only, motors-safe. Use after a manual uVision build+flash to confirm
        # the EKF is live on the running target. (Headless `build` is unreliable on
        # this machine — UV4 -b hits Invalid-argument write races — so building in
        # the uVision GUI and verifying here is the supported path.)
        print(verify_ekf())
        return

    if args.cmd in ("build", "all"):
        ok, log = build(rebuild=args.rebuild)
        print(f"[build] {'OK' if ok else 'FAILED'} {log}")
        if not ok:
            sys.exit(1)
        if args.cmd == "build":
            return

    # flash / all: gate -> confirm -> flash -> verify
    gate = SafetyGate().check()
    print(gate.report())
    if not gate.ok:
        sys.exit(2)
    if not _confirm(args.yes):
        print("[flash] aborted (not confirmed)")
        sys.exit(3)
    ok, log = flash()
    print(f"[flash] {'OK' if ok else 'FAILED'} {log}")
    if not ok:
        sys.exit(1)
    print(verify_ekf())


if __name__ == "__main__":
    main()
