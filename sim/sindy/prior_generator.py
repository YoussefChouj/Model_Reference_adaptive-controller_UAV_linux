"""Generate Prior objects from SINDy results.

Given a ``SindyResult``, this module maps SINDy-active terms to MRAC Θ slots
and builds Prior objects that seed the adaptive law before the drone flies.

**The key conceptual link:**
SINDy on ``[e, x, xm]`` fits ``d(X)/dt = f(X)``. The identified dynamics
tell us which MRAC basis terms are active for this flight condition:
an active term means the adaptive law needs that regressor component to
model the dynamics. We seed those Θ slots and leave the others zero.

**Slot mapping** (from sim/regressor.py BASIS_DEFAULT):

===  ===

Slot 0 — bias (constant term)
Slot 1 — rate damping: proportional to `x` (angular rate)
Slot 2 — drag: proportional to `x * tanh(x)` (bounded nonlinear)
Slot 3 — cross-coupling: gyroscopic term (axis-dependent, SINDy-external)
Slot 4 — control scaling: proportional to `u_nom`
Slot 5 — reference feedforward: proportional to `xm`

The SINDy library uses ``[e, x, xm]`` as features. Cross-coupling (slot 3)
is not discoverable from single-axis telemetry; it is handled by cross-axis
experiments and excluded from prior seeding.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

from sim.priors import (
    ConvergenceResult,
    Prior,
    PriorFactory,
    PlantTag,
    RegressorVariant,
    TargetConstraints,
    to_dimensionless,
)


@dataclass
class PriorGenerationResult:
    """Outcome of a prior generation call."""
    prior: Prior
    convergence: ConvergenceResult
    source: "PriorSource"
    validation_passed: bool
    validation_notes: str


@dataclass
class PriorSource:
    """Provenance record for a SINDy-derived prior."""
    log_path: str
    manifest_name: str
    elf_sha256: str
    recorded_hz: float
    date: str
    sindy_library: str
    sindy_quality_metrics: dict


def generate_prior(
    sindy_result,
    axis: str,
    plant_tag: PlantTag,
    variant_id: str = "default",
    scenario: str = "sindy_fit",
    quality_threshold: float = 0.3,
) -> PriorGenerationResult:
    """Build a ``Prior`` from a SINDy fit result.

    The SINDy library uses ``[e, x, xm]`` as features. The ``SindyResult.coefs``
    matrix has shape ``(3, n_terms)`` where each row is the coefficients for
    ``d(e)/dt``, ``d(x)/dt``, ``d(xm)/dt`` respectively.

    **Slot mapping from library terms:**

    For ``"match_6basis"`` (polynomial degree 1 on [e, x, xm]):
        ``["1", "e", "x", "xm"]`` → [slot 0, slot 1, slot 2, slot 5]
        Slots 3 and 4 are not in the library.

    For ``"overcomplete"`` (polynomial degree 3 on [e, x, xm]):
        Terms beyond ``["1", "e", "x", "xm"]`` (e², ex, x², xm², ...)
        signal new basis functions. The 6 slots with the highest average
        coefficient magnitude are seeded; the rest are zeroed.

    **What "active" means:**
    A term is active if its average absolute coefficient across features
    exceeds the ``active_threshold`` from the SINDy result.

    Parameters
    ----------
    sindy_result
        ``SindyResult`` from ``fitter.fit_sindy``.
    axis
        ``"roll"``, ``"pitch"``, ``"yaw"``, or ``"z"``.
    plant_tag
        ``(K, p, T)`` triple of the source plant.
    variant_id
        ``"default"`` for the 6-basis firmware regressor.
    scenario
        Human-readable identifier, e.g. ``"circle_hover"``.
    quality_threshold
        ``r2_test`` below this → ``well_posed=False``. The prior is still
        generated but refused by ``PriorFactory`` until a better-quality
        flight segment is used.

    Returns
    -------
    PriorGenerationResult
    """
    variant = RegressorVariant.get(variant_id)
    quality = sindy_result.quality_metrics
    r2_test = quality.get("r2_test", 0.0)
    coefs = sindy_result.coefs

    if coefs.size == 0:
        raise ValueError("SindyResult has empty coefs array")

    # Average absolute coefficient magnitude across features.
    avg_mag = np.mean(np.abs(coefs), axis=0)  # shape (n_terms,)
    n_basis = variant.num_basis  # 6

    # Threshold: only terms well above numerical noise.
    threshold = sindy_result.quality_metrics.get("active_threshold", 0.01)

    if sindy_result.library_id == "match_6basis":
        # 4-term library: ["1", "e", "x", "xm"]
        # Map to slots: [0, 1, 2, 5]
        slot_map = {0: 0, 1: 1, 2: 2, 3: 5}  # term_idx → slot
        theta_seed = np.zeros(n_basis, dtype=float)
        for term_idx, slot in slot_map.items():
            if term_idx < len(avg_mag) and avg_mag[term_idx] > threshold:
                theta_seed[slot] = float(avg_mag[term_idx])

    else:
        # overcomplete or linear: select the top-6 terms by average magnitude.
        # This works for any library.
        sorted_indices = np.argsort(avg_mag)[::-1]  # descending
        theta_seed = np.zeros(n_basis, dtype=float)
        for rank, term_idx in enumerate(sorted_indices[:n_basis]):
            if avg_mag[term_idx] > threshold:
                theta_seed[rank] = float(avg_mag[term_idx])

    # Convert to dimensionless.
    theta_tilde = to_dimensionless(theta_seed, plant_tag, variant)

    # Convergence record.
    convergence = ConvergenceResult(
        weight_drift=float(np.std(theta_tilde)),
        drive_rms=float(np.mean(np.abs(coefs))),
        final_norm=float(np.linalg.norm(theta_tilde)),
        max_norm=float(np.linalg.norm(theta_tilde)),
        well_posed=(r2_test >= quality_threshold),
    )

    factory = PriorFactory(plant_tag, variant_id, scenario)
    prior = factory.build(
        theta_seed,
        convergence,
        constraints=TargetConstraints(),
    )

    return PriorGenerationResult(
        prior=prior,
        convergence=convergence,
        source=PriorSource(
            log_path="",
            manifest_name="",
            elf_sha256="",
            recorded_hz=0.0,
            date="",
            sindy_library=sindy_result.library_id,
            sindy_quality_metrics=quality,
        ),
        validation_passed=False,
        validation_notes="validation deferred to sim layer",
    )


def validate_prior_in_sim(
    prior: Prior,
    scenario_name: str = "sindy_validation",
    sim_duration: float = 10.0,
) -> tuple[bool, str]:
    """Run a short sim to verify the prior produces bounded Θ and zero-tracking error.

    This is the gate before a prior can be used for injection.

    Returns
    -------
    (passed, notes)
    """
    # Deferred: requires sim/run.py infrastructure.
    # Implemented as a follow-on task.
    return False, "validation not yet implemented; implement using sim/run.py"


def save_prior(
    result: PriorGenerationResult,
    out_dir: str | Path = "priors",
) -> Path:
    """Write the prior to a JSON file.

    Filename: ``<out_dir>/<scenario>.json``
    """
    import json

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    prior = result.prior
    scenario = prior.source_scenario

    record = {
        "scenario": scenario,
        "axis": "unknown",  # caller should fill this
        "plant_tag": list(prior.plant_tag),
        "variant_id": prior.regressor_variant_id,
        "theta_tilde": prior.theta_tilde.tolist(),
        "convergence": {
            "weight_drift": result.convergence.weight_drift,
            "drive_rms": result.convergence.drive_rms,
            "final_norm": result.convergence.final_norm,
            "max_norm": result.convergence.max_norm,
            "well_posed": result.convergence.well_posed,
        },
        "source": {
            "log_path": result.source.log_path,
            "manifest_name": result.source.manifest_name,
            "elf_sha256": result.source.elf_sha256,
            "recorded_hz": result.source.recorded_hz,
            "date": result.source.date,
            "sindy_library": result.source.sindy_library,
            "sindy_quality": result.source.sindy_quality_metrics,
        },
        "validation": {
            "passed": result.validation_passed,
            "notes": result.validation_notes,
        },
    }

    safe_scenario = "".join(c if c.isalnum() else "_" for c in scenario)
    path = out_dir / f"{safe_scenario}.json"
    n = 1
    while path.exists():
        path = out_dir / f"{safe_scenario}_{n}.json"
        n += 1

    path.write_text(json.dumps(record, indent=2, sort_keys=True))
    return path
