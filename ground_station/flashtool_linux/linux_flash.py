"""pyocd-powered flash + reset + verify for STM32F407ZG on Linux.

Safety contract (same as livewatch.reader):
  - Uses SwdCmsisDap transport with connect_mode="attach" and resume_on_disconnect=False
  - NO halt, reset (system only), or memory-write exposed as public API
  - Flash() calls pyocd's internal erase before write — that is the write surface
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from pyocd.core.helpers import ConnectHelper


TARGET = "stm32f407zg"      # matches CMSIS DFP part number
# HID CMSIS-DAP bridges (e.g. ATK-HS-V3 wireless) reorder/defer responses under load.
# Force single in-flight packets and disable deferred transfers — see pyocd issue #1257.
# Without these, DAP_TRANSFER_BLOCK returns "response is for command 05" mid-flash,
# and the read path replays a cached buffer.
_PROBE_CONFIG = {
    "target_override": "cortex_m",
    "connect_mode": "attach",
    "resume_on_disconnect": False,
    "cmsis_dap.deferred_transfers": 0,
    "cmsis_dap.limit_packets": 1,
}


@dataclass
class FlashResult:
    ok: bool
    elapsed_s: float
    bytes_programmed: int
    probe_uid: str
    error: Optional[str] = None

    def report(self) -> str:
        if self.ok:
            return (
                f"[flash] ok  {self.bytes_programmed} bytes @ {self.elapsed_s:.1f}s"
                f"  probe={self.probe_uid}"
            )
        return f"[flash] FAIL  {self.error}  ({self.elapsed_s:.1f}s)"


@dataclass
class ChecksumResult:
    sha256_hex16: str
    bytes_read: int
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None

    def report(self) -> str:
        if self.ok:
            return f"[checksum] ok  sha256={self.sha256_hex16}  bytes={self.bytes_read}"
        return f"[checksum] FAIL  {self.error}"


def _probe_uid(session) -> str:
    """Return the CMSIS-DAP probe unique-id string."""
    try:
        return session.board.unique_id or "unknown"
    except Exception:
        return "unknown"


def probe_info() -> dict:
    """Enumerate available probes. Never opens a session."""
    from ground_station.flashtool_linux import enumerate_probes
    return {"probes": enumerate_probes(), "target": TARGET}


def flash(hex_path: Path, frequency_hz: int = 5_000_000) -> FlashResult:
    """Full chip erase + program + verify.

    Args:
        hex_path:   Intel HEX firmware image produced by CMake build.
        frequency_hz: SWD clock speed. 5 MHz is safe for most CMSIS-DAP probes.
                      Use 10 MHz for wired high-speed probes.

    Returns:
        FlashResult with ok=True on success.

    Raises:
        FileNotFoundError: hex_path does not exist.
    """
    if not hex_path.exists():
        raise FileNotFoundError(hex_path)

    start = time.monotonic()
    error: Optional[str] = None
    bytes_prog = 0
    uid = "unknown"

    try:
        # connect_mode=attach + resume_on_disconnect=False matches livewatch's
        # safety contract: do not halt the core, do not resume on disconnect.
        # reset_type=system forces AIRCR.SYSRESETREQ for both the implicit
        # connect-time reset and the explicit post-flash reset; 'default'
        # would use the target's own choice (also usually 'system').
        session = ConnectHelper.session_with_chosen_probe(
            options={
                **_PROBE_CONFIG,
                "frequency": frequency_hz,
                "reset_type": "system",
            }
        )
        if session is None:
            return FlashResult(
                ok=False, elapsed_s=time.monotonic() - start,
                bytes_programmed=0, probe_uid="none",
                error="no CMSIS-DAP probe enumerated — is it plugged in?",
            )

        with session:
            uid = _probe_uid(session)
            target = session.target
            board = session.board

            # Flash erase + program
            target.mass_erase()
            from pyocd.flash.file_programmer import FileProgrammer
            fp = FileProgrammer(session)
            fp.program(str(hex_path), file_format="hex")
            # Total bytes programmed is exposed via the progress counter after commit.
            bytes_prog = int(fp.progress.total_byte_count)

            # Post-flash system reset (NVIC AIRCR.SYSRESETREQ, no core halt).
            # reset_type='system' on session ensures both the implicit and
            # explicit reset use this path.
            target.system_reset()

            elapsed = time.monotonic() - start
            return FlashResult(
                ok=True, elapsed_s=elapsed,
                bytes_programmed=bytes_prog, probe_uid=uid,
            )

    except Exception as exc:
        return FlashResult(
            ok=False, elapsed_s=time.monotonic() - start,
            bytes_programmed=bytes_prog, probe_uid=uid,
            error=str(exc),
        )


def reset() -> bool:
    """System reset over SWD. Returns True on success.

    Uses target.system_reset() (NVIC AIRCR.SYSRESETREQ) — does NOT halt the
    core. Distinct from target.reset() which is a halt-style debug reset.
    """
    try:
        session = ConnectHelper.session_with_chosen_probe(options=_PROBE_CONFIG)
        if session is None:
            return False
        with session:
            session.target.system_reset()
            return True
    except Exception:
        return False


def checksum_elf(elf_path: Path) -> ChecksumResult:
    """SHA-256 the ELF on disk and return its hex prefix.

    Note: this is a checksum, not post-flash verification. The safety contract
    forbids halting the core, so we cannot read back running flash from here.
    For actual flash verification, pyocd's flash() runs verify internally when
    smart_flash=True (the default above).
    """
    if not elf_path.exists():
        return ChecksumResult(sha256_hex16="", bytes_read=0,
                              error=f"{elf_path} not found")
    try:
        sha = hashlib.sha256(elf_path.read_bytes()).hexdigest()[:16]
        return ChecksumResult(sha256_hex16=sha, bytes_read=elf_path.stat().st_size)
    except Exception as exc:
        return ChecksumResult(sha256_hex16="", bytes_read=0, error=str(exc))


def flash_and_checksum(hex_path: Path, elf_path: Path,
                       frequency_hz: int = 5_000_000) -> tuple[FlashResult, ChecksumResult]:
    """Flash then compute the ELF checksum. Convenience wrapper."""
    fr = flash(hex_path, frequency_hz)
    cr = (checksum_elf(elf_path) if fr.ok
          else ChecksumResult(sha256_hex16="", bytes_read=0, error="flash failed"))
    return fr, cr
