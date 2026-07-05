"""Bifilar-pendulum moment-of-inertia analysis (docs/bench_characterization.md §1).

Reads a dashboard flight-recording CSV (the long-format `t_s, frame, key, value` file
written by `ground_station/scripts/flight_logger.FlightLogger`), extracts the torsional
period T from the gyro-rate feedback of the vertical body axis, and computes

    I = m·g·d²·T² / (16·π²·L)

with a first-order uncertainty propagation and the standard data-quality checks.

Data contract (verified against the dashboard writer):

* The 20 Hz render loop (`ground_station/gui/dashboard.py` around line 965) calls
  `self._flight_logger.log_snapshot("B", b)` once every ~0.05 s; each `key` from the
  Frame B dict is written as one CSV row `{t_s, frame, key, value}` (see
  `ground_station/scripts/flight_logger.py` lines 26 and 30).
* The Frame B dict key for the rate-feedback of the vertical body axis is one of
  `pid.gyrox.FB`, `pid.gyroy.FB`, `pid.gyroz.FB` — produced by
  `ground_station/comm/serial_bridge.py` `_unpack_frame_b` (the `pid_loops` list at
  line ~611 maps `gyrox → gyroy → gyroz` to `pid.{loop}.FB` at line 626).
* User-facing axis → body-frame mapping (this script's CLI). The authoritative firmware
  cascade wiring is in `TASK/StabilizerTask.c:619-620`:
      Ctrler.gyroyPID.Des = Ctrler.pitchPID.U ;   // gyroy IS the pitch rate loop
      Ctrler.gyroxPID.Des = Ctrler.rollPID.U ;    // gyrox IS the roll rate loop
  Corroborated by the gyro-FB plumbing at `TASK/StabilizerTask.c:131-132` (gyroxPID.FB
  receives `GYRO_FILT_ROLL` of `Gyro_X_Real`, gyroyPID.FB receives `GYRO_FILT_PITCH` of
  `Gyro_Y_Real`) and the SysID-axis wiring at `TASK/StabilizerTask.c:339-340`
  (`SYSID_AXIS_PITCH → gyroyPID.Des`, `SYSID_AXIS_ROLL → gyroxPID.Des`).
  **DO NOT use** the dashboard comment at `dashboard.py:87-91`
  `INNER_PID_AXIS_TO_PIDS` — it is a pre-existing comment bug that swaps roll↔pitch
  (`pitch: 3 # gyroxPID` is wrong); the variable indices are right but the # comment
  is wrong, so anything reading that comment as ground truth will be flipped.
  Concretely: gyrox = ROLL rate, gyroy = PITCH rate, gyroz = YAW rate.
    --axis roll   → pid.gyrox.FB   (roll hang: x-body axis vertical; rate about x = roll rate)
    --axis pitch  → pid.gyroy.FB   (pitch hang: y-body axis vertical; rate about y = pitch rate)
    --axis yaw    → pid.gyroz.FB   (yaw hang: z-body axis vertical; rate about z = yaw rate)

Algorithm (see method header comments and the contract for derivation):

1. Load CSV → uniform time base from `t_s`; report actual mean rate.
2. Detrend (DC-only mean subtraction is enough — band-pass kills drift) and band-pass
   filter (scipy Butterworth, zero-phase `filtfilt`) at 0.1–3 Hz.
3. Two independent period estimators:
   a. Welch periodogram → parabolic interpolation around the peak bin.
   b. Linearly interpolated RISING zero-crossings, linear least-squares fit of
      crossing-index vs crossing-time → slope = T (PRIMARY value), residual std = σ_T.
4. Damping log-decrement δ from successive peak amplitudes (Hilbert envelope); ζ = δ /
   sqrt(4π² + δ²). Report T_undamped = T·sqrt(1-ζ²).
5. I = m·g·d²·T_undamped² / (16·π²·L).
6. σ_I via standard first-order propagation (treats inputs as uncorrelated):
       σ_I² = (∂I/∂m)²·σ_m² + (∂I/∂d)²·σ_d² + (∂I/∂L)²·σ_L² + (∂I/∂T)²·σ_T²
   with σ_T from step 3b and the user-input tolerances ±5 g, ±1 mm.
7. Quality warnings (printed, also exposed in the CSV row):
   * off-axis RMS > 20% of the selected axis RMS in the passband,
   * < 10 detected oscillation cycles,
   * FFT-vs-zero-crossing period disagreement > 1%.

CLI:
    python inertia_analysis.py <flight_csv> --axis {roll,pitch,yaw}
                           --mass KG --d M --L M
                           [--g 9.81] [--start S] [--end S] [--out DIR]
    python inertia_analysis.py --selftest                     # generates synthetic data
"""
from __future__ import annotations

import argparse
import csv
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
from scipy import signal

import matplotlib
matplotlib.use("Agg")                                        # non-interactive backend (style match)
import matplotlib.pyplot as plt

# Force UTF-8 on stdout/stderr so the Greek/math glyphs in our printed summary and warnings
# survive a Windows console (default cp1252 would crash on zeta/sigma/etc.).
try:
    sys.stdout.reconfigure(encoding="utf-8")                  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")                  # type: ignore[attr-defined]
except (AttributeError, OSError):
    pass


# ----------------------------------------------------------------------------- column-name audit

