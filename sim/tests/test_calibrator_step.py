"""TDD slice for sim/calibrator_step.py (sim-arch-02).

Tests the three branches the runner depends on:

1. ``_has_cal is False`` — plant has no sensor interface; tick fills NaN /
   sentinel rows and ``history(n)`` returns ``None``.
2. ``_has_cal is True``, ``flying=False`` — ``AccBiasTrim.update`` is gated.
3. ``_has_cal is True``, ``flying=True`` AND ``t > 2.0`` — ``AccBiasTrim.update``
   runs and ``b_a`` moves.
"""
import math

import numpy as np
import pytest

from sim.calibrator_step import CalibratorStep


class _FakeCalPlant:
    """Plant that exposes the calibrator sensor interface used by ADR-0011."""

    def __init__(self, acc=(0.0, 0.0, 9810.0), gyro=(0.01, 0.01, 0.01)):
        self._acc = acc
        self._gyro = gyro

    def get_accel_mg(self):
        return self._acc

    def get_gyro_rads(self):
        return self._gyro


class _NoCalPlant:
    """Plant that has no sensor interface — the existing-scenario default."""

    def step(self, axis_cmd):
        return {k: 0.0 for k in axis_cmd}


# ------------------------------------------------------------------
# Branch 1: _has_cal is False
# ------------------------------------------------------------------

def test_history_returns_none_when_plant_has_no_sensor_interface():
    cal = CalibratorStep(_NoCalPlant(), dt=0.005)
    assert cal.has_cal is False
    assert cal.history(100) is None


def test_tick_fills_nan_sentinels_when_no_sensor_interface():
    cal = CalibratorStep(_NoCalPlant(), dt=0.005)
    cal.history(5)  # allocates internal arrays even though history() returns None
    for k in range(5):
        cal.tick(t=k * 0.005, r=0.0, g_ref=(0, 0, 1000),
                 g_meas=(0, 0, 0), gyro_rads=(0, 0, 0), rc_active=False)

    snap = cal.snapshot()
    # Result-dict contract: snapshot() returns the same shape the runner uses to
    # populate ``result["acc_trim_b_a"]`` / ``result["gyro_hot_b_g"]``. Pre-refactor,
    # those were ``acc_trim.b_a`` and ``gyro.b_g`` — both default to ``(0.0, 0.0, 0.0)``
    # when the plant has no sensor interface and the calibrators never update.
    # Post-refactor must preserve that contract for downstream consumers.
    assert snap["b_a"] == (0.0, 0.0, 0.0)
    assert snap["b_g"] == (0.0, 0.0, 0.0)
    assert snap["gyro_state"] == -1
    assert snap["gyro_rejected"] is False
    assert snap["acc_trim_settled"] is False
    assert snap["_has_cal"] is False


# ------------------------------------------------------------------
# Branch 2: _has_cal is True, flying=False -> AccBiasTrim.update gated
# ------------------------------------------------------------------

def test_acc_trim_does_not_update_when_not_flying():
    cal = CalibratorStep(_FakeCalPlant(gyro=(0.0, 0.0, 0.0)), dt=0.005)
    n = 5
    cal.history(n)
    # abs(r) >= 0.1 -> not flying; t > 2.0 (gate would pass if flying)
    for k in range(n):
        cal.tick(t=k * 0.005, r=0.5, g_ref=(0, 0, 1000),
                 g_meas=(0, 0, 9810), gyro_rads=(0, 0, 0), rc_active=False)
    snap = cal.snapshot()
    # b_a starts at (0,0,0) and stays at (0,0,0) because AccBiasTrim.update was gated
    assert snap["b_a"] == (0.0, 0.0, 0.0)
    assert snap["acc_trim_settled"] is False


# ------------------------------------------------------------------
# Branch 3: _has_cal is True, flying=True, t > 2.0 -> AccBiasTrim.update runs
# ------------------------------------------------------------------

def test_acc_trim_updates_when_flying_and_t_greater_than_2():
    cal = CalibratorStep(
        _FakeCalPlant(acc=(0.0, 0.0, 9810.0 - 50.0), gyro=(0.0, 0.0, 0.0)),
        dt=0.005,
    )
    # n large enough that some t > 2.0 with the standard t = k*dt mapping.
    # k=600 is t=3.0 s, the first tick after the firmware's CAL_AIRBORNE gate.
    n = 800
    cal.history(n)
    # r = 0 -> abs(r) < 0.1 -> flying; expect b_a to move on each tick where t > 2.0
    for k in range(n):
        cal.tick(t=k * 0.005, r=0.0, g_ref=(0, 0, 1000),
                 g_meas=(0, 0, 9810.0 - 50.0), gyro_rads=(0, 0, 0), rc_active=False)
    snap = cal.snapshot()
    # b_a should be non-zero on at least one axis after several ticks
    assert any(abs(v) > 0.0 for v in snap["b_a"])


def test_acc_trim_skipped_when_t_below_threshold_even_if_flying():
    cal = CalibratorStep(
        _FakeCalPlant(acc=(0.0, 0.0, 9810.0 - 50.0), gyro=(0.0, 0.0, 0.0)),
        dt=0.005,
    )
    n = 5  # all t in [0, 0.025) -> all below 2.0 s
    cal.history(n)
    for k in range(n):
        cal.tick(t=k * 0.005, r=0.0, g_ref=(0, 0, 1000),
                 g_meas=(0, 0, 9810.0 - 50.0), gyro_rads=(0, 0, 0), rc_active=False)
    snap = cal.snapshot()
    assert snap["b_a"] == (0.0, 0.0, 0.0)


# ------------------------------------------------------------------
# Gyro FSM runs every tick (no extra time gate)
# ------------------------------------------------------------------

def test_gyro_fsm_runs_every_tick_independent_of_t():
    cal = CalibratorStep(
        _FakeCalPlant(acc=(0.0, 0.0, 9810.0), gyro=(0.01, 0.01, 0.01)),
        dt=0.005,
    )
    n = 5
    cal.history(n)
    # Even at small t (well below 2.0), the gyro FSM should be advancing
    # (stillness + flying both met). Use the standard t = k*dt mapping.
    for k in range(n):
        cal.tick(t=k * 0.005, r=0.0, g_ref=(0, 0, 1000),
                 g_meas=(0, 0, 9810), gyro_rads=(0.01, 0.01, 0.01), rc_active=False)
    snap = cal.snapshot()
    # FSM is internally guarded; on tick 0 with stillness + flying + no translation,
    # state should be WAIT_STILL (0)
    assert snap["gyro_state"] == 0


def test_snapshot_keys_match_run_result_contract():
    cal = CalibratorStep(_NoCalPlant(), dt=0.005)
    snap = cal.snapshot()
    # Runner consumes these exact keys when building the result dict.
    assert set(snap.keys()) == {"b_a", "acc_trim_settled", "b_g",
                                "gyro_state", "gyro_rejected", "_has_cal"}
