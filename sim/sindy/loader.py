"""Read stream_log CSV files and pivot to wide per-axis FlightDataset format.

Input format (one row per sample, one column per variable):

    t_src_ms,t_host_s,seq,mrac_state.roll.e,mrac_state.roll.u_nom,mrac_state.roll.xm,...
    mrac_state.roll.Theta:6 columns (Theta[0]..Theta[5])

Output: FlightDataset — one per axis per CSV.

The loader handles:
- Single-slot CSVs (one axis or multi-axis in columns)
- Multi-slot CSVs merged on t_src_ms
- Column-name patterns from stream_log: mrac_state.<axis>.<field>
- Reconstruction of x = xm - e, u = u_nom + u_ad
- SEQ gap validation (>5% gaps → warning, dataset still returned with flag)
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np


# ----------------------------------------------------------------------
# Public types
# ----------------------------------------------------------------------


@dataclass
class FlightDataset:
    """Canonical time-series for one axis from one flight log.

    Attributes
    ----------
    t : np.ndarray
        Time in seconds, from t_src_ms.
    axis : str
        "roll", "pitch", "yaw", or "z".
    x : np.ndarray
        Plant state (rad/s). Reconstructed as xm - e.
    u : np.ndarray
        Total control output (Nm). Reconstructed as u_nom + u_ad.
    xm : np.ndarray
        Reference model state (rad/s).
    e : np.ndarray
        Tracking error (rad/s).
    theta : np.ndarray
        (N, 6) adaptive weights, Theta[0]..Theta[5].
    u_nom : np.ndarray
        Baseline PID output (Nm), stored for provenance.
    u_ad : np.ndarray
        Adaptive output (Nm), stored for provenance.
    seq : np.ndarray
        Frame sequence numbers for gap detection.
    meta : dict
        Source metadata: log_path, elf_sha, recorded_hz, sample_count.
    gap_warn : bool
        True if >5 % of expected frames were missing (SEQ gaps).
    """

    t: np.ndarray
    axis: str
    x: np.ndarray
    u: np.ndarray
    xm: np.ndarray
    e: np.ndarray
    theta: np.ndarray
    u_nom: np.ndarray
    u_ad: np.ndarray
    seq: np.ndarray
    meta: dict = field(default_factory=dict)
    gap_warn: bool = False


# ----------------------------------------------------------------------
# Column-name helpers
# ----------------------------------------------------------------------

# Matches mrac_state.<axis>.<field> and mrac_state.<axis>.Theta:N
_MRAC_RE = re.compile(r"^mrac_state\.([a-z]+)\.(.+)$")

# Matches Theta:N suffixes (Theta:6 → Theta[0]..Theta[5])
_THETA_RE = re.compile(r"^Theta:(\d+)$")


def _parse_header(columns: list[str]) -> dict[str, dict[str, list[str]]]:
    """Group column names by axis and field.

    Returns
    -------
    axis_map : dict[axis][field] → [col_name, ...]

    Example
    -------
    >>> _parse_header(["mrac_state.roll.e", "mrac_state.roll.Theta:6",
    ...                "mrac_state.pitch.e"])
    {"roll": {"e": ["mrac_state.roll.e"],
               "Theta": ["mrac_state.roll.Theta:6"]},
     "pitch": {"e": ["mrac_state.pitch.e"]}}
    """
    axes: dict[str, dict[str, list[str]]] = {}
    for col in columns:
        m = _MRAC_RE.match(col)
        if not m:
            continue
        axis, field_raw = m.group(1), m.group(2)

        # Expand Theta:N into Theta[0]..Theta[N-1]
        tm = _THETA_RE.match(field_raw)
        if tm:
            n = int(tm.group(1))
            expanded = [f"mrac_state.{axis}.Theta[{i}]" for i in range(n)]
        else:
            expanded = [col]

        axes.setdefault(axis, {}).setdefault(field_raw, []).append(col)

    return axes


def _read_raw(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Read a stream_log CSV and return (header, rows)."""
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        header = reader.fieldnames or []
        rows = list(reader)
    return header, rows


def _to_array(rows: list[dict[str, str]], col: str) -> np.ndarray:
    """Extract a column as float64. Returns zeros on missing entries."""
    out = np.empty(len(rows), dtype=np.float64)
    for i, row in enumerate(rows):
        raw = row.get(col, "")
        out[i] = float(raw) if raw.strip() else 0.0
    return out


