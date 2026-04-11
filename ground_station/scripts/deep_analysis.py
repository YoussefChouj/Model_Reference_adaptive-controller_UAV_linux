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
    
    rho_instant = np.abs(u_ad_mixer) / np.maximum(np.abs(u_nom_interp), 1.0)
    
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
        u_ad_n = np.array(u_ad) * mixer_scale
        u_nom_n = np.array(u_nom)
        u_nom_interp = np.interp(t_ad, t_nom, u_nom_n)
        rho = np.abs(u_ad_n) / np.maximum(np.abs(u_nom_interp), 1.0)
        
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
        "## Scoreboard",
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

def main():
    if len(sys.argv) < 3:
        sys.exit("Usage: deep_analysis.py <csv_path> <plot_dir>")
        
    csv_path = Path(sys.argv[1])
    plot_dir = Path(sys.argv[2])
    
    print(f"[deep_analysis] Loading {csv_path}")
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
    
    results_dir = Path(__file__).resolve().parent.parent / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    json_path = results_dir / f"{csv_path.stem}.json"
    json_path.write_text(json.dumps(json_record, indent=2, default=str), encoding="utf-8")
    print(f"[deep_analysis] JSON saved: {json_path}")
    
    md_content = build_markdown_report(csv_path, plot_dir, all_results, params, json_record)
    md_path = plot_dir / "report.md"
    md_path.write_text(md_content, encoding="utf-8")
    print(f"[deep_analysis] Report saved: {md_path}")

if __name__ == "__main__":
    main()
