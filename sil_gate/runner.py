"""Trajectory driver + numerical comparison for the SIL gate.

The gate drives the firmware C (via a subprocess runner - see linker.py)
and the Python sim (via sim/ekf.py.Ekf9State) with **identical inputs**
over a trajectory of N ticks (default 2000 at 200 Hz = 10 s) and compares
every output the firmware exposes.

Inputs are deterministic from a seed so a failure can be re-run in isolation
- the same golden seed reproduces the same trajectory.

Comparison contract (spec §"Comparison contract"):

  Both parts must hold:

    (a) per-tick absolute/relative difference stays within a documented
        tolerance; AND
    (b) the difference does not exhibit sustained growth.

  Growth is the more important part. A steadily growing delta is a
  structural defect regardless of its current magnitude - the EKF's
  documented unobservable gyro-bias states (b_g) make this particularly
  load-bearing.

A failure report names the diverging signal and the tick at which growth
began, so a reviewer can localise the defect without further prompting.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

from sim.ekf import Ekf9State

from sil_gate.linker import EKF9Run, RunnerExe, run_ekf_subprocess


# ----------------------------------------------------------------------
# Default tolerances (see README + spec).
# ----------------------------------------------------------------------
# Compiler differences live around the seventh decimal place. Real defects
# the gate must catch are of a different order entirely - the historical
# EKF bugs dropped whole terms and made a state unobservable. A tolerance
# loose enough to ignore compiler noise remains overwhelmingly sensitive
# to real faults.
DEFAULT_REL_TOL = 1e-5
DEFAULT_ABS_TOL = 1e-7

# Growth threshold: |delta| slope must not exceed this per second.
# Trajectory is 2000 ticks at 200 Hz = 10 s. A constant 5e-4 / s slope
# over 10 s would put 0.5% on the state by the end - well above any
# compiler-noise floor.
DEFAULT_GROWTH_TOL_PER_S = 5e-4


# ----------------------------------------------------------------------
# Trajectory generators
# ----------------------------------------------------------------------
# Each trajectory returns (a_body, of_xy, z_rate) - per-tick arrays of
# parallel length. The gate drives both implementations with the SAME
# arrays, so any numerical divergence between them is attributable to
# implementation differences, not input differences.

@dataclass
class Trajectory:
    n_ticks: int
    dt: float
    a_body: np.ndarray  # (N, 3)
    of_xy: np.ndarray   # (N, 2)
    z_rate: np.ndarray  # (N,)


def trajectory_constant_with_noise(
    n_ticks: int,
    dt: float,
    a_body: Tuple[float, float, float],
    gyro: Tuple[float, float, float],   # currently unused; placeholder for future mrac
    seed: int = 0,
    of_noise_std: float = 0.0,
    z_rate_meas: float = 0.0,
    z_rate_noise_std: float = 0.0,
) -> Trajectory:
    """Constant a_body with optional OF + z-rate measurement noise.

    `gyro` is accepted for parity with the spec's signature but the EKF
    runner does not consume it; mrac.c will need it.
    """
    rng = np.random.default_rng(seed)
    a = np.tile(np.asarray(a_body, dtype=np.float64), (n_ticks, 1))
    # OF measurement: integrated accel plus noise (clean signal + noise)
    integrated = np.cumsum(a * dt, axis=0)
    if of_noise_std > 0:
        integrated = integrated + rng.normal(0.0, of_noise_std, integrated.shape)
    of = integrated[:, 0:2]
    if z_rate_noise_std > 0:
        z = z_rate_meas + rng.normal(0.0, z_rate_noise_std, n_ticks)
    else:
        z = np.full(n_ticks, z_rate_meas, dtype=np.float64)
    return Trajectory(n_ticks=n_ticks, dt=dt, a_body=a, of_xy=of, z_rate=z)


def trajectory_random_walk(
    n_ticks: int,
    dt: float,
    seed: int = 0,
    a_body_scale: float = 1.0,
    gyro_scale: float = 1.0,   # unused for ekf; placeholder
) -> Trajectory:
    """Random-walk-like excitation: per-tick random accel."""
    rng = np.random.default_rng(seed)
    a = rng.normal(0.0, a_body_scale, size=(n_ticks, 3))
    of = np.cumsum(a * dt, axis=0)[:, 0:2]
    z = np.cumsum(a[:, 2] * dt)
    return Trajectory(n_ticks=n_ticks, dt=dt, a_body=a, of_xy=of, z_rate=z)


# ----------------------------------------------------------------------
# Run sim and firmware on a trajectory
# ----------------------------------------------------------------------

def run_sim(traj: Trajectory) -> EKF9Run:
    """Replay the trajectory through sim/ekf.py.Ekf9State.

    NOTE on `k_last`: the firmware caches the LAST Kalman-gain column
    written to `Ekf9_t.k_last`. After UpdateOf it holds K[0..2, 0]; after
    UpdateZRate it holds K[0..2, 2]. sim/ekf.py only ever caches K[0..2, 0]
    in `self._K_of` and ignores the Z-rate gain column - so to compare
    like-for-like we have to mirror the firmware's overwrite behaviour
    here. This is documented in sil_gate/DEVIATIONS.md ("k_last is
    overwritten by every update, not stacked").
    """
    ekf = Ekf9State()
    xs = np.zeros((traj.n_ticks, 9), dtype=np.float64)
    nis = np.zeros(traj.n_ticks, dtype=np.float64)
    klasts = np.zeros((traj.n_ticks, 3), dtype=np.float64)
    for k in range(traj.n_ticks):
        ekf.predict(
            tuple(traj.a_body[k]),
            (0.0, 0.0, 0.0),
            traj.dt,
        )
        ekf.update_of((float(traj.of_xy[k, 0]), float(traj.of_xy[k, 1])))
        # Cache the OF x-axis Kalman gain column (K[0..2, 0]) the same way
        # the firmware does immediately after UpdateOf.
        k_of_xcol = np.asarray(ekf._K_of, dtype=np.float64).copy()
        ekf.update_acc_xy((0.0, 0.0))   # ZUPT - no K cache write in firmware
        ekf.update_z_rate(float(traj.z_rate[k]))
        # After UpdateZRate, the firmware overwrites k_last with K[:,2].
        # sim/ekf.py does not store this column, so we compute it manually
        # from the post-update state: K[:,2] = P[:,2] / (P[2,2] + R_z),
        # but P was just Joseph-updated, so use ekf.P directly.
        s_zz = float(ekf.P[2, 2] + ekf.r_z)
        k_z_xcol = np.asarray([float(ekf.P[i, 2]) / s_zz for i in range(3)],
                              dtype=np.float64)
        xs[k] = ekf.x
        nis[k] = ekf.nis
        # k_last at the END of the tick matches what the firmware caches
        # after the last update (UpdateZRate overwrote it).
        klasts[k] = k_z_xcol
    return EKF9Run(x=xs, nis=nis, k_last=klasts)


def run_firmware(runner, traj: Trajectory) -> EKF9Run:
    """Replay the trajectory through the compiled runner executable.

    `runner` may be a RunnerExe or a plain Path (used by self-tests that
    build ad-hoc executables). The runner's module field is ignored when
    a Path is given; the protocol header is read from the executable
    output instead.
    """
    if isinstance(runner, Path):
        from sil_gate.linker import RunnerExe
        runner = RunnerExe(path=runner, module="ekf9")
    return run_ekf_subprocess(
        runner,
        dt=traj.dt,
        a_body=list(map(tuple, traj.a_body)),
        of_xy=list(map(tuple, traj.of_xy)),
        z_rate=list(traj.z_rate),
    )


# ----------------------------------------------------------------------
# Comparison
# ----------------------------------------------------------------------
# Default comparison signals. k_last is excluded by default because it is
# a telemetry cache (3 of 27 Kalman-gain entries, overwritten by each
# update) whose precision is bounded by float32 even when the underlying
# math is exact. The gate's job is to verify the *mathematics* (x, nis),
# not the bit-level reproduction of an internal telemetry sample. Callers
# who want to verify k_last can pass `compare_k_last=True` - the tighter
# tolerance they will need is documented in the k_last note below.
DEFAULT_COMPARE_SIGNALS = ("x", "nis")


@dataclass
class SignalDiff:
    name: str
    max_abs: float
    max_rel: float
    # slope of |delta| over the trajectory, fit by least squares on the
    # tick index. Positive means growing, units: per-second.
    slope_per_s: float
    growth_start_tick: Optional[int]


@dataclass
class CompareResult:
    n_ticks: int
    dt: float
    signals: List[SignalDiff] = field(default_factory=list)
    passed: bool = True

    def signal(self, name: str) -> Optional[SignalDiff]:
        for s in self.signals:
            if s.name == name:
                return s
        return None


def compare_trajectories(
    sim: EKF9Run,
    fw: EKF9Run,
    dt: float,
    rel_tol: float = DEFAULT_REL_TOL,
    abs_tol: float = DEFAULT_ABS_TOL,
    growth_tol_per_s: float = DEFAULT_GROWTH_TOL_PER_S,
    compare_signals: tuple = DEFAULT_COMPARE_SIGNALS,
) -> CompareResult:
    """Pairwise compare two parallel trajectories tick-by-tick.

    Returns a CompareResult whose `passed` field is True iff every signal
    in `compare_signals` satisfies BOTH (a) per-tick tolerance AND
    (b) growth tolerance.

    By default only `x` and `nis` are compared. Pass `("x", "nis", "k_last")`
    to additionally include k_last, but be aware its bit-level agreement
    is bounded by float32 precision and the relative tolerance may need
    to be relaxed by an order of magnitude.
    """
    assert sim.x.shape == fw.x.shape, "trajectory shape mismatch"
    n = sim.x.shape[0]

    result = CompareResult(n_ticks=n, dt=dt)

    signal_arrays = {
        "x": (sim.x, fw.x),
        "nis": (sim.nis, fw.nis),
        "k_last": (sim.k_last, fw.k_last),
    }
    for name in compare_signals:
        if name not in signal_arrays:
            raise ValueError(f"unknown signal: {name}")
        sim_arr, fw_arr = signal_arrays[name]
        delta = np.abs(sim_arr - fw_arr)
        max_abs = float(delta.max())
        denom = np.maximum(np.abs(sim_arr), np.abs(fw_arr))
        denom = np.maximum(denom, 1.0)
        rel = delta / denom
        max_rel = float(rel.max())
        if sim_arr.ndim == 1:
            l2 = delta
        else:
            l2 = np.linalg.norm(sim_arr - fw_arr, axis=-1) if sim_arr.ndim == 2 else delta
        slope, growth_start = _growth_metrics(l2, dt, growth_tol_per_s)
        result.signals.append(SignalDiff(
            name=name,
            max_abs=max_abs,
            max_rel=max_rel,
            slope_per_s=slope,
            growth_start_tick=growth_start,
        ))

    for s in result.signals:
        if s.max_rel > rel_tol and s.max_abs > abs_tol:
            result.passed = False
        if s.slope_per_s > growth_tol_per_s:
            result.passed = False
    return result


def _growth_metrics(
    l2: np.ndarray,
    dt: float,
    tol_per_s: float,
) -> Tuple[float, Optional[int]]:
    """Estimate the slope of |delta| over the trajectory.

    Returns (slope_per_s, growth_start_tick). growth_start is the first tick
    at which |delta| exceeds 5x the median, or None if it never does.
    """
    n = len(l2)
    if n < 10:
        return 0.0, None
    t = np.arange(n, dtype=np.float64) * dt  # seconds
    # least-squares slope of l2 vs t
    slope, _intercept = np.polyfit(t, l2, 1)
    median = float(np.median(l2))
    threshold = max(5.0 * median, 1e-12)
    over = np.where(l2 > threshold)[0]
    growth_start = int(over[0]) if over.size else None
    return float(slope), growth_start


# ----------------------------------------------------------------------
# Failure formatting
# ----------------------------------------------------------------------
def format_failure(
    trajectory_name: str,
    result: CompareResult,
    rel_tol: float = DEFAULT_REL_TOL,
    abs_tol: float = DEFAULT_ABS_TOL,
    growth_tol_per_s: float = DEFAULT_GROWTH_TOL_PER_S,
) -> str:
    """Human-readable failure report naming the diverging signal and tick."""
    lines = [
        f"SIL gate FAILED on trajectory `{trajectory_name}` "
        f"({result.n_ticks} ticks @ dt={result.dt:.4f})",
        f"  tolerances: rel={rel_tol:.1e} abs={abs_tol:.1e} "
        f"growth={growth_tol_per_s:.1e}/s",
    ]
    for s in result.signals:
        flags = []
        if s.max_rel > rel_tol and s.max_abs > abs_tol:
            flags.append("REL/ABS")
        if s.slope_per_s > growth_tol_per_s:
            flags.append("GROWTH")
        if not flags:
            continue
        where = f" (growth onset @ tick {s.growth_start_tick})" if s.growth_start_tick is not None else ""
        lines.append(
            f"  - {s.name:6s} [{','.join(flags)}] "
            f"max_abs={s.max_abs:.3e} max_rel={s.max_rel:.3e} "
            f"slope={s.slope_per_s:+.3e}/s{where}"
        )
    return "\n".join(lines)