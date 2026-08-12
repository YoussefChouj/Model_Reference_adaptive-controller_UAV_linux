"""Sweep A: What_lower_limit x deadzone (firmware quirks).

From sim/experiments.py (sim-arch-03 extract).

prior-00b established that correcting the bias unlock gives ~2-3% improvement in
disturbance-rejection RMSE but does not dominate — e_deadzone is still the primary
suppressor. This sweep quantifies both effects independently.
"""
from __future__ import annotations

from dataclasses import replace

from sim import scenarios
from sim.adaptive_law import AdaptiveFlags, AxisAdaptiveConfig
from sim.run import run
from sim.sweep_runner import SweepResult, SweepRow, write_sweep_artifacts


def _variants(axis: str):
    """(label, config, flags) for the 2x2 sweep over lower-limit x deadzone."""
    base = AxisAdaptiveConfig.for_axis(axis)
    sym = replace(base, What_lower_limit=[-v for v in base.What_limit])
    return [
        ("baseline",   base,                                        AdaptiveFlags()),
        ("symlimit",   sym,                                         AdaptiveFlags()),
        ("nodeadzone", base,                                        AdaptiveFlags(deadzone_on=False)),
        ("both",       sym,                                         AdaptiveFlags(deadzone_on=False)),
    ]


def run_sweep(axis: str, scenario_factory, outdir: str | None = None) -> SweepResult:
    """Run all four variants and write structured artifacts."""
    sc = scenario_factory()
    result = SweepResult(family="bias_deadzone", scenario=sc.name, axis=axis)
    header = None
    for label, cfg, flags in _variants(axis):
        sc_var = replace(sc, name=f"{sc.name}__{label}")
        res = run(sc_var, config=cfg, flags=flags, write_artifacts=True)
        result.rows.append(SweepRow(
            label=label,
            metrics=res["metrics"],
            outdir=res.get("outdir"),
        ))
    if outdir:
        write_sweep_artifacts(outdir, result)
    return result
