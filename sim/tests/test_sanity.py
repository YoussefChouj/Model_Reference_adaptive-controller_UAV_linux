"""Gazebo sanity-gate availability test for spec 4c."""
from __future__ import annotations

import pytest

from sim.gazebo_bridge import gz_binary_available
from sim.sanity import sim_vs_analytic_hover


def test_sanity_fails_cleanly_without_gz():
    available, reason = gz_binary_available()
    if available:
        pytest.skip("gz is installed; live sanity execution belongs to integration testing")
    passes, comparison = sim_vs_analytic_hover(timeout_s=0.1)
    assert passes is False
    assert "reason" in comparison
    assert comparison["reason"]


def test_sanity_returns_typed_reason_for_uninstalled_gz(monkeypatch):
    """The gate must surface the typed ``gz unavailable`` reason on Windows."""
    from sim.gazebo_bridge import GazeboUnavailable

    def _boom(*args, **kwargs):
        raise GazeboUnavailable("gz bindings not importable")

    monkeypatch.setattr("sim.gazebo_bridge.GazeboBridge", _boom)
    passes, comparison = sim_vs_analytic_hover(timeout_s=0.1)
    assert passes is False
    assert comparison["reason"] == "gz bindings unavailable"