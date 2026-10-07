#!/usr/bin/env python3
"""Paper-2 Track A — DEEP sequence encoders (GRU / TCN / Transformer) vs TCSV-M / pooled / cv.

Run with the conda env that has torch (`gf`):
    conda run -n gf python scripts/paper2_sequence_deep_models.py

Closes question #3: does a learned sequence encoder over the raw T-frame object state beat the
incumbent TCSV-M (hand-crafted summaries) and the best no-torch temporal-pooling model?
Red lines unchanged: NO GT feature, NO frame-random split, no backend/object-factor/frontier/HD-map.
Primary metric AURC (lower=better); bootstrap ΔAURC over groups.

Out (paper2/track_a/): paper2_sequence_deep_metrics.csv, paper2_sequence_deep_bootstrap.csv
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np, pandas as pd

WS = Path("/home/ivlab3/fwvio_estimator_ws_wheel")
sys.path.insert(0, str(WS / "scripts"))
import paper2_tcsv_features as F
F.WS = WS / "paper2"
from paper2_tcsv_train_eval import aurc, op_metrics, youden, split_by_key
from paper2_sequence_validity_experiment import (build_windows, pool_stats, impute, fit_hgbm,
                                                 PERFRAME, TCSV_FEATS, MONO, T)
from sklearn.ensemble import HistGradientBoostingClassifier
import torch
import torch.nn as nn

torch.manual_seed(7); np.random.seed(7)
DEV = "cuda" if torch.cuda.is_available() else "cpu"
OUT = WS / "paper2" / "track_a"
OUT.mkdir(parents=True, exist_ok=True)


# ----------------------------- deep models -----------------------------
class GRUNet(nn.Module):
    def __init__(self, fdim, hid=64, layers=1):
        super().__init__()
        self.gru = nn.GRU(fdim, hid, layers, batch_first=True, dropout=0.0)
        self.head = nn.Sequential(nn.Linear(hid, 32), nn.ReLU(), nn.Dropout(0.2), nn.Linear(32, 1))
    def forward(self, x):
        o, h = self.gru(x); return self.head(h[-1]).squeeze(-1)


class TCNNet(nn.Module):
    def __init__(self, fdim, ch=64, k=3):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv1d(fdim, ch, k, padding=k // 2), nn.ReLU(), nn.BatchNorm1d(ch),
            nn.Conv1d(ch, ch, k, padding=k // 2, dilation=1), nn.ReLU(), nn.BatchNorm1d(ch),
            nn.AdaptiveAvgPool1d(1))
        self.head = nn.Sequential(nn.Linear(ch, 32), nn.ReLU(), nn.Dropout(0.2), nn.Linear(32, 1))
    def forward(self, x):              # x [B,T,F] -> [B,F,T]
        z = self.net(x.transpose(1, 2)).squeeze(-1); return self.head(z).squeeze(-1)


class TransNet(nn.Module):
    def __init__(self, fdim, dmodel=64, heads=4, layers=1):
        super().__init__()
        self.proj = nn.Linear(fdim, dmodel)
        self.pos = nn.Parameter(torch.randn(1, T, dmodel) * 0.02)
        enc = nn.TransformerEncoderLayer(dmodel, heads, dmodel * 2, dropout=0.1, batch_first=True)
        self.enc = nn.TransformerEncoder(enc, layers)
        self.head = nn.Sequential(nn.Linear(dmodel, 32), nn.ReLU(), nn.Dropout(0.2), nn.Linear(32, 1))
    def forward(self, x):
        z = self.proj(x) + self.pos
        z = self.enc(z).mean(1); return self.head(z).squeeze(-1)


def train_eval_deep(make_model, Xtr, ytr, Xte, gtr, epochs=60, bs=256, lr=1e-3, wd=1e-4):
    """Group-held validation for early stopping (no frame-random). Returns test scores."""
    # standardize on train
    mu = Xtr.reshape(-1, Xtr.shape[-1]).mean(0); sd = Xtr.reshape(-1, Xtr.shape[-1]).std(0) + 1e-6
    Xtr = (Xtr - mu) / sd; Xte = (Xte - mu) / sd
    # group-held val (25% of train groups)
    ug = np.unique(gtr); rs = np.random.RandomState(7); rs.shuffle(ug)
    vk = set(ug[:max(1, len(ug) // 4)])
    vm = np.array([g in vk for g in gtr])
    Xt, yt = Xtr[~vm], ytr[~vm]; Xv, yv = Xtr[vm], ytr[vm]
    pos_w = float((yt == 0).sum() / max((yt == 1).sum(), 1))
    model = make_model().to(DEV)
    opt = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=wd)
    lossf = nn.BCEWithLogitsLoss(pos_weight=torch.tensor(pos_w, device=DEV))
    Xt_t = torch.tensor(Xt, dtype=torch.float32, device=DEV); yt_t = torch.tensor(yt, dtype=torch.float32, device=DEV)
    Xv_t = torch.tensor(Xv, dtype=torch.float32, device=DEV); yv_t = torch.tensor(yv, dtype=torch.float32, device=DEV)
    Xe_t = torch.tensor(Xte, dtype=torch.float32, device=DEV)
    n = len(Xt_t); best_auc = -1; best_state = None; patience = 12; bad = 0
    from sklearn.metrics import roc_auc_score
    for ep in range(epochs):
        model.train(); perm = torch.randperm(n, device=DEV)
        for i in range(0, n, bs):
            idx = perm[i:i + bs]; opt.zero_grad()
            out = model(Xt_t[idx]); loss = lossf(out, yt_t[idx]); loss.backward(); opt.step()
        model.eval()
        with torch.no_grad():
            pv = torch.sigmoid(model(Xv_t)).cpu().numpy()
        auc = roc_auc_score(yv, pv) if len(np.unique(yv)) > 1 else 0.5
        if auc > best_auc + 1e-4:
            best_auc = auc; best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}; bad = 0
        else:
            bad += 1
            if bad >= patience: break
    if best_state: model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        return torch.sigmoid(model(Xe_t)).cpu().numpy()


def boot(y, sA, sB, gk, n=300, seed=11):
    rs = np.random.RandomState(seed); g = np.asarray(gk); uq = np.unique(g); d = []
    for _ in range(n):
        s = rs.choice(uq, len(uq), True); m = np.concatenate([np.where(g == x)[0] for x in s])
        d.append(aurc(y[m], sA[m]) - aurc(y[m], sB[m]))
    d = np.array(d); return float(d.mean()), float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))


def run():
    car = F.load_carla(W=5); kit = F.load_kitti(W=5)
    car, SEQ_c = build_windows(car, ("town", "run", "track_id"))
    kit, SEQ_k = build_windows(kit, ("seq", "track_id"))
    print(f"[deep] DEV={DEV} CARLA n={len(car)} KITTI n={len(kit)} T={T} F={SEQ_c.shape[2]}")
    DATA = {"carla": (car, SEQ_c, ("town", "run", "track_id")),
            "kitti": (kit, SEQ_k, ("seq", "track_id"))}
    rows, brows = [], []

    def gkey(df, grp): return df[list(grp)].astype(str).agg("@".join, axis=1).to_numpy()

    def evals(name, tr_df, tr_S, te_df, te_S, tr_grp, te_grp_for_boot):
        ytr = tr_df["velocity_valid"].to_numpy(int); yte = te_df["velocity_valid"].to_numpy(int)
        # impute raw seq (fit medians on train, per feature across all frames)
        flat = tr_S.reshape(-1, tr_S.shape[-1])
        med = np.nanmedian(flat, axis=0); med = np.where(np.isfinite(med), med, 0.0)
        Str = np.where(np.isfinite(tr_S), tr_S, med); Ste = np.where(np.isfinite(te_S), te_S, med)
        gtr = gkey(tr_df, tr_grp)
        fdim = Str.shape[-1]
        scores = {}
        # references (no-torch): TCSV-M and best no-torch pooled and cv
        s_tr = impute(tr_df[TCSV_FEATS].astype(float).to_numpy(), tr_df[TCSV_FEATS].astype(float).to_numpy())
        s_te = impute(tr_df[TCSV_FEATS].astype(float).to_numpy(), te_df[TCSV_FEATS].astype(float).to_numpy())
        scores["TCSV-M"] = fit_hgbm(s_tr, ytr, s_te, mono=MONO)
        p_tr = pool_stats(Str); p_te = pool_stats(Ste)
        scores["seq_pool_hgbm"] = fit_hgbm(p_tr, ytr, p_te)
        scores["cv_smoothing_gate"] = np.nan_to_num(-pd.to_numeric(te_df["cv_residual"], errors="coerce").to_numpy(float),
                                                    nan=-1e9)
        # deep
        scores["GRU"] = train_eval_deep(lambda: GRUNet(fdim), Str, ytr, Ste, gtr)
        scores["TCN"] = train_eval_deep(lambda: TCNNet(fdim), Str, ytr, Ste, gtr)
        scores["Transformer"] = train_eval_deep(lambda: TransNet(fdim), Str, ytr, Ste, gtr)
        for mn, sc in scores.items():
            m = op_metrics(yte, sc, youden(sc, yte))
            rows.append(dict(split=name, model=mn, n=len(yte), base_valid=round(float(yte.mean()), 3),
                             **{k: round(v, 4) for k, v in m.items()}))
        if te_grp_for_boot is not None:
            gk = gkey(te_df, te_grp_for_boot)
            for cand in ["GRU", "TCN", "Transformer"]:
                for ref in ["TCSV-M", "seq_pool_hgbm", "cv_smoothing_gate"]:
                    md, lo, hi = boot(yte, scores[cand], scores[ref], gk)
                    brows.append(dict(split=name, cand=cand, vs=ref, dAURC=round(md, 4),
                                      ci_lo=round(lo, 4), ci_hi=round(hi, 4),
                                      verdict=("cand_better" if hi < 0 else "cand_worse" if lo > 0 else "tie")))
        print(f"  [{name}] " + " ".join(f"{k}={op_metrics(yte,v,youden(v,yte))['aurc']:.3f}" for k, v in scores.items()))

    for ds in ["carla", "kitti"]:
        df, S, grp = DATA[ds]; te = split_by_key(df, seed=7, frac=0.25)
        evals(f"{ds}->{ds}", df[~te], S[~te], df[te], S[te], grp, grp)
    evals("carla->kitti", *DATA["carla"][:2], DATA["kitti"][0], DATA["kitti"][1], DATA["carla"][2], None)
    evals("kitti->carla", *DATA["kitti"][:2], DATA["carla"][0], DATA["carla"][1], DATA["kitti"][2], None)
    kdf, kS, kgrp = DATA["kitti"]; cdf, cS, cgrp = DATA["carla"]; kte = split_by_key(kdf, 7, 0.25)
    tr_df = pd.concat([cdf, kdf[~kte]], ignore_index=True); tr_S = np.concatenate([cS, kS[~kte]], 0)
    evals("C+Ktr->Khold", tr_df, tr_S, kdf[kte], kS[kte], ("town", "run", "track_id"), kgrp)

    R = pd.DataFrame(rows); B = pd.DataFrame(brows)
    R.to_csv(OUT / "paper2_sequence_deep_metrics.csv", index=False)
    B.to_csv(OUT / "paper2_sequence_deep_bootstrap.csv", index=False)
    pd.set_option("display.width", 220, "display.max_columns", 40)
    print("\n=== AURC (lower=better) ===")
    print(R.pivot(index="split", columns="model", values="aurc").round(4))
    print("\n=== Bootstrap ΔAURC (cand-ref); neg=>cand better ===")
    print(B.to_string(index=False))


if __name__ == "__main__":
    run()
