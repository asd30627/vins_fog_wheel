#!/usr/bin/env python3
"""Paper-2 Part 2 — analyze validity-aware VINS metrics jsonl -> CSV + RESULTS md.

Reads paper2/track_a/paper2_validity_aware_vins_metrics.jsonl (one line per run×variant),
pivots ATE/RPE/scale by variant, computes % change vs baseline per run, writes:
  paper2_validity_aware_vins_metrics.csv, (partial) PAPER2_VALIDITY_AWARE_VINS_RESULTS.md
"""
from __future__ import annotations
import json
from pathlib import Path
import pandas as pd, numpy as np

OUT = Path("/home/ivlab3/fwvio_estimator_ws_wheel/paper2/track_a")
JL = OUT / "paper2_validity_aware_vins_metrics.jsonl"
VARIANTS = ["baseline", "all_dynamic", "validity_aware", "oracle"]


def main():
    rows = [json.loads(l) for l in JL.read_text().splitlines() if l.strip()]
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "paper2_validity_aware_vins_metrics.csv", index=False)

    L = ["# PAPER2 Part 2 — VALIDITY-AWARE VINS RESULTS", "",
         "> Stereo-inertial VINS-Fusion on CARLA (true VIO), offline replay (CARLA OFF), b05 config, "
         "rate 0.5, ideal IMU + skip-imu-head 150. Intervention = LEFT-image feature suppression of "
         "dynamic-object bboxes (Gaussian-blur, soft boundary), 4 variants. Metric ATE_rmse↓ (Umeyama "
         "SE3-aligned), RPE_trans↓, scale early/late (1.0 ideal), #vio rows, VINS failures. "
         "GT used only for eval/oracle. Date 2026-07-01.", "",
         "Variants: **baseline** (no mask) · **all_dynamic** (mask every detection = DynaVINS-style proxy) · "
         "**validity_aware** (mask only raw_speed>1 m/s = observably-moving, deployable) · "
         "**oracle** (mask only GT gt_speed>1 = truly-moving, upper bound).", "",
         "## Per-run × variant", "| run | variant | ATE_rmse | ATE_mean | RPE_trans | early | late | n_vio | fail | diverged |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for run in sorted(df.run.unique()):
        sub = df[df.run == run].set_index("variant")
        for v in VARIANTS:
            if v in sub.index:
                r = sub.loc[v]
                L.append(f"| {run} | {v} | {r.ate_rmse} | {r.ate_mean} | {r.rpe_trans_med} | "
                         f"{r.early_scale} | {r.late_scale} | {r.n_vio} | {r.vins_failures} | {r.diverged} |")

    L += ["", "## ATE_rmse % change vs baseline (negative = improvement)",
          "| run | all_dynamic | validity_aware | oracle |", "|---|---|---|---|"]
    deltas = {}
    for run in sorted(df.run.unique()):
        sub = df[df.run == run].set_index("variant")
        if "baseline" not in sub.index or sub.loc["baseline"].ate_rmse is None:
            L.append(f"| {run} | (no baseline) | | |"); continue
        base = sub.loc["baseline"].ate_rmse
        cells = []
        for v in ["all_dynamic", "validity_aware", "oracle"]:
            if v in sub.index and sub.loc[v].ate_rmse is not None and base:
                d = 100 * (sub.loc[v].ate_rmse - base) / base
                deltas.setdefault(v, []).append(d)
                cells.append(f"{d:+.1f}%")
            else:
                cells.append("—")
        L.append(f"| {run} | {cells[0]} | {cells[1]} | {cells[2]} |")
    L += ["", "## Mean ATE % change vs baseline (across runs)"]
    for v in ["all_dynamic", "validity_aware", "oracle"]:
        if deltas.get(v):
            L.append(f"- **{v}**: {np.mean(deltas[v]):+.1f}% (n={len(deltas[v])} runs)")
    (OUT / "PAPER2_VALIDITY_AWARE_VINS_RESULTS.md").write_text("\n".join(L) + "\n")
    print("[report] wrote PAPER2_VALIDITY_AWARE_VINS_RESULTS.md +", "metrics.csv;",
          f"runs={df.run.nunique()} rows={len(df)}")
    print(df[["run", "variant", "ate_rmse", "rpe_trans_med", "early_scale", "late_scale", "diverged"]].to_string(index=False))


if __name__ == "__main__":
    main()
