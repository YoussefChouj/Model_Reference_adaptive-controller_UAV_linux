"""PX4 ULog format adapter.

Loads ``.ulog`` files (PX4 public datasets) into ``FlightDataset`` format.
Requires ``pyulog`` (``pip install pyulog``).

PX4 ulog topics used for plant-dynamics SINDy:

- ``vehicle_angular_velocity`` — body rates [roll, pitch, yaw] in rad/s
- ``vehicle_rates_setpoint`` — rate setpoints (the control input u)
- ``actuator_controls_0`` — motor commands (PWM or normalised, depending on log)

The adapter extracts the best available signals. If a topic is absent, the
corresponding fields are ``NaN``. The caller decides what to do with missing data.

For the adaptive-law SINDy, the MRAC signals (``mrac_state.*``) are
**not** in a generic PX4 ulog — those come only from the custom firmware's
variable-frame streaming. This adapter is for plant-dynamics discovery only.

Usage::

    from sim.sindy.adapters.ulog import load_ulog

    ds = load_ulog("PX4_23Hz_flight.ulog", axis="roll")
    # Returns FlightDataset with:
    #   x = roll_rate (from vehicle_angular_velocity)
    #   u = rate_setpoint (from vehicle_rates_setpoint)
    #   xm = NaN (not in PX4 ulog)
    #   e = NaN (not in PX4 ulog)
    #   theta = zeros (not in PX4 ulog)
"""
from __future__ import annotations

import warnings
from pathlib import Path
from typing import Optional

import numpy as np


def load_ulog(
    path: str | Path,
    axis: str = "roll",
) -> Optional["FlightDataset"]:
    """Load a PX4 ``.ulog`` file and extract rate-loop signals.

    Parameters
    ----------
    path
        Path to the ``.ulog`` file.
    axis
        ``"roll"``, ``"pitch"``, or ``"yaw"``. Determines which column
        is extracted from ``vehicle_angular_velocity`` and
        ``vehicle_rates_setpoint``.
    Returns
    -------
    FlightDataset or None
        ``None`` if the file cannot be read or has no useful data.
        The returned dataset has ``NaN`` for ``xm``, ``e``, and ``theta``
        since these are not in a generic PX4 ulog.

    Raises
    ------
    ImportError
        If ``pyulog`` is not installed.
    """
    try:
        from pyulog import ULog
    except ImportError as exc:
        raise ImportError(
            "pyulog is not installed. Install it with:\n"
            "  .venv/bin/python -m pip install pyulog"
        ) from exc

    path = Path(path)
    if not path.exists():
        warnings.warn(f"ulog file not found: {path}")
        return None

    try:
        ulog = ULog(str(path))
    except Exception as exc:
        warnings.warn(f"failed to parse ulog {path}: {exc}")
        return None

    # Map axis → field names in PX4 topics.
    axis_map = {
        "roll": (0, 0),   # (rate_idx, setpoint_idx)
        "pitch": (1, 1),
        "yaw": (2, 2),
    }

    if axis not in axis_map:
        raise ValueError(
            f"axis must be one of {list(axis_map)}, got {axis!r}"
        )
    rate_idx, sp_idx = axis_map[axis]

    # Try to get topics.
    rate_data = _get_topic_array(ulog, "vehicle_angular_velocity",
                                 ["[roll", "[pitch", "[yaw", "roll", "pitch", "yaw"])
    sp_data = _get_topic_array(ulog, "vehicle_rates_setpoint",
                                ["roll_rate", "pitch_rate", "yaw_rate"])

    if rate_data is None and sp_data is None:
        warnings.warn(
            f"ulog {path} has no vehicle_angular_velocity or "
            f"vehicle_rates_setpoint topics"
        )
        return None

    # Build timestamps.
    if rate_data is not None:
        t_sec = rate_data["t_sec"]
        x = rate_data["fields"][rate_idx]
    elif sp_data is not None:
        t_sec = sp_data["t_sec"]
        x = np.full_like(sp_data["fields"][sp_idx], np.nan)
    else:
        return None

    # Build FlightDataset-compatible dict.
    n = len(t_sec)

    # xm and e are not available in PX4 ulog.
    xm = np.full(n, np.nan)
    e = np.full(n, np.nan)

    # Rate setpoint as the control input.
    if sp_data is not None:
        u_nom = sp_data["fields"][sp_idx]
    else:
        u_nom = np.full(n, np.nan)
    u_ad = np.zeros(n)
    u = u_nom + u_ad

    # Theta is not available.
    theta = np.zeros((n, 6))

    return _FlightDatasetWrapper(
        t=t_sec,
        axis=axis,
        x=x,
        u=u,
        xm=xm,
        e=e,
        u_nom=u_nom,
        u_ad=u_ad,
        theta=theta,
        meta={
            "log_path": str(Path(path).resolve()),
            "manifest_name": "ulog",
            "elf_sha256": "",
            "recorded_hz": 0.0,
            "date": "",
            "ulogs_available": _available_topics(ulog),
        },
    )


