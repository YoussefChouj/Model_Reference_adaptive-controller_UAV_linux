"""IMU calibration estimators — ADR-0011 Phases 3 & 4.

Phase 3 (CAL_AIRBORNE_HOVER_TRIM): closed-form accel-bias LS estimator using
the gravity vector observable in world frame during stable hover.

Phase 4 (CAL_HOT_HOVER): gyro hot-bias FSM mirroring the v3 OF-bias estimator
in TASK/StabilizerTask.c:46-143.  Tracks quiescent gyro bias during in-flight
hover and refreshes it with a slow exponential filter (alpha = 1e-4).
"""
from __future__ import annotations

import math


# ------------------------------------------------------------------
# Phase 3 — Accel-bias trim (closed-form LS, gravity reference)
# ------------------------------------------------------------------

class AccBiasTrim:
    """Phase 3: closed-form accel-bias least-squares estimator.

    Cost: || g_ref - g_meas + b_a ||^2  minimized for b_a.
    Closed-form update: b_a <- b_a + mu * (g_ref - g_meas),  mu = 0.02.

    Convergence: residual < 5 mg for 1 s (200 ticks @ 200 Hz) -> settled.
    Degraded: max_ticks elapsed without settled -> best-so-far bias held.

    Args:
        mu: convergence gain (0.02 = slow, ~100 ticks to halve a step).
        settle_mg: residual threshold in mg for settled condition.
        settle_ticks: consecutive ticks below threshold to declare settled.
        max_ticks: hard time limit; if exceeded, degraded flag set.
    """

    def __init__(
        self,
        mu: float = 0.02,
        settle_mg: float = 5.0,
        settle_ticks: int = 200,
        max_ticks: int = 2000,
    ):
        self.mu = mu
        self.settle_mg = settle_mg
        self.settle_ticks = settle_ticks
        self.max_ticks = max_ticks

        self._b_a = (0.0, 0.0, 0.0)
        self._settled = False
        self._degraded = False
        self._settle_count = 0
        self._tick = 0
        self._best_b_a = (0.0, 0.0, 0.0)
        self._best_residual_mag = 1e9

    @property
    def b_a(self) -> tuple[float, float, float]:
        return self._b_a

    @property
    def settled(self) -> bool:
        return self._settled

    @property
    def degraded(self) -> bool:
        return self._degraded

    def update(
        self, g_ref: tuple[float, float, float], g_meas: tuple[float, float, float]
    ) -> tuple[float, float, float]:
        """Advance the estimator one tick.

        Args:
            g_ref: gravity vector in world frame, mg (e.g. (0, 0, 9810)).
            g_meas: measured gravity vector (after rotating g_ref by R(q)^T),
                    plus sensor noise, mg.

        Returns:
            Current b_a estimate, mg.
        """
        if self._settled:
            return self._b_a

        self._tick += 1

        # Residual: g_ref - (g_meas + b_a)  [but g_meas already includes b_a
        # in the sensor, so the measured g has g_ref - b_a baked in].
        # The corrected measurement is g_meas + b_a, which should track g_ref.
        residual_x = g_ref[0] - (g_meas[0] + self._b_a[0])
        residual_y = g_ref[1] - (g_meas[1] + self._b_a[1])
        residual_z = g_ref[2] - (g_meas[2] + self._b_a[2])

        residual_mag = math.sqrt(
            residual_x ** 2 + residual_y ** 2 + residual_z ** 2
        )

        # Track best-so-far for degraded path
        if residual_mag < self._best_residual_mag:
            self._best_residual_mag = residual_mag
            self._best_b_a = self._b_a

        # Closed-form update: b_a += mu * (g_ref - g_meas_corrected)
        self._b_a = (
            self._b_a[0] + self.mu * residual_x,
            self._b_a[1] + self.mu * residual_y,
            self._b_a[2] + self.mu * residual_z,
        )

        # Settled check
        if residual_mag < self.settle_mg:
            self._settle_count += 1
            if self._settle_count >= self.settle_ticks:
                self._settled = True
        else:
            self._settle_count = 0

        # Degraded: hard timeout
        if not self._settled and self._tick >= self.max_ticks:
            self._degraded = True
            self._b_a = self._best_b_a

        return self._b_a


# ------------------------------------------------------------------
# Phase 4 — Gyro hot-bias FSM (mirrors OF bias FSM in StabilizerTask.c)
# ------------------------------------------------------------------

# FSM states
_GYRO_WAIT_STILL = 0
_GYRO_ACCUM = 1
_GYRO_COMMIT = 2


