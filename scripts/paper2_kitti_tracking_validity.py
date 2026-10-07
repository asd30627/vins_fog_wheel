#!/usr/bin/env python3
"""Paper-2 v5 — KITTI Tracking real-sequence VALIDITY validation. STANDALONE; no backend.

Change: paper2-observability-aware-object-validity-v5.

Tests whether the CARLA dynamic_v3 phenomena hold on REAL driving:
  (1) velocity validity decreases with distance, (2) position validity more stable than velocity,
  (3) position-only regime exists, (4) invalid-velocity / refusal still meaningful.

Pipeline: YOLOv8m on image_02 (left) -> match each detection to a GT label_02 object by 2D IoU ->
MONOCULAR bbox-height depth (depth = fy * H_class / bbox_px_height) -> raw 3D (camera ground plane x,z).
GT 3D = label_02 location. (image_03/right zip arrived CORRUPTED -> stereo unavailable; monocular
bbox-height is the standard cheap cue and its depth noise grows with distance the SAME way -> still tests
the geometric observability phenomenon. Honest caveat: depth source differs from CARLA stereo + class-height prior.)
Velocity ERROR (ego-motion-INDEPENDENT): vel_err = ||raw_disp - gt_disp||/dt over consecutive same-track
frames (ego motion cancels in the vector difference -> no oxts ego-comp). Same thresholds/bins as CARLA.
"""
from __future__ import annotations
import argparse, math
from pathlib import Path
import numpy as np, pandas as pd

WS = Path("/home/ivlab3/fwvio_estimator_ws_wheel")
KR = Path("/mnt/sata4t/datasets/kitti/tracking/training")
# GT KITTI type -> (typical real height m, coarse class)
HCLASS = {"Car": 1.5, "Van": 2.0, "Truck": 3.2, "Pedestrian": 1.75, "Person_sitting": 1.4,
          "Cyclist": 1.7, "Tram": 3.4}
YOLO_MOVABLE = {"car", "truck", "bus", "person", "bicycle", "motorcycle"}
DT, POS_T, VEL_T = 0.1, 3.0, 3.0
BINS = [(0, 15, "0-15m"), (15, 30, "15-30m"), (30, 1e9, "30m+")]


def bin_of(r):
    for lo, hi, lb in BINS:
        if lo <= r < hi:
            return lb
    return "30m+"


def iou(a, b):
    x1, y1 = max(a[0], b[0]), max(a[1], b[1]); x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    iw, ih = max(0, x2 - x1), max(0, y2 - y1); inter = iw * ih
    ua = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - inter
    return inter / ua if ua > 0 else 0.0


def parse_calib(seq):
    P = {}
    for ln in (KR / "calib" / f"{seq}.txt").read_text().splitlines():
        if ln[:2] in ("P2", "P3") and ":" in ln:
            P[ln[:2]] = np.array([float(x) for x in ln.split()[1:]]).reshape(3, 4)
    return P["P2"][0, 0], P["P2"][1, 1], P["P2"][0, 2], P["P2"][1, 2]   # fx, fy, cx, cy


