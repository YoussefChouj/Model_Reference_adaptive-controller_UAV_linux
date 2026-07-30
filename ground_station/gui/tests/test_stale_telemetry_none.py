"""Regression: stale telemetry must not crash the render loop.

SerialBridge.get_telemetry_snapshot() deliberately replaces a frame's values with
None once that frame has not arrived for >0.5 s, so the UI can show '--' instead of
stale garbage. The dashboard, however, reads those dicts with `k in a` and
`a.get(k, 0.0)` -- idioms that are correct for a *missing* key but raise
TypeError on a *present-but-None* one:

    TypeError: float() argument must be a string or a real number, not 'NoneType'

That raise propagates out of _frame(), so every panel drawn after the raising line
stops updating while the ones before it keep going -- the "some data streams, some
doesn't" symptom, plus a traceback per rendered frame.

The fix drops None-valued keys at the dashboard boundary. These tests pin both
halves: the bridge still emits None when stale (its documented contract), and the
dashboard never lets a None reach a consumer.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from ground_station.comm.serial_bridge import SerialBridge  # noqa: E402
from ground_station.gui.dashboard import Dashboard  # noqa: E402


class _StubBridge:
    """Stands in for SerialBridge, returning whatever snapshot the test wants."""

    def __init__(self, a, b):
        self._a = a
        self._b = b

    def get_telemetry_snapshot(self):
        return (dict(self._a), dict(self._b))

    def get_last_max_num_basis(self) -> int:
        return 6


def _dash(bridge) -> Dashboard:
    d = Dashboard.__new__(Dashboard)
    d.bridge = bridge
    d._remote_bridge = False
    d._telem = {"a": {}, "b": {}, "c": {}, "id": {}, "of": {}, "max_num_basis": 8}
    d._last_telem_rx_t = 0.0
    return d


def test_bridge_still_nulls_stale_frames():
    """The contract the dashboard has to defend against is real, not hypothetical."""
    br = SerialBridge.__new__(SerialBridge)
    br._telemetry_lock = __import__("threading").Lock()
    br._last_telemetry_a = {"status.arm": 1.0}
    br._last_telemetry_b = {"pid.locx.FB": 12.5}
    br._last_frame_a_t = time.monotonic()      # fresh
    br._last_frame_b_t = time.monotonic() - 5.0  # stale

    a, b = br.get_telemetry_snapshot()
    assert a["status.arm"] == 1.0
    assert b["pid.locx.FB"] is None, "stale Frame B values are nulled -- this is the trap"


def test_none_values_are_dropped_not_carried_into_telem():
    d = _dash(_StubBridge(
        a={"status.arm": 1.0, "status.rc_authority": None},
        b={"pid.locx.FB": None, "pid.z_pos.FB": 0.4},
    ))
    d._sync_telemetry_from_bridge_if_local()

    assert None not in d._telem["a"].values()
    assert None not in d._telem["b"].values()
    # Fresh values survive untouched.
    assert d._telem["a"]["status.arm"] == 1.0
    assert d._telem["b"]["pid.z_pos.FB"] == 0.4
    # Nulled ones become absent, so `in` and `.get(k, default)` both behave.
    assert "status.rc_authority" not in d._telem["a"]
    assert "pid.locx.FB" not in d._telem["b"]


def test_consumer_idioms_no_longer_raise():
    """The exact expressions that were raising, at dashboard.py:806 and :1075."""
    d = _dash(_StubBridge(
        a={"status.arm": None},
        b={"pid.locx.FB": None, "path.twc_target_x": None},
    ))
    d._sync_telemetry_from_bridge_if_local()
    a, b = d._telem["a"], d._telem["b"]

    arm = float(a["status.arm"]) if "status.arm" in a else None
    assert arm is None
    assert float(b.get("pid.locx.FB", 0.0)) == 0.0
    assert float(b.get("path.twc_target_x", 0.0)) == 0.0


def test_fully_stale_link_reports_stale_instead_of_fresh():
    """An all-None snapshot must not refresh the freshness timestamp.

    Before the fix the dict was non-empty (all None), so `if a or b` kept marking
    telemetry OK while every read from it raised.
    """
    d = _dash(_StubBridge(a={"status.arm": None}, b={"pid.locx.FB": None}))
    d._sync_telemetry_from_bridge_if_local()

    assert d._telem["a"] == {}
    assert d._telem["b"] == {}
    assert d._last_telem_rx_t == 0.0, "no fresh values arrived, so the link is stale"
    assert d._telemetry_is_fresh() is False
