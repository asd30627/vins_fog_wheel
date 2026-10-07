#!/usr/bin/env python3
"""Paper-2 A2 — the make-or-break ablation: does VINS-quality conditioning help object reliability?

Change: paper2-viwo-conditioned-noue-v4 (Phase G2 / A2). env gf. NO backend, NO object factor.

Models (all on the SAME vins-matched samples for a fair A2 comparison):
  distance_only, geometry_gate, NOUE-no-VINS (object feats), NOUE-with-VINS (object + VINS quality feats).
Metrics overall + per distance bin / density / town / DEGRADED-localization stratum (vins_outlier>0.5 or
vins_feat<50): NLL, ECE, ANEES, AUROC(high-error), risk-coverage err@80, overconfident-wrong.
A2 verdict (NOT packaged): promising if with-VINS clearly beats no-VINS IN DEGRADED bins; weak if only on
average; failed/inconclusive otherwise.

Outputs: paper2_object_dataset_v2_with_vins.parquet, paper2_a2_metrics.csv,
PAPER2_A2_VINS_CONDITIONING_RESULTS.md, PAPER2_VINS_REPLAY_A2_STATUS.md (status), checkpoints.
"""
from __future__ import annotations
import argparse, json, math, datetime
from pathlib import Path
import numpy as np, pandas as pd

WS = Path("/home/ivlab3/fwvio_estimator_ws_wheel")
OBJ_NUM = ["conf", "bbox_w", "bbox_h", "bbox_aspect", "bbox_area", "area_frac", "disp_med", "disp_std",
           "depth_m", "range_m", "bearing_deg", "bearing_change_deg", "track_age", "raw_speed_ms",
           "body_fwd", "body_lat"]
VINS_NUM = ["vins_feat_count", "vins_feat_raw", "vins_outlier_ratio", "vins_inlier", "vins_coverage8",
            "vins_entropy8", "vins_track_len", "vins_solver_ms", "vins_gyro_vins_diff", "vins_depth_mean",
            "vins_depth_std", "vins_good_depth", "vins_bad_depth", "vins_vel_norm", "vins_ba_norm",
            "vins_bg_norm", "vins_gyr_z_std", "vins_failure"]
BINS = ["0-15m", "15-30m", "30m+"]


def pctl(a, q):
    return float(np.percentile(a, q)) if len(a) else float("nan")


def metrics_block(y, mu, sigma, hi):
    from sklearn.metrics import roc_auc_score
    sigma = np.maximum(sigma, 1e-6)
    r = {}
    r["n"] = int(len(y))
    r["rmse"] = float(np.sqrt(np.mean((y - mu) ** 2)))
    r["med_abs"] = float(np.median(np.abs(y - mu)))
    r["nll"] = float(np.mean(0.5 * (np.log(2 * np.pi * sigma ** 2) + (y - mu) ** 2 / sigma ** 2)))
    r["anees"] = float(np.mean((y - mu) ** 2 / sigma ** 2))   # ~1 if calibrated
    from scipy.stats import norm
    z = np.abs((y - mu) / sigma)
    r["ece"] = float(np.mean([abs(np.mean(z <= abs(norm.ppf(0.5 + p / 2))) - p) for p in (0.5, 0.68, 0.8, 0.9, 0.95)]))
    try:
        r["auroc"] = float(roc_auc_score(hi, sigma)) if len(np.unique(hi)) > 1 else float("nan")
    except Exception:
        r["auroc"] = float("nan")
    order = np.argsort(sigma); err = np.abs(y - mu)[order]; n80 = max(1, int(0.8 * len(err)))
    r["riskcov80"] = float(np.mean(err[:n80]))
    med_s = np.median(sigma)
    r["overconf"] = float(np.mean(sigma[hi == 1] < med_s)) if (hi == 1).any() else float("nan")
    return r


