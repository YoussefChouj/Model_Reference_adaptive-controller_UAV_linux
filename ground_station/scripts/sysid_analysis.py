"""Offline system-identification analysis (ADR-0004, Phase 4).

Consumes a captured high-rate ID-frame log (firmware frame 0x03, enabled via
CMD 0x0F idx 11) and, per excited axis, estimates:

  * the plant frequency response x/u (DIRECT method, Phi_xu/Phi_uu), where the
    plant input is the *total* effort u = u_nom + u_ad (per ADR-0004 dec. 1),
  * the loop response x/r (measured rate over the total rate setpoint),
  * coherence as a quality gate (greys out unreliable frequency bins),
  * the -3 dB bandwidth of x/r -> a recommended `ref_model_bw` (rad/s),
  * a 1st-order lumped model  J*xdot + b*x = u  (plant G = 1/(b + J s)),
    fit two ways: from the FRF over high-coherence bins (PRIMARY — robust to
    feedback) and by time-domain least squares (cross-check only).

Closed-loop excitation note (StabilizerTask: the dither is SUPERIMPOSED on the
rate setpoint with +=, not overwritten):
  The outer angle/position cascade stays active during a run, so `r` is the
  *closed-loop* total setpoint (outer-loop output + dither), NOT a pure probe.
  The plant estimate x/u is still valid because u is the actual plant input and
  the deliberate dither makes it persistently exciting -> coherence stays high
  in the excited band, where the direct-method bias is small. The time-domain
  J fit, by contrast, is biased in closed loop (u correlates with x's noise
  through the feedback), so J is reported from the FRF fit and the LS value is
  shown only as a sanity cross-check.

Caveat (ADR-0004 "Constraints Created"): J and the torque effectiveness in
`mrac_to_mixer` are coupled in flight data. The lumped input->output model is
identifiable and sufficient for MRAC tuning, but the reported J is NOT a
physical inertia without an independent effectiveness measurement.

Data contract (matches ground_station/comm/serial_bridge.py::_unpack_frame_id
and the CSV written by FlightLogger.log_snapshot("ID", ...)):

  CSV columns: t_s, frame, key, value     (flat long format)
  ID-frame keys used:
    id.sample_counter                       firmware 100 Hz tick (time base)
    id.<axis>.r      rate setpoint  (rad/s) -> total (outer-loop output + dither)
    id.<axis>.x      measured rate (rad/s)  -> plant output
    id.<axis>.u_nom  nominal PID effort (SI)
    id.<axis>.u_ad   adaptive effort   (SI) ; plant input u = u_nom + u_ad
    id.<axis>.xm     reference-model state (rad/s) [not used here]
  axis in {pitch, roll, yaw, z}

Time base: id.sample_counter increments once per emitted frame at 100 Hz, so
dt = 1/100 s. We use the counter (not the host arrival time t_s, which carries
wireless jitter) and skip across any counter gaps from dropped frames.

Usage:
    python sysid_analysis.py LOG.csv [--axis pitch] [--coherence-thresh 0.6]
                                     [--out DIR] [--fs 100]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from scipy import signal, optimize

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Reuse the canonical flat-CSV loader (t_s, frame, key, value) -> {key: (t, v)}.
try:
    from .analyze_flight_log import load_flight_data
except ImportError:
    _here = Path(__file__).resolve().parent
    if str(_here) not in sys.path:
        sys.path.insert(0, str(_here))
    from analyze_flight_log import load_flight_data

AXES = ("pitch", "roll", "yaw", "z")
DEFAULT_FS = 100.0           # firmware emits frame 0x03 at 100 Hz
COUNTER_KEY = "id.sample_counter"
MIN_SAMPLES = 256            # need a few Welch windows for a usable estimate

# Link-quality gates. Telemetry frame drops (weak wireless link / drone too far) fragment the
# capture; the FRF is fit on the largest gap-free segment, so heavy drops shrink it until the
# estimate becomes meaningless (e.g. a spurious sub-1 Hz "bandwidth"). These flag that.
LQ_RECV_GOOD = 0.97          # >= this fraction of expected frames received -> good link
LQ_RECV_WARN = 0.85          # below this -> unreliable, results likely garbage
LQ_SEG_MIN = 2000            # largest gap-free segment (samples) needed for a trustworthy fit


def _link_quality(data):
    """Assess telemetry completeness from the firmware sample counter.

    Returns dict with received-frame fraction, gap count, largest gap-free
    segment, and a verdict in {GOOD, WARN, BAD}. A WARN/BAD run means the
    wireless link dropped frames (drone likely too far from the receiver).
    """
    ctr_tup = data.get(COUNTER_KEY)
    if not ctr_tup or len(ctr_tup[1]) < 2:
        return None
    ctr = np.asarray(ctr_tup[1], float)
    # Restrict to the largest monotonic block so a mid-log counter reset (two runs in one
    # file) doesn't make 'span' meaningless.
    resets = np.where(np.diff(ctr) < 0)[0]
    bnds = np.concatenate(([0], resets + 1, [len(ctr)]))
    bi = max(range(len(bnds) - 1), key=lambda i: bnds[i + 1] - bnds[i])
    lo, hi = int(bnds[bi]), int(bnds[bi + 1])
    blk = ctr[lo:hi]
    received = len(blk)
    span = int(blk[-1] - blk[0]) + 1           # frames the firmware emitted over this block
    recv_frac = received / span if span > 0 else 0.0
    gaps = int(np.count_nonzero(np.diff(blk) != 1.0))
    seg_bounds = np.concatenate(([0], np.where(np.diff(blk) != 1.0)[0] + 1, [received]))
    largest_seg = int(max(seg_bounds[1:] - seg_bounds[:-1])) if received else 0
    if recv_frac >= LQ_RECV_GOOD and largest_seg >= LQ_SEG_MIN:
        verdict = "GOOD"
    elif recv_frac >= LQ_RECV_WARN and largest_seg >= LQ_SEG_MIN:
        verdict = "WARN"
    else:
        verdict = "BAD"
    return {"received": received, "span": span, "recv_frac": recv_frac,
            "gaps": gaps, "largest_seg": largest_seg, "verdict": verdict}


def _get(data, axis, field):
    """Return the value array for id.<axis>.<field>, or None."""
    tup = data.get(f"id.{axis}.{field}")
    return np.asarray(tup[1], float) if tup else None


def _reconstruct_axis(data, axis, fs, include_uad):
    """Pull r, x, u for one axis on a uniform 1/fs grid.

    Plant input u = u_nom by default. u_ad is the MRAC adaptive effort; it only
    reaches the motors when output injection is ON (CMD 0x0F idx 10). SysID is run
    in shadow mode (injection OFF) so the plant sees pure PID -> u = u_nom. Pass
    include_uad=True only if a run had injection ON (then u = u_nom + u_ad).

    The host CSV timestamps carry link jitter, so we resample onto the firmware
    sample_counter and drop runs across counter gaps (dropped frames). Returns
    (r, x, u, d, dt) where d is the exogenous dither instrument (or r for pre-v5
    logs without id.dither); None if the axis is absent / too short.
    """
    r = _get(data, axis, "r")
    x = _get(data, axis, "x")
    u_nom = _get(data, axis, "u_nom")
    u_ad = _get(data, axis, "u_ad")
    if r is None or x is None or u_nom is None or u_ad is None:
        return None

    # Exogenous excitation/dither (proto >= 5). The CLEAN IV instrument: unlike r (= outer-loop
    # output + dither), the dither is uncorrelated with in-loop noise, so it stays a valid
    # instrument at low frequency where the outer loop contaminates r. Fall back to r for older logs.
    dith_tup = data.get("id.dither")
    d_full = np.asarray(dith_tup[1], float) if dith_tup else None

    n = min(len(r), len(x), len(u_nom), len(u_ad))
    if d_full is not None:
        n = min(n, len(d_full))
    if n < MIN_SAMPLES:
        return None
    r, x = r[:n], x[:n]
    u = (u_nom[:n] + u_ad[:n]) if include_uad else u_nom[:n]
    d = d_full[:n] if d_full is not None else r.copy()

    # Largest contiguous run between sample-counter gaps (best uniform-dt segment).
    ctr_tup = data.get(COUNTER_KEY)
    if ctr_tup and len(ctr_tup[1]) >= n:
        ctr = np.asarray(ctr_tup[1][:n], float)
        gaps = np.where(np.diff(ctr) != 1.0)[0]
        bounds = np.concatenate(([0], gaps + 1, [n]))
        best = max(range(len(bounds) - 1), key=lambda i: bounds[i + 1] - bounds[i])
        lo, hi = bounds[best], bounds[best + 1]
        if hi - lo >= MIN_SAMPLES:
            r, x, u, d = r[lo:hi], x[lo:hi], u[lo:hi], d[lo:hi]
    return r, x, u, d, 1.0 / fs


def _tfe(out, inp, fs, nperseg):
    """Cross-spectral transfer estimate out/in: f, complex H, coherence.

    H = Pxy / Pxx  (csd-based tfestimate); coherence is the standard magnitude-
    squared coherence used as the per-bin quality gate.
    """
    f, pxx = signal.welch(inp, fs=fs, nperseg=nperseg)
    _, pxy = signal.csd(inp, out, fs=fs, nperseg=nperseg)
    _, coh = signal.coherence(inp, out, fs=fs, nperseg=nperseg)
    with np.errstate(divide="ignore", invalid="ignore"):
        h = np.where(pxx > 0, pxy / pxx, 0.0)
    return f, h, coh


def _plant_iv(x, u, instr, fs, nperseg):
    """Plant FRF x/u via the INDIRECT / instrument-variable method.

    The direct estimate Phi_xu/Phi_uu is biased in closed loop because u (the rate-
    PID output) is computed from x through the controller, so it recovers ~ -1/C
    instead of the plant G (this produced a negative J on real logs). Using an
    exogenous instrument `instr` (ideally the raw dither id.dither; r as fallback):

        G = (x/instr) / (u/instr) = Phi_x,instr / Phi_u,instr

    is consistent regardless of the in-loop feedback/noise. With the true dither as
    instrument this is unbiased even at low frequency (r as instrument is contaminated
    there by the outer loop). Per-bin gate is the MIN of the two coherences.
    """
    f, h_xi, coh_xi = _tfe(x, instr, fs, nperseg)
    _, h_ui, coh_ui = _tfe(u, instr, fs, nperseg)
    with np.errstate(divide="ignore", invalid="ignore"):
        h = np.where(np.abs(h_ui) > 0, h_xi / h_ui, 0.0)
    coh = np.minimum(coh_xi, coh_ui)
    return f, h, coh


def _bandwidth_3db(f, mag, coh, thresh):
    """-3 dB closed-loop bandwidth from the coherent low-frequency gain.

    Reference DC gain = mean |H| over the lowest coherent bins; bandwidth is the
    first frequency where |H| falls below DC/sqrt(2). Returns None if no clean band.
    """
    ok = (coh >= thresh) & (f > 0)
    if not np.any(ok):
        return None
    fo, mo = f[ok], mag[ok]
    dc = float(np.mean(mo[: max(1, len(mo) // 5)]))
    if dc <= 0:
        return None
    below = np.where(mo < dc / np.sqrt(2.0))[0]
    return float(fo[below[0]]) if len(below) else float(fo[-1])


def _fit_first_order(x, u, dt):
    """Time-domain least-squares fit of J*xdot + b*x = u  (xdot via central diff).

    Returns (J, b, r2). CROSS-CHECK ONLY: in closed loop u is correlated with x's
    measurement noise through the feedback, biasing this fit. Prefer the FRF fit
    (_fit_first_order_freq). J,b are lumped input->output coefficients, not
    physical inertia (see module docstring caveat).
    """
    xdot = np.gradient(x, dt)
    A = np.column_stack([xdot, x])
    coef, *_ = np.linalg.lstsq(A, u, rcond=None)
    J, b = float(coef[0]), float(coef[1])
    resid = u - A @ coef
    ss_res = float(np.sum(resid ** 2))
    ss_tot = float(np.sum((u - np.mean(u)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    return J, b, r2


def _fit_first_order_freq(f, h_ol, coh, thresh, fit_fmin=0.0, fit_fmax=10.0):
    """Fit plant G(jw) = 1/(b + J*jw) to the plant FRF over a coherent band.

    Inverting the model: 1/G = b + J*(jw), which is linear and separable —
    Re(1/H) = b, Im(1/H) = w*J. We solve both by coherence-weighted least squares
    using bins with coherence >= thresh AND fit_fmin <= f <= fit_fmax.

    The band limit matters: the rigid-body rate plant is integrator-like (~1/(Js))
    only in a mid band; above it real airframes pick up extra phase lag (mixer/ESC
    delay, gyro filter) that the first-order model can't represent, and including
    those bins drives J negative (verified on flight logs). Keep fit_fmax at/below
    where the FRF phase passes ~-135 deg (read it off the Bode plot). This estimate
    is robust to the feedback that biases the time-domain fit. Returns (J, b, bins).
    """
    ok = (coh >= thresh) & (f >= max(fit_fmin, 1e-9)) & (f <= fit_fmax) & (np.abs(h_ol) > 0)
    if np.count_nonzero(ok) < 2:
        return float("nan"), float("nan"), 0
    w = 2.0 * np.pi * f[ok]
    inv = 1.0 / h_ol[ok]            # = b + j*w*J  (ideal 1st-order plant)
    wt = coh[ok]                    # weight coherent bins more
    # b from the real part (coherence-weighted mean), J from Im(1/H) = w*J.
    b = float(np.sum(wt * inv.real) / np.sum(wt))
    J = float(np.sum(wt * w * inv.imag) / np.sum(wt * w * w))
    return J, b, int(np.count_nonzero(ok))


def _fit_integrator_pole_delay(f, h_ol, coh, thresh, fit_fmin=0.0, fit_fmax=10.0):
    """Fit the rate plant  G(jw) = K / (jw * (1 + jw/p)) * exp(-jw*T).

    This is the correct low-order structure for an angular-RATE plant: a rigid-body
    integrator (rate/torque ~ 1/(J*s)) in series with one lumped actuator/ESC/gyro-filter
    lag pole p and a transport delay T. It spans 0..-270 deg of phase, so unlike the
    first-order 1/(b+J*s) it CAN represent the measured FRF (on real roll logs the phase
    is already < -90 deg at the lowest excited bin and sweeps past -180 deg by ~5 Hz).
    That phase is exactly why the first-order fit returned a non-physical negative J:
    Im(1/G)=w*J is forced negative when the true phase is < -90 deg. This model removes
    that artifact and is the structure to seed a 2nd-order(+delay) MRAC reference model.

    Complex, coherence-weighted least squares over the gate band (coh>=thresh and
    fit_fmin<=f<=fit_fmax). Returns a dict:
        K (integrator gain), pole_radps, delay_s, vaf (% variance accounted for), bins.
    NaN params / bins<4 if the coherent band is too thin to fit.
    """
    nan = float("nan")
    ok = (coh >= thresh) & (f >= max(fit_fmin, 1e-9)) & (f <= fit_fmax) & (np.abs(h_ol) > 0)
    nb = int(np.count_nonzero(ok))
    if nb < 4:
        return {"K": nan, "pole_radps": nan, "delay_s": nan, "vaf": nan, "bins": nb}
    w = 2.0 * np.pi * f[ok]
    G = h_ol[ok]
    wt = np.sqrt(np.clip(coh[ok], 0.0, 1.0))   # amplitude-like coherence weight
    jw = 1j * w

    def model(p):
        K, pole, T = p
        return K / (jw * (1.0 + jw / pole)) * np.exp(-jw * T)

    def resid(p):
        e = (model(p) - G) * wt
        return np.concatenate([e.real, e.imag])

    # Seed: K ~ |G|*w at the lowest bin (integrator gain), lag pole mid-band, small delay.
    K0 = float(np.abs(G[0]) * w[0])
    p0 = [max(K0, 1.0), 20.0, 0.02]
    try:
        sol = optimize.least_squares(
            resid, p0, bounds=([1e-3, 1.0, 0.0], [1e6, 1e3, 0.3]), max_nfev=4000)
        K, pole, T = (float(v) for v in sol.x)
        e = model(sol.x) - G
        var_g = float(np.var(G))
        vaf = 100.0 * (1.0 - float(np.var(e)) / var_g) if var_g > 0 else nan
    except Exception:
        return {"K": nan, "pole_radps": nan, "delay_s": nan, "vaf": nan, "bins": nb}
    return {"K": K, "pole_radps": pole, "delay_s": T, "vaf": vaf, "bins": nb}


def _fit_pure_integrator(f, h_ol, coh, thresh, fit_fmin=0.0, fit_fmax=10.0):
    """Fit G(jw) = K/(jw) * exp(-jw*T) — a PURE INTEGRATOR (relative degree 1).

    For axes with no identifiable lag pole in the excited band (quad YAW: driven by weak
    motor drag-torque, so it is a clean integrator with K ~ 37 and no fast pole), the
    integrator+pole+delay fit rails its pole/delay and collapses VAF even though the plant
    is a clean integrator. This 2-param model recovers K (and any small delay) directly.
    Returns dict {K, delay_s, vaf, bins}; NaN if the coherent band is too thin.
    """
    nan = float("nan")
    ok = (coh >= thresh) & (f >= max(fit_fmin, 1e-9)) & (f <= fit_fmax) & (np.abs(h_ol) > 0)
    nb = int(np.count_nonzero(ok))
    if nb < 3:
        return {"K": nan, "delay_s": nan, "vaf": nan, "bins": nb}
    w = 2.0 * np.pi * f[ok]
    G = h_ol[ok]
    wt = np.sqrt(np.clip(coh[ok], 0.0, 1.0))
    jw = 1j * w

    def model(p):
        K, T = p
        return K / jw * np.exp(-jw * T)

    def resid(p):
        e = (model(p) - G) * wt
        return np.concatenate([e.real, e.imag])

    K0 = float(np.median(np.abs(G) * w))       # robust integrator-gain seed: |G|*w = K
    try:
        sol = optimize.least_squares(
            resid, [max(K0, 1.0), 0.0], bounds=([1e-3, 0.0], [1e6, 0.3]), max_nfev=2000)
        K, T = float(sol.x[0]), float(sol.x[1])
        e = model(sol.x) - G
        var_g = float(np.var(G))
        vaf = 100.0 * (1.0 - float(np.var(e)) / var_g) if var_g > 0 else nan
    except Exception:
        return {"K": nan, "delay_s": nan, "vaf": nan, "bins": nb}
    return {"K": K, "delay_s": T, "vaf": vaf, "bins": nb}


def _excitation_kind(data):
    """Classify the run from the dither crest factor (peak/RMS).

    Swept-sine (chirp) sits at one frequency at a time -> crest ~1.4. A 20-tone
    Schroeder multisine has crest ~3+. Returns (kind, peak, crest); 'unknown' if no
    dither channel (pre-v5 logs).
    """
    nan = float("nan")
    tup = data.get("id.dither")
    if not tup:
        return "unknown", nan, nan
    d = np.asarray(tup[1], float)
    d = d[np.abs(d) > 1e-6]
    if len(d) < 10:
        return "unknown", nan, nan
    peak = float(np.max(np.abs(d)))
    rms = float(np.sqrt(np.mean(d ** 2)))
    crest = peak / rms if rms > 0 else nan
    kind = "chirp" if (crest == crest and crest < 2.0) else "multisine"
    return kind, peak, crest


def analyse_axis(data, axis, fs, coh_thresh, include_uad=False, fit_fmin=0.0, fit_fmax=10.0):
    seg = _reconstruct_axis(data, axis, fs, include_uad)
    if seg is None:
        return None
    r, x, u, d, dt = seg
    nperseg = min(256, len(x) // 4 * 2 or 64)

    # Plant x/u via the IV/indirect method — robust to the closed-loop feedback that biases
    # the direct Phi_xu/Phi_uu estimate. Instrument = the exogenous dither d (clean at all
    # frequencies). h_ol/coh_ol below are therefore the IV plant, not the raw direct estimate.
    f_ol, h_ol, coh_ol = _plant_iv(x, u, d, fs, nperseg)  # plant x/u (instrument = dither)
    f_cl, h_cl, coh_cl = _tfe(x, r, fs, nperseg)          # loop response x/r

    bw_hz = _bandwidth_3db(f_cl, np.abs(h_cl), coh_cl, coh_thresh)
    # PRIMARY plant model: integrator + lag pole + delay (correct order for a rate plant;
    # represents the phase passing -90/-180 deg that broke the old first-order J fit).
    model = _fit_integrator_pole_delay(f_ol, h_ol, coh_ol, coh_thresh, fit_fmin, fit_fmax)
    model["kind"] = "integrator+pole+delay"
    # Relative-degree-1 fallback: if the pole/delay fit is poor (e.g. YAW, a pure integrator with
    # no identifiable pole -> the 3-param fit rails and VAF collapses), try a pure integrator K/s
    # and prefer it when it explains the FRF at least as well. Keeps roll/pitch (VAF ~98%) on the
    # full model untouched.
    vaf_full = model.get("vaf", float("nan"))
    if (vaf_full != vaf_full) or vaf_full < 85.0:
        # Low-bandwidth axes (yaw) live below ~2 Hz; the 256-pt window gives only ~0.78 Hz bins,
        # too few to fit there. Recompute the IV plant at high resolution JUST for this fallback
        # (the primary fit + bandwidth keep the 256-pt window so roll/pitch are unchanged).
        nperseg_hi = int(min(2048, max(nperseg, len(x) // 4)))
        f_hi, h_hi, coh_hi = _plant_iv(x, u, d, fs, nperseg_hi)
        integ = _fit_pure_integrator(f_hi, h_hi, coh_hi, coh_thresh, fit_fmin, fit_fmax)
        vaf_i = integ.get("vaf", float("nan"))
        if vaf_i == vaf_i and ((vaf_full != vaf_full) or vaf_i >= vaf_full):
            model = {"K": integ["K"], "pole_radps": float("inf"), "delay_s": integ["delay_s"],
                     "vaf": vaf_i, "bins": integ["bins"], "kind": "pure integrator (K/s)"}

    return {
        "axis": axis, "n": len(x), "dt": dt, "fs": fs, "coh_thresh": coh_thresh,
        "f_ol": f_ol, "h_ol": h_ol, "coh_ol": coh_ol,
        "f_cl": f_cl, "h_cl": h_cl, "coh_cl": coh_cl,
        "bw_hz": bw_hz,
        "ref_model_bw_radps": (2.0 * np.pi * bw_hz) if bw_hz else None,
        "model": model,                                  # integrator+pole+delay (primary)
    }


def plot_axis(res, out_dir, coh_thresh):
    f_ol, h_ol, coh_ol = res["f_ol"], res["h_ol"], res["coh_ol"]
    f_cl, h_cl, coh_cl = res["f_cl"], res["h_cl"], res["coh_cl"]
    eps = 1e-12

    fig, (axm, axp, axc) = plt.subplots(3, 1, figsize=(9, 9), sharex=True)
    for f, h, coh, lbl, col in (
        (f_ol, h_ol, coh_ol, "plant x/u (IV, instr=dither)", "tab:red"),
        (f_cl, h_cl, coh_cl, "loop response x/r", "royalblue"),
    ):
        m = 20.0 * np.log10(np.abs(h) + eps)
        good = coh >= coh_thresh
        axm.plot(f, m, color=col, alpha=0.25, lw=1.0)
        axm.plot(np.where(good, f, np.nan), np.where(good, m, np.nan),
                 color=col, lw=1.6, label=lbl)
        ph = np.degrees(np.unwrap(np.angle(h)))
        axp.plot(np.where(good, f, np.nan), np.where(good, ph, np.nan), color=col, lw=1.6)
        axc.plot(f, coh, color=col, lw=1.4, label=lbl)

    # Overlay the fitted plant model G = K/(s(1+s/p))e^-sT for visual goodness-of-fit.
    mdl = res.get("model")
    if mdl and mdl.get("vaf") == mdl.get("vaf") and not np.isnan(mdl.get("vaf", np.nan)):
        band = f_ol > 0
        ww = 2.0 * np.pi * f_ol[band]
        jw = 1j * ww
        with np.errstate(divide="ignore", invalid="ignore"):
            Gm = mdl["K"] / (jw * (1.0 + jw / mdl["pole_radps"])) * np.exp(-jw * mdl["delay_s"])
        axm.plot(f_ol[band], 20.0 * np.log10(np.abs(Gm) + eps), color="k", ls="--", lw=1.2,
                 label=f"plant fit (VAF {mdl['vaf']:.0f}%)")
        axp.plot(f_ol[band], np.degrees(np.unwrap(np.angle(Gm))), color="k", ls="--", lw=1.2)

    if res["bw_hz"]:
        axm.axvline(res["bw_hz"], color="k", ls="--", alpha=0.6,
                    label=f"BW {res['bw_hz']:.2f} Hz")
    axc.axhline(coh_thresh, color="k", ls=":", alpha=0.7, label=f"thresh {coh_thresh}")
    axm.set_ylabel("Magnitude (dB)"); axm.legend(fontsize=8); axm.grid(True, alpha=0.3)
    axm.set_title(f"{res['axis'].capitalize()} system-ID  (greyed = coherence < {coh_thresh})")
    axp.set_ylabel("Phase (deg)"); axp.grid(True, alpha=0.3)
    axc.set_ylabel("Coherence"); axc.set_xlabel("Frequency (Hz)")
    axc.set_ylim(0, 1.05); axc.legend(fontsize=8); axc.grid(True, alpha=0.3)
    fig.tight_layout()
    path = out_dir / f"sysid_{res['axis']}.png"
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return path


def print_summary(results):
    print("\n=== System-ID summary (ADR-0004 Phase 4) ===")
    print(f"{'axis':7} {'n':>6} {'BW(Hz)':>8} {'ref_bw(rad/s)':>14} "
          f"{'K':>9} {'pole(Hz)':>9} {'delay(ms)':>10} {'VAF%':>7} {'bins':>5}")
    for r in results:
        bw = f"{r['bw_hz']:.3f}" if r["bw_hz"] else "  n/a "
        rmb = f"{r['ref_model_bw_radps']:.2f}" if r["ref_model_bw_radps"] else "n/a"
        m = r["model"]
        pole_hz = m["pole_radps"] / (2.0 * np.pi) if m["pole_radps"] == m["pole_radps"] else float("nan")
        print(f"{r['axis']:7} {r['n']:>6} {bw:>8} {rmb:>14} "
              f"{m['K']:>9.4g} {pole_hz:>9.3f} {m['delay_s']*1e3:>10.1f} "
              f"{m['vaf']:>7.1f} {m['bins']:>5}")
    print("\nPlant model G(s) = K / (s*(1 + s/p)) * e^(-s*T): integrator + lag pole p + delay T,")
    print("fit to the IV plant FRF over high-coherence bins. This is the correct structure for")
    print("a rate plant (phase passes -90/-180 deg) and replaces the old first-order J fit that")
    print("returned a non-physical negative J. ref_bw = closed-loop -3 dB bandwidth of x/r.")


def write_report(results, out_dir, log_path, fs, fs_note, kind, peak, crest, vbat=None, lq=None):
    """Write a human-readable Markdown report alongside the Bode plot(s)."""
    L = []
    L.append(f"# System-ID analysis — {log_path.name}\n")
    if lq is not None and lq["verdict"] != "GOOD":
        L.append(f"> ⚠️ **LINK QUALITY {lq['verdict']} — results may be UNRELIABLE.** Only "
                 f"{lq['recv_frac']*100:.0f}% of frames were received ({lq['gaps']} gaps; largest "
                 f"clean segment {lq['largest_seg']} samples). The wireless link dropped frames — "
                 f"fly the drone closer to the receiver and re-run.\n")
    L.append(f"- **Source log**: `{log_path}`")
    if lq is not None:
        L.append(f"- **Link quality**: {lq['verdict']} "
                 f"({lq['recv_frac']*100:.0f}% frames received, {lq['gaps']} gaps, "
                 f"largest clean segment {lq['largest_seg']} samples)")
    L.append(f"- **Sample rate (auto)**: {fs:.1f} Hz{(' — ' + fs_note) if fs_note else ''}")
    if kind != "unknown":
        L.append(f"- **Excitation**: {kind}  (dither peak {peak:.1f}, crest factor {crest:.2f})")
    if vbat is not None and len(vbat) and np.isfinite(vbat).any():
        vb = vbat[np.isfinite(vbat)]
        L.append(f"- **Battery (operating point)**: {vb.mean():.2f} V mean, "
                 f"{vb.max():.2f}→{vb.min():.2f} V (sag {vb.max()-vb.min():.2f} V over run). "
                 f"Actuator gain scales with voltage — note this when comparing K across runs.")
    L.append("")
    for r in results:
        m = r["model"]
        L.append(f"## {r['axis'].capitalize()} axis\n")
        bw = f"{r['bw_hz']:.3f} Hz" if r["bw_hz"] else "n/a"
        rmb = f"{r['ref_model_bw_radps']:.2f} rad/s" if r["ref_model_bw_radps"] else "n/a"
        L.append(f"- Closed-loop −3 dB bandwidth: **{bw}**  →  recommended `ref_model_bw` = **{rmb}**")
        if m["vaf"] == m["vaf"] and not np.isnan(m["vaf"]):
            if m.get("kind", "").startswith("pure integrator"):
                L.append("- Plant model  `G(s) = K / s · e^(−sT)`  (**pure integrator, relative "
                         "degree 1** — no identifiable lag pole in the excited band):")
                L.append(f"    - K (integrator gain) = {m['K']:.1f}")
                L.append(f"    - transport delay T = {m['delay_s']*1e3:.0f} ms")
            else:
                L.append("- Plant model  `G(s) = K / (s·(1 + s/p))·e^(−sT)`:")
                L.append(f"    - K (integrator gain) = {m['K']:.1f}")
                L.append(f"    - lag pole p = {m['pole_radps']:.1f} rad/s "
                         f"({m['pole_radps']/(2.0*np.pi):.2f} Hz)")
                L.append(f"    - transport delay T = {m['delay_s']*1e3:.0f} ms")
            L.append(f"    - fit quality **VAF = {m['vaf']:.1f}%** over {m['bins']} coherent bins")
        else:
            L.append(f"- Plant model: not enough coherent bins to fit ({m['bins']}).")
        L.append(f"- Samples used: {r['n']} (largest gap-free segment)")
        L.append(f"\n![{r['axis']} Bode](sysid_{r['axis']}.png)\n")
    (out_dir / "report.md").write_text("\n".join(L), encoding="utf-8")
    return out_dir / "report.md"


def main():
    ap = argparse.ArgumentParser(description="Offline MRAC system-ID analysis (ADR-0004 Phase 4).")
    ap.add_argument("log", help="captured ID-frame CSV (flat t_s,frame,key,value)")
    ap.add_argument("--axis", choices=AXES, help="analyse only this axis (default: all excited)")
    ap.add_argument("--coherence-thresh", type=float, default=0.6,
                    help="coherence quality gate (default 0.6)")
    ap.add_argument("--fs", type=float, default=0.0,
                    help="ID-frame sample rate in Hz. Default 0 = AUTO-detect from the firmware "
                         "sample_counter vs host time. Send_Task does NOT hold a fixed nominal "
                         "rate (measured ~230-267 Hz on single-axis v6 logs), so assuming a "
                         "constant value mis-scales every frequency. Pass a value to override.")
    ap.add_argument("--include-uad", action="store_true",
                    help="add u_ad to the plant input (use ONLY for runs with output "
                         "injection ON; default off = u_nom, the shadow-mode plant input)")
    ap.add_argument("--fit-fmin", type=float, default=0.0,
                    help="lower freq (Hz) for the J/b fit band (default 0)")
    ap.add_argument("--fit-fmax", type=float, default=10.0,
                    help="upper freq (Hz) for the J/b fit band — keep <= where the FRF "
                         "phase passes ~-135 deg, else extra lag drives J negative (default 10)")
    ap.add_argument("--out", default=None,
                    help="output dir (default: <logs>/../analysis/<logname>/ — a dedicated "
                         "per-log folder with the Bode plot(s) + report.md)")
    args = ap.parse_args()

    log_path = Path(args.log)
    if not log_path.exists():
        sys.exit(f"[sysid] log not found: {log_path}")

    data = load_flight_data(log_path)
    if not data or COUNTER_KEY not in data:
        sys.exit("[sysid] no ID-frame data (missing id.sample_counter) — was the 0x03 frame enabled?")

    # Sample rate: AUTO from the firmware counter vs host time unless overridden. The counter
    # is firmware-monotonic (one ++ per emitted frame), so span/host_duration is the true mean
    # emission rate, robust to the Send_Task not holding a fixed nominal rate.
    fs = args.fs
    fs_note = ""
    if fs <= 0.0:
        t_ctr, v_ctr = data[COUNTER_KEY]
        t_ctr = np.asarray(t_ctr, float); v_ctr = np.asarray(v_ctr, float)
        span = float(v_ctr[-1] - v_ctr[0]); dur = float(t_ctr[-1] - t_ctr[0])
        if span <= 0 or dur <= 0:
            # Counter reset / wrap (e.g. two SysID runs captured in one log): the end-to-end
            # span is meaningless. Use the largest monotonically-increasing segment instead.
            diffs = np.diff(v_ctr)
            resets = np.where(diffs < 0)[0]
            bnds = np.concatenate(([0], resets + 1, [len(v_ctr)]))
            bi = max(range(len(bnds) - 1), key=lambda i: bnds[i + 1] - bnds[i])
            lo, hi = int(bnds[bi]), int(bnds[bi + 1] - 1)
            span = float(v_ctr[hi] - v_ctr[lo]); dur = float(t_ctr[hi] - t_ctr[lo])
            fs_note = (f"counter reset detected (two runs in one log?) - fs from largest "
                       f"segment [{lo}:{hi}]")
            print(f"[sysid] WARNING: {fs_note}")
        fs = span / dur if (span > 0 and dur > 0) else DEFAULT_FS
        print(f"[sysid] auto fs = {fs:.1f} Hz (counter span {span:.0f} / {dur:.1f} s host)")

    # Link quality: surface telemetry frame drops BEFORE trusting any number. A WARN/BAD
    # verdict means the wireless link dropped frames (fly the drone closer to the receiver).
    lq = _link_quality(data)
    if lq is not None:
        msg = (f"link quality: {lq['verdict']}  "
               f"({lq['recv_frac']*100:.0f}% frames received, {lq['gaps']} gaps, "
               f"largest clean segment {lq['largest_seg']} samples)")
        if lq["verdict"] == "GOOD":
            print(f"[sysid] {msg}")
        else:
            print("[sysid] " + "!" * 60)
            print(f"[sysid] WARNING - {msg}")
            print("[sysid] Frames were dropped -> results may be UNRELIABLE. Fly the drone "
                  "closer to the wireless receiver and re-run.")
            print("[sysid] " + "!" * 60)

    # Output organization: a dedicated per-log folder under <logs>/../analysis/ (so analysis
    # artifacts live next to, not inside, the raw logs/ tree). Each folder holds the Bode
    # plot(s) and a report.md with the fitted parameters for easy later reference.
    if args.out:
        out_dir = Path(args.out)
    else:
        base = log_path.parent
        analysis_root = (base.parent / "analysis") if base.name.lower() == "logs" \
            else (base / "analysis")
        out_dir = analysis_root / log_path.stem
    out_dir.mkdir(parents=True, exist_ok=True)

    kind, peak, crest = _excitation_kind(data)

    axes = [args.axis] if args.axis else list(AXES)
    results = []
    for ax in axes:
        res = analyse_axis(data, ax, fs, args.coherence_thresh, args.include_uad,
                           args.fit_fmin, args.fit_fmax)
        if res is None:
            print(f"[sysid] {ax}: skipped (absent or < {MIN_SAMPLES} samples)")
            continue
        plot_path = plot_axis(res, out_dir, args.coherence_thresh)
        print(f"[sysid] {ax}: plot -> {plot_path.name}")
        results.append(res)

    if not results:
        sys.exit("[sysid] no axis had usable data.")
    print_summary(results)
    vbat_tup = data.get("id.vbat")
    vbat = np.asarray(vbat_tup[1], float) if vbat_tup else None
    report_path = write_report(results, out_dir, log_path, fs, fs_note, kind, peak, crest, vbat, lq)
    print(f"\n[sysid] analysis saved in {out_dir}")
    print(f"[sysid] report -> {report_path}")


if __name__ == "__main__":
    main()
