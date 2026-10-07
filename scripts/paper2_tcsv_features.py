#!/usr/bin/env python3
"""Paper-2 TCSV — Temporal-Consistency Selective Validator: feature engineering.

STANDALONE; no backend, no GT used in any feature (only the LABEL uses GT).
Formalizes temporal self-consistency of the RAW object-state estimate into physically
meaningful, runtime-observable residuals, on top of the existing geometry/temporal features.

New temporal-residual features (all per-track, runtime-observable):
  - cv_residual                  : constant-velocity prediction error ‖pos - (pos_{-1}+v_{-1}·dt)‖
  - acceleration_score           : |raw acceleration| (instantaneous)
  - jerk_score                   : |d(accel)/dt| (instantaneous)
  - velocity_direction_flip_count: # heading reversals (>90°) over last W transitions
  - bbox_depth_consistency       : frac of last-W pairs where sign(Δlog bbox_area)==sign(−Δdepth)
  - short_window_position_jitter : std of cv_residual over last W frames
  - short_window_velocity_jitter : std of raw_speed over last W frames

Window W controls the 4 windowed features (flip_count, bbox_depth_consistency, the two jitters);
cv_residual / acceleration_score / jerk_score are instantaneous. W=1 collapses the windowed ones
(tests whether temporal aggregation beyond the instantaneous residual helps).

Datasets: CARLA (paper2_raw_object_benchmark_all_with_vins.csv, dt=0.05), KITTI
(paper2_kitti_validity_dataset.csv, dt=0.10). Velocity criterion: ego-independent vel_err<=3 m/s.
Splits handled by the caller (CARLA by run, KITTI by sequence). NO frame random.
"""
from __future__ import annotations
import math
from pathlib import Path
import numpy as np, pandas as pd

WS = Path("/home/ivlab3/fwvio_estimator_ws_wheel")
POS_T, VEL_T = 3.0, 3.0

# GEO (5) + TEMP base (2) + TEMP residual (7) = 14
GEO_FEATS = ["range_m", "bearing_deg", "bbox_area", "depth_m", "det_conf"]
TEMP_BASE_FEATS = ["track_age", "raw_speed"]
TEMP_RESID_FEATS = ["cv_residual", "acceleration_score", "jerk_score",
                    "velocity_direction_flip_count", "bbox_depth_consistency",
                    "short_window_position_jitter", "short_window_velocity_jitter"]
TCSV_FEATS = GEO_FEATS + TEMP_BASE_FEATS + TEMP_RESID_FEATS
# the prior model's 10-feature set, for the "do the new residuals help?" ablation
OLD10_FEATS = ["range_m", "bearing_deg", "bbox_area", "depth_m", "track_age",
               "raw_speed", "raw_accel", "vel_smooth", "det_conf", "bearing_change"]


def _heading(vx, vz):
    return math.atan2(vz, vx)


def _angdiff(a, b):
    d = a - b
    while d > math.pi: d -= 2 * math.pi
    while d < -math.pi: d += 2 * math.pi
    return abs(d)


