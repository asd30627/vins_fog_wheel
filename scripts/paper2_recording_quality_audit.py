#!/usr/bin/env python3
"""Paper-2 Phase -1 — CARLA recording / spawn SANITY AUDIT (per run).

For every dynamic_v3 recording, join GT (gt/*.json: ego_pose + per_instance) with the per-det CSV
(outputs/paper2_perdet/<run>.csv) and compute object-visibility + detectability stats, then classify:
  PASS_CORE | LOW_YIELD | INVALID_RECORDING.

Ego is EXCLUDED from per_instance (the near-zero-range self actor). FOV membership computed from ego
yaw + camera fov (object is visible if forward>0 and |bearing|<fov/2).

Outputs (paper2/track_a/): PAPER2_RECORDING_QUALITY_AUDIT.md, paper2_recording_quality_audit.csv
"""
from __future__ import annotations
import json, math, glob
from pathlib import Path
import numpy as np, pandas as pd

WS = Path("/home/ivlab3/fwvio_estimator_ws_wheel")
DATAROOT = Path("/mnt/sata4t/datasets/carla_fwvio")
PERDET = WS / "outputs" / "paper2_perdet"
OUT = WS / "paper2" / "track_a"; OUT.mkdir(parents=True, exist_ok=True)
EGO_MIN_RANGE = 2.0    # objects closer than this are the ego/self actor -> excluded
DYN_SPD = 1.0          # m/s -> dynamic


def pct(a, q):
    return float(np.percentile(a, q)) if len(a) else float("nan")


