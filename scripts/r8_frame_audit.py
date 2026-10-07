#!/usr/bin/env python3
"""R8 preview/core audit — GT geometry + standalone cv2 ORB feature analysis.

Does NOT touch ORB-SLAM3 backend/core. Uses:
  - gt/*.json (ego_pose, per_instance) for path length, speed, loop distance, semi-static/transient
    object counts (speed threshold classification).
  - the CARLA standard camera projection (camera co-moving with vehicle, local offset
    (1.5, -baseline/2, 1.6) for cam0, no extra rotation) to project each object's 3D oriented bbox
    corners into the LEFT image, giving a 2D bbox per object per sampled frame.
  - a standalone cv2.ORB detector (same nFeatures as the CARLA ORB-SLAM3 config, 1200) run directly on
    saved stereo_left frames, to compute: total keypoints, object-region keypoint ratio, and the
    all_dynamic feature-loss ratio (keypoints lost when moving-object regions are blurred out before
    detection, mirroring the masking pipeline's suppress_regions()).

Usage:
  python3 r8_frame_audit.py --rec <recording_dir> --sample-every 15 --out <out.json>
"""
import argparse, glob, json, math, os
import numpy as np

FX = FY = 320.0
CX = 320.0
CY = 240.0
WIDTH, HEIGHT = 640, 480
STATIC_SPEED_THR = 0.3   # m/s, below this all frames -> "semi-static/candidate anchor"
MOVING_SPEED_THR = 0.5   # m/s, above this at least once -> "transient/moving"


def deg2rad(d):
    return d * math.pi / 180.0


def rot_matrix_ue4(roll, pitch, yaw):
    # UE4/CARLA convention: X-forward, Y-right, Z-up; intrinsic yaw(Z)-pitch(Y)-roll(X) in degrees.
    r, p, y = deg2rad(roll), deg2rad(pitch), deg2rad(yaw)
    cy, sy = math.cos(y), math.sin(y)
    cp, sp = math.cos(p), math.sin(p)
    cr, sr = math.cos(r), math.sin(r)
    Rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
    Ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]])
    Rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]])
    return Rz @ Ry @ Rx


def project_point(world_xyz, ego_pos, ego_rot, cam_offset_local):
    """World point -> image (u,v,valid). CARLA UE4-axis camera co-moving with vehicle, no extra rotation."""
    R_v = rot_matrix_ue4(ego_rot[0], ego_rot[1], ego_rot[2])
    cam_world = np.array(ego_pos) + R_v @ np.array(cam_offset_local)
    rel = np.array(world_xyz) - cam_world
    p_cam_ue4 = R_v.T @ rel   # world -> vehicle/camera-aligned UE4 axes (X-fwd,Y-right,Z-up)
    # UE4 cam axes -> standard pinhole axes (x-right,y-down,z-forward)
    x_std, y_std, z_std = p_cam_ue4[1], -p_cam_ue4[2], p_cam_ue4[0]
    if z_std <= 0.3:
        return None
    u = FX * x_std / z_std + CX
    v = FY * y_std / z_std + CY
    return u, v


def object_bbox_2d(inst, ego_pos, ego_rot, cam_offset_local):
    cx, cy, cz = inst["x"], inst["y"], inst["z"]
    ex, ey, ez = inst.get("ext", [1.0, 1.0, 1.0])
    yaw = inst.get("yaw", 0.0)
    Ro = rot_matrix_ue4(0, 0, yaw)
    corners = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                local = np.array([sx * ex, sy * ey, sz * ez])
                world = np.array([cx, cy, cz]) + Ro @ local
                corners.append(world)
    pts = []
    for c in corners:
        r = project_point(c, ego_pos, ego_rot, cam_offset_local)
        if r is not None:
            pts.append(r)
    if len(pts) < 4:
        return None
    us = [p[0] for p in pts]; vs = [p[1] for p in pts]
    x1, x2 = max(0, min(us)), min(WIDTH, max(us))
    y1, y2 = max(0, min(vs)), min(HEIGHT, max(vs))
    if x2 <= x1 or y2 <= y1:
        return None
    return (x1, y1, x2, y2)