# Axis (CLI) → Frame-B dict key for the rate-feedback of the body axis that is vertical
# during the hang. The CLI axis is the physical axis under test. Authority for the firmware
# `gyro[xyz]PID ↔ roll/pitch/yaw` mapping is `TASK/StabilizerTask.c:619-620, 131-132, 339-340`
# (see module docstring). The dashboard comment `INNER_PID_AXIS_TO_PIDS` at dashboard.py:87-91
# is wrong (its indices are right but the `# gyroxPID`/`# gyroyPID` labels are swapped) and
# must NOT be used as a reference — only the firmware cascade is authoritative.
AXIS_TO_KEY: Dict[str, str] = {
    "roll":  "pid.gyrox.FB",      # x-body axis → roll rate (StabilizerTask.c:132, 620)
    "pitch": "pid.gyroy.FB",      # y-body axis → pitch rate (StabilizerTask.c:131, 619)
    "yaw":   "pid.gyroz.FB",      # z-body axis → yaw rate (StabilizerTask.c:133)
}


# ------------------------------------------------------------------------------ flat-CSV loader

def _load_long_csv(path: Path) -> Dict[str, Tuple[List[float], List[float]]]:
    """Load the dashboard's flat `t_s, frame, key, value` CSV.

    Returns `{key: (t_list, v_list)}` sorted by time. Tracks the host `t_s` column as a
    synthetic `__t_s` key — useful as a sanity timestamp for the report.
    """
    out: Dict[str, Tuple[List[float], List[float]]] = {}
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None or "key" not in reader.fieldnames:
            raise ValueError(f"{path}: not a FlightLogger CSV (missing 'key' column)")
        for row in reader:
            try:
                t = float(row["t_s"])
                k = row["key"]
                v = float(row["value"])
            except (KeyError, ValueError, TypeError):
                continue
            if k not in out:
                out[k] = ([], [])
            out[k][0].append(t)
            out[k][1].append(v)
    # Sort each series by time (render-loop writes can come in slightly jumbled under load).
    for k, (t_list, v_list) in out.items():
        if len(t_list) <= 1:
            continue
        order = np.argsort(t_list)
        out[k] = ([t_list[i] for i in order], [v_list[i] for i in order])
    return out


# ------------------------------------------------------------------------------ helpers

def _bandpass(x: np.ndarray, fs: float, f_lo: float = 0.1, f_hi: float = 3.0,
              order: int = 4) -> np.ndarray:
    """Zero-phase Butterworth band-pass (0.1–3 Hz by default).

    The filter end-effects can introduce spurious zero-crossings right at the record
    boundaries — visible when the input is a damped sinusoid at the lower edge of the
    passband (~0.1 Hz) and the amplitude has decayed near the end. Mitigation: explicit
    edge-extension padding before `sosfiltfilt`, so the filter sees a constant extension
    of the endpoints rather than a step. scipy's `padtype` does not include 'edge', so
    we replicate the boundary samples ourselves, slice the result back, and let
    `sosfiltfilt` use its default 'even' padding (which already preserves endpoints).
    The change vs the un-padded call is at most a fraction of a percent near t_max — that's
    the difference between missing and hitting the 0.5% selftest gate.
    """
    nyq = 0.5 * fs
    f_hi = min(f_hi, 0.95 * nyq)
    sos = signal.butter(order, [f_lo / nyq, f_hi / nyq], btype="band", output="sos")
    # Add `extra` samples of edge replication on each side; the filter's padlen is
    # 3*(max(len_a,len_b)-1) ≈ 36 for a 4th-order Butterworth, so 64 each side is generous.
    extra = max(8 * order, 32)
    x_left = np.full(extra, x[0])
    x_right = np.full(extra, x[-1])
    x_pad = np.concatenate([x_left, x, x_right])
    y_pad = signal.sosfiltfilt(sos, x_pad, padtype="even")
    return y_pad[extra:extra + len(x)]


def _bandpass_safe(x: np.ndarray, fs: float) -> np.ndarray:
    """Convenience wrapper kept for legacy call-sites."""
    return _bandpass(x, fs)


def _fft_peak_period(x: np.ndarray, fs: float) -> Tuple[float, float]:
    """Welch periodogram with zero-padding, parabolic peak interpolation.

    Returns (T_fft_hz, f_peak_hz). Zero-padding gives a finer grid for the parabolic
    fit; we still restrict to the usable band (0.1–3 Hz) so DC leakage and noise do not
    pick a spurious peak.
    """
    n = len(x)
    if n < 8:
        return float("nan"), float("nan")
    # nfft = next power of two ≥ 2*n so peaks are smoother; Welch with a single Hann segment.
    nfft = 1
    while nfft < 2 * n:
        nfft *= 2
    f, pxx = signal.welch(x, fs=fs, nperseg=n, noverlap=0, nfft=nfft,
                           window="hann", scaling="spectrum")
    band = (f >= 0.1) & (f <= 3.0)
    if not np.any(band):
        return float("nan"), float("nan")
    pxx_band = ppx_band = np.where(band, pxx, 0.0)
    k = int(np.argmax(pxx_band))
    if k <= 0 or k >= len(f) - 1:
        return float("nan"), float(f[k])
    # Parabolic peak interpolation around the argmax bin.
    alpha = float(np.log(pxx[k - 1] + 1e-30))
    beta  = float(np.log(pxx[k]     + 1e-30))
    gamma = float(np.log(pxx[k + 1] + 1e-30))
    denom = (alpha - 2.0 * beta + gamma)
    delta = 0.5 * (alpha - gamma) / denom if denom != 0.0 else 0.0
    f_peak = float(f[k] + delta * (f[k + 1] - f[k]))
    return (1.0 / f_peak if f_peak > 0 else float("nan")), f_peak


