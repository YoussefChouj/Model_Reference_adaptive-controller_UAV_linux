"""Experiment sweep: two firmware settings that suppress adaptation.

Phase-1 validation surfaced two firmware choices that constrain how much MRAC can learn
(see sim/README.md):
  1. What_lower_limit slot 0 = -What_limit[0] for pitch/roll/yaw (mrac.c:353-355);
     slots 1-5 = 0.0 on ALL axes.  The sim now has the correct parity.
  2. e_deadzone = 0.05 -> a well-tuned baseline pushes |e| into the deadzone
     in ~0.2s and adaptation halts for the rest of the run.

prior-00b established that correcting the bias unlock (item 1) gives a ~2-3% improvement
in disturbance-rejection RMSE but does not dominate — e_deadzone is still the primary
suppressor (a null result on the hypothesis that bias unlock alone is sufficient).

The sweep therefore tests two open questions:
  * Symmetric lower limit (What_lower_limit = -What_limit for ALL slots) vs the
    corrected firmware parity (slot 0 unlocked, slots 1-5 at 0).  This is Sweep A.
  * Deadzone disabled vs enabled (same corrected parity baseline).
  * Both combined.

Sweep A's research question (unlock slots 1-5) remains OPEN — it requires evidence
plus a flight-safety argument, not a default change.

across the two scenarios that exercise different MRAC failure modes:
  * disturbance rejection (positive-rate bias needs negative u_ad) -> tests slot 0
  * inertia offset (gain mismatch) -> tests whether MRAC can track parametric change

Each variant writes its own sim/runs/ folder for inspection.

Run:  python -m sim.experiments
"""
from __future__ import annotations

from dataclasses import replace

from sim import scenarios
from sim.adaptive_law import AdaptiveFlags, AxisAdaptiveConfig
from sim.plant import CANONICAL_MODELS, IdentifiedPlant
from sim.reference_model import ReferenceModel
from sim.run import run


def _variants(axis: str):
    """(label, config, flags) for the 2x2 sweep over lower-limit x deadzone."""
    base = AxisAdaptiveConfig.for_axis(axis)
    sym = replace(base, What_lower_limit=[-v for v in base.What_limit])
    return [
        ("baseline", base, AdaptiveFlags()),                       # firmware parity
        ("symlimit", sym, AdaptiveFlags()),                        # ask 1
        ("nodeadzone", base, AdaptiveFlags(deadzone_on=False)),    # ask 2
        ("both", sym, AdaptiveFlags(deadzone_on=False)),           # 1 + 2
    ]


def _q_variants(axis: str):
    """(label, q1, q2) Lyapunov-Q sweep for the 2nd-order matrix-P law (ADR-0007).

    Q sets the adaptive-gain magnitude. q1 weights the rate-error channel
    (Pe = q1/(2*wn^2)); q1 = wn recovers the old scalar e-gain 1/(2*wn). q2 weights
    the rate-derivative channel (Pedot)."""
    wn = ReferenceModel.for_axis(axis).bw
    return [
        ("Q=I",        1.0,        1.0),    # scipy-calculator default; gentle on e
        ("Q1=wn",      wn,         1.0),    # Pe == old scalar 1/(2*wn)
        ("Q1=10wn",    10.0 * wn,  1.0),    # aggressive rate-error learning
        ("Q2=50",      1.0,        50.0),   # lean on the derivative channel
    ]


def _delayed_step(axis: str, delay_s: float, *, amp_dps: float = 30.0):
    """Nominal-gain rate step on a plant whose total transport delay is set to
    ``delay_s``. Isolates the CRM/delay interaction: the gain is the identified
    nominal (no inertia mismatch), so the only stressor is the delay — exactly the
    margin ADR-0008 says a large L erodes."""
    model = replace(CANONICAL_MODELS[axis], delay=delay_s)
    sc = scenarios.step(axis, amp_dps=amp_dps)
    return replace(sc, name=f"delay_{axis}_{int(round(delay_s * 1000))}ms",
                   description=f"{amp_dps:g} deg/s step, transport delay {delay_s * 1e3:g} ms",
                   plant_factory=lambda dt: IdentifiedPlant(dt, {axis: model}))


