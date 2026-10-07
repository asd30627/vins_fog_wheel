#!/usr/bin/env python3
"""Paper-2 G2 — NOUE training + baselines + A2 framing (STANDALONE, env gf).

Change: paper2-viwo-conditioned-noue-v4 (Phase G2).

Trains, on the object dataset (paper2_object_dataset_v1.parquet):
  - distance-only baseline (range -> uncertainty via binned stats)
  - geometry-rule gate (non-learning)
  - object-feature MLP = NOUE-object  (Gaussian-NLL pos-error head + BCE heads)
A2 (NOUE-full WITH VINS quality vs WITHOUT) is BLOCKED tonight: no reliability_features_vins.csv for
these recordings (needs a VINS replay). We report the achievable object-side comparison and mark A2 blocked.
H1 (state-residual refine) is an ISOLATED ablation (separate model/metrics).

Metrics (per model, overall + per distance bin): error-prediction RMSE/median/p95, Gaussian NLL,
calibration error (interval coverage), AUROC for high_pos_error, risk-coverage error@80%, overconfident-wrong rate.

Outputs: outputs/paper2_g2_<ts>/{checkpoints, paper2_noue_g2_metrics.csv} + PAPER2_NOUE_G2_RESULTS.md
"""
from __future__ import annotations
import argparse, json, math, datetime
from pathlib import Path
import numpy as np, pandas as pd

WS = Path("/home/ivlab3/fwvio_estimator_ws_wheel")
NUM_FEATS = ["conf", "bbox_w", "bbox_h", "bbox_aspect", "bbox_area", "area_frac",
             "disp_med", "disp_std", "depth_m", "range_m", "bearing_deg", "bearing_change_deg",
             "track_age", "raw_speed_ms", "body_fwd", "body_lat"]
CAT_FEATS = ["cls", "density", "town"]
BINS = ["0-15m", "15-30m", "30m+"]


def onehot(df, cols):
    return pd.get_dummies(df[cols].astype(str), prefix=cols, dummy_na=False)


def calib_error(y, mu, sigma):
    """Interval-coverage calibration error: mean over nominal levels of |emp_coverage - nominal|."""
    z = np.abs((y - mu) / np.maximum(sigma, 1e-6))
    out = []
    for p in (0.5, 0.68, 0.8, 0.9, 0.95):
        k = math.sqrt(2) * 0 + abs(__import__("scipy.stats", fromlist=["norm"]).norm.ppf(0.5 + p / 2))
        out.append(abs(np.mean(z <= k) - p))
    return float(np.mean(out))


def risk_coverage(y_err, score):
    """score: predicted uncertainty (higher=worse). Retain lowest-score fraction; mean error@80% coverage."""
    order = np.argsort(score)
    ys = y_err[order]
    n80 = max(1, int(0.8 * len(ys)))
    return float(np.mean(ys[:n80]))


