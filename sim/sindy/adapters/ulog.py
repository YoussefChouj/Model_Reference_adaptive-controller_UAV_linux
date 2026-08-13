"""PX4 ULog format adapter.

Loads ``.ulog`` files (PX4 public datasets) into ``FlightDataset`` format.
Requires ``pyulog`` (``pip install pyulog``).

PX4 ulog topics used for plant-dynamics SINDy:

- ``vehicle_angular_velocity`` — body rates [roll, pitch, yaw] in rad/s
- ``vehicle_rates_setpoint`` — rate setpoints (the control input u)

If a topic is absent, the corresponding fields are ``NaN``. MRAC signals
(``mrac_state.*``) are not in a generic PX4 ulog — those come only from the
custom firmware's variable-frame streaming. This adapter is for
plant-dynamics discovery only.

Usage::

    from sim.sindy.adapters.ulog import load_ulog
    ds = load_ulog("PX4_23Hz_flight.ulog", axis="roll")
"""
from __future__ import annotations

import warnings
from pathlib import Path
from typing import Optional

import numpy as np


# Axis spec kinds recognised by ``_get_topic_array``. No substring matching —
# exact field-name membership only.
#
# - ``triplet_xyz``:    recognises both forms seen in the wild:
#                         * a single ``"xyz"`` field whose value is a
#                           structured ``(N, 3)`` array (newer pyulog)
#                         * three separate ``"xyz[0]"``, ``"xyz[1]"``, ``"xyz[2]"``
#                           scalar fields (older pyulog / PX4 ulog output)
#   Either form yields ``[roll, pitch, yaw]`` in the same order.
# - ``triplet_named``:  three scalar fields, e.g. ``vehicle_rates_setpoint.roll``,
#                       ``.pitch``, ``.yaw`` (PX4 ≥ 1.10).
# - ``triplet_legacy``: bracket-style (``[roll``, ``[pitch``, ``[yaw``) or
#                       legacy ``*_rate`` setpoint names. Rare in modern logs.
_RATE_AXIS_SPECS: list[dict] = [
    {"kind": "triplet_xyz", "fields": ("xyz", "xyz[0]", "xyz[1]", "xyz[2]")},
    {"kind": "triplet_legacy", "fields": ("[roll", "[pitch", "[yaw")},
]
_SETPOINT_AXIS_SPECS: list[dict] = [
    {"kind": "triplet_named", "fields": ("roll", "pitch", "yaw")},
    {"kind": "triplet_legacy", "fields": ("roll_rate", "pitch_rate", "yaw_rate")},
]
_AXIS_INDEX: dict[str, int] = {"roll": 0, "pitch": 1, "yaw": 2}


def _make_ulog(path: str | Path):
    """Construct a ``pyulog.ULog`` for ``path``. Module-level so unit tests
    can monkeypatch this and inject a fake without touching the filesystem."""
    from pyulog import ULog
    return ULog(str(path))


def load_ulog(path: str | Path, axis: str = "roll") -> Optional["_FlightDatasetWrapper"]:
    """Load a PX4 ``.ulog`` file and extract rate-loop signals.

    Returns ``None`` if the file cannot be read, is missing, or contains
    neither ``vehicle_angular_velocity`` nor ``vehicle_rates_setpoint`` with
    a recognised axis triplet. ``xm``, ``e``, and ``theta`` are ``NaN`` /
    zeros — not in a generic PX4 ulog.

    Raises ``ImportError`` if pyulog is not installed; ``ValueError`` if
    ``axis`` is not ``"roll"``, ``"pitch"``, or ``"yaw"``.
    """
    try:
        from pyulog import ULog  # noqa: F401 — import probe
    except ImportError as exc:
        raise ImportError(
            "pyulog is not installed. Install it with:\n"
            "  .venv/bin/python -m pip install pyulog"
        ) from exc

    path = Path(path)
    try:
        ulog = _make_ulog(path)
    except FileNotFoundError:
        warnings.warn(f"ulog file not found: {path}")
        return None
    except Exception as exc:
        warnings.warn(f"failed to parse ulog {path}: {exc}")
        return None

    if axis not in _AXIS_INDEX:
        raise ValueError(f"axis must be one of {list(_AXIS_INDEX)}, got {axis!r}")
    axis_idx = _AXIS_INDEX[axis]

    rate_data = _get_topic_array(ulog, "vehicle_angular_velocity", _RATE_AXIS_SPECS)
    sp_data = _get_topic_array(ulog, "vehicle_rates_setpoint", _SETPOINT_AXIS_SPECS)
    if rate_data is None and sp_data is None:
        warnings.warn(
            f"ulog {path} has no vehicle_angular_velocity or "
            f"vehicle_rates_setpoint topics"
        )
        return None

    if rate_data is not None:
        t_sec, x = rate_data["t_sec"], rate_data["fields"][axis_idx]
    else:
        t_sec = sp_data["t_sec"]
        x = np.full_like(sp_data["fields"][axis_idx], np.nan)

    n = len(t_sec)
    xm = np.full(n, np.nan)
    e = np.full(n, np.nan)
    u_nom = sp_data["fields"][axis_idx] if sp_data is not None else np.full(n, np.nan)
    u_ad = np.zeros(n)
    theta = np.zeros((n, 6))

    return _FlightDatasetWrapper(
        t=t_sec, axis=axis, x=x, u=u_nom + u_ad, xm=xm, e=e,
        u_nom=u_nom, u_ad=u_ad, theta=theta,
        meta={
            "log_path": str(Path(path).resolve()),
            "manifest_name": "ulog",
            "elf_sha256": "",
            "recorded_hz": 0.0,
            "date": "",
            "ulogs_available": _available_topics(ulog),
        },
    )


