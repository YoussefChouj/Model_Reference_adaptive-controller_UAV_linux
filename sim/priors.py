"""Dimensionless adaptive-prior objects (ADR-0014 D1-D4, ADR-0013 D5).

A *prior* is a learned adaptive weight together with the provenance needed
to redeploy it on a different plant. ADR-0014 D1 establishes the canonical
stored form as the dimensionless object ``Theta_tilde = K * Theta``; the raw
``Theta`` and the identifying triple ``(K, p, T)`` of the source plant are
stored **alongside** it, never in place of it. Deployment on any target is
``Theta = Theta_tilde / K_target`` (D3 per-slot scales aside).

The conversion API is intentionally explicit. A prior must refuse to convert
to a target plant without an explicit ``convert_to(target_plant_tag)`` call:
cross-plant application without conversion is the failure mode ADR-0014 D7
identifies as the thesis headline result, and silently allowing it would
defeat the experiment.

The ``RegressorVariant`` registry (D4) keeps the regressor design open: the
current six-slot regressor is the pinned firmware baseline, and other
variants are sim-only until promoted with their own parity test.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import numpy as np

# Plant-tag tuple: (K, p, T). p may be None for the pure integrator (yaw);
# T is in seconds; K is the lumped input->output gain.
PlantTag = Tuple[float, object, float]


def _validate_plant_tag(tag) -> None:
    if not isinstance(tag, tuple) or len(tag) != 3:
        raise ValueError(
            f"plant_tag must be a (K, p, T) tuple, got {tag!r}"
        )
    K, _p, T = tag
    if not isinstance(K, (int, float)) or K <= 0.0:
        raise ValueError(f"plant_tag K must be a positive scalar, got {K!r}")
    if T is not None and (not isinstance(T, (int, float)) or T < 0.0):
        raise ValueError(f"plant_tag T must be a non-negative scalar, got {T!r}")
    if _p is not None and (not isinstance(_p, (int, float)) or _p <= 0.0):
        raise ValueError(f"plant_tag p must be positive or None, got {_p!r}")


@dataclass(frozen=True)
class RegressorVariant:
    """A declared regressor variant (ADR-0014 D4).

    The current six-slot regressor is the pinned firmware baseline and is
    always available as ``RegressorVariant.DEFAULT``. Other variants can be
    registered through ``RegressorVariant.register``; their outputs are
    sim-only until promoted with a parity test against firmware.
    """
    name: str
    num_basis: int

    def __post_init__(self) -> None:
        if self.name in _VARIANT_REGISTRY:
            raise ValueError(
                f"RegressorVariant {self.name!r} already registered"
            )
        _VARIANT_REGISTRY[self.name] = self

    @classmethod
    def register(cls, name: str, num_basis: int) -> "RegressorVariant":
        """Create and register a new variant. Returns the new variant."""
        return cls(name=name, num_basis=num_basis)

    @classmethod
    def get(cls, name: str) -> "RegressorVariant":
        if name not in _VARIANT_REGISTRY:
            raise KeyError(
                f"unknown RegressorVariant {name!r}; "
                f"registered: {sorted(_VARIANT_REGISTRY)}"
            )
        return _VARIANT_REGISTRY[name]

    @classmethod
    def names(cls) -> list[str]:
        return sorted(_VARIANT_REGISTRY)


# Module-level registry of named RegressorVariant instances. Keyed by
# ``name``; populated by construction. Kept at module scope (not as a
# dataclass field) to avoid frozen-dataclass instance-level state issues
# and to give the registry a single, easy-to-clear location for tests.
_VARIANT_REGISTRY: dict[str, "RegressorVariant"] = {}


# Pinned firmware baseline — six-slot structured regressor (mrac.c:65-91).
# This is the golden-vector target of tests/test_regressor.py and must
# remain bit-identical to the firmware.
RegressorVariant.DEFAULT = RegressorVariant(name="default", num_basis=6)


@dataclass(frozen=True)
class Prior:
    """Dimensionless adaptive prior (ADR-0014 D1, D4; ADR-0013 D5).

    ``theta_tilde`` is the dimensionless object ``K * Theta`` learned on the
    source plant identified by ``plant_tag``. Deployment on the source
    plant (no rescaling) recovers ``Theta = theta_tilde / K_source``.

    Cross-plant application requires an explicit ``convert_to(target_tag)``
    call which returns a new Prior scaled by ``K_source / K_target``.
    """
    theta_tilde: np.ndarray
    plant_tag: PlantTag
    regressor_variant_id: str
    source_scenario: str

    def __post_init__(self) -> None:
        # theta_tilde must be a 1-D float array
        arr = np.asarray(self.theta_tilde, dtype=float)
        if arr.ndim != 1:
            raise ValueError(
                f"theta_tilde must be 1-D, got shape {arr.shape}"
            )
        if not np.all(np.isfinite(arr)):
            raise ValueError("theta_tilde contains non-finite values")
        object.__setattr__(self, "theta_tilde", arr)
        _validate_plant_tag(self.plant_tag)
        # Variant must be registered; pin provenance so a prior can never
        # be silently applied under the wrong variant (ADR-0014 D4).
        try:
            variant = RegressorVariant.get(self.regressor_variant_id)
        except KeyError as exc:
            raise ValueError(
                f"unknown regressor variant {self.regressor_variant_id!r}; "
                f"registered: {RegressorVariant.names()}"
            ) from exc
        if arr.shape[0] != variant.num_basis:
            raise ValueError(
                f"theta_tilde length {arr.shape[0]} does not match "
                f"variant {self.regressor_variant_id!r} num_basis="
                f"{variant.num_basis}"
            )
        if not isinstance(self.source_scenario, str) or not self.source_scenario:
            raise ValueError(
                "source_scenario must be a non-empty string"
            )

    @property
    def K(self) -> float:
        return self.plant_tag[0]

    @property
    def p(self):
        return self.plant_tag[1]

    @property
    def T(self) -> float:
        return self.plant_tag[2]

    def to_raw(self) -> np.ndarray:
        """Recover raw ``Theta`` on the source plant: ``Theta = theta_tilde / K_source``."""
        return self.theta_tilde / self.K

    def convert_to(self, target_plant_tag: PlantTag,
                   target_variant_id: str | None = None) -> "Prior":
        """Return a new Prior rescaled for the target plant.

        The dimensionless ``theta_tilde`` is preserved; deployment on the
        target recovers ``Theta_target = theta_tilde / K_target``. The
        recorded ``plant_tag`` switches to the target so the new Prior is
        tagged for the plant it is now valid on.

        If ``target_variant_id`` is given it must equal the current
        variant — cross-variant application is forbidden by ADR-0014 D4.
        ``target_variant_id=None`` preserves the current variant.
        """
        _validate_plant_tag(target_plant_tag)
        new_variant = target_variant_id or self.regressor_variant_id
        if new_variant != self.regressor_variant_id:
            raise ValueError(
                f"cross-variant prior transfer is forbidden (ADR-0014 D4): "
                f"source {self.regressor_variant_id!r}, "
                f"target {target_variant_id!r}"
            )
        return Prior(
            theta_tilde=self.theta_tilde.copy(),
            plant_tag=target_plant_tag,
            regressor_variant_id=self.regressor_variant_id,
            source_scenario=self.source_scenario,
        )

    def with_scenario(self, scenario: str) -> "Prior":
        """Return a new Prior with ``source_scenario`` overridden.

        Used by the prior factory (ADR-0013 D8) to stamp the scenario
        identity onto a converged ``Theta`` after a deterministic run.
        """
        return Prior(
            theta_tilde=self.theta_tilde.copy(),
            plant_tag=self.plant_tag,
            regressor_variant_id=self.regressor_variant_id,
            source_scenario=scenario,
        )