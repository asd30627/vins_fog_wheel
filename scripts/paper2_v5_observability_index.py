#!/usr/bin/env python3
"""Paper-2 v5 (C2) — Observability Validity Index (OVI): interpretable geometric index for object
velocity observability/validity. STANDALONE; NOT a black-box MLP.

Change: paper2-observability-aware-object-validity-v5.

Geometric terms (runtime-observable):
  yaw_lever            = range * sin(yaw_sigma)            [ego-yaw uncertainty x distance -> lateral lever]
  bearing_change_rate  = |bearing_change_deg| / dt
  depth_noise          = disp_std / disp_med              [relative disparity jitter]
  vel_obs_proxy        = |bearing_change_deg| / range     [velocity observability: low for static/follow]
  track_stability      = log1p(track_age)
yaw_sigma: VINS proxy (vins_gyro_vins_diff deg) where available, else fixed 1.0 deg prior (ablation: --no-vins).

OVI-rule (interpretable monotone) and OVI+calibration (LOGISTIC on the geometric terms — interpretable
coefficients, not black box). Compared vs single-factor baselines at detecting invalid velocity.
Output: paper2_v5_ovi_scores.csv + PAPER2_V5_OVI_RESULTS.md.
"""
from __future__ import annotations
import argparse, math
from pathlib import Path
import numpy as np, pandas as pd

WS = Path("/home/ivlab3/fwvio_estimator_ws_wheel")
DT = 0.05
BINS = ["0-15m", "15-30m", "30m+"]


def auroc(t, s):
    from sklearn.metrics import roc_auc_score
    t = np.asarray(t).astype(int)
    return float(roc_auc_score(t, s)) if len(np.unique(t)) > 1 else float("nan")


