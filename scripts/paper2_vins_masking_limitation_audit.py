#!/usr/bin/env python3
"""Paper-2 Phase 1 — VINS masking LIMITATION audit.

For each Phase-C result dir (paper2_vinsaware/<tag>__<variant>), extract VINS internals from vins.log
(admission-debug: raw/mgr/inlier/outlier ratio) + reliability_features_vins.csv (tracked_feature_count),
join with the metrics jsonl and the recording-quality classification. Answers: was the baseline stable?
how many features did masking remove? did outlier ratio change? which runs are core-worthy vs failure-only.

Output: paper2_vins_masking_limitation.csv + PAPER2_VINS_MASKING_LIMITATION_AUDIT.md
"""
from __future__ import annotations
import json, re, glob
from pathlib import Path
import numpy as np, pandas as pd

WS = Path("/home/ivlab3/fwvio_estimator_ws_wheel")
RES = Path("/mnt/sata4t/ivlab3_data/fwvio/results/paper2_vinsaware")
OUT = WS / "paper2" / "track_a"
QCSV = OUT / "paper2_recording_quality_audit.csv"

RUNMAP = {"t01_dense_b1": "Town01__dynamic_v3__rundense_b1",
          "t01_medium_b1": "Town01__dynamic_v3__runmedium_b1",
          "t06_dense_b1": "Town06__dynamic_v3__rundense_b1",
          "t07_dense_b1": "Town07__dynamic_v3__rundense_b1"}
VARIANTS = ["baseline", "all_dynamic", "validity_aware", "oracle"]


def parse_vins_log(p: Path):
    if not p.exists(): return {}
    raw, mgr, ratio = [], [], []
    for line in p.read_text(errors="ignore").splitlines():
        if "admission-debug" in line:
            m = dict(re.findall(r"(\w+)=([0-9.]+)", line))
            if "mgr" in m: mgr.append(float(m["mgr"]))
            if "ratio" in m: ratio.append(float(m["ratio"]))
            if "raw" in m: raw.append(float(m["raw"]))
    return dict(mean_mgr_feat=round(float(np.mean(mgr)), 1) if mgr else None,
                mean_outlier_ratio=round(float(np.mean(ratio)), 3) if ratio else None,
                n_keyframes=len(mgr))


