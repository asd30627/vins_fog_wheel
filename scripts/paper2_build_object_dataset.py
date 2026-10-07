#!/usr/bin/env python3
"""Paper-2 G2 — build the NOUE object dataset (features + labels) from per-detection benchmark CSV.

Change: paper2-viwo-conditioned-noue-v4 (Phase G2). STANDALONE; no training here.

Input : paper2_raw_object_benchmark_all.csv (per-detection rich rows, GT-matched).
Output: paper2_object_dataset_v1.parquet + .csv, with a group-aware train/val/test split column.

Features (object-only = the "NOUE without VINS quality" input set; VINS-quality cols are BLOCKED — no
reliability_features_vins.csv exists for these recordings without a VINS replay; see report).
Labels : pos/speed/dir error (reg) + high_pos_error / high_speed_error / invalid_velocity /
         observability / utility (binary).
"""
from __future__ import annotations
import argparse
from pathlib import Path
import numpy as np, pandas as pd

WS = Path("/home/ivlab3/fwvio_estimator_ws_wheel")
NUM_FEATS = ["conf", "bbox_w", "bbox_h", "bbox_aspect", "bbox_area", "area_frac",
             "disp_med", "disp_std", "depth_m", "range_m", "bearing_deg", "bearing_change_deg",
             "track_age", "raw_speed_ms", "body_fwd", "body_lat"]
CAT_FEATS = ["cls", "density", "town"]
POS_HI, SPD_HI, INVALID_SPD, INVALID_DIR = 3.0, 3.0, 5.0, 45.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-csv", default=str(WS / "paper2_raw_object_benchmark_all.csv"))
    ap.add_argument("--out", default=str(WS / "paper2_object_dataset_v1"))
    ap.add_argument("--seed", type=int, default=1234)
    args = ap.parse_args()

    df = pd.read_csv(args.in_csv, low_memory=False)
    print(f"[ds] loaded {len(df)} detections")
    df = df[df["matched"] == 1].copy()
    print(f"[ds] matched-only: {len(df)}")
    # numeric coercion
    for c in NUM_FEATS + ["pos_err_m", "speed_err_ms", "dir_err_deg", "gt_range_m", "gt_speed_ms"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df[df["pos_err_m"].notna() & df["depth_m"].notna()].copy()
    print(f"[ds] with pos_err + depth: {len(df)}")

    # labels
    df["high_pos_error"] = (df["pos_err_m"] > POS_HI).astype(int)
    df["high_speed_error"] = (df["speed_err_ms"] > SPD_HI).astype(int)
    df["invalid_velocity"] = ((df["speed_err_ms"] > INVALID_SPD) | (df["dir_err_deg"] > INVALID_DIR)).astype(int)
    # observability: error small relative to range (scales with distance)
    df["observability"] = (df["pos_err_m"] <= (0.10 * df["gt_range_m"] + 1.0)).astype(int)
    # utility: position usable for planner AND velocity not invalid
    df["utility"] = ((df["pos_err_m"] <= POS_HI) & (df["invalid_velocity"] == 0)).astype(int)

    # group-aware split by run (generalization to unseen runs); keep town for per-town eval
    rng = np.random.RandomState(args.seed)
    runs = df["run"].astype(str) + "@" + df["town"].astype(str)
    uniq = sorted(runs.unique())
    rng.shuffle(uniq)
    n = len(uniq)
    n_test = max(1, n // 5); n_val = max(1, n // 5)
    test_g = set(uniq[:n_test]); val_g = set(uniq[n_test:n_test + n_val])
    grp = runs.values
    split = np.where([g in test_g for g in grp], "test",
            np.where([g in val_g for g in grp], "val", "train"))
    df["split"] = split

    # VINS quality features: BLOCKED (no reliability_features_vins.csv for these recordings)
    df["vins_quality_available"] = 0

    keep = ["town", "density", "run", "frame", "track_id", "cls", "dist_bin"] + NUM_FEATS + \
           ["gt_range_m", "gt_speed_ms", "pos_err_m", "speed_err_ms", "dir_err_deg",
            "high_pos_error", "high_speed_error", "invalid_velocity", "observability", "utility",
            "vins_quality_available", "split"]
    out = df[keep].copy()
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(args.out + ".parquet", index=False)
    out.to_csv(args.out + ".csv", index=False)
    print(f"[ds] wrote {args.out}.parquet/.csv  n={len(out)}")
    print("[ds] split counts:", out["split"].value_counts().to_dict())
    print("[ds] dist_bin:", out["dist_bin"].value_counts().to_dict())
    print("[ds] density:", out["density"].value_counts().to_dict())
    print("[ds] label rates: high_pos=%.3f high_spd=%.3f invalid_vel=%.3f obs=%.3f util=%.3f" % (
        out.high_pos_error.mean(), out.high_speed_error.mean(), out.invalid_velocity.mean(),
        out.observability.mean(), out.utility.mean()))
    print("[ds] pos_err by bin (median):",
          out.groupby("dist_bin")["pos_err_m"].median().round(2).to_dict())


if __name__ == "__main__":
    main()