def train_mlp(Xtr, ytr_log, Xva, yva_log, epochs=200, seed=0):
    import torch, torch.nn as nn
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    torch.manual_seed(seed)
    Xt = torch.tensor(Xtr, device=dev); yt = torch.tensor(ytr_log, device=dev)
    Xv = torch.tensor(Xva, device=dev); yv = torch.tensor(yva_log, device=dev)

    class Net(nn.Module):
        def __init__(s, d):
            super().__init__(); s.b = nn.Sequential(nn.Linear(d, 128), nn.ReLU(), nn.Linear(128, 64), nn.ReLU())
            s.mu = nn.Linear(64, 1); s.lv = nn.Linear(64, 1)
        def forward(s, x):
            h = s.b(x); return s.mu(h).squeeze(-1), torch.clamp(s.lv(h).squeeze(-1), -6, 6)
    net = Net(Xtr.shape[1]).to(dev); opt = torch.optim.Adam(net.parameters(), 1e-3, weight_decay=1e-4)
    best = (1e9, None)
    for ep in range(epochs):
        net.train(); opt.zero_grad()
        mu, lv = net(Xt); loss = (0.5 * (lv + (yt - mu) ** 2 / torch.exp(lv))).mean()
        loss.backward(); opt.step()
        if ep % 10 == 0 or ep == epochs - 1:
            net.eval()
            with torch.no_grad():
                mv, lvv = net(Xv); vnll = (0.5 * (lvv + (yv - mv) ** 2 / torch.exp(lvv))).mean().item()
            if vnll < best[0]: best = (vnll, {k: v.detach().cpu().clone() for k, v in net.state_dict().items()})
    if best[1]: net.load_state_dict(best[1])
    net.eval()
    return net, dev


