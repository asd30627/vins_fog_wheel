#!/usr/bin/env python3
"""extract_reliability_dataset.py — DRAFT(等 schema 經使用者確認才執行)。

把每個 KAIST run 的 per-keyframe reliability_features_vins.csv 切成 5s sliding window,
產出 features + labels 的 tabular dataset(TSV)。
- input(每個 run 一個 dst 目錄):reliability_features.csv(harness 已加 cp);vio.tum;vins.log(選,opt-cost)。
- 對每條序列 × 每個 grade × rep 跑;最後做跨 grade 對齊算 grade_sensitive。
- GT 不進 feature。labels 用未來/跨 grade 資訊(合法,事後)。

⚠ 對應 RELIABILITY_DATASET_SCHEMA.md。schema 未確認前**請勿執行**(此檔僅供審閱 schema 的可操作定義)。
"""
import argparse, csv, glob, os, sys
import numpy as np

P1H = "/mnt/sata4t/ivlab3_data/fwvio/results/p1_grade_hard"
P1E = "/mnt/sata4t/ivlab3_data/fwvio/results/p1_grade"   # easy seqs (urban26-29)
WIN_S, STRIDE_S, MIN_KF = 5.0, 1.0, 25
ACC_THR, GYR_THR = 2.5, 1.0   # estimator failureDetection 常數

# grade Allan 參數(real = KVH FOG 近似;injected = gen_kaist_grade_fog.PROFILES)— real 值待使用者確認
GRADE_PARAMS = {
    "kaist_real_005": dict(arw=0.012, bias=0.05, brw=0.0,   scale_ppm=50),   # ⚠ real 近似,待確認
    "industrial_fog": dict(arw=0.03,  bias=0.3,  brw=0.005, scale_ppm=200),
    "precision_mems": dict(arw=0.15,  bias=5.0,  brw=0.05,  scale_ppm=1000),
    "general_imu":    dict(arw=0.3,   bias=10.0, brw=0.1,   scale_ppm=2000),
}

def fcol(rows, name, default=np.nan):
    out = []
    for r in rows:
        try: out.append(float(r.get(name, default)))
        except (TypeError, ValueError): out.append(default)
    return np.array(out, float)

def slope(t, y):
    m = np.isfinite(y)
    if m.sum() < 3: return 0.0
    t0 = t[m] - t[m][0]
    return float(np.polyfit(t0, y[m], 1)[0])

def agg(rows, ts):
    """window 內 feature 聚合 → dict。"""
    g = lambda n: fcol(rows, n)
    ba, bg = g("ba_norm"), g("bg_norm")
    good, bad = g("good_depth_count"), g("bad_depth_count")
    denom = np.where((good+bad) > 0, good+bad, np.nan)
    f = {}
    # A visual
    f["feat_raw_mean"]   = np.nanmean(g("tracked_feature_count_raw"))
    f["feat_mgr_mean"]   = np.nanmean(g("tracked_feature_count_mgr"))
    f["feat_mgr_last"]   = g("tracked_feature_count_mgr")[-1]
    f["outlier_ratio_mean"] = np.nanmean(g("outlier_ratio_last"))
    f["outlier_ratio_max"]  = np.nanmax(g("outlier_ratio_last"))
    f["inlier_count_mean"]  = np.nanmean(g("inlier_count_last"))
    f["coverage8_mean"]  = np.nanmean(g("coverage_8x8"))
    f["entropy8_mean"]   = np.nanmean(g("feature_entropy_8x8"))
    f["reproj_res_mean"] = np.nanmean(g("vg_flow_res_mean"))
    f["avg_track_len_mean"] = np.nanmean(g("avg_track_length"))
    f["good_depth_ratio_mean"] = np.nanmean(good/denom)
    f["visual_gate_pass_rate"] = np.nanmean(g("visual_gate_pass"))
    f["visual_alpha_mean"] = np.nanmean(g("visual_alpha"))
    # B FOG-vision disagreement
    f["yaw_disagree_mean"] = np.nanmean(g("gyro_vins_so3_diff_deg"))
    f["yaw_disagree_max"]  = np.nanmax(g("gyro_vins_so3_diff_deg"))
    f["yaw_disagree_norm_mean"] = np.nanmean(g("gyro_vins_rotvec_diff_norm_deg"))
    # C inertial bias (★)
    f["ba_norm_mean"] = np.nanmean(ba); f["ba_norm_last"] = ba[-1]; f["ba_norm_max"] = np.nanmax(ba)
    f["ba_norm_slope"] = slope(ts, ba)
    f["bg_norm_mean"] = np.nanmean(bg); f["bg_norm_last"] = bg[-1]; f["bg_norm_max"] = np.nanmax(bg)
    f["bg_norm_slope"] = slope(ts, bg)
    # D solver
    f["solver_ms_mean"] = np.nanmean(g("solver_time_ms_last"))
    # E motion excitation
    f["vel_norm_mean"]   = np.nanmean(g("vel_norm"))
    f["delta_p_norm_mean"] = np.nanmean(g("delta_p_norm"))
    f["acc_norm_mean"] = np.nanmean(g("acc_norm_mean")); f["acc_norm_std"] = np.nanmean(g("acc_norm_std")); f["acc_norm_max"] = np.nanmax(g("acc_norm_max"))
    f["gyr_norm_mean"] = np.nanmean(g("gyr_norm_mean")); f["gyr_norm_max"] = np.nanmax(g("gyr_norm_max"))
    f["yaw_rate_mean"] = np.nanmean(g("gyr_z_mean")); f["yaw_rate_std"] = np.nanstd(g("gyr_z_mean"))
    return f

