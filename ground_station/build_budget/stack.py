"""Per-task stack-high-water-mark threshold logic.

The actual numbers (per-task HWMs in words) are read off the firmware by an
operator-run probe (see :mod:`ground_station.livewatch`); for this gate's
test suite the numbers are injected. The contract:

- Allocations are in **words** to match ``USER/main.c`` (``START_STK_SIZE``, etc.
  are ``uint16_t`` words).
- HWMs are likewise in words.
- A task at HWM ``h`` over an allocation ``a`` is at percentage
  ``100 * h / a``.
- A task above the configured threshold (default 80 %) fails the gate.

The implementer intentionally did not flip the firmware's
``configCHECK_FOR_STACK_OVERFLOW`` flag and rebuild — that is the operator's
work at the bench (per the spec's story 10 + hardware-safety rules). Once the
operator enables the facility and supplies the readings, this module is the
gate.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import csv


@dataclass(frozen=True)
class StackReading:
    """One (task name, HWM in words, allocation in words) measurement."""
    task: str
    hwm_words: int
    alloc_words: int

    @property
    def percent(self) -> float:
        if self.alloc_words <= 0:
            return float("inf")
        return 100.0 * self.hwm_words / self.alloc_words

    def to_dict(self) -> dict:
        return {
            "task": self.task, "hwm_words": self.hwm_words,
            "alloc_words": self.alloc_words, "percent": round(self.percent, 2),
        }


@dataclass(frozen=True)
class StackVerdict:
    ok: bool
    failures: tuple[StackReading, ...]
    readings: tuple[StackReading, ...]
    threshold_pct: float


def evaluate_stack(
    readings: list[StackReading],
    threshold_pct: float = 80.0,
) -> StackVerdict:
    """Apply the per-task threshold. Fail if any task is above ``threshold_pct``."""
    fails = tuple(r for r in readings if r.percent >= threshold_pct)
    return StackVerdict(
        ok=not fails,
        failures=fails,
        readings=tuple(readings),
        threshold_pct=threshold_pct,
    )


def load_readings_csv(path: str | Path) -> list[StackReading]:
    """Load ``task,hwm_words,alloc_words`` rows from a CSV.

    Header row optional — if it parses as ``task,hwm_words,alloc_words`` we
    skip it; otherwise the first row is treated as data.
    """
    out: list[StackReading] = []
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        rows = list(reader)
    if not rows:
        return out
    start = 1 if rows[0] and rows[0][0].lower() == "task" else 0
    for row in rows[start:]:
        if not row or len(row) < 3:
            continue
        out.append(StackReading(task=row[0].strip(),
                                 hwm_words=int(row[1]),
                                 alloc_words=int(row[2])))
    return out
