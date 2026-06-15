import sys
import json
from pathlib import Path
import numpy as np
from scipy import signal
import matplotlib.pyplot as plt

# Attempt to import load_flight_data from sibling module
try:
    from .analyze_flight_log import load_flight_data
except ImportError:
    # If running directly, adjust sys.path
    root_dir = Path(__file__).resolve().parent
    if str(root_dir) not in sys.path:
        sys.path.insert(0, str(root_dir))
    try:
        from analyze_flight_log import load_flight_data
    except ImportError:
        def load_flight_data(filepath):
            sys.exit("Error: Could not import load_flight_data from analyze_flight_log")

# physical constants for PAYLOAD_LIGHT
MIXER_PR = 1170.0
MIXER_YAW = 1872.0
MIXER_Z = 222.0
MRAC_DT = 0.005
MAX_NUM_BASIS = 6

WLIM = {
    "pitch": [0.50, 0.60, 0.40, 0.10, 0.40, 0.20],
    "roll":  [0.50, 0.60, 0.40, 0.10, 0.40, 0.20],
    "yaw":   [0.30, 0.40, 0.20, 0.05, 0.30, 0.20],
    "z":     [0.50, 0.60, 0.40, 0.10, 0.40, 0.20],
}

def get_data_array(data, axis, key):
    """Fallback lookup helper for flat and underscore names."""
    name1 = f"mrac.{axis}.{key}"
    name2 = f"mrac_{axis}_{key}"
    if name1 in data: return data[name1]
    if name2 in data: return data[name2]
    return None

def get_pid_array(data, loop, key):
    name1 = f"pid.{loop}.{key}"
    name2 = f"pid_{loop}_{key}"
    if name1 in data: return data[name1]
    if name2 in data: return data[name2]
    return None

def compute_authority(data, axis, mixer_scale) -> dict:
    """Quantify how much control effort comes from MRAC vs PID."""
    u_ad_tuple = get_data_array(data, axis, "u_ad")
    u_nom_tuple = get_data_array(data, axis, "u_nom")
    
    if not u_ad_tuple or not u_nom_tuple:
        return None
        
    t_ad, u_ad = u_ad_tuple
    t_nom, u_nom = u_nom_tuple
    
    u_ad_n = np.array(u_ad)
    u_nom_n = np.array(u_nom)
    t_ad_n = np.array(t_ad)
    t_nom_n = np.array(t_nom)
    
    if len(t_ad_n) == 0 or len(t_nom_n) == 0:
        return None
        
    u_ad_mixer = u_ad_n * mixer_scale
    u_nom_interp = np.interp(t_ad_n, t_nom_n, u_nom_n)

    # Authority share: fraction of the per-axis command coming from the adaptive
    # term. Both u_ad and u_nom are raw MRAC outputs (same units) -- do NOT mixer-
    # scale one side, or rho stops being a [0,1] ratio. (u_ad_mixer is kept only
    # for the physical-effort RMS fields below.)
    rho_instant = np.abs(u_ad_n) / (np.abs(u_ad_n) + np.abs(u_nom_interp) + 1e-6)

    return {
        "rho_mean": float(np.mean(rho_instant)),
        "rho_median": float(np.median(rho_instant)),
        "rho_peak": float(np.max(rho_instant)),
        "rho_p95": float(np.percentile(rho_instant, 95)),
        "u_ad_rms_mixer": float(np.sqrt(np.mean(u_ad_mixer**2))),
        "u_nom_rms": float(np.sqrt(np.mean(u_nom_n**2))),
        "u_ad_peak_mixer": float(np.max(np.abs(u_ad_mixer))),
        "u_nom_peak": float(np.max(np.abs(u_nom_n))),
        "_rho_instant": rho_instant.tolist(),
        "_t_ad": t_ad_n.tolist()
    }

def compute_tracking_metrics(data, loop_name) -> dict:
    """Evaluate how well the controller tracks the reference."""
    des_tuple = get_pid_array(data, loop_name, "Des")
    fb_tuple = get_pid_array(data, loop_name, "FB")
    
    if not des_tuple or not fb_tuple:
        return None
        
    t_des, des = des_tuple
    t_fb, fb = fb_tuple
    
    des_n = np.array(des)
    fb_interp = np.interp(t_des, t_fb, fb)
    err = des_n - fb_interp
    
    rmse = np.sqrt(np.mean(err**2))
    mae = np.mean(np.abs(err))
    peak_error = np.max(np.abs(err))
    
    # 2s sliding window, 0.5s step
    t_n = np.array(t_des)
    if len(t_n) < 2: return None
    
    t_start = t_n[0]
    t_end = t_n[-1]
    
    window_centers = []
    window_rmse = []
    window_is_steady = []
    
    for center in np.arange(t_start + 1.0, t_end - 1.0, 0.5):
        mask = (t_n >= center - 1.0) & (t_n <= center + 1.0)
        w_des = des_n[mask]
        w_err = err[mask]
        if len(w_err) > 0:
            w_rmse = np.sqrt(np.mean(w_err**2))
            w_steady = bool(np.std(w_des) < 0.5)
            window_centers.append(float(center))
            window_rmse.append(float(w_rmse))
            window_is_steady.append(w_steady)
            
    rmse_steady_list = [r for r, s in zip(window_rmse, window_is_steady) if s]
    rmse_transient_list = [r for r, s in zip(window_rmse, window_is_steady) if not s]
    
    return {
        "rmse": float(rmse),
        "mae": float(mae),
        "peak_error": float(peak_error),
        "rmse_steady": float(np.mean(rmse_steady_list)) if rmse_steady_list else None,
        "rmse_transient": float(np.mean(rmse_transient_list)) if rmse_transient_list else None,
        "num_samples": len(t_n),
        "duration_s": float(t_end - t_start),
        "windowed": {
            "t_center": window_centers,
            "rmse": window_rmse,
            "is_steady": window_is_steady
        }
    }

def analyze_weights(data, axis, num_basis, wlim) -> dict:
    """Diagnose adaptive weight health."""
    per_weight = []
    t_master = None
    all_w_n = []
    
    for i in range(num_basis):
        th_tuple = get_data_array(data, axis, f"theta_{i}")
        if not th_tuple:
            continue
        t, v = th_tuple
        if len(t) == 0: continue
        t_n = np.array(t)
        v_n = np.array(v)
        
        if t_master is None: t_master = t_n
        v_interp = np.interp(t_master, t_n, v_n)
        all_w_n.append(v_interp)
        
        final = v_n[-1]
        drift = np.polyfit(t_n, v_n, 1)[0] if len(t_n) > 1 else 0.0
        
        limit = wlim[i] if i < len(wlim) else 1.0
        proj_hits = np.sum(np.abs(v_n) > 0.95 * limit)
        frac = proj_hits / len(v_n)
        
        dv_dt = np.diff(v_n) / np.diff(t_n)
        crossings = np.sum(np.diff(np.sign(dv_dt)) != 0)
        dur = t_n[-1] - t_n[0]
        xc_rate = crossings / dur if dur > 0 else 0.0
        
        per_weight.append({
            "index": i,
            "theta_final": float(final),
            "drift_rate": float(drift),
            "projection_hits_frac": float(frac),
            "zero_crossings_per_sec": float(xc_rate)
        })
    
    if not per_weight: return None
    
    e_tuple = get_data_array(data, axis, "e")
    frozen_frac = 0.0
    if e_tuple:
        t_e, v_e = e_tuple
        if len(t_e) > 0:
            frozen_frac = np.sum(np.abs(np.array(v_e)) > 8.0) / len(v_e)
            
    w_mat = np.array(all_w_n)
    norms = np.linalg.norm(w_mat, axis=0) if w_mat.size > 0 else np.zeros(1)
    norm_final = float(norms[-1])
    
    slope = np.polyfit(t_master, norms, 1)[0] if len(t_master) > 1 else 0.0
    growing = bool(slope > 0.01)
    
    return {
        "num_basis": num_basis,
        "per_weight": per_weight,
        "frozen_frac": float(frozen_frac),
        "weight_norm_final": norm_final,
        "weight_norm_increasing": growing
    }