class GyroBiasHotFsm:
    """Phase 4: gyro hot-bias finite-state machine.

    Mirrors TASK/StabilizerTask.c:46-143 (OF-bias estimator) applied to gyro.

    Transitions (all guards checked every tick; any guard violation resets
    to WAIT_STILL and marks rejected=True):

        WAIT_STILL:
            still_guard: |gyro|_xyz < still_thresh
            flying_guard: flight_phase_flying
            rc_guard: not rc_active
            trans_guard: |lin_acc_xy[0]| + |lin_acc_xy[1]| < lin_acc_thresh_mg
            -> still_count++ ; on reaching still_ticks -> ACCUM

        ACCUM:
            same guards as WAIT_STILL (maintained every tick)
            -> acc_count++ ; gyro sum integrated
            on reaching acc_ticks -> COMMIT

        COMMIT:
            b_g = (1-alpha)*b_g + alpha*sample_mean
            -> WAIT_STILL

    Args:
        still_thresh: gyro stillness gate, rad/s (~3 deg/s).
        still_ticks: ticks at 200 Hz to dwell in WAIT_STILL before ACCUM.
        acc_ticks: ticks at 200 Hz for gyro sample averaging.
        alpha: EWMA filter gain for bias commit (1e-4 = very slow, safe).
        lin_acc_thresh_mg: translational guard threshold, mg.
    """

    def __init__(
        self,
        still_thresh: float = 0.05,
        still_ticks: int = 100,
        acc_ticks: int = 400,
        alpha: float = 1e-4,
        lin_acc_thresh_mg: float = 50.0,
    ):
        self.still_thresh = still_thresh
        self.still_ticks = still_ticks
        self.acc_ticks = acc_ticks
        self.alpha = alpha
        self.lin_acc_thresh_mg = lin_acc_thresh_mg

        self._state = _GYRO_WAIT_STILL
        self._b_g = (0.0, 0.0, 0.0)
        self._rejected = False
        self._still_count = 0
        self._acc_count = 0
        self._sample_sum = (0.0, 0.0, 0.0)

    @property
    def b_g(self) -> tuple[float, float, float]:
        return self._b_g

    def _reset_to_wait(self) -> None:
        self._state = _GYRO_WAIT_STILL
        self._still_count = 0
        self._acc_count = 0
        self._sample_sum = (0.0, 0.0, 0.0)
        self._rejected = True

    def _enter_commit(self) -> None:
        """Compute sample mean and apply EWMA update to b_g."""
        n = self.acc_ticks
        mean_x = self._sample_sum[0] / n
        mean_y = self._sample_sum[1] / n
        mean_z = self._sample_sum[2] / n
        a = self.alpha
        self._b_g = (
            (1.0 - a) * self._b_g[0] + a * mean_x,
            (1.0 - a) * self._b_g[1] + a * mean_y,
            (1.0 - a) * self._b_g[2] + a * mean_z,
        )
        self._state = _GYRO_WAIT_STILL
        self._still_count = 0
        self._acc_count = 0
        self._sample_sum = (0.0, 0.0, 0.0)

    def update(
        self,
        gyro: tuple[float, float, float],
        lin_acc_xy: tuple[float, float, float],
        flight_phase_flying: bool,
        rc_active: bool,
    ) -> dict:
        """Advance the gyro FSM one tick.

        Returns:
            dict with keys:
                state (int): current FSM state (0=WAIT_STILL, 1=ACCUM, 2=COMMIT).
                b_g (tuple): current gyro bias estimate, rad/s.
                rejected (bool): HOT_REJECTED telemetry bit; set whenever
                    WAIT_STILL is reset mid-window.
        """
        self._rejected = False

        # Guard 1: RC must be idle
        if rc_active:
            self._reset_to_wait()
            return {
                "state": self._state,
                "b_g": self._b_g,
                "rejected": self._rejected,
            }

        # Guard 2: must be in FLYING phase
        if not flight_phase_flying:
            self._reset_to_wait()
            return {
                "state": self._state,
                "b_g": self._b_g,
                "rejected": self._rejected,
            }

        # Translational guard: |lin_acc_x| + |lin_acc_y| < threshold
        trans_guard = (
            abs(lin_acc_xy[0]) + abs(lin_acc_xy[1]) < self.lin_acc_thresh_mg
        )

        # Stillness guard
        still_guard = (
            abs(gyro[0]) < self.still_thresh
            and abs(gyro[1]) < self.still_thresh
            and abs(gyro[2]) < self.still_thresh
        )

        if not still_guard or not trans_guard:
            self._reset_to_wait()
            return {
                "state": self._state,
                "b_g": self._b_g,
                "rejected": self._rejected,
            }

        if self._state == _GYRO_WAIT_STILL:
            self._still_count += 1
            if self._still_count >= self.still_ticks:
                self._state = _GYRO_ACCUM

        elif self._state == _GYRO_ACCUM:
            self._sample_sum = (
                self._sample_sum[0] + gyro[0],
                self._sample_sum[1] + gyro[1],
                self._sample_sum[2] + gyro[2],
            )
            self._acc_count += 1
            if self._acc_count >= self.acc_ticks:
                self._enter_commit()

        # COMMITTED state: just stay there; no further accumulation until
        # the next quiescent window (mirrors firmware: refresh, don't freeze)

        return {
            "state": self._state,
            "b_g": self._b_g,
            "rejected": self._rejected,
        }
