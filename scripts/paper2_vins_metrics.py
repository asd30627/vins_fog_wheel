#!/usr/bin/env python3
"""Paper-2 Part 2 — robust VIO metrics for one result dir (handles diverged/empty vio gracefully).

vio.csv = ts,px,py,pz,qw,qx,qy,qz,vx,vy,vz ; GT = <rec>/gt/*.json ego_pose.
Metrics: n_vio, ate_rmse (Umeyama SE3-aligned), ate_mean, early_scale, late_scale, rpe_trans_med,
  max_pos (divergence flag), vins_failures, diverged(bool).
Usage: paper2_vins_metrics.py <rec_dir> <result_dir> [label]  -> prints JSON line.
"""
from __future__ import annotations
import sys, json, glob
import numpy as np


def umeyama_rmse(s, d):
    """RMSE after similarity? No — SE(3) (rotation+translation, no scale) align s->d, return RMSE."""
    ms, md = s.mean(0), d.mean(0)
    S, D = s - ms, d - md
    C = D.T @ S / len(s)
    U, _, Vt = np.linalg.svd(C)
    R = U @ Vt
    if np.linalg.det(R) < 0:
        U[:, -1] *= -1; R = U @ Vt
    aligned = (R @ s.T).T + (md - R @ ms)
    err = np.linalg.norm(aligned - d, axis=1)
    return float(np.sqrt((err ** 2).mean())), float(err.mean())


def main():
    rec, res = sys.argv[1], sys.argv[2]
    label = sys.argv[3] if len(sys.argv) > 3 else res.rstrip("/").split("/")[-1]
    out = dict(label=label, n_vio=0, diverged=True, ate_rmse=None, ate_mean=None,
               early_scale=None, late_scale=None, rpe_trans_med=None, max_pos=None, vins_failures=None)
    # GT
    P, GT = [], []
    for f in sorted(glob.glob(f"{rec}/gt/*.json")):
        d = json.load(open(f)); e = d["ego_pose"]; P.append([e["x"], e["y"], e["z"]]); GT.append(d["ts_ns"] * 1e-9)
    P = np.array(P); GT = np.array(GT)
    if len(P) < 5:
        print(json.dumps(out)); return
    gtsp = np.r_[0, np.linalg.norm(np.diff(P, axis=0), axis=1) / np.maximum(np.diff(GT), 1e-6)]
    # vio
    try:
        v = np.loadtxt(f"{res}/vio.csv", delimiter=",", usecols=range(11))
        if v.ndim == 1:
            v = v.reshape(1, -1)
    except Exception:
        print(json.dumps(out)); return
    out["n_vio"] = int(len(v))
    if len(v) < 5 or not np.isfinite(v[:, 1:4]).all():
        out["max_pos"] = float(np.nanmax(np.abs(v[:, 1:4]))) if len(v) else None
        print(json.dumps(out)); return
    vt, vp, vv = v[:, 0], v[:, 1:4], v[:, 8:11]
    out["max_pos"] = float(np.max(np.abs(vp)))
    # failure count
    try:
        import subprocess
        fc = subprocess.run(["grep", "-c", "failure detection", f"{res}/vins.log"], capture_output=True, text=True).stdout.strip()
        out["vins_failures"] = int(fc) if fc.isdigit() else None
    except Exception:
        pass
    # scale (speed ratio early <11s, late >20s relative to GT start)
    vs = np.linalg.norm(vv, axis=1)
    mv = [(vt[i] - GT[0], vs[i] / gtsp[min(np.searchsorted(GT, vt[i]), len(gtsp) - 1)])
          for i in range(len(vt)) if gtsp[min(np.searchsorted(GT, vt[i]), len(gtsp) - 1)] > 1]
    early = [r for t, r in mv if t < 11]; late = [r for t, r in mv if t > 20]
    out["early_scale"] = round(float(np.median(early)), 4) if early else None
    out["late_scale"] = round(float(np.median(late)), 4) if late else None
    # divergence: max_pos sane vs GT path extent
    gt_extent = float(np.linalg.norm(P.max(0) - P.min(0)))
    out["diverged"] = bool(out["max_pos"] > 10 * max(gt_extent, 1.0))
    # ATE (SE3-aligned RMSE)
    idx = np.clip(np.searchsorted(GT, vt), 0, len(P) - 1)
    try:
        rmse, mean = umeyama_rmse(vp, P[idx])
        out["ate_rmse"] = round(rmse, 3); out["ate_mean"] = round(mean, 3)
    except Exception:
        pass
    # RPE translation (1s windows): error in relative displacement vio vs GT
    try:
        rpe = []
        for i in range(len(vt)):
            j = np.searchsorted(vt, vt[i] + 1.0)
            if j >= len(vt): break
            gi, gj = np.clip(np.searchsorted(GT, [vt[i], vt[j]]), 0, len(P) - 1)
            dvio = np.linalg.norm(vp[j] - vp[i]); dgt = np.linalg.norm(P[gj] - P[gi])
            rpe.append(abs(dvio - dgt))
        out["rpe_trans_med"] = round(float(np.median(rpe)), 4) if rpe else None
    except Exception:
        pass
    print(json.dumps(out))


if __name__ == "__main__":
    main()
