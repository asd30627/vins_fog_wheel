#!/usr/bin/env python3
"""Paper-2 v5 — Selective Object State Validity model. STANDALONE; no backend.

Change: paper2-observability-aware-object-validity-v5.

Learns velocity_valid (and position_valid) from runtime-observable features, with emphasis on TEMPORAL
consistency of the raw estimate (raw_speed, raw_accel, velocity smoothness) — the lever most likely to
beat a pure distance gate. Trains logistic / logistic+interactions / HistGradientBoosting / small MLP and
compares against baselines (distance-gate, OVI-geometric). Splits: CARLA by RUN, KITTI by SEQUENCE, +
cross-dataset (CARLA->KITTI, CARLA+KITTI-train -> held-out KITTI seqs). NO frame random split.
Reports AUROC velocity_valid, F1 invalid_velocity, overconfident-wrong-velocity, retention, false-refusal,
planner-usable, per distance bin. Honest: if it cannot beat the distance gate, says so.
Output: PAPER2_SELECTIVE_VALIDITY_RESULTS.md + paper2_selective_validity_metrics.csv
"""
from __future__ import annotations
import math
from pathlib import Path
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler, PolynomialFeatures
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.metrics import roc_auc_score, f1_score, roc_curve
from sklearn.pipeline import make_pipeline

WS = Path("/home/ivlab3/fwvio_estimator_ws_wheel")
COMMON = ["range_m", "bearing_deg", "bbox_area", "depth_m", "track_age",
          "raw_speed", "raw_accel", "vel_smooth", "det_conf", "bearing_change"]
BINS = ["0-15m", "15-30m", "30m+"]
POS_T, VEL_T = 3.0, 3.0


def temporal(df, posx, posz, dt, frame="frame", group=("run", "track_id")):
    """add raw_speed, raw_accel, vel_smooth per track (sorted by frame)."""
    df = df.sort_values(list(group) + [frame]).copy()
    sp = np.full(len(df), np.nan); ac = np.full(len(df), np.nan); sm = np.full(len(df), np.nan)
    bc = np.full(len(df), np.nan); tage = np.zeros(len(df))
    idx = df.index.to_numpy()
    gi = df.groupby(list(group), sort=False).indices
    X = df[posx].to_numpy(); Z = df[posz].to_numpy(); FR = df[frame].to_numpy()
    BR = df["bearing_deg"].to_numpy() if "bearing_deg" in df else np.zeros(len(df))
    for key, rows in gi.items():
        rows = list(rows)
        vels = [None] * len(rows)
        for i in range(len(rows)):
            tage[rows[i]] = i
            if i >= 1 and (FR[rows[i]] - FR[rows[i-1]]) == 1:
                vx = (X[rows[i]] - X[rows[i-1]]) / dt; vz = (Z[rows[i]] - Z[rows[i-1]]) / dt
                vels[i] = (vx, vz); sp[rows[i]] = math.hypot(vx, vz)
                bc[rows[i]] = BR[rows[i]] - BR[rows[i-1]]
                if i >= 2 and vels[i-1] is not None:
                    ax = (vx - vels[i-1][0]) / dt; az = (vz - vels[i-1][1]) / dt
                    ac[rows[i]] = math.hypot(ax, az)
            # smoothness = std of last up-to-4 raw speeds
            sps = [sp[rows[j]] for j in range(max(0, i-3), i+1) if sp[rows[j]] == sp[rows[j]]]
            if len(sps) >= 2:
                sm[rows[i]] = float(np.std(sps))
    df["raw_speed"] = sp; df["raw_accel"] = ac; df["vel_smooth"] = sm
    df["track_age"] = tage
    if "bearing_change" not in df:
        df["bearing_change"] = bc
    return df


