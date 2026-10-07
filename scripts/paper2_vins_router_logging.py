#!/usr/bin/env python3
"""Paper-2 Phase B — VINS router LOGGING ONLY (does not change VINS output).

Answers: does VINS already remove dynamic-object features (3-px cull), and is there any operable
feature mass left for TCSV-M to route? Correlates per-keyframe VINS feature pixels (perfeat log,
same 640x480 space as detections) with object bboxes + TCSV-M validity.

Inputs (all in the 640x480 image frame; bbox u,v are CENTERS):
  --rec        recording dir (gt/*.json gives frame<->ts_ns)
  --run        run name (e.g. dense_b1) to slice benchmark/scores
  --perfeat-on  perfeat CSV from a run with 3-px cull ON  (survivors)
  --perfeat-off perfeat CSV from a run with 3-px cull OFF (survivors incl. would-be-culled)
  --bench      paper2_raw_object_benchmark_all_with_vins.csv
  --scores     paper2_tcsv_vins_scores.csv (TCSV-M per-detection)
  --out        per-frame CSV out
Emits per-keyframe rows + prints a run summary.
"""
from __future__ import annotations
import sys, json, glob, argparse
from pathlib import Path
import numpy as np, pandas as pd

DYN_CLASSES = {"car", "truck", "person", "bus", "motorcycle", "bicycle"}
IMG_W, IMG_H = 640, 480


def frame_ts_map(rec):
    fr, ts = [], []
    for f in sorted(glob.glob(f"{rec}/gt/*.json")):
        d = json.load(open(f))
        fr.append(int(d["frame"])); ts.append(float(d["ts_ns"]) / 1e9)
    return np.array(fr), np.array(ts)


def load_perfeat(path):
    d = pd.read_csv(path, low_memory=False)
    # need timestamp, u_j, v_j
    keep = [c for c in ["timestamp", "feature_id", "u_j", "v_j"] if c in d.columns]
    d = d[keep].copy()
    for c in keep:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    return d.dropna(subset=["timestamp", "u_j", "v_j"])


def nearest_frame(ts_series, fr_arr, ts_arr):
    idx = np.searchsorted(ts_arr, ts_series)
    idx = np.clip(idx, 0, len(ts_arr) - 1)
    # refine to nearest of idx-1/idx
    left = np.clip(idx - 1, 0, len(ts_arr) - 1)
    pick_left = np.abs(ts_arr[left] - ts_series) < np.abs(ts_arr[idx] - ts_series)
    idx = np.where(pick_left, left, idx)
    return fr_arr[idx]


def bboxes_for_frame(bench_run, scores_run, frame):
    b = bench_run[bench_run["frame"] == frame]
    out = []
    for _, r in b.iterrows():
        w, h = float(r["bbox_w"]), float(r["bbox_h"])
        cx, cy = float(r["u"]), float(r["v"])
        x0, x1 = cx - w / 2, cx + w / 2
        y0, y1 = cy - h / 2, cy + h / 2
        cls = str(r["cls"])
        tid = r["track_id"]
        sc = scores_run[(scores_run["frame"] == frame) & (scores_run["track_id"] == tid)]
        if len(sc):
            pf = float(sc["P_full_state_valid"].iloc[0]); pol = str(sc["policy"].iloc[0]); fw = float(sc["feat_weight"].iloc[0])
        else:
            pf, pol, fw = np.nan, "unscored", np.nan
        out.append((x0, y0, x1, y1, cls, pf, pol, fw))
    return out


