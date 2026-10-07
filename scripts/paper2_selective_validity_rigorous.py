#!/usr/bin/env python3
"""Paper-2 — RIGOROUS decision-level evaluation of selective object-state validity.

Upgrades the single-split point estimates in paper2_train_selective_validity.py to
journal-grade rigor, on REAL data with GT (CARLA n~3k velocity rows, KITTI n~37k):

  1. Repeated grouped K-fold CV (group = run / sequence; no leakage) -> mean +/- 95% CI
  2. Paired significance: best-selective & OVI vs distance-gate AUROC across folds (Wilcoxon)
  3. Cross-dataset generalization CARLA->KITTI with bootstrap 95% CI over KITTI sequences
  4. Per-town / per-density stratified AUROC (CARLA)
  5. Threshold ablation: velocity-valid criterion VEL_T in {2,3,5} m/s -> ranking stability
  6. Pareto front: overconfident-wrong-velocity vs valid retention, with CV CI band (figure)

Reuses data loading / features / models / metrics from paper2_train_selective_validity.py.
Outputs: PAPER2_SELECTIVE_VALIDITY_RIGOROUS.md, paper2_rigorous_*.csv, figs/paper2_pareto.png
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.metrics import roc_auc_score, roc_curve, f1_score

WS = Path("/home/ivlab3/fwvio_estimator_ws_wheel")
sys.path.insert(0, str(WS / "scripts"))
import paper2_train_selective_validity as base  # noqa: E402

RNG = np.random.RandomState(20260630)
COMMON = base.COMMON


# ----------------------------------------------------------------- helpers
def youden(score, y):
    if len(np.unique(y)) < 2:
        return float(np.median(score))
    fpr, tpr, th = roc_curve(y, score)
    return th[np.argmax(tpr - fpr)]


def decision_metrics(y, score, thr):
    y = y.astype(int)
    auc = roc_auc_score(y, score) if len(np.unique(y)) > 1 else np.nan
    emit = score >= thr
    inv = 1 - y
    oc = float(inv[emit].mean()) if emit.any() else np.nan        # overconfident-wrong among emitted
    ret = float(emit[y == 1].sum() / max((y == 1).sum(), 1))      # valid retention
    f1 = f1_score(inv, (~emit).astype(int), zero_division=0)
    return dict(auroc=auc, overconf=oc, retention=ret, false_refusal=1 - ret, f1_invalid=f1)


def grouped_folds(groups, n_splits, seed):
    uq = np.array(sorted(pd.unique(groups)))
    rs = np.random.RandomState(seed)
    rs.shuffle(uq)
    chunks = np.array_split(uq, n_splits)
    for ch in chunks:
        test_mask = np.isin(groups, ch)
        if test_mask.sum() == 0 or (~test_mask).sum() == 0:
            continue
        yield ~test_mask, test_mask


def score_models(tr_df, te_df):
    """Return {model: (train_score, test_score)} for distance_gate, OVI_geom, logistic, hist_gbm."""
    Xtr, Xte = base.prep(tr_df), base.prep(te_df)
    ytr = tr_df["velocity_valid"].values.astype(int)
    geo = ["range_m", "bearing_deg", "depth_m"]
    out = {"distance_gate": (-tr_df["range_m"].values, -te_df["range_m"].values)}
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.pipeline import make_pipeline
    if len(np.unique(ytr)) > 1:
        ovi = make_pipeline(StandardScaler(), LogisticRegression(max_iter=500)).fit(
            tr_df[geo].fillna(0).values, ytr)
        out["OVI_geom"] = (ovi.predict_proba(tr_df[geo].fillna(0).values)[:, 1],
                           ovi.predict_proba(te_df[geo].fillna(0).values)[:, 1])
        lg = make_pipeline(StandardScaler(), LogisticRegression(max_iter=500)).fit(Xtr, ytr)
        out["selective_logistic"] = (lg.predict_proba(Xtr)[:, 1], lg.predict_proba(Xte)[:, 1])
        gb = HistGradientBoostingClassifier(max_iter=300, max_depth=4, learning_rate=0.05,
                                            l2_regularization=1.0).fit(Xtr, ytr)
        out["selective_hist_gbm"] = (gb.predict_proba(Xtr)[:, 1], gb.predict_proba(Xte)[:, 1])
    return out


def ci95(vals):
    v = np.asarray([x for x in vals if x == x], float)
    if len(v) == 0:
        return (np.nan, np.nan, np.nan)
    m = v.mean()
    if len(v) < 2:
        return (m, m, m)
    half = stats.t.ppf(0.975, len(v) - 1) * v.std(ddof=1) / np.sqrt(len(v))
    return (m, m - half, m + half)


# ----------------------------------------------------------------- 1+2 repeated CV
def repeated_cv(df, name, n_splits=5, n_repeats=5):
    groups = df["split_key"].values
    per_fold = {}      # model -> list of metric dicts
    for rep in range(n_repeats):
        for tr_m, te_m in grouped_folds(groups, n_splits, seed=1000 + rep):
            tr, te = df[tr_m], df[te_m]
            yte = te["velocity_valid"].values.astype(int)
            ytr = tr["velocity_valid"].values.astype(int)
            if len(np.unique(yte)) < 2:
                continue
            for nm, (str_, ste) in score_models(tr, te).items():
                thr = youden(str_, ytr)
                per_fold.setdefault(nm, []).append(decision_metrics(yte, ste, thr))
    rows = []
    for nm, folds in per_fold.items():
        agg = {"scenario": name, "model": nm, "n_folds": len(folds)}
        for k in ["auroc", "overconf", "retention", "false_refusal", "f1_invalid"]:
            m, lo, hi = ci95([f[k] for f in folds])
            agg[k] = round(m, 4); agg[f"{k}_lo"] = round(lo, 4); agg[f"{k}_hi"] = round(hi, 4)
        rows.append(agg)
    # paired significance vs distance_gate on per-fold AUROC
    sig = []
    if "distance_gate" in per_fold:
        dg = [f["auroc"] for f in per_fold["distance_gate"]]
        for nm in per_fold:
            if nm == "distance_gate":
                continue
            other = [f["auroc"] for f in per_fold[nm]]
            n = min(len(dg), len(other))
            if n >= 6:
                try:
                    W, p = stats.wilcoxon(other[:n], dg[:n])
                except ValueError:
                    p = np.nan
                d = np.mean(other[:n]) - np.mean(dg[:n])
                sig.append(dict(scenario=name, model=nm, dAUROC=round(d, 4),
                                wilcoxon_p=round(float(p), 5) if p == p else np.nan, n_folds=n))
    return rows, sig


# ----------------------------------------------------------------- 3 cross-dataset bootstrap
def cross_dataset(car, kit, n_boot=1000):
    tr, te = car, kit
    yte = te["velocity_valid"].values.astype(int)
    ytr = tr["velocity_valid"].values.astype(int)
    sc = score_models(tr, te)
    groups = te["split_key"].values
    uq = np.array(sorted(pd.unique(groups)))
    rows = []
    for nm, (str_, ste) in sc.items():
        thr = youden(str_, ytr)
        base_auc = roc_auc_score(yte, ste) if len(np.unique(yte)) > 1 else np.nan
        boot = []
        for _ in range(n_boot):
            ch = RNG.choice(uq, size=len(uq), replace=True)
            idx = np.concatenate([np.where(groups == g)[0] for g in ch])
            yb, sb = yte[idx], ste[idx]
            if len(np.unique(yb)) > 1:
                boot.append(roc_auc_score(yb, sb))
        lo, hi = (np.nanpercentile(boot, 2.5), np.nanpercentile(boot, 97.5)) if boot else (np.nan, np.nan)
        mt = decision_metrics(yte, ste, thr)
        rows.append(dict(scenario="CARLA->KITTI", model=nm, n_test=len(te),
                         auroc=round(base_auc, 4), auroc_lo=round(lo, 4), auroc_hi=round(hi, 4),
                         overconf=round(mt["overconf"], 4), retention=round(mt["retention"], 4),
                         false_refusal=round(mt["false_refusal"], 4)))
    return rows


# ----------------------------------------------------------------- 4 stratified
def stratified(car):
    rows = []
    for col in ["town", "density"]:
        for val, sub in car.groupby(col):
            if sub["velocity_valid"].nunique() < 2 or len(sub) < 200:
                continue
            # train on the rest, test on this stratum's groups (held-out by group within stratum)
            for tr_m, te_m in grouped_folds(sub["split_key"].values, 3, seed=7):
                tr, te = sub[tr_m], sub[te_m]
                if te["velocity_valid"].nunique() < 2 or tr["velocity_valid"].nunique() < 2:
                    continue
                yte = te["velocity_valid"].values.astype(int)
                ytr = tr["velocity_valid"].values.astype(int)
                for nm, (str_, ste) in score_models(tr, te).items():
                    if nm not in ("distance_gate", "selective_logistic"):
                        continue
                    mt = decision_metrics(yte, ste, youden(str_, ytr))
                    rows.append(dict(stratum=f"{col}={val}", model=nm, n=len(te),
                                     auroc=mt["auroc"], overconf=mt["overconf"]))
    g = pd.DataFrame(rows)
    if g.empty:
        return g
    return (g.groupby(["stratum", "model"])
            .agg(auroc=("auroc", "mean"), overconf=("overconf", "mean"), n=("n", "sum"))
            .round(4).reset_index())


# ----------------------------------------------------------------- 5 threshold ablation
def ablation(car_loader, kit_loader):
    rows = []
    for vt in [2.0, 3.0, 5.0]:
        base.VEL_T = vt
        car, kit = car_loader(), kit_loader()
        for name, df in [("CARLA", car), ("KITTI", kit)]:
            groups = df["split_key"].values
            best = {}
            for tr_m, te_m in grouped_folds(groups, 5, seed=3):
                tr, te = df[tr_m], df[te_m]
                if te["velocity_valid"].nunique() < 2:
                    continue
                ytr = tr["velocity_valid"].values.astype(int)
                yte = te["velocity_valid"].values.astype(int)
                for nm, (str_, ste) in score_models(tr, te).items():
                    a = roc_auc_score(yte, ste) if len(np.unique(yte)) > 1 else np.nan
                    best.setdefault(nm, []).append(a)
            for nm, aucs in best.items():
                rows.append(dict(VEL_T=vt, dataset=name, model=nm,
                                 auroc=round(np.nanmean(aucs), 4)))
    base.VEL_T = 3.0
    return pd.DataFrame(rows)


# ----------------------------------------------------------------- 6 pareto
def pareto(df, name, model_list, n_splits=5):
    groups = df["split_key"].values
    grid = np.linspace(0, 1, 41)   # emit-fraction targets via score quantiles
    curves = {m: {"ret": [], "oc": []} for m in model_list}
    for tr_m, te_m in grouped_folds(groups, n_splits, seed=11):
        tr, te = df[tr_m], df[te_m]
        yte = te["velocity_valid"].values.astype(int)
        if len(np.unique(yte)) < 2:
            continue
        sc = score_models(tr, te)
        for m in model_list:
            if m not in sc:
                continue
            ste = sc[m][1]
            ret_row, oc_row = [], []
            for q in grid:
                thr = np.quantile(ste, q)
                emit = ste >= thr
                inv = 1 - yte
                ret_row.append(emit[yte == 1].sum() / max((yte == 1).sum(), 1))
                oc_row.append(inv[emit].mean() if emit.any() else np.nan)
            curves[m]["ret"].append(ret_row)
            curves[m]["oc"].append(oc_row)
    out = {}
    for m, c in curves.items():
        if not c["ret"]:
            continue
        R = np.array(c["ret"]); O = np.array(c["oc"])
        out[m] = dict(ret=np.nanmean(R, 0), oc=np.nanmean(O, 0),
                      oc_lo=np.nanpercentile(O, 2.5, 0), oc_hi=np.nanpercentile(O, 97.5, 0))
    return out


def main():
    car, kit = base.load_carla(), base.load_kitti()
    print(f"[rig] CARLA n={len(car)} vel+={car.velocity_valid.mean():.3f} | "
          f"KITTI n={len(kit)} vel+={kit.velocity_valid.mean():.3f}")

    cv_rows, sig_rows = [], []
    for name, df in [("CARLA->CARLA(run)", car), ("KITTI->KITTI(seq)", kit)]:
        r, s = repeated_cv(df, name)
        cv_rows += r; sig_rows += s
    cv = pd.DataFrame(cv_rows); sig = pd.DataFrame(sig_rows)
    cv.to_csv(WS / "paper2_rigorous_cv.csv", index=False)
    sig.to_csv(WS / "paper2_rigorous_significance.csv", index=False)

    xd = pd.DataFrame(cross_dataset(car, kit))
    xd.to_csv(WS / "paper2_rigorous_crossdataset.csv", index=False)

    strat = stratified(car)
    strat.to_csv(WS / "paper2_rigorous_stratified.csv", index=False)

    abl = ablation(base.load_carla, base.load_kitti)
    abl.to_csv(WS / "paper2_rigorous_ablation.csv", index=False)

    # pareto figure
    pc = pareto(car, "CARLA", ["distance_gate", "OVI_geom", "selective_logistic", "selective_hist_gbm"])
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        (WS / "figs").mkdir(exist_ok=True)
        plt.figure(figsize=(6, 4.2))
        col = {"distance_gate": "tab:gray", "OVI_geom": "tab:green",
               "selective_logistic": "tab:blue", "selective_hist_gbm": "tab:red"}
        for m, c in pc.items():
            order = np.argsort(c["ret"])
            plt.plot(np.array(c["ret"])[order], np.array(c["oc"])[order],
                     label=m, color=col.get(m), lw=2)
            plt.fill_between(np.array(c["ret"])[order], np.array(c["oc_lo"])[order],
                             np.array(c["oc_hi"])[order], color=col.get(m), alpha=0.12)
        plt.xlabel("valid-velocity retention"); plt.ylabel("overconfident-wrong-velocity rate")
        plt.title("CARLA velocity-validity: refusal Pareto (5-fold grouped CV, 95% band)")
        plt.legend(fontsize=8); plt.grid(alpha=0.3); plt.tight_layout()
        plt.savefig(WS / "figs" / "paper2_pareto.png", dpi=140)
        fig_ok = True
    except Exception as e:  # noqa: BLE001
        print("[rig] figure skipped:", e); fig_ok = False

    # ---- report
    L = ["# PAPER2_SELECTIVE_VALIDITY_RIGOROUS", "",
         f"> Journal-grade decision-level eval on REAL data with GT. CARLA velocity rows n={len(car)} "
         f"(vel-valid {car.velocity_valid.mean():.1%}), KITTI n={len(kit)} (vel-valid {kit.velocity_valid.mean():.1%}). "
         "Grouped CV by run/sequence (no leakage); 5-fold x 5 repeats; 95% CI = t-interval over folds.",
         f"> GT velocity-valid criterion: ego-independent vel_err <= {base.VEL_T} m/s. Features: {COMMON}", "",
         "## 1. Repeated grouped-CV: AUROC + refusal metrics (mean [95% CI])",
         "| scenario | model | AUROC | overconf-wrong | retention | false-refusal | F1_inv |",
         "|---|---|---|---|---|---|---|"]
    for _, r in cv.iterrows():
        L.append(f"| {r.scenario} | {r.model} | {r.auroc:.3f} [{r.auroc_lo:.3f},{r.auroc_hi:.3f}] | "
                 f"{r.overconf:.3f} [{r.overconf_lo:.3f},{r.overconf_hi:.3f}] | "
                 f"{r.retention:.3f} | {r.false_refusal:.3f} | {r.f1_invalid:.3f} |")
    L += ["", "## 2. Significance vs distance-gate (paired Wilcoxon on per-fold AUROC)",
          "| scenario | model | ΔAUROC | Wilcoxon p | n_folds |", "|---|---|---|---|---|"]
    for _, r in sig.iterrows():
        star = " ✱" if (r.wilcoxon_p == r.wilcoxon_p and r.wilcoxon_p < 0.05 and r.dAUROC > 0) else ""
        L.append(f"| {r.scenario} | {r.model} | {r.dAUROC:+.3f} | {r.wilcoxon_p}{star} | {r.n_folds} |")
    L += ["", "## 3. Cross-dataset generalization CARLA→KITTI (bootstrap 95% CI over KITTI seqs)",
          "| model | AUROC [95% CI] | overconf-wrong | retention |", "|---|---|---|---|"]
    for _, r in xd.iterrows():
        L.append(f"| {r.model} | {r.auroc:.3f} [{r.auroc_lo:.3f},{r.auroc_hi:.3f}] | {r.overconf:.3f} | {r.retention:.3f} |")
    L += ["", "## 4. Stratified AUROC (CARLA, grouped within stratum)",
          "| stratum | model | AUROC | overconf | n |", "|---|---|---|---|---|"]
    for _, r in strat.iterrows():
        L.append(f"| {r.stratum} | {r.model} | {r.auroc:.3f} | {r.overconf:.3f} | {int(r.n)} |")
    L += ["", "## 5. Threshold ablation (mean grouped-CV AUROC; ranking stability)",
          "| VEL_T | dataset | model | AUROC |", "|---|---|---|---|"]
    for _, r in abl.iterrows():
        L.append(f"| {r.VEL_T} | {r.dataset} | {r.model} | {r.auroc:.3f} |")
    L += ["", "## 6. Refusal Pareto", f"- figure: figs/paper2_pareto.png ({'ok' if fig_ok else 'skipped'})",
          "- lower curve = fewer overconfident-wrong velocities at equal retention = better.", "",
          "## Honest reading",
          "- Distance-gate is the Qiu-2018-style single-scalar observability gate baseline.",
          "- A selective model is journal-meaningful only where it beats the gate with non-overlapping CIs "
          "AND generalizes cross-dataset; in-domain wins that vanish CARLA→KITTI indicate dataset-specific overfit.",
          "- Report the most robust model (typically logistic) as headline; GBM/MLP as high-variance upper bound."]
    (WS / "PAPER2_SELECTIVE_VALIDITY_RIGOROUS.md").write_text("\n".join(L) + "\n")
    print("[rig] done -> PAPER2_SELECTIVE_VALIDITY_RIGOROUS.md")


if __name__ == "__main__":
    main()
