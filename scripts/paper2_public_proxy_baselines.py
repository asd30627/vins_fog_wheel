#!/usr/bin/env python3
"""Paper-2 — PUBLIC / PROXY BASELINES for selective object-velocity validity.

Compares TCSV against a full baseline suite on the SAME selective-risk metrics, across 6 fixed splits.
NO GT in any feature (label only uses GT). NO frame-random split (CARLA by run, KITTI by sequence).

Baselines (honest provenance):
  1. no_policy            — always emit full-state (lower bound)
  2. distance_gate        — score = -range_m
  3. qiu_style            — PROXY of Qiu-2018 geometric-excitation/observability gate (NOT the original);
                            logistic on excitation features [range, |bearing_change|, track_age, bbox_area]
  4. yolo_conf_gate       — score = detector confidence (det_conf)
  5. bbox_depth_gate      — appearance/depth-uncertainty gate; logistic on [bbox_depth_consistency, depth, bbox_area]
  6. cv_smoothing_gate    — constant-velocity smoothing baseline; score = -cv_residual (CV one-step innovation)
  7. selectivenet_proxy   — SelectiveNet-style selector PROXY (softmax-response of an MLP; full joint-trained
                            SelectiveNet needs a DL impl — see TODO). Selector = max class prob.
  8. ovi_geom             — logistic on geometry [range, bearing, depth]
  9. TCSV-rule / TCSV-HistGBM / TCSV-MLP — ours

Metrics per (split, model): AUROC, AURC, overconf, overconf@ret.8, overconf@ret.9, retention, false_refusal, F1_invalid.

Splits: CARLA->CARLA(run), KITTI->KITTI(seq), CARLA->KITTI, KITTI->CARLA,
        CARLA+KITtrain->held-out-KITTI, CARLA+KITtrain->held-out-CARLA.

Output: PAPER2_PUBLIC_PROXY_BASELINE_RESULTS.md, paper2_public_proxy_baselines_metrics.csv
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
import paper2_tcsv_features as F
from paper2_tcsv_train_eval import op_metrics, youden, split_by_key, fit_tcsv_models
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline

WS = Path("/home/ivlab3/fwvio_estimator_ws_wheel")
QIU_FEATS = ["range_m", "bearing_change_abs", "track_age", "bbox_area"]
BBOXDEPTH_FEATS = ["bbox_depth_consistency", "depth_m", "bbox_area"]
OVI_FEATS = ["range_m", "bearing_deg", "depth_m"]


def add_aux(df):
    df = df.copy()
    df["bearing_change_abs"] = df["bearing_change"].abs() if "bearing_change" in df else 0.0
    return df


def logistic_score(tr, te, feats, ytr):
    Xtr = tr[feats].astype(float).fillna(0.0).values
    Xte = te[feats].astype(float).fillna(0.0).values
    m = make_pipeline(StandardScaler(), LogisticRegression(max_iter=500)).fit(Xtr, ytr)
    return m.predict_proba(Xtr)[:, 1], m.predict_proba(Xte)[:, 1]


def build_scores(tr, te, ytr):
    """Return {model: (train_score, test_score)} — all runtime-observable, no GT."""
    s = {}
    s["no_policy"] = (np.ones(len(tr)), np.ones(len(te)))
    s["distance_gate"] = (-tr["range_m"].astype(float).values, -te["range_m"].astype(float).values)
    s["qiu_style(proxy)"] = logistic_score(tr, te, QIU_FEATS, ytr)
    s["yolo_conf_gate"] = (tr["det_conf"].astype(float).fillna(0).values, te["det_conf"].astype(float).fillna(0).values)
    s["bbox_depth_gate"] = logistic_score(tr, te, BBOXDEPTH_FEATS, ytr)
    cv_tr = -tr["cv_residual"].astype(float).fillna(tr["cv_residual"].median()).values
    cv_te = -te["cv_residual"].astype(float).fillna(tr["cv_residual"].median()).values
    s["cv_smoothing_gate"] = (cv_tr, cv_te)
    s["ovi_geom"] = logistic_score(tr, te, OVI_FEATS, ytr)
    # SelectiveNet-style PROXY: MLP predictor, selector = softmax response (max class prob)
    Xtr = F.prep(tr, F.TCSV_FEATS); Xte = F.prep(te, F.TCSV_FEATS)
    mlp = make_pipeline(StandardScaler(), MLPClassifier((64, 32), max_iter=400, early_stopping=True,
                                                        random_state=7)).fit(Xtr, ytr)
    ptr = mlp.predict_proba(Xtr)[:, 1]; pte = mlp.predict_proba(Xte)[:, 1]
    # softmax response = confidence toward "valid"; as a validity score we use P(valid) directly,
    # which equals the selector ranking that emits the most-confident-valid first.
    s["selectivenet_proxy"] = (ptr, pte)
    # TCSV models
    for nm, m in fit_tcsv_models(Xtr, ytr).items():
        s[nm] = (m.predict_proba(Xtr)[:, 1], m.predict_proba(Xte)[:, 1])
    return s


def eval_split(name, tr, te, rows):
    ytr = tr["velocity_valid"].values.astype(int); yte = te["velocity_valid"].values.astype(int)
    for nm, (str_, ste) in build_scores(tr, te, ytr).items():
        thr = -np.inf if nm == "no_policy" else youden(str_, ytr)
        m = op_metrics(yte, ste, thr)
        rows.append(dict(split=name, model=nm, n_test=len(te),
                         **{k: (round(v, 4) if v == v else float("nan")) for k, v in m.items()}))


def main():
    car = add_aux(F.load_carla(W=5)); kit = add_aux(F.load_kitti(W=5))
    print(f"[base] CARLA n={len(car)} vv={car.velocity_valid.mean():.3f} ; KITTI n={len(kit)} vv={kit.velocity_valid.mean():.3f}")
    car_te = split_by_key(car); kit_te = split_by_key(kit)
    rows = []
    eval_split("CARLA->CARLA(run)", car[~car_te], car[car_te], rows)
    eval_split("KITTI->KITTI(seq)", kit[~kit_te], kit[kit_te], rows)
    eval_split("CARLA->KITTI", car, kit, rows)
    eval_split("KITTI->CARLA", kit, car, rows)
    eval_split("CARLA+KITtrain->KIThold", pd.concat([car, kit[~kit_te]]), kit[kit_te], rows)
    eval_split("KITtrain+CARtrain->CARhold", pd.concat([kit, car[~car_te]]), car[car_te], rows)

    M = pd.DataFrame(rows)
    M.to_csv(WS / "paper2_public_proxy_baselines_metrics.csv", index=False)
    write_md(M, len(car), len(kit))
    print("[base] done. rows:", len(M))


def write_md(M, nc, nk):
    cols = ["auroc", "aurc", "overconf", "overconf_at_ret80", "overconf_at_ret90",
            "retention", "false_refusal", "f1_invalid"]
    hdr = {"auroc": "AUROC", "aurc": "AURC↓", "overconf": "overconf",
           "overconf_at_ret80": "OC@ret.8", "overconf_at_ret90": "OC@ret.9",
           "retention": "retention", "false_refusal": "false_ref", "f1_invalid": "F1_inv"}
    L = ["# PAPER2_PUBLIC_PROXY_BASELINE_RESULTS", "",
         f"> TCSV vs public/proxy baselines. CARLA n={nc}, KITTI n={nk}. NO GT features (label only). "
         "NO frame-random split. Selective-risk metrics: AURC↓ (area under risk-coverage, lower=better), "
         "OC@ret = overconfident-wrong velocity at fixed valid-retention.", "",
         "> **Provenance:** `qiu_style(proxy)` is OUR reimplementation of a Qiu-2018-style geometric-excitation/"
         "observability gate — NOT the original paper. `selectivenet_proxy` is a softmax-response selector PROXY "
         "(an MLP's confidence); a full joint-trained SelectiveNet (predictor+selector+coverage loss) needs a DL "
         "framework (torch unavailable here) — `[TODO]`. `cv_smoothing_gate` = constant-velocity one-step "
         "innovation gate.", ""]
    for sp in M.split.unique():
        sub = M[M.split == sp]
        L += [f"## {sp}", "| model | " + " | ".join(hdr[c] for c in cols) + " |",
              "|---|" + "---|" * len(cols)]
        for _, r in sub.iterrows():
            def g(c):
                v = r[c]
                return f"{v:.3f}" if isinstance(v, (int, float)) and v == v else "—"
            star = " **" if r.model.startswith("TCSV-Hist") else ""
            end = "**" if r.model.startswith("TCSV-Hist") else ""
            L.append(f"|{star} {r.model}{end} | " + " | ".join(g(c) for c in cols) + " |")
        # per-split verdict: best AURC among baselines (excl TCSV) vs TCSV-HistGBM
        base = sub[~sub.model.str.startswith("TCSV")]
        tcsv = sub[sub.model == "TCSV-HistGBM"]
        if len(tcsv) and len(base):
            bb = base.loc[base.aurc.idxmin()]
            t = tcsv.iloc[0]
            verdict = "BEATS" if t.aurc < bb.aurc - 0.005 else ("ties" if abs(t.aurc - bb.aurc) <= 0.005 else "LOSES")
            L += ["", f"_best baseline AURC = {bb.model} {bb.aurc:.3f}; TCSV-HistGBM {t.aurc:.3f} → **{verdict}** (AURC↓)._", ""]
    L += ["## Honest reading",
          "- AURC↓ and OC@ret.9 are the operative selective-refusal metrics; AUROC is secondary.",
          "- `qiu_style(proxy)` and `selectivenet_proxy` are reimplementations/proxies — NOT claimed equal to originals.",
          "- In-domain (CARLA->CARLA, KITTI->KITTI) and mixed-train→held-out are the credible regimes; "
          "direct cross-dataset (CARLA->KITTI, KITTI->CARLA) tests generalization and is expected to be weaker.",
          "- If a simple gate matches TCSV on a split, say so plainly."]
    (WS / "PAPER2_PUBLIC_PROXY_BASELINE_RESULTS.md").write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