def compute_spectral_summary(data, axis) -> dict:
    """Frequency content of the adaptive signal."""
    u_ad_tuple = get_data_array(data, axis, "u_ad")
    if not u_ad_tuple: return None
    t, v = u_ad_tuple
    if len(v) < 256: return None
    v = np.asarray(v, float)
    f, Pxx = signal.welch(v, fs=100, nperseg=256)
    if len(Pxx) == 0: return None
    
    # Exclude DC
    max_idx = np.argmax(Pxx[1:]) + 1
    dom_freq = f[max_idx]
    
    # -3dB BW
    p_max = Pxx[max_idx]
    half_power = p_max / 2.0
    bw_idx = np.where(Pxx[max_idx:] < half_power)[0]
    bw = f[max_idx + bw_idx[0]] if len(bw_idx) > 0 else f[-1]
    
    dc_pwr = np.sum(Pxx[f <= 1.0])
    total_pwr = np.sum(Pxx)
    dc_frac = dc_pwr / total_pwr if total_pwr > 0 else 0.0
    
    return {
        "dominant_freq_hz": float(dom_freq),
        "bandwidth_3db_hz": float(bw),
        "psd_dc_fraction": float(dc_frac)
    }

def compute_phase_coherence(data, axis, mixer_scale) -> dict:
    """Determine if MRAC and PID are cooperating or fighting."""
    u_ad_tuple = get_data_array(data, axis, "u_ad")
    u_nom_tuple = get_data_array(data, axis, "u_nom")
    
    if not u_ad_tuple or not u_nom_tuple:
        return None
        
    t_ad, u_ad = u_ad_tuple
    t_nom, u_nom = u_nom_tuple
    
    u_ad_n = np.array(u_ad) * mixer_scale
    u_nom_n = np.array(u_nom)
    t_ad_n = np.array(t_ad)
    t_nom_n = np.array(t_nom)
    
    if len(t_ad_n) == 0 or len(t_nom_n) == 0:
        return None
        
    u_nom_interp = np.interp(t_ad_n, t_nom_n, u_nom_n)
    
    st_u = np.std(u_ad_n)
    st_n = np.std(u_nom_interp)
    if st_u < 1e-6 or st_n < 1e-6:
        xcorr = 0.0
    else:
        xcorr = np.corrcoef(u_ad_n, u_nom_interp)[0, 1]
    
    rel = "decoupled"
    if xcorr > 0.3: rel = "reinforcing"
    elif xcorr < -0.3: rel = "adversarial"
    
    return {
        "xcorr_lag0": float(xcorr),
        "relationship": rel
    }

def generate_alerts(authority, tracking, weights, spectral, phase, axis) -> list:
    """Heuristic alerts for human and AI consumption."""
    alerts = []
    
    # Authority
    if authority:
        rm = authority["rho_mean"]
        rp = authority["rho_p95"]
        if rm < 0.15:
            alerts.append({"level": "WARN", "code": "LOW_AUTHORITY", "message": f"{axis}: MRAC nearly inactive (ρ={rm:.2f}). Check if gamma is too low or deadzone too wide."})
        if rm > 0.6:
            alerts.append({"level": "WARN", "code": "HIGH_AUTHORITY", "message": f"{axis}: MRAC-dominant (ρ={rm:.2f}). PID gains may be insufficient."})
        if rp > 0.9:
            alerts.append({"level": "CRITICAL", "code": "NEAR_SATURATION", "message": f"{axis}: MRAC near saturation (ρ_p95={rp:.2f}). Reduce gamma or increase u_max."})
            
    # Tracking
    if tracking:
        rmse = tracking["rmse"]
        thr = 0.1 if axis == "z" else 3.0
        if rmse > thr:
            alerts.append({"level": "WARN", "code": "POOR_TRACKING", "message": f"{axis}: Tracking degraded (RMSE={rmse:.2f})."})
        rs = tracking["rmse_steady"]
        rt = tracking["rmse_transient"]
        if rs is not None and rt is not None and rs > 1e-3 and rt > 3 * rs:
            alerts.append({"level": "INFO", "code": "TRANSIENT_PENALTY", "message": f"{axis}: Transient RMSE {rt/rs:.1f}× worse than steady-state."})
            
    # Weights
    if weights and weights.get("per_weight"):
        for w in weights["per_weight"]:
            if w["projection_hits_frac"] > 0.05:
                alerts.append({"level": "WARN", "code": "PROJECTION_ACTIVE", "message": f"{axis}: Weight[{w['index']}] hitting projection bound {w['projection_hits_frac']:.0%} of time. Disturbance may exceed budget."})
            if abs(w["drift_rate"]) > 0.01:
                alerts.append({"level": "WARN", "code": "WEIGHT_DRIFT", "message": f"{axis}: Weight[{w['index']}] drifting at {w['drift_rate']:.4f}/s. σ-mod may be too weak."})
        if weights["weight_norm_increasing"]:
            alerts.append({"level": "CRITICAL", "code": "DIVERGING_WEIGHTS", "message": f"{axis}: Weight norm is growing — adaptation may be diverging."})
        if weights["frozen_frac"] > 0.1:
            alerts.append({"level": "WARN", "code": "FREQUENT_FREEZE", "message": f"{axis}: Hard-freeze active {weights['frozen_frac']:.0%} of flight. Check e_freeze threshold."})

    # Spectral
    if spectral:
        df = spectral["dominant_freq_hz"]
        dc = spectral["psd_dc_fraction"]
        if df > 20:
             alerts.append({"level": "WARN", "code": "HIGH_FREQ_CHATTER", "message": f"{axis}: u_ad dominant frequency is {df:.1f} Hz. Increase ω_u (L1 filter) or reduce gamma."})
        if dc > 0.8:
             alerts.append({"level": "INFO", "code": "QUASI_STATIC", "message": f"{axis}: MRAC output is >80% DC — acting as slow integrator. May be fine for bias rejection."})

    # Phase
    if phase and phase["relationship"]:
        rel = phase["relationship"]
        xc = phase["xcorr_lag0"]
        if rel == "adversarial":
            alerts.append({"level": "CRITICAL", "code": "PID_MRAC_FIGHT", "message": f"{axis}: MRAC and PID are anti-correlated (r={xc:.2f}). Check reference model sign convention."})
        elif rel == "reinforcing" and authority and authority["rho_mean"] > 0.3:
            alerts.append({"level": "WARN", "code": "REDUNDANT_EFFORT", "message": f"{axis}: MRAC reinforcing PID (r={xc:.2f}) with significant authority. PID may need retuning."})

    return alerts

# ---------------------------------------------------------------------------
# Path-tracking geometry  (position loops -- the actual preset-path performance)
# ---------------------------------------------------------------------------

