"""Baseline inner-loop rate PID — PARITY: API/pid.c ComputePID + gains in Ctrler[].

This is the nominal controller the MRAC augments. The plant boundary is the rate
loop (ADR-0006 D3), so only the *inner* rate PIDs matter here: gyrox (roll-rate),
gyroy (pitch-rate), gyroz (yaw-rate) from pid.c. Outer angle/position loops are
out of scope for Phase 1.

UNIT CHAIN (the firmware's, reproduced exactly so the sim-to-hardware gap stays
small):
    setpoint/feedback : deg/s        (gyroPID.Des / .FB are deg/s)
    PID output  U     : mixer units  (clamped to +/-UMax)
    u_nom = U / mrac_to_mixer        : Nm   (mrac.c:458-460; the regressor's slot-4
                                              and the identified plant's input, which
                                              was identified as u_nom -> rate, see
                                              docs/sysid_results.md line 73)
    plant output      : rad/s        (identified K is rad/s per Nm; MRAC x is rad/s)

The runner converts rad/s<->deg/s at this module's boundary. mrac_to_mixer uses the
active-build value (ACTIVE_PAYLOAD = PAYLOAD_LIGHT -> 1170 P/R, 1872 yaw; mrac.h:36-40).

The PID is the firmware's *positional* form with its exact quirks replicated:
  * conditional integration: integrate only when not output-saturated in the error's
    direction AND |E| < EMin (pid.c:36-40) -- EMin is an integrate-near-setpoint band;
  * every term clamped independently (Up/Ui/Ud) then the sum clamped to +/-UMax;
  * derivative on error, raw first difference Kd*(E - PreE) -- NOT divided by dt.
"""
from __future__ import annotations

from dataclasses import dataclass

DEG2RAD = 0.0174533
RAD2DEG = 1.0 / DEG2RAD


def _clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


@dataclass
class RatePIDConfig:
    """One inner rate-loop PID (pid.c Ctrler[] row) + its Nm->mixer scaler."""
    Kp: float
    Ki: float
    Kd: float
    UMax: float
    UpMax: float
    UiMax: float
    UdMax: float
    SumEMax: float
    EMin: float
    mrac_to_mixer: float

    # gyrox/gyroy/gyroz rows (pid.c:13-15) + mrac_to_mixer (mrac.h:36-40, LIGHT)
    @classmethod
    def for_axis(cls, axis: str) -> "RatePIDConfig":
        if axis in ("roll", "pitch"):  # gyrox / gyroy are identical
            return cls(Kp=5.0, Ki=0.01, Kd=10.0, UMax=300.0, UpMax=300.0,
                       UiMax=20.0, UdMax=100.0, SumEMax=1000.0, EMin=2.0,
                       mrac_to_mixer=1170.0)
        if axis == "yaw":          # gyroz
            return cls(Kp=8.0, Ki=0.001, Kd=0.02, UMax=250.0, UpMax=250.0,
                       UiMax=60.0, UdMax=10.0, SumEMax=2000.0, EMin=20.0,
                       mrac_to_mixer=1872.0)
        raise ValueError(f"no inner-rate PID config for axis {axis!r}")


class RatePID:
    """Firmware ComputePID (pid.c:32-55), positional form, deg/s in -> mixer U out."""

    def __init__(self, config: RatePIDConfig):
        self.cfg = config
        self.reset()

    def reset(self) -> None:
        self.SumE = 0.0
        self.PreE = 0.0
        self.U = 0.0
        self.Up = self.Ui = self.Ud = 0.0

    def step(self, des: float, fb: float) -> float:
        """One tick: setpoint/feedback in deg/s -> clamped mixer output U."""
        c = self.cfg
        E = des - fb
        # conditional integration (anti-windup + integrate-near-setpoint band)
        if (((self.U <= c.UMax and E > 0.0) or (self.U >= -c.UMax and E < 0.0))
                and abs(E) < c.EMin):
            self.SumE += E
        self.SumE = _clamp(self.SumE, -c.SumEMax, c.SumEMax)
        self.Ui = _clamp(c.Ki * self.SumE, -c.UiMax, c.UiMax)
        self.Up = _clamp(c.Kp * E, -c.UpMax, c.UpMax)
        self.Ud = _clamp(c.Kd * (E - self.PreE), -c.UdMax, c.UdMax)
        self.U = _clamp(self.Up + self.Ui + self.Ud, -c.UMax, c.UMax)
        self.PreE = E
        return self.U

    def u_nom(self) -> float:
        """Latest output mapped to Nm (mrac.c:458-460): u_nom = U / mrac_to_mixer."""
        return self.U / self.cfg.mrac_to_mixer
