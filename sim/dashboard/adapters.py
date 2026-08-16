"""Log-adapter registry.

One :class:`LogAdapter` per file extension. A new log format means a new
subclass; the dashboard never branches on file type. Each adapter returns
a dict ``{"axis": FlightDataset, ...}`` so downstream code stays format-agnostic.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable

from sim.sindy.flight_loader import FlightDataset, load_stream_log_csv


class LogAdapter:
    """Pluggable adapter from a file path to a per-axis dataset map.

    Subclasses register by ``extensions`` and implement :meth:`load`.
    Adding a format (mat, parquet, rosbag, hdf5, …) is one subclass.
    """

    extensions: tuple[str, ...] = ()

    def load(self, path: Path) -> dict[str, FlightDataset]:
        raise NotImplementedError

    def describe(self, path: Path) -> str:
        return f"{self.__class__.__name__}({path.name})"


# ---------------------------------------------------------------------------
# CSV adapter — built-in; flight_loader already handles the stream-log schema.
# ---------------------------------------------------------------------------

class CsvAdapter(LogAdapter):
    extensions = (".csv",)

    def load(self, path: Path) -> dict[str, FlightDataset]:
        datasets: dict[str, FlightDataset] = {}
        # Flat-column CSVs (sim/runs) have no axis prefix — default to roll.
        # Prefixed CSVs (stream_log wide-format) let load_stream_log_csv
        # infer the axis from column names automatically.
        for axis in ("roll", "pitch", "yaw"):
            ds = load_stream_log_csv(path, axis=axis)
            if ds is not None:
                datasets[axis] = ds
        return datasets


# ---------------------------------------------------------------------------
# ULog adapter — PX4 binary log.
# ---------------------------------------------------------------------------

class UlogAdapter(LogAdapter):
    extensions = (".ulg",)

    def load(self, path: Path) -> dict[str, FlightDataset]:
        from sim.sindy.adapters.ulog import load_ulog  # heavy: pyulog
        datasets: dict[str, FlightDataset] = {}
        for axis in ("roll", "pitch", "yaw"):
            ds = load_ulog(path, axis=axis)
            if ds is not None:
                datasets[axis] = ds
        return datasets


# ---------------------------------------------------------------------------
# Registry — single source of truth for what the dashboard can read.
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, list[LogAdapter]] = {}


def _register(adapter: LogAdapter) -> None:
    for ext in adapter.extensions:
        _REGISTRY.setdefault(ext.lower(), []).append(adapter)


def get_adapter(path: str | Path) -> LogAdapter:
    """Resolve the right adapter for a path. Picks the first registered
    adapter whose ``extensions`` matches the suffix."""
    suffix = Path(path).suffix.lower()
    candidates = _REGISTRY.get(suffix)
    if not candidates:
        raise ValueError(
            f"no adapter registered for {suffix!r}; "
            f"supported: {sorted(_REGISTRY)}"
        )
    return candidates[0]


def list_supported_exts() -> list[str]:
    return sorted(_REGISTRY)


# Built-in registrations. New formats are added by appending to this list.
for _adapter in (CsvAdapter(), UlogAdapter()):
    _register(_adapter)