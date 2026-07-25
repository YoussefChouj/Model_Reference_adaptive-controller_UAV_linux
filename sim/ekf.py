"""9-state body-frame Extended Kalman Filter — ADR-0011 parallel estimator.

State vector: [v_body[3], b_a_body[3], b_g_body[3]] — 9 states, body frame.

Predict step: constant-velocity model with body-frame acceleration as input.
    v_body[k+1] = v_body[k] + (a_body[k] - b_a_body[k]) * dt
    b_a_body, b_g_body are random-walk (no direct dynamics).

Measurement updates:
    OF velocity (XY)   -> update v_body[0], v_body[1]
    Body-lin accel XY -> update v_body[0], v_body[1]
    Z-rate            -> update v_body[2]

All values in SI (m/s, m/s², rad/s).
"""
from __future__ import annotations

import numpy as np


class Ekf9State:
    """9-state body-frame EKF. State: [v_body[3], b_a_body[3], b_g_body[3]]."""

    def __init__(
        self,
        q_v: float = 1e-3,
        q_ba: float = 1e-6,
        q_bg: float = 5e-9,
        r_of: float = 6.16e-4,
        r_acc: float = 0.005,
        r_z: float = 0.04,
        dt: float = 0.001,
    ):
        self.dt = dt
        self.q_v = q_v
        self.q_ba = q_ba
        self.q_bg = q_bg
        self.r_of = r_of
        self.r_acc = r_acc
        self.r_z = r_z

        self.x = np.zeros(9, dtype=np.float64)
        self.P = np.diag([q_v, q_v, q_v, q_ba, q_ba, q_ba, q_bg, q_bg, q_bg])
        self.nis = 0.0
        self._K_of = np.zeros(3)

    # ------------------------------------------------------------------
    # Public accessors
    # ------------------------------------------------------------------
    @property
    def v_body(self) -> tuple:
        return tuple(self.x[0:3])

    @property
    def b_a_body(self) -> tuple:
        return tuple(self.x[3:6])

    @property
    def b_g_body(self) -> tuple:
        return tuple(self.x[6:9])

    @property
    def p_diag(self) -> tuple:
        return tuple(np.diag(self.P).tolist())

    @property
    def kalman_gain(self) -> tuple:
        return tuple(self._K_of.tolist())

    # ------------------------------------------------------------------
    # Predict step — constant-velocity model, biases are random-walk
    # ------------------------------------------------------------------
    def predict(self, a_body: tuple, gyro: tuple, dt: float | None = None):
        """Predict step.

        a_body: body-frame specific force, gravity NOT removed (caller removes).
        gyro:   body-frame angular rate, rad/s.
        dt:     step size; defaults to construction-time dt.
        """
        if dt is None:
            dt = self.dt

        q_v = self.q_v
        q_ba = self.q_ba
        q_bg = self.q_bg

        # 9x9 Jacobian of f(x) w.r.t. state:
        #   v_body += (a_body - b_a_body) * dt
        #   b_a_body, b_g_body: no dynamics (identity)
        F = np.eye(9, dtype=np.float64)
        F[0, 3] = -dt  # dv_x / d b_a_x
        F[1, 4] = -dt  # dv_y / d b_a_y
        F[2, 5] = -dt  # dv_z / d b_a_z

        # Process noise covariance (discretised)
        Q = np.diag([
            q_v * dt * dt,
            q_v * dt * dt,
            q_v * dt * dt,
            q_ba,
            q_ba,
            q_ba,
            q_bg,
            q_bg,
            q_bg,
        ])

        # State update: x = f(x) — v_body propagates by (a_body - b_a) * dt
        ax, ay, az = a_body
        bx, by, bz = self.x[3], self.x[4], self.x[5]
        self.x[0] += (ax - bx) * dt
        self.x[1] += (ay - by) * dt
        self.x[2] += (az - bz) * dt
        # b_a and b_g are random-walk: x unchanged for indices 3..8

        # Covariance: P = F @ P @ F.T + Q
        self.P = F @ self.P @ F.T + Q

        # NIS reset on predict
        self.nis = 0.0

    # ------------------------------------------------------------------
    # Measurement updates
    # ------------------------------------------------------------------
    def update_of(self, of_vel_xy: tuple):
        """Optical-flow velocity measurement (m/s), body XY.

        Measurement model: z = H @ x + v
        H = [[1,0,0, 0,0,0, 0,0,0],
             [0,1,0, 0,0,0, 0,0,0]]
        z = [v_body[0], v_body[1]] + noise
        """
        H = np.zeros((2, 9), dtype=np.float64)
        H[0, 0] = 1.0
        H[1, 1] = 1.0

        R = np.diag([self.r_of, self.r_of])

        z = np.array(of_vel_xy, dtype=np.float64)
        x_pred = self.x[0:2]

        innovation = z - x_pred
        S = H @ self.P @ H.T + R
        K = self.P @ H.T @ np.linalg.inv(S)

        self.x = self.x + K @ innovation
        # Symmetric update: P = (I - K H) P (I - K H).T + K R K.T
        I_KH = np.eye(9) - K @ H
        self.P = I_KH @ self.P @ I_KH.T + K @ R @ K.T

        self.nis = float(innovation @ np.linalg.solve(S, innovation))
        self._K_of = K[0:3, 0].copy()  # Kalman gain for X (first column of K)

    def update_acc_xy(self, lin_acc_xy: tuple):
        """Body-frame linear acceleration XY measurement (m/s²), gravity removed.

        Measurement model: z = H @ x + v
        H selects v_body[0] and v_body[1] (the same observation as OF).
        In a body-frame EKF with a constant-velocity predict, the measurement
        residual z - Hx tells us how much the velocity estimate is off — the
        acceleration bias lives in the predict step, not directly in the
        measurement model, so the Jacobians and update are identical to OF.
        """
        H = np.zeros((2, 9), dtype=np.float64)
        H[0, 0] = 1.0
        H[1, 1] = 1.0

        R = np.diag([self.r_acc, self.r_acc])

        z = np.array(lin_acc_xy, dtype=np.float64)
        x_pred = self.x[0:2]

        innovation = z - x_pred
        S = H @ self.P @ H.T + R
        K = self.P @ H.T @ np.linalg.inv(S)

        self.x = self.x + K @ innovation
        I_KH = np.eye(9) - K @ H
        self.P = I_KH @ self.P @ I_KH.T + K @ R @ K.T

        self.nis = float(innovation @ np.linalg.solve(S, innovation))

    def update_z_rate(self, z_rate: float):
        """Z-rate measurement (m/s), altitude derivative.

        H = [[0,0,1, 0,0,0, 0,0,0]]
        z = v_body[2] + noise
        """
        H = np.zeros((1, 9), dtype=np.float64)
        H[0, 2] = 1.0

        r_z = self.r_z

        innovation = z_rate - self.x[2]
        s_zz = self.P[2, 2] + r_z
        K = self.P[:, 2:3] / s_zz          # 9×1 Kalman gain

        self.x = self.x + K.flatten() * innovation

        I_KH = np.eye(9) - K * H           # 9×9 outer-product form
        self.P = I_KH @ self.P @ I_KH.T + self.r_z * (K @ K.T)

        self.nis = innovation ** 2 / r_z
