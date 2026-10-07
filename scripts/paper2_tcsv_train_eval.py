#!/usr/bin/env python3
"""Paper-2 TCSV — train & evaluate the Temporal-Consistency Selective Validator.

Models (NO transformer / attention / large nets — by design):
  - no_policy     : emit everything (lower bound, base invalid rate)
  - distance_gate : -range_m gate (Qiu-style simplest geometric refusal)
  - OVI_geom      : logistic on geometry only (observability index baseline)
  - TCSV-rule     : interpretable shallow decision tree (depth 3) = rule gate
  - TCSV-HistGBM  : main model
  - TCSV-MLP      : small neural control (64,32)

Selective-risk / operating evaluation (NOT just AUROC):
  AUROC, overconfident-wrong-velocity, valid-velocity retention, false_refusal, F1_invalid,
  AURC (area under risk-coverage), overconf @ fixed valid-retention = 0.8 / 0.9, risk-coverage CSV.

Also: (a) does the new temporal-residual feature set beat the prior OLD10 set? (HistGBM ablation)
      (b) permutation importance (GEO vs TEMP-base vs TEMP-residual, + top features)
      (c) temporal-window ablation W in {1,3,5,7}, in-domain, NO frame random split.

Splits: CARLA by run, KITTI by sequence, + cross-dataset. Output:
  PAPER2_TCSV_RESULTS.md, paper2_tcsv_metrics.csv, paper2_tcsv_riskcov.csv,
  paper2_tcsv_window_ablation.csv, paper2_tcsv_importance.csv, figs/fig_tcsv_riskcov.png
"""
from __future__ import annotations
from pathlib import Path
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.tree import DecisionTreeClassifier, export_text
from sklearn.metrics import roc_auc_score, f1_score, roc_curve
from sklearn.pipeline import make_pipeline
from sklearn.inspection import permutation_importance
import paper2_tcsv_features as F

WS = Path("/home/ivlab3/fwvio_estimator_ws_wheel")


# ----------------------------- metrics -----------------------------
def youden(score, y):
    if len(np.unique(y)) < 2: return float(np.median(score))
    fpr, tpr, th = roc_curve(y, score); return th[np.argmax(tpr - fpr)]


def aurc(y, score):
    """Area under the risk-coverage curve (risk=overconfident-wrong among emitted). Lower=better."""
    inv = (1 - y).astype(float)
    order = np.argsort(-score)
    inv_s = inv[order]
    cov = np.arange(1, len(y) + 1) / len(y)
    risk = np.cumsum(inv_s) / np.arange(1, len(y) + 1)
    return float(np.trapz(risk, cov))


def overconf_at_retention(y, score, target_ret):
    """Set threshold so valid-retention == target_ret; return (overconf, coverage)."""
    vs = np.sort(score[y == 1])[::-1]
    nv = len(vs)
    if nv == 0: return float("nan"), float("nan")
    k = int(np.ceil(target_ret * nv))
    k = min(max(k, 1), nv)
    thr = vs[k - 1]
    emit = score >= thr
    inv = 1 - y
    oc = float(inv[emit].mean()) if emit.any() else float("nan")
    return oc, float(emit.mean())


def op_metrics(y, score, thr):
    y = y.astype(int); emit = score >= thr; inv = 1 - y
    oc = float(inv[emit].mean()) if emit.any() else float("nan")
    ret = float(emit[y == 1].sum() / max((y == 1).sum(), 1))
    f1 = f1_score(inv, (~emit).astype(int), zero_division=0)
    auc = roc_auc_score(y, score) if len(np.unique(y)) > 1 else float("nan")
    oc8, _ = overconf_at_retention(y, score, 0.8)
    oc9, _ = overconf_at_retention(y, score, 0.9)
    return dict(auroc=auc, overconf=oc, retention=ret, false_refusal=1 - ret, f1_invalid=f1,
                aurc=aurc(y, score), overconf_at_ret80=oc8, overconf_at_ret90=oc9)


# ----------------------------- models -----------------------------
def fit_tcsv_models(Xtr, ytr):
    out = {}
    out["TCSV-rule"] = DecisionTreeClassifier(max_depth=3, min_samples_leaf=200,
                                              class_weight="balanced", random_state=7).fit(Xtr, ytr)
    out["TCSV-HistGBM"] = HistGradientBoostingClassifier(max_iter=300, max_depth=4, learning_rate=0.05,
                                                         l2_regularization=1.0, random_state=7).fit(Xtr, ytr)
    out["TCSV-MLP"] = make_pipeline(StandardScaler(),
                                    MLPClassifier((64, 32), max_iter=400, early_stopping=True,
                                                  random_state=7)).fit(Xtr, ytr)
    return out


