"""Core data loader for flight telemetry CSV files.

Handles the flat t_s,frame,key,value format and provides utilities
for signal extraction and grouping.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import numpy as np


def load_flight_csv(csv_path: str | Path) -> Dict[str, Tuple[List[float], List[float]]]:
    """Load flight telemetry from CSV.

    Args:
        csv_path: Path to the flight CSV file.

    Returns:
        Dictionary mapping keys to (time, value) tuples.
    """
    data: Dict[str, Tuple[List[float], List[float]]] = {}

    with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                t = float(row["t_s"])
                k = row["key"].strip()
                v = float(row["value"])
            except (ValueError, KeyError):
                continue

            if k not in data:
                data[k] = ([], [])
            data[k][0].append(t)
            data[k][1].append(v)

    return data


def get_signal(
    data: Dict[str, Tuple[List[float], List[float]]],
    key: str,
    default: Optional[Tuple[List[float], List[float]]] = None
) -> Tuple[Optional[List[float]], Optional[List[float]]]:
    """Get a signal by key with fallback support.

    Args:
        data: Loaded flight data.
        key: Signal key to look up.
        default: Default value if key not found.

    Returns:
        (time, values) tuple or default.
    """
    if key in data:
        return data[key]
    
    # Try underscore variant for compatibility
    alt_key = key.replace(".", "_")
    if alt_key in data:
        return data[alt_key]
    
    return default if default is not None else (None, None)


def detect_frame_types(
    data: Dict[str, Tuple[List[float], List[float]]]
) -> Dict[str, List[str]]:
    """Detect which frame types (A, B, etc.) are present in the data.

    Args:
        data: Loaded flight data.

    Returns:
        Dictionary mapping frame letters to list of keys in that frame.
    """
    # This is a placeholder - frames are encoded in the CSV, not in keys
    # For now, return known frame structure
    return {
        "A": [k for k in data.keys() if k.startswith("mrac.") or k.startswith("status.")],
        "B": [k for k in data.keys() if k.startswith("pid.") or k.startswith("path.")],
    }


def extract_signal_groups(
    data: Dict[str, Tuple[List[float], List[float]]]
) -> Dict[str, Dict[str, List[str]]]:
    """Extract hierarchical signal groups from keys.

    Args:
        data: Loaded flight data.

    Returns:
        Nested dictionary of signal groups: groups[system][subsystem] = [keys]
    """
    groups: Dict[str, Dict[str, List[str]]] = {}

    for key in data.keys():
        parts = key.split(".")
        if len(parts) >= 2:
            system = parts[0]
            subsystem = parts[1] if len(parts) > 1 else "_root"

            if system not in groups:
                groups[system] = {}
            if subsystem not in groups[system]:
                groups[system][subsystem] = []
            groups[system][subsystem].append(key)

    return groups


def estimate_sample_rate(
    data: Dict[str, Tuple[List[float], List[float]]]
) -> float:
    """Estimate the sample rate from time differences.

    Args:
        data: Loaded flight data.

    Returns:
        Estimated sample rate in Hz.
    """
    # Find the most sampled signal
    max_len = 0
    sample_times = None

    for key, (times, values) in data.items():
        if len(times) > max_len:
            max_len = len(times)
            sample_times = times

    if sample_times is None or len(sample_times) < 2:
        return 0.0

    times = np.array(sample_times)
    dt = np.median(np.diff(times))

    if dt > 0:
        return 1.0 / dt
    return 0.0


def compute_data_quality(
    data: Dict[str, Tuple[List[float], List[float]]]
) -> Dict[str, Any]:
    """Compute data quality metrics.

    Args:
        data: Loaded flight data.

    Returns:
        Dictionary of quality metrics.
    """
    # Expected signals for different systems
    expected_mrac = [
        "mrac.pitch.e", "mrac.pitch.u_ad", "mrac.pitch.u_nom",
        "mrac.roll.e", "mrac.roll.u_ad", "mrac.roll.u_nom",
        "mrac.yaw.e", "mrac.yaw.u_ad", "mrac.yaw.u_nom",
        "mrac.z.e", "mrac.z.u_ad", "mrac.z.u_nom",
    ]

    expected_pid = [
        "pid.pitch.Des", "pid.pitch.FB", "pid.pitch.U",
        "pid.roll.Des", "pid.roll.FB", "pid.roll.U",
        "pid.gyrox.Des", "pid.gyrox.FB", "pid.gyrox.U",
        "pid.locx.Des", "pid.locx.FB",
        "pid.z_pos.Des", "pid.z_pos.FB",
    ]

    present = list(data.keys())
    missing_mrac = [k for k in expected_mrac if k not in present and k.replace(".", "_") not in present]
    missing_pid = [k for k in expected_pid if k not in present and k.replace(".", "_") not in present]

    # Compute time coverage
    all_times = set()
    for times, _ in data.values():
        all_times.update(times)

    time_span = 0.0
    if all_times:
        time_list = sorted(all_times)
        time_span = time_list[-1] - time_list[0] if len(time_list) > 1 else 0.0

    # Find gaps
    max_gap = 0.0
    if len(all_times) > 1:
        sorted_times = sorted(all_times)
        gaps = np.diff(sorted_times)
        if len(gaps) > 0:
            max_gap = float(np.max(gaps))

    return {
        "total_signals": len(data),
        "total_samples": sum(len(v) for _, v in data.values()),
        "time_span_s": time_span,
        "missing_mrac_signals": len(missing_mrac),
        "missing_pid_signals": len(missing_pid),
        "missing_signals": missing_mrac + missing_pid,
        "max_gap_s": max_gap,
    }
