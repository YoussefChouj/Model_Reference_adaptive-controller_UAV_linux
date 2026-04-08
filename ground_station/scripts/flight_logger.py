"""
Flight CSV logging and offline analysis (Frame A + Frame B telemetry).
"""
from __future__ import annotations

import csv
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class FlightLogger:
    def __init__(self) -> None:
        self._fp: Optional[Any] = None
        self._writer: Optional[Any] = None
        self._path: Optional[Path] = None
        self._rows = 0
        self._t0: float = 0.0

    def start(self, filename: Path) -> None:
        self.stop()
        filename.parent.mkdir(parents=True, exist_ok=True)
        self._path = filename
        self._fp = open(filename, "w", newline="", encoding="utf-8")
        self._writer = csv.writer(self._fp)
        self._writer.writerow(["t_s", "frame", "key", "value"])
        self._rows = 0
        self._t0 = time.monotonic()

    def log_snapshot(self, frame: str, data: Dict[str, float]) -> None:
        if self._writer is None:
            return
        t = time.monotonic() - self._t0
        for k in sorted(data.keys()):
            self._writer.writerow([f"{t:.4f}", frame, k, f"{data[k]:.8g}"])
            self._rows += 1

    def stop(self) -> None:
        if self._fp is not None:
            try:
                self._fp.close()
            except Exception:
                pass
            self._fp = None
            self._writer = None
        p = self._path
        self._path = None
        if p is not None:
            try:
                sz = p.stat().st_size
            except Exception:
                sz = 0
            print(f"FlightLogger: closed {p} rows={self._rows} size={sz} bytes", flush=True)

    @staticmethod
    def analyze(filename: Path) -> Dict[str, Any]:
        """Minimal summary: duration, numeric ranges for mrac.pitch.e, pid.z_rate FB."""
        if not filename.exists():
            return {"error": "file not found"}
        t_min, t_max = None, None
        pitch_e: List[float] = []
        thr_vals: List[float] = []
        with open(filename, newline="", encoding="utf-8") as f:
            r = csv.DictReader(f)
            for row in r:
                try:
                    ts = float(row["t_s"])
                except Exception:
                    continue
                t_min = ts if t_min is None else min(t_min, ts)
                t_max = ts if t_max is None else max(t_max, ts)
                if row.get("key") == "mrac.pitch.e":
                    try:
                        pitch_e.append(float(row["value"]))
                    except Exception:
                        pass
                if row.get("key") == "pid.locx.FB":
                    pass
        dur = (t_max - t_min) if (t_min is not None and t_max is not None) else 0.0
        pe_min = min(pitch_e) if pitch_e else None
        pe_max = max(pitch_e) if pitch_e else None
        return {
            "duration_s": dur,
            "mrac_pitch_e_min": pe_min,
            "mrac_pitch_e_max": pe_max,
            "rows": sum(1 for _ in open(filename, encoding="utf-8")) - 1,
        }
