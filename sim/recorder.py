"""Append-only trajectory recorders (engine-agnostic, ADR-0012 D7).

The column schema matches the ``state_dict`` returned by any
:class:`sim.plant.Plant.step()`, so the recorder is agnostic to which
engine (identified / rigid-body / MuJoCo) produced the trajectory.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import IO, Any, Protocol


CSV_COLUMNS = [
    "t", "x", "y", "z", "vx", "vy", "vz", "phi", "theta", "psi",
    "p", "q", "r", "q0", "q1", "q2", "q3", "thrust",
    "m1", "m2", "m3", "m4", "command_z", "command_roll",
    "command_pitch", "command_yaw",
]


class Recorder(Protocol):
    """Pluggable sink used by :class:`sim.runner.Runner` (the ``loop.tick``-driven run)."""

    def start(self, outdir: Path) -> None: ...
    def record(self, state_dict: dict, t: float) -> None: ...
    def stop(self) -> None: ...
    def summary(self) -> dict: ...


class _RecorderBase:
    def __init__(self) -> None:
        self._stream: IO[str] | None = None
        self._n_records = 0
        self._first_t: float | None = None
        self._last_t: float | None = None
        self.path: Path | None = None

    def _count(self, t: float) -> None:
        if self._first_t is None:
            self._first_t = float(t)
        self._last_t = float(t)
        self._n_records += 1

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.flush()
            self._stream.close()
            self._stream = None

    def summary(self) -> dict:
        duration = 0.0
        if self._first_t is not None and self._last_t is not None:
            duration = self._last_t - self._first_t
        return {"n_records": self._n_records, "duration_s": duration}


class CSVRecorder(_RecorderBase):
    """Write a flush-on-every-row ``trajectory.csv`` file."""

    def __init__(self) -> None:
        super().__init__()
        self._writer: csv.DictWriter | None = None

    def start(self, outdir: Path) -> None:
        outdir.mkdir(parents=True, exist_ok=True)
        self.path = outdir / "trajectory.csv"
        self._stream = self.path.open("a", encoding="utf-8", newline="")
        self._writer = csv.DictWriter(self._stream, fieldnames=CSV_COLUMNS)
        if self.path.stat().st_size == 0:
            self._writer.writeheader()
            self._stream.flush()

    def record(self, state_dict: dict, t: float) -> None:
        if self._stream is None or self._writer is None:
            raise RuntimeError("CSVRecorder.start() must be called before record()")
        motors = list(state_dict.get("motors", (0.0, 0.0, 0.0, 0.0)))
        assert len(motors) == 4, "CSVRecorder expects four per-motor thrust values"
        command = state_dict.get("command", {})
        row: dict[str, Any] = {key: state_dict.get(key, 0.0) for key in CSV_COLUMNS}
        row.update({
            "t": float(t),
            "m1": motors[0], "m2": motors[1], "m3": motors[2], "m4": motors[3],
            "command_z": command.get("z", state_dict.get("command_z", 0.0)),
            "command_roll": command.get("roll", state_dict.get("command_roll", 0.0)),
            "command_pitch": command.get("pitch", state_dict.get("command_pitch", 0.0)),
            "command_yaw": command.get("yaw", state_dict.get("command_yaw", 0.0)),
        })
        self._writer.writerow(row)
        self._stream.flush()
        self._count(t)


class JSONLRecorder(_RecorderBase):
    """Write one flush-on-every-record JSON object per line."""

    def start(self, outdir: Path) -> None:
        outdir.mkdir(parents=True, exist_ok=True)
        self.path = outdir / "trajectory.jsonl"
        self._stream = self.path.open("a", encoding="utf-8")

    def record(self, state_dict: dict, t: float) -> None:
        if self._stream is None:
            raise RuntimeError("JSONLRecorder.start() must be called before record()")
        record = dict(state_dict)
        motors = record.get("motors")
        if hasattr(motors, "tolist"):
            record["motors"] = motors.tolist()
        record["t"] = float(t)
        self._stream.write(json.dumps(record, sort_keys=True) + "\n")
        self._stream.flush()
        self._count(t)


__all__ = ["CSV_COLUMNS", "Recorder", "CSVRecorder", "JSONLRecorder"]