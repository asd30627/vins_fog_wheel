#!/usr/bin/env python3
"""Paper-2 G0/G1 — RAW object position/velocity probe + per-detection feature/label extractor (STANDALONE).

Change: paper2-noue-g0-data-grounding / paper2-viwo-conditioned-noue-v4.

NO training, NO NOUE, NO VINS-estimator change, NO object factor. Off-the-shelf parts only:
  YOLOv8m (movable COCO) -> OpenCV SGBM depth (REAL stereo, not GT) -> back-project to body frame
  -> ultralytics ByteTrack association -> ego-motion comp (gt ego_pose) -> raw velocity
  -> GT match by BEARING (robust to depth error) -> per-detection features + error labels.

Writes a RICH per-detection CSV (object features + raw state + GT-matched errors + tags) that is the
shared backbone for the raw-object benchmark (B) and the G2 NOUE dataset (C). Also prints the
distance-binned error table.

Coordinate frames (CARLA): body = (forward=+x, lateral=+y=right, up=+z); lateral sign-consistent
between detection (image +u = right) and GT (inverse-yaw rotation). Match in body frame by bearing.

Run (env `gf`):
  conda run -n gf python scripts/paper2_raw_object_probe.py --rec <REC_DIR> --out-csv <perdet.csv> [--max-frames N]
"""
from __future__ import annotations
import argparse, json, math, sys, csv
from pathlib import Path
import numpy as np

MOVABLE = {"person", "bicycle", "car", "motorcycle", "bus", "truck"}
DIST_BINS = [(0.0, 15.0, "0-15m"), (15.0, 30.0, "15-30m"), (30.0, 1e9, "30m+")]
MATCH_BEARING_RAD = math.radians(4.0)   # bearing-based GT match gate (robust to depth error)
YAW_INJECT_DEG = 1.0


def intrinsics(W, H, fov_deg):
    f = (W / 2.0) / math.tan(math.radians(fov_deg) / 2.0)   # CARLA pinhole fx=fy=f
    return f, f, W / 2.0, H / 2.0


def bin_of(r):
    for lo, hi, lbl in DIST_BINS:
        if lo <= r < hi:
            return lbl
    return DIST_BINS[-1][2]


def pct(a, q):
    return float(np.percentile(a, q)) if len(a) else float("nan")