def _zero_crossings_period(t: np.ndarray, x: np.ndarray) -> Tuple[float, float, int]:
    """Rising zero-crossings → linear LS fit of crossing-time vs crossing-index.

    Returns (T_period_s, sigma_T_s, n_crossings). We use the FIT slope as the primary T
    (robust to single noisy crossings) and the residual std as σ_T (the input to the
    uncertainty propagation in §3b of the spec). Filtering upstream guarantees a clean
    sinusoid with hundreds of crossings for a 20–30 s record.
    """
    if len(x) < 4:
        return float("nan"), float("nan"), 0
    sgn = np.sign(x)
    # Strict rising crossings (sign goes negative → positive).
    # np.sign(0) is 0; we treat 0 as positive so that a touch-above-and-back doesn't double-count.
    sgn_pos = np.where(sgn == 0, 1.0, sgn)
    diffs = np.diff(sgn_pos)
    crossings_idx = np.where(diffs > 0)[0]                 # index of the sample BEFORE the crossing
    if crossings_idx.size < 2:
        return float("nan"), float("nan"), int(crossings_idx.size)
    # Linear interpolation of where x crosses zero in each [i, i+1] pair.
    t_cross: List[float] = []
    for i in crossings_idx:
        # Defensive: never index past the end. `sosfiltfilt` can introduce a sign flip right
        # at the last sample when the filter tail decays; we may report an extra crossing here.
        # The caller already trims to a stable window; if i+1 is genuinely out of range the
        # crossing is unusable for a period fit, so skip it.
        if i + 1 >= len(x):
            continue
        x0, x1 = float(x[i]), float(x[i + 1])
        if x1 == x0:
            t_cross.append(float(t[i]))
        else:
            frac = -x0 / (x1 - x0)
            frac = min(max(frac, 0.0), 1.0)
            t_cross.append(float(t[i] + frac * (t[i + 1] - t[i])))
    tc = np.asarray(t_cross, float)
    n_idx = np.arange(tc.size, dtype=float)
    # Least-squares fit: tc = slope * n_idx + intercept
    slope, intercept = np.polyfit(n_idx, tc, 1)
    resid = tc - (slope * n_idx + intercept)
    sigma_T = float(np.std(resid, ddof=1)) if len(resid) > 2 else float("nan")
    return float(slope), sigma_T, int(tc.size)


def _log_decrement_damping(t: np.ndarray, x: np.ndarray) -> Tuple[float, float]:
    """Log-decrement from peak-picking on the (filtered) signal.

    ζ = δ / sqrt(4π² + δ²) where δ = (1/M)·Σ ln(A_k / A_{k+M}) over M-cycle groups.
    For very low damping (ζ < 0.05) the envelope is essentially flat, so ζ is close to
    zero and the period correction `T·sqrt(1-ζ²)` is negligible — but we still report it.
    Returns (zeta, T_undamped_factor) where T_undamped = T * T_undamped_factor.
    """
    if len(x) < 8:
        return 0.0, 1.0
    # Pick peaks: simple local-max detector over non-overlapping windows of ~half a period.
    # We don't know the period yet, so use a 0.3 s window as a coarse prior (works up to ~3 Hz).
    span = t[-1] - t[0] if len(t) > 1 else 0.0
    if span <= 0:
        return 0.0, 1.0
    half_period_window = max(int(0.15 * (len(x) - 1) / span), 1)
    peaks: List[Tuple[float, float]] = []
    i = 0
    n = len(x)
    while i < n:
        j = min(i + half_period_window, n)
        k = i + int(np.argmax(np.abs(x[i:j])))
        peaks.append((float(t[k]), float(x[k])))
        i = j
    if len(peaks) < 4:
        return 0.0, 1.0
    a_t, a_v = zip(*peaks)
    a_v = np.asarray(a_v, float)
    a_abs = np.abs(a_v)
    if a_abs[0] <= 0:
        return 0.0, 1.0
    # Per-cycle log-decrement: average of |ln(a_{k}/a_{k+1})| over sign-aligned neighbours.
    # The detector above captures one peak per half-period, so take every 2nd for one full period.
    log_ratios = np.log(a_abs[:-2] / a_abs[2:])
    delta = float(np.mean(log_ratios))                   # δ per period
    if delta <= 0 or not math.isfinite(delta):
        return 0.0, 1.0
    zeta = delta / math.sqrt(4.0 * math.pi ** 2 + delta ** 2)
    T_factor = math.sqrt(max(1.0 - zeta ** 2, 0.0))
    return float(zeta), float(T_factor)


def _inertia(mass: float, g: float, d: float, L: float, T: float) -> float:
    """I = m·g·d²·T² / (16·π²·L)."""
    return mass * g * d ** 2 * T ** 2 / (16.0 * math.pi ** 2 * L)


