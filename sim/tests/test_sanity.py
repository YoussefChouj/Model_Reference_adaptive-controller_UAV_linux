"""Per-plant SysID gain-matching gate test (ADR-0012 D5).

Replaces the spec-4c Gazebo-era ``sim_vs_analytic_hover`` test with a
test of :func:`sim.sanity.check_plant_gain_match` against an
:class:`sim.plant.IdentifiedPlant`. The test asserts the skeleton
behaviour: the gain estimator returns the canonical K within the
documented tolerance, and a plant that disagrees fails cleanly.
"""
from __future__ import annotations

import pytest

from sim.plant import AxisModel, IdentifiedPlant, Plant
from sim.sanity import check_plant_gain_match

DT = 0.005


class _StubPlant(Plant):
    """Plant whose steady-state gain is exactly 2x the commanded input.

    Used to exercise the FAIL path of the gate: with target ``K=165``
    on roll, ``K_rel_err = 1.0`` which exceeds the default 10 %
    tolerance.
    """

    def reset(self) -> None:
        pass

    def step(self, u: dict) -> dict:
        # Map each axis command to its body-rate key with a 2x gain.
        out = {"p": 0.0, "q": 0.0, "r": 0.0, "vz": 0.0}
        out["p"] = 2.0 * float(u.get("roll", 0.0))
        out["q"] = 2.0 * float(u.get("pitch", 0.0))
        out["r"] = 2.0 * float(u.get("yaw", 0.0))
        out["vz"] = 2.0 * float(u.get("z", 0.0))
        return out

    @staticmethod
    def is_available() -> tuple[bool, str]:
        return (True, "stub plant")


def test_canonical_identified_plant_passes_within_tolerance():
    plant = IdentifiedPlant.canonical(DT)
    passes, results = check_plant_gain_match(
        plant, axes=("roll", "pitch"), duration_s=1.0, dt=DT,
    )
    assert passes is True
    assert {r.axis for r in results} == {"roll", "pitch"}
    for result in results:
        # The skeleton estimator is a slope approximation; we only
        # require the order of magnitude to agree (the gain ratio
        # K_rel_err <= 0.10 means the measured K is within +/-10% of
        # target -- the canonical roll plant K=165 has slope ~165 rad/s
        # per unit command, which is well within tolerance).
        assert result.K_rel_err <= 0.30  # generous: skeleton estimator


def test_plant_with_wrong_gain_fails_cleanly():
    plant = _StubPlant()
    passes, results = check_plant_gain_match(
        plant, axes=("roll",), duration_s=0.5, dt=DT,
    )
    assert passes is False
    assert len(results) == 1
    assert results[0].K_rel_err > 0.5


def test_empty_axes_is_vacuously_passing():
    plant = IdentifiedPlant.canonical(DT)
    passes, results = check_plant_gain_match(plant, axes=())
    assert passes is True
    assert results == []
