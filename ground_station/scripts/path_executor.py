"""
Ground-station path follower: 10 Hz virtual stick commands (CMD 0x06).

Firmware only applies CMD 0x06 when sbus_lost and FlyMode_SDK �� plan bench /
simulation accordingly.
"""
from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple


class PositionSourceError(RuntimeError):
    pass


@dataclass
class Waypoint:
    x: float
    y: float
    z: float
    speed: float = 0.5
    hold_s: float = 0.0


def _stick_from_error(err_m: float, gain: float = 0.5) -> float:
    """Return a normalised stick value in [-1.0, +1.0] for CMD 0x06."""
    return max(-1.0, min(1.0, err_m * gain))


class PathExecutor:
    def __init__(
        self,
        send_cmd: Callable[[int, int, float], None],
        get_telemetry: Callable[[], Tuple[Dict[str, float], Dict[str, float]]],
        should_abort: Callable[[], bool],
        get_position_source: Callable[[], str],
    ) -> None:
        self._send_cmd = send_cmd
        self._get_telemetry = get_telemetry
        self._should_abort = should_abort
        self._get_position_source = get_position_source
        self._thread: Optional[threading.Thread] = None
        self._sim_xyz = [0.0, 0.0, 0.0]

    def abort(self) -> None:
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        self._thread = None

    def _source_ok(self) -> str:
        s = self._get_position_source()
        if s in ("None", ""):
            raise PositionSourceError("Enable a position source first")
        if s in ("SLAM", "GPS"):
            raise PositionSourceError("Position source not available yet")
        return s

    def _feedback(self, src: str) -> Tuple[float, float, float]:
        _, b = self._get_telemetry()
        if src == "Simulation":
            return (self._sim_xyz[0], self._sim_xyz[1], self._sim_xyz[2])
        return (
            float(b.get("pid.locx.FB", 0.0)),
            float(b.get("pid.locy.FB", 0.0)),
            float(b.get("pid.z_pos.FB", 0.0)),
        )

    def _send_sticks(self, thr: float, pit: float, rol: float, yaw: float) -> None:
        for i, v in enumerate([thr, pit, rol, yaw]):
            self._send_cmd(0x06, i, float(v))

    def _sim_integrate(self, thr: float, pit: float, rol: float, dt: float) -> None:
        self._sim_xyz[0] += pit * 0.4 * dt
        self._sim_xyz[1] += rol * 0.4 * dt
        self._sim_xyz[2] += thr * 0.15 * dt

    def _loop_body(self, src: str) -> None:
        dt = 0.1
        while not self._should_abort():
            px, py, pz = self._feedback(src)
            # placeholder �� subclasses set target via closure
            return

    def execute_point_to_point(
        self,
        start: Tuple[float, float, float],
        end: Tuple[float, float, float],
        speed_mps: float,
    ) -> None:
        def run() -> None:
            try:
                src = self._source_ok()
                if src == "Simulation":
                    self._sim_xyz = [start[0], start[1], start[2]]
                dist = math.sqrt(sum((end[i] - start[i]) ** 2 for i in range(3)))
                duration = max(0.5, dist / max(0.1, speed_mps))
                t0 = time.monotonic()
                while time.monotonic() - t0 < duration and not self._should_abort():
                    u = (time.monotonic() - t0) / duration
                    tx = start[0] + (end[0] - start[0]) * u
                    ty = start[1] + (end[1] - start[1]) * u
                    tz = start[2] + (end[2] - start[2]) * u
                    px, py, pz = self._feedback(src)
                    thr = _stick_from_error(tz - pz, 0.4)
                    pit = _stick_from_error(-(tx - px), 0.35)
                    rol = _stick_from_error(-(ty - py), 0.35)
                    self._send_sticks(thr, pit, rol, 0.0)
                    if src == "Simulation":
                        self._sim_integrate(thr, pit, rol, 0.1)
                    time.sleep(0.1)
            except PositionSourceError:
                pass

        self.abort()
        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()

    def execute_sinusoidal(
        self,
        center: Tuple[float, float, float],
        axis: str,
        amplitude: float,
        freq_hz: float,
        duration_s: float,
    ) -> None:
        def run() -> None:
            try:
                src = self._source_ok()
                if src == "Simulation":
                    self._sim_xyz = [center[0], center[1], center[2]]
                t0 = time.monotonic()
                while time.monotonic() - t0 < duration_s and not self._should_abort():
                    tt = time.monotonic() - t0
                    off = amplitude * math.sin(2 * math.pi * freq_hz * tt)
                    tx, ty, tz = center[0], center[1], center[2]
                    ax = axis.upper()
                    if ax == "X":
                        tx += off
                    elif ax == "Y":
                        ty += off
                    else:
                        tz += off
                    px, py, pz = self._feedback(src)
                    self._send_sticks(
                        _stick_from_error(tz - pz),
                        _stick_from_error(-(tx - px)),
                        _stick_from_error(-(ty - py)),
                        0.0,
                    )
                    if src == "Simulation":
                        self._sim_integrate(
                            _stick_from_error(tz - pz),
                            _stick_from_error(-(tx - px)),
                            _stick_from_error(-(ty - py)),
                            0.1,
                        )
                    time.sleep(0.1)
            except PositionSourceError:
                pass

        self.abort()
        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()

    def execute_circle(
        self,
        center: Tuple[float, float, float],
        radius: float,
        speed_mps: float,
        cw: bool,
    ) -> None:
        def run() -> None:
            try:
                src = self._source_ok()
                if src == "Simulation":
                    self._sim_xyz = [center[0] + radius, center[1], center[2]]
                omega = speed_mps / max(0.5, radius)
                if not cw:
                    omega = -omega
                t0 = time.monotonic()
                while time.monotonic() - t0 < 120.0 and not self._should_abort():
                    tt = time.monotonic() - t0
                    ang = omega * tt
                    tx = center[0] + radius * math.cos(ang)
                    ty = center[1] + radius * math.sin(ang)
                    tz = center[2]
                    px, py, pz = self._feedback(src)
                    self._send_sticks(
                        _stick_from_error(tz - pz),
                        _stick_from_error(-(tx - px)),
                        _stick_from_error(-(ty - py)),
                        0.0,
                    )
                    if src == "Simulation":
                        self._sim_integrate(
                            _stick_from_error(tz - pz),
                            _stick_from_error(-(tx - px)),
                            _stick_from_error(-(ty - py)),
                            0.1,
                        )
                    if tt > 2 * math.pi / max(1e-3, abs(omega)) + 0.5:
                        break
                    time.sleep(0.1)
            except PositionSourceError:
                pass

        self.abort()
        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()

    def execute_waypoints(self, wps: List[Waypoint]) -> None:
        def run() -> None:
            try:
                src = self._source_ok()
                for wp in wps:
                    t_end = time.monotonic() + max(0.0, wp.hold_s) + 2.0
                    while time.monotonic() < t_end and not self._should_abort():
                        px, py, pz = self._feedback(src)
                        ex, ey, ez = wp.x - px, wp.y - py, wp.z - pz
                        if math.sqrt(ex * ex + ey * ey + ez * ez) < 0.08:
                            break
                        self._send_sticks(
                            _stick_from_error(ez),
                            _stick_from_error(-ex),
                            _stick_from_error(-ey),
                            0.0,
                        )
                        if src == "Simulation":
                            self._sim_integrate(
                                _stick_from_error(ez),
                                _stick_from_error(-ex),
                                _stick_from_error(-ey),
                                0.1,
                            )
                        time.sleep(0.1)
            except PositionSourceError:
                pass

        self.abort()
        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()
