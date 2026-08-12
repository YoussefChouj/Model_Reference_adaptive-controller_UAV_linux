"""spec-11 one-factor sensitivity sweep.

From sim/experiments.py (sim-arch-03 extract).

Vary e_deadzone, What_limit, and Gamma independently; report RMSE ranking.
prior-00b indicated e_deadzone dominates; this sweep confirms or refutes it.
"""
from __future__ import annotations

from dataclasses import replace

from sim.adaptive_law import AdaptiveFlags, AxisAdaptiveConfig
from sim.run import run
from sim.sweep_runner import SweepResult, SweepRow, write_sweep_artifacts


def run_sweep(axis: str, scenario_factory, outdir: str | None = None) -> SweepResult:
    """Vary e_deadzone, What_limit, and Gamma independently."""
    dep_cfg = AxisAdaptiveConfig.for_deployment(axis)
    sc = scenario_factory()
    flags = AdaptiveFlags()

    def _run(label, cfg):
        r = run(replace(sc, name=f"{sc.name}__{label}"),
                config=cfg, flags=flags, write_artifacts=True)
        return r["metrics"]["rmse_track"], r.get("outdir")

    dz_vals = [0.005, 0.01, 0.02, 0.05, 0.10]
    wl_scales = [0.5, 1.0, 2.0, 5.0]
    g_scales = [0.5, 1.0, 2.0, 5.0]

    result = SweepResult(family="sensitivity", scenario=sc.name, axis=axis)

    for dz in dz_vals:
        cfg = replace(dep_cfg, e_deadzone=dz)
        rmse, outdir_row = _run(f"dz{dz}", cfg)
        result.rows.append(SweepRow(label=f"deadzone={dz}", metrics={"rmse_track": rmse},
                                    outdir=outdir_row))

    n_wl = len(result.rows)
    for s in wl_scales:
        wlim = [v * s for v in dep_cfg.What_limit]
        cfg = replace(dep_cfg, What_limit=wlim)
        rmse, outdir_row = _run(f"wl{s}", cfg)
        result.rows.append(SweepRow(label=f"wlimit_scale={s}", metrics={"rmse_track": rmse},
                                    outdir=outdir_row))

    n_gamma = len(result.rows)
    for s in g_scales:
        gamma = [v * s for v in dep_cfg.gamma]
        cfg = replace(dep_cfg, gamma=gamma)
        rmse, outdir_row = _run(f"gamma{s}", cfg)
        result.rows.append(SweepRow(label=f"gamma_scale={s}", metrics={"rmse_track": rmse},
                                    outdir=outdir_row))

    # Ranking by spread (max - min RMSE) within each factor group
    dz_rmses  = [result.rows[i].metrics["rmse_track"] for i in range(0, n_wl)]
    wl_rmses  = [result.rows[i].metrics["rmse_track"] for i in range(n_wl, n_gamma)]
    gamma_rmses = [result.rows[i].metrics["rmse_track"] for i in range(n_gamma, len(result.rows))]

    dz_spread  = max(dz_rmses)  - min(dz_rmses)
    wl_spread  = max(wl_rmses)  - min(wl_rmses)
    g_spread   = max(gamma_rmses) - min(gamma_rmses)

    ranking = sorted([("e_deadzone", dz_spread),
                     ("What_limit", wl_spread),
                     ("Gamma", g_spread)],
                    key=lambda x: x[1], reverse=True)

    print(f"\n# spec-11: sensitivity sweep -- {sc.name} (axis={axis})")
    print(f"# Sensitivity ranking (spread = max - min RMSE):")
    for name, spread in ranking:
        print(f"  {name:15s}  spread = {spread:+.4g}")
    print(f"# Dominant factor: {ranking[0][0]}")

    if outdir:
        write_sweep_artifacts(outdir, result)
    return result