def count_in(feats, boxes, pred):
    if not boxes:
        return 0
    sel = [b for b in boxes if pred(b)]
    if not sel:
        return 0
    n = 0
    for (u, v) in feats:
        for (x0, y0, x1, y1, *_rest) in sel:
            if x0 <= u <= x1 and y0 <= v <= y1:
                n += 1; break
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rec", required=True); ap.add_argument("--run", required=True)
    ap.add_argument("--perfeat-on", required=True); ap.add_argument("--perfeat-off", default="")
    ap.add_argument("--bench", required=True); ap.add_argument("--scores", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    fr_arr, ts_arr = frame_ts_map(a.rec)
    bench = pd.read_csv(a.bench, low_memory=False)
    bench = bench[(bench["run"].astype(str) == a.run) & (bench["matched"] == 1)].copy()
    for c in ["frame", "u", "v", "bbox_w", "bbox_h", "track_id"]:
        bench[c] = pd.to_numeric(bench[c], errors="coerce")
    scores = pd.read_csv(a.scores, low_memory=False)
    scores = scores[scores["run"].astype(str) == a.run].copy()
    for c in ["frame", "track_id", "P_full_state_valid", "feat_weight"]:
        scores[c] = pd.to_numeric(scores[c], errors="coerce")

    pon = load_perfeat(a.perfeat_on)
    pon["frame"] = nearest_frame(pon["timestamp"].values, fr_arr, ts_arr)
    poff = load_perfeat(a.perfeat_off) if a.perfeat_off else None
    if poff is not None:
        poff["frame"] = nearest_frame(poff["timestamp"].values, fr_arr, ts_arr)

    def is_dyn(b): return b[4] in DYN_CLASSES
    def is_tcsv_low(b): return (b[6] in ("reject_high_dynamic", "suppress_full_state_low")) or (b[5] == b[5] and b[5] < 0.4)
    def is_any(b): return True

    rows = []
    for frame, g in pon.groupby("frame"):
        feats = list(zip(g["u_j"].values, g["v_j"].values))
        boxes = bboxes_for_frame(bench, scores, frame)
        n_obj = count_in(feats, boxes, is_any)
        n_dyn = count_in(feats, boxes, is_dyn)
        n_low = count_in(feats, boxes, is_tcsv_low)
        # feature action distribution by the bbox a feature falls in (first match)
        act = {"keep_static_reliable": 0, "keep_position_lower_weight": 0, "soft_uncertain": 0,
               "suppress_full_state_low": 0, "reject_high_dynamic": 0, "unscored": 0, "background": 0}
        for (u, v) in feats:
            hit = None
            for b in boxes:
                if b[0] <= u <= b[2] and b[1] <= v <= b[3]:
                    hit = b[6]; break
            act[hit if hit in act else "background" if hit is None else "unscored"] += 1
        n_off_obj = ""
        if poff is not None:
            goff = poff[poff["frame"] == frame]
            feats_off = list(zip(goff["u_j"].values, goff["v_j"].values))
            n_off_obj = count_in(feats_off, boxes, is_any)
        rows.append(dict(run=a.run, frame=int(frame), n_feat=len(feats), n_in_obj=n_obj,
                         n_in_dynamic=n_dyn, n_in_tcsv_low=n_low, n_obj_bbox=len(boxes),
                         n_feat_off=len(poff[poff["frame"] == frame]) if poff is not None else "",
                         n_in_obj_off=n_off_obj,
                         act_keep=act["keep_static_reliable"], act_lower=act["keep_position_lower_weight"],
                         act_soft=act["soft_uncertain"], act_suppress=act["suppress_full_state_low"],
                         act_reject=act["reject_high_dynamic"], act_background=act["background"]))
    out = pd.DataFrame(rows).sort_values("frame")
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(a.out, index=False)

    # summary
    tot_feat = out["n_feat"].sum(); tot_obj = out["n_in_obj"].sum()
    tot_low = out["n_in_tcsv_low"].sum()
    would_reject = out["act_reject"].sum() + out["act_suppress"].sum()
    culled = ""
    if poff is not None and out["n_in_obj_off"].replace("", np.nan).notna().any():
        oon = out["n_in_obj"].sum(); ooff = pd.to_numeric(out["n_in_obj_off"], errors="coerce").sum()
        culled = f"{ooff - oon:.0f} in-bbox feats removed by 3-px cull ({100*(ooff-oon)/max(ooff,1):.1f}% of in-bbox-off)"
    print(f"[phaseB] run={a.run} keyframes={len(out)}")
    print(f"  total surviving feats={tot_feat}  in-object-bbox={tot_obj} ({100*tot_obj/max(tot_feat,1):.1f}%)")
    print(f"  in-TCSV-low-bbox={tot_low} ({100*tot_low/max(tot_feat,1):.1f}% of feats)")
    print(f"  TCSV would drop (reject+suppress bbox feats)={would_reject} ({100*would_reject/max(tot_feat,1):.1f}% of feats)")
    print(f"  3-px cull on in-bbox: {culled if culled else 'n/a (no perfeat-off)'}")
    print(f"  wrote {a.out}")


if __name__ == "__main__":
    main()
