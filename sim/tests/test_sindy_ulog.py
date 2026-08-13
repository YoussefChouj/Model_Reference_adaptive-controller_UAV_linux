"""Unit + smoke tests for ``sim.sindy.adapters.ulog``.

The PX4 ulog adapter must accept every schema in the wild (1.10 → 1.17),
including the UAV-SEAD HuggingFace dataset. The unit tests inject a
``FakeULog`` via the module-level ``_make_ulog`` seam; the slow test
exercises the real ``pyulog`` parser against a cached file.

Test table (per spec):
- test_loads_modern_xyz_schema        — xyz + roll/pitch/yaw scalars
- test_loads_only_rates_no_setpoint   — rate present, setpoint absent
- test_loads_only_setpoint_no_rates   — setpoint present, rate absent
- test_loads_legacy_bracket_schema    — legacy [roll/[pitch/[yaw
- test_returns_none_when_no_rate_topics — no relevant topics
- test_axis_roll_pitch_yaw_mapping    — xyz column ordering
- test_warns_when_topic_present_but_no_axis_match
- test_loads_real_uav_sead_ulog       — slow, real cached .ulg
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

# Make the worktree's sim package importable even when pytest is launched
# from the operator's repo.
_THIS_DIR = Path(__file__).resolve().parent
_WORKTREE = _THIS_DIR.parents[1]
if str(_WORKTREE) not in sys.path:
    sys.path.insert(0, str(_WORKTREE))

from sim.sindy.adapters import ulog as ulog_mod
from sim.sindy.adapters.ulog import load_ulog  # noqa: E402


# ---------------------------------------------------------------------------
# Fake ULog — mimics the subset of pyulog.ULog that ``_get_topic_array`` uses
# ---------------------------------------------------------------------------

class _FakeDataset:
    """Stub for ``pyulog``'s ``ULog.get_dataset(name).data`` return value."""

    def __init__(self, fields: dict):
        self.data = fields


class FakeULog:
    """In-memory ULog stand-in.

    ``topics`` is a dict: ``{topic_name: {"timestamp": np.ndarray, ...}}``.
    ``get_dataset(name)`` returns an object with a ``.data`` dict.
    """

    def __init__(self, topics: dict):
        self._topics = topics
        # Mirror pyulog's ``data_list`` for ``_available_topics``.
        self.data_list = [SimpleNamespace(name=n) for n in topics]

    def get_dataset(self, name: str):
        if name not in self._topics:
            raise KeyError(name)
        return _FakeDataset(dict(self._topics[name]))


@pytest.fixture
def patch_ulog_factory(monkeypatch):
    """Replace ``_make_ulog`` so ``load_ulog`` uses a ``FakeULog`` instead of
    opening a real file. The factory takes a callable returning a ULog-like
    object.
    """

    def _set(fake_factory):
        monkeypatch.setattr(ulog_mod, "_make_ulog", lambda path: fake_factory())

    return _set


def _timestamp(n: int, start_us: int = 1_000_000, step_us: int = 10_000):
    return np.arange(n, dtype=np.float64) * step_us + start_us


def _rate_xyz_topics(n: int = 50, seed: int = 0):
    rng = np.random.default_rng(seed)
    ts = _timestamp(n)
    rate_xyz = rng.normal(scale=0.5, size=(n, 3)).astype(np.float32)
    return {
        "vehicle_angular_velocity": {
            "timestamp": ts,
            "xyz": rate_xyz,
        },
    }


def _setpoint_named_topics(n: int = 50, seed: int = 1):
    rng = np.random.default_rng(seed)
    ts = _timestamp(n)
    roll = rng.normal(scale=0.4, size=n).astype(np.float32)
    pitch = rng.normal(scale=0.4, size=n).astype(np.float32)
    yaw = rng.normal(scale=0.2, size=n).astype(np.float32)
    return {
        "vehicle_rates_setpoint": {
            "timestamp": ts,
            "roll": roll,
            "pitch": pitch,
            "yaw": yaw,
        },
    }


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

def test_loads_modern_xyz_schema(patch_ulog_factory):
    """Both rate (xyz) and setpoint (named) present → populated dataset."""

    rate_topics = _rate_xyz_topics(n=40)
    sp_topics = _setpoint_named_topics(n=40)
    rate_xyz = rate_topics["vehicle_angular_velocity"]["xyz"]

    def factory():
        return FakeULog({**rate_topics, **sp_topics})

    patch_ulog_factory(factory)

    ds = load_ulog("/fake/path.ulog", axis="roll")
    assert ds is not None
    assert ds.n_samples == 40
    np.testing.assert_allclose(ds.x, rate_xyz[:, 0])
    np.testing.assert_allclose(
        ds.u, sp_topics["vehicle_rates_setpoint"]["roll"], atol=1e-6
    )
    assert ds.axis == "roll"
    assert ds.meta["manifest_name"] == "ulog"


def test_loads_only_rates_no_setpoint(patch_ulog_factory):
    """Only rate topic present → x populated, u = NaN, dataset returned."""

    rate_topics = _rate_xyz_topics(n=30)
    rate_xyz = rate_topics["vehicle_angular_velocity"]["xyz"]

    def factory():
        return FakeULog(rate_topics)

    patch_ulog_factory(factory)

    ds = load_ulog("/fake/path.ulog", axis="pitch")
    assert ds is not None
    assert ds.n_samples == 30
    np.testing.assert_allclose(ds.x, rate_xyz[:, 1])
    assert np.all(np.isnan(ds.u))
    assert np.all(np.isnan(ds.u_nom))


