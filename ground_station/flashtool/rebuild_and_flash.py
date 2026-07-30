"""Rebuild and flash the firmware, deterministically, with the drone powered on.

    python -m ground_station.flashtool.rebuild_and_flash              # build only
    python -m ground_station.flashtool.rebuild_and_flash --yes        # build + flash

This encodes the sequence validated on live hardware on 2026-07-29 so that a
future session does not have to rediscover it. Every step below exists because
something went wrong without it.

**The build no longer requires powering the drone down.** A headless build once
halted the flight controller -- LED dark, ESCs beeping, no self-recovery -- because
loading the uVision project initialises ``<pMon>BIN\\CMSIS_AGDI.dll`` and that
driver claims the probe over SWD. ``safe_flash._pMon_neutralised`` points ``<pMon>``
at the simulator DLL for the duration of the build and restores the file byte-exact,
so the CMSIS-DAP driver is never loaded. Verified with the target powered and
streaming telemetry throughout, before and after.

The remaining hazards this handles:

* **A rebuild relinks and RAM symbols move** (measured: ``DroneStatus.ARM_Status``
  0x20016776 -> 0x200169E6). Between building and flashing, the on-disk ELF
  describes an image the drone is not running. So the artifact triple is snapshotted
  first, the pre-flash safety read resolves names through the *snapshot*, and a
  failed flash restores it -- otherwise livewatch and every safety gate that
  resolves addresses would be reading the wrong ones.
* **Flashing over the wireless probe fails intermittently.** ``Erase Done.
  Programming Failed!RDDI-DAP Error`` leaves the part erased and the drone dark.
  That is an incomplete write, not a brick, and a plain retry has fixed it. So
  flashing retries rather than escalating a transient to the operator.
* **Flashing is not consented to by the drone being powered on.** ``--yes`` is
  required; without it this builds and stops.

Exit codes are per-stage so an unattended caller cannot mistake a failure for
success: 2 UV4 resident, 3 build failed, 4 uvoptx not restored, 5 target dark,
6 not disarmed / unreadable, 7 flash failed after retries, 8 dark after flash.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import time
from pathlib import Path

from . import safe_flash as sf
from .target_power import PortUnavailable, powered_from_sample, sample

SNAPSHOT = sf._OBJ / ".prev-flashed"
ARTIFACTS = ("JX_FLY.axf", "JX_FLY.hex", "JX_FLY.map")
DISARMED = 0


def _say(msg):
    print("[rebuild-flash] " + msg, flush=True)


# ---- steps ---------------------------------------------------------------

def uv4_resident() -> bool:
    """A GUI uVision instance holds OBJ/ handles and will break the build."""
    import subprocess
    try:
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq UV4.exe", "/FO", "LIST"],
            capture_output=True, text=True, timeout=30).stdout
    except Exception:
        return False
    return "UV4.exe" in out


def snapshot_artifacts() -> bool:
    """Copy the currently-flashed triple aside. Returns True if anything was saved."""
    SNAPSHOT.mkdir(parents=True, exist_ok=True)
    saved = 0
    for name in ARTIFACTS:
        src = sf._OBJ / name
        if src.exists():
            shutil.copy2(src, SNAPSHOT / name)
            saved += 1
    return saved > 0


def restore_artifacts() -> None:
    """Put the flashed triple back, so on-disk addresses match the running image."""
    for name in ARTIFACTS:
        src = SNAPSHOT / name
        if src.exists():
            shutil.copy2(src, sf._OBJ / name)


def build(rebuild: bool = True, timeout: float = 900):
    """UV4 compile+link with the debug driver neutralised. -> (ok, text)."""
    before = hashlib.sha256(sf._OPTS.read_bytes()).hexdigest()
    with sf._pMon_neutralised():
        rc, text = sf._run_uv4("-r" if rebuild else "-b", "rebuild.log", timeout)
    after = hashlib.sha256(sf._OPTS.read_bytes()).hexdigest()
    return rc, text, before == after


def target_alive(seconds: float = 1.5, port: str = "COM6") -> bool:
    return powered_from_sample(sample(port, seconds))


def arm_status(elf: Path):
    """Read ARM_Status through the given ELF, releasing SWD afterwards.

    Must be the SNAPSHOT ELF, not the freshly built one -- the drone is still
    running the old image and the symbol has moved.
    """
    from ..livewatch.reader import LiveReader
    reader = LiveReader(str(elf)).connect()
    try:
        return reader.sample(reader.plan(["DroneStatus.ARM_Status"]))[
            "DroneStatus.ARM_Status"]
    finally:
        reader.close()


def flash(attempts: int = 3, timeout: float = 600):
    """UV4 -f, retrying transient RDDI-DAP write failures. -> (ok, text)."""
    text = ""
    for i in range(1, attempts + 1):
        rc, text = sf._run_uv4("-f", "reflash%d.log" % i, timeout)
        if rc < 2 and "Failed" not in text:
            _say("flash succeeded on attempt %d" % i)
            return True, text
        _say("attempt %d failed (exit %d) -- the part may be erased; retrying" % (i, rc))
        time.sleep(2)
    return False, text


# ---- pipeline ------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--yes", action="store_true",
                    help="consent to flash; without it this builds and stops")
    ap.add_argument("--incremental", action="store_true", help="UV4 -b instead of -r")
    ap.add_argument("--port", default="COM6")
    ap.add_argument("--attempts", type=int, default=3)
    args = ap.parse_args(argv)

    if uv4_resident():
        _say("REFUSING: a uVision GUI instance is running and holds OBJ/ handles.")
        return 2

    had_snapshot = snapshot_artifacts()
    _say("snapshotted the flashed artifacts" if had_snapshot
         else "no existing artifacts to snapshot (first build?)")

    _say("building (<pMon> neutralised -- safe with the target powered)")
    rc, text, restored = build(rebuild=not args.incremental)
    for line in text.splitlines():
        if "Error(s)" in line or "Program Size" in line:
            _say("  " + line.strip())
    if not restored:
        _say("REFUSING: uvoptx was NOT restored byte-exact. Fix it before flashing.")
        return 4
    if rc >= 2:
        _say("build FAILED (UV4 exit %d)" % rc)
        if had_snapshot:
            restore_artifacts()
        return 3
    _say("build OK (UV4 exit %d: 0 clean, 1 warnings)" % rc)

    if not args.yes:
        _say("built but NOT flashed -- pass --yes to flash.")
        if had_snapshot:
            restore_artifacts()
            _say("restored the flashed artifacts so on-disk addresses still match "
                 "the running image (the new build is in OBJ/ only after --yes).")
        return 0

    try:
        if not target_alive(port=args.port):
            _say("REFUSING to flash: the target is dark.")
            return 5
    except PortUnavailable as exc:
        _say("REFUSING to flash: cannot read %s" % exc)
        return 5

    snap_elf = SNAPSHOT / "JX_FLY.axf"
    if had_snapshot and snap_elf.exists():
        try:
            status = arm_status(snap_elf)
        except Exception as exc:
            _say("REFUSING to flash: could not read ARM_Status (%s)" % exc)
            return 6
        if status != DISARMED:
            _say("REFUSING to flash: ARM_Status=%r, expected %d (DisArmed)"
                 % (status, DISARMED))
            return 6
        _say("ARM_Status=0 (DisArmed) -- props off; flashing resets the target")

    ok, _ = flash(attempts=args.attempts)
    if not ok:
        _say("flash FAILED after %d attempts. The part may be erased and the drone "
             "dark. Restoring the previous artifacts; reflash from the uVision GUI."
             % args.attempts)
        restore_artifacts()
        return 7

    time.sleep(3)
    if not target_alive(port=args.port):
        _say("flashed, but the target did NOT come back up.")
        return 8

    shutil.rmtree(SNAPSHOT, ignore_errors=True)
    _say("DONE: flashed, target alive, OBJ/JX_FLY.axf now matches the running image.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
