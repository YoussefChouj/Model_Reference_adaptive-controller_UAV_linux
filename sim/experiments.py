"""Experiment sweep entry point (sim-arch-03).

``python -m sim.experiments`` runs all five sweep families:
    A: What_lower_limit x deadzone
    B: Lyapunov-Q
    C: CRM vs transport delay
    D: spec-11 paired learn/deploy
    E: spec-11 one-factor sensitivity

Each sweep family is implemented in ``sim/sweeps/``.  See those modules for
documentation and the ``run_sweep`` API.

Structured artifacts are written to ``sweep_results/<ts>/`` via
``sim.sweep_runner.write_sweep_artifacts``.
"""
from __future__ import annotations

import datetime
from pathlib import Path

from sim import scenarios
from sim.sweeps import bias_deadzone, lyapunov_q, crm_delay, paired_envelope, sensitivity


def main() -> None:
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    outdir = Path(f"sim/sweep_results/{ts}")
    outdir.mkdir(parents=True, exist_ok=True)

    builders = {
        "disturbance_roll":    lambda: scenarios.disturbance_rejection("roll"),
        "inertia_offset_roll": lambda: scenarios.inertia_offset("roll", factor=0.6),
    }

    for sname, build in builders.items():
        axis = build().axis
        bias_deadzone.run_sweep(axis, build, outdir=f"{outdir}/bias_deadzone_{sname}")
        lyapunov_q.run_sweep(axis, build, outdir=f"{outdir}/lyapunov_q_{sname}")
        paired_envelope.run_sweep(axis, build, outdir=f"{outdir}/paired_envelope_{sname}")
        sensitivity.run_sweep(axis, build, outdir=f"{outdir}/sensitivity_{sname}")

    crm_delay.run_sweep("roll", outdir=f"{outdir}/crm_delay")


if __name__ == "__main__":
    main()