def audit_run(rec: Path):
    meta = {}
    mp = rec / "recording_meta.json"
    if mp.exists():
        meta = json.loads(mp.read_text())
    fov = float(meta.get("fov", 90.0)); half = fov / 2.0
    gts = sorted(glob.glob(f"{rec}/gt/*.json"))
    n_frames = len(gts)
    ranges, dyn_ranges = [], []
    obj_per_frame, infov_per_frame, infov_near_per_frame = [], [], []
    dyn_obj_ids = set(); all_obj_ids = set()
    ego_in_instances = 0
    for f in gts:
        d = json.load(open(f)); e = d["ego_pose"]; yaw = math.radians(e["yaw"])
        ins = d.get("per_instance", {})
        nobj = 0; ninfov = 0; ninfov_near = 0
        for oid, o in ins.items():
            dx = o["x"] - e["x"]; dy = o["y"] - e["y"]; rng = math.hypot(dx, dy)
            if rng < EGO_MIN_RANGE:
                ego_in_instances += 1; continue  # ego/self
            all_obj_ids.add(oid); nobj += 1; ranges.append(rng)
            spd = float(o.get("speed", 0.0))
            if spd > DYN_SPD:
                dyn_obj_ids.add(oid); dyn_ranges.append(rng)
            fwd = dx * math.cos(yaw) + dy * math.sin(yaw)
            lat = -dx * math.sin(yaw) + dy * math.cos(yaw)
            infov = fwd > 0 and abs(math.degrees(math.atan2(abs(lat), max(fwd, 1e-6)))) < half
            if infov:
                ninfov += 1
                if rng < 50: ninfov_near += 1
        obj_per_frame.append(nobj); infov_per_frame.append(ninfov); infov_near_per_frame.append(ninfov_near)
    ranges = np.array(ranges) if ranges else np.array([np.nan])

    # per-det CSV
    pdp = PERDET / f"{rec.name}.csv"
    det_total = matched_total = 0; near50 = 0; frac_fullframe = 0.0
    img_area = float(meta.get("W", 640)) * float(meta.get("H", 480))
    barea = np.array([np.nan]); n_tracks = 0; pv = vv = 0
    if pdp.exists():
        dd = pd.read_csv(pdp, low_memory=False)
        for c in ["matched", "range_m", "bbox_area", "track_id", "gt_speed_ms", "raw_speed_ms"]:
            if c in dd: dd[c] = pd.to_numeric(dd[c], errors="coerce")
        det_total = len(dd)
        m = dd[dd.get("matched", 0) == 1] if "matched" in dd else dd.iloc[0:0]
        matched_total = len(m)
        if "range_m" in m: near50 = int((m["range_m"] < 50).sum())
        if "bbox_area" in dd and len(dd):
            barea = dd["bbox_area"].dropna().to_numpy()
            # spawn-collision detector: fraction of dets whose bbox covers >50% of the frame
            frac_fullframe = float(np.mean(barea > 0.5 * img_area)) if len(barea) else 0.0
        if "track_id" in m: n_tracks = int(m["track_id"].nunique())

    # labels from canonical loader would be heavy per-run; approximate pos/vel valid from per-det matched
    # (loader uses same thresholds). Count via per-det gt columns if present.
    if pdp.exists() and "matched" in dd:
        mm = dd[dd["matched"] == 1]
        if "pos_err_m" in dd:
            pe = pd.to_numeric(mm.get("pos_err_m"), errors="coerce")
            pv = int((pe <= 3.0).sum())
        if "speed_err_ms" in dd and "dir_err_deg" in dd:
            se = pd.to_numeric(mm.get("speed_err_ms"), errors="coerce")
            de = pd.to_numeric(mm.get("dir_err_deg"), errors="coerce")
            vv = int(((se <= 3.0) & (de <= 45.0)).sum())

    exp_frames = int(meta.get("n_frames", 0)) or n_frames
    r = dict(
        run=rec.name, town=meta.get("town", rec.name.split("__")[0]),
        density=meta.get("condition", ""), tag=meta.get("run", ""),
        n_frames=n_frames, exp_frames=exp_frames, frames_ok=bool(n_frames >= 0.9 * max(exp_frames, 1)),
        fov=fov, ego_self_rows=ego_in_instances,
        gt_obj_per_frame=round(float(np.mean(obj_per_frame)), 2) if obj_per_frame else 0.0,
        rng_min=round(float(np.nanmin(ranges)), 1), rng_median=round(float(np.nanmedian(ranges)), 1),
        rng_p10=round(pct(ranges, 10), 1), rng_p90=round(pct(ranges, 90), 1),
        pct_lt30=round(float(np.mean(ranges < 30) * 100), 1), pct_lt50=round(float(np.mean(ranges < 50) * 100), 1),
        pct_gt150=round(float(np.mean(ranges > 150) * 100), 1),
        infov_per_frame=round(float(np.mean(infov_per_frame)), 2) if infov_per_frame else 0.0,
        infov_near_per_frame=round(float(np.mean(infov_near_per_frame)), 2) if infov_near_per_frame else 0.0,
        det_total=det_total, matched_total=matched_total,
        det_per_frame=round(det_total / max(n_frames, 1), 2),
        matched_lt50m=near50,
        bbox_area_p10=round(pct(barea, 10), 1), bbox_area_med=round(pct(barea, 50), 1),
        bbox_area_p90=round(pct(barea, 90), 1), frac_fullframe=round(frac_fullframe, 3),
        n_tracks=n_tracks, n_gt_objects=len(all_obj_ids), n_dynamic_objects=len(dyn_obj_ids),
        pos_valid_pos=pv, vel_valid_pos=vv,
    )
    r["classification"] = classify(r)
    r["use_object_validity"] = r["matched_total"] >= 50 and r["n_tracks"] >= 5
    r["use_vins_masking"] = r["matched_lt50m"] >= 30 and r["n_dynamic_objects"] >= 1
    r["use_ttc_planner"] = r["infov_near_per_frame"] >= 0.5 and r["n_dynamic_objects"] >= 1
    return r


def classify(r):
    # INVALID: no detections at all, or nothing matched, or everything far / not visible, or frames broken
    if not r["frames_ok"]:
        return "INVALID_RECORDING"
    if r["det_total"] == 0 or r["matched_total"] < 5:
        return "INVALID_RECORDING"
    if r["pct_gt150"] >= 95 or r["infov_near_per_frame"] < 0.05:
        return "INVALID_RECORDING"
    if r["frac_fullframe"] >= 0.30:   # spawn-collision: an NPC glued to the camera fills >50% frame in >30% of dets
        return "INVALID_RECORDING"
    # PASS_CORE: enough matched detections, near objects, dynamic objects, visible bbox
    if (r["matched_total"] >= 150 and r["det_per_frame"] >= 0.5 and r["matched_lt50m"] >= 30
            and r["n_dynamic_objects"] >= 1 and r["bbox_area_med"] >= 100 and r["n_tracks"] >= 5):
        return "PASS_CORE"
    return "LOW_YIELD"


