"""spec-11 paired learn/deploy experiment.

From sim/experiments.py (sim-arch-03 extract).

Learn under the learning envelope, replay under the deployment envelope with the
learned weights seeded via ``theta_seed`` (sim-arch-03: AdaptiveLaw now reads
this field). Report the gap: does the deployment envelope reach the weights
the learning envelope finds?

Both answers are decisive — zero gap means priors buy nothing.
"""
from __future__ import annotations

from dataclasses import replace

from sim.adaptive_law import AdaptiveFlags, AxisAdaptiveConfig
from sim.run import run
from sim.sweep_runner import SweepResult, SweepRow, write_sweep_artifacts


def run_sweep(axis: str, scenario_factory, outdir: str | None = None) -> SweepResult:
    """Run the paired learn/deploy experiment; write structured artifacts."""
    lrng_cfg = AxisAdaptiveConfig.for_learning(axis)
    dep_cfg = AxisAdaptiveConfig.for_deployment(axis)

    sc_learn = replace(scenario_factory(), name=f"{scenario_factory().name}__learn")
    res_learn = run(sc_learn, config=lrng_cfg, flags=AdaptiveFlags(),
                    write_artifacts=True)
    theta_learn = lrng_cfg.theta_final
    norm_learn = float(res_learn["metrics"]["final_weight_norm"])

    # Phase 2: fresh deployment run
    sc_deploy = replace(scenario_factory(), name=f"{scenario_factory().name}__deploy")
    res_deploy = run(sc_deploy, config=dep_cfg, flags=AdaptiveFlags(),
                     write_artifacts=True)
    norm_deploy = float(res_deploy["metrics"]["final_weight_norm"])

    # Phase 3: deployment with learned weights seeded (sigma_prior=0, attractor off)
    cold_cfg = replace(dep_cfg, theta_seed=theta_learn, sigma_prior=0.0)
    cold_flags = AdaptiveFlags(sigma_prior_on=False)
    sc_cold = replace(scenario_factory(),
                      name=f"{scenario_factory().name}__deploy_thetaLearn")
    res_cold = run(sc_cold, config=cold_cfg, flags=cold_flags,
                   write_artifacts=True)
    norm_cold = float(res_cold["metrics"]["final_weight_norm"])

    gap_rmse = res_learn["metrics"]["rmse_track"] - res_deploy["metrics"]["rmse_track"]

    result = SweepResult(
        family="paired_envelope",
        scenario=scenario_factory().name,
        axis=axis,
        metadata={"gap_rmse": gap_rmse},
        rows=[
            SweepRow("learning_envelope",
                     {k: res_learn["metrics"].get(k) for k in ["rmse_track", "final_weight_norm"]},
                     res_learn.get("outdir")),
            SweepRow("deployment_envelope",
                     {k: res_deploy["metrics"].get(k) for k in ["rmse_track", "final_weight_norm"]},
                     res_deploy.get("outdir")),
            SweepRow("deployment_thetaLearn",
                     {k: res_cold["metrics"].get(k) for k in ["rmse_track", "final_weight_norm"]},
                     res_cold.get("outdir")),
        ],
    )

    # Also print the human-readable summary (spec behaviour preserved)
    print(f"\n# spec-11: paired learn/deploy -- {scenario_factory().name} (axis={axis})")
    print(f"#   Learning envelope final ||Theta|| = {norm_learn:.4g}")
    print(f"#   Deployment envelope final ||Theta|| = {norm_deploy:.4g}")
    print(f"#   Deployment+thetaLearn final ||Theta|| = {norm_cold:.4g}")
    print(f"#   Learning envelope RMSE = {res_learn['metrics']['rmse_track']:.4g}")
    print(f"#   Deployment envelope RMSE = {res_deploy['metrics']['rmse_track']:.4g}")
    print(f"#   RMSE gap (learn - deploy) = {gap_rmse:+.4g}  "
          f"{'[positive: deployment better]' if gap_rmse > 0 else '[negative: learning better]'}")

    if outdir:
        write_sweep_artifacts(outdir, result)
    return result
