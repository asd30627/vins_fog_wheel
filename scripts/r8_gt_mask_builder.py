#!/usr/bin/env python3
"""R8-3 — build STEREO-consistent GT-based masks for a CARLA recording (no detector, no backend
change). Two variants, matching the R8-3 diagnostic plan:

  class_prior : mask ALL GT object 3D-bbox projections (static + moving) in every frame — proxy for a
                 naive "vehicle-class" detector mask (all_dynamic in the earlier VINS/ORB terminology).
  oracle_cull : mask ONLY objects with GT speed >= 0.5 m/s (transient/moving) — leaves semi-static
                 (parked/candidate-anchor) object regions UNMASKED. This operationalizes "oracle
                 candidate-anchor recovery" as an input-masking headroom test: does keeping (not
                 masking) the semi-static regions, while removing the genuinely transient ones, do
                 better than masking everything or masking nothing?

Right-image bbox derived via depth-based disparity (disp = fx*baseline/depth), matching the earlier
stereo-mask methodology (phase6_make_stereo_mask.py) but built directly from GT depth instead of a
per-detection CSV (this recording has no detector run on it, only GT).

Output format: {frame: {"L": [[x1,y1,x2,y2],...], "R": [[x1,y1,x2,y2],...]}} — same as
paper2_carla_stereo_player_masked.py --stereo-mask-json expects.
"""
import argparse, glob, json, math, os
import numpy as np

FX = FY = 320.0
CX = 320.0
CY = 240.0
WIDTH, HEIGHT = 640, 480
MOVING_SPEED_THR = 0.5


def deg2rad(d):
    return d * math.pi / 180.0


def rot_matrix_ue4(roll, pitch, yaw):
    r, p, y = deg2rad(roll), deg2rad(pitch), deg2rad(yaw)
    cy, sy = math.cos(y), math.sin(y)
    cp, sp = math.cos(p), math.sin(p)
    cr, sr = math.cos(r), math.sin(r)
    Rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
    Ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]])
    Rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]])
    return Rz @ Ry @ Rx


def project_point(world_xyz, ego_pos, ego_rot, cam_offset_local):
    R_v = rot_matrix_ue4(ego_rot[0], ego_rot[1], ego_rot[2])
    cam_world = np.array(ego_pos) + R_v @ np.array(cam_offset_local)
    rel = np.array(world_xyz) - cam_world
    p_cam_ue4 = R_v.T @ rel
    x_std, y_std, z_std = p_cam_ue4[1], -p_cam_ue4[2], p_cam_ue4[0]
    if z_std <= 0.3:
        return None
    u = FX * x_std / z_std + CX
    v = FY * y_std / z_std + CY
    return u, v, z_std


def object_bbox_and_depth(inst, ego_pos, ego_rot, cam_offset_local):
    cx, cy, cz = inst["x"], inst["y"], inst["z"]
    ex, ey, ez = inst.get("ext", [1.0, 1.0, 1.0])
    yaw = inst.get("yaw", 0.0)
    Ro = rot_matrix_ue4(0, 0, yaw)
    pts = []
    depths = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                local = np.array([sx * ex, sy * ey, sz * ez])
                world = np.array([cx, cy, cz]) + Ro @ local
                r = project_point(world, ego_pos, ego_rot, cam_offset_local)
                if r is not None:
                    pts.append((r[0], r[1])); depths.append(r[2])
    if len(pts) < 4:
        return None
    us = [p[0] for p in pts]; vs = [p[1] for p in pts]
    x1, x2 = max(0, min(us)), min(WIDTH, max(us))
    y1, y2 = max(0, min(vs)), min(HEIGHT, max(vs))
    if x2 <= x1 or y2 <= y1:
        return None
    depth = float(np.median(depths))
    return (x1, y1, x2, y2), depth


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rec", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--pad", type=int, default=4)
    a = ap.parse_args()

    meta_path = os.path.join(a.rec, "recording_meta.json")
    baseline_m = 0.5
    if os.path.exists(meta_path):
        try:
            baseline_m = json.load(open(meta_path)).get("baseline_m", 0.5)
        except Exception:
            pass
    cam0_offset = (1.5, -baseline_m / 2.0, 1.6)

    gt_files = sorted(glob.glob(os.path.join(a.rec, "gt", "*.json")))
    class_prior = {}
    oracle_cull = {}
    n_frames_obj = 0
    n_boxes_cp = n_boxes_oc = 0

    for f in gt_files:
        d = json.load(open(f))
        frame_no = d["frame"]
        ego = d["ego_pose"]
        ego_pos = (ego["x"], ego["y"], ego["z"])
        ego_rot = (ego.get("roll", 0.0), ego.get("pitch", 0.0), ego["yaw"])
        L_all, R_all = [], []
        L_moving, R_moving = [], []
        for oid, inst in d.get("per_instance", {}).items():
            res = object_bbox_and_depth(inst, ego_pos, ego_rot, cam0_offset)
            if res is None:
                continue
            (x1, y1, x2, y2), depth = res
            disp = FX * baseline_m / max(depth, 0.5)
            rx1 = max(0.0, x1 - disp - a.pad); rx2 = min(float(WIDTH), x2 - disp + a.pad)
            Lbox = [round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1)]
            L_all.append(Lbox)
            if rx2 > rx1:
                R_all.append([round(rx1, 1), round(y1, 1), round(rx2, 1), round(y2, 1)])
            if inst.get("speed", 0.0) >= MOVING_SPEED_THR:
                L_moving.append(Lbox)
                if rx2 > rx1:
                    R_moving.append([round(rx1, 1), round(y1, 1), round(rx2, 1), round(y2, 1)])
        if L_all:
            n_frames_obj += 1
        class_prior[str(frame_no)] = {"L": L_all, "R": R_all}
        oracle_cull[str(frame_no)] = {"L": L_moving, "R": R_moving}
        n_boxes_cp += len(L_all); n_boxes_oc += len(L_moving)

    os.makedirs(a.out_dir, exist_ok=True)
    rec_name = os.path.basename(a.rec.rstrip("/"))
    p_cp = os.path.join(a.out_dir, f"stereo_mask_{rec_name}__class_prior.json")
    p_oc = os.path.join(a.out_dir, f"stereo_mask_{rec_name}__oracle_cull.json")
    json.dump(class_prior, open(p_cp, "w"))
    json.dump(oracle_cull, open(p_oc, "w"))
    print(f"[r8-mask] class_prior: {n_frames_obj} frames w/ objects, {n_boxes_cp} boxes -> {p_cp}")
    print(f"[r8-mask] oracle_cull: {n_boxes_oc} boxes (moving only) -> {p_oc}")


if __name__ == "__main__":
    main()
