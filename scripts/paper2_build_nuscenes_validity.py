#!/usr/bin/env python3
"""Paper-2 nuScenes Stage C (nusc env) — assemble validity dataset (KITTI-schema).

Per YOLO detection (dets.csv): lidar depth in bbox -> raw ego-frame position -> raw world velocity
(finite-diff along ByteTrack track) -> match to GT (IoU) -> labels. Emit paper2_nuscenes_validity_dataset.csv
with columns mirroring the KITTI validity CSV so paper2_tcsv_features.load_nuscenes can reuse the pipeline.

Features are runtime-observable (YOLO bbox + lidar depth); only labels (pos_err, vel_err) use GT.
"""
from __future__ import annotations
import csv, os, math
from collections import defaultdict
from pathlib import Path
import numpy as np
from nuscenes.nuscenes import NuScenes
from nuscenes.utils.data_classes import LidarPointCloud
from nuscenes.utils.geometry_utils import view_points
from pyquaternion import Quaternion

ROOT = "/mnt/sata4t/datasets/nuscenes"
OUTDIR = Path("/home/ivlab3/fwvio_estimator_ws_wheel/paper2/nuscenes")
POS_T, VEL_T = 3.0, 3.0
IOU_MATCH = 0.3


def iou(a, b):
    x0 = max(a[0], b[0]); y0 = max(a[1], b[1]); x1 = min(a[2], b[2]); y1 = min(a[3], b[3])
    iw = max(0, x1 - x0); ih = max(0, y1 - y0); inter = iw * ih
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua > 0 else 0.0


def lidar_uvz(nusc, cam_sd_tok, lidar_sd_tok):
    """Project LIDAR_TOP points into CAM_FRONT -> (u,v,depth) arrays (depth>0, in image)."""
    sd_cam = nusc.get("sample_data", cam_sd_tok); sd_lid = nusc.get("sample_data", lidar_sd_tok)
    pc = LidarPointCloud.from_file(os.path.join(ROOT, sd_lid["filename"]))
    cs_lid = nusc.get("calibrated_sensor", sd_lid["calibrated_sensor_token"])
    ep_lid = nusc.get("ego_pose", sd_lid["ego_pose_token"])
    cs_cam = nusc.get("calibrated_sensor", sd_cam["calibrated_sensor_token"])
    ep_cam = nusc.get("ego_pose", sd_cam["ego_pose_token"])
    # lidar -> ego_lid -> global -> ego_cam -> cam
    pc.rotate(Quaternion(cs_lid["rotation"]).rotation_matrix); pc.translate(np.array(cs_lid["translation"]))
    pc.rotate(Quaternion(ep_lid["rotation"]).rotation_matrix); pc.translate(np.array(ep_lid["translation"]))
    pc.translate(-np.array(ep_cam["translation"])); pc.rotate(Quaternion(ep_cam["rotation"]).rotation_matrix.T)
    pc.translate(-np.array(cs_cam["translation"])); pc.rotate(Quaternion(cs_cam["rotation"]).rotation_matrix.T)
    pts = pc.points[:3, :]; depth = pts[2, :]
    K = np.array(cs_cam["camera_intrinsic"])
    uv = view_points(pts, K, normalize=True)[:2, :]
    m = depth > 1.0
    return uv[0, m], uv[1, m], depth[m], K, cs_cam, ep_cam


def ego_to_global(p_ego, ep):
    return Quaternion(ep["rotation"]).rotate(np.array(p_ego)) + np.array(ep["translation"])