def _seq_gap_ratio(seq: np.ndarray) -> float:
    """Fraction of expected frames missing (gap count / expected count)."""
    if len(seq) < 2:
        return 0.0
    expected = int(seq[-1]) - int(seq[0]) + 1
    return max(0.0, 1.0 - len(seq) / expected)


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------


def load_stream_log(
    path: str | Path,
    *,
    axis_filter: Optional[list[str]] = None,
) -> list[FlightDataset]:
    """Load a stream_log CSV and return one FlightDataset per detected axis.

    Parameters
    ----------
    path
        Path to the CSV produced by stream_log.py.
    axis_filter
        If given, only load these axes (e.g. ["roll", "pitch"]).

    Returns
    -------
    list[FlightDataset]
        One dataset per axis. Order is sorted by axis name.

    Raises
    ------
    ValueError
        If no MRAC columns are found in the CSV.
    """
    path = Path(path)
    header, rows = _read_raw(path)

    # Drop metadata columns
    meta_cols = {"t_src_ms", "t_host_s", "seq"}
    data_cols = [c for c in header if c not in meta_cols]
    axis_map = _parse_header(data_cols)

    if not axis_map:
        raise ValueError(
            f"no MRAC columns found in {path}; "
            "expected mrac_state.<axis>.<field> columns"
        )

    # Optionally restrict axes
    if axis_filter:
        axis_map = {ax: cols for ax, cols in axis_map.items() if ax in axis_filter}

    datasets: list[FlightDataset] = []
    for axis in sorted(axis_map.keys()):
        fields = axis_map[axis]

        # Core MRAC signals
        e_col  = _one(fields, "e")
        xm_col = _one(fields, "xm")
        un_col = _one(fields, "u_nom")
        ua_col = _one(fields, "u_ad")

        # Theta array — Theta:N is expanded to Theta[0]..Theta[N-1]
        theta_cols = _theta_cols(fields)

        # Build arrays
        t   = _to_array(rows, "t_src_ms") / 1000.0      # ms → s
        seq = _to_array(rows, "seq")

        e   = _to_array(rows, e_col) if e_col else np.zeros_like(t)
        xm  = _to_array(rows, xm_col) if xm_col else np.zeros_like(t)
        un  = _to_array(rows, un_col) if un_col else np.zeros_like(t)
        ua  = _to_array(rows, ua_col) if ua_col else np.zeros_like(t)
        th  = _theta_array(rows, theta_cols) if theta_cols else np.zeros((len(t), 6))

        x = xm - e
        u = un + ua

        # Validate: warn on >5% SEQ gaps
        gap_ratio = _seq_gap_ratio(seq)
        gap_warn = gap_ratio > 0.05

        # Measure actual rate from median dt
        dt_vals = np.diff(t)
        dt_median = np.median(dt_vals[dt_vals > 0])
        recorded_hz = 1.0 / dt_median if dt_median > 0 else 0.0

        datasets.append(
            FlightDataset(
                t=t, axis=axis, x=x, u=u, xm=xm, e=e,
                theta=th, u_nom=un, u_ad=ua, seq=seq,
                meta={
                    "log_path": str(path.resolve()),
                    "recorded_hz": round(recorded_hz, 1),
                    "sample_count": len(t),
                    "gap_ratio": round(gap_ratio, 4),
                    "elf_sha": "",          # filled by caller if known
                },
                gap_warn=gap_warn,
            )
        )

    return datasets


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _one(fields: dict[str, list[str]], key: str) -> Optional[str]:
    """Return the single column for a scalar field, or None."""
    col_list = fields.get(key)
    if not col_list:
        return None
    return col_list[0]


def _theta_cols(fields: dict[str, list[str]]) -> list[str]:
    """Return Theta[N] column names in order, or empty list."""
    cols: list[str] = []
    for key in sorted(fields.keys()):
        m = _THETA_RE.match(key)
        if m:
            n = int(m.group(1))
            cols.extend(sorted(
                c for c in fields[key]
                if re.search(r"Theta\[\d+\]", c)
            ))
    # Remove duplicates while preserving order
    seen: set[str] = set()
    out: list[str] = []
    for c in cols:
        if c not in seen:
            seen.add(c)
            out.append(c)
    # Trim to max 6
    return out[:6]


def _theta_array(rows: list[dict[str, str]], cols: list[str]) -> np.ndarray:
    """Build (N, 6) theta matrix from Theta[N] columns."""
    n = len(rows)
    th = np.zeros((n, 6), dtype=np.float64)
    for j, col in enumerate(cols[:6]):
        for i, row in enumerate(rows):
            raw = row.get(col, "")
            th[i, j] = float(raw) if raw.strip() else 0.0
    return th
