#!/usr/bin/env python3
"""Paper-2 Part 2 / Phase C — build per-frame dynamic-object masks for a CARLA run, 3 variants.

From the run's per-det CSV (outputs/paper2_perdet/<run>.csv) emit {frame:[[x0,y0,x1,y1],...]} JSON:
  all_dynamic    : EVERY detection bbox (naive "remove all detected objects" = DynaVINS-style proxy).
  validity_aware : only detections the object appears to be MOVING from its OWN raw estimate
                   (raw_speed_ms > SPD). Deployable (no GT) — a runtime validity/observability signal.
  oracle         : only detections GT confirms are MOVING (gt_speed_ms > SPD). Perfect dynamic/static
                   routing = upper bound (GT used for EVAL/oracle only, never as a runtime feature).

bbox reconstructed from per-det (u,v)=center, (bbox_w,bbox_h)=pixel size. Writes JSONs next to a mask dir.
Prints per-variant boxed-frame / total-box counts so over/under-masking is visible.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
import pandas as pd, numpy as np

WS = Path("/home/ivlab3/fwvio_estimator_ws_wheel")
PERDET = WS / "outputs" / "paper2_perdet"


def boxes_from(df):
    out = {}
    for _, r in df.iterrows():
        u, v, w, h = r["u"], r["v"], r["bbox_w"], r["bbox_h"]
        if not np.isfinite([u, v, w, h]).all():
            continue
        x0, y0, x1, y1 = u - w / 2, v - h / 2, u + w / 2, v + h / 2
        out.setdefault(int(r["frame"]), []).append([round(float(x0), 1), round(float(y0), 1),
                                                    round(float(x1), 1), round(float(y1), 1)])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="per-det stem, e.g. Town01__dynamic_v3__rundense_b1")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--spd", type=float, default=1.0, help="moving-speed threshold m/s")
    a = ap.parse_args()
    out = Path(a.out_dir); out.mkdir(parents=True, exist_ok=True)
    d = pd.read_csv(PERDET / f"{a.run}.csv", low_memory=False)
    for c in ["u", "v", "bbox_w", "bbox_h", "frame", "raw_speed_ms", "gt_speed_ms", "matched"]:
        if c in d: d[c] = pd.to_numeric(d[c], errors="coerce")
    n = len(d)
    variants = {
        "all_dynamic": d,
        "validity_aware": d[d["raw_speed_ms"] > a.spd],
        "oracle": d[(d["matched"] == 1) & (d["gt_speed_ms"] > a.spd)],
    }
    summary = {}
    for name, sub in variants.items():
        bx = boxes_from(sub)
        p = out / f"mask_{a.run}__{name}.json"
        p.write_text(json.dumps(bx))
        nb = sum(len(v) for v in bx.values())
        summary[name] = dict(n_det=len(sub), n_frames=len(bx), n_boxes=nb, path=str(p))
        print(f"[mask] {name}: det={len(sub)}/{n} frames={len(bx)} boxes={nb} -> {p.name}")
    (out / f"mask_{a.run}__summary.json").write_text(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
