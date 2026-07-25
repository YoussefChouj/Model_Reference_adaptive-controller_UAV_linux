"""flashtool — safety-gated headless build + flash for the STM32F407 FC.

Unlike the read-only `livewatch` package, this tool WRITES the target (reflash =
halt/erase/program/reset). Every flash is preceded by a read-only safety gate that
refuses to proceed unless the running firmware reports DISARMED and no motor bench
test active — so a board with props on cannot be flashed while it could spin.

Build and flash both go through Keil `UV4.exe` (the same, proven flash path the user
runs by hand), not pyOCD flash algorithms, to avoid an unvalidated flash-algo/pack on
this custom board.
"""
from .safe_flash import SafetyGate, build, flash, verify_ekf

__all__ = ["SafetyGate", "build", "flash", "verify_ekf"]