def _crm_delay_sweep(axis: str = "roll"):
    """Sweep C: quantify the Lavretsky CRM robustness tradeoff (ADR-0008).

    For each CRM gain l1, ramp the plant transport delay until the closed loop
    loses stability and report the *critical delay* — the margin. A larger l1 that
    buys a smaller critical delay is the tradeoff made concrete. We flag a run as
    degraded before hard divergence using overshoot / error growth, since the loop
    rings violently well before max|x| trips the 1e3 ``stable`` guard."""
    l1_vals = [0.0, 20.0, 40.0, 80.0]
    delays_ms = [15, 25, 35, 45, 55, 65, 75, 85, 95, 110, 130, 150]
    base_rmse = run(_delayed_step(axis, 0.015), crm_l1=0.0,
                    write_artifacts=False)["metrics"]["rmse_track"]

    print("\n# Sweep C: CRM robustness vs transport delay (ADR-0008 Lavretsky tradeoff)")
    print(f"#   axis={axis}, nominal gain, baseline rmse@15ms={base_rmse:.4g}")
    print(f"#   DEGRADED = rmse > 3x baseline or overshoot > 50%; UNSTABLE = not metrics.stable")
    header = (f"{'l1':>5}{'delay_ms':>10}{'rmse':>10}{'overshoot%':>12}"
              f"{'zero_x':>8}{'verdict':>10}")
    summary = []
    for l1 in l1_vals:
        print("\n" + header)
        crit = None
        for d_ms in delays_ms:
            res = run(_delayed_step(axis, d_ms / 1000.0), crm_l1=l1,
                      write_artifacts=False)
            m = res["metrics"]
            os_pct = m.get("track_peak_overshoot_pct") or 0.0
            degraded = (m["rmse_track"] > 3.0 * base_rmse) or (os_pct > 50.0)
            unstable = not m["stable"]
            verdict = "UNSTABLE" if unstable else ("DEGRADED" if degraded else "ok")
            print(f"{l1:>5.0f}{d_ms:>10}{m['rmse_track']:>10.4g}{os_pct:>12.4g}"
                  f"{m['robust_err_zero_crossings']:>8}{verdict:>10}")
            if crit is None and (degraded or unstable):
                crit = d_ms
        summary.append((l1, crit))

    print("\n# Critical delay per CRM gain (first DEGRADED/UNSTABLE delay)")
    print(f"{'l1':>5}{'critical_delay_ms':>20}")
    for l1, crit in summary:
        print(f"{l1:>5.0f}{(str(crit) if crit is not None else '>150'):>20}")


def _print(sname, label, res):
    m = res["metrics"]
    print(f"{sname:<22}{label:<12}{m['final_weight_norm']:>12.4g}"
          f"{m['max_weight_norm']:>12.4g}{m['rmse_track']:>10.4g}"
          f"{m['max_abs_err']:>10.4g}  {res['outdir']}")


def main() -> None:
    builders = {
        "disturbance_roll": lambda: scenarios.disturbance_rejection("roll"),
        "inertia_offset_roll": lambda: scenarios.inertia_offset("roll", factor=0.6),
    }
    header = (f"{'scenario':<22}{'variant':<12}{'final||W||':>12}{'max||W||':>12}"
              f"{'rmse':>10}{'maxerr':>10}  outdir")

    print("\n# Sweep A: What_lower_limit x deadzone (firmware quirks)\n" + header)
    for sname, build in builders.items():
        for label, cfg, flags in _variants(build().axis):
            sc = replace(build(), name=f"{build().name}__{label}")
            _print(sname, label, run(sc, config=cfg, flags=flags))

    # Sweep B isolates the Q-gain knob, so use a symmetric lower limit (adaptation can
    # move in both directions) — otherwise the disturbance case is clamped regardless of Q.
    print("\n# Sweep B: Lyapunov-Q knob, 2nd-order matrix-P law (symmetric lower limit)\n"
          + header)
    for sname, build in builders.items():
        base = AxisAdaptiveConfig.for_axis(build().axis)
        sym = replace(base, What_lower_limit=[-v for v in base.What_limit])
        for label, q1, q2 in _q_variants(build().axis):
            sc = replace(build(), name=f"{build().name}__Q_{label}")
            _print(sname, label, run(sc, config=sym, q1=q1, q2=q2))

    _crm_delay_sweep("roll")


if __name__ == "__main__":
    main()
