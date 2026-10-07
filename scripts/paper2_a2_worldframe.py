#!/usr/bin/env python3
"""Paper-2 A2 (test 2, the deployment-relevant mechanism) — VINS-error PROPAGATED object world error.

Change: paper2-viwo-conditioned-noue-v4 (Phase A2). env gf. NO backend.

Test 1 (paper2_a2_ablation.py) used GT ego-comp -> object error = SENSOR error only -> VINS quality was
just a scene-difficulty proxy -> A2 failed. Here we model the DEPLOYMENT mechanism: an object localized
via the VINS ego-pose inherits the VINS localization error. We:
  1. per recording: sim3-align VINS trajectory (vio.csv) to GT ego (gt/*.json) -> per-frame localization
     residual loc_err_xy (m) and yaw_err (rad).  [analytical propagation model — stated, not hidden]
  2. propagate to each detection: object_world_err = body_pos_err(sensor) + loc_err_xy + |yaw_err|*range.
  3. condition: NOUE-no-VINS (object feats) vs NOUE-with-VINS (+ VINS quality) predicting object_world_err.
Hypothesis: VINS quality SHOULD help here (object feats cannot see ego localization error; VINS quality can).

Outputs: appends to PAPER2_A2_VINS_CONDITIONING_RESULTS.md, writes paper2_a2_worldframe_metrics.csv,
updates PAPER2_VINS_REPLAY_A2_STATUS.md verdict.
"""
from __future__ import annotations
import argparse, csv, json, glob, math, datetime
from pathlib import Path
import numpy as np, pandas as pd

WS = Path("/home/ivlab3/fwvio_estimator_ws_wheel")
DATAROOT = Path("/mnt/sata4t/datasets/carla_fwvio")
VINSROOT = Path("/mnt/sata4t/ivlab3_data/fwvio/results/paper2_vins")
OBJ_NUM = ["conf", "bbox_w", "bbox_h", "bbox_aspect", "bbox_area", "area_frac", "disp_med", "disp_std",
           "depth_m", "range_m", "bearing_deg", "bearing_change_deg", "track_age", "raw_speed_ms",
           "body_fwd", "body_lat"]
VINS_NUM = ["vins_feat_count", "vins_feat_raw", "vins_outlier_ratio", "vins_inlier", "vins_coverage8",
            "vins_entropy8", "vins_track_len", "vins_solver_ms", "vins_gyro_vins_diff", "vins_depth_mean",
            "vins_depth_std", "vins_good_depth", "vins_bad_depth", "vins_vel_norm", "vins_ba_norm",
            "vins_bg_norm", "vins_gyr_z_std", "vins_failure"]
BINS = ["0-15m", "15-30m", "30m+"]


def umeyama_sim3_2d(src, tgt):
    """Least-squares sim3 (scale,R,t) aligning src->tgt (Nx2). Returns aligned src."""
    mu_s = src.mean(0); mu_t = tgt.mean(0)
    sc = src - mu_s; tc = tgt - mu_t
    cov = (tc.T @ sc) / len(src)
    U, D, Vt = np.linalg.svd(cov)
    S = np.eye(2)
    if np.linalg.det(U) * np.linalg.det(Vt) < 0:
        S[1, 1] = -1
    R = U @ S @ Vt
    var_s = (sc ** 2).sum() / len(src)
    s = (D * np.array([1, S[1, 1]])).sum() / var_s if var_s > 1e-9 else 1.0
    t = mu_t - s * R @ mu_s
    return (s * (R @ src.T).T + t), s


def quat_yaw(qx, qy, qz, qw):
    return math.atan2(2 * (qw * qz + qx * qy), 1 - 2 * (qy * qy + qz * qz))


