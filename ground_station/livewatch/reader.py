"""Safe attach-mode live reader over the wireless CMSIS-DAP probe (pyOCD).

Safety contract (do not weaken):
  connect_mode="attach"        -> never halts or resets the running core
  target_override="cortex_m"   -> generic core access, no STM32 flash/reset logic
  resume_on_disconnect=False   -> nothing to resume; we never halted
  read paths only              -> no write_memory / halt / reset call exists here
Reading RAM cannot change the ARM flag, so a disarmed drone stays disarmed.

Performance: watched symbols are coalesced into the minimum number of contiguous
block reads (one CMSIS-DAP transaction each), because per-transaction USB latency
dominates, not bytes transferred. Watching a whole struct therefore costs ~1
transaction regardless of field count.

The coalescing (`build_plan`) and decoding (`Plan.decode`) are pure functions with
no hardware dependency, so they are unit-tested offline against synthetic bytes.
"""
from __future__ import annotations

import struct
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from .symbols import Symbol, SymbolResolver

# Merge two symbols into one block read only when the gap between them is smaller
# than the cost of a second transaction, expressed in bytes.
#
# Measured on the wireless CMSIS-DAP probe (2026-07-24): it is BANDWIDTH-limited,
# not latency-limited -- ~1.7 ms fixed per transaction PLUS only ~25-30 KB/s of
# transfer (a 4 B read = 1.72 ms; a 425 B read = 16.7 ms). So bridging an unused
# gap of G bytes costs ~G/28 ms, while a second transaction costs ~1.7 ms:
# merging wins only when  G/28 ms < 1.7 ms  ->  G < ~48 bytes. Hence 48.
#
# Contrast a *wired* CMSIS-DAP probe (latency-limited): there a much larger
# threshold would be optimal. Only affects efficiency, never correctness; retune
# per probe. Override via LiveReader(..., gap_merge_bytes=N) if you switch probes.
_GAP_MERGE_BYTES = 48


@dataclass
class Region:
    start: int
    size: int

    @property
    def end(self) -> int:
        return self.start + self.size


@dataclass
class Plan:
    """A resolved, coalesced read plan: which blocks to read, and how to slice them."""
    symbols: list[Symbol]
    regions: list[Region]

    def decode(self, region_bytes: list[bytes]) -> dict[str, object]:
        """Decode a full sample. `region_bytes[i]` is the raw read of `regions[i]`."""
        out: dict[str, object] = {}
        for sym in self.symbols:
            ri, off = self._locate(sym.address)
            raw = region_bytes[ri][off: off + sym.size]
            out[sym.name] = sym.decode(raw) if sym.is_scalar else raw
        return out

    def _locate(self, addr: int) -> tuple[int, int]:
        for i, r in enumerate(self.regions):
            if r.start <= addr < r.end:
                return i, addr - r.start
        raise KeyError(f"address 0x{addr:08X} not covered by plan")


def build_plan(resolver: SymbolResolver, names: list[str],
               gap_merge_bytes: int = _GAP_MERGE_BYTES) -> Plan:
    """Resolve names and coalesce their memory into minimal contiguous read regions."""
    syms = [resolver.resolve(n) for n in names]
    ordered = sorted(syms, key=lambda s: s.address)
    regions: list[Region] = []
    for s in ordered:
        if regions and s.address <= regions[-1].end + gap_merge_bytes:
            last = regions[-1]
            new_end = max(last.end, s.address + s.size)
            last.size = new_end - last.start
        else:
            regions.append(Region(s.address, s.size))
    return Plan(symbols=syms, regions=regions)


class LiveReader:
    """Opens a read-only attach session and samples a Plan on demand or as a stream."""

    def __init__(self, elf_path: str | Path, gap_merge_bytes: int = _GAP_MERGE_BYTES):
        self.resolver = SymbolResolver(elf_path)
        self.gap_merge_bytes = gap_merge_bytes
        self._session = None
        self._target = None

    # ---- connection (lazy; keeps offline tests hardware-free) ----------

    def connect(self):
        from pyocd.core.helpers import ConnectHelper
        self._session = ConnectHelper.session_with_chosen_probe(
            options={
                "target_override": "cortex_m",
                "connect_mode": "attach",       # non-halting
                "resume_on_disconnect": False,
            }
        )
        if self._session is None:
            raise RuntimeError("no CMSIS-DAP probe found (is Keil holding it? close its debug session)")
        self._session.open()
        self._target = self._session.target
        return self

    def close(self):
        if self._session is not None:
            self._session.close()
            self._session = self._target = None
        self.resolver.close()

    def __enter__(self):
        return self.connect()

    def __exit__(self, *exc):
        self.close()

    # ---- sampling ------------------------------------------------------

    def plan(self, names: list[str]) -> Plan:
        return build_plan(self.resolver, names, self.gap_merge_bytes)

    def sample(self, plan: Plan) -> dict[str, object]:
        if self._target is None:
            raise RuntimeError("not connected; call connect() or use as context manager")
        blocks = [bytes(self._target.read_memory_block8(r.start, r.size))
                  for r in plan.regions]
        return plan.decode(blocks)

    def stream(self, names: list[str], hz: float = 20.0,
               duration: float | None = None) -> Iterator[dict]:
        """Yield {'t': elapsed_s, <name>: value, ...} samples at ~hz until duration."""
        plan = self.plan(names)
        period = 1.0 / hz
        t0 = time.perf_counter()
        next_t = t0
        while True:
            now = time.perf_counter()
            row = {"t": now - t0}
            row.update({k: v for k, v in self.sample(plan).items()
                        if not isinstance(v, (bytes, bytearray))})
            yield row
            if duration is not None and (now - t0) >= duration:
                return
            next_t += period
            sleep = next_t - time.perf_counter()
            if sleep > 0:
                time.sleep(sleep)
            else:
                next_t = time.perf_counter()  # fell behind; resync, don't spiral
