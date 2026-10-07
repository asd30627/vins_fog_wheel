#!/usr/bin/env python3
"""Paper-2 nuScenes Stage B (gf env) — YOLOv8m BATCHED detection on CAM_FRONT keyframes (no tracking).

Batched GPU predict (fast). track_id left -1; assembly groups by matched GT instance_token (grouping may
use GT, like CARLA). Reads manifest.csv; writes dets.csv:
  sample_token, scene, frame_idx, cls, conf, x0,y0,x1,y1, u,v,bw,bh.
"""
from __future__ import annotations
import csv
from pathlib import Path
from ultralytics import YOLO

OUTDIR = Path("/home/ivlab3/fwvio_estimator_ws_wheel/paper2/nuscenes")
YOLO_W = "/home/ivlab3/fwvio_estimator_ws_wheel/kaist_grade_scripts/yolov8m.pt"
MOVABLE = {"car", "truck", "bus", "motorcycle", "bicycle", "person"}
CONF = 0.25
BATCH = 16


def main():
    rows = list(csv.DictReader(open(OUTDIR / "manifest.csv")))
    model = YOLO(YOLO_W); names = model.names
    out = open(OUTDIR / "dets.csv", "w", newline=""); w = csv.writer(out)
    w.writerow(["sample_token", "scene", "frame_idx", "cls", "conf", "x0", "y0", "x1", "y1", "u", "v", "bw", "bh"])
    n_det = 0
    for i in range(0, len(rows), BATCH):
        chunk = rows[i:i + BATCH]
        res = model.predict([r["img_path"] for r in chunk], device=0, imgsz=960, conf=CONF,
                            verbose=False, batch=BATCH)
        for r, rr in zip(chunk, res):
            if rr.boxes is None:
                continue
            for b in rr.boxes:
                cls = names[int(b.cls)]
                if cls not in MOVABLE:
                    continue
                x0, y0, x1, y1 = b.xyxy[0].tolist()
                conf = float(b.conf) if b.conf is not None else 0.0
                w.writerow([r["sample_token"], r["scene"], r["frame_idx"], cls, round(conf, 4),
                            round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1),
                            round((x0 + x1) / 2, 1), round((y0 + y1) / 2, 1), round(x1 - x0, 1), round(y1 - y0, 1)])
                n_det += 1
        if (i // BATCH + 1) % 20 == 0:
            print(f"[yolo] {i+len(chunk)}/{len(rows)} imgs, {n_det} dets", flush=True)
    out.close()
    print(f"[yolo] done: {len(rows)} imgs, {n_det} dets -> {OUTDIR}/dets.csv")


if __name__ == "__main__":
    main()
