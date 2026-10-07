#!/usr/bin/env python3
"""Paper-2 nuScenes Stage A (nusc env) — CAM_FRONT keyframe manifest + GT (ego-frame pos/vel).

Emits, over scenes whose CAM_FRONT image + LIDAR_TOP are already extracted:
  manifest.csv : scene, sample_token, t_s, frame_idx (per-scene order), img_path, cam_sd, lidar_sd, fx,fy,cx,cy
  gt.csv       : sample_token, instance, category, visibility, num_lidar_pts,
                 bx0,by0,bx1,by1 (2D bbox in CAM_FRONT), gt_fwd,gt_lat (ego frame), gt_vx,gt_vy (ego frame),
                 gt_range, gt_speed
GT (pos/vel) is for LABELS/eval only. No GT enters features. Movable categories only.
"""
from __future__ import annotations
import argparse, csv, os
from pathlib import Path
import numpy as np
from nuscenes.nuscenes import NuScenes
from nuscenes.utils.geometry_utils import view_points, BoxVisibility
from pyquaternion import Quaternion

ROOT = "/mnt/sata4t/datasets/nuscenes"
OUTDIR = Path("/home/ivlab3/fwvio_estimator_ws_wheel/paper2/nuscenes"); OUTDIR.mkdir(parents=True, exist_ok=True)
MOVABLE = ("vehicle.", "human.")  # cars, trucks, buses, bikes, pedestrians


def global_to_ego(p_global, ego):
    q = Quaternion(ego["rotation"]).inverse
    return q.rotate(np.array(p_global) - np.array(ego["translation"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-scenes", type=int, default=0, help="0=all extracted")
    a = ap.parse_args()
    nusc = NuScenes(version="v1.0-trainval", dataroot=ROOT, verbose=False)
    man = open(OUTDIR / "manifest.csv", "w", newline=""); mw = csv.writer(man)
    mw.writerow(["scene", "sample_token", "t_s", "frame_idx", "img_path", "cam_sd", "lidar_sd", "fx", "fy", "cx", "cy", "img_w", "img_h"])
    gt = open(OUTDIR / "gt.csv", "w", newline=""); gw = csv.writer(gt)
    gw.writerow(["sample_token", "instance", "category", "visibility", "num_lidar_pts",
                 "bx0", "by0", "bx1", "by1", "gt_fwd", "gt_lat", "gt_vx", "gt_vy", "gt_range", "gt_speed",
                 "gt_vx_glob", "gt_vy_glob"])
    n_scene = n_kf = n_gt = 0
    for sc in nusc.scene:
        cam_sd0 = nusc.get("sample", sc["first_sample_token"])["data"]["CAM_FRONT"]
        if not os.path.exists(os.path.join(ROOT, nusc.get("sample_data", cam_sd0)["filename"])):
            continue  # scene not extracted yet
        n_scene += 1
        if a.max_scenes and n_scene > a.max_scenes:
            n_scene -= 1; break
        st = sc["first_sample_token"]; fi = 0
        while st:
            s = nusc.get("sample", st)
            cam_sd = s["data"]["CAM_FRONT"]; lidar_sd = s["data"]["LIDAR_TOP"]
            sd = nusc.get("sample_data", cam_sd)
            imgp = os.path.join(ROOT, sd["filename"])
            cs = nusc.get("calibrated_sensor", sd["calibrated_sensor_token"])
            K = np.array(cs["camera_intrinsic"]); ego = nusc.get("ego_pose", sd["ego_pose_token"])
            if os.path.exists(imgp):
                mw.writerow([sc["token"], st, round(s["timestamp"] / 1e6, 6), fi, imgp, cam_sd, lidar_sd,
                             round(K[0, 0], 3), round(K[1, 1], 3), round(K[0, 2], 3), round(K[1, 2], 3),
                             sd["width"], sd["height"]])
                n_kf += 1
                # GT boxes visible in CAM_FRONT
                _, boxes, K2 = nusc.get_sample_data(cam_sd, box_vis_level=BoxVisibility.ANY)
                for b in boxes:
                    if not b.name.startswith(MOVABLE):
                        continue
                    ann = nusc.get("sample_annotation", b.token)
                    corners = view_points(b.corners(), K2, normalize=True)[:2, :]
                    x0, y0 = corners[0].min(), corners[1].min(); x1, y1 = corners[0].max(), corners[1].max()
                    x0 = max(0, x0); y0 = max(0, y0); x1 = min(sd["width"], x1); y1 = min(sd["height"], y1)
                    if x1 <= x0 + 1 or y1 <= y0 + 1:
                        continue
                    p_ego = global_to_ego(ann["translation"], ego)          # x fwd, y left, z up
                    v_glob = nusc.box_velocity(ann["token"])
                    v_ego = Quaternion(ego["rotation"]).inverse.rotate(np.nan_to_num(v_glob))
                    fwd, lat = float(p_ego[0]), float(p_ego[1])
                    vg = np.nan_to_num(v_glob)
                    gw.writerow([st, ann["instance_token"], b.name, ann["visibility_token"], ann["num_lidar_pts"],
                                 round(float(x0), 1), round(float(y0), 1), round(float(x1), 1), round(float(y1), 1),
                                 round(fwd, 3), round(lat, 3), round(float(v_ego[0]), 3), round(float(v_ego[1]), 3),
                                 round(float(np.hypot(fwd, lat)), 3), round(float(np.hypot(v_ego[0], v_ego[1])), 3),
                                 round(float(vg[0]), 3), round(float(vg[1]), 3)])
                    n_gt += 1
            st = s["next"]; fi += 1
    man.close(); gt.close()
    print(f"[manifest] scenes={n_scene} keyframes={n_kf} gt_boxes={n_gt} -> {OUTDIR}/manifest.csv, gt.csv")


if __name__ == "__main__":
    main()