def _inertia_uncertainty(mass: float, g: float, d: float, L: float, T: float,
                         sigma_m: float, sigma_d: float, sigma_L: float,
                         sigma_T: float) -> Tuple[float, Dict[str, float]]:
    """First-order propagation; returns (sigma_I, % contribution dict).

    I depends on m, d², 1/L, T². All inputs treated as uncorrelated (they are: m is a scale
    measurement, d/L are geometry, T is from the gyro fit). The dominant terms in the bench
    experiment are usually d² (errors enter squared) and 1/L (errors enter inversely);
    T contributes twice via σ_T² scaled by (2T)².
    """
    # Partial derivatives:
    dI_dm = g * d ** 2 * T ** 2 / (16.0 * math.pi ** 2 * L)
    dI_dd = mass * g * 2.0 * d * T ** 2 / (16.0 * math.pi ** 2 * L)
    dI_dL = -mass * g * d ** 2 * T ** 2 / (16.0 * math.pi ** 2 * L ** 2)
    dI_dT = mass * g * d ** 2 * 2.0 * T / (16.0 * math.pi ** 2 * L)
    var = (dI_dm * sigma_m) ** 2 + (dI_dd * sigma_d) ** 2 + (dI_dL * sigma_L) ** 2 \
        + (dI_dT * sigma_T) ** 2
    sigma_I = math.sqrt(var)
    # Relative contributions to the variance (more interpretable than to I).
    contribs = {
        "mass":    (dI_dm * sigma_m) ** 2,
        "d":       (dI_dd * sigma_d) ** 2,
        "L":       (dI_dL * sigma_L) ** 2,
        "T":       (dI_dT * sigma_T) ** 2,
    }
    total = sum(contribs.values())
    pct = {k: (100.0 * v / total if total > 0 else 0.0) for k, v in contribs.items()}
    return sigma_I, pct


# ------------------------------------------------------------------------------ per-axis pipeline

def _analyse(t_sel: np.ndarray, x_sel_filt: np.ndarray, fs: float,
             t_off1: np.ndarray, x_off1_filt: np.ndarray,
             t_off2: np.ndarray, x_off2_filt: np.ndarray,
             dt_window: Tuple[float, float] | None) -> dict:
    """Run the period / damping / quality pipeline for one recording.

    `x_off1_filt` and `x_off2_filt` are the two OFF-axis gyros already band-passed onto
    the same uniform time grid as `x_sel_filt`. The trimming window (`dt_window`) is
    applied before band-passing upstream.
    """
    T_fft, f_peak = _fft_peak_period(x_sel_filt, fs)
    T_zc, sigma_T, n_x = _zero_crossings_period(t_sel, x_sel_filt)

    # Primary T = zero-crossing fit; correction from damping.
    zeta, T_factor = _log_decrement_damping(t_sel, x_sel_filt)
    T_zc_corr = T_zc * T_factor

    # Quality: FFT vs ZC disagreement
    if (not math.isnan(T_fft)) and (not math.isnan(T_zc)) and T_zc > 0:
        disagree_pct = 100.0 * abs(T_fft - T_zc) / T_zc
    else:
        disagree_pct = float("nan")

    # Cycles in the trimmed window.
    n_cycles = ((t_sel[-1] - t_sel[0]) / T_zc) if (T_zc == T_zc and T_zc > 0) else 0.0

    rms_sel = float(np.sqrt(np.mean(x_sel_filt ** 2)))
    rms_off1 = float(np.sqrt(np.mean(x_off1_filt ** 2))) if x_off1_filt.size else 0.0
    rms_off2 = float(np.sqrt(np.mean(x_off2_filt ** 2))) if x_off2_filt.size else 0.0
    rms_off_max = max(rms_off1, rms_off2)
    off_axis_pct = 100.0 * rms_off_max / rms_sel if rms_sel > 0 else 0.0

    return {
        "T_fft_s": T_fft,
        "f_peak_hz": f_peak,
        "T_zc_s": T_zc,
        "sigma_T_s": sigma_T,
        "n_crossings": n_x,
        "zeta": zeta,
        "T_correction_factor": T_factor,
        "T_used_s": T_zc_corr,
        "n_cycles": n_cycles,
        "disagree_pct_fft_vs_zc": disagree_pct,
        "rms_selected": rms_sel,
        "rms_off1": rms_off1,
        "rms_off2": rms_off2,
        "off_axis_pct": off_axis_pct,
        # Stored for plotting
        "t": t_sel,
        "x_filt": x_sel_filt,
    }


# ------------------------------------------------------------------------------ main pipeline

