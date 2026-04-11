import sys
import argparse
import json
from pathlib import Path
import csv

def main():
    parser = argparse.ArgumentParser(description="Cross-flight ranking engine for experiments.")
    parser.add_argument("--dir", type=str, default="ground_station/results/", help="Path to results directory")
    parser.add_argument("--top", type=int, default=None, help="How many to show")
    parser.add_argument("--sort", type=str, default="composite_score", help="Field to sort by (e.g. composite_score or pitch.rmse)")
    parser.add_argument("--format", type=str, choices=["table", "json", "csv"], default="table", help="Output format")
    parser.add_argument("--export", action="store_true", help="Write output to file in addition to stdout")
    
    args = parser.parse_args()
    
    results_dir = Path(args.dir)
    if not results_dir.exists():
        print(f"[experiment_db] Directory {args.dir} does not exist.")
        return
        
    json_files = list(results_dir.glob("*.json"))
    if not json_files:
        print("[experiment_db] No experiments found.")
        return
        
    records = []
    
    for jf in json_files:
        try:
            with open(jf, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            row = {
                "experiment_id": data.get("experiment_id", ""),
                "timestamp": data.get("timestamp", ""),
                "duration_s": data.get("duration_s", 0),
                "rows_parsed": data.get("rows_parsed", 0),
            }
            
            axes = ["pitch", "roll", "yaw", "z"]
            for ax in axes:
                sb = data.get("scoreboard", {}).get(ax, {})
                row[f"{ax}_rmse"] = sb.get("rmse")
                row[f"{ax}_rho_mean"] = sb.get("rho_mean")
                row[f"{ax}_rho_p95"] = sb.get("rho_p95")
                row[f"{ax}_phase"] = sb.get("phase_relationship", "")
                row[f"{ax}_alerts_critical"] = sb.get("alerts_critical", 0)
                row[f"{ax}_alerts_warn"] = sb.get("alerts_warn", 0)
                row[f"{ax}_weight_norm"] = sb.get("weight_norm_final", 0.0)
                
            # Composite score (lower is better)
            # Default sort: score = mean(axis_rmse) + 2.0 * mean(axis_alerts_critical) + 0.5 * max(axis_rho_p95)
            rmses = [row[f"{ax}_rmse"] for ax in axes if row.get(f"{ax}_rmse") is not None]
            c_alerts = [row[f"{ax}_alerts_critical"] for ax in axes if row.get(f"{ax}_alerts_critical") is not None]
            rho_p95s = [row[f"{ax}_rho_p95"] for ax in axes if row.get(f"{ax}_rho_p95") is not None]
            
            mean_rmse = sum(rmses)/len(rmses) if rmses else 999.0
            mean_c_alerts = sum(c_alerts)/len(c_alerts) if c_alerts else 0.0
            max_rho = max(rho_p95s) if rho_p95s else 0.0
            
            row["composite_score"] = mean_rmse + 2.0 * mean_c_alerts + 0.5 * max_rho
            
            if row["rows_parsed"] < 100:
                row["SUSPECT"] = True
            else:
                row["SUSPECT"] = False
                
            records.append(row)
            
        except Exception as e:
            print(f"[experiment_db] Error parsing {jf}: {e}")
            
    # Sorting
    if args.sort == "composite_score":
        records.sort(key=lambda r: r.get("composite_score", 999.0))
    else:
        # e.g. pitch.rmse -> pitch_rmse
        k = args.sort.replace(".", "_")
        records.sort(key=lambda r: r.get(k, 999.0) if r.get(k) is not None else 999.0)
        
    if args.top:
        records = records[:args.top]
        
    if args.format == "table":
        # simple pretty print
        header = f"{'Experiment':<20} | {'Score':<10} | {'Rows':<6} | {'Pitch RMSE':<10} | {'Roll RMSE':<10} | {'Yaw RMSE':<10} | {'Alerts C/W':<10}"
        print(header)
        print("-" * len(header))
        for r in records:
            suspect = " [SUSPECT]" if r["SUSPECT"] else ""
            p_rmse = f"{r['pitch_rmse']:.3f}" if r.get("pitch_rmse") is not None else "-"
            r_rmse = f"{r['roll_rmse']:.3f}" if r.get("roll_rmse") is not None else "-"
            y_rmse = f"{r['yaw_rmse']:.3f}" if r.get("yaw_rmse") is not None else "-"
            
            cw = sum([r.get(f"{ax}_alerts_critical", 0) for ax in axes])
            ww = sum([r.get(f"{ax}_alerts_warn", 0) for ax in axes])
            al = f"{cw}/{ww}"
            
            print(f"{r['experiment_id']:<20}{suspect} | {r['composite_score']:<10.3f} | {r['rows_parsed']:<6} | {p_rmse:<10} | {r_rmse:<10} | {y_rmse:<10} | {al:<10}")
            
    elif args.format == "json":
        jout = json.dumps(records, indent=2)
        print(jout)
        if args.export:
            p = results_dir / "rankings.json"
            p.write_text(jout)
            print(f"[experiment_db] Exported to {p}")
            
    elif args.format == "csv":
        if records:
            import io
            sio = io.StringIO()
            idx = list(records[0].keys())
            writer = csv.DictWriter(sio, fieldnames=idx)
            writer.writeheader()
            for r in records:
                writer.writerow(r)
            cout = sio.getvalue()
            print(cout)
            if args.export:
                p = results_dir / "rankings.csv"
                p.write_text(cout)
                print(f"[experiment_db] Exported to {p}")

if __name__ == "__main__":
    main()
