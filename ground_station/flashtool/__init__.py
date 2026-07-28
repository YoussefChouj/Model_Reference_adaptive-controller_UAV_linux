"""flashtool — safety-gated headless build + flash for the STM32F407 FC.

Unlike the read-only ``livewatch`` package, this tool WRITES the target (reflash =
halt/erase/program/reset). Every flash is preceded by a read-only safety gate that
refuses to proceed unless the running firmware reports DISARMED and no motor bench
test active — so a board with props on cannot be flashed while it could spin.

Build and flash both go through Keil ``UV4.exe`` (the same, proven flash path the user
runs by hand), not pyOCD flash algorithms, to avoid an unvalidated flash-algo/pack on
this custom board.

The package exposes three small standalone modules so they can be unit-tested
without invoking UV4:

* ``build_id`` — compute the build identity (SHA-256 of flash segments) and
  emit the C source that stamps it into the firmware image.
* ``preflight`` — UV4.exe + CMSIS-DAP-holder interlocks that gate every probe
  operation.
* ``artifact_custody`` — snapshot / restore the flashed-matching triple so an
  abandoned build cannot leave livewatch reading stale DWARF.
"""
from .safe_flash import SafetyGate, build, flash, verify_ekf
from . import artifact_custody, build_id, preflight

__all__ = [
    "SafetyGate", "build", "flash", "verify_ekf",
    "artifact_custody", "build_id", "preflight",
]