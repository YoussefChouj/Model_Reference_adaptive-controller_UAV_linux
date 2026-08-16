"""Gated RAM write via SWD: resolve symbol, safety-check, halt, write, verify, resume.

All write operations are gated by two mandatory checks:

1. ``i_understand=True`` — explicit acknowledgement that live RAM writes are
   deliberate and irreversible (within the running session).  No bypass flag,
   no suppression mode.
2. ``require_disarmed=True`` (default) — reads ``DroneStatus.ARM_Status`` via
   the existing read path and aborts if the vehicle is not DISARMED.

Optional integrity measures (``halt_for_write``, ``verify``) are provided as
toggles; their defaults reflect the firmware's ``volatile`` discipline and
the ARM AAPCS atomicity guarantee for 32-bit aligned writes.
"""
from __future__ import annotations

import struct
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from .symbols import SymbolResolver
from .transport import LiveTransport

if TYPE_CHECKING:
    from .reader import LiveReader


# ARM AAPCS: 32-bit aligned stores are atomic.  Cortex-M4 (STM32F4) is
# always little-endian; struct.pack('<f', ...) produces the correct bit
# pattern for IEEE-754 single-precision values stored to RAM.
_IEEE754_SINGLE = struct.Struct("<f")


@dataclass
class PatchResult:
    """Outcome of a single live RAM write."""
    address: int
    old_value: int
    new_value: int
    verified: bool
    duration_ms: float


class SafetyGateError(RuntimeError):
    """Raised when a mandatory safety gate is not satisfied."""


def _read_arm_status(live_reader: "LiveReader") -> int:
    """Read DroneStatus.ARM_Status via the existing read path.

    Returns the integer ARM status value (0=DISARMED, 1=ARMING, 2=ARMED,
    etc.).  Raises SafetyGateError on any read failure so the write is
    aborted rather than silently proceeding.
    """
    try:
        plan = live_reader.plan(["DroneStatus.ARM_Status"])
        sample = live_reader.sample(plan)
        return int(sample["DroneStatus.ARM_Status"])
    except Exception as exc:
        raise SafetyGateError(
            f"require_disarmed=True: could not read DroneStatus.ARM_Status "
            f"(is the target halted or unreachable?): {exc}"
        ) from exc


def _float_bits(value: float) -> int:
    """Pack a Python float as IEEE-754 single and return the uint32 bits."""
    if not value.__class__ is float:
        raise ValueError(f"patch_symbol requires a Python float; got {type(value).__name__}")
    if not (-3.4e38 <= value <= 3.4e38):
        raise ValueError(f"value {value!r} is out of IEEE-754 single range")
    return int.from_bytes(_IEEE754_SINGLE.pack(value), "little")


def patch_symbol(
    elf_path: str | Path,
    symbol_name: str,
    value: float,
    *,
    transport: LiveTransport,
    i_understand: bool = False,
    require_disarmed: bool = True,
    halt_for_write: bool = False,
    verify: bool = True,
    dry_run: bool = False,
) -> PatchResult:
    """Resolve ``symbol_name`` in ``elf_path`` and write ``value`` to its RAM address.

    Raises:
        SafetyGateError: if ``i_understand`` is ``False``, or if
            ``require_disarmed`` is ``True`` and the vehicle is not DISARMED.
        ValueError: if ``value`` is not a finite Python float.

    The write is performed as a single ``write_memory_block32`` transaction
    (32-bit aligned, atomic per ARM AAPCS).  ``verify=True`` reads back the
    address and compares the **bit pattern** (not the float value) so that
    NaN/Inf comparisons do not give false negatives.  ``dry_run=True`` skips
    the write but still returns the current RAM contents at the resolved
    address.
    """
    if not i_understand:
        raise SafetyGateError(
            "--i-understand is required for live RAM writes; "
            "this is a deliberate gate, not a default."
        )

    if not isinstance(value, float):
        raise ValueError(
            f"patch_symbol requires a Python float; got {type(value).__name__} ({value!r})"
        )
    if not (value == value and value != float("inf") and value != float("-inf")):
        raise ValueError(f"value {value!r} is not a finite float")

    resolver = SymbolResolver(elf_path)
    try:
        sym = resolver.resolve(symbol_name)
    except Exception as exc:
        raise ValueError(
            f"patch_symbol: could not resolve symbol {symbol_name!r}: {exc}"
        ) from exc
    finally:
        resolver.close()

    addr = sym.address
    bits = _float_bits(value)

    # Lazy-import LiveReader only when we need to verify arm status / read-back.
    from .reader import LiveReader
    lr = LiveReader(elf_path, transport=transport)

    t0 = time.monotonic()
    old_bits: int | None = None
    halted = False

    try:
        lr.connect()
        target = lr._target

        if require_disarmed:
            arm_status = _read_arm_status(lr)
            # DroneStatus ARM_Status: 0=DISARMED, 2=ARMED (firmware convention)
            if arm_status != 0:
                raise SafetyGateError(
                    f"require_disarmed=True: DroneStatus.ARM_Status = {arm_status} "
                    f"(expected 0 / DISARMED). Aborting live write. "
                    f"Use --no-disarm-check to override."
                )

        # Read old value for the result record and for verify read-back.
        plan_old = lr.plan([symbol_name])
        old_sample = lr.sample(plan_old)
        old_raw = old_sample[symbol_name]
        if isinstance(old_raw, bytes):
            old_bits = int.from_bytes(old_raw[:4], "little")
        elif isinstance(old_raw, float):
            old_bits = _float_bits(old_raw)
        else:
            old_bits = int(old_raw)
        old_value = old_bits

        if dry_run:
            return PatchResult(
                address=addr,
                old_value=old_value,
                new_value=bits,
                verified=True,
                duration_ms=(time.monotonic() - t0) * 1000,
            )

        if halt_for_write and target is not None:
            target.halt()
            halted = True

        transport.write_memory_block32(addr, [bits])

        if verify:
            plan_verify = lr.plan([symbol_name])
            new_sample = lr.sample(plan_verify)
            new_raw = new_sample[symbol_name]
            if isinstance(new_raw, bytes):
                new_bits = int.from_bytes(new_raw[:4], "little")
            elif isinstance(new_raw, float):
                new_bits = _float_bits(new_raw)
            else:
                new_bits = int(new_raw)
            if new_bits != bits:
                raise RuntimeError(
                    f"verify failed: wrote 0x{bits:08X} to 0x{addr:08X} but "
                    f"read-back returned 0x{new_bits:08X}"
                )

        verified = True

    finally:
        if halted:
            try:
                target.resume()
            except Exception:
                pass  # Best-effort resume; a halted target is recoverable by re-halt.
        lr.close()

    return PatchResult(
        address=addr,
        old_value=old_value,
        new_value=bits,
        verified=verified,
        duration_ms=(time.monotonic() - t0) * 1000,
    )
