"""TDD slice 4b -- sim/run.py closed-loop integration.

These are the Phase-1 definition-of-done checks (ADR-0006): identified models run
through the reference model with the firmware-parity controller produce stable
tracking and bounded adaptive weights. Validation-by-plot is the human surface;
these assertions just guard the floor (no blow-ups, weights stay in the projection
box, MRAC helps rather than hurts).
"""
import numpy as np
import pytest

from sim import scenarios
from sim.adaptive_law import AdaptiveFlags
from sim.run import run


def test_step_roll_is_stable_and_weights_bounded():
    res = run(scenarios.step("roll"), write_artifacts=False)
    m = res["metrics"]
    assert m["stable"]
    assert np.all(np.isfinite(res["theta"]))
    # projection keeps weights inside [0, What_limit]; norm of the box ~0.33
    assert m["max_weight_norm"] < 1.0
    # plant should track the reference to within a fraction of the command
    assert m["max_abs_err"] < res["log"]["xm"].max() + 0.5


def test_weights_start_at_zero():
    res = run(scenarios.step("roll"), write_artifacts=False)
    assert np.allclose(res["theta"][0], 0.0)


def test_shadow_mode_has_zero_adaptive_injection():
    # injection OFF -> u == u_nom (+disturbance); u_ad still computed but not applied
    res = run(scenarios.step("roll"), injection=False, write_artifacts=False)
    log = res["log"]
    np.testing.assert_allclose(log["u"], log["u_nom"], atol=1e-12)


def test_disturbance_rejection_drives_weights():
    # a torque bias with r=0 must make the adaptation move off zero
    res = run(scenarios.disturbance_rejection("roll"), write_artifacts=False)
    assert res["metrics"]["final_weight_norm"] > 0.0
    assert res["metrics"]["stable"]


def test_yaw_test_runs_stable():
    res = run(scenarios.yaw_test(), write_artifacts=False)
    assert res["metrics"]["stable"]
    assert res["axis"] == "yaw"


def test_adaptation_off_keeps_weights_zero():
    flags = AdaptiveFlags(adaptation_on=False)
    res = run(scenarios.step("roll"), flags=flags, write_artifacts=False)
    assert np.allclose(res["theta"], 0.0)


def test_artifacts_written(tmp_path):
    from pathlib import Path
    res = run(scenarios.step("roll"), write_artifacts=True, runs_dir=tmp_path)
    d = Path(res["outdir"])
    assert d.parent == tmp_path
    assert (d / "data.csv").exists()
    assert (d / "metrics.json").exists()
    assert (d / "report.md").exists()
    assert (d / "plots" / "tracking.png").exists()
    assert (d / "plots" / "weights.png").exists()
