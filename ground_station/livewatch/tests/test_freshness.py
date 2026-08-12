"""Offline tests for the livewatch freshness probe.

The freshness subcommand is a small wrapper around LiveReader.sample(); the
hardware-dependent part is the symbol read. We test the *decision* logic with
a synthetic transport that returns a sequence of values.
"""
from __future__ import annotations

import io
import sys
import time
from pathlib import Path
from typing import Iterator

import pytest


def _make_args(field: str = "tick", delay_ms: float = 1.0,
               samples: int = 3, require_monotonic: bool = False):
    """Build an argparse.Namespace compatible with cmd_freshness()."""
    import argparse
    return argparse.Namespace(
        elf=str(Path(__file__)),     # not used; transport is mocked
        field=field, delay_ms=delay_ms,
        samples=samples, require_monotonic=require_monotonic,
        transport="swd",             # ignored; we replace _transport
    )


def _patch_transport_with_sequence(monkeypatch, sequence: list[bytes]) -> None:
    """Replace _transport() and SymbolResolver so cmd_freshness runs offline.

    cmd_freshness() instantiates LiveReader(args.elf, transport=_transport(args))
    directly. We patch SymbolResolver to return a no-op stub so the ELF argument
    is never actually opened.
    """
    from ground_station.livewatch import cli
    from ground_station.livewatch import symbols as sym_mod
    from ground_station.livewatch import reader as rd_mod

    class FakeTransport:
        name = "fake"
        gap_merge_bytes = 48
        cost_model = None

        def __init__(self, seq):
            self.seq = list(seq)
            self.idx = 0

        def connect(self):
            pass

        def close(self):
            pass

        def sample(self, plan):
            # cmd_freshness reads once per loop iteration; advance on each call
            if self.idx < len(self.seq):
                out = self.seq[self.idx]
                self.idx += 1
            else:
                out = self.seq[-1]
            return [out]

    class _NoopResolver:
        def __init__(self, elf):
            pass

        def resolve(self, name):
            return sym_mod.Symbol(name=name, address=0, size=4, fmt="I")
        def close(self):
            pass

    monkeypatch.setattr(cli, "_transport", lambda args: FakeTransport(sequence))
    # reader.py does `from .symbols import SymbolResolver`, so patch its binding too.
    monkeypatch.setattr(sym_mod, "SymbolResolver", _NoopResolver)
    monkeypatch.setattr(rd_mod, "SymbolResolver", _NoopResolver)


def test_freshness_advancing_values_succeeds(monkeypatch, capsys):
    """When values change between samples, exit 0 and report FRESH."""
    from ground_station.livewatch import cli

    _patch_transport_with_sequence(monkeypatch, [
        (1).to_bytes(4, "little"),
        (2).to_bytes(4, "little"),
        (3).to_bytes(4, "little"),
    ])

    rc = cli.cmd_freshness(_make_args(samples=3))
    out = capsys.readouterr().out
    assert rc == 0
    assert "FRESH" in out
    assert "STALE" not in out


def test_freshness_constant_values_fails(monkeypatch, capsys):
    """When every read returns the same value, exit 3 (stale) and report STALE."""
    from ground_station.livewatch import cli

    _patch_transport_with_sequence(monkeypatch, [
        (42).to_bytes(4, "little"),
        (42).to_bytes(4, "little"),
        (42).to_bytes(4, "little"),
    ])

    rc = cli.cmd_freshness(_make_args(samples=3))
    out = capsys.readouterr().out
    assert rc == 3
    assert "STALE" in out


def test_freshness_require_monotonic_catches_reorder(monkeypatch, capsys):
    """With --require-monotonic, a non-monotonic sequence fails."""
    from ground_station.livewatch import cli

    _patch_transport_with_sequence(monkeypatch, [
        (1).to_bytes(4, "little"),
        (2).to_bytes(4, "little"),
        (1).to_bytes(4, "little"),  # regressed — bridge reordered
    ])

    rc = cli.cmd_freshness(_make_args(samples=3, require_monotonic=True))
    out = capsys.readouterr().out
    assert rc == 3
    assert "STALE" in out


def test_freshness_rejects_samples_lt_2(monkeypatch):
    """Refuse to run with fewer than 2 samples (would always pass)."""
    from ground_station.livewatch import cli
    _patch_transport_with_sequence(monkeypatch, [(0).to_bytes(4, "little")])
    with pytest.raises(SystemExit):
        cli.cmd_freshness(_make_args(samples=1))