def parse_label(seq):
    d = {}
    for ln in (KR / "label_02" / f"{seq}.txt").read_text().splitlines():
        p = ln.split()
        if len(p) < 17 or p[2] not in HCLASS:
            continue
        loc = [float(p[13]), float(p[14]), float(p[15])]
        if loc[2] <= 0:
            continue
        d.setdefault(int(p[0]), []).append(dict(tid=int(p[1]), typ=p[2],
                    bbox=[float(p[6]), float(p[7]), float(p[8]), float(p[9])], loc=loc,
                    trunc=float(p[4]), occ=float(p[5])))
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seqs", default="all")
    ap.add_argument("--max-frames", type=int, default=0)
    ap.add_argument("--yolo", default="/home/ivlab3/fwvio_estimator_ws_wheel/kaist_grade_scripts/yolov8m.pt")
    a = ap.parse_args()
    import cv2
    from ultralytics import YOLO
    model = YOLO(a.yolo); names = model.names
    seqs = sorted(p.stem for p in (KR / "label_02").glob("*.txt")) if a.seqs == "all" else a.seqs.split(",")
    rows = []
    for seq in seqs:
        idir = KR / "image_02" / seq
        if not idir.exists():
            continue
        fx, fy, cx, cy = parse_calib(seq); lab = parse_label(seq)
        frames = sorted(int(p.stem) for p in idir.glob("*.png"))
        if a.max_frames:
            frames = frames[: a.max_frames]
        prev = {}
        for fi in frames:
            if fi not in lab:
                continue
            img = cv2.imread(str(idir / f"{fi:06d}.png"))
            if img is None:
                continue
            res = model(img, conf=0.30, verbose=False)[0]
            dets = []
            if res.boxes is not None:
                for b in res.boxes:
                    if names[int(b.cls)] in YOLO_MOVABLE:
                        dets.append((b.xyxy[0].tolist(), float(b.conf)))
            cur = {}
            for o in lab[fi]:
                # IoU-match a YOLO det to this GT object
                best = None; bi = 0.4; bconf = 0.0
                for bb, cf in dets:
                    j = iou(bb, o["bbox"])
                    if j > bi:
                        bi = j; best = bb; bconf = cf
                if best is None:
                    continue
                x1, y1, x2, y2 = best; u = (x1+x2)/2; hpx = max(y2 - y1, 1.0); wpx = max(x2 - x1, 1.0)
                depth = fy * HCLASS[o["typ"]] / hpx            # monocular bbox-height depth
                rawX = (u - cx) * depth / fx; rawZ = depth
                gtX, gtZ = o["loc"][0], o["loc"][2]; rng = gtZ
                pos_err = math.hypot(rawX - gtX, rawZ - gtZ)
                bearing = math.degrees(math.atan2(rawX, rawZ))
                rec = dict(seq=seq, frame=fi, tid=o["tid"], typ=o["typ"], range_m=rng, depth_m=depth,
                           bbox_h=hpx, bbox_w=wpx, bbox_area=hpx*wpx, det_conf=round(bconf,3),
                           bearing_deg=round(bearing,2), raw_x=round(rawX,3), raw_z=round(rawZ,3),
                           iou=round(bi, 2), trunc=o["trunc"], occ=o["occ"], pos_err_m=pos_err)
                p = prev.get(o["tid"]); vel_err = float("nan")
                if p and (fi - p[0]) == 1:
                    rd = (rawX - p[1][0], rawZ - p[1][1]); gd = (gtX - p[2][0], gtZ - p[2][1])
                    vel_err = math.hypot(rd[0]-gd[0], rd[1]-gd[1]) / DT
                rec["vel_err_ms"] = vel_err
                rows.append(rec); cur[o["tid"]] = (fi, (rawX, rawZ), (gtX, gtZ))
            prev = cur
        print(f"[kitti] {seq}: rows={len(rows)}")

    if not rows:
        print("[kitti] NO rows (no YOLO-GT matches / images missing)."); return
    df = pd.DataFrame(rows)
    df["dist_bin"] = df["range_m"].apply(bin_of)
    df["position_valid"] = (df["pos_err_m"] <= POS_T).astype(int)
    df["has_vel"] = df["vel_err_ms"].notna().astype(int)
    df["velocity_valid"] = np.where(df["has_vel"] == 1, (df["vel_err_ms"] <= VEL_T).astype(int), 0)
    df["position_only"] = ((df["position_valid"] == 1) & (df["velocity_valid"] == 0)).astype(int)
    df["invalid_velocity"] = (df["velocity_valid"] == 0).astype(int)
    df.to_csv(WS / "paper2_kitti_validity_dataset.csv", index=False)
    print(f"[kitti] total {len(df)} (with vel {int(df.has_vel.sum())})")
    for _, _, b in BINS:
        g = df[df.dist_bin == b]; gv = g[g.has_vel == 1]
        print(f"  {b}: n={len(g)} pos_valid={g.position_valid.mean():.2f} "
              f"vel_valid={gv.velocity_valid.mean():.2f} (nvel={len(gv)}) pos_only={g.position_only.mean():.2f}")


if __name__ == "__main__":
    main()