def test_loads_only_setpoint_no_rates(patch_ulog_factory):
    """Only setpoint present → u populated, x = NaN, dataset returned."""

    sp_topics = _setpoint_named_topics(n=25)
    sp = sp_topics["vehicle_rates_setpoint"]

    def factory():
        return FakeULog(sp_topics)

    patch_ulog_factory(factory)

    ds = load_ulog("/fake/path.ulog", axis="yaw")
    assert ds is not None
    assert ds.n_samples == 25
    np.testing.assert_allclose(ds.u, sp["yaw"], atol=1e-6)
    assert np.all(np.isnan(ds.x))


def test_loads_legacy_bracket_schema(patch_ulog_factory):
    """Legacy [roll/[pitch/[yaw field names → rate populated."""

    n = 20
    ts = _timestamp(n)
    roll = np.linspace(-0.3, 0.3, n, dtype=np.float32)
    pitch = np.linspace(-0.2, 0.2, n, dtype=np.float32)
    yaw = np.zeros(n, dtype=np.float32)
    topics = {
        "vehicle_angular_velocity": {
            "timestamp": ts,
            "[roll": roll,
            "[pitch": pitch,
            "[yaw": yaw,
        },
    }

    def factory():
        return FakeULog(topics)

    patch_ulog_factory(factory)

    ds = load_ulog("/fake/path.ulog", axis="roll")
    assert ds is not None
    assert ds.n_samples == 20
    np.testing.assert_allclose(ds.x, roll, atol=1e-6)


def test_returns_none_when_no_rate_topics(patch_ulog_factory):
    """No relevant topics → None + warning."""

    topics = {
        "vehicle_attitude": {
            "timestamp": _timestamp(10),
            "q": np.zeros((10, 4), dtype=np.float32),
        },
    }

    def factory():
        return FakeULog(topics)

    patch_ulog_factory(factory)

    with pytest.warns(UserWarning, match="vehicle_angular_velocity"):
        ds = load_ulog("/fake/path.ulog")
    assert ds is None


def test_axis_roll_pitch_yaw_mapping(patch_ulog_factory):
    """xyz column ordering: roll=0, pitch=1, yaw=2."""

    n = 15
    ts = _timestamp(n)
    xyz = np.zeros((n, 3), dtype=np.float32)
    xyz[:, 0] = 0.1  # roll
    xyz[:, 1] = 0.2  # pitch
    xyz[:, 2] = 0.3  # yaw
    topics = {
        "vehicle_angular_velocity": {"timestamp": ts, "xyz": xyz},
    }

    def factory():
        return FakeULog(topics)

    patch_ulog_factory(factory)

    ds_roll = load_ulog("/fake/path.ulog", axis="roll")
    ds_pitch = load_ulog("/fake/path.ulog", axis="pitch")
    ds_yaw = load_ulog("/fake/path.ulog", axis="yaw")

    np.testing.assert_allclose(ds_roll.x, xyz[:, 0])
    np.testing.assert_allclose(ds_pitch.x, xyz[:, 1])
    np.testing.assert_allclose(ds_yaw.x, xyz[:, 2])


def test_warns_when_topic_present_but_no_axis_match(patch_ulog_factory):
    """Topic exists but fields don't match any axis spec → warning + None.

    Note: the rate topic has ``acc`` (a different xyz-like field), not the
    expected ``xyz``, ``[roll``, ``[pitch``, ``[yaw``. The setpoint topic
    has only ``acc``, no roll/pitch/yaw. Therefore both lookups miss and
    the outer ``rate_data is None and sp_data is None`` path fires.
    """
    n = 8
    ts = _timestamp(n)
    topics = {
        "vehicle_angular_velocity": {
            "timestamp": ts,
            "acc": np.zeros((n, 3), dtype=np.float32),
        },
        "vehicle_rates_setpoint": {
            "timestamp": ts,
            "acc": np.zeros(n, dtype=np.float32),
        },
    }

    def factory():
        return FakeULog(topics)

    patch_ulog_factory(factory)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        ds = load_ulog("/fake/path.ulog")
    assert ds is None
    # At least one warning must mention the missing rate/setpoint topics OR
    # the unavailable axis triplet.
    msgs = [str(w.message) for w in caught]
    assert any(
        "vehicle_angular_velocity" in m
        or "vehicle_rates_setpoint" in m
        or "no axis triplet matched" in m
        for m in msgs
    ), f"expected rate/setpoint warning, got {msgs}"


# ---------------------------------------------------------------------------
# Slow test — real cached PX4 .ulg from UAV-SEAD HuggingFace mirror
# ---------------------------------------------------------------------------

_REAL_ULOG = _WORKTREE / "sim" / "flight_logs" / "uav_sead_smallest.ulg"
_pyulog_missing = False
try:
    import pyulog  # noqa: F401
except ImportError:
    _pyulog_missing = True


@pytest.mark.slow
@pytest.mark.skipif(_pyulog_missing, reason="pyulog not installed")
@pytest.mark.skipif(not _REAL_ULOG.exists(), reason=f"cached ulog missing: {_REAL_ULOG}")
def test_loads_real_uav_sead_ulog():
    """End-to-end smoke against the cached UAV-SEAD .ulg file."""
    ds = load_ulog(str(_REAL_ULOG), axis="roll")
    assert ds is not None
    assert ds.n_samples > 100, f"only {ds.n_samples} samples; expected >100"
    # x and u must have at least some finite samples (NaN-only would mean
    # the adapter failed silently).
    assert not np.all(np.isnan(ds.x)), "x is all-NaN; adapter failed to extract"
    assert not np.all(np.isnan(ds.u)), "u is all-NaN; adapter failed to extract"