def _get_topic_array(ulog, topic_name: str, axis_specs: list[dict]):
    """Return ``{"t_sec": ..., "fields": np.ndarray([roll, pitch, yaw])}``.

    For each spec in ``axis_specs`` (in order), check whether **all** named
    fields exist in ``data.data``. First match wins. No substring matching.

    Returns ``None`` if the topic is absent or no spec matches. If the topic
    exists but no spec matched, a warning lists the available fields before
    returning ``None``.
    """
    try:
        data = ulog.get_dataset(topic_name)
    except Exception:
        return None
    fields = data.data
    if not fields:
        return None

    # PX4 publishes ``timestamp`` in microseconds. Heuristic:
    #   max > 1e9 → microseconds (current PX4); > 1e6 → ms; else seconds.
    ts_field = next((k for k in fields if "time" in k.lower()
                     or k in ("timestamp", "t", "time_us")),
                    next(iter(fields)))
    t_raw = np.asarray(fields[ts_field])
    t_max = float(np.nanmax(t_raw))
    if t_max > 1e9:
        t_sec = t_raw / 1e6
    elif t_max > 1e6:
        t_sec = t_raw / 1e3
    else:
        t_sec = t_raw

    for spec in axis_specs:
        kind, spec_fields = spec["kind"], spec["fields"]
        if kind == "triplet_xyz":
            # Two pyulog shapes exist for ``vehicle_angular_velocity.xyz``:
            #   * single ``"xyz"`` field whose value is a structured (N, 3)
            #     array (newer pyulog, after the ULog parser flattens fixed
            #     arrays)
            #   * three separate ``"xyz[0]"``, ``"xyz[1]"``, ``"xyz[2]"`` scalar
            #     fields (older pyulog / canonical PX4 ulog output)
            # ``spec_fields`` lists the candidates in priority order; the
            # structured form is preferred when both are present.
            if "xyz" in fields:
                raw = np.asarray(fields["xyz"])
                if raw.ndim == 2 and raw.shape[1] == 3:
                    return {"t_sec": t_sec,
                            "fields": np.stack([raw[:, 0], raw[:, 1], raw[:, 2]], axis=0)}
                warnings.warn(
                    f"topic {topic_name!r} has key 'xyz' but shape "
                    f"{raw.shape!r}; expected (N, 3); trying indexed fields"
                )
            idx_keys = ("xyz[0]", "xyz[1]", "xyz[2]")
            if all(k in fields for k in idx_keys):
                return {"t_sec": t_sec,
                        "fields": np.stack([np.asarray(fields[k]) for k in idx_keys], axis=0)}
            continue
        if kind in ("triplet_named", "triplet_legacy"):
            if not all(f in fields for f in spec_fields):
                continue
            return {"t_sec": t_sec,
                    "fields": np.stack([np.asarray(fields[f]) for f in spec_fields], axis=0)}
        warnings.warn(f"unknown axis spec kind {kind!r}; skipping")

    warnings.warn(
        f"topic {topic_name!r} exists but no axis triplet matched. "
        f"Available fields: {sorted(fields.keys())}"
    )
    return None


def _available_topics(ulog) -> list[str]:
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
        self._ds = dict(t=t, axis=axis, x=x, u=u, xm=xm, e=e,
                        u_nom=u_nom, u_ad=u_ad, theta=theta, meta=meta)

    def __getattr__(self, name):
        try:
            return self._ds[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    @property
    def n_samples(self) -> int:
        return len(self._ds["t"])

    def validate(self, max_seq_gap_pct: float = 5.0) -> list[str]:
        ws: list[str] = []
        if self.n_samples < 2:
            ws.append("fewer than 2 samples")
        if np.any(np.diff(self.t) <= 0):
            ws.append("non-monotonic timestamps")
        return ws