def tags_from_dir(name):
    # Town10HD__dynamic_v3__runsparse_b1 -> town=Town10HD, run=sparse_b1, density=sparse
    town = name.split("__")[0]
    run = name.split("__run")[-1] if "__run" in name else name
    density = "unknown"
    for d in ("sparse", "medium", "dense"):
        if run.startswith(d) or d in run:
            density = d; break
    return town, density, run


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rec", required=True)
    ap.add_argument("--out-csv", default="paper2_raw_object_probe_results.csv")
    ap.add_argument("--max-frames", type=int, default=0)
    ap.add_argument("--yolo", default="/home/ivlab3/fwvio_estimator_ws_wheel/kaist_grade_scripts/yolov8m.pt")
    ap.add_argument("--conf", type=float, default=0.35)
    ap.add_argument("--town", default=""); ap.add_argument("--density", default=""); ap.add_argument("--run", default="")
    args = ap.parse_args()

    rec = Path(args.rec)
    if not (rec / "recording_meta.json").exists():
        print(f"[probe] FATAL: no recording_meta.json under {rec}", file=sys.stderr); sys.exit(2)
    meta = json.loads((rec / "recording_meta.json").read_text())
    W = int(meta.get("W", 1280)); H = int(meta.get("H", 720)); fov = float(meta.get("fov", 90))
    baseline = float(meta.get("baseline_m", 0.5)); fps = float(meta.get("fps", 20)); dt = 1.0 / fps
    fx, fy, cx, cy = intrinsics(W, H, fov)
    town, density, run = tags_from_dir(rec.name)
    if args.town: town = args.town
    if args.density: density = args.density
    if args.run: run = args.run
    print(f"[probe] {rec.name} {W}x{H} fov={fov} base={baseline} fps={fps} town={town} density={density}")

    lefts = sorted((rec / "stereo_left").glob("*.png"))
    if args.max_frames:
        lefts = lefts[: args.max_frames]
    if not lefts:
        print(f"[probe] FATAL: no stereo_left frames", file=sys.stderr); sys.exit(2)
    gt_files = sorted((rec / "gt").glob("*.json"))
    pos_gt = bool(gt_files) and all(k in next(iter(json.loads(gt_files[len(gt_files)//2].read_text())
                                    .get("per_instance", {1: {}}).values()), {}) for k in ("x", "y", "z"))

    import cv2
    from ultralytics import YOLO
    model = YOLO(args.yolo); names = model.names
    sgbm = cv2.StereoSGBM_create(minDisparity=0, numDisparities=128, blockSize=5,
                                 P1=8*3*5**2, P2=32*3*5**2, uniquenessRatio=10,
                                 speckleWindowSize=100, speckleRange=2, disp12MaxDiff=1)

    track_hist = {}     # tid -> dict(first_frame, last_frame, last_bearing, last_world)
    rows = []; n_det = 0
    err = {lbl: dict(pos=[], spd=[], dir=[], yaw_lat=[], yaw_pred=[]) for _, _, lbl in DIST_BINS}

    for fi, lp in enumerate(lefts):
        rp = rec / "stereo_right" / lp.name
        limg = cv2.imread(str(lp)); rimg = cv2.imread(str(rp)) if rp.exists() else None
        if limg is None:
            continue
        disp = None
        if rimg is not None:
            lg = cv2.cvtColor(limg, cv2.COLOR_BGR2GRAY); rg = cv2.cvtColor(rimg, cv2.COLOR_BGR2GRAY)
            disp = sgbm.compute(lg, rg).astype(np.float32) / 16.0
        res = model.track(limg, persist=True, conf=args.conf, verbose=False, tracker="bytetrack.yaml")[0]
        gframe = json.loads(gt_files[fi].read_text()) if (gt_files and fi < len(gt_files)) else None
        ego = gframe.get("ego_pose") if gframe else None
        gt_insts = gframe.get("per_instance", {}) if gframe else {}
        eyaw = math.radians(ego["yaw"]) if ego else 0.0
        cyaw, syaw = math.cos(eyaw), math.sin(eyaw)
        if res.boxes is None:
            continue
        for b in res.boxes:
            cls = names[int(b.cls)]
            if cls not in MOVABLE:
                continue
            n_det += 1
            x1, y1, x2, y2 = b.xyxy[0].tolist()
            bw, bh = x2 - x1, y2 - y1
            u = (x1 + x2) / 2.0; v = (y1 + y2) / 2.0
            tid = int(b.id) if b.id is not None else -1
            conf = float(b.conf) if b.conf is not None else 0.0
            depth = float("nan"); d_med = float("nan")
            if disp is not None:
                xs1, ys1 = max(0, int(x1)), max(0, int(y1)); xs2, ys2 = min(W, int(x2)), min(H, int(y2))
                patch = disp[ys1:ys2, xs1:xs2]; valid = patch[patch > 0.5]
                if valid.size > 10:
                    d_med = float(np.median(valid)); depth = fx * baseline / d_med
                    d_std = float(np.std(valid))
                else:
                    d_std = float("nan")
            else:
                d_std = float("nan")
            has_d = depth == depth
            det_fwd = depth if has_d else float("nan")
            det_lat = (u - cx) * depth / fx if has_d else float("nan")
            rng = math.hypot(det_fwd, det_lat) if has_d else float("nan")
            bearing = math.atan2(det_lat, det_fwd) if has_d else float("nan")

            th = track_hist.get(tid)
            track_age = (fi - th["first_frame"]) if th else 0
            bearing_change = (bearing - th["last_bearing"]) if (th and has_d and th.get("last_bearing") == th.get("last_bearing")) else float("nan")

            # ego-motion-compensated world pos + raw velocity
            spd = float("nan"); vel_w = np.array([np.nan, np.nan])
            p_world = None
            if ego is not None and has_d:
                wx = ego["x"] + cyaw * det_fwd - syaw * det_lat
                wy = ego["y"] + syaw * det_fwd + cyaw * det_lat
                p_world = (wx, wy)
                if th and th.get("last_world") is not None:
                    nfr = fi - th["last_frame"]
                    if nfr > 0:
                        vel_w = (np.array(p_world) - np.array(th["last_world"])) / (nfr * dt)
                        spd = float(np.linalg.norm(vel_w))
            track_hist[tid] = dict(first_frame=(th["first_frame"] if th else fi), last_frame=fi,
                                   last_bearing=bearing, last_world=p_world)

            # GT match by bearing (front actors only)
            matched = 0; gt_range = gt_fwd = gt_lat = pos_err = gspd = spd_err = dir_err = float("nan"); gt_type = ""
            if pos_gt and has_d and ego is not None and gt_insts:
                bestb = MATCH_BEARING_RAD; best = None; best_fl = None
                for inst in gt_insts.values():
                    if "x" not in inst:
                        continue
                    dx = inst["x"] - ego["x"]; dy = inst["y"] - ego["y"]
                    fgt = cyaw*dx + syaw*dy; lgt = -syaw*dx + cyaw*dy
                    if fgt <= 0:
                        continue
                    db = abs(bearing - math.atan2(lgt, fgt))
                    if db < bestb:
                        bestb = db; best = inst; best_fl = (fgt, lgt)
                if best is not None:
                    matched = 1; gt_fwd, gt_lat = best_fl
                    gt_range = math.hypot(gt_fwd, gt_lat)
                    pos_err = math.hypot(det_fwd - gt_fwd, det_lat - gt_lat)
                    gspd = math.hypot(best.get("vx", 0.0), best.get("vy", 0.0))
                    gt_type = best.get("type_id", "")
                    if spd == spd:
                        spd_err = abs(spd - gspd)
                        if gspd > 0.5 and np.linalg.norm(vel_w) > 0.5:
                            cosang = float(np.dot(vel_w, [best["vx"], best["vy"]]) / (np.linalg.norm(vel_w)*gspd))
                            dir_err = math.degrees(math.acos(max(-1, min(1, cosang))))
                    lbl = bin_of(gt_range)
                    err[lbl]["pos"].append(pos_err)
                    if spd_err == spd_err: err[lbl]["spd"].append(spd_err)
                    if dir_err == dir_err: err[lbl]["dir"].append(dir_err)
                    a = math.radians(YAW_INJECT_DEG)
                    fy_ = math.cos(a)*det_fwd - math.sin(a)*det_lat; ly_ = math.sin(a)*det_fwd + math.cos(a)*det_lat
                    err[lbl]["yaw_lat"].append(float(math.hypot(det_fwd-fy_, det_lat-ly_)))
                    err[lbl]["yaw_pred"].append(gt_range * math.sin(a))

            def r2(x): return round(x, 3) if (x == x) else ""
            rows.append(dict(town=town, density=density, run=run, frame=fi, track_id=tid, cls=cls, conf=round(conf,3),
                             bbox_w=round(bw,1), bbox_h=round(bh,1), bbox_aspect=r2(bw/bh if bh>0 else float('nan')),
                             bbox_area=round(bw*bh,1), area_frac=r2(bw*bh/(W*H)), u=round(u,1), v=round(v,1),
                             disp_med=r2(d_med), disp_std=r2(d_std), depth_m=r2(depth), range_m=r2(rng),
                             bearing_deg=r2(math.degrees(bearing) if bearing==bearing else float('nan')),
                             bearing_change_deg=r2(math.degrees(bearing_change) if bearing_change==bearing_change else float('nan')),
                             track_age=track_age, body_fwd=r2(det_fwd), body_lat=r2(det_lat),
                             raw_speed_ms=r2(spd), matched=matched, gt_range_m=r2(gt_range), gt_type_id=gt_type,
                             pos_err_m=r2(pos_err), gt_speed_ms=r2(gspd), speed_err_ms=r2(spd_err),
                             dir_err_deg=r2(dir_err),
                             dist_bin=(bin_of(gt_range) if matched else (bin_of(rng) if rng==rng else ""))))

    out_csv = Path(args.out_csv)
    if rows:
        with out_csv.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    n_match = sum(r["matched"] for r in rows)
    print(f"[probe] frames={len(lefts)} det={n_det} matched={n_match} pos_gt={pos_gt} -> {out_csv} ({len(rows)} rows)")
    if pos_gt:
        print("distance_bin | n | pos_med | pos_p95 | spd_med | spd_p95 | dir_med | dir_p95 | yaw1_lat_med | rsin1_med")
        for _, _, lbl in DIST_BINS:
            e = err[lbl]; n = len(e["pos"])
            print(f"{lbl} | {n} | {pct(e['pos'],50):.2f} | {pct(e['pos'],95):.2f} | {pct(e['spd'],50):.2f} | "
                  f"{pct(e['spd'],95):.2f} | {pct(e['dir'],50):.1f} | {pct(e['dir'],95):.1f} | "
                  f"{pct(e['yaw_lat'],50):.2f} | {pct(e['yaw_pred'],50):.2f}")
    else:
        print("[probe] position GT absent -> error table BLOCKED (pipeline ran).")


if __name__ == "__main__":
    main()