def analyse(csv_path: Path, axis: str, mass: float, d: float, L: float,
            g: float = 9.81, sigma_m: float = 0.005, sigma_d: float = 0.001,
            sigma_L: float = 0.001, start: float | None = None, end: float | None = None
            ) -> dict:
    """End-to-end pipeline: load → trim → uniform grid → detrend → band-pass → analyse."""
    if axis not in AXIS_TO_KEY:
        raise ValueError(f"--axis must be one of {list(AXIS_TO_KEY)}, got {axis!r}")
    key_sel = AXIS_TO_KEY[axis]
    # Off-axis keys = the two gyro FB columns that are NOT the selected axis. Computed
    # from the frame map: gyrox→roll in firmware naming but pitch_rate is rate-about-x,
    # so always work with the file-level keys (gyrox/gyroy/gyroz.FB) — those are what the
    # CSV actually carries.
    ALL_GYRO_KEYS = ("pid.gyrox.FB", "pid.gyroy.FB", "pid.gyroz.FB")
    off_axis_keys = [k for k in ALL_GYRO_KEYS if k != key_sel]
    if len(off_axis_keys) != 2:
        raise RuntimeError("internal: wrong number of off-axis keys for {0}".format(axis))

    data = _load_long_csv(csv_path)
    needed = [key_sel] + off_axis_keys
    missing = [k for k in needed if k not in data]
    if missing:
        raise SystemExit(
            f"[inertia] CSV missing required gyro keys {missing}. "
            "Confirm the dashboard was recording Frame B at 20 Hz during the bifilar test."
        )

    def _arr(key: str) -> Tuple[np.ndarray, np.ndarray]:
        t_list, v_list = data[key]
        return np.asarray(t_list, float), np.asarray(v_list, float)

    t_sel_raw, v_sel_raw = _arr(key_sel)
    off1_t, off1_v = _arr(off_axis_keys[0])
    off2_t, off2_v = _arr(off_axis_keys[1])
    # Use the selected-axis t_s span to define the time grid (it has the most samples).
    t_min = float(min(t_sel_raw[0], off1_t[0], off2_t[0]))
    t_max = float(max(t_sel_raw[-1], off1_t[-1], off2_t[-1]))
    if start is not None:
        t_min = max(t_min, start)
    if end is not None:
        t_max = min(t_max, end)
    if t_max <= t_min:
        raise SystemExit(f"[inertia] empty window after trimming: [{t_min}, {t_max}] s")

    # Uniform 20 Hz grid (render loop targets 20 Hz; the docstring says "ample for ~0.5 Hz").
    fs = 20.0
    dt = 1.0 / fs
    n = int(round((t_max - t_min) / dt)) + 1
    t_uniform = t_min + dt * np.arange(n)

    def _resample(t_raw: np.ndarray, v_raw: np.ndarray) -> np.ndarray:
        # Linear interpolation; clip to the available span so out-of-range samples get the
        # nearest edge value (cleaner than NaN propagation for the band-pass filter).
        return np.interp(t_uniform, t_raw, v_raw)

    x_sel = _resample(t_sel_raw, v_sel_raw)
    x_off1 = _resample(off1_t, off1_v)
    x_off2 = _resample(off2_t, off2_v)

    # Empirical mean rate over the recorded window:
    n_sel_obs = len(v_sel_raw)
    dur_obs = float(t_sel_raw[-1] - t_sel_raw[0]) if n_sel_obs > 1 else 0.0
    fs_measured = (n_sel_obs - 1) / dur_obs if dur_obs > 0 else float("nan")

    # Band-pass filter the selected axis and the two off-axis gyros on the SAME grid.
    # Hilbert / envelope works poorly on raw noisy data; the band-pass gives a clean sinusoid
    # for period and damping estimates. Off-axis signals get the same filter for a fair RMS
    # comparison (otherwise the comparison would mix passband with raw noise).
    x_sel_filt = _bandpass(x_sel - np.mean(x_sel), fs)
    x_off1_filt = _bandpass(x_off1 - np.mean(x_off1), fs)
    x_off2_filt = _bandpass(x_off2 - np.mean(x_off2), fs)

    res = _analyse(t_uniform, x_sel_filt, fs,
                   t_uniform, x_off1_filt, t_uniform, x_off2_filt,
                   dt_window=(t_min, t_max))

    T_used = res["T_used_s"]
    sigma_T = res["sigma_T_s"]
    if not math.isfinite(T_used) or T_used <= 0:
        I_hat = float("nan")
        I_unc = float("nan")
        pct = {}
    else:
        I_hat = _inertia(mass, g, d, L, T_used)
        I_unc, pct = _inertia_uncertainty(mass, g, d, L, T_used,
                                          sigma_m, sigma_d, sigma_L, sigma_T)

    return {
        "source_csv": str(csv_path),
        "axis": axis,
        "axis_key": key_sel,
        "off_axis_keys": tuple(off_axis_keys),
        "mass": mass, "g": g, "d": d, "L": L,
        "sigma_m": sigma_m, "sigma_d": sigma_d, "sigma_L": sigma_L,
        "n_samples_selected": n_sel_obs,
        "fs_measured_hz": fs_measured,
        "fs_used_hz": fs,
        "t_min": t_min, "t_max": t_max,
        # Raw plot data; off-axis order matches off_axis_keys.
        "t_uniform": t_uniform,
        "x_filt": res["x_filt"],
        "x_off_filt": (x_off1_filt, x_off2_filt),
        # Period / damping
        "T_fft_s": res["T_fft_s"],
        "f_peak_hz": res["f_peak_hz"],
        "T_zc_s": res["T_zc_s"],
        "sigma_T_s": res["sigma_T_s"],
        "n_crossings": res["n_crossings"],
        "zeta": res["zeta"],
        "T_correction_factor": res["T_correction_factor"],
        "T_used_s": T_used,
        # Quality
        "n_cycles": res["n_cycles"],
        "off_axis_pct": res["off_axis_pct"],
        "disagree_pct_fft_vs_zc": res["disagree_pct_fft_vs_zc"],
        # I
        "I": I_hat,
        "sigma_I": I_unc,
        "uncertainty_contrib_pct": pct,
    }


