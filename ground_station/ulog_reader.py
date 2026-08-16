"""DWARF-aware ULog reader.

Turns a PX4 .ulg file into DataFrames indexed by timestamp (seconds, monotonic).
Optionally resolves ulog field names to DWARF firmware symbols via the existing
SymbolResolver from ground_station.livewatch.symbols.
"""
from __future__ import annotations

import struct
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from pyulog import ULog

from ground_station.livewatch.symbols import SymbolResolver


@dataclass(frozen=True)
class ResolvedField:
    ulog_field: str
    dwarf_path: str
    address: int
    size: int


@dataclass(frozen=True)
class UnresolvedField:
    ulog_field: str
    reason: str   # 'not_in_elf' | 'ambiguous'


def _ulog_to_dwarf(name: str) -> str | None:
    """Try to reverse-map a ulog field name to DWARF dotted/indexed notation.

    ``s_ekf_x_3``  ->  ``s.ekf.x[3]``    (all underscores in the base become dots)
    ``q_0``         ->  ``q[0]``
    ``s_ekf_x``     ->  ``None``   (no trailing index)
    ``timestamp``   ->  ``None``

    The last underscore-separated segment must be numeric (array index).
    All underscores in the base (everything before the numeric index) become
    dot separators. ``s_ekf`` becomes ``s.ekf``; ``q`` stays ``q``.
    """
    if name == "timestamp":
        return None
    parts = name.split("_")
    if len(parts) < 2 or not parts[-1].isdigit():
        return None
    idx = parts[-1]
    # The last non-index segment is the array field name; dot before it.
    # Everything before that stays as-is (preserves multi-segment bases like s_ekf).
    base_parts = parts[:-1]
    # Convert last segment of base to dot notation (it's the field name before the index)
    if len(base_parts) == 1:
        base = base_parts[0]
    else:
        base = ".".join(base_parts[:-1]) + "." + base_parts[-1]
    return f"{base}[{idx}]"


class ULogReader:
    """DWARF-aware PX4 ulog reader."""

    def __init__(self, ulog_path: str | Path, elf_path: str | Path | None = None):
        self.ulog_path = Path(ulog_path)
        self._resolver: SymbolResolver | None = None
        self._dwarf_cache: dict[str, tuple[str, int, int] | None] = {}

        if elf_path:
            try:
                self._resolver = SymbolResolver(elf_path)
            except Exception as exc:
                warnings.warn(f"SymbolResolver({elf_path}): {exc}; DWARF resolution disabled")
                self._resolver = None

        try:
            self._ulog = ULog(str(self.ulog_path), disable_str_exceptions=True)
        except Exception as exc:
            raise ValueError(f"not a valid ulog file: {self.ulog_path}: {exc}") from exc

        # Build {topic_name -> Data}
        self._datasets: dict[str, Any] = {}
        for ds in self._ulog.data_list:
            self._datasets[ds.name] = ds

    # ---- public API ---------------------------------------------------------

    @property
    def topics(self) -> list[str]:
        return list(self._datasets)

    def topic(self, name: str) -> pd.DataFrame:
        ds = self._datasets[name]
        data = ds.data

        # Build column list from field_data (preserves order)
        col_names = [fd.field_name for fd in ds.field_data]
        col_values: dict[str, np.ndarray] = {}
        for col in col_names:
            col_values[col] = data[col]

        # Timestamp in microseconds -> seconds
        ts_us = data["timestamp"].astype(np.float64)
        ts_s = ts_us / 1e6

        df = pd.DataFrame(col_values, index=ts_s)
        df.index.name = "t_sec"
        df.sort_index(inplace=True)

        # Optionally add DWARF-resolved twin columns
        if self._resolver is not None:
            for field in col_names:
                resolved = self._resolve_field(field)
                if resolved is not None:
                    dw_path, addr, size = resolved
                    df[f"resolved_{dw_path}"] = df[field]

        return df

    def at(self, t_seconds: float) -> dict[str, Any]:
        """Snapshot of every topic at the closest sample to *t_seconds*."""
        out = {}
        for name, ds in self._datasets.items():
            ts_us = ds.data["timestamp"]
            ts_s = ts_us / 1e6
            idx = np.abs(ts_s - t_seconds).argmin()
            out[name] = {fd.field_name: ds.data[fd.field_name][idx]
                         for fd in ds.field_data}
        return out

    def between(self, t0: float, t1: float) -> dict[str, pd.DataFrame]:
        """Slice every topic to [t0, t1) in seconds."""
        return {name: df[(df.index >= t0) & (df.index < t1)]
                for name, df in ((n, self.topic(n)) for n in self.topics)}

    def fields_resolved(self) -> list[ResolvedField | UnresolvedField]:
        """All ulog fields annotated with DWARF resolution status."""
        results: list[ResolvedField | UnresolvedField] = []

        for ds in self._ulog.data_list:
            for fd in ds.field_data:
                name = fd.field_name
                result = self._resolve_field_full(name)
                if isinstance(result, tuple):
                    dw_path, addr, size = result
                    results.append(ResolvedField(name, dw_path, addr, size))
                else:
                    results.append(UnresolvedField(name, result))

        return results

    # ---- DWARF helpers ------------------------------------------------------

    def _resolve_field(self, field: str) -> tuple[str, int, int] | None:
        """Return (dwarf_path, address, size) or None."""
        result = self._resolve_field_full(field)
        if isinstance(result, tuple):
            return result
        return None

    def _resolve_field_full(self, field: str) -> tuple[str, int, int] | str:
        """Return DWARF resolution result for one ulog field.

        Returns:
            (dwarf_path, address, size) on success.
            'not_in_elf'  — no matching DWARF symbol found.
            'ambiguous'    — multiple candidates match.

        Tries four forms in order:
          1. field as-is (e.g. "Gyro_X_Ori")
          2. ulog->dwarf form (e.g. "s_ekf_x_3" -> "s_ekf.x[3]")
          3. field with underscores -> dots (e.g. "Gyro_X_Ori" -> "Gyro.X.Ori")
          4. last-segment-only conversion (e.g. "q_0" -> "q[0]")
        """
        if self._resolver is None:
            return "not_in_elf"

        if field in self._dwarf_cache:
            return self._dwarf_cache[field]

        # Iterate every plausible DWARF path for this ulog field.
        candidates: list[str] = [field]
        dw_path = _ulog_to_dwarf(field)
        if dw_path is not None:
            candidates.append(dw_path)
        # Field names with underscores sometimes map to DWARF dotted paths.
        if "_" in field:
            candidates.append(field.replace("_", "."))
        # `q_0` style without dots: try splitting first underscore as array index.
        uscore = field.rfind("_")
        if 0 < uscore < len(field) - 1 and field[uscore + 1:].isdigit():
            candidates.append(field[:uscore] + f"[{field[uscore + 1:]}]")

        last_err: Exception | None = None
        for path in candidates:
            try:
                sym = self._resolver.resolve(path)
                self._dwarf_cache[field] = (path, sym.address, sym.size)
                return (path, sym.address, sym.size)
            except KeyError as e:
                last_err = e
                continue
            except ValueError as e:
                last_err = e
                continue

        self._dwarf_cache[field] = "not_in_elf"
        return "not_in_elf"


# ---- module-level convenience -----------------------------------------------


def load_ulog(path: str | Path, elf_path: str | Path | None = None) -> ULogReader:
    return ULogReader(path, elf_path)
