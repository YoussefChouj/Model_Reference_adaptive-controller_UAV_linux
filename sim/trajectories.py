"""Dense trajectory generation (spec 4a / prior-10).

A trajectory is a dense waypoint sequence with an aggressiveness
parameter. The generated samples are exactly what a position/attitude
outer loop would command at each tick (200 Hz, dt = 0.005 s). The
trajectory is *open-loop*: it does not know the plant state, only the
geometry of the path and the speed parameter. The closed-loop path
metric (``cross-track error`` etc.) is computed against the realised
plant trajectory by ``sim.metrics.compute_path``.

Preset taxonomy (matched to TASK/AutoflyTask.c parameterisation):

  * **sinusoid** — single-axis sinusoidal offset from a centre point
    (axis 0=X, 1=Y, 2=Z). Firmware: ``sinusoid_path``.
  * **figure8** — Bernoulli (type=0) or Gerono (type=1) lemniscate.
    Firmware: ``figure8_path``.
  * **circle** — constant-radius in the XZ plane. Firmware: ``circle_path``.
  * **lemniscate** — Bernoulli figure-8 (spec 4a baseline, published
    anchors available).
  * **polygon** — regular N-sided polygon with sharp corners.
  * **waypoints** — user-supplied list of (x,y,z) points, equal-time
    segments.

All presets expose deterministic generation — same params -> identical
waypoint sequence — so tests can assert on exact coordinates.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import math

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


# ---------------------------------------------------------------------------
# Firmware-matched presets (matched to TASK/AutoflyTask.c parameterisation)
# ---------------------------------------------------------------------------

def sinusoid(*, axis: int = 0,
             center: tuple[float, float, float] = (0.0, 0.0, 1.0),
             amplitude: float = 0.5,
             frequency: float = 0.5,
             duration: float = 8.0,
             dt: float = 0.005) -> Trajectory:
    """Single-axis sinusoidal offset from a centre point.

    Matches ``sinusoid_path`` in ``TASK/AutoflyTask.c``:
        val = amplitude * sin(2*PI * frequency * t_elapsed)
    injected into the chosen axis (0=X, 1=Y, 2=Z), offset from centre.
    Yaw = 0.

    Args:
        axis: which axis to modulate (0=x, 1=y, 2=z)
        center: (cx, cy, cz) base position
        amplitude: oscillation half-amplitude, metres
        frequency: Hz
        duration: total run time, seconds
        dt: sample interval, seconds (200 Hz = 0.005)
    """
    if axis not in (0, 1, 2):
        raise ValueError("axis must be 0 (x), 1 (y), or 2 (z)")
    n_coarse = max(3, int(duration * 200))
    t_coarse = np.linspace(0.0, duration, n_coarse)
    x_coarse = np.full_like(t_coarse, center[0], float)
    y_coarse = np.full_like(t_coarse, center[1], float)
    z_coarse = np.full_like(t_coarse, center[2], float)
    offset = amplitude * np.sin(2.0 * np.pi * frequency * t_coarse)
    if axis == 0:
        x_coarse = x_coarse + offset
    elif axis == 1:
        y_coarse = y_coarse + offset
    else:
        z_coarse = z_coarse + offset
    wp = _resample(t_coarse, x_coarse, y_coarse, z_coarse, dt, duration)
    axis_name = ("x", "y", "z")[axis]
    return Trajectory(
        name=f"sinusoid_{axis_name}_amp{amplitude}_f{frequency}",
        waypoints=wp,
        aggressiveness=1.0,
    )


def figure8(*, center: tuple[float, float, float] = (0.0, 0.0, 1.0),
            amplitude: float = 1.0,
            angular_speed: float = 1.0,
            type: int = 0,
            duration: float = 8.0,
            dt: float = 0.005) -> Trajectory:
    """Figure-8 (lemniscate), Bernoulli or Gerono variant.

    Matches ``figure8_path`` in ``TASK/AutoflyTask.c``:

    Type 0 (Bernoulli, lying infinity / wider in x):
        cx = cx + amp * cos(t) / (1 + sin²(t))
        cy = cy + amp * sin(t) * cos(t) / (1 + sin²(t))
    Type 1 (Gerono, vertical figure-8 / taller in y):
        cx = cx + 0.5*amp * sin(2t)
        cy = cy + amp * sin(t)

    Z = center_z. Yaw = 0. Angular speed is in parametric rad/s.

    Args:
        center: (cx, cy, cz) centre of the figure
        amplitude: half-extent of the figure, metres
        angular_speed: parametric angular rate, rad/s
        type: 0 = Bernoulli, 1 = Gerono
        duration: total run time, seconds
        dt: sample interval, seconds
    """
    if type not in (0, 1):
        raise ValueError("type must be 0 (Bernoulli) or 1 (Gerono)")
    cx, cy, cz = center
    n_coarse = max(3, int(duration * 200))
    t_coarse = np.linspace(0.0, duration, n_coarse)
    theta = angular_speed * t_coarse
    if type == 0:
        # Bernoulli
        s = np.sin(theta)
        c = np.cos(theta)
        denom = 1.0 + s * s
        x_coarse = cx + amplitude * c / denom
        y_coarse = cy + amplitude * s * c / denom
    else:
        # Gerono
        x_coarse = cx + 0.5 * amplitude * np.sin(2.0 * theta)
        y_coarse = cy + amplitude * np.sin(theta)
    z_coarse = np.full_like(t_coarse, cz)
    wp = _resample(t_coarse, x_coarse, y_coarse, z_coarse, dt, duration)
    type_name = "bernoulli" if type == 0 else "gerono"
    return Trajectory(
        name=f"figure8_{type_name}_amp{amplitude}_w{angular_speed}",
        waypoints=wp,
        aggressiveness=1.0,
    )


# ---------------------------------------------------------------------------
# Closed-form curve descriptors (for compute_path cross-track projection)
# ---------------------------------------------------------------------------

class CircleCurve:
    """Closed-form circle descriptor for analytic cross-track projection."""
    __slots__ = ("cx", "cy", "radius")

    def __init__(self, cx: float, cy: float, radius: float):
        self.cx = cx
        self.cy = cy
        self.radius = radius

    def cross_track(self, x: float, y: float) -> float:
        return abs(math.hypot(x - self.cx, y - self.cy) - self.radius)

    def along_track(self, x: float, y: float, t: float, duration: float) -> float:
        """Signed arc-length from the trajectory target at time t to (x,y)."""
        theta_t = (t / duration) * (2.0 * math.pi)
        seg_len = self.radius * 2.0 * math.pi
        target_x = self.cx + self.radius * math.cos(theta_t)
        target_y = self.cy + self.radius * math.sin(theta_t)
        angle_t = math.atan2(target_y - self.cy, target_x - self.cx)
        angle_p = math.atan2(y - self.cy, x - self.cx)
        dtheta = (angle_p - angle_t + math.pi) % (2.0 * math.pi) - math.pi
        return dtheta * self.radius


class BernoulliCurve:
    """Closed-form Bernoulli lemniscate descriptor (type=0)."""
    __slots__ = ("cx", "cy", "amplitude")

    def __init__(self, cx: float, cy: float, amplitude: float):
        self.cx = cx
        self.cy = cy
        self.amplitude = amplitude

    def _theta_from_param(self, t: float, duration: float) -> float:
        return (t / duration) * 2.0 * math.pi

    def closest_point(self, x: float, y: float, n_search: int = 720) -> float:
        """Return the parametric t value (radians) of the closest point on
        the lemniscate to (x, y) by brute-force search."""
        best_t = 0.0
        best_d = math.inf
        xn, yn = x - self.cx, y - self.cy
        for i in range(n_search + 1):
            t = i * 2.0 * math.pi / n_search
            s = math.sin(t)
            c = math.cos(t)
            denom = 1.0 + s * s
            dx = self.amplitude * c / denom - xn
            dy = self.amplitude * s * c / denom - yn
            d = dx * dx + dy * dy
            if d < best_d:
                best_d = d
                best_t = t
        return best_t

    def cross_track(self, x: float, y: float) -> float:
        t_closest = self.closest_point(x, y)
        s = math.sin(t_closest)
        c = math.cos(t_closest)
        denom = 1.0 + s * s
        cx_p = self.cx + self.amplitude * c / denom
        cy_p = self.cy + self.amplitude * s * c / denom
        return math.hypot(x - cx_p, y - cy_p)

    def along_track(self, x: float, y: float, t: float,
                    duration: float) -> float:
        t_target = self._theta_from_param(t, duration)
        t_closest = self.closest_point(x, y)
        # Arc-length differential: ds/dt = |dP/dt| for the lemniscate.
        # Use mean circumradius approximation: L ≈ 2π * a * 1.3 (Bernoulli).
        approx_arc = self.amplitude * 2.0 * math.pi * 1.3
        return approx_arc * (t_closest - t_target) / (2.0 * math.pi)


class GeronoCurve:
    """Closed-form Gerono lemniscate descriptor (type=1)."""
    __slots__ = ("cx", "cy", "amplitude")

    def __init__(self, cx: float, cy: float, amplitude: float):
        self.cx = cx
        self.cy = cy
        self.amplitude = amplitude

    def _theta_from_param(self, t: float, duration: float) -> float:
        return (t / duration) * 2.0 * math.pi

    def closest_point(self, x: float, y: float, n_search: int = 720) -> float:
        best_t = 0.0
        best_d = math.inf
        xn, yn = x - self.cx, y - self.cy
        for i in range(n_search + 1):
            t = i * 2.0 * math.pi / n_search
            dx = 0.5 * self.amplitude * math.sin(2.0 * t) - xn
            dy = self.amplitude * math.sin(t) - yn
            d = dx * dx + dy * dy
            if d < best_d:
                best_d = d
                best_t = t
        return best_t

    def cross_track(self, x: float, y: float) -> float:
        t_closest = self.closest_point(x, y)
        cx_p = self.cx + 0.5 * self.amplitude * math.sin(2.0 * t_closest)
        cy_p = self.cy + self.amplitude * math.sin(t_closest)
        return math.hypot(x - cx_p, y - cy_p)

    def along_track(self, x: float, y: float, t: float,
                    duration: float) -> float:
        t_target = self._theta_from_param(t, duration)
        t_closest = self.closest_point(x, y)
        approx_arc = self.amplitude * 2.0 * math.pi * 1.3
        return approx_arc * (t_closest - t_target) / (2.0 * math.pi)


class SinusoidCurve:
    """Closed-form sinusoid in one axis (cross-track = perpendicular to
    the 1-D oscillation line)."""
    __slots__ = ("axis", "center", "amplitude", "frequency")

    def __init__(self, axis: int, center: tuple[float, float, float],
                 amplitude: float, frequency: float):
        self.axis = axis
        self.center = center
        self.amplitude = amplitude
        self.frequency = frequency

    def cross_track(self, x: float, y: float) -> float:
        # Projection of (x,y) onto the infinite oscillation line.
        # Oscillates in one axis; perpendicular = distance from that axis.
        if self.axis == 0:
            return abs(y - self.center[1])
        elif self.axis == 1:
            return abs(x - self.center[0])
        else:
            return 0.0

    def along_track(self, x: float, y: float, t: float,
                    duration: float) -> float:
        # Signed position along the oscillation axis.
        phase = 2.0 * math.pi * self.frequency * t
        target_val = self.center[self.axis] + self.amplitude * math.sin(phase)
        if self.axis == 0:
            return x - target_val
        elif self.axis == 1:
            return y - target_val
        else:
            return 0.0


def closed_form_cross_track(traj: Trajectory, x: float, y: float,
                            t: float) -> tuple[float, float]:
    """Compute closed-form cross-track and along-track vs the ideal curve.

    Returns ``(cross_track_m, along_track_m)``. Falls back to the
    polyline projector from ``trajectory_runner._cross_track`` if the
    trajectory type is not recognised.
    """
    name = traj.name
    # Match by name prefix (deterministic, no duck-typing on curve objects).
    import re
    if name.startswith("circle") and "_aggr" in name:
        # Extract centre and radius from waypoint geometry.
        # The circle is in the XZ plane. Centre = mean of all waypoints (least-squares
        # plane fit; exact for a full circle). Radius: use the first waypoint
        # (t=0, where the parametric angle is known exactly at cos/sin=±1),
        # avoiding the mean-x bias that cosine introduces over a full period.
        wp = traj.waypoints
        cx = float(np.mean(wp[:, 1]))
        cy = float(np.mean(wp[:, 2]))  # y centre (≈ 0 for XZ circle)
        cz = float(np.mean(wp[:, 3]))
        # Radius from the first waypoint at t=0 (known parametric angle).
        radius = float(math.sqrt(
            (wp[0, 1] - cx) ** 2 + (wp[0, 3] - cz) ** 2))
        curve = CircleCurve(cx, cy, radius)
    elif name.startswith("figure8_bernoulli"):
        wp = traj.waypoints
        cx = float(np.mean(wp[:, 1]))
        cy = float(np.mean(wp[:, 2]))
        # Amplitude: half the max x-extent from centroid.
        amp = float(np.max(np.abs(wp[:, 1] - cx)))
        curve = BernoulliCurve(cx, cy, amp)
    elif name.startswith("figure8_gerono"):
        wp = traj.waypoints
        cx = float(np.mean(wp[:, 1]))
        cy = float(np.mean(wp[:, 2]))
        amp = float(np.max(np.abs(wp[:, 2] - cy)))
        curve = GeronoCurve(cx, cy, amp)
    elif name.startswith("sinusoid"):
        # Extract axis from the name: sinusoid_x_, sinusoid_y_, sinusoid_z_
        axis_map = {"x": 0, "y": 1, "z": 2}
        for key, ax in axis_map.items():
            if f"sinusoid_{key}_" in name:
                # Find center from first waypoint.
                wp = traj.waypoints
                cx = float(wp[0, 1])
                cy = float(wp[0, 2])
                cz = float(wp[0, 3])
                # Amplitude and frequency encoded in name.
                m_amp = re.search(r"amp([0-9.]+)", name)
                m_f = re.search(r"f([0-9.]+)", name)
                amp = float(m_amp.group(1)) if m_amp else 0.5
                freq = float(m_f.group(1)) if m_f else 0.5
                curve = SinusoidCurve(ax, (cx, cy, cz), amp, freq)
                break
        else:
            curve = None
    else:
        curve = None

    if curve is not None:
        ct = float(curve.cross_track(x, y))
        at = float(curve.along_track(x, y, t, traj.duration))
        return ct, at
    else:
        # Fall back to polyline (for polygon, waypoints, lemniscate).
        # Import here to avoid circular dependency: trajectories -> trajectory_runner.
        from sim.trajectory_runner import _cross_track, _along_track_arc
        ct, k_proj = _cross_track(traj, x, y)
        idx_t = max(0, min(int(round(t / 0.005)), traj.n - 1))
        at = _along_track_arc(traj, idx_t, k_proj)
        return ct, at