def reconstruct_ideal_curve(mode, params, n=3000):
    """Closed-form ideal XY curve in cm (loc-PID units), or None if not planar.
    Mirrors the firmware parametric formulas in TASK/AutoflyTask.c. Centre/radius/
    amplitude params arrive in metres (GUI) and are scaled x100 to cm."""
    cx = float(params.get("cx", 0.0)) * 100.0
    cy = float(params.get("cy", 0.0)) * 100.0
    th = np.linspace(0.0, 2.0 * np.pi, n)
    if mode == "circle":
        R = float(params.get("radius_m", 0.0)) * 100.0
        if R <= 0:
            return None
        return cx + R * np.cos(th), cy + R * np.sin(th)
    if mode == "figure8":
        A = float(params.get("amplitude_m", 0.0)) * 100.0
        if A <= 0:
            return None
        shape = str(params.get("shape", "bernoulli")).lower()
        if shape.startswith("ger"):  # Gerono: vertical 8
            return cx + 0.5 * A * np.sin(2.0 * th), cy + A * np.sin(th)
        s = np.sin(th); c = np.cos(th); denom = 1.0 + s * s  # Bernoulli lemniscate
        return cx + A * c / denom, cy + A * s * c / denom
    return None


def _min_dist_to_curve(fx, fy, ix, iy):
    """Per-point minimum distance from flown (fx,fy) to ideal point set (ix,iy)."""
    d = np.empty(len(fx))
    for i in range(len(fx)):
        dx = ix - fx[i]; dy = iy - fy[i]
        d[i] = np.sqrt(np.min(dx * dx + dy * dy))
    return d


def _xcorr_lag_ms(t, des, fb, max_lag_s=2.0):
    """Positive along-track/phase lag (ms): how far FB trails the reference."""
    des = np.asarray(des, float); fb = np.asarray(fb, float)
    des = des - des.mean(); fb = fb - fb.mean()
    if des.std() < 1e-6 or fb.std() < 1e-6:
        return None
    dt = float(np.median(np.diff(t))) if len(t) > 1 else 0.005
    if dt <= 0:
        return None
    max_k = int(max_lag_s / dt)
    n = len(des)
    best_k, best_c = 0, -1e9
    for k in range(0, max_k + 1):
        if k >= n - 10:
            break
        a = des[:n - k]; b = fb[k:]
        denom = np.linalg.norm(a) * np.linalg.norm(b) + 1e-9
        c = float(np.dot(a, b) / denom)
        if c > best_c:
            best_c, best_k = c, k
    return best_k * dt * 1000.0