def main():
    man = {r["sample_token"]: r for r in csv.DictReader(open(OUTDIR / "manifest.csv"))}
    gts = defaultdict(list)
    for g in csv.DictReader(open(OUTDIR / "gt.csv")):
        gts[g["sample_token"]].append(g)
    dets = list(csv.DictReader(open(OUTDIR / "dets.csv")))
    by_kf = defaultdict(list)
    for d in dets:
        by_kf[d["sample_token"]].append(d)
    nusc = NuScenes(version="v1.0-trainval", dataroot=ROOT, verbose=False)

    # pass 1: per-detection raw pos (ego + global), depth, matched GT
    recs = []
    for stok, ds in by_kf.items():
        if stok not in man:
            continue
        m = man[stok]
        u, v, z, K, cs_cam, ep_cam = lidar_uvz(nusc, m["cam_sd"], m["lidar_sd"])
        fx, fy, cx, cy = K[0, 0], K[1, 1], K[0, 2], K[1, 2]
        gt_boxes = gts.get(stok, [])
        for d in ds:
            bb = [float(d["x0"]), float(d["y0"]), float(d["x1"]), float(d["y1"])]
            inb = (u >= bb[0]) & (u <= bb[2]) & (v >= bb[1]) & (v <= bb[3])
            if inb.sum() < 3:
                continue  # no lidar support -> undepthable, skip
            depth = float(np.median(z[inb]))
            uu, vv = float(d["u"]), float(d["v"])
            # back-project bbox center at median depth -> camera frame -> ego frame
            xc = (uu - cx) / fx * depth; yc = (vv - cy) / fy * depth; zc = depth
            p_cam = np.array([xc, yc, zc])
            p_ego = Quaternion(cs_cam["rotation"]).rotate(p_cam) + np.array(cs_cam["translation"])
            fwd, lat = float(p_ego[0]), float(p_ego[1])
            p_glob = ego_to_global(p_ego, ep_cam)
            # match to GT by IoU
            best = None; best_iou = IOU_MATCH
            for g in gt_boxes:
                gb = [float(g["bx0"]), float(g["by0"]), float(g["bx1"]), float(g["by1"])]
                i = iou(bb, gb)
                if i > best_iou:
                    best_iou = i; best = g
            # group id = matched GT instance (grouping/labels may use GT, like CARLA's GT track_id);
            # features are computed from RAW positions only. Unmatched -> no group (tid=-1).
            tid_str = best["instance"] if best else "-1"
            recs.append(dict(seq=d["scene"], tid=tid_str, frame=int(d["frame_idx"]),
                             t_s=float(m["t_s"]), raw_x=lat, raw_z=fwd, px=p_glob[0], py=p_glob[1],
                             range_m=math.hypot(fwd, lat), bearing_deg=math.degrees(math.atan2(lat, fwd)),
                             bbox_area=float(d["bw"]) * float(d["bh"]), depth_m=depth, det_conf=float(d["conf"]),
                             matched=1 if best else 0,
                             gt_fwd=float(best["gt_fwd"]) if best else np.nan,
                             gt_lat=float(best["gt_lat"]) if best else np.nan,
                             gt_vx_glob=float(best["gt_vx_glob"]) if best else np.nan,
                             gt_vy_glob=float(best["gt_vy_glob"]) if best else np.nan,
                             gt_speed_ms=math.hypot(float(best["gt_vx_glob"]), float(best["gt_vy_glob"])) if best else np.nan,
                             category=best["category"] if best else "", visibility=best["visibility"] if best else "",
                             num_lidar_pts=int(best["num_lidar_pts"]) if best else 0))
    # pass 2: raw world velocity by finite-diff along track (consecutive keyframes)
    recs.sort(key=lambda r: (r["seq"], r["tid"], r["frame"]))
    by_track = defaultdict(list)
    for r in recs:
        if r["tid"] != "-1":
            by_track[(r["seq"], r["tid"])].append(r)
    for key, rs in by_track.items():
        for i in range(len(rs)):
            r = rs[i]; r["raw_speed_ms"] = np.nan; r["vel_err_ms"] = np.nan
            if i >= 1 and rs[i]["frame"] - rs[i - 1]["frame"] == 1:
                dt = rs[i]["t_s"] - rs[i - 1]["t_s"]
                if dt > 1e-3:
                    vx = (rs[i]["px"] - rs[i - 1]["px"]) / dt; vy = (rs[i]["py"] - rs[i - 1]["py"]) / dt
                    r["raw_speed_ms"] = math.hypot(vx, vy)
                    if r["matched"] and np.isfinite(r["gt_vx_glob"]):
                        r["vel_err_ms"] = math.hypot(vx - r["gt_vx_glob"], vy - r["gt_vy_glob"])
    for r in recs:
        r["pos_err_m"] = (math.hypot(r["raw_x"] - r["gt_lat"], r["raw_z"] - r["gt_fwd"])
                          if r["matched"] and np.isfinite(r["gt_fwd"]) else np.nan)

    cols = ["seq", "tid", "frame", "t_s", "raw_x", "raw_z", "range_m", "bearing_deg", "bbox_area", "depth_m",
            "det_conf", "raw_speed_ms", "matched", "pos_err_m", "vel_err_ms", "gt_speed_ms", "category",
            "visibility", "num_lidar_pts"]
    out = OUTDIR / "paper2_nuscenes_validity_dataset.csv"
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore"); w.writeheader()
        for r in recs:
            w.writerow({k: (round(r[k], 4) if isinstance(r.get(k), float) else r.get(k)) for k in cols})
    nm = sum(r["matched"] for r in recs); nv = sum(1 for r in recs if np.isfinite(r.get("vel_err_ms", np.nan)))
    print(f"[nusc-build] dets_with_depth={len(recs)} matched={nm} with_vel={nv} -> {out}")
    if nv:
        vv = np.mean([1 if (np.isfinite(r.get('vel_err_ms', np.nan)) and r['vel_err_ms'] <= VEL_T) else 0
                      for r in recs if np.isfinite(r.get('vel_err_ms', np.nan))])
        pv = np.mean([1 if (np.isfinite(r.get('pos_err_m', np.nan)) and r['pos_err_m'] <= POS_T) else 0
                      for r in recs if r['matched']])
        print(f"[nusc-build] velocity_valid base rate={vv:.3f} position_valid base rate={pv:.3f}")


if __name__ == "__main__":
    main()