def main():
    recs = sorted(p for p in DATAROOT.glob("Town*__dynamic_v3__run*") if p.is_dir() and (p / "gt").exists())
    rows = [audit_run(r) for r in recs]
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "paper2_recording_quality_audit.csv", index=False)

    counts = df.classification.value_counts().to_dict()
    L = ["# PAPER2 Phase -1 — CARLA RECORDING / SPAWN QUALITY AUDIT", "",
         f"> Per-run object-visibility + detectability audit over {len(df)} dynamic_v3 recordings "
         f"(4 towns × 12 runs). Ego excluded from per_instance (range<{EGO_MIN_RANGE} m). FOV from ego "
         f"yaw + camera fov. Date 2026-07-01.", "",
         f"## Classification summary",
         f"- **PASS_CORE**: {counts.get('PASS_CORE',0)}  ·  **LOW_YIELD**: {counts.get('LOW_YIELD',0)}  ·  "
         f"**INVALID_RECORDING**: {counts.get('INVALID_RECORDING',0)}", "",
         "Gate rules — INVALID: frames incomplete OR det=0 OR matched<5 OR >95% objects beyond 150 m OR "
         "in-FOV-near objects <0.05/frame. PASS_CORE: matched≥150 & det/frame≥0.5 & matched<50m≥30 & "
         "dynamic≥1 & bbox_med≥100 px² & tracks≥5. else LOW_YIELD.", "",
         "## Per-run (sorted town, then run)",
         "| run | class | frames | gt_obj/f | rng_med | %<50m | %>150m | infov_near/f | det | matched | m<50m | bbox_med | tracks | dyn | use:validity/mask/ttc |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for _, r in df.sort_values(["town", "run"]).iterrows():
        use = f"{int(r.use_object_validity)}/{int(r.use_vins_masking)}/{int(r.use_ttc_planner)}"
        L.append(f"| {r.run.replace('__dynamic_v3__run','/')} | {r.classification} | {r.n_frames} | "
                 f"{r.gt_obj_per_frame} | {r.rng_median} | {r.pct_lt50} | {r.pct_gt150} | {r.infov_near_per_frame} | "
                 f"{r.det_total} | {r.matched_total} | {r.matched_lt50m} | {r.bbox_area_med} | {r.n_tracks} | "
                 f"{r.n_dynamic_objects} | {use} |")

    inv = df[df.classification == "INVALID_RECORDING"]
    low = df[df.classification == "LOW_YIELD"]
    core = df[df.classification == "PASS_CORE"]
    L += ["", "## INVALID_RECORDING runs (must exclude / re-record)"]
    for _, r in inv.sort_values("run").iterrows():
        reason = []
        if not r.frames_ok: reason.append(f"frames {r.n_frames}/{r.exp_frames}")
        if r.det_total == 0: reason.append("YOLO det=0")
        if r.matched_total < 5: reason.append(f"matched={r.matched_total}")
        if r.pct_gt150 >= 95: reason.append(f"{r.pct_gt150}% objects >150m")
        if r.infov_near_per_frame < 0.05: reason.append(f"in-FOV<50m={r.infov_near_per_frame}/f")
        if r.frac_fullframe >= 0.30: reason.append(f"SPAWN-COLLISION: {r.frac_fullframe*100:.0f}% dets fill >50% frame")
        L.append(f"- **{r.run}**: {', '.join(reason)}")
    L += ["", f"## Core set: {len(core)} runs | Low-yield: {len(low)} | Invalid: {len(inv)}",
          "- rotated-spawn (r30/r60/r90) low-yield/invalid rate: "
          f"{(df[df.run.str.contains('_r3|_r6|_r9')].classification!='PASS_CORE').mean()*100:.0f}% "
          "vs b1(spawn=0): "
          f"{(df[df.run.str.contains('_b1')].classification!='PASS_CORE').mean()*100:.0f}%",
          "", "## Verdict",
          f"- Town06 sparse_r30 status: **{df[df.run=='Town06__dynamic_v3__runsparse_r30'].classification.iloc[0] if (df.run=='Town06__dynamic_v3__runsparse_r30').any() else 'n/a'}** "
          "(previously hidden by a header-only placeholder — now correctly classified).",
          "- Only PASS_CORE runs may enter core experiments; LOW_YIELD -> appendix/robustness; INVALID -> excluded/re-record.",
          "- See PAPER2_CARLA_SPAWN_BUG_AUDIT.md for root cause of the far-object / low-yield pattern."]
    (OUT / "PAPER2_RECORDING_QUALITY_AUDIT.md").write_text("\n".join(L) + "\n")
    print(f"[qaudit] {len(df)} runs: PASS_CORE={counts.get('PASS_CORE',0)} "
          f"LOW_YIELD={counts.get('LOW_YIELD',0)} INVALID={counts.get('INVALID_RECORDING',0)}")
    print(f"[qaudit] INVALID:", inv.run.tolist())
    print(f"[qaudit] wrote PAPER2_RECORDING_QUALITY_AUDIT.md + csv")


if __name__ == "__main__":
    main()
