"""prior-06 injection-channel sweep: 8-cell matrix + sigma_prior sweep + mismatched-prior test.

Three orthogonal channels (ADR-0013 D4-D7):
  V (value)  -- sigma_prior attractor in AdaptiveLaw; Theta_prior set + sigma_prior > 0
  A (authority) -- feedforward Theta_prior.T @ Phi in ControlLoop via PriorInjection
  E (envelope)  -- scenario_envelope="learning" (widened Gamma/What_limit/e_deadzone)

Sweep A: 8-cell (V × A × E) full-factorial on one scenario.
Sweep B: sigma_prior sweep 0→10 with value channel on.
Sweep C: mismatched-prior damage — learn under one scenario, deploy under another.
  This is the precursor of the thesis headline result (ADR-0014 D7): a confidently
  wrong prior is worse than no prior, and the gap must be characterised.
"""
from __future__ import annotations

from dataclasses import replace
from itertools import product

import numpy as np

from sim.adaptive_law import AdaptiveFlags, AxisAdaptiveConfig
from sim.priors import ConvergenceResult, PriorFactory, to_dimensionless
from sim.regressor import RegressorVariant
from sim.run import run


def _build_prior_from_run(res: dict, factory: PriorFactory) -> "Prior | None":
    """Extract a converged Prior from a run result, or None if not well-posed."""
    from sim.priors import Prior
    conv_dict = res.get("convergence", {})
    if not conv_dict.get("well_posed", False):
        return None
    try:
        conv = ConvergenceResult(
            weight_drift=conv_dict["weight_drift"],
            drive_rms=conv_dict["drive_rms"],
            final_norm=conv_dict["final_norm"],
            max_norm=conv_dict["max_norm"],
            well_posed=True,
        )
        prior = factory.build(res["theta"][-1], conv)
        return prior
    except (KeyError, ValueError):
        return None


def _deploy_cell(scenario_factory, label: str, *,
                 value_on: bool, authority_on: bool, envelope_on: bool,
                 prior: "Prior | None" = None,
                 sigma_prior: float = 0.5,
                 axis: str = "roll",
                 write_artifacts: bool = False) -> dict:
    """Run one cell of the 8-cell matrix or mismatched-prior sweep.

    ``prior`` is a dimensionless Prior object. When provided, ``run()`` re-dimensionalises
    it using the run's own plant_tag and wires the resulting ``theta_prior`` into both
    the value channel (AdaptiveLaw ``sigma_prior`` attractor) and the authority channel
    (PriorInjection feedforward ``Theta_prior.T @ Phi``).

    When ``prior`` is None, ``sigma_prior`` and ``feedforward_on`` are used directly
    (no re-dimensionalisation — used for the baseline / all-off cell).
    """
    from sim.priors import from_dimensionless, to_dimensionless, Prior

    sc = scenario_factory()
    env = "learning" if envelope_on else "deployment"
    effective_sigma = sigma_prior if value_on else 0.0

    if prior is not None:
        # Re-dimensionalise the dimensionless prior for the target plant (self-deployment)
        target_tag = prior.plant_tag
        variant = RegressorVariant.get(prior.regressor_variant_id)
        theta_prior_raw = from_dimensionless(prior.theta_tilde, target_tag, variant)
        # Re-package as a Prior on the current plant so run() can route it correctly
        theta_tilde_local = to_dimensionless(theta_prior_raw, target_tag, variant)
        local_prior = Prior(
            theta_tilde=theta_tilde_local,
            plant_tag=target_tag,
            regressor_variant_id=prior.regressor_variant_id,
            source_scenario=sc.name,
        )
        res = run(sc,
                  prior=local_prior,
                  scenario_envelope=env,
                  sigma_prior=effective_sigma,
                  feedforward_on=authority_on,
                  feedforward_ramp_s=0.5,
                  feedforward_max_abs=2.0,
                  write_artifacts=write_artifacts)
    else:
        # No prior — use sigma_prior/feedforward_on as bare scalars (no re-dimensionalisation)
        res = run(sc,
                  scenario_envelope=env,
                  sigma_prior=effective_sigma,
                  feedforward_on=authority_on,
                  feedforward_ramp_s=0.5,
                  feedforward_max_abs=2.0,
                  write_artifacts=write_artifacts)

    res["value_on"] = value_on
    res["authority_on"] = authority_on
    res["envelope_on"] = envelope_on
    return res


