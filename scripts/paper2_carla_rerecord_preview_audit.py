#!/usr/bin/env python3
"""Paper-2 Phase R2 — preview quality audit + gate for a re-recorded (dynamic_v3fix) run.

Reads recording_meta.json (spawn stats), gt/*.json (object range/FOV) and the per-det CSV (YOLO
detections + matched), computes the preview gate metrics and classifies PASS_PREVIEW / LOW_YIELD_PREVIEW
/ FAIL_PREVIEW. Appends one row to the preview CSV.

usage: paper2_carla_rerecord_preview_audit.py --rec <REC_DIR> --perdet <perdet.csv> --out-csv <csv>
"""
from __future__ import annotations
import json, glob, math, argparse
from pathlib import Path
import numpy as np, pandas as pd

EGO_MIN_RANGE = 2.0
FOV_DEG = 90.0  # cam0 fov in config


def gt_stats(rec):
    # per_instance x,y are EGO-RELATIVE (body frame): x=forward, y=lateral. range=hypot(x,y),
    # bearing=atan2(y,x) off the forward axis. Drive frames only would need the release_frame; we use all.
    gts = sorted(glob.glob(f"{rec}/gt/*.json"))
    rngs, infov, infov50 = [], 0, 0
    nfr = 0
    for f in gts:
        d = json.load(open(f))
        ins = d.get("per_instance", {})
        nfr += 1; nobj = 0
        for k, v in ins.items():
            x = v.get("x"); y = v.get("y")
            if x is None or y is None:
                continue
            r = math.hypot(x, y)
            if r < EGO_MIN_RANGE:
                continue
            rngs.append(r)
            b = abs(math.degrees(math.atan2(y, x)))   # bearing off forward axis
            if x > 0 and b <= FOV_DEG/2:               # in front + within FOV cone
                infov += 1; nobj += 1
                if r < 50: infov50 += 1
    rngs = np.array(rngs) if rngs else np.array([np.nan])
    return dict(frames=nfr, gt_obj_per_f=round(len(rngs)/max(nfr,1),1),
                rng_med=round(float(np.nanmedian(rngs)),1), rng_p10=round(float(np.nanpercentile(rngs,10)),1),
                rng_p90=round(float(np.nanpercentile(rngs,90)),1),
                pct_lt30=round(100*np.mean(rngs<30),1), pct_lt50=round(100*np.mean(rngs<50),1),
                pct_gt150=round(100*np.mean(rngs>150),1),
                infov_per_f=round(infov/max(nfr,1),2), infov_lt50_per_f=round(infov50/max(nfr,1),2))


def det_stats(perdet, W=640, H=480):
    if not Path(perdet).exists():
        return dict(det_total=0, matched=0, matched_lt50=0, det_per_f=0, bbox_med=float("nan"),
                    fullframe_ratio=float("nan"), tracks=0)
    d = pd.read_csv(perdet, low_memory=False)
    for c in ["bbox_area","range_m","matched","frame","track_id","depth_m"]:
        if c in d: d[c] = pd.to_numeric(d[c], errors="coerce")
    det = len(d); m = d[d.get("matched",0)==1] if "matched" in d else d.iloc[0:0]
    rng = m["range_m"] if "range_m" in m else pd.Series(dtype=float)
    area = float(W*H)
    ff = (d["bbox_area"]/area > 0.3).mean() if "bbox_area" in d and det else float("nan")
    nfr = d["frame"].nunique() if "frame" in d else 1
    return dict(det_total=det, matched=len(m),
                matched_lt50=int((rng<50).sum()) if len(rng) else 0,
                det_per_f=round(det/max(nfr,1),2),
                bbox_med=round(float(d["bbox_area"].median()),1) if "bbox_area" in d and det else float("nan"),
                fullframe_ratio=round(float(ff),3) if ff==ff else float("nan"),
                tracks=int(d["track_id"].nunique()) if "track_id" in d else 0)


def classify(m):
    # Gate on what YOLO actually DETECTS near (not all GT instances — hybrid global-coverage NPCs are
    # intentionally far and would otherwise inflate pct_gt150). Key signal = matched + matched_lt50.
    if m["det_total"] == 0 or m["matched"] == 0:
        return "FAIL_PREVIEW", "det=0 or matched=0"
    if m.get("fullframe_ratio", 0) and m["fullframe_ratio"] > 0.05:
        return "FAIL_PREVIEW", f"glued-face: full-frame bbox ratio {m['fullframe_ratio']}"
    if m["matched_lt50"] < 20:
        return "FAIL_PREVIEW", f"too few near detections (matched<50m={m['matched_lt50']})"
    # Gate on the DETECTED near-object rate (det_per_f = YOLO in-FOV detections/frame — the operational
    # visibility that drives VINS features). GT infov_lt50 is unreliable with hybrid far global NPCs.
    passc = (m["det_total"] > 50 and m["matched"] > 100 and m["matched_lt50"] > 20 and
             m["det_per_f"] > 0.5 and m["spawn_ratio"] > 0.6 and
             (m["fullframe_ratio"] != m["fullframe_ratio"] or m["fullframe_ratio"] < 0.05))
    if passc:
        return "PASS_PREVIEW", f"near-object yield ok (matched<50m={m['matched_lt50']})"
    return "LOW_YIELD_PREVIEW", f"usable but below PASS (matched={m['matched']}, matched<50m={m['matched_lt50']})"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rec", required=True); ap.add_argument("--perdet", required=True)
    ap.add_argument("--out-csv", required=True); ap.add_argument("--setting", default="")
    a = ap.parse_args()
    rec = a.rec
    meta = json.load(open(f"{rec}/recording_meta.json"))
    g = gt_stats(rec); d = det_stats(a.perdet)
    sr = meta["spawned_npc"]/max(meta["requested_npc"],1)
    m = dict(run=Path(rec).name, setting=a.setting or meta.get("run","")+"/"+meta.get("condition",""),
             npc_mode=meta.get("npc_mode"), requested=meta["requested_npc"], spawned=meta["spawned_npc"],
             spawn_ratio=round(sr,2), autopilot_delay=meta.get("autopilot_delay_enabled"),
             run_kind=meta.get("run_kind"), drive_frames=meta.get("drive_frames"), **g, **d)
    cls, reason = classify(m); m["class"] = cls; m["reason"] = reason
    out = Path(a.out_csv); df = pd.DataFrame([m])
    df.to_csv(out, mode="a", header=not out.exists(), index=False)
    print(f"[preview-audit] {m['run']}: {cls} ({reason})")
    for k in ["spawn_ratio","gt_obj_per_f","rng_med","pct_lt50","pct_gt150","infov_lt50_per_f",
              "det_total","matched","matched_lt50","det_per_f","bbox_med","fullframe_ratio","tracks"]:
        print(f"    {k:16s} {m.get(k)}")


if __name__ == "__main__":
    main()
