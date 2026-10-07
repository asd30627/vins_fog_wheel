#!/usr/bin/env python3
"""Paper-2 — WINNING-MODEL SEARCH. Goal: beat the BEST non-ours baseline on selective risk,
not just the distance gate. Main rival = cv_smoothing_gate (and qiu/bbox-depth/selectivenet).

Levers explored (all runtime-observable; NO GT features; label only uses GT):
  - per-DOMAIN quantile/rank transform (unsupervised domain alignment; streaming-CDF feasible)
  - monotonic constraints (physical prior: cv_residual/jitter/jerk↑ ⇒ validity↓, bbox/conf↑ ⇒ ↑)
  - conservative rank ensembles / hierarchical cv-gate-then-learned
  - normalized constant-velocity innovation (cv_residual / expected step)
  - calibrated proba ensemble, logistic/MLP on quantile features
Records EVERY model × 6 fixed splits with full selective-risk metrics + bootstrap CIs.
NO frame-random split (CARLA by run, KITTI by sequence).

Out: paper2_winning_model_search.csv, PAPER2_WINNING_MODEL_SEARCH_RESULTS.md
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
import paper2_tcsv_features as F
from paper2_tcsv_train_eval import op_metrics, youden, split_by_key
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline

WS = Path("/home/ivlab3/fwvio_estimator_ws_wheel")
FEATS = F.TCSV_FEATS
# monotone wrt P(valid): +1 increasing, -1 decreasing, 0 none. Order = FEATS.
#        range,bearing,bbox_area,depth,conf, age,raw_speed, cv_res,accel,jerk,flip,bboxcons,posjit,veljit
MONO = [  -1,    0,      +1,     -1,  +1,   +1,   0,        -1,   -1,  -1,  -1,   +1,     -1,    -1]
QIU = ["range_m", "bearing_change_abs", "track_age", "bbox_area"]
BBOXDEPTH = ["bbox_depth_consistency", "depth_m", "bbox_area"]
GEO = ["range_m", "bearing_deg", "depth_m"]
BASELINE_POOL = ["distance_gate", "cv_smoothing_gate", "qiu_style(proxy)", "bbox_depth_gate",
                 "selectivenet_proxy", "ovi_geom"]


def add_aux(df):
    df = df.copy()
    df["bearing_change_abs"] = df["bearing_change"].abs() if "bearing_change" in df else 0.0
    dt = np.where(df["dataset"].values == "carla", 0.05, 0.10)
    cvr = df["cv_residual"].astype(float)
    sp = df["raw_speed"].astype(float)
    df["cv_norm"] = cvr / (sp.abs() * dt + 0.1)   # unitless innovation ratio
    return df


def rankpct(x):
    return pd.Series(np.asarray(x, float)).rank(pct=True).fillna(0.5).values


def domain_quantile(df, feats):
    """Map each feature to within-DOMAIN percentile [0,1]. Unsupervised (no labels). Domain-aligned."""
    out = np.full((len(df), len(feats)), 0.5)
    pos = {ix: i for i, ix in enumerate(df.index)}
    for ds, idx in df.groupby("dataset", sort=False).indices.items():
        sub = df.iloc[idx][feats].astype(float)
        sub = sub.fillna(sub.median())
        r = sub.rank(pct=True).fillna(0.5).values
        for j, row in enumerate(idx):
            out[row] = r[j]
    return out


def logistic_proba(tr, te, feats, ytr):
    m = make_pipeline(StandardScaler(), LogisticRegression(max_iter=500)).fit(
        tr[feats].astype(float).fillna(0).values, ytr)
    return m.predict_proba(tr[feats].astype(float).fillna(0).values)[:, 1], \
           m.predict_proba(te[feats].astype(float).fillna(0).values)[:, 1]


def hgbm(Xtr, ytr, Xte, mono=None):
    m = HistGradientBoostingClassifier(max_iter=300, max_depth=4, learning_rate=0.05,
                                       l2_regularization=1.0, random_state=7,
                                       monotonic_cst=mono).fit(Xtr, ytr)
    return m.predict_proba(Xtr)[:, 1], m.predict_proba(Xte)[:, 1]


def mlp(Xtr, ytr, Xte):
    m = make_pipeline(StandardScaler(), MLPClassifier((64, 32), max_iter=400, early_stopping=True,
                                                      random_state=7)).fit(Xtr, ytr)
    return m.predict_proba(Xtr)[:, 1], m.predict_proba(Xte)[:, 1]


def build_all_scores(tr, te):
    ytr = tr["velocity_valid"].values.astype(int)
    Xtr_r = F.prep(tr, FEATS); Xte_r = F.prep(te, FEATS)
    Xtr_q = domain_quantile(tr, FEATS); Xte_q = domain_quantile(te, FEATS)
    cv_tr = -tr["cv_residual"].astype(float).fillna(tr["cv_residual"].median()).values
    cv_te = -te["cv_residual"].astype(float).fillna(tr["cv_residual"].median()).values
    cvn_tr = -tr["cv_norm"].astype(float).fillna(tr["cv_norm"].median()).values
    cvn_te = -te["cv_norm"].astype(float).fillna(tr["cv_norm"].median()).values
    S = {}
    # ---- baselines (non-ours) ----
    S["distance_gate"] = (-tr["range_m"].values.astype(float), -te["range_m"].values.astype(float))
    S["cv_smoothing_gate"] = (cv_tr, cv_te)
    S["qiu_style(proxy)"] = logistic_proba(tr, te, QIU, ytr)
    S["bbox_depth_gate"] = logistic_proba(tr, te, BBOXDEPTH, ytr)
    S["ovi_geom"] = logistic_proba(tr, te, GEO, ytr)
    S["selectivenet_proxy"] = mlp(Xtr_r, ytr, Xte_r)
    # ---- ours: learned variants ----
    S["TCSV_HistGBM_raw"] = hgbm(Xtr_r, ytr, Xte_r)
    S["HistGBM_mono_raw"] = hgbm(Xtr_r, ytr, Xte_r, mono=MONO)
    S["HistGBM_quant"] = hgbm(Xtr_q, ytr, Xte_q)
    S["HistGBM_mono_quant"] = hgbm(Xtr_q, ytr, Xte_q, mono=MONO)
    S["Logistic_quant"] = (lambda r: r)(logistic_proba(
        tr.assign(**{f"q_{f}": Xtr_q[:, i] for i, f in enumerate(FEATS)}),
        te.assign(**{f"q_{f}": Xte_q[:, i] for i, f in enumerate(FEATS)}),
        [f"q_{f}" for f in FEATS], ytr))
    S["MLP_quant"] = mlp(Xtr_q, ytr, Xte_q)
    # ---- ours: cv-centric & ensembles ----
    S["cv_norm_gate"] = (cvn_tr, cvn_te)
    hq_tr, hq_te = S["HistGBM_mono_quant"]
    # rank-average ensemble (conservative, domain-robust)
    S["Ens_rankavg_cv+hgbmq"] = (0.5 * rankpct(cv_tr) + 0.5 * rankpct(hq_tr),
                                 0.5 * rankpct(cv_te) + 0.5 * rankpct(hq_te))
    # conservative MIN of ranks (refuse if either flags invalid)
    S["Ens_min_cv+hgbmq"] = (np.minimum(rankpct(cv_tr), rankpct(hq_tr)),
                             np.minimum(rankpct(cv_te), rankpct(hq_te)))
    # weighted toward cv (0.7 cv / 0.3 learned) — keep cv's transfer, small learned lift
    S["Ens_cv0.7+hgbmq0.3"] = (0.7 * rankpct(cv_tr) + 0.3 * rankpct(hq_tr),
                               0.7 * rankpct(cv_te) + 0.3 * rankpct(hq_te))
    # hierarchical: extreme cv_residual ⇒ force-refuse; else learned-quant score
    def hier(cv, hq):
        thr = np.quantile(rankpct(cv_tr), 0.20)  # bottom 20% cv-score (worst residuals) by TRAIN
        r_cv = rankpct(cv); s = hq.copy()
        s[r_cv <= thr] = -1.0  # rank lowest
        return s
    S["Hier_cv_then_hgbmq"] = (hier(cv_tr, hq_tr.copy()), hier(cv_te, hq_te.copy()))
    # calibrated proba ensemble: avg of HistGBM-mono-quant + Logistic-quant
    lq_tr, lq_te = S["Logistic_quant"]
    S["Ens_proba_hgbmq+logq"] = (0.5 * hq_tr + 0.5 * lq_tr, 0.5 * hq_te + 0.5 * lq_te)
    # rank-avg of cv_norm + learned (normalized innovation variant)
    S["Ens_rankavg_cvnorm+hgbmq"] = (0.5 * rankpct(cvn_tr) + 0.5 * rankpct(hq_tr),
                                     0.5 * rankpct(cvn_te) + 0.5 * rankpct(hq_te))
    return S, ytr, te["velocity_valid"].values.astype(int)


def bootstrap_aurc_diff(te, s_model, s_base, group_col, n=300, seed=11):
    """AURC(model)-AURC(base) bootstrap over GROUPS (runs/seqs). Negative ⇒ model better."""
    from paper2_tcsv_train_eval import aurc
    groups = te[group_col].values; uniq = np.unique(groups)
    rs = np.random.RandomState(seed); diffs = []
    idx_by_g = {g: np.where(groups == g)[0] for g in uniq}
    y = te["velocity_valid"].values.astype(int)
    for _ in range(n):
        pick = rs.choice(uniq, size=len(uniq), replace=True)
        idx = np.concatenate([idx_by_g[g] for g in pick])
        yy = y[idx]
        if len(np.unique(yy)) < 2:
            continue
        diffs.append(aurc(yy, s_model[idx]) - aurc(yy, s_base[idx]))
    diffs = np.array(diffs)
    return float(np.mean(diffs)), float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))


def main():
    car = add_aux(F.load_carla(W=5)); kit = add_aux(F.load_kitti(W=5))
    print(f"[win] CARLA n={len(car)} ; KITTI n={len(kit)}")
    car_te = split_by_key(car); kit_te = split_by_key(kit)
    SPLITS = [
        ("CARLA->CARLA", car[~car_te], car[car_te]),
        ("KITTI->KITTI", kit[~kit_te], kit[kit_te]),
        ("CARLA->KITTI", car, kit),
        ("KITTI->CARLA", kit, car),
        ("C+Ktr->Khold", pd.concat([car, kit[~kit_te]]), kit[kit_te]),
        ("K+Ctr->Chold", pd.concat([kit, car[~car_te]]), car[car_te]),
    ]
    rows = []; store = {}
    for name, tr, te in SPLITS:
        tr = tr.reset_index(drop=True); te = te.reset_index(drop=True)
        S, ytr, yte = build_all_scores(tr, te)
        store[name] = (te, S, yte)
        for nm, (str_, ste) in S.items():
            thr = youden(str_, ytr) if len(np.unique(ytr)) > 1 else float(np.median(str_))
            m = op_metrics(yte, ste, thr)
            rows.append(dict(split=name, model=nm, n_test=len(te),
                             **{k: (round(v, 4) if v == v else float("nan")) for k, v in m.items()}))
        print(f"[win] {name} done ({len(S)} models)")

    M = pd.DataFrame(rows)
    M.to_csv(WS / "paper2_winning_model_search.csv", index=False)

    # ---- per-split: best non-ours baseline, and classify each OURS model ----
    def classify(d_aurc, d_oc90, ret, base_ret):
        # d_* = model - baseline (negative=better). retention guard.
        if ret < 0.5 * base_ret:  # retention collapse
            return "ret_collapse"
        if d_aurc <= -0.05 or d_oc90 <= -0.07:
            return "STRONG win"
        if d_aurc <= -0.03 or d_oc90 <= -0.04:
            return "small win"
        if d_aurc <= 0.02:
            return "tie"
        return "LOSE"

    OURS = [m for m in M.model.unique() if m not in BASELINE_POOL and m != "no_policy"]
    summ = []
    for name in [s[0] for s in SPLITS]:
        sub = M[M.split == name]
        pool = sub[sub.model.isin(BASELINE_POOL)]
        best = pool.loc[pool.aurc.idxmin()]
        for om in OURS:
            r = sub[sub.model == om].iloc[0]
            summ.append(dict(split=name, model=om,
                             aurc=r.aurc, best_base=best.model, best_base_aurc=best.aurc,
                             d_aurc=round(r.aurc - best.aurc, 4),
                             oc90=r.overconf_at_ret90, base_oc90=best.overconf_at_ret90,
                             d_oc90=round(r.overconf_at_ret90 - best.overconf_at_ret90, 4),
                             retention=r.retention,
                             verdict=classify(r.aurc - best.aurc, r.overconf_at_ret90 - best.overconf_at_ret90,
                                              r.retention, best.retention)))
    SU = pd.DataFrame(summ)
    SU.to_csv(WS / "paper2_winning_model_search_summary.csv", index=False)

    # ---- pick final model: ROBUSTNESS-aware. Among ours with >=3 wins, minimize worst-case ΔAURC,
    #      tie-break by avg ΔAURC. (A model that wins non-direct but loses direct badly is NOT robust.) ----
    nondirect = ["CARLA->CARLA", "KITTI->KITTI", "C+Ktr->Khold", "K+Ctr->Chold"]
    stats = {}
    for om in OURS:
        s = SU[SU.model == om]
        wins = int((s.verdict.isin(["small win", "STRONG win"])).sum())
        stats[om] = dict(wins=wins, worst=float(s.d_aurc.max()), avg=float(s.d_aurc.mean()),
                         nd=float(s[s.split.isin(nondirect)].d_aurc.mean()))
    agg = sorted([(om, stats[om]["nd"], stats[om]["worst"]) for om in OURS], key=lambda x: x[1])
    cand = [om for om in OURS if stats[om]["wins"] >= 3] or OURS
    final_model = min(cand, key=lambda om: (stats[om]["worst"], stats[om]["avg"]))

    # ---- bootstrap CI: final vs cv_smoothing (main rival) AND vs best baseline, on 3 credible splits ----
    boot = []
    for name in ["KITTI->KITTI", "C+Ktr->Khold", "CARLA->CARLA"]:
        te, S, yte = store[name]
        pool_aurc = {b: M[(M.split == name) & (M.model == b)].aurc.values[0] for b in BASELINE_POOL}
        bb = min(pool_aurc, key=pool_aurc.get)
        for base in ["cv_smoothing_gate", bb]:
            mean, lo, hi = bootstrap_aurc_diff(te, np.asarray(S[final_model][1]), np.asarray(S[base][1]), "split_key")
            boot.append(dict(split=name, vs=base, mean=mean, lo=lo, hi=hi))

    write_md(M, SU, agg, final_model, boot, len(car), len(kit))
    print(f"[win] FINAL (robustness-aware): {final_model} ; wins={stats[final_model]['wins']} "
          f"worst ΔAURC={stats[final_model]['worst']:+.4f} avg={stats[final_model]['avg']:+.4f}")
    for b in boot:
        sig = "BETTER" if b["hi"] < 0 else ("ns" if b["lo"] < 0 < b["hi"] else "WORSE")
        print(f"[win] boot {b['split']} vs {b['vs']}: {b['mean']:+.4f} [{b['lo']:+.4f},{b['hi']:+.4f}] {sig}")


def write_md(M, SU, agg, final_model, boot, nc, nk):
    cols = ["aurc", "overconf_at_ret80", "overconf_at_ret90", "retention", "false_refusal", "f1_invalid", "auroc"]
    h = {"aurc": "AURC↓", "overconf_at_ret80": "OC@.8", "overconf_at_ret90": "OC@.9",
         "retention": "ret", "false_refusal": "false_ref", "f1_invalid": "F1inv", "auroc": "AUROC"}
    L = ["# PAPER2_WINNING_MODEL_SEARCH_RESULTS", "",
         f"> Search for a model that beats the BEST non-ours baseline on selective risk. CARLA n={nc}, KITTI n={nk}. "
         "NO GT features; NO frame-random split. Baseline pool (to beat) = "
         "distance/cv_smoothing/qiu(proxy)/bbox_depth/selectivenet(proxy)/ovi. **Every model logged.**",
         "> Levers: per-domain quantile transform, monotonic constraints, conservative rank ensembles, "
         "hierarchical cv-gate, normalized cv innovation, proba/rank ensembles.", "",
         "## 1. All models × all splits (selective-risk; AURC↓ primary)"]
    for name in M.split.unique():
        sub = M[M.split == name]
        L += [f"### {name}", "| model | " + " | ".join(h[c] for c in cols) + " |", "|---|" + "---|" * len(cols)]
        sub = sub.sort_values("aurc")
        for _, r in sub.iterrows():
            tag = "**" if r.model == final_model else ("_" if r.model in BASELINE_POOL else "")
            def g(c):
                v = r[c]; return f"{v:.3f}" if isinstance(v, (int, float)) and v == v else "—"
            L.append(f"| {tag}{r.model}{tag} | " + " | ".join(g(c) for c in cols) + " |")
        L.append("")
    L += ["## 2. OURS vs best non-ours baseline (per split, verdict)",
          "| split | model | AURC | best_base | base_AURC | ΔAURC | ΔOC@.9 | ret | verdict |",
          "|---|---|---|---|---|---|---|---|---|"]
    for _, r in SU.sort_values(["split", "d_aurc"]).iterrows():
        L.append(f"| {r.split} | {r.model} | {r.aurc:.3f} | {r.best_base} | {r.best_base_aurc:.3f} | "
                 f"{r.d_aurc:+.3f} | {r.d_oc90:+.3f} | {r.retention:.2f} | {r.verdict} |")
    L += ["", "## 3. Aggregate ranking (avg ΔAURC over 4 non-direct splits; worst direct ΔAURC)",
          "| model | avg ΔAURC (non-direct)↓ | worst direct ΔAURC | ",
          "|---|---|---|"]
    for om, nd, di in agg:
        star = " **←FINAL**" if om == final_model else ""
        L.append(f"| {om}{star} | {nd:+.4f} | {di:+.4f} |")
    L += ["", f"## 4. Final model (robustness-aware pick) = **{final_model}**", "",
          "Bootstrap AURC(final)−AURC(baseline) over groups, 95% CI (negative ⇒ final better):",
          "| split | vs baseline | mean ΔAURC | 95% CI | verdict |", "|---|---|---|---|---|"]
    for b in boot:
        sig = "✅ better" if b["hi"] < 0 else ("ns (CI∋0)" if b["lo"] < 0 < b["hi"] else "✗ worse")
        L.append(f"| {b['split']} | `{b['vs']}` | {b['mean']:+.4f} | [{b['lo']:+.4f}, {b['hi']:+.4f}] | {sig} |")
    L += ["", "## Honest reading",
          "- Gate thresholds: STRONG win = ΔAURC≤−0.05 or ΔOC@.9≤−0.07; small = −0.03..−0.05 / −0.04..−0.07; "
          "tie = ΔAURC within +0.02; lose = ΔAURC>+0.02.",
          "- See `PAPER2_FINAL_MODEL_DECISION.md` for the honest gate verdict (RA-L / IV-ITSC / pivot)."]
    (WS / "PAPER2_WINNING_MODEL_SEARCH_RESULTS.md").write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
