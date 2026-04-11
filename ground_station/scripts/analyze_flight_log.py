import argparse
import csv
import pathlib
import sys
from datetime import datetime
import matplotlib.pyplot as plt

def load_flight_data(csv_path: pathlib.Path) -> dict:
    """Read the flat t,frame,key,value format and rebuild into time series."""
    data = {}
    time_points = []
    
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                t = float(row["t_s"])
                k = row["key"]
                v = float(row["value"])
            except Exception:
                continue
                
            if len(time_points) == 0 or t != time_points[-1]:
                time_points.append(t)
                
            if k not in data:
                data[k] = ([], [])
            data[k][0].append(t)
            data[k][1].append(v)
            
    return data

def _save(fig: plt.Figure, out_dir: pathlib.Path, name: str) -> None:
    p = out_dir / f"{name}.png"
    fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved: {p.name}")

def plot_tracking(data: dict, out_dir: pathlib.Path, src_name: str) -> None:
    # We will plot Pitch, Roll, Yaw, Z, LocX, LocY if available
    loops = ["pitch", "roll", "yaw", "z_pos", "locx", "locy"]
    
    for loop in loops:
        des_k = f"pid.{loop}.Des"
        fb_k = f"pid.{loop}.FB"
        u_k = f"pid.{loop}.U"
        
        has_des = des_k in data or f"pid_{loop}_Des" in data
        has_fb = fb_k in data or f"pid_{loop}_FB" in data
        
        if not (has_des or has_fb):
            continue
            
        real_des_k = des_k if des_k in data else f"pid_{loop}_Des"
        real_fb_k = fb_k if fb_k in data else f"pid_{loop}_FB"
        real_u_k = u_k if u_k in data else f"pid_{loop}_U"
        
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
        
        if has_des:
            ax1.plot(data[real_des_k][0], data[real_des_k][1], 'k--', lw=1.5, label="Target / Desired")
        if has_fb:
            ax1.plot(data[real_fb_k][0], data[real_fb_k][1], 'royalblue', lw=1.5, label="Measured / Feedback")
            
        ax1.set_title(f"{loop.upper()} Tracking - {src_name}")
        ax1.set_ylabel("Value")
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        if real_u_k in data:
            ax2.plot(data[real_u_k][0], data[real_u_k][1], 'tab:red', lw=1.2, label="Control Effort (U)")
            ax2.set_ylabel("Effort")
            ax2.legend()
            ax2.grid(True, alpha=0.3)
            
        ax2.set_xlabel("Time (s)")
        fig.tight_layout()
        _save(fig, out_dir, f"tracking_{loop}")

def plot_mrac_adaptive(data: dict, out_dir: pathlib.Path, src_name: str) -> None:
    # mrac_pitch_e, mrac_pitch_u_ad, mrac_pitch_u_nom
    axes = ["pitch", "roll", "yaw", "z"]
    
    for axis in axes:
        e_k = f"mrac.{axis}.e"
        uad_k = f"mrac.{axis}.u_ad"
        unom_k = f"mrac.{axis}.u_nom"

        real_e_k = e_k if e_k in data else f"mrac_{axis}_e"
        real_uad_k = uad_k if uad_k in data else f"mrac_{axis}_u_ad"
        real_unom_k = unom_k if unom_k in data else f"mrac_{axis}_u_nom"

        if real_e_k not in data and real_uad_k not in data:
            continue
            
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
        
        if real_e_k in data:
            ax1.plot(data[real_e_k][0], data[real_e_k][1], 'crimson', lw=1.2, label="MRAC Tracking Error (e)")
            ax1.axhline(0, color="k", lw=0.5, alpha=0.5)
            ax1.set_ylabel("Error")
            ax1.legend()
            ax1.grid(True, alpha=0.3)
            
        if real_uad_k in data:
            ax2.plot(data[real_uad_k][0], data[real_uad_k][1], 'tab:purple', lw=1.5, label="Adaptive Output (U_ad)")
        if real_unom_k in data:
            ax2.plot(data[real_unom_k][0], data[real_unom_k][1], 'tab:green', lw=1.5, label="Nominal Output (U_nom)")
            
        ax2.set_title(f"{axis.upper()} MRAC Outputs")
        ax2.set_ylabel("Command")
        ax2.set_xlabel("Time (s)")
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        fig.tight_layout()
        _save(fig, out_dir, f"mrac_{axis}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv", nargs="?", help="CSV file to analyze")
    args = parser.parse_args()

    if args.csv:
        path = pathlib.Path(args.csv)
    else:
        results = sorted(pathlib.Path("logs").glob("flight_*.csv"))
        if not results:
            sys.exit("No flight CSV found in logs/")
        path = results[-1]
        print(f"Using: {path}")

    data = load_flight_data(path)
    
    if not data:
        sys.exit("Data file is empty or invalid format.")

    script_dir = pathlib.Path(__file__).resolve().parent
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder_name = f"{path.stem}_analysis_{ts}"
    out_dir = script_dir.parent.parent / "Analysis_plots" / folder_name
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nSaving plots to: {out_dir}\n")

    src = path.name
    plot_tracking(data, out_dir, src)
    plot_mrac_adaptive(data, out_dir, src)

    print(f"\nDone - plots saved in:\n  {out_dir}")
    # Write marker file so dashboard knows it succeeded and where
    (out_dir / ".success").write_text(str(out_dir.resolve()))
    
if __name__ == "__main__":
    main()