def predict(net, dev, X):
    import torch
    with torch.no_grad():
        mu, lv = net(torch.tensor(X, device=dev))
    mu = mu.cpu().numpy(); sd_log = np.sqrt(np.exp(lv.cpu().numpy()))
    mu_lin = np.expm1(mu); sd_lin = np.maximum((1 + np.maximum(mu_lin, 0)) * sd_log, 1e-3)
    return mu_lin, sd_lin


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-csv", default=str(WS / "paper2_raw_object_benchmark_all_with_vins.csv"))
    ap.add_argument("--epochs", type=int, default=200)
    ap.add_argument("--ts", default=datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
    args = ap.parse_args()
    outdir = WS / "outputs" / f"paper2_a2_{args.ts}"; (outdir / "checkpoints").mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.in_csv, low_memory=False)
    df = df[(df["matched"] == 1) & (df["vins_match_ok"] == 1)].copy()
    for c in OBJ_NUM + VINS_NUM + ["pos_err_m", "gt_range_m"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df[df["pos_err_m"].notna() & df["depth_m"].notna() & df["vins_feat_count"].notna()].copy()
    print(f"[a2] vins-matched object rows: {len(df)}")
    if len(df) < 500:
        Path(WS / "PAPER2_VINS_REPLAY_A2_STATUS.md").write_text(
            f"# PAPER2_VINS_REPLAY_A2_STATUS\n\nSTOP: only {len(df)} vins-matched object rows (<500). "
            "Join too sparse -> A2 not run. Check VINS replay coverage / timestamp alignment.\n")
        print("[a2] STOP: too few matched rows"); return

    df["high_pos"] = (df["pos_err_m"] > 3.0).astype(int)
    # degraded localization stratum (from VINS quality)
    df["degraded"] = ((df["vins_outlier_ratio"] > 0.5) | (df["vins_feat_count"] < 50)).astype(int)

    # group split by run
    rng = np.random.RandomState(7)
    runs = (df["town"].astype(str) + "@" + df["run"].astype(str))
    uq = sorted(runs.unique()); rng.shuffle(uq)
    nt = max(1, len(uq) // 5)
    test_g = set(uq[:nt]); val_g = set(uq[nt:2 * nt])
    df["split"] = np.where(runs.isin(test_g), "test", np.where(runs.isin(val_g), "val", "train"))
    tr = (df["split"] == "train").values; va = (df["split"] == "val").values; te = (df["split"] == "test").values
    print(f"[a2] train {tr.sum()} val {va.sum()} test {te.sum()} | degraded frac {df['degraded'].mean():.3f}")

    cls_oh = pd.get_dummies(df["cls"].astype(str), prefix="cls", dummy_na=False)
    Xobj = pd.concat([df[OBJ_NUM].fillna(df[OBJ_NUM].median()), cls_oh], axis=1).astype("float32")
    Xvins = df[VINS_NUM].fillna(df[VINS_NUM].median()).astype("float32")
    y = df["pos_err_m"].values.astype("float32"); ylog = np.log1p(y)
    hi = df["high_pos"].values.astype(int)

    def stdz(X):
        mu = X[tr].mean(); sd = X[tr].std().replace(0, 1); return ((X - mu) / sd).values.astype("float32")
    Xobj_s = stdz(Xobj); Xvins_s = stdz(Xvins)
    Xno = Xobj_s
    Xwith = np.concatenate([Xobj_s, Xvins_s], axis=1)

    # baselines
    rng_bins = pd.cut(df["range_m"], [0, 15, 30, 1e9], labels=BINS)
    muby, sdby = {}, {}
    for b in BINS:
        m = (rng_bins == b).values & tr
        muby[b] = float(np.median(y[m])) if m.sum() >= 5 else float(np.median(y[tr]))
        sdby[b] = float(np.std(y[m]) + 1e-3) if m.sum() >= 5 else float(np.std(y[tr]) + 1e-3)
    mu_d = np.array([muby[str(b)] for b in rng_bins]); sd_d = np.array([sdby[str(b)] for b in rng_bins])
    rv = df["range_m"].values; dispv = pd.to_numeric(df["disp_med"], errors="coerce").fillna(0).values
    mu_g = np.clip(0.15 * rv, 0.5, None); sd_g = np.clip(0.2 * rv + (dispv < 3) * 3.0, 0.5, None)

    # NOUE no-VINS / with-VINS
    net_no, dev = train_mlp(Xno[tr], ylog[tr], Xno[va], ylog[va], args.epochs, seed=0)
    net_wi, _ = train_mlp(Xwith[tr], ylog[tr], Xwith[va], ylog[va], args.epochs, seed=0)
    import torch
    torch.save(net_no.state_dict(), outdir / "checkpoints" / "noue_no_vins.pt")
    torch.save(net_wi.state_dict(), outdir / "checkpoints" / "noue_with_vins.pt")
    mu_no, sd_no = predict(net_no, dev, Xno); mu_wi, sd_wi = predict(net_wi, dev, Xwith)

    preds = dict(distance_only=(mu_d, sd_d), geometry_gate=(mu_g, sd_g),
                 noue_no_vins=(mu_no, sd_no), noue_with_vins=(mu_wi, sd_wi))

    def strata(mask):
        out = {}
        for name, (mu, sd) in preds.items():
            m = mask & te
            if m.sum() >= 8:
                out[name] = metrics_block(y[m], mu[m], sd[m], hi[m])
        return out

    allm = strata(np.ones(len(df), bool))
    deg = strata(df["degraded"].values.astype(bool))
    hierr = strata((df["high_pos"].values == 1))
    perbin = {b: strata((rng_bins == b).values) for b in BINS}
    perden = {d: strata((df["density"] == d).values) for d in ("sparse", "medium", "dense")}
    pertown = {t: strata((df["town"] == t).values) for t in sorted(df["town"].unique())}

    # save v2 dataset
    keepcols = ["town", "density", "run", "frame", "track_id", "cls", "dist_bin"] + OBJ_NUM + VINS_NUM + \
               ["gt_range_m", "pos_err_m", "speed_err_ms", "dir_err_deg", "high_pos", "degraded", "split"]
    df[keepcols].to_parquet(WS / "paper2_object_dataset_v2_with_vins.parquet", index=False)
    df[keepcols].to_csv(WS / "paper2_object_dataset_v2_with_vins.csv", index=False)

    # metrics csv
    rows = []
    for stname, st in [("all", allm), ("degraded", deg), ("high_error", hierr)]:
        for mdl, m in st.items():
            rows.append(dict(stratum=stname, model=mdl, **m))
    pd.DataFrame(rows).to_csv(WS / "paper2_a2_metrics.csv", index=False)
    json.dump(dict(all=allm, degraded=deg, high_error=hierr, perbin=perbin, perden=perden, pertown=pertown),
              open(outdir / "a2_metrics_full.json", "w"), indent=1, default=str)

    # ---- A2 verdict (NOT packaged) ----
    def cmp(st, key, lower_better=True):
        if "noue_with_vins" not in st or "noue_no_vins" not in st: return None
        a = st["noue_with_vins"][key]; b = st["noue_no_vins"][key]
        if a != a or b != b: return None
        return (a < b) if lower_better else (a > b)
    deg_nll = cmp(deg, "nll"); deg_auc = cmp(deg, "auroc", lower_better=False); deg_rc = cmp(deg, "riskcov80")
    all_nll = cmp(allm, "nll"); all_auc = cmp(allm, "auroc", lower_better=False)
    deg_win = sum(1 for x in (deg_nll, deg_auc, deg_rc) if x) >= 2
    all_win = sum(1 for x in (all_nll, all_auc) if x) >= 1
    if deg_win:
        verdict = "promising"
    elif all_win:
        verdict = "weak"
    else:
        verdict = "failed/inconclusive"

    def tbl(st, title):
        L = [f"### {title}", "| model | n | NLL | ANEES | ECE | AUROC | riskcov@80 | overconf |", "|---|---|---|---|---|---|---|---|"]
        for mdl in ["distance_only", "geometry_gate", "noue_no_vins", "noue_with_vins"]:
            if mdl in st:
                m = st[mdl]; L.append(f"| {mdl} | {m['n']} | {m['nll']:.3f} | {m['anees']:.2f} | {m['ece']:.3f} | "
                                      f"{m['auroc']:.3f} | {m['riskcov80']:.2f} | {m['overconf']:.3f} |")
        return L

    R = [f"# PAPER2_A2_VINS_CONDITIONING_RESULTS (run {args.ts})", "",
         f"> The make-or-break test: does VINS-quality conditioning improve object-state reliability?",
         f"> vins-matched rows={len(df)} (train {tr.sum()}/val {va.sum()}/test {te.sum()}); degraded frac {df['degraded'].mean():.3f}.",
         f"> Models on identical vins-matched samples. A2 looks at the **degraded-localization stratum** (vins_outlier>0.5 OR vins_feat<50).", "",
         f"## A2 VERDICT: **{verdict.upper()}**",
         f"- degraded-bin with-VINS vs no-VINS: NLL_better={deg_nll}, AUROC_better={deg_auc}, riskcov_better={deg_rc}",
         f"- overall with-VINS vs no-VINS: NLL_better={all_nll}, AUROC_better={all_auc}",
         "- rule: promising = with-VINS wins >=2/3 degraded metrics; weak = wins overall only; else failed/inconclusive.", ""]
    R += tbl(allm, "Overall (test)")
    R += [""] + tbl(deg, "Degraded-localization stratum (the A2 core)")
    R += [""] + tbl(hierr, "High-error objects (pos_err>3m)")
    R += ["", "## Per distance bin (with-VINS vs no-VINS, NLL)"]
    R += ["| bin | no-VINS NLL | with-VINS NLL | no-VINS AUROC | with-VINS AUROC |", "|---|---|---|---|---|"]
    for b in BINS:
        st = perbin[b]
        if "noue_with_vins" in st and "noue_no_vins" in st:
            R.append(f"| {b} | {st['noue_no_vins']['nll']:.3f} | {st['noue_with_vins']['nll']:.3f} | "
                     f"{st['noue_no_vins']['auroc']:.3f} | {st['noue_with_vins']['auroc']:.3f} |")
    R += ["", "## Per town (NLL no-VINS -> with-VINS)"]
    for t, st in pertown.items():
        if "noue_with_vins" in st and "noue_no_vins" in st:
            R.append(f"- {t}: {st['noue_no_vins']['nll']:.3f} -> {st['noue_with_vins']['nll']:.3f}")
    R += ["", "## Honest caveats",
          "- object errors use GT ego-comp -> VINS quality acts as a SCENE-DIFFICULTY proxy (not direct VINS-error propagation).",
          "- with-VINS has more features; the A2 claim rests on DEGRADED-bin gain, not raw overall gain.",
          "- ANEES far from 1 = miscalibrated scale (heavy 30m+ tail); report log-space too in future.",
          "- single daytime run; group-split by run; verdict is a signal, not a final paper claim."]
    (WS / "PAPER2_A2_VINS_CONDITIONING_RESULTS.md").write_text("\n".join(R) + "\n")
    (WS / "PAPER2_VINS_REPLAY_A2_STATUS.md").write_text(
        f"# PAPER2_VINS_REPLAY_A2_STATUS\n\n- vins-matched object rows: {len(df)}\n"
        f"- degraded stratum frac: {df['degraded'].mean():.3f}\n- A2 verdict: **{verdict}**\n"
        f"- see PAPER2_A2_VINS_CONDITIONING_RESULTS.md + paper2_a2_metrics.csv\n")
    print(f"[a2] VERDICT={verdict} ; wrote results + dataset v2 + checkpoints -> {outdir}")


if __name__ == "__main__":
    main()