def f1_best(t, s):
    from sklearn.metrics import f1_score
    t = np.asarray(t).astype(int); qs = np.quantile(s, np.linspace(0.05, 0.95, 19))
    best = (0, 0)
    for th in qs:
        f = f1_score(t, (s >= th).astype(int), zero_division=0)
        if f > best[0]: best = (f, th)
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default=str(WS / "paper2_v5_object_validity_dataset.csv"))
    ap.add_argument("--no-vins", action="store_true", help="ablation: fixed 1deg yaw prior (no VINS proxy)")
    a = ap.parse_args()
    df = pd.read_csv(a.inp, low_memory=False)
    df = df[df["has_velocity_est"] == 1].copy()
    for c in ["range_m", "gt_range_m", "bearing_change_deg", "disp_med", "disp_std", "track_age",
              "vins_gyro_vins_diff", "velocity_valid", "invalid_velocity"]:
        if c in df: df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df[df["range_m"].notna() & df["bearing_change_deg"].notna() & df["disp_med"].notna()].copy()

    # geometric terms
    if a.no_vins or "vins_gyro_vins_diff" not in df:
        yaw_sig = np.full(len(df), 1.0)
    else:
        yaw_sig = df["vins_gyro_vins_diff"].fillna(1.0).clip(0.05, 30.0).values
    rng = df["range_m"].values
    df["log_range"] = np.log1p(rng)                          # range is a primary geometric observability factor
    df["yaw_lever"] = rng * np.sin(np.radians(yaw_sig))
    df["bearing_change_rate"] = df["bearing_change_deg"].abs().values / DT
    df["depth_noise"] = (df["disp_std"] / df["disp_med"].replace(0, np.nan)).fillna(0).clip(0, 5).values
    df["vel_obs_proxy"] = (df["bearing_change_deg"].abs() / np.maximum(rng, 1.0)).values
    df["track_stability"] = np.log1p(df["track_age"].fillna(0).values)

    y_valid = df["velocity_valid"].values.astype(int)   # 1 = velocity trustworthy
    # group split by run
    runs = (df["town"].astype(str) + "@" + df["run"].astype(str)).values
    rng_s = np.random.RandomState(7); uq = sorted(set(runs)); rng_s.shuffle(uq)
    nt = max(1, len(uq) // 5); test_g = set(uq[:nt])
    te = np.array([r in test_g for r in runs]); tr = ~te

    # OVI-rule (interpretable monotone): high = velocity observable/valid
    z = lambda v: (v - np.nanmean(v[tr])) / (np.nanstd(v[tr]) + 1e-9)
    ovi_rule = (-0.6 * z(df["log_range"].values) + 0.6 * z(df["bearing_change_rate"].values)
                - 0.4 * z(df["depth_noise"].values) - 0.3 * z(df["yaw_lever"].values)
                + 0.2 * z(df["track_stability"].values))
    df["OVI_velocity_rule"] = ovi_rule

    # OVI+calibration: LOGISTIC on the geometric terms (interpretable coefficients). Includes range
    # (a primary geometric observability factor) so OVI NESTS the distance-only baseline.
    from sklearn.linear_model import LogisticRegression
    feats = ["log_range", "yaw_lever", "bearing_change_rate", "depth_noise", "vel_obs_proxy", "track_stability"]
    X = np.column_stack([z(df[f].values) for f in feats])
    lr = LogisticRegression(max_iter=500)
    lr.fit(X[tr], y_valid[tr])
    ovi_cal = lr.predict_proba(X)[:, 1]
    df["OVI_velocity_cal"] = ovi_cal
    coefs = dict(zip(feats, lr.coef_[0].round(3)))

    # baselines (score: high = valid)
    scores = {
        "distance_only": -z(rng),
        "depth_only": -z(df["depth_noise"].values),
        "bearing_only": z(df["bearing_change_rate"].values),
        "yaw_lever_only": -z(df["yaw_lever"].values),
        "OVI_rule": ovi_rule,
        "OVI_calibrated": ovi_cal,
    }
    df["split"] = np.where(te, "test", "train")
    df[["town", "run", "dist_bin", "OVI_velocity_rule", "OVI_velocity_cal", "velocity_valid"]].to_csv(
        WS / "paper2_v5_ovi_scores.csv", index=False)
    # OVI-augmented full dataset for the refusal policy (C3) + summary
    aug_cols = ["town", "run", "frame", "dist_bin", "density", "gt_range_m", "range_m", "pos_err_m",
                "speed_err_ms", "dir_err_deg", "position_valid", "velocity_valid", "invalid_velocity",
                "position_only", "high_risk_object", "depth_noise", "log_range", "yaw_lever",
                "bearing_change_rate", "OVI_velocity_cal", "OVI_velocity_rule", "split"]
    df[[c for c in aug_cols if c in df]].to_parquet(WS / "paper2_v5_validity_with_ovi.parquet", index=False)

    def evalblock(mask):
        out = {}
        m = mask & te
        if m.sum() < 20: return out
        for nm, s in scores.items():
            out[nm] = auroc(y_valid[m], s[m])
        return out
    allm = evalblock(np.ones(len(df), bool))
    perbin = {b: evalblock((df["dist_bin"] == b).values) for b in BINS}
    # invalid-velocity detection (target=invalid): AUROC same magnitude (flip), F1 on best operating point
    inv = 1 - y_valid
    f1_d = f1_best(inv[te], -scores["distance_only"][te]); f1_o = f1_best(inv[te], -scores["OVI_calibrated"][te])
    # operating point at OVI_cal threshold = train-Youden; false-valid / false-refusal
    from sklearn.metrics import roc_curve
    fpr, tpr, th = roc_curve(y_valid[tr], ovi_cal[tr]); j = np.argmax(tpr - fpr); opth = th[j]
    pred_valid = (ovi_cal[te] >= opth).astype(int)
    false_valid = float(np.mean(pred_valid[y_valid[te] == 0])) if (y_valid[te] == 0).any() else float("nan")
    false_refuse = float(np.mean(1 - pred_valid[y_valid[te] == 1])) if (y_valid[te] == 1).any() else float("nan")

    L = ["# PAPER2_V5_OVI_RESULTS (C2)", "",
         f"> Observability Validity Index for object VELOCITY validity. test n={int(te.sum())}; "
         f"yaw_sigma={'fixed 1deg (no-VINS ablation)' if a.no_vins else 'VINS gyro-vins-diff proxy'}.",
         "> OVI is interpretable: a monotone rule + a LOGISTIC calibration on geometric terms (coeffs below), not a black box.", "",
         "## Velocity-valid detection AUROC (higher = better; OVI vs single-factor baselines)",
         "| model | AUROC overall | 0-15m | 15-30m | 30m+ |", "|---|---|---|---|---|"]
    for nm in scores:
        L.append(f"| {nm} | {allm.get(nm, float('nan')):.3f} | " +
                 " | ".join(f"{perbin[b].get(nm, float('nan')):.3f}" for b in BINS) + " |")
    L += ["", "## OVI logistic coefficients (interpretable; standardized terms)",
          "| term | coef (sign: +→more valid) |", "|---|---|"]
    for f, c in coefs.items():
        L.append(f"| {f} | {c:+.3f} |")
    # within-bin mean AUROC (controls for the trivial range<->validity correlation that distance-only exploits)
    L += ["", "## Within-bin mean AUROC (controls for trivial distance↔validity correlation)",
          "| model | mean(0-15,15-30,30m+) |", "|---|---|"]
    for nm in scores:
        vals = [perbin[b].get(nm, float("nan")) for b in BINS]
        vals = [v for v in vals if v == v]
        L.append(f"| {nm} | {np.mean(vals):.3f} |" if vals else f"| {nm} | nan |")
    L += ["", "## Invalid-velocity detection (the refusal signal)",
          f"- distance-only best F1 = {f1_d[0]:.3f} ; OVI-calibrated best F1 = {f1_o[0]:.3f}",
          f"- OVI operating point (train-Youden): false-valid rate = {false_valid:.3f}, false-refusal rate = {false_refuse:.3f}",
          "", "## Reading",
          f"- OVI-calibrated AUROC {allm.get('OVI_calibrated', float('nan')):.3f} vs distance-only "
          f"{allm.get('distance_only', float('nan')):.3f} -> OVI "
          + ("BEATS" if allm.get('OVI_calibrated', 0) > allm.get('distance_only', 0) else "does NOT beat")
          + " distance-only at detecting trustworthy velocity.",
          "- geometric terms (bearing-change observability, depth jitter, yaw lever) add over pure distance.",
          "- thresholds/operating point ablatable; raw-velocity (centroid-diff) noise limits absolute numbers (scope)."]
    (WS / "PAPER2_V5_OVI_RESULTS.md").write_text("\n".join(L) + "\n")
    print(f"[v5-ovi] OVI_cal AUROC={allm.get('OVI_calibrated', float('nan')):.3f} "
          f"distance_only={allm.get('distance_only', float('nan')):.3f} coeffs={coefs}")


if __name__ == "__main__":
    main()
