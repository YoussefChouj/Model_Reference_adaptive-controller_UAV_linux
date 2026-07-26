"""Prove the ELF matches the firmware actually running on the target.

Every livewatch read resolves a NAME to an ADDRESS out of OBJ/JX_FLY.axf. If that
ELF is not the build that is flashed, the addresses are wrong and the tool returns
plausible-looking garbage rather than an error -- a float is a float whatever it
points at. That is the one way a strictly read-only tool can still mislead you, and
it is not hypothetical: the 2026-07-26 rebuild shifted .bss by 12 bytes and silently
invalidated two pinned test goldens.

So: compare bytes of the ELF's loadable flash segments against the same addresses
read back from the target. Any relink moves code, so a handful of sampled chunks is
enough to catch a stale ELF. This operation intentionally remains SWD-only because
the UART5 observation protocol cannot read internal flash. Reads flash only -- no
write, no halt, no reset.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from elftools.elf.elffile import ELFFile

# STM32F407 internal flash. Segments outside this (RAM-loaded .data copies, etc.)
# have no stable on-target image to compare against, so they are skipped.
FLASH_BASE = 0x08000000
FLASH_END = 0x08100000


@dataclass(frozen=True)
class Sample:
    address: int
    expected: bytes


def flash_segments(elf_path: str | Path) -> list[tuple[int, bytes]]:
    """(paddr, contents) for each loadable segment resident in internal flash."""
    out: list[tuple[int, bytes]] = []
    with open(elf_path, "rb") as f:
        for seg in ELFFile(f).iter_segments():
            h = seg.header
            if h.p_type != "PT_LOAD" or h.p_filesz == 0:
                continue
            if not (FLASH_BASE <= h.p_paddr < FLASH_END):
                continue
            out.append((int(h.p_paddr), seg.data()[: h.p_filesz]))
    return out


def plan_samples(segments: list[tuple[int, bytes]], n: int = 5,
                 chunk: int = 64) -> list[Sample]:
    """Pick `n` evenly spread chunks across the flash image.

    Even spread rather than random: it is deterministic (two runs compare the same
    bytes, so a mismatch is reproducible) and it always includes the first and last
    chunk, which is where a relink shows up most reliably. Spread also beats
    sampling one contiguous block -- a stale ELF can share a prefix with the flashed
    image and diverge only later.
    """
    samples: list[Sample] = []
    for base, data in segments:
        if not data:
            continue
        usable = max(len(data) - chunk, 0)
        count = min(n, max(1, usable // chunk + 1))
        for i in range(count):
            off = 0 if count == 1 else (usable * i) // (count - 1)
            samples.append(Sample(base + off, bytes(data[off: off + chunk])))
    return samples


@dataclass
class VerifyResult:
    checked: int
    mismatched: int
    first_bad: int | None      # address of the first differing chunk
    bytes_compared: int

    @property
    def ok(self) -> bool:
        return self.checked > 0 and self.mismatched == 0

    def describe(self) -> str:
        if self.checked == 0:
            return "no loadable flash segments found in the ELF - cannot verify"
        if self.ok:
            return (f"ELF matches target: {self.checked} chunk(s), "
                    f"{self.bytes_compared} B compared, 0 mismatches")
        return (f"STALE ELF: {self.mismatched}/{self.checked} chunk(s) differ "
                f"(first at 0x{self.first_bad:08X}). Symbol addresses are NOT "
                f"trustworthy - rebuild or reflash before reading anything.")


def compare(samples: list[Sample], read_block) -> VerifyResult:
    """Compare planned samples against the target. `read_block(addr, size) -> bytes`."""
    bad = 0
    first_bad = None
    total = 0
    for s in samples:
        actual = bytes(read_block(s.address, len(s.expected)))
        total += len(s.expected)
        if actual != s.expected:
            bad += 1
            if first_bad is None:
                first_bad = s.address
    return VerifyResult(checked=len(samples), mismatched=bad,
                        first_bad=first_bad, bytes_compared=total)
