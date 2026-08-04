"""Motor-bench thermal guard.

On 2026-07-29 a thrust sweep held one motor near full power for ~50 minutes -- 40
logged points at CCR >= 3800, roughly 6 s apart, with no cool-down -- and burned it
out. The thrust data itself was clean (holding the curve shape fixed, the motor's
scale factor stayed within +/-3 % right up to the final sweep, so the failure was
abrupt rather than a fade), but the duty cycle was the cause.

The guard budgets dwell above a hot CCR threshold. Spending the budget drops the
motor to idle -- still turning, so the prop keeps air moving over it, which STOP
does not -- and starts a rest during which the operating point is pinned at idle.

These tests pin the parts that have to hold for the guard to be worth anything:
the drop happens, the rest cannot be nudged away with the slider, and stop/start
is not a way to skip the cooldown.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from ground_station.gui import dashboard as dash_mod  # noqa: E402
from ground_station.gui.dashboard import Dashboard  # noqa: E402


class _FakeDpg:
    """Minimal stand-in for dearpygui: widget values in a dict."""

    def __init__(self, values):
        self.values = dict(values)
        self.colors = {}

    def get_value(self, tag):
        if tag not in self.values:
            raise KeyError(tag)
        return self.values[tag]

    def set_value(self, tag, val):
        self.values[tag] = val

    def configure_item(self, tag, **kw):
        self.colors[tag] = kw.get("color")


DEFAULTS = {
    "bench_guard_on": True,
    "bench_idle_ccr": 2150,
    "bench_hot_ccr": 3700,
    "bench_hot_max_s": 20,
    "bench_rest_s": 45,
    "bench_ccr": 3800,
    "bench_guard_status": "",
    "bench_log_status": "",
    "bench_autoidle": True,
    "bench_grams": 0.0,
    "bench_tare_g": 0.0,
}


def _dash(monkeypatch, **overrides):
    fake = _FakeDpg({**DEFAULTS, **overrides})
    monkeypatch.setattr(dash_mod, "dpg", fake)
    d = Dashboard.__new__(Dashboard)
    d._motor_test_active = True
    d._motor_test_ccr = int(fake.values["bench_ccr"])
    d._motor_test_id = 4
    d._motor_test_step = 200
    d._motor_test_allow_high = True
    d._bench_hot_s = 0.0
    d._bench_rest_until = 0.0
    d._bench_guard_t = 0.0
    d._bench_ccr_change_t = 0.0
    d._bench_sweep = ""
    d._bench_idling = False
    d._bench_target = int(fake.values["bench_ccr"])
    d.sent = []
    d._send_cmd = lambda c, i, v: d.sent.append((c, i, v))
    return d, fake


def _run(d, seconds, t0=1000.0, step=0.5):
    """Advance the guard by `seconds` of wall clock in `step` increments."""
    t = t0
    end = t0 + seconds
    while t <= end:
        d._bench_guard_tick(t)
        t += step
    return t


def test_dwell_above_threshold_drops_to_idle_and_rests(monkeypatch):
    d, fake = _dash(monkeypatch)
    _run(d, 25.0)                       # budget is 20 s
    assert d._motor_test_ccr == 2150, "motor must be pulled down to idle"
    assert d._bench_rest_until > 0.0, "a rest must be in progress"
    assert d._motor_test_active, "guard idles the motor, it does not stop it"
    assert (0x16, 2, 2150.0) in d.sent
    # The sweep point survives -- this is what makes the guard usable rather than a
    # punishment: after the rest, GO returns to exactly where the operator was.
    assert fake.values["bench_ccr"] == 3800, "the guard must NOT clobber the target"
    assert d._bench_target_ccr() == 3800


def test_rest_cannot_be_nudged_away_with_the_slider(monkeypatch):
    d, _ = _dash(monkeypatch)
    _run(d, 25.0)
    # Operator drags the slider back up mid-rest. The target moves; the motor does not.
    d._bench_set_target(3900)
    assert d._bench_current_ccr() == 2150, "commanded CCR must stay at idle while resting"
    # ...and GO is refused outright.
    d._bench_resume()
    assert d._bench_current_ccr() == 2150


def test_rest_expires_then_budget_is_clear(monkeypatch):
    d, _ = _dash(monkeypatch)
    t = _run(d, 25.0)
    assert d._bench_rest_until > 0.0
    d._bench_guard_tick(t + 46.0)       # rest is 45 s
    assert d._bench_rest_until == 0.0
    assert d._bench_hot_s == 0.0, "budget resets after a completed rest"
    # Still idling: a timer expiring must never spin the motor back up by itself.
    assert d._bench_idling
    assert d._bench_current_ccr() == 2150
    d._bench_resume()                   # operator action
    assert d._bench_current_ccr() == 3800


def test_stop_does_not_cancel_an_in_progress_rest(monkeypatch):
    """Otherwise stop/start is a one-click way to skip the cooldown."""
    d, _ = _dash(monkeypatch)
    _run(d, 25.0)
    resting_until = d._bench_rest_until
    d._bench_stop()
    assert d._bench_rest_until == resting_until
    d._bench_resume()
    assert d._bench_current_ccr() == 2150


def test_budget_recovers_while_below_the_threshold(monkeypatch):
    d, _ = _dash(monkeypatch)
    _run(d, 10.0)                       # 10 s of the 20 s budget
    spent = d._bench_hot_s
    assert 9.0 <= spent <= 11.0
    d._motor_test_ccr = 3000            # back below the hot threshold
    _run(d, 10.0, t0=1100.0)
    assert d._bench_hot_s < spent, "cooling must give budget back"
    assert d._bench_rest_until == 0.0, "no rest is triggered while cool"


def test_disabled_guard_never_intervenes(monkeypatch):
    d, _ = _dash(monkeypatch, bench_guard_on=False)
    _run(d, 120.0)
    assert d._motor_test_ccr == 3800
    assert d._bench_rest_until == 0.0
    assert d._bench_hot_s == 0.0


def test_below_threshold_never_accumulates(monkeypatch):
    d, _ = _dash(monkeypatch, bench_ccr=3600)
    _run(d, 120.0)
    assert d._bench_hot_s == 0.0
    assert d._bench_rest_until == 0.0


def test_stopped_motor_does_not_burn_budget(monkeypatch):
    d, _ = _dash(monkeypatch)
    d._motor_test_active = False
    _run(d, 60.0)
    assert d._bench_hot_s == 0.0
    assert d._bench_rest_until == 0.0


def test_idle_button_drops_ccr_without_stopping(monkeypatch):
    d, fake = _dash(monkeypatch)
    d._bench_go_idle("manual")
    assert d._motor_test_ccr == 2150
    assert d._motor_test_active, "IDLE is not STOP"
    assert (0x16, 2, 2150.0) in d.sent
    assert d._bench_sweep == "down"
    assert fake.values["bench_ccr"] == 3800, "IDLE must not move the slider"


def test_idle_preserves_the_sweep_point_and_go_returns_to_it(monkeypatch):
    """The friction the separation exists to remove: idling between points used to
    overwrite the slider, so every point cost a manual drag back up."""
    d, fake = _dash(monkeypatch, bench_ccr=3000)
    d._bench_go_idle("manual")
    assert d._bench_current_ccr() == 2150
    assert d._bench_target_ccr() == 3000, "target survives the idle"
    d._bench_resume()
    assert d._bench_current_ccr() == 3000, "GO returns to the same point, one click"


def test_step_buttons_preset_the_next_point_while_idling(monkeypatch):
    d, fake = _dash(monkeypatch, bench_ccr=3000)
    d._bench_go_idle("manual")
    d._bench_step_ccr(+1)               # step is 200
    assert d._bench_target_ccr() == 3200
    assert d._bench_current_ccr() == 2150, "stepping while idle must not spin the motor up"
    assert (0x16, 2, 3200.0) not in d.sent
    d._bench_resume()
    assert d._bench_current_ccr() == 3200
    assert (0x16, 2, 3200.0) in d.sent


def test_resume_restarts_the_settle_clock(monkeypatch):
    """settle_s must count from when the motor reached the point, not from the +/- click."""
    d, _ = _dash(monkeypatch, bench_ccr=3000)
    d._bench_go_idle("manual")
    d._bench_step_ccr(+1)
    d._bench_ccr_change_t = 0.0
    d._bench_resume()
    assert d._bench_ccr_change_t > 0.0
    assert d._bench_sweep == "up"


def test_log_point_auto_idles(monkeypatch, tmp_path):
    d, fake = _dash(monkeypatch, bench_ccr=3000, bench_grams=120.0)
    d._bench_idling = False
    d._bench_csv_path = tmp_path/"t.csv"
    d._bench_csv_path.write_text("hdr\n", encoding="utf-8")
    d._log_lock = __import__("threading").Lock()
    d._telem = {}
    d._bench_log_point()
    assert d._bench_idling, "the reading is taken; holding power after it is heat for nothing"
    assert d._bench_current_ccr() == 2150
    assert d._bench_target_ccr() == 3000, "still parked on the point that was just logged"
    assert "3000" in d._bench_csv_path.read_text(), "the row records the CCR it was logged at"


def test_start_comes_up_at_idle_not_at_the_stale_slider_value(monkeypatch):
    d, _ = _dash(monkeypatch, bench_ccr=3800)
    d._motor_test_active = False
    d._telem = {"a": {"status.arm": 0.0}}
    d._bench_start()
    assert d._bench_idling
    assert d._bench_current_ccr() == 2150, "RUN is not a request for full power"
    assert (0x16, 2, 2150.0) in d.sent
    assert (0x16, 2, 3800.0) not in d.sent


def test_guard_ignores_a_stalled_render_loop(monkeypatch):
    """A 60 s gap between ticks must not instantly spend a 20 s budget."""
    d, _ = _dash(monkeypatch)
    d._bench_guard_tick(1000.0)
    d._bench_guard_tick(1060.0)         # one huge dt
    assert d._bench_hot_s <= 1.0
    assert d._bench_rest_until == 0.0