def run_injection_sweep(axis: str, scenario_factory, outdir: str | None = None,
                        mismatched_scenario_factory=None) -> dict:
    """Full prior-06 injection characterisation.

    Returns a dict with three sub-results:
      matrix_8cell  -- 8× SweepRow with V×A×E combinations
      sigma_sweep    -- sigma_prior values vs RMSE and ||Theta-Theta_prior||
      mismatched     -- cross-scenario prior deployment damage
    """
    from sim.sweep_runner import SweepResult, SweepRow, write_sweep_artifacts

    dep_cfg = AxisAdaptiveConfig.for_deployment(axis)
    lrng_cfg = AxisAdaptiveConfig.for_learning(axis)

    # Learn a prior under learning envelope for the mismatched test
    if mismatched_scenario_factory is not None:
        mismatched_sc = mismatched_scenario_factory()
        lrng_run = run(mismatched_sc,
                       scenario_envelope="learning",
                       write_artifacts=False)
        factory = PriorFactory(
            plant_tag=tuple(lrng_run["plant_tag"]),
            variant_id=lrng_run["regressor_variant_id"],
            source_scenario=mismatched_sc.name,
        )
        mismatch_prior = _build_prior_from_run(lrng_run, factory)
        mismatch_tag = tuple(lrng_run["plant_tag"])
    else:
        mismatch_prior = None
        mismatch_tag = None

    results = {}

    # ------------------------------------------------------------------
    # Sweep A: 8-cell full-factorial matrix
    # ------------------------------------------------------------------
    matrix_result = SweepResult(family="injection_matrix", scenario=scenario_factory().name,
                                 axis=axis)
    dep_cfg_local = AxisAdaptiveConfig.for_deployment(axis)

    for value_on, authority_on, envelope_on in product([False, True], repeat=3):
        # Build prior from a clean learning-envelope run on the same scenario
        clean_run = run(scenario_factory(),
                        scenario_envelope="learning",
                        write_artifacts=False)
        fac = PriorFactory(
            plant_tag=tuple(clean_run["plant_tag"]),
            variant_id=clean_run["regressor_variant_id"],
            source_scenario=clean_run["scenario"],
        )
        prior = _build_prior_from_run(clean_run, fac)

        label = f"V{int(value_on)}A{int(authority_on)}E{int(envelope_on)}"
        sigma_p = 0.5  # moderate sigma_prior for the value channel
        res = _deploy_cell(
            scenario_factory, label,
            value_on=value_on, authority_on=authority_on, envelope_on=envelope_on,
            prior=prior, sigma_prior=sigma_p,
            axis=axis, write_artifacts=False)

        rmse = res["metrics"].get("rmse_track", float("nan"))
        final_norm = float(res["metrics"].get("final_weight_norm", float("nan")))
        cell_result = SweepRow(
            label=label,
            metrics={"rmse_track": rmse, "final_weight_norm": final_norm},
            outdir=res.get("outdir"))
        matrix_result.rows.append(cell_result)

    # Baseline: no prior, no channels
    base_run = run(scenario_factory(), write_artifacts=False)
    baseline_rmse = base_run["metrics"].get("rmse_track", float("nan"))
    matrix_result.rows.append(SweepRow(
        label="baseline_none",
        metrics={"rmse_track": baseline_rmse,
                 "final_weight_norm": float(base_run["metrics"].get("final_weight_norm", 0))},
        outdir=base_run.get("outdir")))

    results["matrix_8cell"] = matrix_result
    results["baseline_rmse"] = baseline_rmse

    # ------------------------------------------------------------------
    # Sweep B: sigma_prior values with value channel on
    # ------------------------------------------------------------------
    sigma_result = SweepResult(family="sigma_prior_sweep", scenario=scenario_factory().name,
                                axis=axis)
    sigma_vals = [0.0, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0]

    # Learn one clean prior once (used for all sigma values)
    clean_run = run(scenario_factory(), scenario_envelope="learning", write_artifacts=False)
    fac = PriorFactory(plant_tag=tuple(clean_run["plant_tag"]),
                       variant_id=clean_run["regressor_variant_id"],
                       source_scenario=clean_run["scenario"])
    prior = _build_prior_from_run(clean_run, fac)

    for sp in sigma_vals:
        label = f"sigma_{sp}"
        res = _deploy_cell(
            scenario_factory, label,
            value_on=True, authority_on=False, envelope_on=False,
            prior=prior, sigma_prior=sp,
            axis=axis, write_artifacts=False)
        rmse = res["metrics"].get("rmse_track", float("nan"))
        final_norm = float(res["metrics"].get("final_weight_norm", float("nan")))
        # Also compute ||Theta - Theta_prior|| at end
        theta_final = res["theta"][-1]
        if prior is not None:
            from sim.priors import from_dimensionless
            variant = RegressorVariant.get(prior.regressor_variant_id)
            tp_raw = from_dimensionless(prior.theta_tilde, prior.plant_tag, variant)
            dist = float(np.linalg.norm(theta_final - tp_raw))
        else:
            dist = float("nan")
        sigma_result.rows.append(SweepRow(
            label=label,
            metrics={"rmse_track": rmse, "final_weight_norm": final_norm,
                     "theta_prior_distance": dist, "sigma_prior": sp},
            outdir=res.get("outdir")))

    results["sigma_sweep"] = sigma_result

    # ------------------------------------------------------------------
    # Sweep C: mismatched-prior damage
    # ------------------------------------------------------------------
    mismatched_result = SweepResult(family="mismatched_prior", scenario=scenario_factory().name,
                                    axis=axis)

    if mismatch_prior is not None and prior is not None:
        # Mismatched: deploy mismatch_prior on the target scenario (primary factory)
        # The mismatch_prior's plant_tag differs from the target's plant_tag,
        # so from_dimensionless produces a mis-scaled theta_prior.
        target_tag = tuple(clean_run["plant_tag"])
        from sim.priors import from_dimensionless
        variant = RegressorVariant.get(mismatch_prior.regressor_variant_id)
        mismatched_tp_raw = from_dimensionless(
            mismatch_prior.theta_tilde, target_tag, variant)

        for value_on, authority_on in product([False, True], repeat=2):
            label = f"mis_V{int(value_on)}A{int(authority_on)}"
            # Build a local Prior on the mismatched prior's plant_tag for self-consistency
            from sim.priors import to_dimensionless, Prior
            theta_tilde_local = to_dimensionless(mismatched_tp_raw, target_tag, variant)
            local_prior = Prior(
                theta_tilde=theta_tilde_local,
                plant_tag=target_tag,
                regressor_variant_id=mismatch_prior.regressor_variant_id,
                source_scenario=mismatch_prior.source_scenario,
            )
            res = _deploy_cell(
                scenario_factory, label,
                value_on=value_on, authority_on=authority_on, envelope_on=False,
                prior=local_prior,
                sigma_prior=0.5,
                axis=axis, write_artifacts=False)
            rmse = res["metrics"].get("rmse_track", float("nan"))
            final_norm = float(res["metrics"].get("final_weight_norm", float("nan")))
            # Damage = RMSE with prior - RMSE without prior
            damage = rmse - baseline_rmse
            mismatched_result.rows.append(SweepRow(
                label=label,
                metrics={"rmse_track": rmse, "final_weight_norm": final_norm,
                         "mismatched_damage": damage},
                outdir=res.get("outdir")))
    else:
        mismatched_result.rows.append(SweepRow(
            label="no_prior",
            metrics={"rmse_track": baseline_rmse, "mismatched_damage": 0.0},
            outdir=None))

    results["mismatched"] = mismatched_result

    # ------------------------------------------------------------------
    # Print human-readable summary
    # ------------------------------------------------------------------
    print(f"\n# prior-06: injection sweep -- {scenario_factory().name} (axis={axis})")
    print(f"# Baseline RMSE (no prior): {baseline_rmse:.4g}")

    print(f"\n# -- 8-cell V×A×E matrix (value × authority × envelope) --")
    print(f"{'Label':<10} {'V':>3} {'A':>3} {'E':>3} {'RMSE':>10}  {'||Theta||':>10}")
    for row in matrix_result.rows:
        v = int(row.label[1]) if len(row.label) > 1 and row.label[0] == "V" else 0
        a = int(row.label[-3]) if "A" in row.label else 0
        e = int(row.label[-1]) if "E" in row.label else 0
        rmse = row.metrics.get("rmse_track", float("nan"))
        fn = row.metrics.get("final_weight_norm", float("nan"))
        print(f"{row.label:<10} {v:>3} {a:>3} {e:>3} {rmse:>10.4g}  {fn:>10.4g}")

    print(f"\n# -- sigma_prior sweep (value channel on) --")
    print(f"{'Label':<20} {'sigma_prior':>12} {'RMSE':>10}  {'||Theta||':>10}  {'dist_to_prior':>14}")
    for row in sigma_result.rows:
        sp = row.metrics.get("sigma_prior", float("nan"))
        rmse = row.metrics.get("rmse_track", float("nan"))
        fn = row.metrics.get("final_weight_norm", float("nan"))
        dist = row.metrics.get("theta_prior_distance", float("nan"))
        print(f"{row.label:<20} {sp:>12.4g} {rmse:>10.4g}  {fn:>10.4g}  {dist:>14.4g}")

    print(f"\n# -- mismatched-prior damage (learn under {mismatched_scenario_factory().name if mismatched_scenario_factory else '?'}, deploy under {scenario_factory().name}) --")
    print(f"{'Label':<15} {'V':>3} {'A':>3} {'RMSE':>10}  {'damage':>10}")
    for row in mismatched_result.rows:
        v = int(row.label[row.label.find("V") + 1]) if "V" in row.label else 0
        a = int(row.label[row.label.find("A") + 1]) if "A" in row.label else 0
        rmse = row.metrics.get("rmse_track", float("nan"))
        dmg = row.metrics.get("mismatched_damage", 0.0)
        print(f"{row.label:<15} {v:>3} {a:>3} {rmse:>10.4g}  {dmg:>+10.4g}")

    # Recommendation
    print(f"\n# -- Recommendation --")
    best_row = min((r for r in matrix_result.rows if r.label != "baseline_none"),
                   key=lambda r: r.metrics.get("rmse_track", float("inf")))
    worst_row = max((r for r in matrix_result.rows if r.label != "baseline_none"),
                    key=lambda r: r.metrics.get("rmse_track", float("-inf")))
    print(f"# Best cell: {best_row.label} RMSE={best_row.metrics.get('rmse_track', 0):.4g}")
    print(f"# Worst cell: {worst_row.label} RMSE={worst_row.metrics.get('rmse_track', 0):.4g}")
    print(f"# Authority-first recommended on-rig: A alone leaves certified law bit-identical")
    print(f"#   and can be killed independently (ADR-0013 D6).")

    if outdir:
        write_sweep_artifacts(outdir, matrix_result)
        # Also write sigma sweep and mismatched as JSON
        import json, datetime
        ts_dir = f"{outdir}_sigma"
        from pathlib import Path
        Path(ts_dir).parent.mkdir(parents=True, exist_ok=True)
        sig_out = Path(outdir) / "sigma_sweep.json"
        mis_out = Path(outdir) / "mismatched.json"
        sig_out.parent.mkdir(parents=True, exist_ok=True)

        def _rows_to_dict(rows):
            return [{"label": r.label, "metrics": r.metrics} for r in rows]

        sig_out.write_text(json.dumps({
            "family": "sigma_prior_sweep", "scenario": scenario_factory().name,
            "axis": axis, "rows": _rows_to_dict(sigma_result.rows),
            "timestamp": datetime.datetime.now().isoformat(),
        }, indent=2))
        mis_out.write_text(json.dumps({
            "family": "mismatched_prior", "scenario": scenario_factory().name,
            "axis": axis, "rows": _rows_to_dict(mismatched_result.rows),
            "timestamp": datetime.datetime.now().isoformat(),
        }, indent=2))

    return results