def load_gt(rec):
    files = sorted(glob.glob(os.path.join(rec, "gt", "*.json")))
    return files


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rec", required=True)
    ap.add_argument("--sample-every", type=int, default=15)
    ap.add_argument("--out", required=True)
    ap.add_argument("--orb-nfeatures", type=int, default=1200)
    a = ap.parse_args()

    gt_files = load_gt(a.rec)
    if not gt_files:
        json.dump({"error": "no gt files"}, open(a.out, "w"))
        print(f"[r8-audit] ERROR: no gt files in {a.rec}")
        return

    meta_path = os.path.join(a.rec, "recording_meta.json")
    baseline_m = 0.5
    if os.path.exists(meta_path):
        try:
            baseline_m = json.load(open(meta_path)).get("baseline_m", 0.5)
        except Exception:
            pass
    cam0_offset = (1.5, -baseline_m / 2.0, 1.6)

    # ---- GT geometry: path length, speed, loop distance, semi-static/transient object sets ----
    poses = []
    speeds = []
    obj_max_speed = {}   # object id -> max observed speed across the recording
    for f in gt_files:
        d = json.load(open(f))
        e = d["ego_pose"]
        poses.append((e["x"], e["y"]))
        speeds.append(d.get("ego_speed", 0.0))
        for oid, inst in d.get("per_instance", {}).items():
            sp = inst.get("speed", 0.0)
            obj_max_speed[oid] = max(obj_max_speed.get(oid, 0.0), sp)

    path_len = sum(math.dist(poses[i], poses[i + 1]) for i in range(len(poses) - 1))
    mean_speed = float(np.mean(speeds)) if speeds else 0.0
    start = poses[0]
    half = len(poses) // 2
    loop_dist = min(math.dist(start, p) for p in poses[half:]) if len(poses) > half else float("nan")

    semi_static_ids = [oid for oid, s in obj_max_speed.items() if s < STATIC_SPEED_THR]
    transient_ids = [oid for oid, s in obj_max_speed.items() if s >= MOVING_SPEED_THR]

    # ---- Image analysis: ORB keypoints + object-region ratio + all_dynamic feature-loss ----
    try:
        import cv2
        CV_OK = True
    except ImportError:
        CV_OK = False

    frame_stats = []
    if CV_OK:
        orb = cv2.ORB_create(nfeatures=a.orb_nfeatures)
        idxs = list(range(0, len(gt_files), max(1, a.sample_every)))
        for i in idxs:
            d = json.load(open(gt_files[i]))
            frame_no = d["frame"]
            img_path = os.path.join(a.rec, "stereo_left", f"{frame_no:06d}.png")
            if not os.path.exists(img_path):
                continue
            img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
            if img is None:
                continue
            ego = d["ego_pose"]
            ego_pos = (ego["x"], ego["y"], ego["z"])
            ego_rot = (ego.get("roll", 0.0), ego.get("pitch", 0.0), ego["yaw"])
            boxes = []
            moving_boxes = []
            for oid, inst in d.get("per_instance", {}).items():
                bb = object_bbox_2d(inst, ego_pos, ego_rot, cam0_offset)
                if bb is None:
                    continue
                boxes.append(bb)
                if inst.get("speed", 0.0) >= MOVING_SPEED_THR:
                    moving_boxes.append(bb)

            kps = orb.detect(img, None)
            n_total = len(kps)

            def in_any_box(pt, bxs):
                x, y = pt
                for (x1, y1, x2, y2) in bxs:
                    if x1 <= x <= x2 and y1 <= y <= y2:
                        return True
                return False

            n_in_obj = sum(1 for k in kps if in_any_box(k.pt, boxes)) if boxes else 0

            # all_dynamic masking simulation: blur out moving-object regions, re-detect
            img_masked = img.copy()
            for (x1, y1, x2, y2) in moving_boxes:
                xi1, yi1, xi2, yi2 = int(x1), int(y1), int(x2), int(y2)
                if xi2 > xi1 and yi2 > yi1:
                    roi = img_masked[yi1:yi2, xi1:xi2]
                    k = 31 if min(roi.shape[:2]) > 31 else (min(roi.shape[:2]) // 2 * 2 + 1)
                    if k >= 3:
                        img_masked[yi1:yi2, xi1:xi2] = cv2.GaussianBlur(roi, (k, k), 0)
            kps_masked = orb.detect(img_masked, None)
            n_masked = len(kps_masked)

            frame_stats.append(dict(frame=frame_no, n_total=n_total, n_in_obj=n_in_obj,
                                     n_boxes=len(boxes), n_moving_boxes=len(moving_boxes),
                                     n_masked=n_masked))

    if frame_stats:
        tot = sum(f["n_total"] for f in frame_stats)
        in_obj = sum(f["n_in_obj"] for f in frame_stats)
        masked = sum(f["n_masked"] for f in frame_stats)
        obj_region_ratio = in_obj / tot if tot else 0.0
        all_dynamic_loss_ratio = 1.0 - (masked / tot if tot else 1.0)
        mean_kp = tot / len(frame_stats)
    else:
        obj_region_ratio = all_dynamic_loss_ratio = mean_kp = float("nan")

    result = dict(
        rec=os.path.basename(a.rec.rstrip("/")),
        n_gt_frames=len(gt_files),
        path_len_m=round(path_len, 1),
        duration_s=round(len(gt_files) / 20.0, 1),
        mean_speed_ms=round(mean_speed, 2),
        loop_dist_to_start_m=round(loop_dist, 1) if not math.isnan(loop_dist) else None,
        semi_static_object_count=len(semi_static_ids),
        transient_object_count=len(transient_ids),
        n_frames_sampled=len(frame_stats),
        mean_orb_keypoints=round(mean_kp, 1) if not math.isnan(mean_kp) else None,
        object_region_keypoint_ratio=round(obj_region_ratio, 3) if not math.isnan(obj_region_ratio) else None,
        all_dynamic_feature_loss_ratio=round(all_dynamic_loss_ratio, 3) if not math.isnan(all_dynamic_loss_ratio) else None,
        cv2_available=CV_OK,
    )
    json.dump(result, open(a.out, "w"), indent=1)
    print(f"[r8-audit] {result}")


if __name__ == "__main__":
    main()