def metrics_block(y, mu, sigma, hi):
    from sklearn.metrics import roc_auc_score
    res = {}
    res["rmse"] = float(np.sqrt(np.mean((y - mu) ** 2)))
    res["med_abs"] = float(np.median(np.abs(y - mu)))
    res["p95_abs"] = float(np.percentile(np.abs(y - mu), 95))
    res["nll"] = float(np.mean(0.5 * (np.log(2 * np.pi * sigma ** 2) + (y - mu) ** 2 / sigma ** 2)))
    res["calib_err"] = calib_error(y, mu, sigma)
    try:
        res["auroc_high"] = float(roc_auc_score(hi, sigma)) if len(np.unique(hi)) > 1 else float("nan")
    except Exception:
        res["auroc_high"] = float("nan")
    res["riskcov_err80"] = risk_coverage(np.abs(y - mu), sigma)
    # overconfident-wrong: high-error samples assigned below-median sigma
    med_s = np.median(sigma)
    res["overconf_wrong"] = float(np.mean(sigma[hi == 1] < med_s)) if (hi == 1).any() else float("nan")
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ds", default=str(WS / "paper2_object_dataset_v1.parquet"))
    ap.add_argument("--epochs", type=int, default=200)
    ap.add_argument("--ts", default=datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
    args = ap.parse_args()
    outdir = WS / "outputs" / f"paper2_g2_{args.ts}"; (outdir / "checkpoints").mkdir(parents=True, exist_ok=True)

    df = pd.read_parquet(args.ds)
    df = df[df["pos_err_m"].notna()].copy()
    Xnum = df[NUM_FEATS].astype(float).fillna(df[NUM_FEATS].astype(float).median())
    Xcat = onehot(df, CAT_FEATS)
    X = pd.concat([Xnum, Xcat], axis=1).astype("float32")
    y = df["pos_err_m"].values.astype("float32")
    hi = df["high_pos_error"].values.astype("int64")
    inv = df["invalid_velocity"].values.astype("float32")
    obs = df["observability"].values.astype("float32")
    util = df["utility"].values.astype("float32")
    sp = df["split"].values
    tr, va, te = sp == "train", sp == "val", sp == "test"
    print(f"[g2] n={len(df)} feats={X.shape[1]} train={tr.sum()} val={va.sum()} test={te.sum()}")
    if te.sum() < 20 or tr.sum() < 50:
        print("[g2] WARN small split; metrics noisy")

    mu_tr = X[tr].mean(); sd_tr = X[tr].std().replace(0, 1)
    Xs = ((X - mu_tr) / sd_tr).values.astype("float32")

    metrics = {}
    # ---- baseline: distance-only (binned median mu + IQR sigma from TRAIN) ----
    rng_bins = pd.cut(df["range_m"], bins=[0, 15, 30, 1e9], labels=BINS)
    mu_by, sd_by = {}, {}
    for b in BINS:
        m = (rng_bins == b) & tr
        if m.sum() >= 5:
            mu_by[b] = float(np.median(y[m])); sd_by[b] = float(np.std(y[m]) + 1e-3)
        else:
            mu_by[b] = float(np.median(y[tr])); sd_by[b] = float(np.std(y[tr]) + 1e-3)
    mu_d = np.array([mu_by[str(b)] for b in rng_bins]); sd_d = np.array([sd_by[str(b)] for b in rng_bins])
    metrics["distance_only"] = metrics_block(y[te], mu_d[te], sd_d[te], hi[te])

    # ---- baseline: geometry-rule gate (range & disparity heuristic) ----
    rng_v = df["range_m"].values; disp_v = pd.to_numeric(df["disp_med"], errors="coerce").fillna(0).values
    mu_g = np.clip(0.15 * rng_v, 0.5, None)               # error grows ~linearly with range
    sd_g = np.clip(0.20 * rng_v + (disp_v < 3.0) * 3.0, 0.5, None)
    metrics["geometry_gate"] = metrics_block(y[te], mu_g[te], sd_g[te], hi[te])

    # ---- NOUE-object: MLP, Gaussian-NLL pos-error head + BCE(invalid/obs/util) ----
    import torch, torch.nn as nn
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    torch.manual_seed(0)
    Xt = torch.tensor(Xs, device=dev)
    yt = torch.tensor(y, device=dev); lyt = torch.log1p(yt)   # predict log1p(pos_err) for stability
    invt = torch.tensor(inv, device=dev); obst = torch.tensor(obs, device=dev); utt = torch.tensor(util, device=dev)
    tri = torch.tensor(np.where(tr)[0], device=dev); vai = torch.tensor(np.where(va)[0], device=dev)

    class NOUE(nn.Module):
        def __init__(s, d):
            super().__init__()
            s.tr = nn.Sequential(nn.Linear(d, 128), nn.ReLU(), nn.Linear(128, 64), nn.ReLU())
            s.mu = nn.Linear(64, 1); s.lv = nn.Linear(64, 1)
            s.inv = nn.Linear(64, 1); s.obs = nn.Linear(64, 1); s.ut = nn.Linear(64, 1)
        def forward(s, x):
            h = s.tr(x)
            return s.mu(h).squeeze(-1), s.lv(h).squeeze(-1), s.inv(h).squeeze(-1), s.obs(h).squeeze(-1), s.ut(h).squeeze(-1)

    net = NOUE(Xs.shape[1]).to(dev); opt = torch.optim.Adam(net.parameters(), lr=1e-3, weight_decay=1e-4)
    bce = nn.BCEWithLogitsLoss()
    best = (1e9, None)
    for ep in range(args.epochs):
        net.train(); opt.zero_grad()
        mu, lv, pinv, pobs, put = net(Xt[tri])
        lv = torch.clamp(lv, -6, 6)
        nll = (0.5 * (lv + (lyt[tri] - mu) ** 2 / torch.exp(lv))).mean()
        loss = nll + bce(pinv, invt[tri]) + bce(pobs, obst[tri]) + bce(put, utt[tri])
        loss.backward(); opt.step()
        if ep % 20 == 0 or ep == args.epochs - 1:
            net.eval()
            with torch.no_grad():
                mu_v, lv_v, *_ = net(Xt[vai]); lv_v = torch.clamp(lv_v, -6, 6)
                vnll = (0.5 * (lv_v + (lyt[vai] - mu_v) ** 2 / torch.exp(lv_v))).mean().item()
            if vnll < best[0]:
                best = (vnll, {k: v.detach().cpu().clone() for k, v in net.state_dict().items()})
    if best[1]:
        net.load_state_dict(best[1])
    torch.save(net.state_dict(), outdir / "checkpoints" / "noue_object.pt")
    net.eval()
    with torch.no_grad():
        mu_a, lv_a, pinv_a, pobs_a, put_a = net(Xt)
        lv_a = torch.clamp(lv_a, -6, 6)
    # back-transform from log1p space to error space (mu in log1p) for metrics
    mu_lin = np.expm1(mu_a.cpu().numpy()); sd_log = np.sqrt(np.exp(lv_a.cpu().numpy()))
    # delta-method sigma in linear space: d expm1 = exp(log1p)=1+err ; sigma_lin ~ (1+mu_lin)*sd_log
    sd_lin = np.maximum((1 + np.maximum(mu_lin, 0)) * sd_log, 1e-3)
    metrics["noue_object"] = metrics_block(y[te], mu_lin[te], sd_lin[te], hi[te])

    # per-distance-bin metrics for noue_object
    perbin = {}
    for b in BINS:
        mb = (rng_bins == b).values & te
        if mb.sum() >= 8:
            perbin[b] = metrics_block(y[mb], mu_lin[mb], sd_lin[mb], hi[mb])
    metrics["noue_object_perbin"] = perbin

    # binary head quality
    from sklearn.metrics import roc_auc_score
    def safe_auc(t, s):
        t = t.astype(int)
        return float(roc_auc_score(t, s)) if len(np.unique(t)) > 1 else float("nan")
    metrics["heads_auroc"] = dict(
        invalid_velocity=safe_auc(inv[te], torch.sigmoid(pinv_a).cpu().numpy()[te]),
        observability=safe_auc(obs[te], torch.sigmoid(pobs_a).cpu().numpy()[te]),
        utility=safe_auc(util[te], torch.sigmoid(put_a).cpu().numpy()[te]))

    # dump test-set predictions for output-policy / G3-lite (decoupled)
    te_idx = np.where(te)[0]
    preds = pd.DataFrame(dict(
        town=df["town"].values[te], density=df["density"].values[te], dist_bin=df["dist_bin"].values[te],
        range_m=df["range_m"].values[te], gt_range_m=df["gt_range_m"].values[te],
        pos_err_m=y[te], pred_pos_err=mu_lin[te], pred_sigma=sd_lin[te],
        p_invalid_vel=torch.sigmoid(pinv_a).cpu().numpy()[te],
        p_observability=torch.sigmoid(pobs_a).cpu().numpy()[te],
        p_utility=torch.sigmoid(put_a).cpu().numpy()[te],
        invalid_velocity=inv[te], observability=obs[te], utility=util[te],
        speed_err_ms=df["speed_err_ms"].values[te]))
    preds.to_csv(outdir / "test_predictions.csv", index=False)
    (WS / "paper2_g2_test_predictions.csv").write_text((outdir / "test_predictions.csv").read_text())

    # ---- H1 isolated ablation: residual refine head predicts delta to reduce pos_err proxy ----
    # (isolated: separate tiny net predicting a multiplicative shrink of raw error; report RMSE + calib impact)
    class H1(nn.Module):
        def __init__(s, d):
            super().__init__(); s.net = nn.Sequential(nn.Linear(d, 64), nn.ReLU(), nn.Linear(64, 1))
        def forward(s, x): return s.net(x).squeeze(-1)
    h1 = H1(Xs.shape[1]).to(dev); o2 = torch.optim.Adam(h1.parameters(), lr=1e-3, weight_decay=1e-4)
    for ep in range(args.epochs):
        h1.train(); o2.zero_grad()
        pred = h1(Xt[tri])  # predict log1p(pos_err) directly (point estimate, no uncertainty)
        l = ((pred - lyt[tri]) ** 2).mean(); l.backward(); o2.step()
    h1.eval()
    with torch.no_grad():
        h1p = np.expm1(h1(Xt).cpu().numpy())
    # H1 "refine": use its point estimate as mu, but it has NO calibrated sigma -> reuse a constant sigma
    sd_const = np.full_like(h1p, np.std(y[tr]) + 1e-3)
    metrics["h1_residual_refine"] = metrics_block(y[te], h1p[te], sd_const[te], hi[te])
    torch.save(h1.state_dict(), outdir / "checkpoints" / "h1_residual.pt")

    # ---- A2: BLOCKED ----
    metrics["A2_with_vins_quality"] = {"status": "BLOCKED",
        "reason": "no reliability_features_vins.csv for these CARLA recordings (needs VINS replay); per G0 spec, VINS-conditioned marked blocked, not fabricated"}

    # write metrics csv + report
    rows = []
    for model in ["distance_only", "geometry_gate", "noue_object", "h1_residual_refine"]:
        m = metrics[model]; rows.append(dict(model=model, **{k: round(v, 4) for k, v in m.items()}))
    pd.DataFrame(rows).to_csv(outdir / "paper2_noue_g2_metrics.csv", index=False)
    (WS / "paper2_noue_g2_metrics.csv").write_text((outdir / "paper2_noue_g2_metrics.csv").read_text())
    json.dump(metrics, open(outdir / "metrics_full.json", "w"), indent=1, default=str)

    # A2 verdict (achievable comparison: does NOUE-object beat distance-only / geometry on calibration?)
    no = metrics["noue_object"]; do = metrics["distance_only"]; ge = metrics["geometry_gate"]
    beats = (no["nll"] < do["nll"]) and (no["auroc_high"] > max(do["auroc_high"], ge["auroc_high"]) if no["auroc_high"]==no["auroc_high"] else False)

    R = [f"# PAPER2_NOUE_G2_RESULTS — Phase G2 (run {args.ts})", "",
         f"> dataset n={len(df)} (train {tr.sum()}/val {va.sum()}/test {te.sum()}); feats={X.shape[1]} (object-only).",
         "> **A2 (VINS-quality conditioning) = BLOCKED** — no reliability_features_vins.csv for these recordings (needs VINS replay). Not fabricated.",
         "> Achievable G2 comparison tonight: distance-only vs geometry-gate vs NOUE-object (learned, all object features).", "",
         "## Test metrics (pos-error prediction + calibration)",
         "| model | rmse | med_abs | p95_abs | NLL | calib_err | AUROC_high | riskcov_err@80 | overconf_wrong |",
         "|---|---|---|---|---|---|---|---|---|"]
    for model in ["distance_only", "geometry_gate", "noue_object", "h1_residual_refine"]:
        m = metrics[model]
        R.append(f"| {model} | {m['rmse']:.2f} | {m['med_abs']:.2f} | {m['p95_abs']:.2f} | {m['nll']:.3f} | "
                 f"{m['calib_err']:.3f} | {m['auroc_high']:.3f} | {m['riskcov_err80']:.2f} | {m['overconf_wrong']:.3f} |")
    R += ["", "## NOUE-object per distance bin", "| bin | n_metric | rmse | NLL | AUROC_high | overconf_wrong |", "|---|---|---|---|---|---|"]
    for b in BINS:
        if b in perbin:
            m = perbin[b]; R.append(f"| {b} | - | {m['rmse']:.2f} | {m['nll']:.3f} | {m['auroc_high']:.3f} | {m['overconf_wrong']:.3f} |")
    R += ["", "## NOUE-object binary heads (AUROC)",
          f"- invalid_velocity: {metrics['heads_auroc']['invalid_velocity']}",
          f"- observability: {metrics['heads_auroc']['observability']}",
          f"- utility: {metrics['heads_auroc']['utility']}", "",
          "## H1 isolated ablation",
          "- H1 = point-estimate residual refine (NO calibrated uncertainty); reused constant sigma for metrics.",
          f"- H1 rmse={metrics['h1_residual_refine']['rmse']:.2f} vs NOUE-object rmse={no['rmse']:.2f}.",
          "- Interpretation: if H1 rmse < NOUE rmse but calib_err/NLL worse, it trades calibration for point accuracy (keep isolated).", "",
          "## A2 status", f"- **{metrics['A2_with_vins_quality']['status']}** — {metrics['A2_with_vins_quality']['reason']}",
          "- Achievable proxy verdict (NOUE-object vs distance-only/geometry): "
          + ("NOUE-object improves NLL+AUROC over baselines (object features help)." if beats
             else "NOUE-object does NOT clearly beat baselines on NLL+AUROC (object features alone limited)."),
          "", "## Honest caveats",
          "- A2's核心 (VINS-quality conditioning) NOT tested tonight — blocked on VINS replay.",
          "- small/medium dataset; group-split by run; metrics noisy if test small.",
          "- labels use fixed thresholds (pos>3m, spd>3, invalid spd>5 or dir>45) — choices, documented in builder."]
    (WS / "PAPER2_NOUE_G2_RESULTS.md").write_text("\n".join(R) + "\n")
    print(f"[g2] wrote PAPER2_NOUE_G2_RESULTS.md + metrics + checkpoints -> {outdir}")
    print("[g2] A2 = BLOCKED (VINS replay needed). NOUE-object vs baselines verdict:", "BEATS" if beats else "NOT-CLEAR")


if __name__ == "__main__":
    main()
