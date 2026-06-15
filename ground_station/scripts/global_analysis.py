"""Stage-3 global cross-run analysis.

Scans the per-mode append-only history written by eval_store and produces a
cross-run view in Analysis_plots/_global/:
  - global_report.md  : per-mode leaderboard + latest-vs-previous-vs-champion deltas
  - global_summary.json: machine-readable digest (for the analyze-results skill / AI)
  - trend_<mode>.png  : rank_score over consecutive runs

Run on demand:  python global_analysis.py
The per-run auto path only *appends* to history (cheap); this rebuilds the view.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
import eval_store  # noqa: E402


def _ordered_runs(hist):
    runs = [h for h in hist if h.get("rank_score") is not None]
    runs.sort(key=lambda h: h.get("timestamp") or "")
    # history.jsonl is append-only, so re-analysing a log adds a duplicate line.
    # Collapse by experiment_id keeping the most recent, so "latest vs previous"
    # never compares a run against itself.
    dedup = {}
    for r in runs:
        dedup[r.get("experiment_id") or id(r)] = r
    out = list(dedup.values())
    out.sort(key=lambda h: h.get("timestamp") or "")
    return out


def _trend_plot(mode, runs, out_dir):
    if len(runs) < 2:
        return None
    try:
        scores = [r["rank_score"] for r in runs]
        healthy = [bool(r.get("health_ok")) for r in runs]
        idx = list(range(1, len(runs) + 1))
        fig, ax = plt.subplots(figsize=(9, 4))
        ax.plot(idx, scores, "-", color="gray", lw=1, zorder=1)
        ok = [i for i, h in zip(idx, healthy) if h]
        bad = [i for i, h in zip(idx, healthy) if not h]
        ax.scatter(ok, [scores[i - 1] for i in ok], c="g", label="health OK", zorder=2)
        if bad:
            ax.scatter(bad, [scores[i - 1] for i in bad], c="r", label="CRITICAL (ineligible)", zorder=2)
        best = min(scores)
        ax.axhline(best, color="b", ls="--", alpha=0.5, label=f"best {best:.2f}")
        ax.set_title(f"{mode}: rank score over runs ({runs[0].get('rank_metric','')})")
        ax.set_xlabel("run # (chronological)")
        ax.set_ylabel("rank score (lower = better)")
        ax.grid(True, alpha=0.3); ax.legend()
        p = out_dir / f"trend_{mode}.png"
        fig.savefig(p, bbox_inches="tight"); plt.close(fig)
        return p.name
    except Exception as e:
        print(f"[global] trend plot failed for {mode}: {e}")
        return None


def _fmt(v, p=2):
    return f"{v:.{p}f}" if isinstance(v, (int, float)) else "-"


def main():
    gs_root = _HERE.parent
    out_dir = gs_root.parent / "Analysis_plots" / "_global"
    out_dir.mkdir(parents=True, exist_ok=True)

    modes = eval_store.all_modes(gs_root)
    digest = {"generated": datetime.utcnow().isoformat() + "Z", "modes": {}}

    md = [
        "# Global Cross-Run Analysis",
        "",
        f"_Generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} from "
        f"{len(modes)} path mode(s)._",
        "",
        "## Best per mode",
        "",
        "| Mode | Runs | Best score | Metric | Champion run |",
        "|------|------|-----------|--------|--------------|",
    ]

    per_mode_sections = []
    for mode in modes:
        hist = eval_store.load_history(gs_root, mode)
        runs = _ordered_runs(hist)
        total = len(hist)
        best = eval_store.champions_dir(gs_root) / mode / "best_overall.json"
        best_rec = json.loads(best.read_text(encoding="utf-8")) if best.exists() else None
        lb_path = eval_store.champions_dir(gs_root) / mode / "leaderboard.json"
        lb = json.loads(lb_path.read_text(encoding="utf-8")) if lb_path.exists() else []

        best_score = best_rec.get("rank_score") if best_rec else None
        best_metric = best_rec.get("rank_metric") if best_rec else "-"
        best_run = best_rec.get("experiment_id") if best_rec else "-"
        md.append(f"| {mode} | {total} | {_fmt(best_score)} | {best_metric} | {best_run} |")

        trend_img = _trend_plot(mode, runs, out_dir)

        sec = [f"## {mode}", ""]
        if trend_img:
            sec += [f"![{mode} trend]({trend_img})", ""]

        # latest vs previous vs champion
        if runs:
            latest = runs[-1]
            prev = runs[-2] if len(runs) >= 2 else None
            sec += ["**Latest run**: " + (latest.get("experiment_id") or "?"), ""]
            sec += [
                "| | rank score | crit | warn |",
                "|--|--|--|--|",
                f"| latest | {_fmt(latest.get('rank_score'))} | {latest.get('alerts_critical',0)} | {latest.get('alerts_warn',0)} |",
            ]
            if prev:
                sec.append(f"| previous | {_fmt(prev.get('rank_score'))} | {prev.get('alerts_critical',0)} | {prev.get('alerts_warn',0)} |")
            if best_rec:
                sec.append(f"| champion | {_fmt(best_rec.get('rank_score'))} | {best_rec.get('alerts_critical',0)} | {best_rec.get('alerts_warn',0)} |")
            sec.append("")
            # delta narrative
            if prev and latest.get("rank_score") is not None and prev.get("rank_score") is not None:
                d = latest["rank_score"] - prev["rank_score"]
                verb = "improved" if d < 0 else "regressed"
                sec.append(f"- Latest {verb} vs previous by **{abs(d):.2f}** ({prev['rank_score']:.2f} → {latest['rank_score']:.2f}).")
            if best_rec and latest.get("rank_score") is not None:
                if latest.get("experiment_id") == best_rec.get("experiment_id"):
                    sec.append("- 🏆 Latest run **is the current champion** for this mode.")
                else:
                    gap = latest["rank_score"] - best_rec["rank_score"]
                    sec.append(f"- Off champion by {gap:.2f} (champion {best_rec['rank_score']:.2f}).")
            sec.append("")

        # leaderboard (best per config)
        if lb:
            sec += [
                "### Leaderboard (best per tuning-config)",
                "",
                "| Rank | Score | Metric | Cross-track mean (cm) | Config hash | Run |",
                "|------|-------|--------|----------------------|-------------|-----|",
            ]
            for i, r in enumerate(lb, 1):
                sec.append(
                    f"| {i} | {_fmt(r.get('rank_score'))} | {r.get('rank_metric','-')} "
                    f"| {_fmt(r.get('crosstrack_mean_cm'))} | `{r.get('config_hash','-')}` "
                    f"| {r.get('experiment_id','-')} |")
            sec.append("")

        per_mode_sections.append("\n".join(sec))

        digest["modes"][mode] = {
            "runs": total,
            "best_score": best_score,
            "best_metric": best_metric,
            "champion_run": best_run,
            "leaderboard": [
                {k: r.get(k) for k in ("experiment_id", "rank_score", "rank_metric",
                                       "crosstrack_mean_cm", "config_hash", "alerts_critical")}
                for r in lb
            ],
            "latest_run": runs[-1].get("experiment_id") if runs else None,
            "latest_score": runs[-1].get("rank_score") if runs else None,
        }

    md.append("")
    md.extend(per_mode_sections)

    (out_dir / "global_report.md").write_text("\n".join(md), encoding="utf-8")
    (out_dir / "global_summary.json").write_text(json.dumps(digest, indent=2, default=str), encoding="utf-8")
    print(f"[global] wrote {out_dir / 'global_report.md'}")
    print(f"[global] wrote {out_dir / 'global_summary.json'}")


if __name__ == "__main__":
    main()