def _get_topic_array(ulog, topic_name: str, field_hints: list[str]):
    """Extract one topic as (t_sec, fields_array).

    Returns None if the topic is absent.
    field_hints is a list of possible field names to find the axis indices.
    """
    try:
        data = ulog.get_dataset(topic_name)
    except Exception:
        return None

    fields = data.data
    if not fields:
        return None

    # Get timestamp field.
    ts_field = None
    for key in fields.keys():
        if "time" in key.lower() or key in ("timestamp", "t", "time_us"):
            ts_field = key
            break

    if ts_field is None:
        # Use the first field.
        ts_field = list(fields.keys())[0]

    t_raw = np.asarray(fields[ts_field])
    # Convert microseconds to seconds if needed.
    if t_raw.max() > 1e9:  # microseconds
        t_sec = t_raw / 1e6
    elif t_raw.max() > 1e6:  # milliseconds
        t_sec = t_raw / 1e3
    else:
        t_sec = t_raw

    # Extract rate fields — try different naming conventions.
    axis_fields = []
    for hint in field_hints:
        if hint in fields:
            axis_fields.append(np.asarray(fields[hint]))

    if not axis_fields:
        return None

    # If we got 3 fields (roll, pitch, yaw), use them directly.
    if len(axis_fields) == 3:
        return {"t_sec": t_sec, "fields": np.array(axis_fields)}

    # Otherwise try to split a multi-element field.
    flat = np.concatenate(axis_fields) if axis_fields else np.array([])
    if flat.size % 3 == 0 and flat.size >= 3:
        fields_arr = flat[:3]  # take first 3
    else:
        fields_arr = flat

    return {"t_sec": t_sec, "fields": fields_arr}


def _available_topics(ulog) -> list[str]:
    """Return all logged topic names."""
    try:
        return [d.name for d in ulog.data_list]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Wrapper — same interface as sim.sindy.flight_loader.FlightDataset
# ---------------------------------------------------------------------------

class _FlightDatasetWrapper:
    """Thin wrapper so ulog data has the same interface as FlightDataset."""

    __slots__ = ("_ds",)

    def __init__(self, t, axis, x, u, xm, e, u_nom, u_ad, theta, meta):
        self._ds = dict(
            t=t, axis=axis, x=x, u=u, xm=xm, e=e,
            u_nom=u_nom, u_ad=u_ad, theta=theta, meta=meta,
        )

    @property
    def t(self) -> np.ndarray:
        return self._ds["t"]

    @property
    def axis(self) -> str:
        return self._ds["axis"]

    @property
    def x(self) -> np.ndarray:
        return self._ds["x"]

    @property
    def u(self) -> np.ndarray:
        return self._ds["u"]

    @property
    def xm(self) -> np.ndarray:
        return self._ds["xm"]

    @property
    def e(self) -> np.ndarray:
        return self._ds["e"]

    @property
    def u_nom(self) -> np.ndarray:
        return self._ds["u_nom"]

    @property
    def u_ad(self) -> np.ndarray:
        return self._ds["u_ad"]

    @property
    def theta(self) -> np.ndarray:
        return self._ds["theta"]

    @property
    def meta(self) -> dict:
        return self._ds["meta"]

    @property
    def n_samples(self) -> int:
        return len(self._ds["t"])

    def validate(self, max_seq_gap_pct: float = 5.0) -> list[str]:
        warnings = []
        if self.n_samples < 2:
            warnings.append("fewer than 2 samples")
        if np.any(np.diff(self.t) <= 0):
            warnings.append("non-monotonic timestamps")
        return warnings
