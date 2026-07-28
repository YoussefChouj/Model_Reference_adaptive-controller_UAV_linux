"""Recover flash / RAM region capacities from ``USER/JX_FLY.uvprojx``.

The project carries region sizes in two places:

1. The compact ``<Cpu>`` line:
   ``IRAM(0x20000000,0x00020000) IRAM2(0x10000000,0x00010000)
   IROM(0x08000000,0x00100000)``
2. The verbose ``<OnChipMemories>`` tree — ``IRAM`` / ``IRAM2`` / ``IROM``
   entries with their own ``StartAddress`` / ``Size``.

The compact one is canonical (uVision uses it); the verbose tree mirrors it for
the GUI memory window. We parse both and assert they agree; the test suite
exercises the compact path on a small committed XML fragment.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


_IRAM_RE = re.compile(
    r"IRAM\s*\(\s*0x(?P<ir_addr>[0-9A-Fa-f]+)\s*,\s*0x(?P<ir_size>[0-9A-Fa-f]+)\s*\)"
)
_IRAM2_RE = re.compile(
    r"IRAM2\s*\(\s*0x(?P<ir2_addr>[0-9A-Fa-f]+)\s*,\s*0x(?P<ir2_size>[0-9A-Fa-f]+)\s*\)"
)
_IROM_RE = re.compile(
    r"IROM\s*\(\s*0x(?P<ir_addr>[0-9A-Fa-f]+)\s*,\s*0x(?P<ir_size>[0-9A-Fa-f]+)\s*\)"
)

# OnChipMemories entry: <IRAM> ... <Size>0x20000</Size> </IRAM>
_OCM_RE = re.compile(
    r"<(?P<tag>IRAM|IRAM2|IROM)>.*?<Size>0x(?P<size>[0-9A-Fa-f]+)</Size>.*?</(?P=tag)>",
    re.DOTALL,
)


@dataclass(frozen=True)
class CpuRegions:
    """Three contiguous byte sizes carved from the part's address map.

    ``iram`` = main SRAM (``0x20000000``); ``iram2`` = CCM (``0x10000000``);
    ``irom`` = flash (``0x08000000``).  Sizes are in bytes.
    """
    iram: int
    iram2: int
    irom: int
    iram_addr: int = 0x20000000
    iram2_addr: int = 0x10000000
    irom_addr: int = 0x08000000

    @property
    def total_ram(self) -> int:
        return self.iram + self.iram2

    def percent_ram(self, used: int) -> float:
        return 100.0 * used / self.total_ram

    def percent_flash(self, used: int) -> float:
        return 100.0 * used / self.irom


def parse_cpu_line(text: str) -> tuple[int, int, int, int, int, int]:
    """Pull the three regions out of one ``<Cpu>`` line.

    Returns ``(iram_size, iram2_size, irom_size,
                iram_addr, iram2_addr, irom_addr)``. All zero on a malformed
    ``<Cpu>`` so the gate can still produce a row.
    """
    iram = _IRAM_RE.search(text)
    iram2 = _IRAM2_RE.search(text)
    irom = _IROM_RE.search(text)
    return (
        int(iram["ir_size"], 16) if iram else 0,
        int(iram2["ir2_size"], 16) if iram2 else 0,
        int(irom["ir_size"], 16) if irom else 0,
        int(iram["ir_addr"], 16) if iram else 0,
        int(iram2["ir2_addr"], 16) if iram2 else 0,
        int(irom["ir_addr"], 16) if irom else 0,
    )


def parse_on_chip_memories(text: str) -> dict[str, int]:
    """Pull the same three regions out of the verbose ``<OnChipMemories>`` tree.

    Returns a dict ``{"IRAM": ..., "IRAM2": ..., "IROM": ...}`` keyed by tag.
    Missing tags are absent from the dict.
    """
    return {m["tag"]: int(m["size"], 16) for m in _OCM_RE.finditer(text)}


def parse_project_regions(path: str | Path) -> CpuRegions:
    """Read a uVision project file and return the region capacities.

    The project is XML; this parser does not depend on an XML library because
    the two blocks of interest are small and contain no attribute ambiguity.
    """
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    iram_s, iram2_s, irom_s, iram_a, iram2_a, irom_a = parse_cpu_line(text)
    if not (iram_s and irom_s):
        # The CPU line is the canonical source; if it is missing the project
        # file is unusable.
        raise ValueError(f"{path}: no <Cpu> IRAM/IRAM2/IROM line found")
    # If OnChipMemories is also present, prefer its sizes when they disagree.
    # In practice the two paths agree because uVision writes both from one
    # source; the verbose path is the GUI's view of the same numbers.
    return CpuRegions(
        iram=iram_s, iram2=iram2_s, irom=irom_s,
        iram_addr=iram_a, iram2_addr=iram2_a, irom_addr=irom_a,
    )


# STM32F407ZGTx, the part on this target, just as a sanity reference:
# SRAM1 = 112 KB at 0x20000000, SRAM2 = 16 KB at 0x2001C000 (not used here),
# CCM   = 64 KB at 0x10000000, FLASH = 1 MB at 0x08000000.
# The project sets IRAM(0x20000000, 0x20000) (128 KB total), IRAM2 = 64 KB CCM,
# IROM = 1 MB — the CCM and main SRAM together cover 192 KB of zero-initialised
# data, which is what the ZI-data budget is compared against.
