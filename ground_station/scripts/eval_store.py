"""Champion store + cross-run history for flight evaluation.

Stage 2/3 of the analysis pipeline (see CONTEXT.md). Keeps, per path mode, the
best run for each (mode x tuning-config), health-gated, and an append-only
history used by global_analysis.py for cross-run trends.

A run is described by a compact *record* derived from the deep_analysis JSON.
Ranking is by `rank_score` (lower = better); a run with any CRITICAL alert is
ineligible to be champion (health gate).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

LEADERBOARD_N = 5

# Params that define a distinct *tuning-config* for a mode. Translation of the
# whole path (cx/cy) and duration do NOT change the config; shape + gains do.
_CONFIG_PARAM_KEYS = (
    "amplitude_m", "radius_m", "omega_rad_s", "freq_Hz", "axis", "shape",
    "waypoint_spacing_m", "cz", "target_z_m",
)
_CONFIG_FW_KEYS = ("gamma", "wlim", "sigma")


def champions_dir(gs_root: Path) -> Path:
    return gs_root / "champions"


def config_hash(record: Dict[str, Any]) -> str:
    """Stable short hash over the ranking-relevant params + gains."""
    params = record.get("params", {}) or {}
    fw = record.get("firmware_params", {}) or {}
    keep: Dict[str, Any] = {k: params[k] for k in _CONFIG_PARAM_KEYS if k in params}
    for k in _CONFIG_FW_KEYS:
        if k in fw:
            keep[f"fw_{k}"] = fw[k]
    blob = json.dumps(keep, sort_keys=True, default=str)
    return hashlib.sha1(blob.encode()).hexdigest()[:10]


def build_record(json_record: Dict[str, Any], mode: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Compact, comparable record from the full deep_analysis JSON."""
    sb = json_record.get("scoreboard", {}) or {}
    geom = json_record.get("path_geometry", {}) or {}
    total_crit = sum(int(v.get("alerts_critical", 0) or 0) for v in sb.values())
    total_warn = sum(int(v.get("alerts_warn", 0) or 0) for v in sb.values())
    rec = {
        "experiment_id": json_record.get("experiment_id"),
        "csv_file": json_record.get("csv_file"),
        "timestamp": json_record.get("timestamp"),
        "mode": mode,
        "duration_s": json_record.get("duration_s"),
        "params": params or {},
        "firmware_params": json_record.get("firmware_params", {}),
        "rank_score": geom.get("rank_score"),
        "rank_metric": geom.get("rank_metric"),
        "planar_rmse_cm": geom.get("planar_rmse_cm"),
        "crosstrack_mean_cm": geom.get("crosstrack_mean_cm"),
        "crosstrack_p95_cm": geom.get("crosstrack_p95_cm"),
        "alongtrack_lag_ms": geom.get("alongtrack_lag_ms"),
        "settling_s": geom.get("settling_s"),
        "alerts_critical": total_crit,
        "alerts_warn": total_warn,
        "health_ok": total_crit == 0,
    }
    rec["config_hash"] = config_hash(rec)
    return rec


def _better(a: Dict[str, Any], b: Optional[Dict[str, Any]]) -> bool:
    """Is record `a` a better champion than incumbent `b`? Lower rank_score wins.
    Health gate: a non-health_ok run never beats anything; nothing beats nothing."""
    if a.get("rank_score") is None or not a.get("health_ok"):
        return False
    if b is None:
        return True
    if b.get("rank_score") is None:
        return True
    return a["rank_score"] < b["rank_score"]


def _read_json(p: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def update_store(gs_root: Path, record: Dict[str, Any]) -> Dict[str, Any]:
    """Append the run to history and update champion + leaderboard for its mode.

    Returns a small delta dict describing what changed (for the per-run narrative).
    """
    mode = record.get("mode") or "unknown"
    mdir = champions_dir(gs_root) / mode
    (mdir / "by_config").mkdir(parents=True, exist_ok=True)
    exp_id = record.get("experiment_id")

    # 1. history (one JSON per line) -- feeds global trends. Re-analysing a log
    # must be idempotent: drop any prior line for this experiment_id before
    # appending, so the run is counted once and "latest vs previous" is honest.
    hist_path = mdir / "history.jsonl"
    prior = [ln for ln in load_history(gs_root, mode)
             if not (exp_id and ln.get("experiment_id") == exp_id)]
    prior.append(record)
    with hist_path.open("w", encoding="utf-8") as f:
        for ln in prior:
            f.write(json.dumps(ln, default=str) + "\n")

    delta: Dict[str, Any] = {"mode": mode, "config_hash": record["config_hash"]}

    # 2. best-per-config. Prune any stale by_config entry that belongs to THIS
    # experiment under a different hash (e.g. a firmware-snapshot change between
    # analyses), or the same run would linger twice on the leaderboard.
    if exp_id:
        for p in (mdir / "by_config").glob("cfg_*.json"):
            if p.name == f"cfg_{record['config_hash']}.json":
                continue
            c = _read_json(p)
            if c and c.get("experiment_id") == exp_id:
                p.unlink()
    cfg_path = mdir / "by_config" / f"cfg_{record['config_hash']}.json"
    prev_cfg = _read_json(cfg_path)
    delta["prev_config_best"] = (prev_cfg or {}).get("rank_score")
    if _better(record, prev_cfg):
        cfg_path.write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
        delta["new_config_champion"] = True
    else:
        delta["new_config_champion"] = False

    # 3. rebuild leaderboard + overall best from all configs
    configs = [_read_json(p) for p in (mdir / "by_config").glob("cfg_*.json")]
    configs = [c for c in configs if c and c.get("rank_score") is not None]
    configs.sort(key=lambda r: r["rank_score"])
    leaderboard = configs[:LEADERBOARD_N]
    (mdir / "leaderboard.json").write_text(
        json.dumps(leaderboard, indent=2, default=str), encoding="utf-8")

    prev_overall = _read_json(mdir / "best_overall.json")
    delta["prev_overall_best"] = (prev_overall or {}).get("rank_score")
    if leaderboard:
        best = leaderboard[0]
        (mdir / "best_overall.json").write_text(
            json.dumps(best, indent=2, default=str), encoding="utf-8")
        delta["overall_best"] = best.get("rank_score")
        delta["is_overall_champion"] = (best.get("experiment_id") == record.get("experiment_id"))
    else:
        delta["overall_best"] = None
        delta["is_overall_champion"] = False

    return delta


def load_history(gs_root: Path, mode: str) -> List[Dict[str, Any]]:
    p = champions_dir(gs_root) / mode / "history.jsonl"
    out: List[Dict[str, Any]] = []
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def all_modes(gs_root: Path) -> List[str]:
    cdir = champions_dir(gs_root)
    if not cdir.exists():
        return []
    return sorted(p.name for p in cdir.iterdir() if p.is_dir())
