#!/usr/bin/env python3
"""Paper-2 A2 — join VINS reliability features to per-detection object rows by nearest timestamp.

Change: paper2-viwo-conditioned-noue-v4 (Phase G2 / A2). STANDALONE.

Input : paper2_raw_object_benchmark_all.csv (per-detection; has town/density/run/frame + obj feats + labels)
        + per-recording reliability_features_vins.csv (from VINS replay).
Output: paper2_raw_object_benchmark_all_with_vins.csv (+ VINS quality cols + vins_match_ok),
        PAPER2_OBJECT_VINS_JOIN_REPORT.md.

Alignment: object detection at frame fi -> ts = gt[fi].ts_ns/1e9 -> nearest reliability row timestamp
(gate --max-dt). If reliability csv columns and object ts don't overlap -> reported, not force-joined.
"""
from __future__ import annotations
import argparse, csv, json, bisect, glob
from pathlib import Path
import numpy as np, pandas as pd

WS = Path("/home/ivlab3/fwvio_estimator_ws_wheel")
DATAROOT = Path("/mnt/sata4t/datasets/carla_fwvio")
VINSROOT = Path("/mnt/sata4t/ivlab3_data/fwvio/results/paper2_vins")
# reliability col -> output col (deployable quality features)
VINS_COLS = {
    "tracked_feature_count_mgr": "vins_feat_count", "tracked_feature_count_raw": "vins_feat_raw",
    "outlier_ratio_last": "vins_outlier_ratio", "inlier_count_last": "vins_inlier",
    "coverage_8x8": "vins_coverage8", "feature_entropy_8x8": "vins_entropy8",
    "avg_track_length": "vins_track_len", "solver_time_ms_last": "vins_solver_ms",
    "gyro_vins_so3_diff_deg": "vins_gyro_vins_diff", "depth_mean": "vins_depth_mean",
    "depth_std": "vins_depth_std", "good_depth_count": "vins_good_depth",
    "bad_depth_count": "vins_bad_depth", "vel_norm": "vins_vel_norm",
    "ba_norm": "vins_ba_norm", "bg_norm": "vins_bg_norm", "gyr_z_std": "vins_gyr_z_std",
    "failure_detected_last": "vins_failure",
}


def reliability_tag(town, run):
    return f"rep_{run}_{town}"


def gt_ts_map(rec_dir):
    m = {}
    for f in glob.glob(f"{rec_dir}/gt/*.json"):
        fi = int(Path(f).stem)
        try:
            m[fi] = json.load(open(f))["ts_ns"] / 1e9
        except Exception:
            pass
    return m


def load_reliability(tag):
    p = VINSROOT / tag / "reliability_features_vins.csv"
    if not p.exists():
        return None, None
    rows = list(csv.DictReader(open(p)))
    if not rows:
        return None, None
    rows.sort(key=lambda r: float(r["timestamp"]))
    ts = [float(r["timestamp"]) for r in rows]
    return rows, ts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-csv", default=str(WS / "paper2_raw_object_benchmark_all.csv"))
    ap.add_argument("--out-csv", default=str(WS / "paper2_raw_object_benchmark_all_with_vins.csv"))
    ap.add_argument("--max-dt", type=float, default=0.15)
    args = ap.parse_args()

    df = pd.read_csv(args.in_csv, low_memory=False)
    print(f"[join] {len(df)} detection rows")
    groups = df.groupby(["town", "run"])
    rel_cache = {}; ts_cache = {}; gtts_cache = {}
    per_rec_stats = []
    out_cols = {v: [] for v in VINS_COLS.values()}
    match_ok = []

    for (town, run), idx in groups.groups.items():
        tag = reliability_tag(town, run)
        if tag not in rel_cache:
            rel_cache[tag], ts_cache[tag] = load_reliability(tag)
        rrows, rts = rel_cache[tag], ts_cache[tag]
        rec_dir = DATAROOT / f"{town}__dynamic_v3__run{run}"
        if rec_dir not in gtts_cache:
            gtts_cache[rec_dir] = gt_ts_map(rec_dir)
        gtm = gtts_cache[rec_dir]
        sub = df.loc[idx]
        nmatch = 0
        for ridx, row in sub.iterrows():
            fi = int(row["frame"]); ts = gtm.get(fi)
            matched = 0
            vals = {v: "" for v in VINS_COLS.values()}
            if rrows is not None and ts is not None:
                j = bisect.bisect_left(rts, ts)
                cand = [k for k in (j - 1, j) if 0 <= k < len(rts)]
                if cand:
                    k = min(cand, key=lambda k: abs(rts[k] - ts))
                    if abs(rts[k] - ts) <= args.max_dt:
                        matched = 1; nmatch += 1
                        for c, ov in VINS_COLS.items():
                            vals[ov] = rrows[k].get(c, "")
            for v in VINS_COLS.values():
                out_cols[v].append(vals[v])
            match_ok.append(matched)
        per_rec_stats.append((tag, len(sub), nmatch, rrows is not None and len(rrows) or 0))

    # reorder out_cols/match_ok to df row order (groupby preserves index; we appended per-group in index order)
    # rebuild via a position map
    order = []
    for (town, run), idx in groups.groups.items():
        order.extend(list(idx))
    pos = np.argsort(order)  # map appended-order -> original df order
    for v in VINS_COLS.values():
        arr = np.array(out_cols[v], dtype=object)
        df[v] = arr[pos]
    df["vins_match_ok"] = np.array(match_ok, dtype=int)[pos]

    df.to_csv(args.out_csv, index=False)
    total_match = int(df["vins_match_ok"].sum())
    print(f"[join] wrote {args.out_csv} ; vins_match_ok {total_match}/{len(df)} ({total_match/len(df):.3f})")

    # report
    L = ["# PAPER2_OBJECT_VINS_JOIN_REPORT", "",
         f"> Join VINS reliability features to {len(df)} object detections by nearest timestamp (max_dt {args.max_dt}s).",
         f"> Overall VINS match rate: **{total_match}/{len(df)} ({total_match/len(df):.3f})**.", "",
         "## Per-recording match", "| reliability_tag | obj_det | matched | rel_rows |", "|---|---|---|---|"]
    for tag, nobj, nm, nrel in sorted(per_rec_stats):
        L.append(f"| {tag} | {nobj} | {nm} | {nrel} |")
    nomatch = [t for t, no, nm, nr in per_rec_stats if nm == 0]
    L += ["", "## Notes",
          f"- recordings with 0 VINS match: {nomatch or 'none'} (VINS replay missing/failed or ts disjoint).",
          "- VINS quality cols joined: " + ", ".join(VINS_COLS.values()),
          "- matched rows carry deployable VINS localization-quality features for the A2 conditioning test."]
    (WS / "PAPER2_OBJECT_VINS_JOIN_REPORT.md").write_text("\n".join(L) + "\n")
    print("[join] wrote PAPER2_OBJECT_VINS_JOIN_REPORT.md")


if __name__ == "__main__":
    main()
