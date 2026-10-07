#!/usr/bin/env python3
"""Paper-2 — CALIBRATION of the TCSV validity score.

A refusal gate's score should be a usable probability. We report ECE, Brier, reliability diagrams for
TCSV-HistGBM and TCSV-MLP (in-domain CARLA & KITTI), and whether Platt (sigmoid) / isotonic calibration
on a held-out calibration split improves ECE. NO frame-random split (by run / seq).
Output: PAPER2_CALIBRATION_RESULTS.md + figs/fig_tcsv_reliability.png
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
import paper2_tcsv_features as F
from paper2_tcsv_train_eval import split_by_key
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss

WS = Path("/home/ivlab3/fwvio_estimator_ws_wheel")


def ece(y, p, nbins=15):
    bins = np.linspace(0, 1, nbins + 1); e = 0.0; n = len(y)
    for i in range(nbins):
        m = (p >= bins[i]) & (p < bins[i + 1]) if i < nbins - 1 else (p >= bins[i]) & (p <= bins[i + 1])
        if m.sum() == 0: continue
        e += (m.sum() / n) * abs(y[m].mean() - p[m].mean())
    return e


def reliability(y, p, nbins=10):
    bins = np.linspace(0, 1, nbins + 1); xs, ys = [], []
    for i in range(nbins):
        m = (p >= bins[i]) & (p < bins[i + 1]) if i < nbins - 1 else (p >= bins[i]) & (p <= bins[i + 1])
        if m.sum() == 0: continue
        xs.append(p[m].mean()); ys.append(y[m].mean())
    return np.array(xs), np.array(ys)


def main():
    car = F.load_carla(); kit = F.load_kitti()
    feats = F.TCSV_FEATS
    rows = []; curves = {}
    for ds, d in [("CARLA", car), ("KITTI", kit)]:
        te = split_by_key(d)
        tr_mask = ~te
        # split train into fit + calib (by split_key too, to keep no-leak)
        tr_keys = sorted(d[tr_mask]["split_key"].unique())
        rs = np.random.RandomState(3); rs.shuffle(tr_keys)
        ncal = max(1, len(tr_keys) // 4); cal_keys = set(tr_keys[:ncal])
        calib = d["split_key"].isin(cal_keys).values & tr_mask
        fitm = tr_mask & (~calib)
        X = F.prep(d, feats); y = d["velocity_valid"].values.astype(int)
        for nm, mk in [("TCSV-HistGBM", lambda: HistGradientBoostingClassifier(max_iter=300, max_depth=4,
                        learning_rate=0.05, l2_regularization=1.0, random_state=7)),
                       ("TCSV-MLP", lambda: make_pipeline(StandardScaler(),
                        MLPClassifier((64, 32), max_iter=400, early_stopping=True, random_state=7)))]:
            m = mk().fit(X[fitm], y[fitm])
            p_te = m.predict_proba(X[te])[:, 1]; yte = y[te]
            p_cal = m.predict_proba(X[calib])[:, 1]; ycal = y[calib]
            base = dict(ece=ece(yte, p_te), brier=brier_score_loss(yte, p_te))
            # Platt
            platt = LogisticRegression(max_iter=500).fit(p_cal.reshape(-1, 1), ycal)
            p_pl = platt.predict_proba(p_te.reshape(-1, 1))[:, 1]
            # isotonic
            iso = IsotonicRegression(out_of_bounds="clip").fit(p_cal, ycal)
            p_is = iso.predict(p_te)
            rows.append(dict(dataset=ds, model=nm,
                             ece_raw=round(base["ece"], 4), brier_raw=round(base["brier"], 4),
                             ece_platt=round(ece(yte, p_pl), 4), brier_platt=round(brier_score_loss(yte, p_pl), 4),
                             ece_isotonic=round(ece(yte, p_is), 4), brier_isotonic=round(brier_score_loss(yte, p_is), 4)))
            if nm == "TCSV-HistGBM":
                curves[ds] = (reliability(yte, p_te), reliability(yte, p_is))

    M = pd.DataFrame(rows); M.to_csv(WS / "paper2_calibration_metrics.csv", index=False)
    # figure
    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        fig, ax = plt.subplots(1, 2, figsize=(10, 4.2))
        for i, ds in enumerate(["CARLA", "KITTI"]):
            (xr, yr), (xi, yi) = curves[ds]
            ax[i].plot([0, 1], [0, 1], "k--", lw=1, label="perfect")
            ax[i].plot(xr, yr, "o-", label="raw HistGBM")
            ax[i].plot(xi, yi, "s-", label="isotonic")
            ax[i].set_title(f"{ds} reliability"); ax[i].set_xlabel("predicted P(valid)")
            ax[i].set_ylabel("empirical fraction valid"); ax[i].grid(alpha=0.3); ax[i].legend(fontsize=8)
        fig.tight_layout(); (WS / "figs").mkdir(exist_ok=True)
        fig.savefig(WS / "figs/fig_tcsv_reliability.png", dpi=130); plt.close(fig)
    except Exception as e:
        print("[cal] fig skipped:", e)

    L = ["# PAPER2_CALIBRATION_RESULTS", "",
         "> Is the TCSV validity score a usable probability for refusal thresholding? ECE (15-bin), Brier, "
         "reliability diagrams; Platt/isotonic fit on a held-out calibration split (by run/seq, no leak).", "",
         "| dataset | model | ECE_raw | ECE_platt | ECE_isotonic | Brier_raw | Brier_platt | Brier_isotonic |",
         "|---|---|---|---|---|---|---|---|"]
    for _, r in M.iterrows():
        L.append(f"| {r.dataset} | {r.model} | {r.ece_raw:.3f} | {r.ece_platt:.3f} | {r.ece_isotonic:.3f} | "
                 f"{r.brier_raw:.3f} | {r.brier_platt:.3f} | {r.brier_isotonic:.3f} |")
    L += ["", "## Reading",
          "- Lower ECE/Brier = better-calibrated. If isotonic/Platt clearly lowers ECE, deploy the calibrated "
          "score and pick the refusal threshold on the calibrated probability.",
          "- AURC/AUROC are rank metrics and are unchanged by monotone calibration; calibration matters for "
          "choosing an interpretable operating threshold, not for ranking.",
          "- Figure: figs/fig_tcsv_reliability.png"]
    (WS / "PAPER2_CALIBRATION_RESULTS.md").write_text("\n".join(L) + "\n")
    print("[cal] done")


if __name__ == "__main__":
    main()