def load_run(dst):
    csvf = os.path.join(dst, "reliability_features.csv")
    if not os.path.isfile(csvf): return None
    with open(csvf) as fh: rows = list(csv.DictReader(fh))
    if len(rows) < MIN_KF: return None
    ts = fcol(rows, "timestamp")
    fd = fcol(rows, "failure_detected_last")
    # derive failure also directly from thresholds (robust to column semantics)
    ba, bg = fcol(rows, "ba_norm"), fcol(rows, "bg_norm")
    fd = np.where((fd > 0) | (ba > ACC_THR) | (bg > GYR_THR), 1, 0)
    return dict(rows=rows, ts=ts, fd=fd, t0=ts[0], tmax=ts[-1])

def windows(run, seq, grade, rep):
    rows, ts, fd, t0, tmax = run["rows"], run["ts"], run["fd"], run["t0"], run["tmax"]
    ba_full = fcol(rows, "ba_norm")
    out = []
    t_end = t0 + WIN_S
    while t_end <= tmax:
        m = (ts > t_end - WIN_S) & (ts <= t_end)
        if m.sum() >= MIN_KF:
            wr = [rows[i] for i in np.where(m)[0]]; wts = ts[m]
            f = agg(wr, wts)
            # labels
            fut30 = (ts > t_end) & (ts <= t_end + 30.0)
            lab_fail30 = int(fd[fut30].sum() > 0)
            lab_surv60 = int(tmax >= t_end + 60.0)
            # current margin (= 2.5 - ba_norm_last) is an IDENTITY of a feature -> sanity only.
            lab_accmargin = ACC_THR - f["ba_norm_last"]
            # ★ early-warning target: worst (min) margin reached over next 30s, predicted from CURRENT features.
            # No future rows -> assume no change (fall back to current). n_future recorded for honest filtering.
            ba_fut = ba_full[fut30]
            n_fut = int(fut30.sum())
            ba_fut_max = float(np.nanmax(ba_fut)) if n_fut > 0 else f["ba_norm_last"]
            lab_accmargin_min30 = ACC_THR - ba_fut_max
            gp = GRADE_PARAMS.get(grade, {})
            rec = dict(dataset="kaist", sequence=seq, grade=grade, rep=rep,
                       t_end=round(float(t_end), 3), tau=round(float(t_end - t0), 3),
                       n_future_kf=n_fut,
                       grade_arw=gp.get("arw"), grade_bias=gp.get("bias"),
                       grade_brw=gp.get("brw"), grade_scale_ppm=gp.get("scale_ppm"),
                       **{k: (round(float(v), 6) if np.isfinite(v) else "") for k, v in f.items()},
                       failure_in_30s=lab_fail30, survival_60s=lab_surv60,
                       acc_bias_margin=round(float(lab_accmargin), 6),
                       acc_margin_min30=round(float(lab_accmargin_min30), 6),
                       grade_sensitive="")  # filled by Q5 pass
            out.append(rec)
        t_end += STRIDE_S
    return out

def add_grade_sensitive(records):
    """Q5 (user-specified): grade_sensitive positives ONLY for urban38-pankyo real-grade
    windows with tau in [870, 931]; everything else 0."""
    for r in records:
        r["grade_sensitive"] = int(
            r["sequence"] == "urban38-pankyo"
            and r["grade"] == "kaist_real_005"
            and 870.0 <= r["tau"] <= 931.0
        )

def discover(seq):
    # all 12 seqs re-run into p1_grade_hard with CSV-copy
    return sorted(glob.glob(f"{P1H}/{seq}/*_rep*"))

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seqs", nargs="*", default=None)
    ap.add_argument("--out", default="/home/ivlab3/fwvio_estimator_ws_wheel/kaist_grade_scripts/reliability_dataset.tsv")
    a = ap.parse_args()
    HARD = ["urban18-highway","urban19-highway","urban20-highway","urban21-highway",
            "urban22-highway","urban24-highway","urban30-gangnam","urban38-pankyo"]
    EASY = ["urban26-dongtan","urban27-dongtan","urban28-pankyo","urban29-pankyo"]
    seqs = a.seqs or (EASY + HARD)
    records, missing = [], []
    for seq in seqs:
        for dst in discover(seq):
            name = os.path.basename(dst)            # e.g. industrial_fog_rep0
            grade = "_".join(name.split("_")[:-1]); rep = name.split("_")[-1]
            run = load_run(dst)
            if run is None: missing.append(dst); continue
            records += windows(run, seq, grade, rep)
    add_grade_sensitive(records)
    if not records:
        print("NO RECORDS — likely reliability_features.csv missing (need CSV-copy re-run).")
        for m in missing[:20]: print("  missing/short:", m)
        sys.exit(1)
    cols = list(records[0].keys())
    with open(a.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, delimiter="\t"); w.writeheader()
        for r in records: w.writerow(r)
    print(f"wrote {len(records)} windows -> {a.out}  (missing/short runs: {len(missing)})")
