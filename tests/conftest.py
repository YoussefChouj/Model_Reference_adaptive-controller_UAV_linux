"""Shared fixtures for livewatch patch tests.

Provides minimal synthetic transport doubles that record calls and
allow tests to control read/write/behaviour without hardware.
"""
from __future__ import annotations

import struct
from typing import Any
from unittest.mock import MagicMock


_IEEE754 = struct.Struct("<f")


class SyntheticTransport:
    """Record-and-replay transport double for patch testing.

    Records write_memory_block32 calls and returns user-supplied bytes for
    read_memory_block8.  A real LiveReader / Plan is used so the decode
    path is exercised.
    """

    def __init__(self):
        self.writes: list[tuple[int, list[int]]] = []
        self.halt_called: bool = False
        self.resume_called: bool = False
        self._read_values: dict[int, bytes] = {}
        self._target_halt: bool = True

    def write_memory_block32(self, address: int, values: list[int]) -> None:
        self.writes.append((address, list(values)))

    def write16(self, address: int, value: int) -> None:
        self.writes.append((address, [value]))

    def write8(self, address: int, value: int) -> None:
        self.writes.append((address, [value]))

    def halt(self) -> None:
        self.halt_called = True

    def resume(self) -> None:
        self.resume_called = True

    @property
    def target(self) -> SyntheticTransport:
        return self

    @property
    def name(self) -> str:
        return "synthetic"

    @property
    def gap_merge_bytes(self) -> int:
        return 48

    def sample(self, plan) -> list[bytes]:
        out = []
        for r in plan.regions:
            buf = bytearray(r.size)
            for sym in plan.symbols:
                if r.start <= sym.address < r.end:
                    off = sym.address - r.start
                    raw = self._read_values.get(sym.address)
                    if raw is not None:
                        buf[off:off + min(len(raw), r.end - sym.address)] = raw[:r.end - sym.address]
            out.append(bytes(buf))
        return out

    def connect(self) -> "SyntheticTransport":
        return self

    def close(self) -> None:
        pass

    def set_read_value(self, address: int, value: float | int | bytes) -> None:
        if isinstance(value, float):
            self._read_values[address] = _IEEE754.pack(value)
        elif isinstance(value, int):
            self._read_values[address] = value.to_bytes(4, "little")
        else:
            self._read_values[address] = bytes(value)

    def clear_writes(self) -> None:
        self.writes.clear()
