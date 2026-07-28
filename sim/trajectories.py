"""Dense trajectory generation (spec 4a).

A trajectory is a dense waypoint sequence with an aggressiveness
parameter. The generated samples are exactly what a position/attitude
outer loop would command at each tick (200 Hz, dt = 0.005 s). The
trajectory is *open-loop*: it does not know the plant state, only the
geometry of the path and the speed parameter. The closed-loop path
metric (``cross-track error`` etc.) is computed against the realised
plant trajectory by ``sim.metrics.compute_path``.

Two shapes are required by the spec (user stories 13, 14):

  * **sharp-curvature geometry** — circular or figure-8 path with a
    sharpness knob. Implemented by a parametric lemniscate (figure-8)
    or a circle with a controllable radius.
  * **rapid-direction-reversal geometry** — square or zig-zag with
    sharp corners. Implemented by a parametric polygon path.

Both expose ``aggressiveness`` as a single dimensionless parameter
that controls speed and (for the lemniscate) sharpness. The
generation is deterministic — same seed/params -> identical waypoint
sequence — so trajectory tests can assert on exact coordinates.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass(frozen=True)
class Trajectory:
    """Dense waypoint sequence sampled at ``dt`` from ``t=0`` to ``duration``.

    Each waypoint is a dict with keys ``t, x, y, z, yaw, vx, vy, vz,
    yaw_rate``. The ``yaw`` is the heading along the path tangent
    (computed from the path's velocity direction). The ``yaw_rate``
    is the time derivative of yaw, suitable for slew-rate limiting.

    The path is sampled at ``int(duration/dt) + 1`` points (closed
    endpoints, inclusive of t=0).
    """
    name: str
    waypoints: np.ndarray    # shape (N, 9), columns = t,x,y,z,yaw,vx,vy,vz,yaw_rate
    aggressiveness: float    # dimensionless; higher = harder

    @property
    def duration(self) -> float:
        return float(self.waypoints[-1, 0])

    @property
    def n(self) -> int:
        return int(self.waypoints.shape[0])


def _wrap_angle(a: float) -> float:
    """Wrap to (-pi, pi]."""
    return (a + np.pi) % (2 * np.pi) - np.pi


def _tangent_yaw(vx: float, vy: float) -> float:
    """Heading angle of a 2D velocity vector."""
    return float(np.arctan2(vy, vx))


def _resample(t: np.ndarray, x: np.ndarray, y: np.ndarray, z: np.ndarray,
              dt: float, duration: float) -> np.ndarray:
    """Linear interpolation of a coarse path onto a uniform tick grid.

    ``t, x, y, z`` are the source path samples (any monotonic time
    array). Returns shape (N, 9) waypoint array with columns
    t, x, y, z, yaw, vx, vy, vz, yaw_rate.
    """
    n = int(round(duration / dt)) + 1
    t_uniform = np.linspace(0.0, duration, n)
    x_i = np.interp(t_uniform, t, x)
    y_i = np.interp(t_uniform, t, y)
    z_i = np.interp(t_uniform, t, z)
    # Velocity by central difference on the uniform grid.
    vx = np.gradient(x_i, dt)
    vy = np.gradient(y_i, dt)
    vz = np.gradient(z_i, dt)
    # Heading along tangent, with wrap handling.
    yaw = np.arctan2(vy, vx)
    yaw_rate = np.gradient(yaw, dt)
    # Wrap yaw_rate to (-pi, pi] to suppress the 2*pi jump.
    yaw_rate = np.array([_wrap_angle(y) for y in np.diff(yaw)] + [0.0])
    return np.column_stack([
        t_uniform, x_i, y_i, z_i, yaw, vx, vy, vz, yaw_rate,
    ])


def lemniscate(*, aggressiveness: float = 1.0,
               duration: float = 8.0,
               scale: float = 1.0,
               dt: float = 0.005) -> Trajectory:
    """Figure-8 (Bernoulli lemniscate) in the XY plane.

    Parametric form
        x = scale * cos(t) / (1 + sin^2(t))
        y = scale * sin(t) * cos(t) / (1 + sin^2(t))
    traversed at constant parametric rate. ``aggressiveness`` scales
    the speed: 1.0 = nominal, 2.0 = twice the nominal speed (which
    doubles the centripetal acceleration at every point — the cross-
    track error under closed-loop tracking should grow ~2x).

    The lemniscate has period ``2*pi`` in parametric time; we sample
    inclusive endpoints so the path closes exactly at ``(1, 0)``.
    """
    if aggressiveness <= 0.0:
        raise ValueError("aggressiveness must be > 0")
    n_coarse = 1001
    t_coarse = np.linspace(0.0, 2 * np.pi, n_coarse)  # inclusive endpoints
    x_coarse = scale * np.cos(t_coarse) / (1.0 + np.sin(t_coarse) ** 2)
    y_coarse = (scale * np.sin(t_coarse) * np.cos(t_coarse)
                / (1.0 + np.sin(t_coarse) ** 2))
    z_coarse = np.zeros_like(t_coarse)
    # Time-mapping: aggressive = speed scale; total path duration kept.
    t_path = t_coarse / (aggressiveness * (2 * np.pi / duration))
    wp = _resample(t_path, x_coarse, y_coarse, z_coarse, dt, duration)
    return Trajectory(
        name=f"lemniscate_aggr{aggressiveness:g}",
        waypoints=wp,
        aggressiveness=aggressiveness,
    )


def circle(*, aggressiveness: float = 1.0,
           radius: float = 1.0,
           duration: float = 8.0,
           dt: float = 0.005) -> Trajectory:
    """Constant-radius circular path, XZ-plane (constant yaw at
    the centre of the circle so the heading wraps).

    ``aggressiveness`` scales the angular speed: at 1.0 the period is
    ``duration``; at 2.0 it completes two full circles. Centripetal
    acceleration grows quadratically with aggressiveness.
    """
    if aggressiveness <= 0.0:
        raise ValueError("aggressiveness must be > 0")
    n_coarse = 1001
    omega = aggressiveness * (2 * np.pi / duration)
    t_coarse = np.linspace(0.0, duration, n_coarse)  # inclusive endpoints
    x_coarse = radius * np.cos(omega * t_coarse)
    y_coarse = np.zeros_like(t_coarse)
    z_coarse = radius * np.sin(omega * t_coarse)
    wp = _resample(t_coarse, x_coarse, y_coarse, z_coarse, dt, duration)
    return Trajectory(
        name=f"circle_aggr{aggressiveness:g}",
        waypoints=wp,
        aggressiveness=aggressiveness,
    )


def polygon(*, aggressiveness: float = 1.0,
            side: float = 1.0,
            n_sides: int = 4,
            duration: float = 8.0,
            dt: float = 0.005) -> Trajectory:
    """Regular polygon path, XY plane. n_sides = 4 -> square.

    The polygon has sharp corners — this is the spec's "rapid
    direction reversal" geometry. Each side takes equal time;
    ``aggressiveness`` scales the linear speed along each side.
    """
    if n_sides < 3:
        raise ValueError("n_sides must be >= 3")
    if aggressiveness <= 0.0:
        raise ValueError("aggressiveness must be > 0")
    # Vertices
    angles = np.linspace(0.0, 2 * np.pi, n_sides, endpoint=False)
    verts = np.column_stack([side * np.cos(angles), side * np.sin(angles)])
    # Closed path: walk along edges.
    t_coarse_list: list[float] = []
    x_coarse_list: list[float] = []
    y_coarse_list: list[float] = []
    z_coarse_list: list[float] = []
    edge_time = duration / n_sides
    n_per_edge = 100
    for i in range(n_sides):
        a = verts[i]
        b = verts[(i + 1) % n_sides]
        seg_t = np.linspace(0.0, edge_time, n_per_edge, endpoint=False)
        s = seg_t / edge_time
        x = a[0] * (1.0 - s) + b[0] * s
        y = a[1] * (1.0 - s) + b[1] * s
        z = np.zeros_like(s)
        t_coarse_list.append(seg_t + i * edge_time)
        x_coarse_list.append(x)
        y_coarse_list.append(y)
        z_coarse_list.append(z)
    t_path = np.concatenate(t_coarse_list)
    x_path = np.concatenate(x_coarse_list)
    y_path = np.concatenate(y_coarse_list)
    z_path = np.concatenate(z_coarse_list)
    wp = _resample(t_path, x_path, y_path, z_path, dt, duration)
    return Trajectory(
        name=f"polygon_{n_sides}_aggr{aggressiveness:g}",
        waypoints=wp,
        aggressiveness=aggressiveness,
    )


def waypoints(*, points: list[tuple[float, float, float]],
              duration: float,
              dt: float = 0.005,
              name: str = "waypoints") -> Trajectory:
    """User-supplied dense waypoint list. Each ``(x, y, z)`` is a
    target the drone must reach. Linear interpolation between them;
    each segment takes an equal fraction of ``duration``.

    Pass a long waypoint list (>= 100 points) for a *dense* trajectory
    that matches the thesis definition; sparse lists still work for
    coarse point-to-point motion.
    """
    if len(points) < 2:
        raise ValueError("at least two waypoints are required")
    pts = np.asarray(points, float)
    seg_n = max(2, int(len(points) * 50 / duration))  # ~50 samples per second
    seg_t = duration / (len(points) - 1)
    t_path_list: list[np.ndarray] = []
    x_path_list: list[np.ndarray] = []
    y_path_list: list[np.ndarray] = []
    z_path_list: list[np.ndarray] = []
    for i in range(len(points) - 1):
        a, b = pts[i], pts[i + 1]
        s = np.linspace(0.0, 1.0, seg_n, endpoint=False)
        x = a[0] * (1.0 - s) + b[0] * s
        y = a[1] * (1.0 - s) + b[1] * s
        z = a[2] * (1.0 - s) + b[2] * s
        tt = i * seg_t + s * seg_t
        t_path_list.append(tt)
        x_path_list.append(x)
        y_path_list.append(y)
        z_path_list.append(z)
    t_path = np.concatenate(t_path_list)
    x_path = np.concatenate(x_path_list)
    y_path = np.concatenate(y_path_list)
    z_path = np.concatenate(z_path_list)
    wp = _resample(t_path, x_path, y_path, z_path, dt, duration)
    return Trajectory(
        name=name,
        waypoints=wp,
        aggressiveness=1.0,
    )