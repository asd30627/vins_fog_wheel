#!/usr/bin/env python3
"""Paper-2 Track A — SEQUENCE-LEVEL object-state validity, feasibility experiment.

Question: does giving the model the RAW T-frame per-object sequence buy anything over the
incumbent TCSV-M (HistGBM-mono on hand-crafted W=5 temporal-consistency SUMMARIES)?

Decisive no-torch gate: a model with FULL access to all T frames' raw features (flattened MLP
and pooled-stat HistGBM/MLP) is an upper proxy for what a GRU/TCN could extract from the same
sequence. If these do NOT beat TCSV-M, a deep sequence encoder is very unlikely to, and torch
is not justified. If they show promise, escalate to torch GRU/TCN.

Red lines: NO GT feature (label only uses GT); NO frame-random split (KITTI by seq, CARLA by
run); no backend/object-factor/frontier/HD-map. Primary metric: AURC (lower=better).

Out (under paper2/track_a/): paper2_sequence_validity_metrics.csv
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np, pandas as pd

WS = Path("/home/ivlab3/fwvio_estimator_ws_wheel")
sys.path.insert(0, str(WS / "scripts"))
import paper2_tcsv_features as F
F.WS = WS / "paper2"   # data CSVs now live in paper2/ (subfolder policy)
from paper2_tcsv_train_eval import aurc, op_metrics, youden, split_by_key
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

OUT = WS / "paper2" / "track_a"
OUT.mkdir(parents=True, exist_ok=True)
T = 5  # sequence window length (matches incumbent W=5)

# per-frame RAW observable features that exist in BOTH datasets post-compute (NO GT)
PERFRAME = ["range_m", "depth_m", "bbox_area", "bearing_deg", "det_conf",
            "raw_speed", "cv_residual", "acceleration_score", "track_age"]
LOG_FEATS = {"range_m", "depth_m", "bbox_area"}
# TCSV-M (incumbent final): 14 summary feats + monotone prior
TCSV_FEATS = F.TCSV_FEATS
#       range,bearing,bbox_area,depth,conf, age,raw_speed, cv_res,accel,jerk,flip,bboxcons,posjit,veljit
MONO = [  -1,    0,      +1,     -1,  +1,   +1,   0,        -1,   -1,  -1,  -1,   +1,     -1,    -1]


def _perframe_matrix(df):
    """Per-row per-frame feature vector (log-transform scale feats)."""
    M = np.zeros((len(df), len(PERFRAME)), float)
    for j, c in enumerate(PERFRAME):
        v = pd.to_numeric(df[c], errors="coerce").to_numpy(float) if c in df else np.full(len(df), np.nan)
        if c in LOG_FEATS:
            v = np.log1p(np.clip(v, 0, None))
        M[:, j] = v
    return M


def build_windows(df, group):
    """For each labeled row build a [T, Ffeat] window of the last T frames of its track
    (edge-padded if shorter). Returns SEQ [N,T,F], idx (row order), and the row df aligned."""
    df = df.sort_values(list(group) + ["frame"]).reset_index(drop=True)
    M = _perframe_matrix(df)
    nF = M.shape[1]
    gi = df.groupby(list(group), sort=False).indices
    SEQ = np.zeros((len(df), T, nF), float)
    for key, rows in gi.items():
        rows = list(rows)
        for pos, r in enumerate(rows):
            lo = pos - T + 1
            window_rows = [rows[max(0, k)] for k in range(lo, pos + 1)]  # edge-pad with earliest
            SEQ[r] = M[window_rows, :]
    return df, SEQ


def pool_stats(SEQ):
    """Temporal-pooling summary per window: mean,std,min,max,last,slope(last-first) per feature."""
    mean = SEQ.mean(1); std = SEQ.std(1); mn = SEQ.min(1); mx = SEQ.max(1)
    last = SEQ[:, -1, :]; slope = SEQ[:, -1, :] - SEQ[:, 0, :]
    return np.concatenate([mean, std, mn, mx, last, slope], axis=1)


def impute(train_X, X):
    med = np.nanmedian(train_X, axis=0)
    med = np.where(np.isfinite(med), med, 0.0)
    Xf = np.where(np.isfinite(X), X, med)
    return Xf


def fit_hgbm(Xtr, ytr, Xte, mono=None):
    m = HistGradientBoostingClassifier(max_iter=300, max_depth=4, learning_rate=0.05,
                                       l2_regularization=1.0, random_state=7,
                                       monotonic_cst=mono).fit(Xtr, ytr)
    return m.predict_proba(Xte)[:, 1]


def fit_mlp(Xtr, ytr, Xte, hidden=(128, 64)):
    m = make_pipeline(StandardScaler(),
                      MLPClassifier(hidden, max_iter=500, early_stopping=True,
                                    alpha=1e-3, random_state=7)).fit(Xtr, ytr)
    return m.predict_proba(Xte)[:, 1]


def boot_aurc_diff(y, sA, sB, ngroups_key, n=300, seed=11):
    """Bootstrap AURC(A)-AURC(B) over GROUPS (runs/seqs), not rows. neg => A better."""
    rs = np.random.RandomState(seed)
    groups = np.asarray(ngroups_key)
    uniq = np.unique(groups)
    diffs = []
    for _ in range(n):
        samp = rs.choice(uniq, size=len(uniq), replace=True)
        mask = np.concatenate([np.where(groups == g)[0] for g in samp])
        diffs.append(aurc(y[mask], sA[mask]) - aurc(y[mask], sB[mask]))
    diffs = np.array(diffs)
    return float(diffs.mean()), float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))


def run():
    car = F.load_carla(W=5); kit = F.load_kitti(W=5)
    car, SEQ_c = build_windows(car, ("town", "run", "track_id"))
    kit, SEQ_k = build_windows(kit, ("seq", "track_id"))
    print(f"[seq] CARLA n={len(car)} vv={car.velocity_valid.mean():.3f} ; "
          f"KITTI n={len(kit)} vv={kit.velocity_valid.mean():.3f} ; T={T} Ffeat={SEQ_c.shape[2]}")

    DATA = {"carla": (car, SEQ_c, ("town", "run", "track_id")),
            "kitti": (kit, SEQ_k, ("seq", "track_id"))}

    def feats_for(df, SEQ):
        flat = SEQ.reshape(len(df), -1)        # [N, T*F]
        pooled = pool_stats(SEQ)               # [N, 6F]
        summ = df[TCSV_FEATS].astype(float).to_numpy()  # incumbent 14 summary feats
        cv = -pd.to_numeric(df["cv_residual"], errors="coerce").to_numpy(float)  # cv gate score
        return flat, pooled, summ, cv

    rows = []
    boot_rows = []

    def eval_split(name, tr_df, tr_SEQ, te_df, te_SEQ, group_for_boot):
        ytr = tr_df["velocity_valid"].to_numpy(int)
        yte = te_df["velocity_valid"].to_numpy(int)
        f_tr, p_tr, s_tr, _ = feats_for(tr_df, tr_SEQ)
        f_te, p_te, s_te, cv_te = feats_for(te_df, te_SEQ)
        # impute (fit on train)
        f_tr_i, f_te_i = impute(f_tr, f_tr), impute(f_tr, f_te)
        p_tr_i, p_te_i = impute(p_tr, p_tr), impute(p_tr, p_te)
        s_tr_i, s_te_i = impute(s_tr, s_tr), impute(s_tr, s_te)

        scores = {}
        scores["cv_smoothing_gate"] = np.nan_to_num(cv_te, nan=np.nanmin(cv_te))
        scores["TCSV-M(hgbm-mono summary)"] = fit_hgbm(s_tr_i, ytr, s_te_i, mono=MONO)
        scores["seq_flat_mlp"] = fit_mlp(f_tr_i, ytr, f_te_i, hidden=(128, 64))
        scores["seq_pool_hgbm"] = fit_hgbm(p_tr_i, ytr, p_te_i)
        scores["seq_pool_mlp"] = fit_mlp(p_tr_i, ytr, p_te_i, hidden=(128, 64))

        for mname, sc in scores.items():
            m = op_metrics(yte, sc, youden(sc, yte))
            rows.append(dict(split=name, model=mname, n=len(yte),
                             base_valid=float(yte.mean()), **{k: round(v, 4) for k, v in m.items()}))
        # bootstrap vs incumbents (only for in-domain, where group structure is meaningful)
        if group_for_boot is not None:
            gk = te_df[list(group_for_boot)].astype(str).agg("@".join, axis=1).to_numpy()
            for cand in ["seq_flat_mlp", "seq_pool_hgbm", "seq_pool_mlp"]:
                for ref in ["TCSV-M(hgbm-mono summary)", "cv_smoothing_gate"]:
                    md, lo, hi = boot_aurc_diff(yte, scores[cand], scores[ref], gk)
                    boot_rows.append(dict(split=name, cand=cand, vs=ref,
                                          dAURC_mean=round(md, 4), ci_lo=round(lo, 4), ci_hi=round(hi, 4),
                                          verdict=("cand_better" if hi < 0 else
                                                   "cand_worse" if lo > 0 else "tie")))
        return scores

    # ---- in-domain (by-group split) ----
    for ds in ["carla", "kitti"]:
        df, SEQ, grp = DATA[ds]
        te = split_by_key(df, seed=7, frac=0.25)
        gboot = grp[:-1] if False else grp  # in-domain bootstrap over its own group keys
        eval_split(f"{ds}->{ds}", df[~te], SEQ[~te], df[te], SEQ[te], gboot)

    # ---- direct cross-dataset ----
    eval_split("carla->kitti", DATA["carla"][0], DATA["carla"][1], DATA["kitti"][0], DATA["kitti"][1], None)
    eval_split("kitti->carla", DATA["kitti"][0], DATA["kitti"][1], DATA["carla"][0], DATA["carla"][1], None)

    # ---- mixed-train -> held-out (C + Ktrain -> Khold) ----
    kdf, kSEQ, kgrp = DATA["kitti"]; cdf, cSEQ, cgrp = DATA["carla"]
    kte = split_by_key(kdf, seed=7, frac=0.25)
    tr_df = pd.concat([cdf, kdf[~kte]], ignore_index=True)
    tr_SEQ = np.concatenate([cSEQ, kSEQ[~kte]], axis=0)
    eval_split("C+Ktr->Khold", tr_df, tr_SEQ, kdf[kte], kSEQ[kte], kgrp)

    R = pd.DataFrame(rows)
    B = pd.DataFrame(boot_rows)
    R.to_csv(OUT / "paper2_sequence_validity_metrics.csv", index=False)
    B.to_csv(OUT / "paper2_sequence_validity_bootstrap.csv", index=False)
    pd.set_option("display.width", 200, "display.max_columns", 30)
    print("\n=== AURC (lower=better) by split x model ===")
    piv = R.pivot(index="split", columns="model", values="aurc")
    print(piv.round(4))
    print("\n=== AUROC ===")
    print(R.pivot(index="split", columns="model", values="auroc").round(4))
    print("\n=== Bootstrap ΔAURC (cand - ref) over groups; neg => cand better ===")
    if len(B):
        print(B.to_string(index=False))
    return R, B


if __name__ == "__main__":
    run()