def load_carla():
    d = pd.read_csv(WS / "paper2_raw_object_benchmark_all_with_vins.csv", low_memory=False)
    d = d[d["matched"] == 1].copy()
    for c in ["pos_err_m", "raw_speed_ms", "gt_speed_ms", "dir_err_deg", "body_fwd", "body_lat",
              "range_m", "bearing_deg", "bbox_area", "depth_m", "frame", "track_id", "conf"]:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d[d["pos_err_m"].notna() & d["body_fwd"].notna()].copy()
    d["det_conf"] = d["conf"]
    # velocity validity via ego-independent vel_err (cosine law)
    rs, gs, dr = d["raw_speed_ms"], d["gt_speed_ms"], np.radians(d["dir_err_deg"])
    vel_err = np.sqrt(np.clip(rs**2 + gs**2 - 2*rs*gs*np.cos(dr), 0, None))
    d["has_v"] = (d["raw_speed_ms"].notna() & d["gt_speed_ms"].notna() & d["dir_err_deg"].notna()).astype(int)
    d["position_valid"] = (d["pos_err_m"] <= POS_T).astype(int)
    d["velocity_valid"] = np.where(d["has_v"] == 1, (vel_err <= VEL_T).astype(int), 0)
    d = temporal(d, "body_lat", "body_fwd", 0.05, group=("run", "track_id"))
    d["split_key"] = d["town"].astype(str) + "@" + d["run"].astype(str)
    d["dataset"] = "carla"
    return d


def load_kitti():
    d = pd.read_csv(WS / "paper2_kitti_validity_dataset.csv", low_memory=False)
    for c in ["pos_err_m", "vel_err_ms", "range_m", "bearing_deg", "bbox_area", "depth_m", "frame",
              "tid", "det_conf", "raw_x", "raw_z"]:
        if c in d: d[c] = pd.to_numeric(d[c], errors="coerce")
    d["track_id"] = d["tid"]; d["run"] = d["seq"].astype(str)
    d["has_v"] = d["vel_err_ms"].notna().astype(int)
    d["position_valid"] = (d["pos_err_m"] <= POS_T).astype(int)
    d["velocity_valid"] = np.where(d["has_v"] == 1, (d["vel_err_ms"] <= VEL_T).astype(int), 0)
    d = temporal(d, "raw_x", "raw_z", 0.1, group=("seq", "track_id"))
    d["split_key"] = "kitti@" + d["seq"].astype(str)
    d["dataset"] = "kitti"
    return d


def prep(df):
    X = df[COMMON].astype(float)
    X = X.fillna(X.median(numeric_only=True)).fillna(0.0)
    return X.values


def split_by_key(df, seed=7, frac=0.25):
    keys = sorted(df["split_key"].unique())
    rs = np.random.RandomState(seed); rs.shuffle(keys)
    nt = max(1, int(len(keys) * frac)); test = set(keys[:nt])
    return df["split_key"].isin(test).values


def metrics(y, score, thr=None):
    y = y.astype(int)
    auc = roc_auc_score(y, score) if len(np.unique(y)) > 1 else float("nan")
    # operating point: train-Youden passed in via thr; else use median
    if thr is None: thr = np.median(score)
    emit = score >= thr     # emit velocity if predicted valid
    inv = 1 - y
    oc = float(inv[emit].mean()) if emit.any() else float("nan")          # overconfident-wrong among emitted
    ret = float(emit[y == 1].sum() / max((y == 1).sum(), 1))             # valid retention
    rec_inv = float((~emit)[inv == 1].sum() / max((inv == 1).sum(), 1))  # invalid recall
    f1 = f1_score(inv, (~emit).astype(int), zero_division=0)
    return dict(auroc=auc, overconf=oc, retention=ret, invalid_recall=rec_inv, false_refusal=1-ret, f1_invalid=f1)


def fit_models(Xtr, ytr):
    out = {}
    out["logistic"] = make_pipeline(StandardScaler(), LogisticRegression(max_iter=500)).fit(Xtr, ytr)
    out["logistic_interact"] = make_pipeline(StandardScaler(), PolynomialFeatures(2, interaction_only=True, include_bias=False),
                                             LogisticRegression(max_iter=1000)).fit(Xtr, ytr)
    out["hist_gbm"] = HistGradientBoostingClassifier(max_iter=300, max_depth=4, learning_rate=0.05,
                                                     l2_regularization=1.0).fit(Xtr, ytr)
    out["mlp"] = make_pipeline(StandardScaler(), MLPClassifier((64, 32), max_iter=400, early_stopping=True)).fit(Xtr, ytr)
    return out