def split_by_key(df, seed=7, frac=0.25):
    keys = sorted(df["split_key"].unique())
    rs = np.random.RandomState(seed); rs.shuffle(keys)
    nt = max(1, int(len(keys) * frac)); test = set(keys[:nt])
    return df["split_key"].isin(test).values


# ----------------------------- main pipeline -----------------------------
def main():
    car = F.load_carla(W=5); kit = F.load_kitti(W=5)
    print(f"[tcsv] CARLA n={len(car)} vv={car.velocity_valid.mean():.3f} ; KITTI n={len(kit)} vv={kit.velocity_valid.mean():.3f}")
    feats = F.TCSV_FEATS
    rows = []; riskcov_rows = []

    def baselines(tr_df, te_df, ytr, yte):
        geo = ["range_m", "bearing_deg", "depth_m"]
        ovi = make_pipeline(StandardScaler(), LogisticRegression(max_iter=500)).fit(tr_df[geo].fillna(0).values, ytr)
        sc = {}
        # no_policy: emit all -> constant score above any threshold
        sc["no_policy"] = (np.ones(len(tr_df)), np.ones(len(te_df)))
        sc["distance_gate"] = (-tr_df["range_m"].values, -te_df["range_m"].values)
        sc["OVI_geom"] = (ovi.predict_proba(tr_df[geo].fillna(0).values)[:, 1],
                          ovi.predict_proba(te_df[geo].fillna(0).values)[:, 1])
        return sc

    def run_scenario(name, tr_df, te_df, feat_list=feats, save_riskcov=False, tag="TCSV"):
        Xtr = F.prep(tr_df, feat_list); Xte = F.prep(te_df, feat_list)
        ytr = tr_df["velocity_valid"].values.astype(int); yte = te_df["velocity_valid"].values.astype(int)
        scores = baselines(tr_df, te_df, ytr, yte)
        for nm, m in fit_tcsv_models(Xtr, ytr).items():
            if hasattr(m, "predict_proba"):
                scores[nm] = (m.predict_proba(Xtr)[:, 1], m.predict_proba(Xte)[:, 1])
        for nm, (str_, ste) in scores.items():
            if nm == "no_policy":
                thr = -np.inf  # emit everything
            else:
                thr = youden(str_, ytr)
            mt = op_metrics(yte, ste, thr)
            rows.append(dict(scenario=name, feats=tag, model=nm, n_test=len(te_df),
                             **{k: (round(v, 4) if v == v else v) for k, v in mt.items()}))
            if save_riskcov and nm in ("distance_gate", "OVI_geom", "TCSV-HistGBM", "TCSV-MLP"):
                inv = (1 - yte).astype(float); order = np.argsort(-ste)
                cov = np.arange(1, len(yte) + 1) / len(yte)
                risk = np.cumsum(inv[order]) / np.arange(1, len(yte) + 1)
                step = max(1, len(yte) // 100)
                for j in range(0, len(yte), step):
                    riskcov_rows.append(dict(scenario=name, model=nm,
                                             coverage=round(float(cov[j]), 4), risk=round(float(risk[j]), 4)))

    car_te = split_by_key(car); kit_te = split_by_key(kit)
    run_scenario("CARLA->CARLA(run)", car[~car_te], car[car_te], save_riskcov=True)
    run_scenario("KITTI->KITTI(seq)", kit[~kit_te], kit[kit_te], save_riskcov=True)
    run_scenario("CARLA->KITTI", car, kit)
    run_scenario("CARLA+KITtrain->KIThold", pd.concat([car, kit[~kit_te]]), kit[kit_te])

    # ---- (a) does the NEW temporal-residual set beat OLD10? (HistGBM, in-domain) ----
    def hgbm_one(tr_df, te_df, feat_list):
        Xtr = F.prep(tr_df, feat_list); Xte = F.prep(te_df, feat_list)
        ytr = tr_df["velocity_valid"].values.astype(int); yte = te_df["velocity_valid"].values.astype(int)
        m = HistGradientBoostingClassifier(max_iter=300, max_depth=4, learning_rate=0.05,
                                           l2_regularization=1.0, random_state=7).fit(Xtr, ytr)
        s_tr = m.predict_proba(Xtr)[:, 1]; s_te = m.predict_proba(Xte)[:, 1]
        return op_metrics(yte, s_te, youden(s_tr, ytr))
    ablation = []
    for nm, tr, te in [("CARLA", car[~car_te], car[car_te]), ("KITTI", kit[~kit_te], kit[kit_te])]:
        old = hgbm_one(tr, te, F.OLD10_FEATS); new = hgbm_one(tr, te, feats)
        ablation.append((nm, old, new))

    # ---- (b) permutation importance (HistGBM, in-domain test) ----
    imp_rows = []
    for nm, tr, te in [("CARLA", car[~car_te], car[car_te]), ("KITTI", kit[~kit_te], kit[kit_te])]:
        Xtr = F.prep(tr, feats); Xte = F.prep(te, feats)
        ytr = tr["velocity_valid"].values.astype(int); yte = te["velocity_valid"].values.astype(int)
        m = HistGradientBoostingClassifier(max_iter=300, max_depth=4, learning_rate=0.05,
                                           l2_regularization=1.0, random_state=7).fit(Xtr, ytr)
        pi = permutation_importance(m, Xte, yte, scoring="roc_auc", n_repeats=10, random_state=7, n_jobs=-1)
        for f, mean, std in zip(feats, pi.importances_mean, pi.importances_std):
            grp = ("GEO" if f in F.GEO_FEATS else "TEMP_base" if f in F.TEMP_BASE_FEATS else "TEMP_resid")
            imp_rows.append(dict(dataset=nm, feature=f, group=grp,
                                 importance=round(float(mean), 5), std=round(float(std), 5)))

    # ---- (c) temporal-window ablation W in {1,3,5,7} (in-domain HistGBM) ----
    win_rows = []
    for W in [1, 3, 5, 7]:
        cW = F.load_carla(W=W); kW = F.load_kitti(W=W)
        cte = split_by_key(cW); kte = split_by_key(kW)
        for nm, tr, te in [("CARLA", cW[~cte], cW[cte]), ("KITTI", kW[~kte], kW[kte])]:
            mt = hgbm_one(tr, te, feats)
            win_rows.append(dict(W=W, dataset=nm, auroc=round(mt["auroc"], 4),
                                 aurc=round(mt["aurc"], 4), overconf_at_ret90=round(mt["overconf_at_ret90"], 4)))

    # ---- rule text (interpretability) ----
    Xtr_c = F.prep(car[~car_te], feats)
    rule = DecisionTreeClassifier(max_depth=3, min_samples_leaf=200, class_weight="balanced",
                                  random_state=7).fit(Xtr_c, car[~car_te]["velocity_valid"].values.astype(int))
    rule_txt = export_text(rule, feature_names=feats, max_depth=3)

    # ---- save artifacts ----
    M = pd.DataFrame(rows); M.to_csv(WS / "paper2_tcsv_metrics.csv", index=False)
    pd.DataFrame(riskcov_rows).to_csv(WS / "paper2_tcsv_riskcov.csv", index=False)
    pd.DataFrame(win_rows).to_csv(WS / "paper2_tcsv_window_ablation.csv", index=False)
    IMP = pd.DataFrame(imp_rows); IMP.to_csv(WS / "paper2_tcsv_importance.csv", index=False)

    # ---- figure ----
    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        RC = pd.DataFrame(riskcov_rows)
        fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
        for i, sc in enumerate(["CARLA->CARLA(run)", "KITTI->KITTI(seq)"]):
            for mdl in ["distance_gate", "OVI_geom", "TCSV-MLP", "TCSV-HistGBM"]:
                s = RC[(RC.scenario == sc) & (RC.model == mdl)]
                if len(s): ax[i].plot(s.coverage, s.risk, label=mdl, lw=2 if mdl.startswith("TCSV") else 1.2)
            ax[i].set_title(sc); ax[i].set_xlabel("coverage (emit fraction)")
            ax[i].set_ylabel("risk (overconfident-wrong velocity)"); ax[i].grid(alpha=0.3); ax[i].legend(fontsize=8)
        fig.suptitle("TCSV risk-coverage (lower = better selective refusal)")
        fig.tight_layout(); (WS / "figs").mkdir(exist_ok=True)
        fig.savefig(WS / "figs/fig_tcsv_riskcov.png", dpi=130); plt.close(fig)
    except Exception as e:
        print("[tcsv] figure skipped:", e)

    # ---- write results md ----
    write_results(M, ablation, IMP, pd.DataFrame(win_rows), rule_txt, len(car), len(kit))
    print("[tcsv] done. metrics rows:", len(M))


def write_results(M, ablation, IMP, WIN, rule_txt, nc, nk):
    L = ["# PAPER2_TCSV_RESULTS", "",
         "> TCSV = Temporal-Consistency Selective Validator. CARLA n=%d, KITTI n=%d. "
         "Splits: CARLA by run, KITTI by sequence (NO frame random). Velocity criterion = ego-independent "
         "vel_err<=3 m/s. Features = 5 GEO + 2 TEMP-base + 7 TEMP-residual (all runtime-observable; only the "
         "LABEL uses GT). Window W=5 unless stated." % (nc, nk), "",
         "## 1. Operating evaluation by scenario (AUROC + selective-risk metrics)",
         "| scenario | model | AUROC | overconf | retention | false_ref | F1_inv | AURC↓ | OC@ret.8 | OC@ret.9 |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for _, r in M[M.feats == "TCSV"].iterrows():
        def g(x): return f"{x:.3f}" if isinstance(x, (int, float)) and x == x else "—"
        L.append(f"| {r.scenario} | {r.model} | {g(r.auroc)} | {g(r.overconf)} | {g(r.retention)} | "
                 f"{g(r.false_refusal)} | {g(r.f1_invalid)} | {g(r.aurc)} | {g(r.overconf_at_ret80)} | {g(r.overconf_at_ret90)} |")

    L += ["", "## 2. Do the NEW temporal-residual features beat the prior OLD10 set? (HistGBM, in-domain)",
          "| dataset | feats | AUROC | AURC↓ | overconf@ret.9 |", "|---|---|---|---|---|"]
    for nm, old, new in ablation:
        L.append(f"| {nm} | OLD10 | {old['auroc']:.3f} | {old['aurc']:.3f} | {old['overconf_at_ret90']:.3f} |")
        L.append(f"| {nm} | TCSV14 | {new['auroc']:.3f} | {new['aurc']:.3f} | {new['overconf_at_ret90']:.3f} |")

    L += ["", "## 3. Permutation importance (HistGBM, ΔAUROC when feature shuffled; in-domain test)"]
    for ds in ["CARLA", "KITTI"]:
        sub = IMP[IMP.dataset == ds].sort_values("importance", ascending=False)
        grp = IMP[IMP.dataset == ds].groupby("group").importance.sum()
        L += [f"", f"**{ds}** — group totals: " + ", ".join(f"{k}={v:.4f}" for k, v in grp.items()),
              "| rank | feature | group | importance | std |", "|---|---|---|---|---|"]
        for i, (_, r) in enumerate(sub.head(8).iterrows(), 1):
            L.append(f"| {i} | {r.feature} | {r.group} | {r.importance:.4f} | {r['std']:.4f} |")

    L += ["", "## 4. Temporal-window ablation (in-domain HistGBM; W=1 collapses windowed features)",
          "| W | dataset | AUROC | AURC↓ | overconf@ret.9 |", "|---|---|---|---|---|"]
    for _, r in WIN.iterrows():
        L.append(f"| {int(r.W)} | {r.dataset} | {r.auroc:.3f} | {r.aurc:.3f} | {r.overconf_at_ret90:.3f} |")

    L += ["", "## 5. TCSV-rule (interpretable depth-3 tree, CARLA train) — the rule gate",
          "```", rule_txt.strip(), "```",
          "", "## Honest verdict",
          "- AURC (area under risk-coverage) is the cleanest selective-refusal summary (lower=better); "
          "overconf@ret.9 = the overconfident-wrong-velocity rate when forced to keep 90% of valid velocities.",
          "- See §2 for whether the new temporal residuals actually add over the prior 10-feature model, and §3 "
          "for whether temporal-consistency features dominate importance. Both reported as-is, good or bad.",
          "- Figure: figs/fig_tcsv_riskcov.png"]
    (WS / "PAPER2_TCSV_RESULTS.md").write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
