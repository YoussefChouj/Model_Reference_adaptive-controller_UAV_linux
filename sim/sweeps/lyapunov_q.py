"""Sweep B: Lyapunov-Q (ADR-0007 2nd-order matrix-P law).

From sim/experiments.py (sim-arch-03 extract).

Q sets the adaptive-gain magnitude. q1 weights the rate-error channel
(Pe = q1/(2*wn^2)); q1 = wn recovers the old scalar e-gain 1/(2*wn). q2 weights
the rate-derivative channel (Pedot).
"""
from __future__ import annotations

from dataclasses import replace

from sim import scenarios
from sim.adaptive_law import AdaptiveFlags, AxisAdaptiveConfig
from sim.reference_model import ReferenceModel
from sim.run import run
from sim.sweep_runner import SweepResult, SweepRow, write_sweep_artifacts


def _q_variants(axis: str):
    wn = ReferenceModel.for_axis(axis).bw
    return [
        ("Q=I",     1.0,       1.0),
        ("Q1=wn",   wn,        1.0),
        ("Q1=10wn", 10.0 * wn, 1.0),
        ("Q2=50",   1.0,       50.0),
    ]


def run_sweep(axis: str, scenario_factory, outdir: str | None = None) -> SweepResult:
    """Run Q-gain sweep with symmetric lower limit (adaptation can move both ways)."""
    sc = scenario_factory()
    base = AxisAdaptiveConfig.for_axis(axis)
    sym = replace(base, What_lower_limit=[-v for v in base.What_limit])
    result = SweepResult(family="lyapunov_q", scenario=sc.name, axis=axis)
    for label, q1, q2 in _q_variants(axis):
        sc_var = replace(sc, name=f"{sc.name}__Q_{label}")
        res = run(sc_var, config=sym, q1=q1, q2=q2, write_artifacts=True)
        result.rows.append(SweepRow(
            label=label,
            metrics=res["metrics"],
            outdir=res.get("outdir"),
        ))
    if outdir:
        write_sweep_artifacts(outdir, result)
    return result