def per_frame_loc_error(tag, rec_dir):
    """Return dict frame->(loc_err_xy, yaw_err_rad) after sim3 alignment of VINS to GT ego."""
    vio = VINSROOT / tag / "vio.csv"
    if not vio.exists():
        return {}
    V = [r for r in csv.reader(open(vio)) if len(r) >= 8 and r[0][0].isdigit()]
    if len(V) < 10:
        return {}
    vts = np.array([float(r[0]) for r in V])
    vxy = np.array([[float(r[1]), float(r[2])] for r in V])
    vyaw = np.array([quat_yaw(float(r[4]), float(r[5]), float(r[6]), float(r[7])) for r in V])
    # GT ego per frame
    gt = {}
    for f in glob.glob(f"{rec_dir}/gt/*.json"):
        fi = int(Path(f).stem); g = json.load(open(f))
        gt[fi] = (g["ts_ns"] / 1e9, g["ego_pose"]["x"], g["ego_pose"]["y"], math.radians(g["ego_pose"]["yaw"]))
    frames = sorted(gt)
    gts = np.array([gt[fi][0] for fi in frames])
    gxy = np.array([[gt[fi][1], gt[fi][2]] for fi in frames])
    gyaw = np.array([gt[fi][3] for fi in frames])
    # nearest VINS sample per GT frame
    idx = np.searchsorted(vts, gts)
    idx = np.clip(idx, 0, len(vts) - 1)
    vxy_f = vxy[idx]; vyaw_f = vyaw[idx]; dt = np.abs(vts[idx] - gts)
    valid = dt < 0.1
    if valid.sum() < 10:
        return {}
    aligned, s = umeyama_sim3_2d(vxy_f[valid], gxy[valid])
    out = {}
    al = np.full((len(frames), 2), np.nan); al[valid] = aligned
    for k, fi in enumerate(frames):
        if not valid[k]:
            continue
        loc = float(np.linalg.norm(al[k] - gxy[k]))
        dyaw = abs(((vyaw_f[k] - gyaw[k]) + math.pi) % (2 * math.pi) - math.pi)
        out[fi] = (loc, dyaw)
    return out


def metrics_block(y, mu, sigma, hi):
    from sklearn.metrics import roc_auc_score
    from scipy.stats import norm
    sigma = np.maximum(sigma, 1e-6); r = {"n": int(len(y))}
    r["rmse"] = float(np.sqrt(np.mean((y - mu) ** 2))); r["med_abs"] = float(np.median(np.abs(y - mu)))
    r["nll"] = float(np.mean(0.5 * (np.log(2 * np.pi * sigma ** 2) + (y - mu) ** 2 / sigma ** 2)))
    r["anees"] = float(np.mean((y - mu) ** 2 / sigma ** 2))
    z = np.abs((y - mu) / sigma)
    r["ece"] = float(np.mean([abs(np.mean(z <= abs(norm.ppf(0.5 + p / 2))) - p) for p in (0.5, 0.68, 0.8, 0.9, 0.95)]))
    try:
        r["auroc"] = float(roc_auc_score(hi, sigma)) if len(np.unique(hi)) > 1 else float("nan")
    except Exception:
        r["auroc"] = float("nan")
    order = np.argsort(sigma); err = np.abs(y - mu)[order]; n80 = max(1, int(0.8 * len(err)))
    r["riskcov80"] = float(np.mean(err[:n80])); med_s = np.median(sigma)
    r["overconf"] = float(np.mean(sigma[hi == 1] < med_s)) if (hi == 1).any() else float("nan")
    return r


def train_predict(Xtr, ytr, Xva, yva, Xall, epochs=200):
    import torch, torch.nn as nn
    dev = "cuda" if torch.cuda.is_available() else "cpu"; torch.manual_seed(0)
    Xt, yt = torch.tensor(Xtr, device=dev), torch.tensor(ytr, device=dev)
    Xv, yv = torch.tensor(Xva, device=dev), torch.tensor(yva, device=dev)

    class N(nn.Module):
        def __init__(s, d):
            super().__init__(); s.b = nn.Sequential(nn.Linear(d, 128), nn.ReLU(), nn.Linear(128, 64), nn.ReLU())
            s.mu = nn.Linear(64, 1); s.lv = nn.Linear(64, 1)
        def forward(s, x):
            h = s.b(x); return s.mu(h).squeeze(-1), torch.clamp(s.lv(h).squeeze(-1), -6, 6)
    net = N(Xtr.shape[1]).to(dev); opt = torch.optim.Adam(net.parameters(), 1e-3, weight_decay=1e-4)
    best = (1e9, None)
    for ep in range(epochs):
        net.train(); opt.zero_grad(); mu, lv = net(Xt)
        loss = (0.5 * (lv + (yt - mu) ** 2 / torch.exp(lv))).mean(); loss.backward(); opt.step()
        if ep % 10 == 0:
            net.eval()
            with torch.no_grad():
                mv, lvv = net(Xv); vn = (0.5 * (lvv + (yv - mv) ** 2 / torch.exp(lvv))).mean().item()
            if vn < best[0]: best = (vn, {k: v.detach().cpu().clone() for k, v in net.state_dict().items()})
    if best[1]: net.load_state_dict(best[1])
    net.eval()
    with torch.no_grad():
        mu, lv = net(torch.tensor(Xall, device=dev))
    mu = mu.cpu().numpy(); sdl = np.sqrt(np.exp(lv.cpu().numpy()))
    ml = np.expm1(mu); return ml, np.maximum((1 + np.maximum(ml, 0)) * sdl, 1e-3)