def compute_settling(data, params):
    """TWC point-to-point settling against the commanded target."""
    fxb = get_pid_array(data, "locx", "FB")
    fyb = get_pid_array(data, "locy", "FB")
    if not fxb or not fyb:
        return None
    tx = float(params.get("target_x_m", 0.0)) * 100.0
    ty = float(params.get("target_y_m", 0.0)) * 100.0
    t = np.asarray(fxb[0]); x = np.asarray(fxb[1]); y = np.interp(t, fyb[0], fyb[1])
    dist = np.sqrt((x - tx) ** 2 + (y - ty) ** 2)
    if len(dist) == 0:
        return None
    tail = max(1, len(dist) // 20)
    band = 5.0  # cm settling band
    settled = np.where(dist <= band)[0]
    return {
        "initial_err_cm": float(dist[0]),
        "final_err_cm": float(np.mean(dist[-tail:])),
        "peak_err_cm": float(np.max(dist)),
        "settling_band_cm": band,
        "settling_time_s": float(t[settled[0]] - t[0]) if len(settled) else None,
    }


def _decompose_axis(t, des, fb):
    """Split a single-axis tracking error into DC-bias / amplitude-gain /
    phase-lag / residual contributions (all cm RMS, additive in spirit).

    Model: fb(t) ~= gain * des(t - lag) + bias.  The three named contributions
    are the standalone RMS each defect alone would inject, so a fat RMSE can be
    read as "mostly lag" vs "mostly drift" vs "mostly gain loss". `residual` is
    the part no constant offset/gain/lag explains (noise, distortion, nonlin)."""
    des = np.asarray(des, float); fb = np.asarray(fb, float)
    n = len(des)
    std_d = float(np.std(des))
    total_rmse = float(np.sqrt(np.mean((fb - des) ** 2)))
    if np.ptp(des) < 1.0:  # reference essentially constant (cm) -> hold, not a path
        return {"reference": "static", "bias_cm": float(np.mean(fb - des)),
                "total_rmse_cm": total_rmse}
    lag_ms = _xcorr_lag_ms(t, des, fb)
    dt = float(np.median(np.diff(t))) if n > 1 else 0.005
    k = int(round((lag_ms / 1000.0) / dt)) if lag_ms else 0
    if 0 < k < n - 10:
        d_lag = des[:n - k]; f_al = fb[k:]; d_now = des[k:]
        err_phase = float(np.sqrt(np.mean((d_now - d_lag) ** 2)))
    else:
        k = 0; d_lag = des; f_al = fb; err_phase = 0.0
    A = np.vstack([d_lag, np.ones_like(d_lag)]).T
    (gain, bias), *_ = np.linalg.lstsq(A, f_al, rcond=None)
    gain = float(gain); bias = float(bias)
    resid = f_al - (gain * d_lag + bias)
    return {
        "reference": "dynamic",
        "bias_cm": bias,
        "gain": gain,
        "lag_ms": lag_ms,
        "total_rmse_cm": total_rmse,
        "err_bias_cm": abs(bias),
        "err_amplitude_cm": abs(gain - 1.0) * std_d,
        "err_phase_cm": err_phase,
        "residual_rmse_cm": float(np.sqrt(np.mean(resid ** 2))),
    }


def compute_tracking_decomposition(data):
    """Per planar axis, decompose tracking error into bias/gain/lag/residual."""
    out = {}
    for loop, name in (("locx", "x"), ("locy", "y")):
        des = get_pid_array(data, loop, "Des"); fb = get_pid_array(data, loop, "FB")
        if not des or not fb:
            continue
        t = np.asarray(des[0]); d = np.asarray(des[1])
        f = np.interp(t, fb[0], fb[1])
        if len(t) < 10:
            continue
        out[name] = _decompose_axis(t, d, f)
    return out or None


def compute_yaw_hold_drift(data):
    """Heading-hold drift: how far yaw FB wanders from its commanded angle.
    Yaw is gyro-integrated (no absolute reference), so a steady offset + slow
    drift is the expected signature of bias/asymmetry -- this quantifies it."""
    des = get_pid_array(data, "yaw", "Des"); fb = get_pid_array(data, "yaw", "FB")
    if not des or not fb:
        return None
    t = np.asarray(des[0]); d = np.asarray(des[1])
    f = np.interp(t, fb[0], fb[1])
    if len(t) < 10:
        return None
    e = f - d  # heading error (deg)
    dur = float(t[-1] - t[0])
    slope = float(np.polyfit(t, e, 1)[0]) if dur > 0 else 0.0  # deg/s
    tail = max(1, len(e) // 10)
    return {
        "cmd_deg": float(np.median(d)),
        "mean_offset_deg": float(np.mean(e)),
        "final_offset_deg": float(np.mean(e[-tail:])),
        "drift_rate_deg_s": slope,
        "total_drift_deg": slope * dur,
        "peak_to_peak_deg": float(np.ptp(e)),
    }


def compute_path_geometry(data, mode, params):
    """Position-loop tracking + cross-track / along-track geometry. The headline
    path-performance block; also produces the champion ranking scalar."""
    out = {"mode": mode}

    pos = {}
    for loop, name in (("locx", "x"), ("locy", "y"), ("z_pos", "z")):
        m = compute_tracking_metrics(data, loop)
        if m:
            pos[name] = {k: m[k] for k in
                         ("rmse", "mae", "peak_error", "rmse_steady", "rmse_transient")}
    out["position_tracking"] = pos

    dx = get_pid_array(data, "locx", "Des"); fxb = get_pid_array(data, "locx", "FB")
    dy = get_pid_array(data, "locy", "Des"); fyb = get_pid_array(data, "locy", "FB")
    fx = fy = None
    if dx and fxb and dy and fyb:
        t = np.asarray(dx[0]); desx = np.asarray(dx[1])
        desy = np.interp(t, dy[0], dy[1])
        fx = np.interp(t, fxb[0], fxb[1]); fy = np.interp(t, fyb[0], fyb[1])
        emag = np.sqrt((desx - fx) ** 2 + (desy - fy) ** 2)
        out["planar_rmse_cm"] = float(np.sqrt(np.mean(emag ** 2)))
        out["planar_peak_cm"] = float(np.max(emag))
        rngx, rngy = float(np.ptp(desx)), float(np.ptp(desy))
        if max(rngx, rngy) > 1e-3:
            if rngx >= rngy:
                out["alongtrack_lag_ms"] = _xcorr_lag_ms(t, desx, fx)
            else:
                out["alongtrack_lag_ms"] = _xcorr_lag_ms(t, desy, fy)

    ideal = reconstruct_ideal_curve(mode, params)
    if ideal is not None and fx is not None:
        ix, iy = ideal
        d = _min_dist_to_curve(fx, fy, ix, iy)
        out["crosstrack_mean_cm"] = float(np.mean(d))
        out["crosstrack_p95_cm"] = float(np.percentile(d, 95))
        out["crosstrack_max_cm"] = float(np.max(d))

    out["tracking_decomp"] = compute_tracking_decomposition(data)
    out["yaw_drift"] = compute_yaw_hold_drift(data)

    if mode == "twc":
        out["settling"] = compute_settling(data, params)
        out["settling_s"] = (out["settling"] or {}).get("settling_time_s")

    # ranking scalar (lower = better). Per ADR-0002 rank by position-tracking
    # RMSE. For TWC the planar XY error is the point-to-point accuracy that
    # matters; settling time is reported separately (and is None when the run
    # never settled, so it must NOT be the rank scalar -- that would reward a
    # failed flight by falling through to the ~1cm altitude RMSE).
    rank, metric = None, None
    if mode == "twc":
        if out.get("planar_rmse_cm") is not None:
            rank, metric = out["planar_rmse_cm"], "planar_rmse_cm"
        elif pos.get("z"):
            rank, metric = pos["z"]["rmse"], "z_rmse"
    elif mode == "sinusoid" and str(params.get("axis")) == "2":
        if pos.get("z"):
            rank, metric = pos["z"]["rmse"], "z_rmse"
    else:
        if out.get("planar_rmse_cm") is not None:
            rank, metric = out["planar_rmse_cm"], "planar_rmse_cm"
        elif pos.get("z"):
            rank, metric = pos["z"]["rmse"], "z_rmse"
    out["rank_score"] = rank
    out["rank_metric"] = metric
    return out


def compute_context(data):
    """Flight-context: battery sag, status-signal events, data health."""
    out = {}
    spans = [(t[0], t[-1], len(t)) for t, _ in data.values() if t]
    if spans:
        out["duration_s"] = float(max(b for _, b, _ in spans) - min(a for a, _, _ in spans))
    if data:
        dense = max(data.items(), key=lambda kv: len(kv[1][0]))
        t = np.asarray(dense[1][0])
        if len(t) > 2:
            gaps = np.diff(t)
            out["samples"] = int(len(t))
            out["median_dt_s"] = float(np.median(gaps))
            out["max_gap_s"] = float(np.max(gaps))

    vb = data.get("status.vbat") or data.get("status_vbat")
    if vb and len(vb[1]) > 1:
        v = np.asarray(vb[1], float)
        out["vbat_start"] = float(v[0]); out["vbat_end"] = float(v[-1])
        out["vbat_drop"] = float(v[0] - v[-1])

    events = []
    for key in ("status.sbus_lost", "status.flymode", "status.arm", "status.rc_authority"):
        sig = data.get(key)
        if not sig:
            continue
        t, v = sig
        for i in range(1, len(v)):
            if v[i] != v[i - 1]:
                events.append({"t": float(t[i]), "signal": key.split(".")[-1],
                               "from": v[i - 1], "to": v[i]})
    events.sort(key=lambda e: e["t"])
    out["events"] = events[:50]
    return out


def build_verdict(json_record):
    """Rule-based 'What Happened' narrative -- the pipeline's primary purpose."""
    geom = json_record.get("path_geometry", {}) or {}
    ctx = json_record.get("context", {}) or {}
    sb = json_record.get("scoreboard", {}) or {}
    mode = geom.get("mode", json_record.get("mode", "?"))
    lines = []

    pr = geom.get("planar_rmse_cm")
    if pr is not None:
        lines.append(f"Planar XY tracking RMSE was **{pr:.1f} cm** (peak {geom.get('planar_peak_cm', 0):.1f} cm).")
    pos = geom.get("position_tracking", {})
    if pos:
        worst = max(pos.items(), key=lambda kv: kv[1].get("rmse", 0) or 0)
        unit = "cm" if worst[0] in ("x", "y") else "m"
        lines.append(f"Worst-tracked position axis was **{worst[0].upper()}** (RMSE {worst[1]['rmse']:.2f} {unit}).")
    ct = geom.get("crosstrack_mean_cm")
    if ct is not None:
        lines.append(f"Held within **{ct:.1f} cm mean / {geom.get('crosstrack_max_cm', 0):.1f} cm max** of the ideal {mode} curve.")
    lag = geom.get("alongtrack_lag_ms")
    if lag is not None:
        lines.append(f"Feedback trailed the reference by ~**{lag:.0f} ms** (along-track/phase lag).")

    # dominant tracking-error cause (from the bias/gain/lag decomposition)
    decomp = geom.get("tracking_decomp") or {}
    dyn = {ax: d for ax, d in decomp.items() if d.get("reference") == "dynamic"}
    if dyn:
        worst_ax = max(dyn, key=lambda a: dyn[a].get("total_rmse_cm", 0) or 0)
        d = dyn[worst_ax]
        causes = {"DC offset/drift": d.get("err_bias_cm", 0) or 0,
                  "amplitude loss": d.get("err_amplitude_cm", 0) or 0,
                  "phase lag": d.get("err_phase_cm", 0) or 0,
                  "residual": d.get("residual_rmse_cm", 0) or 0}
        top = max(causes, key=causes.get)
        lines.append(
            f"**{worst_ax.upper()}** tracking error is dominated by **{top}** "
            f"(bias {d.get('err_bias_cm',0):.0f} / amp {d.get('err_amplitude_cm',0):.0f} / "
            f"lag {d.get('err_phase_cm',0):.0f} / resid {d.get('residual_rmse_cm',0):.0f} cm RMS; "
            f"gain {d.get('gain',0):.2f}).")
    yd = geom.get("yaw_drift")
    if yd is not None and (abs(yd.get("total_drift_deg", 0)) > 2 or abs(yd.get("final_offset_deg", 0)) > 2):
        lines.append(
            f"Yaw held **{yd.get('final_offset_deg',0):+.1f}°** off command "
            f"(drift {yd.get('drift_rate_deg_s',0):+.2f}°/s over the run) — "
            f"expected heading-hold signature of bias/asymmetry.")
    if mode == "twc" and geom.get("settling"):
        st = geom["settling"]; stt = st.get("settling_time_s")
        if stt is not None:
            lines.append(f"Reached the {st['settling_band_cm']:.0f} cm target band in **{stt:.1f} s**; final error {st['final_err_cm']:.1f} cm.")
        else:
            lines.append(f"**Never settled** within {st['settling_band_cm']:.0f} cm of target (final error {st['final_err_cm']:.1f} cm).")

    crit = sum(int(v.get("alerts_critical", 0) or 0) for v in sb.values())
    warn = sum(int(v.get("alerts_warn", 0) or 0) for v in sb.values())
    if crit:
        lines.append(f"⚠ **{crit} CRITICAL** MRAC alert(s) — run is INELIGIBLE as a champion until resolved.")
    elif warn:
        lines.append(f"{warn} warning-level MRAC alert(s); no critical issues.")
    else:
        lines.append("MRAC health clean: no warnings or critical alerts.")

    best_axis, best_rho = None, -1.0
    for ax, v in sb.items():
        rm = v.get("rho_mean")
        if rm is not None and rm > best_rho:
            best_rho, best_axis = rm, ax
    if best_axis is not None:
        lines.append(f"MRAC was most active on **{best_axis}** (ρ_mean {best_rho:.2f}).")

    if ctx.get("vbat_drop") is not None and ctx["vbat_drop"] > 0.3:
        lines.append(f"Battery sagged **{ctx['vbat_drop']:.2f} V** over the run — check for correlated drift.")
    sbus = [e for e in ctx.get("events", []) if e["signal"] == "sbus_lost" and e["to"]]
    if sbus:
        ts = ", ".join(f"{e['t']:.1f}s" for e in sbus[:3])
        lines.append(f"⚠ **SBUS-loss** event(s) at t={ts}.")
    if ctx.get("max_gap_s") and ctx.get("median_dt_s") and ctx["max_gap_s"] > 10 * ctx["median_dt_s"]:
        lines.append(f"Telemetry gap up to **{ctx['max_gap_s'] * 1000:.0f} ms** — some data may be missing.")
    return lines


def snapshot_firmware_params() -> dict:
    """Record immutable parameter snapshot for this experiment."""
    params = {
        "payload": "PAYLOAD_LIGHT",
        "mrac_dt": 0.005,
        "num_basis": 6,
        "mixer": {"pitch": 1170.0, "roll": 1170.0, "yaw": 1872.0, "z": 222.0},
        "gamma": {
            "pitch": [0.50, 3.30, 1.00, 2.00, 0.10, 1.00],
            "roll":  [0.50, 3.30, 1.00, 2.00, 0.10, 1.00],
            "yaw":   [0.30, 2.00, 0.70, 1.50, 0.10, 1.00],
        },
        "wlim": {
            "pitch": [0.50, 0.60, 0.40, 0.10, 0.40, 0.20],
            "roll":  [0.50, 0.60, 0.40, 0.10, 0.40, 0.20],
            "yaw":   [0.30, 0.40, 0.20, 0.05, 0.30, 0.20],
        },
        "sigma": {"pitch": "from_config", "roll": "from_config", "yaw": "from_config"},
        "features": {
            "projection": True,
            "sigma_mod": True,
            "deadzone": True,
            "l1_filter": True,
            "pch": True,
            "perf_recovery": True,
        },
    }
    # TODO: parse from telemetry config dump frame when available
    manifest_path = Path(__file__).resolve().parent.parent / "params_manifest.json"
    if manifest_path.exists():
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                user_params = json.load(f)
            params.update(user_params)
        except Exception as e:
            print(f"[deep_analysis] Error reading params_manifest.json: {e}")
    return params

def build_json_record(csv_path, all_axis_results, params_snapshot) -> dict:
    """The experiment record JSON consumed by the analyze-results AI skill."""
    from datetime import datetime
    import csv
    
    try:
        rows = sum(1 for line in open(csv_path, "r", encoding="utf-8", errors="replace")) - 1
    except:
        rows = 0
        
    dur = 0.0
    for res in all_axis_results.values():
        if res and res["tracking"]:
            dur = max(dur, res["tracking"]["duration_s"])
            
    record = {
        "experiment_id": f"exp_{csv_path.stem}",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "csv_file": csv_path.name,
        "rows_parsed": max(0, rows),
        "duration_s": dur,
        "firmware_params": params_snapshot,
        "scoreboard": {},
        "diagnostics": {}
    }
    
    for ax, res in all_axis_results.items():
        if not res: continue
        auth = res["authority"] or {}
        trk = res["tracking"] or {}
        wgt = res["weights"] or {}
        phz = res["phase"] or {}
        alrt = res["alerts"] or []
        
        crit = sum(1 for a in alrt if a["level"] == "CRITICAL")
        warn = sum(1 for a in alrt if a["level"] == "WARN")
        
        record["scoreboard"][ax] = {
            "rmse": trk.get("rmse"),
            "rmse_steady": trk.get("rmse_steady"),
            "rmse_transient": trk.get("rmse_transient"),
            "rho_mean": auth.get("rho_mean"),
            "rho_p95": auth.get("rho_p95"),
            "phase_relationship": phz.get("relationship"),
            "weight_norm_final": wgt.get("weight_norm_final"),
            "alerts_critical": crit,
            "alerts_warn": warn
        }
        
        # Clone without private/heavy fields
        diag_auth = {k:v for k,v in auth.items() if not k.startswith("_")} if auth else None
        diag_trk = {k:v for k,v in trk.items() if k != "windowed"} if trk else None
        
        record["diagnostics"][ax] = {
            "authority": diag_auth,
            "tracking": diag_trk,
            "weights": wgt,
            "spectral": res["spectral"],
            "phase": phz,
            "alerts": alrt
        }
        
    record["meta"] = {
        "analyzer_version": "1.0.0",
        "analysis_timestamp": datetime.utcnow().isoformat() + "Z"
    }
    return record

def _save_fig(fig, out_dir, name):
    try:
        path = out_dir / name
        fig.savefig(path, bbox_inches='tight')
        plt.close(fig)
    except Exception as e:
        print(f"[deep_analysis] Warning: could not save {name}: {e}")

def plot_windowed_rmse(track, axis, plot_dir):
    if not track or "windowed" not in track: return
    win = track["windowed"]
    try:
        fig, ax = plt.subplots(figsize=(8,4))
        is_st = np.array(win["is_steady"], dtype=bool)
        t_c = np.array(win["t_center"])
        r = np.array(win["rmse"])
        ax.plot(t_c, r, 'k-', linewidth=1, label="Windowed RMSE")
        if is_st.any():
            ax.plot(t_c[is_st], r[is_st], 'go', label="Steady")
        if (~is_st).any():
            ax.plot(t_c[~is_st], r[~is_st], 'ro', label="Transient")
        ax.set_title(f"{axis.capitalize()} Windowed RMSE")
        ax.set_ylabel("RMSE")
        ax.set_xlabel("Time (s)")
        ax.legend()
        _save_fig(fig, plot_dir, f"windowed_rmse_{axis}.png")
    except Exception as e:
        print(f"[deep_analysis] Failed windowed_rmse for {axis}: {e}")

def plot_weight_trajectories(data, axis, num_basis, wlim_arr, plot_dir):
    fig, ax = plt.subplots(figsize=(10,5))
    valid = False
    for i in range(num_basis):
        tup = get_data_array(data, axis, f"theta_{i}")
        if tup:
            valid = True
            t, v = tup
            labels = ["bias", "angle", "rate", "drag", "un", "v"]
            lbl = labels[i] if i < len(labels) else str(i)
            ax.plot(t, v, label=f"W[{i}] {lbl}")
            lim = wlim_arr[i] if i < len(wlim_arr) else 1.0
            ax.axhline(lim, color=plt.gca().lines[-1].get_color(), linestyle='--', alpha=0.5)
            ax.axhline(-lim, color=plt.gca().lines[-1].get_color(), linestyle='--', alpha=0.5)
    if valid:
        ax.set_title(f"{axis.capitalize()} Adaptive Weights")
        ax.set_ylabel("Weight Value")
        ax.set_xlabel("Time (s)")
        ax.legend(loc='center left', bbox_to_anchor=(1, 0.5))
        _save_fig(fig, plot_dir, f"weight_trajectory_{axis}.png")

def plot_spectral(data, axis, plot_dir):
    tup = get_data_array(data, axis, "u_ad")
    if not tup: return
    t, v = tup
    if len(v) < 256: return
    v = np.asarray(v, float)
    try:
        f, Pxx = signal.welch(v, fs=100, nperseg=256)
        fig, ax = plt.subplots(figsize=(8,4))
        ax.semilogy(f, Pxx)
        ax.set_title(f"{axis.capitalize()} u_ad PSD")
        ax.set_xlabel("Freq (Hz)")
        ax.set_ylabel("Power")
        _save_fig(fig, plot_dir, f"spectral_{axis}.png")
    except Exception as e:
        print(f"[deep_analysis] Failed spectral for {axis}: {e}")

def plot_authority_timeline(data, axis, mixer_scale, plot_dir):
    try:
        u_ad_tup = get_data_array(data, axis, "u_ad")
        u_nom_tup = get_data_array(data, axis, "u_nom")
        if not u_ad_tup or not u_nom_tup: return
        t_ad, u_ad = u_ad_tup
        t_nom, u_nom = u_nom_tup
        u_ad_n = np.array(u_ad)
        u_nom_n = np.array(u_nom)
        u_nom_interp = np.interp(t_ad, t_nom, u_nom_n)
        rho = np.abs(u_ad_n) / (np.abs(u_ad_n) + np.abs(u_nom_interp) + 1e-6)
        
        fig, ax = plt.subplots(figsize=(10,4))
        ax.plot(t_ad, rho, 'k', linewidth=0.5, alpha=0.5)
        window = min(len(rho), 50)
        if window > 0:
            rho_smooth = np.convolve(rho, np.ones(window)/window, mode='same')
            ax.plot(t_ad, rho_smooth, 'b-', linewidth=2)
        ax.axhspan(0.6, max(1.0, np.max(rho)), color='red', alpha=0.2)
        ax.axhspan(0, 0.15, color='blue', alpha=0.2)
        ax.set_title(f"{axis.capitalize()} Authority (ρ)")
        ax.set_ylabel("ρ")
        ax.set_xlabel("Time (s)")
        _save_fig(fig, plot_dir, f"authority_timeline_{axis}.png")
    except Exception as e:
        print(f"[deep_analysis] Failed authority timeline for {axis}: {e}")

def plot_xy_trajectory(data, mode, params, plot_dir):
    """Commanded (Des) vs flown (FB) XY path, overlaid with the ideal curve."""
    dx = get_pid_array(data, "locx", "Des"); fxb = get_pid_array(data, "locx", "FB")
    dy = get_pid_array(data, "locy", "Des"); fyb = get_pid_array(data, "locy", "FB")
    if not (fxb and fyb):
        return
    try:
        fig, ax = plt.subplots(figsize=(7, 7))
        if dx and dy:
            t = np.asarray(dx[0])
            ax.plot(dx[1], np.interp(t, dy[0], dy[1]), 'k--', lw=1.0, alpha=0.7, label="Commanded (Des)")
        tf = np.asarray(fxb[0])
        ax.plot(fxb[1], np.interp(tf, fyb[0], fyb[1]), 'royalblue', lw=1.2, label="Flown (FB)")
        ideal = reconstruct_ideal_curve(mode, params)
        if ideal is not None:
            ax.plot(ideal[0], ideal[1], 'g-', lw=1.0, alpha=0.5, label="Ideal curve")
        ax.set_title(f"XY Trajectory - {mode}")
        ax.set_xlabel("X (cm)"); ax.set_ylabel("Y (cm)")
        ax.axis("equal"); ax.grid(True, alpha=0.3); ax.legend()
        _save_fig(fig, plot_dir, "xy_trajectory.png")
    except Exception as e:
        print(f"[deep_analysis] Failed xy_trajectory: {e}")


def plot_position_tracking(data, plot_dir):
    """Des vs FB time series for the position loops (locx, locy, z_pos)."""
    for loop, name in (("locx", "X"), ("locy", "Y"), ("z_pos", "Z")):
        des = get_pid_array(data, loop, "Des"); fb = get_pid_array(data, loop, "FB")
        if not (des and fb):
            continue
        try:
            fig, ax = plt.subplots(figsize=(10, 4))
            ax.plot(des[0], des[1], 'k--', lw=1.2, label="Des")
            ax.plot(fb[0], fb[1], 'royalblue', lw=1.2, label="FB")
            unit = "m" if loop == "z_pos" else "cm"
            ax.set_title(f"{name} Position Tracking")
            ax.set_ylabel(f"{name} ({unit})"); ax.set_xlabel("Time (s)")
            ax.grid(True, alpha=0.3); ax.legend()
            _save_fig(fig, plot_dir, f"position_{loop}.png")
        except Exception as e:
            print(f"[deep_analysis] Failed position plot {loop}: {e}")


def plot_tracking_decomposition(decomp, plot_dir):
    """Stacked bars: per axis, how much of the RMSE each defect injects."""
    if not decomp:
        return
    dyn = {ax: d for ax, d in decomp.items() if d.get("reference") == "dynamic"}
    if not dyn:
        return
    try:
        axes = list(dyn.keys())
        comps = [("DC bias", "err_bias_cm", "#d62728"),
                 ("Amplitude", "err_amplitude_cm", "#ff7f0e"),
                 ("Phase lag", "err_phase_cm", "#1f77b4"),
                 ("Residual", "err_residual_cm", "#7f7f7f")]
        fig, ax = plt.subplots(figsize=(7, 4.5))
        x = np.arange(len(axes))
        bottom = np.zeros(len(axes))
        for label, key, color in comps:
            k = "residual_rmse_cm" if key == "err_residual_cm" else key
            vals = np.array([dyn[a].get(k, 0) or 0 for a in axes], float)
            ax.bar(x, vals, bottom=bottom, label=label, color=color)
            bottom += vals
        for i, a in enumerate(axes):
            ax.text(i, bottom[i], f"  RMSE {dyn[a].get('total_rmse_cm',0):.0f}",
                    ha="center", va="bottom", fontsize=9)
        ax.set_xticks(x); ax.set_xticklabels([a.upper() for a in axes])
        ax.set_ylabel("Error contribution (cm RMS)")
        ax.set_title("Tracking error decomposition (cause breakdown)")
        ax.legend(); ax.grid(True, axis="y", alpha=0.3)
        _save_fig(fig, plot_dir, "tracking_decomposition.png")
    except Exception as e:
        print(f"[deep_analysis] Failed tracking_decomposition: {e}")


def _verdict_and_path_md(json_record) -> list:
    """Top-of-report 'What Happened' verdict + path-performance scorecard."""
    geom = json_record.get("path_geometry", {}) or {}
    md = ["## What Happened", ""]
    for line in json_record.get("verdict", []) or ["(no verdict generated)"]:
        md.append(f"- {line}")
    md += ["", "## Path Tracking", "", "![XY Trajectory](xy_trajectory.png)", ""]

    def f(v, p=2):
        return f"{v:.{p}f}" if isinstance(v, (int, float)) else "-"

    md += [
        "| Metric | Value |",
        "|--------|-------|",
        f"| Planar XY RMSE (cm) | {f(geom.get('planar_rmse_cm'))} |",
        f"| Planar peak (cm) | {f(geom.get('planar_peak_cm'))} |",
        f"| Cross-track mean / p95 / max (cm) | {f(geom.get('crosstrack_mean_cm'))} / {f(geom.get('crosstrack_p95_cm'))} / {f(geom.get('crosstrack_max_cm'))} |",
        f"| Along-track lag (ms) | {f(geom.get('alongtrack_lag_ms'), 0)} |",
        f"| Rank score ({geom.get('rank_metric', '-')}) | {f(geom.get('rank_score'))} |",
    ]
    st = geom.get("settling")
    if st:
        md.append(f"| TWC settling time (s) | {f(st.get('settling_time_s'))} |")
        md.append(f"| TWC final error (cm) | {f(st.get('final_err_cm'))} |")
    pos = geom.get("position_tracking", {})
    if pos:
        md += ["", "| Axis | RMSE | MAE | Peak |", "|------|------|-----|------|"]
        for nm in ("x", "y", "z"):
            if nm in pos:
                p = pos[nm]
                md.append(f"| {nm.upper()} | {f(p.get('rmse'))} | {f(p.get('mae'))} | {f(p.get('peak_error'))} |")
        md += ["", "![X](position_locx.png)", "![Y](position_locy.png)", "![Z](position_z_pos.png)", ""]

    decomp = geom.get("tracking_decomp") or {}
    dyn = {ax: d for ax, d in decomp.items() if d.get("reference") == "dynamic"}
    if dyn:
        md += [
            "### Tracking error decomposition",
            "",
            "_Splits each axis RMSE into the cause that injects it: a steady DC "
            "offset, amplitude attenuation (gain≠1), phase lag, or residual "
            "distortion. Read the largest column as the thing to fix first._",
            "",
            "![Decomposition](tracking_decomposition.png)",
            "",
            "| Axis | Total RMSE | DC bias | Amplitude | Phase lag | Residual | Gain | Lag (ms) |",
            "|------|-----------|---------|-----------|-----------|----------|------|----------|",
        ]
        for ax in ("x", "y"):
            d = dyn.get(ax)
            if not d:
                continue
            md.append(
                f"| {ax.upper()} | {f(d.get('total_rmse_cm'))} | {f(d.get('err_bias_cm'))} "
                f"| {f(d.get('err_amplitude_cm'))} | {f(d.get('err_phase_cm'))} "
                f"| {f(d.get('residual_rmse_cm'))} | {f(d.get('gain'))} | {f(d.get('lag_ms'), 0)} |")
        md.append("")

    yd = geom.get("yaw_drift")
    if yd is not None:
        md += [
            "### Yaw heading-hold drift",
            "",
            "| Cmd (°) | Final offset (°) | Mean offset (°) | Drift (°/s) | Total drift (°) | P2P (°) |",
            "|---------|------------------|-----------------|-------------|-----------------|---------|",
            f"| {f(yd.get('cmd_deg'))} | {f(yd.get('final_offset_deg'))} | {f(yd.get('mean_offset_deg'))} "
            f"| {f(yd.get('drift_rate_deg_s'))} | {f(yd.get('total_drift_deg'))} | {f(yd.get('peak_to_peak_deg'))} |",
            "",
        ]
    return md


def build_markdown_report(csv_path, plot_dir, all_results, params_snapshot, json_record) -> str:
    timestamp = json_record.get("timestamp", "")
    duration = json_record.get("duration_s", 0)
    samples = json_record.get("rows_parsed", 0)
    payload = params_snapshot.get("payload", "UNKNOWN")
    exp_id = json_record.get("experiment_id", "")
    
    md = [
        f"# Flight Analysis Report: {exp_id}",
        "",
        f"**Date:** {timestamp} | **Duration:** {duration:.1f}s | **Samples:** {samples} | **Config:** {payload}",
        "",
        "---",
        "",
    ]
    md += _verdict_and_path_md(json_record)
    md += [
        "## MRAC Scoreboard (attitude / rate loops)",
        "",
        "| Axis  | RMSE | RMSE_ss | RMSE_tr | ρ_mean | ρ_p95 | Phase | ‖Θ‖ | ⚠ | 🔴 |",
        "|-------|------|---------|---------|--------|-------|-------|------|---|---|"
    ]
    
    for ax in ["pitch", "roll", "yaw", "z"]:
        sb = json_record["scoreboard"].get(ax, {})
        if not sb:
            md.append(f"| {ax.capitalize()} | - | - | - | - | - | - | - | - | - |")
            continue
        
        def fmt(v, p=3): return f"{v:.{p}f}" if v is not None else "-"
        
        md.append(f"| {ax.capitalize()} | {fmt(sb.get('rmse'))} | {fmt(sb.get('rmse_steady'))} | {fmt(sb.get('rmse_transient'))} "
                  f"| {fmt(sb.get('rho_mean'))} | {fmt(sb.get('rho_p95'))} | {sb.get('phase_relationship', '-')} "
                  f"| {fmt(sb.get('weight_norm_final'))} | {sb.get('alerts_warn', 0)} | {sb.get('alerts_critical', 0)} |")

    md.extend(["", "## Alerts", ""])
    
    all_alerts = []
    for ax, res in all_results.items():
        if res and res["alerts"]:
            all_alerts.extend(res["alerts"])
            
    all_alerts.sort(key=lambda a: {"CRITICAL": 0, "WARN": 1, "INFO": 2}.get(a["level"], 3))
    
    for a in all_alerts:
        md.append(f"- [{a['level']}] **{a['code']}**: {a['message']}")
        
    md.extend(["", "## Per-Axis Detail", ""])
    
    for ax in ["pitch", "roll", "yaw", "z"]:
        res = all_results.get(ax)
        if not res: continue
        
        md.extend([f"### {ax.capitalize()}", ""])
        trk = res["tracking"]
        if trk:
            md.extend([
                "#### Tracking",
                f"![{ax.capitalize()} Tracking](windowed_rmse_{ax}.png)",
                "",
                "| Metric | Value |",
                "|--------|-------|",
                f"| RMSE | {trk.get('rmse', 0):.3f} |",
                f"| MAE | {trk.get('mae', 0):.3f} |",
                f"| Peak Error | {trk.get('peak_error', 0):.3f} |",
                f"| Steady-State RMSE | {trk.get('rmse_steady') or '-' } |",
                f"| Transient RMSE | {trk.get('rmse_transient') or '-' } |",
                ""
            ])
            
        auth = res["authority"]
        phz = res["phase"]
        if auth:
            md.extend([
                "#### Control Authority",
                f"![{ax.capitalize()} Authority](authority_timeline_{ax}.png)",
                f"- ρ_mean = {auth.get('rho_mean',0):.3f}, ρ_p95 = {auth.get('rho_p95',0):.3f}",
                f"- u_ad RMS = {auth.get('u_ad_rms_mixer',0):.2f} mixer units, u_nom RMS = {auth.get('u_nom_rms',0):.2f} mixer units",
                f"- Phase relationship: {phz.get('relationship', '-')} (r = {phz.get('xcorr_lag0', 0):.2f})",
                ""
            ])
            
        wgt = res["weights"]
        if wgt:
            md.extend([
                "#### Weight Health",
                f"![{ax.capitalize()} Adaptive Weights](weight_trajectory_{ax}.png)",
                "| Weight | θ_final | Drift (/s) | Proj. Hits | Oscillation (/s) |",
                "|--------|---------|------------|------------|-------------------|"
            ])
            labels = ["bias", "angle", "rate", "drag", "un", "v"]
            for w in wgt.get("per_weight", []):
                idx = w["index"]
                lbl = labels[idx] if idx < len(labels) else str(idx)
                md.append(f"| W[{idx}] {lbl} | {w['theta_final']:.3f} | {w['drift_rate']:.4f} | {w['projection_hits_frac']:.1%} | {w['zero_crossings_per_sec']:.2f} |")
                
            trend = "↑ DIVERGING" if wgt.get("weight_norm_increasing") else "→ STABLE/CONVERGING"
            md.extend([
                "",
                f"- ‖Θ‖ final = {wgt.get('weight_norm_final',0):.3f}, trending: {trend}",
                f"- Hard-freeze fraction: {wgt.get('frozen_frac',0):.1%}",
                ""
            ])
            
        spec = res["spectral"]
        if spec:
            md.extend([
                "#### Spectral",
                f"![{ax.capitalize()} Spectral](spectral_{ax}.png)",
                f"- Dominant freq: {spec.get('dominant_freq_hz', 0):.1f} Hz | Bandwidth: {spec.get('bandwidth_3db_hz', 0):.1f} Hz | DC fraction: {spec.get('psd_dc_fraction', 0):.0%}",
                ""
            ])

    md.extend([
        "## Firmware Parameters (Snapshot)",
        "```json",
        json.dumps(params_snapshot, indent=2),
        "```",
        ""
    ])
    
    return "\n".join(md)

def _load_meta(csv_path):
    """Resolve (mode, real_params) from an optional argv[3] meta json
    ({"mode":..., "params":{...}}), else infer mode from the filename."""
    mode, real_params = None, {}
    if len(sys.argv) >= 4 and sys.argv[3]:
        try:
            meta = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
            mode = meta.get("mode")
            real_params = meta.get("params", {}) or {}
        except Exception as e:
            print(f"[deep_analysis] could not read meta file: {e}")
    if not mode:
        parts = csv_path.stem.split("_")
        mode = parts[1] if len(parts) >= 3 else "unknown"
    return mode, real_params


def _write_summary_md(plot_dir, csv_path, mode, real_params, json_record):
    """Enriched per-run summary.md: header + What-Happened verdict + headline scorecard."""
    from datetime import datetime
    geom = json_record.get("path_geometry", {}) or {}
    lines = [
        f"# Flight Summary: {mode.upper()}",
        "",
        f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ",
        f"**Source CSV**: `{csv_path.name}`  ",
        f"**Mode**: `{mode}`  ",
        f"**Rank score** ({geom.get('rank_metric', '-')}): "
        f"{geom.get('rank_score') if geom.get('rank_score') is not None else '-'}  ",
        "",
        "## What Happened",
        "",
    ]
    for line in json_record.get("verdict", []) or ["(no verdict generated)"]:
        lines.append(f"- {line}")
    lines += ["", "## Parameters", ""]
    for k, v in (real_params or {}).items():
        lines.append(f"- **{k}**: {v}")
    lines += [
        "",
        "## Plots & Full Report",
        "",
        "See `report.md` and the `.png` files in this folder (XY trajectory, position,",
        "tracking, MRAC authority/weights/spectral).",
        "",
    ]
    (plot_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    if len(sys.argv) < 3:
        sys.exit("Usage: deep_analysis.py <csv_path> <plot_dir> [meta_json]")

    csv_path = Path(sys.argv[1])
    plot_dir = Path(sys.argv[2])
    plot_dir.mkdir(parents=True, exist_ok=True)
    mode, real_params = _load_meta(csv_path)

    print(f"[deep_analysis] Loading {csv_path}  (mode={mode})")
    data = load_flight_data(str(csv_path))
    if not data:
        sys.exit("[deep_analysis] Empty or invalid CSV.")

    AXES = {
        "pitch": {"mixer": MIXER_PR, "rate_loop": "pitch"},
        "roll":  {"mixer": MIXER_PR, "rate_loop": "roll"},
        "yaw":   {"mixer": MIXER_YAW, "rate_loop": "yaw"},
        "z":     {"mixer": MIXER_Z,  "rate_loop": "z_pos"},
    }
    
    params = snapshot_firmware_params()
    all_results = {}
    
    for axis, cfg in AXES.items():
        try:
            auth    = compute_authority(data, axis, cfg["mixer"])
            track   = compute_tracking_metrics(data, cfg["rate_loop"])
            wts     = analyze_weights(data, axis, MAX_NUM_BASIS, WLIM.get(axis, WLIM["pitch"]))
            spec    = compute_spectral_summary(data, axis)
            phase   = compute_phase_coherence(data, axis, cfg["mixer"])
            alerts  = generate_alerts(auth, track, wts, spec, phase, axis)
            
            all_results[axis] = {
                "authority": auth,
                "tracking": track,
                "weights": wts,
                "spectral": spec,
                "phase": phase,
                "alerts": alerts,
            }
            
            plot_windowed_rmse(track, axis, plot_dir)
            plot_weight_trajectories(data, axis, MAX_NUM_BASIS, WLIM.get(axis, WLIM["pitch"]), plot_dir)
            plot_spectral(data, axis, plot_dir)
            plot_authority_timeline(data, axis, cfg["mixer"], plot_dir)
            
        except Exception as e:
            print(f"[deep_analysis] Error processing axis {axis}: {e}")
            all_results[axis] = None

    json_record = build_json_record(csv_path, all_results, params)

    # --- path-tracking geometry, flight context, verdict (the holistic blocks) ---
    json_record["mode"] = mode
    json_record["params"] = real_params
    json_record["path_geometry"] = compute_path_geometry(data, mode, real_params)
    json_record["context"] = compute_context(data)
    json_record["verdict"] = build_verdict(json_record)

    plot_xy_trajectory(data, mode, real_params, plot_dir)
    plot_position_tracking(data, plot_dir)
    plot_tracking_decomposition(json_record["path_geometry"].get("tracking_decomp"), plot_dir)

    gs_root = Path(__file__).resolve().parent.parent
    results_dir = gs_root / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    json_path = results_dir / f"{csv_path.stem}.json"
    json_path.write_text(json.dumps(json_record, indent=2, default=str), encoding="utf-8")
    print(f"[deep_analysis] JSON saved: {json_path}")

    md_content = build_markdown_report(csv_path, plot_dir, all_results, params, json_record)
    (plot_dir / "report.md").write_text(md_content, encoding="utf-8")
    _write_summary_md(plot_dir, csv_path, mode, real_params, json_record)
    print(f"[deep_analysis] Report + summary saved in {plot_dir}")

    # --- champion store + cross-run history (stage 2/3) ---
    try:
        import eval_store
        record = eval_store.build_record(json_record, mode, real_params)
        delta = eval_store.update_store(gs_root, record)
        json_record["champion_delta"] = delta
        json_path.write_text(json.dumps(json_record, indent=2, default=str), encoding="utf-8")
        if delta.get("is_overall_champion"):
            print(f"[deep_analysis] NEW CHAMPION for {mode} (score={record.get('rank_score')})")
        else:
            print(f"[deep_analysis] champion store updated ({mode}/{record['config_hash']})")
    except Exception as e:
        print(f"[deep_analysis] champion store update failed: {e}")


if __name__ == "__main__":
    main()