# ------------------------------------------------------------------------------ output

def _print_summary(r: dict) -> None:
    axis = r["axis"]
    print(f"\n=== Bifilar pendulum inertia — axis={axis} ===")
    print(f"  source CSV     : {r['source_csv']}")
    print(f"  axis key       : {r['axis_key']}  (Frame B, dashboard `flight_*.csv`)")
    print(f"  m, g, d, L     : {r['mass']:.4f} kg, {r['g']:.3f} m/s², "
          f"{r['d']:.4f} m, {r['L']:.4f} m")
    print(f"  trim window    : [{r['t_min']:.2f}, {r['t_max']:.2f}] s")
    print(f"  samples, fs    : {r['n_samples_selected']} obs at {r['fs_measured_hz']:.2f} Hz "
          f"(grid resampled to {r['fs_used_hz']:.1f} Hz uniform)")
    print(f"  cycles in trim : {r['n_cycles']:.1f}")
    print(f"  T_FFT          : {r['T_fft_s']:.5f} s   (f_peak {r['f_peak_hz']:.4f} Hz)")
    print(f"  T_ZC (fit)     : {r['T_zc_s']:.5f} s   σ_T = {r['sigma_T_s']*1e3:.3f} ms"
          f"  ({r['n_crossings']} crossings)")
    print(f"  ζ              : {r['zeta']:.4f}   T_correction = {r['T_correction_factor']:.6f}"
          f"  (sqrt(1-ζ²); negligible below ζ≈0.05 → factor ≈ 1.0000)")
    print(f"  T_used         : {r['T_used_s']:.5f} s  (ZC fit, damping-corrected)")
    I = r["I"]; sI = r["sigma_I"]
    if math.isfinite(I):
        I_str = f"{I*1e3:.3f} g·m²" if abs(I) < 1 else f"{I:.4f} kg·m²"
        sI_str = f"{sI*1e3:.3f} g·m²" if abs(sI) < 1 else f"{sI:.4f} kg·m²"
        print(f"  I              : {I_str}  ± {sI_str}  (1σ)")
        pct = r["uncertainty_contrib_pct"]
        print("  uncertainty %  : " +
              "  ".join(f"{k}={v:.1f}%" for k, v in pct.items()))
    else:
        print("  I              : n/a (could not extract a clean period)")

    # Quality gates
    print("  --- quality ---")
    if not math.isfinite(r["n_cycles"]) or r["n_cycles"] < 10:
        print("  WARN: < 10 oscillation cycles detected — period estimate is unreliable.")
    if r["off_axis_pct"] > 20.0:
        print(f"  WARN: off-axis gyro RMS is {r['off_axis_pct']:.1f}% of selected axis "
              "(threshold 20%) — rig is swaying conically, redo the run.")
    if (not math.isnan(r["disagree_pct_fft_vs_zc"])) and r["disagree_pct_fft_vs_zc"] > 1.0:
        print(f"  WARN: FFT and zero-crossing periods disagree by "
              f"{r['disagree_pct_fft_vs_zc']:.2f}% (threshold 1%) — estimate is shaky.")
    if not math.isfinite(r["sigma_T_s"]) or r["sigma_T_s"] <= 0:
        print("  WARN: σ_T from the zero-crossing fit is zero or undefined; "
              "uncertainty propagation is a lower bound.")


