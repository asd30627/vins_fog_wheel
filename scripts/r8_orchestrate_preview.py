#!/usr/bin/env python3
"""R8-1 preview orchestrator: for each (town, scenario), record -> GT/image audit -> ORB-SLAM3
baseline pose-count check -> append a row to the preview audit CSV. Fault-tolerant: writes each row
as soon as it's ready, so partial progress survives a hang/interrupt on a later town.

Does NOT modify ORB-SLAM3 backend. Uses the existing wrapper (run_orbslam_carla_logged.sh) purely to
get n_poses for the ">80% poses" PASS criterion.
"""
import csv, json, os, subprocess, sys, time

WS = "/home/ivlab3/fwvio_estimator_ws_wheel"
OUT_CSV = f"{WS}/paper2/track_a/paper2_r8_preview_audit.csv"
FRAMES = 1500

TOWNS = ["Town01", "Town10HD", "Town02", "Town04", "Town05"]
SCENARIOS = ["normal_urban_loop", "anchor_recovery", "dynamic_noise"]

FIELDS = ["town", "scenario", "run_tag", "record_ok", "n_gt_frames", "path_len_m", "duration_s",
          "mean_speed_ms", "loop_dist_to_start_m", "semi_static_object_count",
          "transient_object_count", "mean_orb_keypoints", "object_region_keypoint_ratio",
          "all_dynamic_feature_loss_ratio", "orb_n_poses", "orb_pose_pct", "orb_resets",
          "orb_ok", "pass_verdict", "notes"]


def sh(cmd, timeout=None, log=None):
    lf = open(log, "w") if log else subprocess.DEVNULL
    try:
        r = subprocess.run(cmd, shell=True, timeout=timeout, stdout=lf, stderr=subprocess.STDOUT)
        return r.returncode
    except subprocess.TimeoutExpired:
        return -1
    finally:
        if log:
            lf.close()


def main():
    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    write_header = not os.path.exists(OUT_CSV)
    f = open(OUT_CSV, "a", newline="")
    w = csv.DictWriter(f, fieldnames=FIELDS)
    if write_header:
        w.writeheader()
        f.flush()

    for town in TOWNS:
        for scen in SCENARIOS:
            run_tag = f"{scen}_preview"
            rec_dir = f"/mnt/sata4t/datasets/carla_fwvio/{town}__dynamic_v3r8__run{run_tag}"
            row = {k: "" for k in FIELDS}
            row["town"] = town; row["scenario"] = scen; row["run_tag"] = run_tag
            print(f"\n===== {town} / {scen} {time.strftime('%H:%M:%S')} =====", flush=True)

            # 1) record (timeout guard: 8 min)
            rec_log = f"{WS}/logs/phase6/r8_record_{town}_{scen}.log"
            rc = sh(f"bash {WS}/scripts/r8_record_preview.sh {town} {scen} {run_tag} {FRAMES}",
                    timeout=480, log=rec_log)
            if rc != 0 or not os.path.isdir(rec_dir):
                row["record_ok"] = "FAIL"
                row["notes"] = f"recording failed/timeout rc={rc}"
                w.writerow(row); f.flush()
                print(f"  [FAIL] recording rc={rc}", flush=True)
                continue
            row["record_ok"] = "OK"

            # 2) GT + image audit
            audit_json = f"{WS}/logs/phase6/r8_audit_{town}_{scen}.json"
            sh(f"python3 {WS}/scripts/r8_frame_audit.py --rec {rec_dir} --sample-every 15 --out {audit_json}",
               timeout=300)
            if os.path.exists(audit_json):
                aj = json.load(open(audit_json))
                for k in ["n_gt_frames", "path_len_m", "duration_s", "mean_speed_ms",
                          "loop_dist_to_start_m", "semi_static_object_count",
                          "transient_object_count", "mean_orb_keypoints",
                          "object_region_keypoint_ratio", "all_dynamic_feature_loss_ratio"]:
                    row[k] = aj.get(k, "")
            print(f"  audit: path={row['path_len_m']}m speed={row['mean_speed_ms']} "
                  f"semi_static={row['semi_static_object_count']} transient={row['transient_object_count']} "
                  f"obj_ratio={row['object_region_keypoint_ratio']}", flush=True)

            # 3) ORB-SLAM3 baseline pose-count check (existing wrapper, no backend change)
            orb_label = f"r8_{town}_{scen}"
            orb_log = f"{WS}/logs/phase6/run_r8_orb_{town}_{scen}.log"
            sh(f"bash {WS}/scripts/run_orbslam_carla_logged.sh {rec_dir} {orb_label}",
               timeout=420, log=orb_log)
            sh("pkill -9 -f stereo-inertial; pkill -9 -f paper2_carla_stereo_player_masked", timeout=15)
            time.sleep(2)
            tum = f"{WS}/logs/phase6/orbslam_carla_{orb_label}.tum"
            n_poses = 0
            if os.path.exists(tum):
                n_poses = sum(1 for _ in open(tum))
            n_gt = int(row["n_gt_frames"]) if row["n_gt_frames"] else FRAMES
            pct = round(100.0 * n_poses / max(1, n_gt), 1)
            resets = 0
            slog = f"{WS}/logs/phase6/orbslam_carla_{orb_label}.log"
            if os.path.exists(slog):
                resets = sum(1 for l in open(slog) if "Reseting" in l)
            row["orb_n_poses"] = n_poses
            row["orb_pose_pct"] = pct
            row["orb_resets"] = resets
            row["orb_ok"] = "OK" if pct >= 80 else "LOW"
            print(f"  ORB baseline: poses={n_poses}/{n_gt} ({pct}%) resets={resets}", flush=True)

            # 4) PASS verdict per R8-1 criteria
            try:
                path_ok = float(row["path_len_m"]) > 150
                speed_ok = float(row["mean_speed_ms"]) > 2.5
                orb_ok = pct > 80
                obj_ratio = row["object_region_keypoint_ratio"]
                obj_ok = (obj_ratio not in ("", None)) and float(obj_ratio) > 0.15
                anchor_ok = int(row["semi_static_object_count"] or 0) >= 5
                transient_ok = int(row["transient_object_count"] or 0) >= 3
                verdict_bits = dict(path_ok=path_ok, speed_ok=speed_ok, orb_ok=orb_ok,
                                     obj_region_ok=obj_ok, anchor_count_ok=anchor_ok,
                                     transient_count_ok=transient_ok)
                core_pass = path_ok and speed_ok and orb_ok
                row["pass_verdict"] = ("PASS" if core_pass else "FAIL") + " " + json.dumps(verdict_bits)
            except Exception as e:
                row["pass_verdict"] = f"ERROR {e}"

            w.writerow(row); f.flush()
            print(f"  verdict: {row['pass_verdict']}", flush=True)

    f.close()
    print("\n===== R8-1 PREVIEW BATCH DONE =====", flush=True)


if __name__ == "__main__":
    main()
