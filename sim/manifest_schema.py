"""Single source of truth for the manifest schema (sim-arch-04).

``ManifestPayload`` is the frozen dataclass that every manifest writer
(``write_manifest`` and the run-artifact writer) serialises to JSON.
Bumping ``MANIFEST_SCHEMA_VERSION`` from the implicit "1.0" to "1.1"
documents the addition of the spec-11 / prior-05 fields
(``envelope``, ``regressor_variant_id``, ``theta_tilde_raw``,
``plant_tag``, ``convergence``, ``target_valid``).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

MANIFEST_SCHEMA_VERSION = "1.1"


@dataclass(frozen=True)
class ManifestPayload:
    """Full manifest schema, versioned at ``MANIFEST_SCHEMA_VERSION``.

    Fields with a ``= None`` default are optional.  ``to_dict()`` omits
    every field whose value is ``None`` so the JSON contains only
    meaningful keys.

    ``schema_version`` is always emitted (it is the only field with no
    default), giving downstream consumers a versioned handle on the shape.
    """

    # engine-agnostic reproducibility (existing)
    scenario: dict
    seed: int
    git_sha: str
    sim_sha: str
    urdf_sha: str
    wall_time_s: float
    sim_time_s: float
    exit_reason: str
    machine: Any
    plant_name: str = "identified"
    spawn_z: float | None = None
    # spec-11 / prior-05 additions
    envelope: str | None = None
    regressor_variant_id: str | None = None
    theta_tilde_raw: list[float] | None = None
    plant_tag: tuple | None = None
    convergence: dict | None = None
    target_valid: bool | None = None
    # always emitted — version handle for downstream consumers
    schema_version: str = MANIFEST_SCHEMA_VERSION

    def to_dict(self) -> dict:
        """Return a JSON-ready dict with all ``None`` values omitted."""
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None}

    @classmethod
    def from_run_result(cls, result: dict) -> "ManifestPayload":
        """Build a ``ManifestPayload`` from a ``sim.run.run()`` result dict.

        The ``result`` dict is the canonical in-memory representation of a
        run.  This factory extracts the manifest-relevant fields, converting
        ``plant_tag`` from a list to a tuple and ``convergence`` from a
        ``ConvergenceResult`` frozen-dataclass instance to a plain dict
        (already performed by ``_convergence_to_dict`` in ``sim.run``).
        """
        pt_raw = result.get("plant_tag")
        plant_tag: tuple | None = None
        if pt_raw is not None:
            plant_tag = tuple(pt_raw)

        conv_raw = result.get("convergence")
        # ``convergence`` is already a dict (see ``_convergence_to_dict``).
        convergence: dict | None = None
        if conv_raw is not None:
            convergence = dict(conv_raw)

        # ``scenario`` may arrive as a dict (preferred, from ``scenario_to_dict``),
        # or as a raw Scenario object (legacy).  Accept both.
        scenario_raw = result.get("scenario_dict")
        if scenario_raw is None:
            # Legacy Scenario object: extract the name only.
            scenario_raw = result.get("scenario")
            if hasattr(scenario_raw, "name"):
                scenario_raw = {"name": getattr(scenario_raw, "name", "?")}
            else:
                scenario_raw = {"name": str(scenario_raw) if scenario_raw else "?"}

        return cls(
            scenario=scenario_raw if isinstance(scenario_raw, dict) else {},
            seed=int(result.get("seed", 0)),
            git_sha=str(result.get("git_sha", "")),
            sim_sha=str(result.get("sim_sha", "")),
            urdf_sha=str(result.get("urdf_sha", "")),
            wall_time_s=float(result.get("wall_time_s", 0.0)),
            sim_time_s=float(result.get("sim_time_s", 0.0)),
            exit_reason=str(result.get("exit_reason", "unknown")),
            machine=result.get("machine"),
            plant_name=str(result.get("plant_name", "identified")),
            spawn_z=float(result["spawn_z"])
                if result.get("spawn_z") is not None else None,
            envelope=result.get("envelope"),
            regressor_variant_id=result.get("regressor_variant_id"),
            theta_tilde_raw=result.get("theta_tilde_raw"),
            plant_tag=plant_tag,
            convergence=convergence,
            target_valid=result.get("target_valid"),
        )