def _plot(r: dict, png_path: Path) -> Path:
    """2-panel figure: filtered time series with crossings + periodogram with peak."""
    fig, (ax_t, ax_f) = plt.subplots(2, 1, figsize=(10, 7), sharex=False)

    # Time series (downsampled to ~1000 pts so the PNG isn't huge)
    t = r["t_uniform"]; y = r["x_filt"]
    step = max(1, len(t) // 1000)
    ax_t.plot(t[::step], y[::step], lw=0.8, color="royalblue", label="filtered (selected axis)")
    # Two off-axis lines, named after the dashboard keys (their CSV column names).
    off_palette = ["tab:orange", "tab:green"]
    for off_key, off_signal, color in zip(r["off_axis_keys"], r["x_off_filt"], off_palette):
        ax_t.plot(t[::step], off_signal[::step], lw=0.5, color=color, alpha=0.6,
                  label=f"off-axis {off_key}")
    # Mark detected rising zero-crossings so the user can sanity-check by eye.
    if math.isfinite(r["T_zc_s"]) and r["T_zc_s"] > 0:
        sgn = np.sign(y); sgn = np.where(sgn == 0, 1.0, sgn)
        idx = np.where(np.diff(sgn) > 0)[0]
        if idx.size:
            ax_t.plot(t[idx], y[idx], "o", ms=3, color="k", alpha=0.6, label="rising zero-crossing")
    ax_t.set_xlabel("time (s)")
    ax_t.set_ylabel("gyro rate (deg/s) [filtered]")
    ax_t.set_title(
        f"axis={r['axis']}  T_zc={r['T_zc_s']:.4f} s  ζ={r['zeta']:.4f}  "
        f"cycles={r['n_cycles']:.1f}"
    )
    ax_t.grid(True, alpha=0.3); ax_t.legend(fontsize=8, loc="upper right")

    # Periodogram (Welch on the bandpassed signal; plot against the same 0.1–3 Hz band used
    # elsewhere in the pipeline so a glance tells you the algorithm picked the right peak).
    fs = r["fs_used_hz"]
    f, pxx = signal.welch(y, fs=fs, nperseg=min(len(y), 256),
                           window="hann", scaling="spectrum")
    band = (f >= 0.1) & (f <= 3.0)
    ax_f.semilogy(f[band], np.maximum(pxx[band], 1e-12), lw=1.0, color="royalblue")
    if math.isfinite(r["f_peak_hz"]):
        ax_f.axvline(r["f_peak_hz"], color="k", ls="--", lw=1.0,
                     label=f"FFT peak f={r['f_peak_hz']:.3f} Hz (T={r['T_fft_s']:.4f} s)")
        ax_f.legend(fontsize=8)
    ax_f.set_xlabel("frequency (Hz)")
    ax_f.set_ylabel("PSD (bandpass units²/Hz)")
    ax_f.grid(True, alpha=0.3)
    ax_f.set_xlim(0.1, 3.0)

    fig.tight_layout()
    fig.savefig(png_path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return png_path


def _append_csv(r: dict, csv_path: Path) -> None:
    """Append one row to inertia_results.csv (champion-store / append style)."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    header = ["timestamp_utc", "source_csv", "axis", "mass_kg", "d_m", "L_m",
              "n_cycles", "T_zc_s", "sigma_T_s", "zeta",
              "I_kgm2", "sigma_I_kgm2"]
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    I = r["I"]; sI = r["sigma_I"]
    row = [ts, r["source_csv"], r["axis"], f"{r['mass']:.6f}", f"{r['d']:.6f}",
           f"{r['L']:.6f}", f"{r['n_cycles']:.3f}", f"{r['T_zc_s']:.6f}",
           f"{r['sigma_T_s']:.6e}", f"{r['zeta']:.6f}",
           f"{I:.6e}" if math.isfinite(I) else "nan",
           f"{sI:.6e}" if math.isfinite(sI) else "nan"]
    write_header = not csv_path.exists()
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(header)
        w.writerow(row)


def _plot_and_append(r: dict, out_dir: Path) -> Tuple[Path, Path]:
    stem = Path(r["source_csv"]).stem + f"_inertia_{r['axis']}"
    png_path = out_dir / f"{stem}.png"
    csv_path = out_dir / "inertia_results.csv"
    _plot(r, png_path)
    _append_csv(r, csv_path)
    return png_path, csv_path


# ------------------------------------------------------------------------------ selftest

def _selftest() -> None:
    """Synthetic damped sinusoid → run the pipeline in-memory and assert close to truth.

    Synthetic inputs:
        T_target = 2.0 s, ζ_target = 0.02, fs = 20 Hz, N = 600 (30 s)
        selected axis  : x(t) = A·exp(-zeta·ωn·t)·sin(2π·t/T) + small_off + noise
        off-axis y      : 5% of selected (will trigger the >20% WARN check; we expect 5%, well under)
        off-axis z      : 5% of selected
    The synthetic (m, g, d, L) imply an I_target. We assert the pipeline recovers T within
    0.5% and I within 1%.
    """
    rng = np.random.default_rng(20260705)
    T_true = 2.0
    zeta_true = 0.02
    fs = 20.0
    N = int(30.0 * fs)
    t = np.arange(N) / fs
    omega_n = 2.0 * np.pi / T_true
    A0 = 60.0
    decay = np.exp(-zeta_true * omega_n * t)
    # Synthesize three orthogonal samples so the selected axis (yaw → pid.gyroz.FB) carries
    # the FULL oscillation amplitude and the two off-axis gyros are 5% of that — matching
    # the warn threshold logic in §7. Anything else and the off-axis % gate trips
    # spuriously on the selftest (real bench data: the selected axis is always the largest
    # by design).
    main = A0 * decay * np.sin(2.0 * np.pi * t / T_true) + rng.normal(0.0, 0.5, N)
    off_y = 0.05 * A0 * decay * np.sin(2.0 * np.pi * t / T_true + 0.5) + rng.normal(0.0, 0.2, N)
    off_x = 0.05 * A0 * decay * np.cos(2.0 * np.pi * t / T_true + 1.0) + rng.normal(0.0, 0.2, N)

    # Bridge to the analysis pipeline by writing a long-format CSV the loader can read.
    tmp = Path.cwd() / ".inertia_selftest_input.csv"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["t_s", "frame", "key", "value"])
        for i in range(N):
            # axis=yaw → pid.gyroz.FB carries the main signal
            w.writerow([f"{t[i]:.4f}", "B", "pid.gyrox.FB", f"{off_x[i]:.6f}"])
            w.writerow([f"{t[i]:.4f}", "B", "pid.gyroy.FB", f"{off_y[i]:.6f}"])
            w.writerow([f"{t[i]:.4f}", "B", "pid.gyroz.FB", f"{main[i]:.6f}"])

    # Synthetic rig geometry (true I implied by synthetic T).
    m = 0.9885
    d = 0.4
    L = 1.2
    g = 9.81
    sigma_m, sigma_d, sigma_L = 0.005, 0.001, 0.001

    r = analyse(tmp, axis="yaw", mass=m, d=d, L=L, g=g,
                sigma_m=sigma_m, sigma_d=sigma_d, sigma_L=sigma_L)

    T_used = r["T_used_s"]
    I_used = r["I"]

    # Expected period from the synthetic inputs (after damping correction).
    # T_used ≈ T_true * sqrt(1-ζ²) ≈ 1.99980 s
    T_expected = T_true * math.sqrt(1.0 - zeta_true ** 2)
    I_expected = _inertia(m, g, d, L, T_expected)

    T_err_pct = abs(T_used - T_expected) / T_expected * 100.0
    I_err_pct = abs(I_used - I_expected) / I_expected * 100.0

    print("\n--- selftest summary ---")
    print("  T_true         = {0:.4f} s".format(T_true))
    print("  T_fft          = {0:.4f} s   (peak f = {1:.4f} Hz)".format(r['T_fft_s'], r['f_peak_hz']))
    print("  T_zc(fit)      = {0:.4f} s   n_crossings = {1}".format(r['T_zc_s'], r['n_crossings']))
    print("  zeta           = {0:.5f}   T_factor = {1:.6f}".format(r['zeta'], r['T_correction_factor']))
    print("  T_expected     = {0:.4f} s (after sqrt(1-zeta^2) correction)".format(T_expected))
    print("  T_recovered    = {0:.4f} s   error = {1:.3f}%  (must be <0.5%)".format(T_used, T_err_pct))
    print("  I_expected     = {0:.4e} kg.m^2".format(I_expected))
    print("  I_recovered    = {0:.4e} kg.m^2   error = {1:.3f}%  (must be <1%)".format(I_used, I_err_pct))
    print("  sigma_T        = {0:.3f} ms".format(r['sigma_T_s']*1e3))
    print("  sigma_I        = {0:.3e} kg.m^2".format(r['sigma_I']))
    print("  cycles         = {0:.1f}".format(r['n_cycles']))
    print("  off-axis pct   = {0:.1f}%".format(r['off_axis_pct']))
    print("  FFT vs ZC pct  = {0:.2f}%".format(r['disagree_pct_fft_vs_zc']))

    tmp.unlink(missing_ok=True)

    assert T_err_pct < 0.5, f"T recovered error {T_err_pct:.3f}% exceeds 0.5% gate"
    assert I_err_pct < 1.0, f"I recovered error {I_err_pct:.3f}% exceeds 1.0% gate"
    print("[inertia selftest] PASSED")


# ------------------------------------------------------------------------------ argparse

def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="Bifilar-pendulum moment-of-inertia analysis (docs/bench_characterization.md §1)."
    )
    ap.add_argument("log", nargs="?",
                    help="dashboard flight-recording CSV (the long-format t_s,frame,key,value "
                         "file written by the 20 Hz 'Flight recording' button). Not required "
                         "with --selftest.")
    ap.add_argument("--axis", choices=list(AXIS_TO_KEY.keys()),
                    help="physical axis under test (selects which body-frame gyro FB column)")
    ap.add_argument("--mass", type=float, help="drone mass [kg]")
    ap.add_argument("--d", type=float, help="horizontal separation of the two strings [m]")
    ap.add_argument("--L", type=float, help="string length (vertical) [m]")
    ap.add_argument("--g", type=float, default=9.81, help="gravity (default 9.81 m/s²)")
    ap.add_argument("--sigma-m", type=float, default=0.005,
                    help="1σ mass uncertainty (default 5 g = 0.005 kg)")
    ap.add_argument("--sigma-d", type=float, default=0.001,
                    help="1σ d uncertainty (default 1 mm = 0.001 m)")
    ap.add_argument("--sigma-L", type=float, default=0.001,
                    help="1σ L uncertainty (default 1 mm = 0.001 m)")
    ap.add_argument("--start", type=float, default=None,
                    help="trim window start [s] (default: earliest sample)")
    ap.add_argument("--end", type=float, default=None,
                    help="trim window end [s] (default: latest sample)")
    ap.add_argument("--out", default=None,
                    help="output directory (default: <repo>/ground_station/logs/bench). "
                         "Writes <stem>_inertia_<axis>.png and appends to inertia_results.csv.")
    ap.add_argument("--selftest", action="store_true",
                    help="run the in-memory synthetic-data pipeline and exit (no CSV needed).")
    return ap


def main(argv: List[str] | None = None) -> int:
    ap = _build_parser()
    args = ap.parse_args(argv)

    if args.selftest:
        _selftest()
        return 0

    if args.log is None:
        ap.error("a flight CSV is required (or pass --selftest)")
    for name in ("axis", "mass", "d", "L"):
        if getattr(args, name) is None:
            ap.error(f"--{name} is required (or pass --selftest)")
    csv_path = Path(args.log)
    if not csv_path.exists():
        print(f"[inertia] log not found: {csv_path}", file=sys.stderr)
        return 1

    out_dir = Path(args.out) if args.out else (
        csv_path.resolve().parent.parent / "logs" / "bench"
        if csv_path.resolve().parent.name == "logs"
        else Path("ground_station/logs/bench").resolve()
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    r = analyse(csv_path, args.axis, args.mass, args.d, args.L, args.g,
                args.sigma_m, args.sigma_d, args.sigma_L, args.start, args.end)
    _print_summary(r)
    png, csv_out = _plot_and_append(r, out_dir)
    print(f"\n[inertia] plot -> {png}")
    print(f"[inertia] appended row -> {csv_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