def compute_tcsv_features(df, posx, posz, dt, group, frame="frame", W=5):
    """Add raw temporal + TCSV residual features per track (sorted by frame).

    Only consecutive frames (Δframe==1) contribute to differential quantities, so gaps
    do not leak a spurious huge velocity. All quantities use RAW detections only.
    """
    df = df.sort_values(list(group) + [frame]).copy()
    n = len(df)
    # base temporal (mirror existing pipeline so OLD10 ablation is apples-to-apples)
    raw_speed = np.full(n, np.nan); raw_accel = np.full(n, np.nan)
    vel_smooth = np.full(n, np.nan); bearing_change = np.full(n, np.nan); track_age = np.zeros(n)
    # TCSV residuals
    cv_res = np.full(n, np.nan); accel_score = np.full(n, np.nan); jerk_score = np.full(n, np.nan)
    flip_cnt = np.zeros(n); bbox_depth_con = np.full(n, np.nan)
    pos_jit = np.full(n, np.nan); vel_jit = np.full(n, np.nan)

    X = df[posx].to_numpy(float); Z = df[posz].to_numpy(float); FR = df[frame].to_numpy()
    BR = df["bearing_deg"].to_numpy(float) if "bearing_deg" in df else np.zeros(n)
    AREA = df["bbox_area"].to_numpy(float) if "bbox_area" in df else np.full(n, np.nan)
    DEP = df["depth_m"].to_numpy(float) if "depth_m" in df else np.full(n, np.nan)
    gi = df.groupby(list(group), sort=False).indices

    for key, rows in gi.items():
        rows = list(rows)
        vel = [None] * len(rows)      # (vx,vz) per frame
        acc = [None] * len(rows)      # accel magnitude per frame
        head = [None] * len(rows)     # heading per frame
        cvr = [np.nan] * len(rows)    # cv residual per frame
        for i in range(len(rows)):
            r = rows[i]; track_age[r] = i
            if i >= 1 and (FR[rows[i]] - FR[rows[i-1]]) == 1:
                dx = X[r] - X[rows[i-1]]; dz = Z[r] - Z[rows[i-1]]
                vx, vz = dx / dt, dz / dt
                vel[i] = (vx, vz); head[i] = _heading(vx, vz)
                sp = math.hypot(vx, vz); raw_speed[r] = sp
                bearing_change[r] = BR[r] - BR[rows[i-1]]
                # constant-velocity residual: predict pos_i from pos_{i-1} + v_{i-1}*dt
                if i >= 2 and vel[i-1] is not None:
                    px = X[rows[i-1]] + vel[i-1][0] * dt
                    pz = Z[rows[i-1]] + vel[i-1][1] * dt
                    cvr[i] = math.hypot(X[r] - px, Z[r] - pz)
                    cv_res[r] = cvr[i]
                    ax = (vx - vel[i-1][0]) / dt; az = (vz - vel[i-1][1]) / dt
                    am = math.hypot(ax, az); acc[i] = am
                    raw_accel[r] = am; accel_score[r] = am
                    if i >= 3 and acc[i-1] is not None:
                        jerk_score[r] = abs(am - acc[i-1]) / dt
            # ---- windowed features over last W transitions / frames ----
            lo = max(0, i - W + 1)
            # vel_smooth (legacy, std of last up-to-4 raw speeds)
            sps = [raw_speed[rows[j]] for j in range(max(0, i-3), i+1) if raw_speed[rows[j]] == raw_speed[rows[j]]]
            if len(sps) >= 2: vel_smooth[r] = float(np.std(sps))
            # short-window velocity jitter (window W)
            wsp = [raw_speed[rows[j]] for j in range(lo, i+1) if raw_speed[rows[j]] == raw_speed[rows[j]]]
            if len(wsp) >= 2: vel_jit[r] = float(np.std(wsp))
            # short-window position jitter (std of cv residual over window W)
            wcv = [cvr[j] for j in range(lo, i+1) if cvr[j] == cvr[j]]
            if len(wcv) >= 2: pos_jit[r] = float(np.std(wcv))
            elif len(wcv) == 1: pos_jit[r] = 0.0
            # velocity direction flips: # consecutive heading pairs with >90° reversal in window
            hw = [head[j] for j in range(lo, i+1) if head[j] is not None]
            fc = 0
            for j in range(1, len(hw)):
                if _angdiff(hw[j], hw[j-1]) > math.pi / 2: fc += 1
            flip_cnt[r] = fc
            # bbox-depth consistency: sign(Δlog area)==sign(−Δdepth) frac over window
            agree = []
            for j in range(lo + 1, i + 1):
                a0, a1 = AREA[rows[j-1]], AREA[rows[j]]
                d0, d1 = DEP[rows[j-1]], DEP[rows[j]]
                if not (np.isfinite(a0) and np.isfinite(a1) and a0 > 0 and a1 > 0
                        and np.isfinite(d0) and np.isfinite(d1)):
                    continue
                dla = math.log(a1) - math.log(a0); dd = d1 - d0
                if abs(dla) < 1e-6 and abs(dd) < 1e-6:
                    continue
                agree.append(1.0 if (np.sign(dla) == np.sign(-dd)) else 0.0)
            if agree: bbox_depth_con[r] = float(np.mean(agree))

    df["raw_speed"] = raw_speed; df["raw_accel"] = raw_accel; df["vel_smooth"] = vel_smooth
    df["track_age"] = track_age
    if "bearing_change" not in df.columns: df["bearing_change"] = bearing_change
    df["cv_residual"] = cv_res; df["acceleration_score"] = accel_score; df["jerk_score"] = jerk_score
    df["velocity_direction_flip_count"] = flip_cnt; df["bbox_depth_consistency"] = bbox_depth_con
    df["short_window_position_jitter"] = pos_jit; df["short_window_velocity_jitter"] = vel_jit
    return df


