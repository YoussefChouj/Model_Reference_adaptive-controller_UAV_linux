"""Outer control loops — attitude and position (spec 4a).

Three cascaded loops, all running at the firmware controller tick
(``dt = 0.005 s``, 200 Hz) so the unit chain matches what the firmware
executes. The plant integration may be RK4 internally; the controller
recurrences stay forward-Euler to keep firmware parity (ADR-0006 D1).

    Position loop   (outer, m + m/s)   -> desired attitude + thrust
        |
    Attitude loop   (mid, rad + rad/s) -> desired body rates
        |
    Rate loop       (inner, rad/s)     -> motor torques  [firmware MRAC + PID]

The rate loop is the existing ``ControlLoop`` (``sim.loop``) and the
MRAC law (``sim.adaptive_law``); this module adds the two outer loops
above it. A single ``OuterLoop.tick(state) -> u_dict`` call drives
the whole cascade.

The loops are intentionally simple P/PI controllers with no anti-windup
machinery — saturation is handled by the actuator model inside the
plant (``RigidBodyPlant`` clips motor thrust at 0 / per-motor max). The
**purpose** of these loops is to give the trajectory scenarios a
controllable target (position/attitude), not to design the thesis
tracking controller. Spec 4a builds the *environment*; the controller
itself is thesis work.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


# Per-axis firmware outer-loop gains (firmware docs/TODO; these are
# the values used in flight logs and are documented in
# docs/progress.md as "baseline, not retuned"). Per-axis gains, not
# shared, because of the 10.9 % pitch-roll inertia asymmetry.
@dataclass(frozen=True)
class OuterLoopGains:
    """Position + attitude loop gains (firmware baseline, per-axis)."""
    # attitude: phi (roll), theta (pitch), psi (yaw) commands.
    att_kp: tuple  # (roll_kp, pitch_kp, yaw_kp), rad/s per rad
    att_kd: tuple  # (roll_kd, pitch_kd, yaw_kd), rad/s per rad/s
    # position: x, y, z commands. Z has its own set (centred in m, vel m/s).
    pos_kp: tuple  # (x_kp, y_kp, z_kp), m/s per m
    pos_ki: tuple  # (x_ki, y_ki, z_ki), m/s per m*s
    # Maximum commanded attitude (rad) and rate (rad/s). Reasonable
    # bounds for a small quad; tuned for safety in the analytic sim.
    max_roll_pitch: float = 0.5    # rad, ~30 deg
    max_yaw_rate: float = 1.5     # rad/s
    max_horizontal_vel: float = 2.0  # m/s
    max_climb_rate: float = 1.5    # m/s
    # Minimum throttle to prevent the integrator from commanding zero
    # thrust at hover-trim. Defaults to the analytical hover thrust.
    hover_thrust: float = 0.0      # N, computed at construction if 0

    @classmethod
    def baseline(cls, mass: float, gravity: float = 9.80665) -> "OuterLoopGains":
        """Conservative first-baseline outer-loop gains.

        The 6-DOF plant is high-order and lightly damped; aggressive
        outer-loop gains excite attitude dynamics and produce
        divergence. These gains are deliberately conservative so the
        closed-loop trajectory runs complete without saturating; the
        developer can retune as thesis work. Per-axis, not shared,
        because of the 10.9 % pitch-roll inertia asymmetry.
        """
        hov = mass * gravity
        return cls(
            att_kp=(8.0, 7.6, 5.0),     # roll, pitch (-5 % for Iyy), yaw
            att_kd=(1.2, 1.2, 0.8),
            pos_kp=(1.5, 1.5, 1.5),     # m/s per m -> moderate
            pos_ki=(0.0, 0.0, 0.05),    # Z integrator (very weak, anti-windup)
            max_roll_pitch=0.5,         # rad, ~30 deg
            max_yaw_rate=2.0,           # rad/s
            max_horizontal_vel=3.0,     # m/s
            max_climb_rate=1.0,         # m/s
            hover_thrust=hov,
        )


class _RateLimit:
    """Slew-rate limit on a scalar signal."""
    def __init__(self, rate_max: float, dt: float):
        self.rate_max = rate_max
        self.dt = dt

    def __call__(self, x: float, prev: float) -> float:
        dx = x - prev
        lim = self.rate_max * self.dt
        if dx > lim:
            return prev + lim
        if dx < -lim:
            return prev - lim
        return x


class OuterLoop:
    """Attitude + position outer loops (spec 4a). One per drone.

    ``tick(state, target) -> u_dict`` produces the per-axis command
    dict that the rate loop + MRAC consume. ``state`` is a state dict
    as returned by ``RigidBodyPlant.step``; ``target`` is the desired
    pose (position, attitude, yaw) at this tick.

    The loops use anti-windup on the Z integrator and saturation on
    the velocity commands to prevent unbounded growth during
    transient errors.
    """

    def __init__(self, *, dt: float = 0.005,
                 gains: OuterLoopGains | None = None,
                 mass: float = 1.2961, gravity: float = 9.80665):
        self.dt = dt
        self.gains = gains if gains is not None else OuterLoopGains.baseline(
            mass, gravity)
        if self.gains.hover_thrust <= 0.0:
            self.gains = OuterLoopGains(
                att_kp=self.gains.att_kp, att_kd=self.gains.att_kd,
                pos_kp=self.gains.pos_kp, pos_ki=self.gains.pos_ki,
                max_roll_pitch=self.gains.max_roll_pitch,
                max_yaw_rate=self.gains.max_yaw_rate,
                max_horizontal_vel=self.gains.max_horizontal_vel,
                max_climb_rate=self.gains.max_climb_rate,
                hover_thrust=mass * gravity,
            )
        # Integrators (Z only — horizontal position has zero Ki by default).
        self._pos_int = np.zeros(3)
        # Slew-rate limiters.
        self._lim_roll = _RateLimit(self.gains.max_yaw_rate, dt)
        self._lim_pitch = _RateLimit(self.gains.max_yaw_rate, dt)
        self._lim_yaw = _RateLimit(self.gains.max_yaw_rate, dt)
        self._lim_vx = _RateLimit(self.gains.max_horizontal_vel, dt)
        self._lim_vy = _RateLimit(self.gains.max_horizontal_vel, dt)
        self._lim_vz = _RateLimit(self.gains.max_climb_rate, dt)

    def reset(self) -> None:
        self._pos_int = np.zeros(3)
        self._last_roll_cmd = 0.0
        self._last_pitch_cmd = 0.0
        self._last_yaw_cmd = 0.0
        self._last_vx_cmd = 0.0
        self._last_vy_cmd = 0.0
        self._last_vz_cmd = 0.0

    def tick(self, state: dict, target: dict) -> dict:
        """Compute one outer-loop tick.

        ``state`` carries the keys returned by ``RigidBodyPlant.step``:
        ``x,y,z,vx,vy,vz,phi,theta,psi,p,q,r``.
        ``target`` carries the desired pose: ``x,y,z,yaw`` (all optional;
        missing keys hold their current value).
        Returns ``u`` in firmware u-units (Nm for roll/pitch/yaw, N for z).
        """
        # 1. Position loop: desired position -> desired velocity, with
        #    saturation to prevent runaway commands.
        x_t = float(target.get("x", state["x"]))
        y_t = float(target.get("y", state["y"]))
        z_t = float(target.get("z", state["z"]))
        vx_t = (x_t - state["x"]) * self.gains.pos_kp[0]
        vy_t = (y_t - state["y"]) * self.gains.pos_kp[1]
        # Z integrator with anti-windup: only integrate if the
        # integrator output would not push the climb-rate command
        # past saturation.
        vz_t_raw = (z_t - state["z"]) * self.gains.pos_kp[2]
        cand_int = self._pos_int[2] + vz_t_raw * self.dt
        cand_vz = vz_t_raw + cand_int * self.gains.pos_ki[2]
        # Climb-rate saturation check.
        max_vz = self.gains.max_climb_rate
        if abs(cand_vz) > max_vz:
            # Don't grow the integrator further (clamping / anti-windup).
            cand_int = self._pos_int[2]
        self._pos_int[2] = cand_int
        vz_t = vz_t_raw + cand_int * self.gains.pos_ki[2]
        # Saturation on velocity commands (the position loop's output
        # is velocity, not attitude directly; attitude derives from it).
        vx_t = float(np.clip(vx_t,
                             -self.gains.max_horizontal_vel,
                             self.gains.max_horizontal_vel))
        vy_t = float(np.clip(vy_t,
                             -self.gains.max_horizontal_vel,
                             self.gains.max_horizontal_vel))
        vz_t = float(np.clip(vz_t,
                             -self.gains.max_climb_rate,
                             self.gains.max_climb_rate))
        # Slew-limit the velocity commands.
        vx_t = self._lim_vx(vx_t, getattr(self, "_last_vx_cmd", 0.0))
        vy_t = self._lim_vy(vy_t, getattr(self, "_last_vy_cmd", 0.0))
        vz_t = self._lim_vz(vz_t, getattr(self, "_last_vz_cmd", 0.0))
        self._last_vx_cmd, self._last_vy_cmd, self._last_vz_cmd = vx_t, vy_t, vz_t
        # 2. Velocity -> attitude (NED, body-x forward). For a small
        #    quad at low speed, desired attitude = K_v * velocity error,
        #    with the standard "pitch forward to move forward" sign.
        #    Position loop outer; attitude inner; commanded in radians.
        vx_err = vx_t - state["vx"]
        vy_err = vy_t - state["vy"]
        # In NED with body x forward, a positive body-x velocity requires
        # a negative body-y rotation (nose-down tilt): theta_des = -vx_err / g
        theta_des = -vx_err / 9.80665
        phi_des = vy_err / 9.80665
        # Clamp.
        theta_des = float(np.clip(theta_des,
                                  -self.gains.max_roll_pitch,
                                  self.gains.max_roll_pitch))
        phi_des = float(np.clip(phi_des,
                                -self.gains.max_roll_pitch,
                                self.gains.max_roll_pitch))
        yaw_t = float(target.get("yaw", state["psi"]))
        # Wrap yaw error to (-pi, pi].
        yaw_err = (yaw_t - state["psi"] + np.pi) % (2 * np.pi) - np.pi
        # 3. Attitude loop: desired attitude -> desired body rates.
        roll_err = phi_des - state["phi"]
        pitch_err = theta_des - state["theta"]
        yaw_err_clamped = float(np.clip(yaw_err,
                                        -self.gains.max_yaw_rate,
                                        self.gains.max_yaw_rate))
        # Per-axis PD.
        roll_rate_des = (
            self.gains.att_kp[0] * roll_err
            - self.gains.att_kd[0] * state["p"]
        )
        pitch_rate_des = (
            self.gains.att_kp[1] * pitch_err
            - self.gains.att_kd[1] * state["q"]
        )
        yaw_rate_des = (
            self.gains.att_kp[2] * yaw_err_clamped
            - self.gains.att_kd[2] * state["r"]
        )
        # Saturate the rate commands to a hard maximum so the inner
        # rate loop never sees an unbounded demand.
        max_rate = self.gains.max_yaw_rate
        roll_rate_des = float(np.clip(roll_rate_des, -max_rate, max_rate))
        pitch_rate_des = float(np.clip(pitch_rate_des, -max_rate, max_rate))
        yaw_rate_des = float(np.clip(yaw_rate_des, -max_rate, max_rate))
        # Slew-limit the rate commands.
        roll_rate_des = self._lim_roll(roll_rate_des,
                                       getattr(self, "_last_roll_cmd", 0.0))
        pitch_rate_des = self._lim_pitch(pitch_rate_des,
                                         getattr(self, "_last_pitch_cmd", 0.0))
        yaw_rate_des = self._lim_yaw(yaw_rate_des,
                                     getattr(self, "_last_yaw_cmd", 0.0))
        self._last_roll_cmd = roll_rate_des
        self._last_pitch_cmd = pitch_rate_des
        self._last_yaw_cmd = yaw_rate_des
        # 4. Hover thrust + vertical command -> total Z command (N).
        #    Thrust-to-climb-rate conversion: extra thrust = m * a_climb,
        #    where a_climb is the acceleration to maintain commanded
        #    climb rate in the presence of translational drag.
        #    Steady-state at v_max (max_climb_rate): a_climb = 0,
        #    so thrust = hover (after drag balances gravity).
        #    To accelerate from 0 to v_max in 1 s: a_climb = v_max.
        #    Use a fraction of v_max as the required dthrust gain:
        #    dthrust = m * 1.0 * vz_t (gain = 1.0 m/s^2 per m/s).
        m = float(target.get("mass", 1.2961))
        dthrust_gain = 1.0 * m  # N per (m/s) of climb rate
        dthrust = dthrust_gain * vz_t
        thrust_total = self.gains.hover_thrust + dthrust
        # Saturate thrust to a maximum of 2x hover (firmware's mixer
        # can command up to ~1.5x before saturation; we cap at 2x).
        thrust_total = float(np.clip(thrust_total,
                                     0.0,
                                     self.gains.hover_thrust * 2.0))
        # Return in firmware u-units: roll/pitch/yaw = rad/s (rate command
        # in MRAC space); z = N (total thrust, the analytic plant
        # converts to per-motor PWM internally).
        return {
            "roll": float(roll_rate_des),
            "pitch": float(pitch_rate_des),
            "yaw": float(yaw_rate_des),
            "z": float(thrust_total),
        }