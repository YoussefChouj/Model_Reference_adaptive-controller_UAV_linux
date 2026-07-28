"""The checked-in baseline.

The baseline is plain YAML so a ``git diff`` against it shows exactly which
numbers were raised (and the developer is expected to write a one-line reason
in the commit message when they do). The gate never writes this file.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Baseline:
    """The accepted figures; comparing against them is what the gate does.

    Sizes are in bytes. The warning inventory is a frozen set of
    ``(diagnostic identity, text)`` pairs, exactly matching what
    :class:`~ground_station.build_budget.parser.Warning` produces via
    :meth:`Warning.identity`.

    ``stack_threshold_pct`` is the fail threshold for per-task high-water marks,
    expressed as a percentage of the task's allocated stack. Spec calls for a
    starting value of 80; the field lives on the baseline so raising it for a
    specific task is a one-line edit at the same place as raising a memory
    budget.
    """
    code: int
    ro_data: int
    rw_data: int
    zi_data: int
    warning_identities: frozenset[tuple[str, str]]
    stack_threshold_pct: float = 80.0
    note: str = ""
    requirements: tuple[str, ...] = field(default_factory=tuple)


def load_baseline(path: str | Path) -> Baseline:
    """Load a baseline YAML file."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    sizes = raw["sizes"]
    warns_raw = raw.get("warning_identities", [])
    identities = frozenset(
        (tuple(item["identity"]) if isinstance(item, dict) else tuple(item))
        for item in warns_raw
    )
    if not identities:
        # Coerce list-of-[code,text] lists into tuples if YAML returned them
        # as lists (PyYAML sometimes does — depends on the entry shape).
        identities = frozenset(tuple(item) for item in warns_raw)
    return Baseline(
        code=int(sizes["code"]),
        ro_data=int(sizes["ro_data"]),
        rw_data=int(sizes["rw_data"]),
        zi_data=int(sizes["zi_data"]),
        warning_identities=identities,
        stack_threshold_pct=float(raw.get("stack_threshold_pct", 80.0)),
        note=str(raw.get("note", "")),
        requirements=tuple(raw.get("requirements", ())),
    )