def load_carla(W=5):
    d = pd.read_csv(WS / "paper2_raw_object_benchmark_all_with_vins.csv", low_memory=False)
    d = d[d["matched"] == 1].copy()
    for c in ["pos_err_m", "raw_speed_ms", "gt_speed_ms", "dir_err_deg", "body_fwd", "body_lat",
              "range_m", "bearing_deg", "bbox_area", "depth_m", "frame", "track_id", "conf"]:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d[d["pos_err_m"].notna() & d["body_fwd"].notna()].copy()
    d["det_conf"] = d["conf"]
    rs, gs, dr = d["raw_speed_ms"], d["gt_speed_ms"], np.radians(d["dir_err_deg"])
    vel_err = np.sqrt(np.clip(rs**2 + gs**2 - 2*rs*gs*np.cos(dr), 0, None))
    d["has_v"] = (d["raw_speed_ms"].notna() & d["gt_speed_ms"].notna() & d["dir_err_deg"].notna()).astype(int)
    d["position_valid"] = (d["pos_err_m"] <= POS_T).astype(int)
    d["velocity_valid"] = np.where(d["has_v"] == 1, (vel_err <= VEL_T).astype(int), 0)
    d = compute_tcsv_features(d, "body_lat", "body_fwd", 0.05, group=("town", "run", "track_id"), W=W)
    d["split_key"] = d["town"].astype(str) + "@" + d["run"].astype(str)
    d["dataset"] = "carla"
    return d


def load_kitti(W=5):
    d = pd.read_csv(WS / "paper2_kitti_validity_dataset.csv", low_memory=False)
    for c in ["pos_err_m", "vel_err_ms", "range_m", "bearing_deg", "bbox_area", "depth_m", "frame",
              "tid", "det_conf", "raw_x", "raw_z"]:
        if c in d: d[c] = pd.to_numeric(d[c], errors="coerce")
    d["track_id"] = d["tid"]
    d["has_v"] = d["vel_err_ms"].notna().astype(int)
    d["position_valid"] = (d["pos_err_m"] <= POS_T).astype(int)
    d["velocity_valid"] = np.where(d["has_v"] == 1, (d["vel_err_ms"] <= VEL_T).astype(int), 0)
    d = compute_tcsv_features(d, "raw_x", "raw_z", 0.10, group=("seq", "track_id"), W=W)
    d["split_key"] = "kitti@" + d["seq"].astype(str)
    d["dataset"] = "kitti"
    return d


def load_nuscenes(W=5):
    """nuScenes CAM_FRONT validity dataset (YOLO+lidar raw estimate). dt=0.5 (2 Hz keyframes),
    group by scene. Same schema/labels as KITTI. Only GT-matched detections."""
    d = pd.read_csv(WS / "nuscenes" / "paper2_nuscenes_validity_dataset.csv", low_memory=False)
    for c in ["pos_err_m", "vel_err_ms", "range_m", "bearing_deg", "bbox_area", "depth_m", "frame",
              "det_conf", "raw_x", "raw_z", "matched"]:
        if c in d: d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d[d["matched"] == 1].copy()
    d["track_id"] = d["tid"].astype(str)   # GT instance token (string) — grouping only
    d["has_v"] = d["vel_err_ms"].notna().astype(int)
    d["position_valid"] = (d["pos_err_m"] <= POS_T).astype(int)
    d["velocity_valid"] = np.where(d["has_v"] == 1, (d["vel_err_ms"] <= VEL_T).astype(int), 0)
    d = compute_tcsv_features(d, "raw_x", "raw_z", 0.50, group=("seq", "track_id"), W=W)
    d["split_key"] = "nusc@" + d["seq"].astype(str)
    d["dataset"] = "nuscenes"
    return d


def prep(df, feats):
    X = df[feats].astype(float)
    X = X.fillna(X.median(numeric_only=True)).fillna(0.0)
    return X.values


if __name__ == "__main__":
    c = load_carla(); k = load_kitti()
    print(f"CARLA n={len(c)} vel_valid={c.velocity_valid.mean():.3f}")
    print(f"KITTI n={len(k)} vel_valid={k.velocity_valid.mean():.3f}")
    print("TCSV feats:", TCSV_FEATS)
    print(c[TEMP_RESID_FEATS].describe().round(3).T[["mean", "std", "min", "max"]])
