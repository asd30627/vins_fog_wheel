#!/usr/bin/env python3
"""Paper-2 G0 — validate one CARLA dynamic_v3 recording dir. Prints a TSV status line; exit 0 if OK.

Checks: recording_meta.json present; stereo_left/right + depth_left/seg_left/flow_left + gt counts
== meta n_frames; a mid gt frame's per_instance has all required fields incl type_id; reports
n_instances and disk size (GB). Used by paper2_carla_dataset_driver.sh.
"""
from __future__ import annotations
import json, sys, glob, os, subprocess
from pathlib import Path

REQ_FIELDS = ("speed", "vx", "vy", "vz", "x", "y", "z", "yaw", "ext", "type_id")


def disk_gb(p: Path) -> float:
    try:
        out = subprocess.check_output(["du", "-sb", str(p)]).split()[0]
        return round(int(out) / 1e9, 2)
    except Exception:
        return -1.0


def main():
    rec = Path(sys.argv[1])
    meta_f = rec / "recording_meta.json"
    if not meta_f.exists():
        print(f"FAIL\t{rec.name}\tno_recording_meta"); sys.exit(1)
    meta = json.loads(meta_f.read_text())
    nf = int(meta.get("n_frames", 0))
    counts = {d: len(glob.glob(str(rec / d / "*"))) for d in
              ("stereo_left", "stereo_right", "depth_left", "seg_left", "flow_left", "gt")}
    counts_ok = all(c == nf for c in counts.values()) and nf > 0
    # per-instance field check on a mid drive-phase gt frame
    gt_files = sorted((rec / "gt").glob("*.json"))
    n_inst = 0; type_ok = False; fields_ok = False
    if gt_files:
        g = json.loads(gt_files[min(len(gt_files) - 1, int(nf * 0.85))].read_text())
        pi = g.get("per_instance", {}); n_inst = len(pi)
        if pi:
            any_inst = next(iter(pi.values()))
            fields_ok = all(k in any_inst for k in REQ_FIELDS)
            type_ok = "type_id" in any_inst
    dgb = disk_gb(rec)
    ok = counts_ok and fields_ok and type_ok and n_inst >= 1
    status = "OK" if ok else "FAIL"
    note = []
    if not counts_ok: note.append(f"counts={counts}")
    if not fields_ok: note.append("missing_fields")
    if not type_ok: note.append("no_type_id")
    print(f"{status}\t{rec.name}\tn_frames={nf}\tcounts_ok={counts_ok}\tn_inst={n_inst}\t"
          f"type_id={type_ok}\tdisk_gb={dgb}\t{';'.join(note) if note else '-'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
