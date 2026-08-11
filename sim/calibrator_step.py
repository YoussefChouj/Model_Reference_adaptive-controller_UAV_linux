"""Per-tick calibrator wiring — extracted from sim/run.py (sim-arch-02).

Owns the ``AccBiasTrim`` + ``GyroBiasHotFsm`` instances and the gating that
mirrors the firmware timing (ADR-0011 Phases 3 & 4). The runner calls
``tick(...)`` every simulation tick; ``history(n)`` returns the pre-allocated
log arrays for CSV export and the result dict.

The gating logic must stay bit-identical to the inline block it replaced
(sim/run.py:122-156 pre-refactor). Three branches:

1. ``_has_cal is False`` (plant has no ``get_accel_mg`` / ``get_gyro_rads``):
   every cal_log entry is NaN / sentinel ``-1`` / ``False`` — this is the
   scenario default; existing scenarios return ``None`` for these.
2. ``flying = abs(r) < 0.1`` AND ``t > 2.0``: ``AccBiasTrim.update`` runs.
   This matches ADR-0011 cold-cal → CAL_AIRBORNE transition.
3. Otherwise: ``GyroBiasHotFsm.update`` runs every tick (FSM is internally
   guarded by stillness + translation + rc_active + flying checks).
"""
from __future__ import annotations

import numpy as np

from sim.calibrator import AccBiasTrim, GyroBiasHotFsm


class CalibratorStep:
    """Per-tick glue for the IMU calibrators (ADR-0011 Phases 3 + 4).

    Args:
        plant: scenario plant. ``_has_cal`` is True iff the plant exposes both
            ``get_accel_mg()`` and ``get_gyro_rads()``.
        dt: simulation timestep, seconds. Currently unused (kept in the
            signature for parity with future firmware tick-rate-driven gates).
    """

    def __init__(self, plant, dt: float) -> None:
        self.dt = dt
        self._has_cal = (hasattr(plant, "get_accel_mg")
                         and hasattr(plant, "get_gyro_rads"))
        self._acc = AccBiasTrim()
        self._gyro = GyroBiasHotFsm()
        self._cal_log: dict | None = None
        self._n: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @property
    def has_cal(self) -> bool:
        return self._has_cal

    def tick(self, *, t: float, r: float, g_ref: tuple, g_meas: tuple,
             gyro_rads: tuple, rc_active: bool) -> dict:
        """Advance the calibrators one tick; populate the log row.

        Returns a snapshot dict with the same keys the runner appends to its
        result: ``b_a``, ``acc_trim_settled``, ``b_g``, ``gyro_state``,
        ``gyro_rejected``, ``_has_cal``.
        """
        k = self._idx_for_t(t)

        if self._has_cal:
            flying = abs(r) < 0.1
            if flying and t > 2.0:
                self._acc.update(g_ref, g_meas)

            # GyroBiasHotFsm runs every tick; FSM internally checks rc_active,
            # flying, stillness, and translational guards.
            gyro_res = self._gyro.update(gyro_rads, (g_meas[0], g_meas[1], 0.0),
                                         flying, rc_active=rc_active)

            self._cal_log["b_a_x"][k] = self._acc.b_a[0]
            self._cal_log["b_a_y"][k] = self._acc.b_a[1]
            self._cal_log["b_a_z"][k] = self._acc.b_a[2]
            self._cal_log["b_g_x"][k] = self._gyro.b_g[0]
            self._cal_log["b_g_y"][k] = self._gyro.b_g[1]
            self._cal_log["b_g_z"][k] = self._gyro.b_g[2]
            self._cal_log["gyro_state"][k] = gyro_res["state"]
            self._cal_log["gyro_rejected"][k] = gyro_res["rejected"]
        else:
            for kk in ("b_a_x", "b_a_y", "b_a_z", "b_g_x", "b_g_y", "b_g_z"):
                self._cal_log[kk][k] = float("nan")
            self._cal_log["gyro_state"][k] = -1
            self._cal_log["gyro_rejected"][k] = False

        return self.snapshot()

    def history(self, n: int) -> dict | None:
        """Pre-allocate the log arrays and return them.

        The arrays are always allocated (so ``tick()`` has a place to write
        NaN sentinel rows when the plant has no sensor interface) but the
        *returned* value is ``None`` when ``_has_cal is False`` so the runner
        can stash ``None`` in the result dict, matching the pre-refactor
        ``sim/run.py:182`` contract.
        """
        self._n = n
        self._cal_log = {
            "b_a_x": np.empty(n), "b_a_y": np.empty(n), "b_a_z": np.empty(n),
            "b_g_x": np.empty(n), "b_g_y": np.empty(n), "b_g_z": np.empty(n),
            "gyro_state": np.empty(n, dtype=int),
            "gyro_rejected": np.empty(n, dtype=bool),
        }
        if not self._has_cal:
            return None
        return self._cal_log

    def snapshot(self) -> dict:
        """Return the current calibrator state as a dict.

        Always includes ``_has_cal`` so callers can branch without re-checking
        ``hasattr(plant, ...)``. When ``_has_cal is False``, the bias tuples
        are ``(0.0, 0.0, 0.0)`` (mirroring the pre-refactor ``AccBiasTrim`` /
        ``GyroBiasHotFsm`` defaults; the NaN sentinels stay in the internal
        ``_cal_log`` arrays for CSV export and are never exposed via this
        snapshot) and the gyro state is ``-1``.
        """
        if self._has_cal:
            return {
                "b_a": self._acc.b_a,
                "acc_trim_settled": self._acc.settled,
                "b_g": self._gyro.b_g,
                "gyro_state": int(self._gyro._state),
                "gyro_rejected": bool(self._gyro._rejected),
                "_has_cal": True,
            }
        return {
            "b_a": (0.0, 0.0, 0.0),
            "acc_trim_settled": False,
            "b_g": (0.0, 0.0, 0.0),
            "gyro_state": -1,
            "gyro_rejected": False,
            "_has_cal": False,
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _idx_for_t(self, t: float) -> int:
        """Translate ``t`` back to the index the runner used to allocate the log.

        Mirrors the ``k = int(round(t / dt))`` mapping the runner uses for its
        log arrays. We re-derive it from ``self.dt`` so the call site stays
        terse (``cal.tick(t=t, r=r, ...)`` instead of ``cal.tick(k=k, t=t, ...)``).
        Rounding matches ``int(round(...))`` from the runner.
        """
        return int(round(t / self.dt))
