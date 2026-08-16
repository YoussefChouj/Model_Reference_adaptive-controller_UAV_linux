"""Load stream_log CSV output into a FlightDataset.

stream_log writes one CSV per slot, or one merged CSV when --symbol was used.
The format is always:
    t_src_ms, t_host_s, seq, [variable columns...]

Variable names come from DWARF paths, so a Theta:6 manifest entry produces
columns "mrac_state.roll.Theta[0]" .. "mrac_state.roll.Theta[5]".
The old 4-column long format (t_s, frame, key, value) is handled by an
adapter; stream_log always uses wide format.

Two Theta column naming conventions are accepted:
- Theta[0] .. Theta[5]   ← stream_log default naming (DWARF path + index)
- theta_0 .. theta_5     ← legacy wide CSV export
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np


# Axes supported by the MRAC firmware.
_SUPPORTED_AXES = ("roll", "pitch", "yaw", "z")

# Mapping from canonical field name → list of regexes that match column names.
# Tested in order; first match wins.
#
# Column name styles supported:
#   - DWARF path  : mrac_state.roll.e   (stream_log default)
#   - prefixed    : roll.e, roll_e       (legacy with axis prefix)
#   - flat        : e, xm, u_nom        (sim/runs CSV — no axis prefix)
_FIELD_PATTERNS: dict[str, list[re.Pattern]] = {
    "e": [
        re.compile(r"^mrac_state\.(\w+)\.e$"),
        re.compile(r"^(\w+)\.e$"),
        re.compile(r"^(\w+)_e$"),
        re.compile(r"^e$"),                      # flat — sim CSV
    ],
    "u_nom": [
        re.compile(r"^mrac_state\.(\w+)\.u_nom$"),
        re.compile(r"^(\w+)\.u_nom$"),
        re.compile(r"^(\w+)_u_nom$"),
        re.compile(r"^u_nom$"),                   # flat — sim CSV
    ],
    "u_ad": [
        re.compile(r"^mrac_state\.(\w+)\.u_ad$"),
        re.compile(r"^(\w+)\.u_ad$"),
        re.compile(r"^(\w+)_u_ad$"),
        re.compile(r"^u_ad$"),                    # flat — sim CSV
    ],
    "xm": [
        re.compile(r"^mrac_state\.(\w+)\.xm$"),
        re.compile(r"^(\w+)\.xm$"),
        re.compile(r"^(\w+)_xm$"),
        re.compile(r"^xm$"),                       # flat — sim CSV
    ],
    "theta": [
        re.compile(r"^mrac_state\.(\w+)\.Theta\[(\d+)\]$"),
        re.compile(r"^mrac_state\.(\w+)\.theta_(\d+)$"),
        re.compile(r"^(\w+)\.theta_(\d+)$"),
        re.compile(r"^(\w+)_theta_(\d+)$"),
        re.compile(r"^theta_(\d+)$"),             # flat — sim CSV: theta_0..theta_5
    ],
    # Plant state x (bare, no axis prefix — used when xm and e are present)
    "x": [
        re.compile(r"^mrac_state\.(\w+)\.x$"),
        re.compile(r"^(\w+)\.x$"),
        re.compile(r"^(\w+)_x$"),
        re.compile(r"^x$"),                        # flat — sim CSV
    ],
}


@dataclass
class FlightDataset:
    """MRAC signals for one axis, pivoted from stream_log CSV.

    Attributes
    ----------
    t : np.ndarray
        Seconds, from ``t_src_ms``.
    axis : str
        ``"roll"``, ``"pitch"``, ``"yaw"``, or ``"z"``.
    x : np.ndarray
        Plant state (rad/s). Reconstructed as ``xm - e``.
    u : np.ndarray
        Total control output (Nm). Reconstructed as ``u_nom + u_ad``.
    xm : np.ndarray
        Reference model state (rad/s).
    e : np.ndarray
        Tracking error (rad/s).
    u_nom : np.ndarray
        Baseline PID output (Nm).
    u_ad : np.ndarray
        MRAC adaptive output (Nm).
    theta : np.ndarray
        Adaptive weights, shape ``(n_samples, 6)``.
    meta : dict
        Source provenance: ``log_path``, ``manifest_name``, ``elf_sha256``,
        ``recorded_hz``, ``date``, ``columns``.
    """
    t: np.ndarray
    axis: str
    x: np.ndarray
    u: np.ndarray
    xm: np.ndarray
    e: np.ndarray
    u_nom: np.ndarray
    u_ad: np.ndarray
    theta: np.ndarray
    meta: dict = field(default_factory=dict)

    @property
    def n_samples(self) -> int:
        return len(self.t)

    def validate(self, max_seq_gap_pct: float = 5.0) -> list[str]:
        """Check dataset health. Returns list of warnings (empty = healthy)."""
        warnings: list[str] = []

        if len(self.t) < 2:
            warnings.append("fewer than 2 samples")
            return warnings

        dt = np.diff(self.t)
        if np.any(dt <= 0):
            warnings.append("non-monotonic timestamps detected")

        median_dt = float(np.median(dt))
        if median_dt <= 0:
            warnings.append("non-positive median dt")
        else:
            implied_hz = 1.0 / median_dt
            if implied_hz < 1.0:
                warnings.append(f"implied sample rate {implied_hz:.2f} Hz is below 1 Hz")
            meta_hz = self.meta.get("recorded_hz", 0)
            if meta_hz > 0 and abs(implied_hz - meta_hz) / meta_hz > 0.2:
                warnings.append(
                    f"implied sample rate {implied_hz:.1f} Hz differs >20% "
                    f"from declared rate {meta_hz:.1f} Hz"
                )

        for name, arr in [
            ("x", self.x), ("u", self.u), ("xm", self.xm),
            ("e", self.e), ("u_nom", self.u_nom), ("u_ad", self.u_ad),
        ]:
            if not np.all(np.isfinite(arr)):
                n_nan = int(np.sum(~np.isfinite(arr)))
                warnings.append(f"{name} has {n_nan} non-finite values")

        return warnings


def load_stream_log_csv(
    path: str | Path,
    axis: Optional[str] = None,
    manifest_name: str = "adhoc",
    elf_sha256: Optional[str] = None,
    recorded_hz: Optional[float] = None,
) -> FlightDataset:
    """Load a stream_log CSV for one axis.

    Parameters
    ----------
    path
        Path to the CSV written by ``stream_log.py``.
    axis
        Which axis to extract. Required if the file contains multiple axes.
        If the file has only one axis, it is inferred automatically.
    manifest_name
        Identifier for the variable set that produced this CSV.
    elf_sha256
        Firmware build SHA (from the ``.meta.json`` sidecar if available).
    recorded_hz
        Declared sample rate. Inferred from median dt if not provided.

    Returns
    -------
    FlightDataset

    Raises
    ------
    ValueError
        If the file contains no MRAC columns, or if the requested axis is absent.
    """
    path = Path(path)
    import csv

    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        cols = reader.fieldnames
        if not cols:
            raise ValueError(f"empty CSV: {path}")

        # Detect which axis(s) appear in the column names.
        axes_found: dict[str, set[str]] = {a: set() for a in _SUPPORTED_AXES}
        axis: Optional[str] = axis  # local binding

        col_to_field: dict[str, str] = {}   # col_name → canonical field
        col_to_axis: dict[str, str] = {}    # col_name → axis
        theta_cols: dict[str, dict[int, str]] = {}  # axis → {index: col_name}

        # Flat-column fields: no axis prefix, no capture group.
        # Determined by simple set membership instead of regex.
        _FLAT_FIELDS = {"e", "xm", "u_nom", "u_ad", "x"}

        for col in cols:
            if col in ("t_src_ms", "t_host_s", "seq"):
                continue

            matched_axis: Optional[str] = None
            matched_field: Optional[str] = None
            m: Optional[re.Match] = None

            # 1. Flat column (no axis prefix — e.g. sim/runs CSV).
            if col in _FLAT_FIELDS:
                matched_field = col
                matched_axis = axis

            # 2a. Axis-prefixed column — group(1) must be a real axis.
            #     Excludes flat theta_0..5 (group is a digit).
            if not matched_field:
                for field_name, patterns in _FIELD_PATTERNS.items():
                    for pat in patterns:
                        m = pat.match(col)
                        if m and m.lastindex and m.lastindex >= 1:
                            # Flat theta_0..5 has digit as group(1) — not an axis.
                            if m.group(1) in _SUPPORTED_AXES:
                                matched_field = field_name
                                matched_axis = m.group(1)
                                break
                    if matched_field:
                        break

            # 2b. Flat theta_0..5 — no axis, group(1) is a digit index.
            if not matched_field and col.startswith("theta_"):
                try:
                    idx = int(col.rsplit("_", 1)[-1])
                    theta_cols.setdefault(axis, {})[idx] = col
                    axes_found[axis].add("theta")
                    continue
                except ValueError:
                    pass

            if matched_field:
                if matched_field == "theta":
                    idx = int(m.group(m.lastindex)) if m.lastindex else int(col.rsplit("_", 1)[-1])
                    theta_cols.setdefault(matched_axis, {})[idx] = col
                else:
                    col_to_field[col] = matched_field
                    col_to_axis[col] = matched_axis or axis
                    axes_found[col_to_axis[col]].add(matched_field)

        # Determine which axis to extract.
        present = [a for a, fields in axes_found.items() if fields]
        if not present:
            raise ValueError(
                f"no MRAC columns found in {path}. "
                f"Columns: {list(cols)[:10]}"
            )

        if axis is None:
            if len(present) == 1:
                axis = present[0]
            else:
                raise ValueError(
                    f"multiple axes in {path}: {present}. "
                    f"Pass axis= to disambiguate."
                )

        if axis not in present:
            raise ValueError(
                f"axis {axis!r} not found in {path}. "
                f"Present axes: {present}"
            )

        # Collect columns for this axis.
        field_cols: dict[str, str] = {}
        for col, field in col_to_field.items():
            if col_to_axis.get(col) == axis:
                field_cols[field] = col

        theta_map = theta_cols.get(axis, {})

        # Read rows.
        t_list: list[float] = []
        e_list: list[float] = []
        u_nom_list: list[float] = []
        u_ad_list: list[float] = []
        xm_list: list[float] = []
        theta_rows: list[list[float]] = []

        # Detect timestamp column: stream_log uses t_src_ms (ms),
        # sim runs use bare t (seconds).
        if "t_src_ms" in cols:
            t_scale = 1.0 / 1000.0   # ms → s
            t_col = "t_src_ms"
        elif "t" in cols:
            t_scale = 1.0            # already seconds
            t_col = "t"
        else:
            raise ValueError(f"no timestamp column found in {path}. Columns: {list(cols)[:10]}")

        for row in reader:
            t_list.append(float(row[t_col]) * t_scale)

            def _f(col_name: str) -> float:
                val = row.get(col_name, "")
                return float(val) if val.strip() else float("nan")

            e_list.append(_f(field_cols.get("e", "")))
            u_nom_list.append(_f(field_cols.get("u_nom", "")))
            u_ad_list.append(_f(field_cols.get("u_ad", "")))
            xm_list.append(_f(field_cols.get("xm", "")))

            theta_row = [
                _f(theta_map[i]) if i in theta_map else float("nan")
                for i in range(6)
            ]
            theta_rows.append(theta_row)

        t = np.array(t_list, dtype=float)
        e = np.array(e_list, dtype=float)
        u_nom = np.array(u_nom_list, dtype=float)
        u_ad = np.array(u_ad_list, dtype=float)
        xm = np.array(xm_list, dtype=float)
        theta = np.array(theta_rows, dtype=float)

        # Reconstruct plant state and total output.
        x = xm - e
        u = u_nom + u_ad

        # Validate SEQ gaps if present.
        seq_gap_warnings: list[str] = []
        if "seq" in cols:
            seqs = [int(row["seq"]) for row in csv.DictReader(path.open())]
            gaps = [s2 - s1 for s1, s2 in zip(seqs[:-1], seqs[1:]) if s2 > s1]
            if gaps:
                max_gap = max(gaps)
                n_big = sum(1 for g in gaps if g > 1)
                gap_pct = n_big / len(gaps) * 100
                if gap_pct > 5.0:
                    seq_gap_warnings.append(
                        f"SEQ gap rate {gap_pct:.1f}% exceeds 5% threshold "
                        f"(max gap={max_gap})"
                    )

        # Infer recorded_hz from median dt if not provided.
        if recorded_hz is None and len(t) >= 2:
            dt = float(np.median(np.diff(t)))
            if dt > 0:
                recorded_hz = round(1.0 / dt, 1)

        meta: dict = {
            "log_path": str(path.resolve()),
            "manifest_name": manifest_name,
            "elf_sha256": elf_sha256 or "",
            "recorded_hz": recorded_hz or 0.0,
            "date": "",
            "columns": list(cols),
        }

        return FlightDataset(
            t=t, axis=axis, x=x, u=u, xm=xm, e=e,
            u_nom=u_nom, u_ad=u_ad, theta=theta, meta=meta,
        )
