#!/usr/bin/env python3
"""Paper-2 G0 — align VINS quality features to object observations by nearest timestamp.

Change: paper2-noue-g0-data-grounding (Workstream D).

What it does (STANDALONE, stdlib-only, no estimator change, no training):
  Given (1) an object-observation CSV with a timestamp column (seconds), and
        (2) a VINS `reliability_features_vins.csv`,
  emit one joined row per object observation, attaching the NOUE-v0 conditioning features
  from the reliability row nearest in time (gated by --max-dt).

v0 conditioning features are taken from EXISTING reliability columns only (G0 does NOT add
estimator logging). See PAPER2_NOUE_FEATURE_SCHEMA_V0.md.

Usage:
  python scripts/paper2_align_vins_quality_to_objects.py \
     --objects <obj.csv> --ts-col ts_s \
     --reliability /path/reliability_features_vins.csv \
     --out paper2_object_vins_quality_join_demo.csv [--max-dt 0.2]
"""
from __future__ import annotations
import argparse, csv, bisect, sys
from pathlib import Path

# v0 conditioning features: name in reliability CSV  (good_depth_ratio is derived below)
V0_COLS = [
    "timestamp",
    "tracked_feature_count_raw", "tracked_feature_count_mgr",
    "outlier_ratio_last", "coverage_8x8", "avg_track_length",
    "solver_time_ms_last", "failure_detected_last", "failure_reason_proxy",
    "gyr_z_mean", "gyr_z_std", "gyro_vins_so3_diff_deg",
    "vel_norm", "ba_norm", "bg_norm",
    "depth_mean", "depth_std", "good_depth_count", "bad_depth_count",
]


def load_reliability(path):
    with open(path, newline="") as f:
        r = csv.DictReader(f)
        rows = list(r)
    missing = [c for c in V0_COLS if c not in r.fieldnames]
    if missing:
        print(f"[align] FATAL: reliability CSV missing v0 cols: {missing}", file=sys.stderr); sys.exit(2)
    rows.sort(key=lambda d: float(d["timestamp"]))
    ts = [float(d["timestamp"]) for d in rows]
    return rows, ts


def nearest_idx(ts_sorted, t):
    i = bisect.bisect_left(ts_sorted, t)
    if i == 0:
        return 0
    if i >= len(ts_sorted):
        return len(ts_sorted) - 1
    return i if abs(ts_sorted[i] - t) < abs(ts_sorted[i - 1] - t) else i - 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--objects", required=True)
    ap.add_argument("--ts-col", default="ts_s", help="timestamp column (seconds) in the objects CSV")
    ap.add_argument("--reliability", required=True)
    ap.add_argument("--out", default="paper2_object_vins_quality_join_demo.csv")
    ap.add_argument("--max-dt", type=float, default=0.2, help="max |dt| seconds to accept a match")
    args = ap.parse_args()

    rel_rows, rel_ts = load_reliability(args.reliability)
    print(f"[align] reliability rows={len(rel_rows)} ts=[{rel_ts[0]:.3f}, {rel_ts[-1]:.3f}]s")

    with open(args.objects, newline="") as f:
        obj_rows = list(csv.DictReader(f))
    if not obj_rows or args.ts_col not in obj_rows[0]:
        print(f"[align] FATAL: objects CSV empty or missing ts col '{args.ts_col}'", file=sys.stderr); sys.exit(2)

    out_rows = []; matched = 0
    for o in obj_rows:
        t = float(o[args.ts_col])
        j = nearest_idx(rel_ts, t); dt = rel_ts[j] - t
        row = dict(o)
        row["vins_ts"] = f"{rel_ts[j]:.6f}"; row["vins_dt_s"] = f"{dt:.6f}"
        ok = abs(dt) <= args.max_dt
        row["vins_match_ok"] = int(ok)
        rr = rel_rows[j]
        for c in V0_COLS:
            row[f"vins_{c}"] = rr[c] if ok else ""
        if ok:
            g, b = float(rr["good_depth_count"]), float(rr["bad_depth_count"])
            row["vins_good_depth_ratio"] = f"{g/(g+b):.4f}" if (g + b) > 0 else ""
            matched += 1
        else:
            row["vins_good_depth_ratio"] = ""
        out_rows.append(row)

    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys())); w.writeheader(); w.writerows(out_rows)
    print(f"[align] objects={len(obj_rows)} matched(|dt|<= {args.max_dt}s)={matched} -> {args.out}")


if __name__ == "__main__":
    main()