def main():
    df = pd.read_csv(WS / "paper2_raw_object_benchmark_all_with_vins.csv", low_memory=False)
    df = df[(df["matched"] == 1) & (df["vins_match_ok"] == 1)].copy()
    for c in OBJ_NUM + VINS_NUM + ["pos_err_m", "gt_range_m", "frame"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df[df["pos_err_m"].notna() & df["vins_feat_count"].notna()].copy()

    # per-recording localization error (sim3-aligned), join by frame
    loc_xy = np.full(len(df), np.nan); yaw_e = np.full(len(df), np.nan)
    for (town, run), idx in df.groupby(["town", "run"]).groups.items():
        tag = f"rep_{run}_{town}"; rec = DATAROOT / f"{town}__dynamic_v3__run{run}"
        fe = per_frame_loc_error(tag, rec)
        sub = df.loc[idx]
        for ridx, row in sub.iterrows():
            v = fe.get(int(row["frame"]))
            if v:
                loc_xy[df.index.get_loc(ridx)] = v[0]; yaw_e[df.index.get_loc(ridx)] = v[1]
    df["loc_err_xy"] = loc_xy; df["yaw_err_rad"] = yaw_e
    df = df[df["loc_err_xy"].notna()].copy()
    # propagate: object world error = sensor + ego translation drift + ego yaw drift * range
    df["world_err"] = df["pos_err_m"] + df["loc_err_xy"] + df["yaw_err_rad"].abs() * df["gt_range_m"]
    print(f"[a2w] rows with loc error: {len(df)} ; world_err median {df['world_err'].median():.2f} "
          f"(sensor-only median {df['pos_err_m'].median():.2f}); loc_err_xy median {df['loc_err_xy'].median():.2f}")

    df["high_world"] = (df["world_err"] > df["world_err"].median()).astype(int)
    df["degraded"] = ((df["vins_outlier_ratio"] > 0.5) | (df["vins_feat_count"] < 50)).astype(int)
    rng = np.random.RandomState(7); runs = df["town"].astype(str) + "@" + df["run"].astype(str)
    uq = sorted(runs.unique()); rng.shuffle(uq); nt = max(1, len(uq) // 5)
    test_g = set(uq[:nt]); val_g = set(uq[nt:2 * nt])
    df["split"] = np.where(runs.isin(test_g), "test", np.where(runs.isin(val_g), "val", "train"))
    tr = (df.split == "train").values; va = (df.split == "val").values; te = (df.split == "test").values

    cls_oh = pd.get_dummies(df["cls"].astype(str), prefix="cls")
    Xobj = pd.concat([df[OBJ_NUM].fillna(df[OBJ_NUM].median()), cls_oh], axis=1).astype("float32")
    Xv = df[VINS_NUM].fillna(df[VINS_NUM].median()).astype("float32")
    y = df["world_err"].values.astype("float32"); ylog = np.log1p(y)
    hi = df["high_world"].values.astype(int)
    stdz = lambda X: ((X - X[tr].mean()) / X[tr].std().replace(0, 1)).values.astype("float32")
    Xo = stdz(Xobj); Xw = np.concatenate([Xo, stdz(Xv)], axis=1)

    mu_no, sd_no = train_predict(Xo[tr], ylog[tr], Xo[va], ylog[va], Xo)
    mu_wi, sd_wi = train_predict(Xw[tr], ylog[tr], Xw[va], ylog[va], Xw)

    def strat(mask):
        m = mask & te; out = {}
        if m.sum() >= 8:
            out["no_vins"] = metrics_block(y[m], mu_no[m], sd_no[m], hi[m])
            out["with_vins"] = metrics_block(y[m], mu_wi[m], sd_wi[m], hi[m])
        return out
    allm = strat(np.ones(len(df), bool)); deg = strat(df.degraded.values.astype(bool))
    perbin = {b: strat((df["dist_bin"] == b).values) for b in BINS}

    def better(st, k, lower=True):
        if "with_vins" not in st: return None
        a, b = st["with_vins"][k], st["no_vins"][k]
        return (a < b) if lower else (a > b)
    dN, dA, dR = better(deg, "nll"), better(deg, "auroc", False), better(deg, "riskcov80")
    aN, aA = better(allm, "nll"), better(allm, "auroc", False)
    deg_win = sum(1 for x in (dN, dA, dR) if x) >= 2; all_win = sum(1 for x in (aN, aA) if x) >= 1
    verdict = "promising" if deg_win else ("weak" if all_win else "failed/inconclusive")

    rows = []
    for sn, st in [("all", allm), ("degraded", deg)]:
        for mdl, m in st.items(): rows.append(dict(stratum=sn, model=mdl, **m))
    pd.DataFrame(rows).to_csv(WS / "paper2_a2_worldframe_metrics.csv", index=False)

    def tbl(st, title):
        L = [f"### {title}", "| model | n | NLL | ANEES | ECE | AUROC | riskcov@80 | overconf |", "|---|---|---|---|---|---|---|---|"]
        for mdl in ["no_vins", "with_vins"]:
            if mdl in st:
                m = st[mdl]; L.append(f"| {mdl} | {m['n']} | {m['nll']:.3f} | {m['anees']:.2f} | {m['ece']:.3f} | {m['auroc']:.3f} | {m['riskcov80']:.2f} | {m['overconf']:.3f} |")
        return L
    A = ["", "", "---", "", "# A2 TEST 2 — VINS-error-PROPAGATED object WORLD error (deployment mechanism)", "",
         f"> object_world_err = sensor body_pos_err + ego loc drift (sim3-aligned) + |yaw drift|*range. n={len(df)} "
         f"(train {tr.sum()}/test {te.sum()}). This is the mechanism test 1 could not see (test 1 used GT ego-comp).", "",
         f"## A2 (world-frame) VERDICT: **{verdict.upper()}**",
         f"- degraded: with-VINS vs no-VINS NLL_better={dN} AUROC_better={dA} riskcov_better={dR}",
         f"- overall: NLL_better={aN} AUROC_better={aA}",
         f"- world_err median {df['world_err'].median():.2f} m vs sensor-only {df['pos_err_m'].median():.2f} m "
         f"(localization adds {df['world_err'].median()-df['pos_err_m'].median():.2f} m median).", ""]
    A += tbl(allm, "Overall (test)") + [""] + tbl(deg, "Degraded-localization stratum")
    A += ["", "## Per distance bin (NLL no-VINS -> with-VINS)"]
    for b in BINS:
        st = perbin[b]
        if "with_vins" in st:
            A.append(f"- {b}: {st['no_vins']['nll']:.3f} -> {st['with_vins']['nll']:.3f} ; AUROC {st['no_vins']['auroc']:.3f} -> {st['with_vins']['auroc']:.3f}")
    A += ["", "## Honest caveats (test 2)",
          "- world_err uses an ANALYTICAL additive propagation model (sensor + loc drift + yaw*range), not a re-localized object pipeline.",
          "- VINS scale drift here is partly artifact of aggressive-turn 640 recordings; real VINS would drift less.",
          "- if with-VINS wins, it confirms VINS quality conditions the LOCALIZATION-propagated object error (the deployment claim);",
          "  it does NOT revive test-1 (sensor-only error), which VINS quality cannot help."]
    with open(WS / "PAPER2_A2_VINS_CONDITIONING_RESULTS.md", "a") as f:
        f.write("\n".join(A) + "\n")
    cur = (WS / "PAPER2_VINS_REPLAY_A2_STATUS.md").read_text() if (WS / "PAPER2_VINS_REPLAY_A2_STATUS.md").exists() else ""
    (WS / "PAPER2_VINS_REPLAY_A2_STATUS.md").write_text(
        cur + f"\n## A2 test 2 (world-frame, propagated): verdict **{verdict}** "
        f"(world_err med {df['world_err'].median():.2f}m, loc adds {df['world_err'].median()-df['pos_err_m'].median():.2f}m)\n")
    print(f"[a2w] WORLD-FRAME VERDICT={verdict}")


if __name__ == "__main__":
    main()
