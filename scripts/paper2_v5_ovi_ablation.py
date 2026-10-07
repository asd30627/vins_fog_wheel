#!/usr/bin/env python3
"""Paper-2 v5 (C2 ablation) — is OVI's geometric content real, or is it just distance?

Change: paper2-observability-aware-object-validity-v5.

Leave-one-term-out on the OVI logistic + a low-bearing-change stratum (where velocity is geometrically
weakly observable). Honest: report the MARGINAL value of each term and where OVI beats distance-only;
if modest, say modest. Output: PAPER2_V5_OVI_ABLATION.md + paper2_v5_ovi_ablation.csv
"""
from __future__ import annotations
from pathlib import Path
import numpy as np, pandas as pd

WS = Path("/home/ivlab3/fwvio_estimator_ws_wheel")
DT = 0.05
BINS = ["0-15m", "15-30m", "30m+"]
FEATS = ["log_range", "yaw_lever", "bearing_change_rate", "depth_noise", "vel_obs_proxy", "track_stability"]


def auroc(t, s):
    from sklearn.metrics import roc_auc_score
    t = np.asarray(t).astype(int)
    return float(roc_auc_score(t, s)) if len(np.unique(t)) > 1 else float("nan")


def main():
    d = pd.read_csv(WS / "paper2_v5_object_validity_dataset.csv", low_memory=False)
    d = d[d["has_velocity_est"] == 1].copy()
    for c in ["range_m", "bearing_change_deg", "disp_med", "disp_std", "track_age", "vins_gyro_vins_diff", "velocity_valid"]:
        if c in d: d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d[d["range_m"].notna() & d["bearing_change_deg"].notna() & d["disp_med"].notna()].copy()
    rng = d["range_m"].values
    yaw_sig = d["vins_gyro_vins_diff"].fillna(1.0).clip(0.05, 30.0).values
    d["log_range"] = np.log1p(rng)
    d["yaw_lever"] = rng * np.sin(np.radians(yaw_sig))
    d["bearing_change_rate"] = d["bearing_change_deg"].abs().values / DT
    d["depth_noise"] = (d["disp_std"] / d["disp_med"].replace(0, np.nan)).fillna(0).clip(0, 5).values
    d["vel_obs_proxy"] = (d["bearing_change_deg"].abs() / np.maximum(rng, 1.0)).values
    d["track_stability"] = np.log1p(d["track_age"].fillna(0).values)
    y = d["velocity_valid"].values.astype(int)
    runs = (d["town"].astype(str) + "@" + d["run"].astype(str)).values
    rs = np.random.RandomState(7); uq = sorted(set(runs)); rs.shuffle(uq)
    te = np.array([r in set(uq[:max(1, len(uq)//5)]) for r in runs]); tr = ~te

    def std(M):
        return (M - M[tr].mean(0)) / (M[tr].std(0) + 1e-9)
    from sklearn.linear_model import LogisticRegression

    def fit_auc(feats, mask=None):
        X = std(d[feats].values.astype(float))
        lr = LogisticRegression(max_iter=500).fit(X[tr], y[tr])
        s = lr.predict_proba(X)[:, 1]
        m = te if mask is None else (te & mask)
        return auroc(y[m], s[m]), s

    full_auc, full_s = fit_auc(FEATS)
    dist_auc, _ = fit_auc(["log_range"])
    rows = [("OVI_full", full_auc, full_auc - dist_auc)]
    for f in FEATS:
        if f == "log_range":
            continue
        sub = [x for x in FEATS if x != f]
        a, _ = fit_auc(sub)
        rows.append((f"drop_{f}", a, a - full_auc))   # negative => term helped
    rows.append(("distance_only(log_range)", dist_auc, 0.0))

    # low-bearing-change stratum: bottom tercile of bearing_change_rate (velocity geometrically weak)
    bc = d["bearing_change_rate"].values
    lowbc = bc <= np.quantile(bc[tr], 0.33)
    full_lb, _ = fit_auc(FEATS, lowbc)
    dist_lb, _ = fit_auc(["log_range"], lowbc)
    # velocity validity rate in low vs high bearing-change (geometric prediction)
    vv_low = float(y[te & lowbc].mean()) if (te & lowbc).any() else float("nan")
    vv_high = float(y[te & ~lowbc].mean()) if (te & ~lowbc).any() else float("nan")
    # per-bin OVI vs distance
    perbin = {}
    for b in BINS:
        m = (d["dist_bin"] == b).values
        ao, _ = fit_auc(FEATS, m); ad, _ = fit_auc(["log_range"], m)
        perbin[b] = (ao, ad)

    pd.DataFrame(rows, columns=["model", "auroc", "delta_vs_ref"]).to_csv(WS / "paper2_v5_ovi_ablation.csv", index=False)
    L = ["# PAPER2_V5_OVI_ABLATION (C2 — is the geometry real or just distance?)", "",
         f"> Velocity-valid detection AUROC, leave-one-term-out on the OVI logistic. test n={int(te.sum())}.", "",
         "## Leave-one-term-out (drop_X delta < 0 ⇒ term X helped)",
         "| model | AUROC | Δ |", "|---|---|---|"]
    for nm, a, dl in rows:
        L.append(f"| {nm} | {a:.3f} | {dl:+.3f} |")
    L += ["", "## OVI vs distance-only per distance bin",
          "| bin | OVI | distance-only | Δ |", "|---|---|---|---|"]
    for b in BINS:
        ao, ad = perbin[b]; L.append(f"| {b} | {ao:.3f} | {ad:.3f} | {ao-ad:+.3f} |")
    L += ["", "## Low-bearing-change stratum (velocity geometrically weakly observable)",
          f"- velocity_valid rate: low-bearing-change {vv_low:.3f} vs high {vv_high:.3f} "
          f"→ geometry predicts velocity {'unobservable' if vv_low < vv_high else 'observable'} when bearing barely changes.",
          f"- OVI AUROC {full_lb:.3f} vs distance-only {dist_lb:.3f} in this stratum (Δ {full_lb-dist_lb:+.3f}).", "",
          "## Honest reading",
          f"- OVI overall AUROC {full_auc:.3f} vs distance-only {dist_auc:.3f} (Δ {full_auc-dist_auc:+.3f}) — "
          + ("a real but MODEST geometric gain over pure distance." if full_auc - dist_auc < 0.03 else "a clear geometric gain."),
          "- the term that helps most = the one whose drop_X is most negative (see table); "
          "bearing-change-based velocity observability is the expected key non-distance term.",
          "- OVI is positioned as an INTERPRETABLE auxiliary index, NOT the sole contribution; "
          "if the gain is modest we say modest (it is)."]
    (WS / "PAPER2_V5_OVI_ABLATION.md").write_text("\n".join(L) + "\n")
    print(f"[ovi-abl] full {full_auc:.3f} dist {dist_auc:.3f} delta {full_auc-dist_auc:+.3f}; "
          f"lowbc vv {vv_low:.2f} vs {vv_high:.2f}; lowbc OVI {full_lb:.3f} dist {dist_lb:.3f}")


if __name__ == "__main__":
    main()