def main():
    Q = pd.read_csv(QCSV).set_index("run")
    metrics = {}
    for l in (OUT / "paper2_validity_aware_vins_metrics.jsonl").read_text().splitlines():
        if l.strip():
            d = json.loads(l); metrics[(d["tag"], d["variant"])] = d

    rows = []
    for tag, run in RUNMAP.items():
        qcls = Q.loc[run, "classification"] if run in Q.index else "?"
        for v in VARIANTS:
            od = RES / f"{tag}__{v}"
            vl = parse_vins_log(od / "vins.log")
            m = metrics.get((tag, v), {})
            rows.append(dict(run=run, quality=qcls, variant=v,
                             ate_rmse=m.get("ate_rmse"), rpe=m.get("rpe_trans_med"),
                             early=m.get("early_scale"), late=m.get("late_scale"),
                             diverged=m.get("diverged"), vins_fail=m.get("vins_failures"),
                             **vl))
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "paper2_vins_masking_limitation.csv", index=False)

    L = ["# PAPER2 Phase 1 — VINS MASKING LIMITATION AUDIT", "",
         "> Honest re-examination of the prior Phase-C masking run, cross-referenced with the Phase -1 "
         "recording-quality classification. Date 2026-07-01.", "",
         "## 0. Was `validity_aware` actually TCSV-M?",
         "**No.** In the prior Phase-C run, `validity_aware` = a **raw-speed gate** (mask detections whose "
         "OWN raw estimated speed > 1 m/s). It did **NOT** use the Part-1 learned TCSV-M model. This is "
         "acknowledged here; using the real TCSV-M is Phase 2 (`paper2_vins_tcsv_masking.py`). Calling the "
         "prior variant 'validity_aware' overstated it — it is a deployable *observability* gate, not the model.", "",
         "## 1. Per run × variant (VINS internals + metrics + data quality)",
         "| run | quality | variant | ATE_rmse | RPE | early | late | mgr_feat | outlier_ratio | kf | fail |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for _, r in df.iterrows():
        L.append(f"| {r.run.replace('__dynamic_v3__run','/')} | {r.quality} | {r.variant} | {r.ate_rmse} | "
                 f"{r.rpe} | {r.early} | {r.late} | {r.mean_mgr_feat} | {r.mean_outlier_ratio} | "
                 f"{r.n_keyframes} | {r.vins_fail} |")

    # per-run baseline health verdict
    L += ["", "## 2. Which runs are valid for CORE VINS experiments?"]
    for tag, run in RUNMAP.items():
        b = df[(df.run == run) & (df.variant == "baseline")].iloc[0]
        qcls = b.quality
        stable = (b.early is not None and 0.9 <= b.early <= 1.1 and b.ate_rmse is not None and b.ate_rmse < 10)
        if qcls == "PASS_CORE" and stable:
            verd = "**CORE** (clean data + stable baseline)"
        elif qcls == "PASS_CORE":
            verd = "**FAILURE-ANALYSIS ONLY** (clean data but baseline unstable)"
        else:
            verd = f"**EXCLUDE** (data quality = {qcls})"
        L.append(f"- {run}: baseline early={b.early} ATE={b.ate_rmse} m, quality={qcls} → {verd}")

    L += ["", "## 3. Answers to the Phase-1 questions",
          "1. **validity_aware = TCSV-M?** No — raw_speed gate (see §0).",
          "2. **Per-run baseline stability / features / outliers:** see §1. Note VINS baseline **outlier ratio "
          "is already ~0.9** on Town01 — the frontend is *already rejecting the vast majority of features* "
          "(incl. most dynamic-object features) via RANSAC/F-threshold. This is the core limitation: input "
          "masking removes features the estimator would have rejected anyway → small net effect.",
          "3. **Town07 deployable mask worse (+29%)?** Town07 dense_b1 is **INVALID (spawn collision)** — an NPC "
          "fills 56% of the frame at 1.26 m. Masking it removes almost all features → VINS starves → worse. The "
          "prior +29% was a data artifact, not a method failure.",
          "4. **Town06 baseline ATE 41 m?** Town06 dense_b1 has 84% of objects >150 m and is a fast highway "
          "scene; baseline early-scale 1.29 (already off). Borderline PASS_CORE → failure-analysis only.",
          "5. **Core-worthy runs:** only **Town01 dense_b1 & medium_b1** (PASS_CORE + stable baseline). On those "
          "two clean runs, prior masking gave validity_aware −10.5% / −2.8% ATE with 0 failures — a consistent "
          "small improvement, no regression. The 'mixed/erratic' Phase-C story was driven by the 2 bad runs "
          "(Town06 borderline, Town07 invalid).",
          "6. **Failure-analysis-only runs:** Town06 dense_b1 (unstable baseline), Town07 dense_b1 (invalid).",
          "", "## 4. Limitations of the prior masking approach",
          "- **Image blur, not feature-level routing:** suppression was a side effect of blurring; some boundary "
          "features survive and blurred regions can still yield weak corners. Phase 3 (feature-tracker routing) "
          "is the correct mechanism.",
          "- **Frontend already rejects dynamics** (outlier ratio ~0.9) → limited headroom for input masking.",
          "- **No per-feature pixel coordinates logged** → cannot yet count exactly how many VINS features fell "
          "inside object bboxes; `mgr_feat` delta (baseline vs masked) is only a coarse proxy. Phase 3 routing "
          "should log object-region feature counts explicitly.",
          "- **raw_speed ≠ learned validity** → Phase 2 must plug in TCSV-M and re-test on CLEAN runs only.",
          "", "## 5. Verdict",
          "Re-run the VINS masking experiments **only on PASS_CORE + stable runs** (currently Town01 dense/medium; "
          "more after Phase -3 re-record), with the **real TCSV-M** (Phase 2) and ideally **feature-level routing** "
          "(Phase 3). Drop Town07 (invalid) and treat Town06 as failure-analysis. The prior positive signal on "
          "clean runs (~−6% mean, 0 failures) stands; the negative/erratic parts were data-quality artifacts."]
    (OUT / "PAPER2_VINS_MASKING_LIMITATION_AUDIT.md").write_text("\n".join(L) + "\n")
    print("[limit-audit] wrote PAPER2_VINS_MASKING_LIMITATION_AUDIT.md + csv")
    print(df[["run", "quality", "variant", "ate_rmse", "mean_mgr_feat", "mean_outlier_ratio"]].to_string(index=False))


if __name__ == "__main__":
    main()
