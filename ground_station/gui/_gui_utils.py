from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List


def simple_yaml_kv_load(path: Path) -> Dict[str, Any]:
    """Load a flat key: value YAML file (no nesting). Returns {} on missing/error."""
    if not path.exists():
        return {}
    out: Dict[str, Any] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if re.fullmatch(r"-?\d+", value):
            out[key] = int(value)
        elif re.fullmatch(r"-?\d+\.\d*", value):
            out[key] = float(value)
        else:
            out[key] = value
    return out


def simple_yaml_kv_write(path: Path, cfg: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    preferred_order = [
        "serial_port",
        "baud_rate",
        "vofa_host",
        "vofa_port",
        "vofa_port_a",
        "vofa_port_b",
        "vofa_executable",
    ]
    keys = list(cfg.keys())
    keys.sort(key=lambda k: preferred_order.index(k) if k in preferred_order else len(preferred_order))
    lines: List[str] = []
    for k in keys:
        v = cfg[k]
        lines.append(f"{k}: {v}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