def main():
    car = load_carla(); kit = load_kitti()
    print(f"[sel] CARLA n={len(car)} vel_valid={car.velocity_valid.mean():.3f} ; KITTI n={len(kit)} vel_valid={kit.velocity_valid.mean():.3f}")
    rows = []

    def youden(score, y):
        fpr, tpr, th = roc_curve(y, score); return th[np.argmax(tpr - fpr)]

    def run_scenario(name, tr_df, te_df):
        Xtr, ytr = prep(tr_df), tr_df["velocity_valid"].values.astype(int)
        Xte, yte = prep(te_df), te_df["velocity_valid"].values.astype(int)
        geo = ["range_m", "bearing_deg", "depth_m"]
        ovi = make_pipeline(StandardScaler(), LogisticRegression(max_iter=500)).fit(tr_df[geo].fillna(0).values, ytr)
        models = fit_models(Xtr, ytr)
        # (train_score, test_score) per model
        scores = {"distance_gate": (-tr_df["range_m"].values, -te_df["range_m"].values),
                  "OVI_geom": (ovi.predict_proba(tr_df[geo].fillna(0).values)[:, 1],
                               ovi.predict_proba(te_df[geo].fillna(0).values)[:, 1])}
        for nm, m in models.items():
            scores[f"selective_{nm}"] = (m.predict_proba(Xtr)[:, 1], m.predict_proba(Xte)[:, 1])
        for nm, (str_, ste) in scores.items():
            thr = youden(str_, ytr) if len(np.unique(ytr)) > 1 else float(np.median(str_))
            mt = metrics(yte, ste, thr)
            rows.append(dict(scenario=name, model=nm, n_test=len(te_df), **{k: round(v, 4) for k, v in mt.items()}))

    # scenarios
    car_te = split_by_key(car); kit_te = split_by_key(kit)
    run_scenario("CARLA->CARLA(run)", car[~car_te], car[car_te])
    run_scenario("KITTI->KITTI(seq)", kit[~kit_te], kit[kit_te])
    run_scenario("CARLA->KITTI", car, kit)
    run_scenario("CARLA+KITtrain->KIThold", pd.concat([car, kit[~kit_te]]), kit[kit_te])

    M = pd.DataFrame(rows); M.to_csv(WS / "paper2_selective_validity_metrics.csv", index=False)
    # decide: best selective vs distance_gate AUROC per scenario
    L = ["# PAPER2_SELECTIVE_VALIDITY_RESULTS", "",
         f"> Selective velocity-validity model vs baselines. CARLA n={len(car)}, KITTI n={len(kit)}. "
         "Splits: CARLA by run, KITTI by sequence (NO frame random). Velocity criterion = ego-independent vel_err≤3 m/s.",
         f"> Features (common): {COMMON}", "",
         "## AUROC (velocity_valid) + refusal metrics by scenario",
         "| scenario | model | AUROC | overconf | retention | false_refusal | F1_invalid |", "|---|---|---|---|---|---|---|"]
    for _, r in M.iterrows():
        L.append(f"| {r.scenario} | {r.model} | {r.auroc:.3f} | {r.overconf:.3f} | {r.retention:.3f} | {r.false_refusal:.3f} | {r.f1_invalid:.3f} |")
    L += ["", "## Does the selective model BEAT the distance gate? (AUROC)", "| scenario | distance_gate | best_selective | Δ | verdict |", "|---|---|---|---|---|"]
    verdicts = []
    for sc in M.scenario.unique():
        ms = M[M.scenario == sc]; dg = ms[ms.model == "distance_gate"].auroc.values[0]
        sel = ms[ms.model.str.startswith("selective")]
        best = sel.loc[sel.auroc.idxmax()]
        d = best.auroc - dg; v = "BEATS" if d > 0.02 else ("ties" if d > -0.02 else "loses")
        verdicts.append((sc, v, d))
        L.append(f"| {sc} | {dg:.3f} | {best.model}={best.auroc:.3f} | {d:+.3f} | **{v}** |")
    nbeat = sum(1 for _, v, _ in verdicts if v == "BEATS")
    L += ["", "## Honest verdict",
          f"- selective model BEATS distance gate (Δ>0.02 AUROC) in **{nbeat}/{len(verdicts)}** scenarios.",
          "- if it beats in-domain (CARLA->CARLA, KITTI->KITTI) the temporal/observability features add real signal beyond distance;",
          "- cross-dataset (CARLA->KITTI) tests generalization of the learned validity boundary.",
          "- if it does NOT beat distance gate, the honest conclusion: validity is largely distance/geometry-determined; "
          "report the phenomenon + a simple gate, NOT a model, as the contribution."]
    (WS / "PAPER2_SELECTIVE_VALIDITY_RESULTS.md").write_text("\n".join(L) + "\n")
    print("[sel] verdicts:", verdicts)


if __name__ == "__main__":
    main()
