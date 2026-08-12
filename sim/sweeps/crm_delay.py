"""Sweep C: CRM robustness vs transport delay (ADR-0008 Lavretsky tradeoff).

From sim/experiments.py (sim-arch-03 extract).

For each CRM gain l1, ramp the plant transport delay until the closed loop
loses stability and report the *critical delay* — the margin.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Callable

from sim import scenarios
from sim.plant import CANONICAL_MODELS, IdentifiedPlant
from sim.run import run
from sim.sweep_runner import SweepResult, SweepRow, write_sweep_artifacts


def _delayed_step(axis: str, delay_s: float, *, amp_dps: float = 30.0):
    model = replace(CANONICAL_MODELS[axis], delay=delay_s)
    sc = scenarios.step(axis, amp_dps=amp_dps)
    return replace(sc,
                   name=f"delay_{axis}_{int(round(delay_s * 1000))}ms",
                   description=(f"{amp_dps:g} deg/s step, transport delay "
                               f"{delay_s * 1e3:g} ms"),
                   plant_factory=lambda dt: IdentifiedPlant(dt, {axis: model}))


def run_sweep(axis: str = "roll", outdir: str | None = None) -> SweepResult:
    """Sweep CRM l1 vs transport delay; report critical delay per l1."""
    l1_vals = [0.0, 20.0, 40.0, 80.0]
    delays_ms = [15, 25, 35, 45, 55, 65, 75, 85, 95, 110, 130, 150]

    base_rmse = run(_delayed_step(axis, 0.015), crm_l1=0.0,
                     write_artifacts=False)["metrics"]["rmse_track"]

    result = SweepResult(family="crm_delay", scenario="step", axis=axis,
                         metadata={"base_rmse_15ms": base_rmse, "l1_vals": l1_vals,
                                   "delays_ms": delays_ms})

    for l1 in l1_vals:
        for d_ms in delays_ms:
            res = run(_delayed_step(axis, d_ms / 1000.0), crm_l1=l1,
                      write_artifacts=False)
            m = res["metrics"]
            os_pct = m.get("track_peak_overshoot_pct") or 0.0
            degraded = (m["rmse_track"] > 3.0 * base_rmse) or (os_pct > 50.0)
            unstable = not m["stable"]
            verdict = "UNSTABLE" if unstable else ("DEGRADED" if degraded else "ok")
            result.rows.append(SweepRow(
                label=f"l1={l1:.0f}_d={d_ms}ms",
                metrics={
                    "rmse_track": m["rmse_track"],
                    "overshoot_pct": os_pct,
                    "stable": m["stable"],
                    "degraded": degraded,
                    "verdict": verdict,
                },
                outdir=None,
            ))

    if outdir:
        write_sweep_artifacts(outdir, result)
    return result
