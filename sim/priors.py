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
variants are sim-only until promoted with their own parity test. Each variant
carries its ``basis_declarations`` as data (ADR-0014 D3) so that future
basis functions are declared the same way without hand-derived tables.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

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
class BasisDeclaration:
    """Per-basis declaration (ADR-0014 D3).

    Each basis function declares:
      * ``name``        : identifier ("bias", "rate", "drag", ...)
      * ``input``       : which regressor input the slot consumes
      * ``dimension``   : physical dimension symbol (e.g. "1", "rad/s")
      * ``normalise``   : characteristic scale that renders the slot O(1)
      * ``normalise_via``: optional reference scale name ("u_max", "J_xx", ...)
                          used to look up the value at run time (informational;
                          resolution is a future decision, not implemented here)

    The dimensionless form is computed mechanically from the declaration;
    a future regressor with new basis slots declares them the same way.
    """
    name: str
    input: str
    dimension: str
    normalise: float
    normalise_via: Optional[str] = None


# Module-level registry of named RegressorVariant instances. Keyed by
# ``name``; populated by construction. Kept at module scope (not as a
# dataclass field) to avoid frozen-dataclass instance-level state issues
# and to give the registry a single, easy-to-clear location for tests.
_VARIANT_REGISTRY: dict[str, "RegressorVariant"] = {}


@dataclass(frozen=True)
class RegressorVariant:
    """A declared regressor variant (ADR-0014 D4).

    The current six-slot regressor is the pinned firmware baseline and is
    always available as ``RegressorVariant.DEFAULT``. Other variants can be
    registered through ``RegressorVariant.register``; their outputs are
    sim-only until promoted with a parity test against firmware.

    Each variant carries ``basis_declarations``: a tuple of
    :class:`BasisDeclaration` objects defining the per-slot name, input,
    dimension, and normalisation scale. The ``normalise`` field is the
    multiplicative scale applied to that slot (ADR-0014 D3: scale by
    ``1.0 / normalise`` so a unit at the characteristic scale maps to 1.0).

    ``RegressorVariant.DEFAULT`` is instantiated without declarations; they are
    attached by ``sim.regressor`` after ``BASIS_DEFAULT`` is defined, via
    :meth:`set_basis_declarations`. Sim-only variants pass declarations at
    construction time.
    """
    name: str
    num_basis: int
    basis_declarations: Tuple[BasisDeclaration, ...] = ()

    def __post_init__(self) -> None:
        if self.name in _VARIANT_REGISTRY:
            raise ValueError(
                f"RegressorVariant {self.name!r} already registered"
            )
        _VARIANT_REGISTRY[self.name] = self

    @classmethod
    def register(cls, name: str, num_basis: int,
                basis_declarations: Tuple[BasisDeclaration, ...] = ()
                ) -> "RegressorVariant":
        """Create and register a new variant. Returns the new variant."""
        return cls(name=name, num_basis=num_basis,
                   basis_declarations=basis_declarations)

    @classmethod
    def get(cls, name: str) -> "RegressorVariant":
        if name not in _VARIANT_REGISTRY:
            raise KeyError(
                f"unknown RegressorVariant {name!r}; "
                f"registered: {sorted(_VARIANT_REGISTRY)}"
            )
        return _VARIANT_REGISTRY[name]

    @classmethod
    def all(cls) -> list[str]:
        """All registered variant names, sorted."""
        return sorted(_VARIANT_REGISTRY)

    @classmethod
    def set_basis_declarations(cls, name: str,
                               declarations: Tuple[BasisDeclaration, ...]
                               ) -> None:
        """Attach basis declarations to an existing variant.

        Used to attach ``BASIS_DEFAULT`` to ``RegressorVariant.DEFAULT`` after
        ``BASIS_DEFAULT`` is defined in ``sim.regressor`` (avoids a circular
        import). The variant's ``basis_declarations`` are set in-place using
        ``object.__setattr__`` (the frozen dataclass rejects normal assignment).
        """
        variant = cls.get(name)
        if variant.basis_declarations:
            raise ValueError(
                f"RegressorVariant {name!r} already has basis_declarations; "
                f"cannot overwrite"
            )
        # Mutate in-place so the existing singleton gets the declarations.
        # The frozen dataclass blocks normal attribute assignment.
        object.__setattr__(variant, "basis_declarations", declarations)

    @property
    def has_trivial_normalise(self) -> bool:
        """True when every basis normalise is 1.0 (bit-identical to baseline)."""
        return all(b.normalise == 1.0 for b in self.basis_declarations)

    @property
    def scale_vector(self) -> np.ndarray:
        """Per-slot normalisation vector: slot i contributes ``1/normalise[i]``.

        Used by :meth:`to_phi` to rescale a raw phi vector.
        """
        if not self.basis_declarations:
            return np.ones(self.num_basis)
        return np.array([1.0 / b.normalise for b in self.basis_declarations])


# Pinned firmware baseline — six-slot structured regressor (mrac.c:65-91).
# basis_declarations are attached by sim.regressor after BASIS_DEFAULT is defined.
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
                f"registered: {RegressorVariant.all()}"
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
