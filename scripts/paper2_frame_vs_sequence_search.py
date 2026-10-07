#!/usr/bin/env python3
"""Paper-2 Part 1 — PER-FRAME vs SEQUENCE model search (large bake-off, honest).

Pick ONE strongest per-frame model and ONE strongest sequence model for object-state VALIDITY
(selective refusal), and decide whether sequence beats per-frame.

RED LINES (enforced in code):
  * NO GT feature. GT only builds labels / evaluation.
  * NO frame-random split. Split by group key (CARLA town@run, KITTI kitti@seq); a track lives in
    exactly one group => no track in both train & test.
  * Sequence windows are PAST-ONLY: window for a labeled row at track-position p = frames
    [p-T+1 .. p], edge-padded with the EARLIEST available frame. No future leak. No centered window.
  * NO backend touched here (Part 1 = validity model only). Bad results reported as-is.

Alignment guarantee: per split we sort ONCE by (group, frame); per-frame matrix, TCSV-14 summary,
and the [T,F] window tensor are all built from that same sorted frame, so every score array is
row-aligned by construction (paired bootstrap is valid).

Labels: velocity_valid (primary), position_valid, full_state_valid (multi-label feasibility).

Metrics: AUROC(up), AURC(down, primary), OC@ret0.8(down), OC@ret0.9(down), retention,
  false_refusal, F1_invalid, n, base_valid, train/test group counts, fit_ms.

Splits: CARLA->CARLA, KITTI->KITTI, CARLA->KITTI, KITTI->CARLA, C+Ktrain->Khold, K+Ctrain->Chold.

Outputs (paper2/track_a/):
  paper2_frame_vs_sequence_metrics.csv, _seqsweep.csv, _bootstrap.csv, _multilabel.csv, _meta.json
  PAPER2_FRAME_VS_SEQUENCE_RESULTS.md, PAPER2_FRAME_VS_SEQUENCE_DECISION.md (DECISION written separately)
"""
from __future__ import annotations
import sys, time, json
from pathlib import Path
import numpy as np, pandas as pd

WS = Path("/home/ivlab3/fwvio_estimator_ws_wheel")
sys.path.insert(0, str(WS / "scripts"))
import paper2_tcsv_features as F
F.WS = WS / "paper2"
from paper2_tcsv_train_eval import aurc, op_metrics, youden, split_by_key
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

OUT = WS / "paper2" / "track_a"; OUT.mkdir(parents=True, exist_ok=True)

PERFRAME = ["range_m", "depth_m", "bbox_area", "bearing_deg", "det_conf",
            "raw_speed", "cv_residual", "acceleration_score", "track_age"]
LOG_FEATS = {"range_m", "depth_m", "bbox_area"}
TCSV = F.TCSV_FEATS
MONO = [-1, 0, +1, -1, +1, +1, 0, -1, -1, -1, -1, +1, -1, -1]
GROUP = {"carla": ("town", "run", "track_id"), "kitti": ("seq", "track_id")}

try:
    import torch; import torch.nn as nn
    HAS_TORCH = torch.cuda.is_available(); DEV = "cuda" if HAS_TORCH else "cpu"
except Exception:
    HAS_TORCH = False; DEV = "cpu"


# ----------------------------- sorted frame + windows -----------------------------
def perframe_matrix(df):
    M = np.zeros((len(df), len(PERFRAME)), float)
    for j, c in enumerate(PERFRAME):
        v = pd.to_numeric(df[c], errors="coerce").to_numpy(float) if c in df else np.full(len(df), np.nan)
        if c in LOG_FEATS:
            v = np.log1p(np.clip(v, 0, None))
        M[:, j] = v
    return M


def sorted_windows(df, group, T):
    """Return (df_sorted, SEQ[N,T,F]) with SEQ row-aligned to df_sorted. PAST-ONLY edge-pad."""
    df = df.sort_values(list(group) + ["frame"]).reset_index(drop=True)
    M = perframe_matrix(df); nF = M.shape[1]
    gi = df.groupby(list(group), sort=False).indices
    SEQ = np.zeros((len(df), T, nF), float)
    for key, rows in gi.items():
        rows = list(rows)
        for pos, r in enumerate(rows):
            wr = [rows[max(0, k)] for k in range(pos - T + 1, pos + 1)]
            SEQ[r] = M[wr, :]
    return df, SEQ


def pool(SEQ, kind):
    if kind == "mean":   return SEQ.mean(1)
    if kind == "max":    return SEQ.max(1)
    if kind == "std":    return SEQ.std(1)
    if kind == "last":   return SEQ[:, -1, :]
    if kind == "quantile":
        return np.concatenate([np.percentile(SEQ, q, axis=1) for q in (25, 50, 75)], axis=1)
    if kind == "mean_std_last":
        return np.concatenate([SEQ.mean(1), SEQ.std(1), SEQ[:, -1, :]], axis=1)
    if kind == "full":
        return np.concatenate([SEQ.mean(1), SEQ.std(1), SEQ.min(1), SEQ.max(1),
                               SEQ[:, -1, :], SEQ[:, -1, :] - SEQ[:, 0, :]], axis=1)
    raise ValueError(kind)


def impute(train_X, X):
    med = np.nanmedian(train_X, axis=0); med = np.where(np.isfinite(med), med, 0.0)
    return np.where(np.isfinite(X), X, med)


# ----------------------------- learners -----------------------------
def hgbm(Xtr, ytr, Xte, mono=None, balanced=False):
    sw = None
    if balanced:
        p = ytr.mean(); sw = np.where(ytr == 1, 0.5 / max(p, 1e-6), 0.5 / max(1 - p, 1e-6))
    m = HistGradientBoostingClassifier(max_iter=300, max_depth=4, learning_rate=0.05,
                                       l2_regularization=1.0, random_state=7, monotonic_cst=mono)
    m.fit(Xtr, ytr, sample_weight=sw)
    return m.predict_proba(Xte)[:, 1]


def mlp(Xtr, ytr, Xte, hidden=(128, 64)):
    m = make_pipeline(StandardScaler(),
                      MLPClassifier(hidden, max_iter=500, early_stopping=True, alpha=1e-3,
                                    random_state=7)).fit(Xtr, ytr)
    return m.predict_proba(Xte)[:, 1]


def logit(Xtr, ytr, Xte, balanced=False):
    m = make_pipeline(StandardScaler(),
                      LogisticRegression(max_iter=800, class_weight=("balanced" if balanced else None))
                      ).fit(Xtr, ytr)
    return m.predict_proba(Xte)[:, 1]


def torch_train(model, Xtr, ytr, Xte, epochs=80, lr=1e-3, seed=7):
    torch.manual_seed(seed); np.random.seed(seed)
    Xtr_t = torch.tensor(Xtr, dtype=torch.float32, device=DEV)
    ytr_t = torch.tensor(ytr, dtype=torch.float32, device=DEV)
    Xte_t = torch.tensor(Xte, dtype=torch.float32, device=DEV)
    n = len(Xtr); nv = max(1, int(0.2 * n)); idx = np.random.permutation(n); vi, ti = idx[:nv], idx[nv:]
    pos = max(ytr.mean(), 1e-6); pw = torch.tensor([(1 - pos) / pos], dtype=torch.float32, device=DEV)
    opt = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
    lossf = nn.BCEWithLogitsLoss(pos_weight=pw)
    best = (1e9, None); bad = 0
    for ep in range(epochs):
        model.train(); opt.zero_grad()
        loss = lossf(model(Xtr_t[ti]).squeeze(-1), ytr_t[ti]); loss.backward(); opt.step()
        model.eval()
        with torch.no_grad():
            vl = lossf(model(Xtr_t[vi]).squeeze(-1), ytr_t[vi]).item()
        if vl < best[0] - 1e-4:
            best = (vl, {k: v.detach().clone() for k, v in model.state_dict().items()}); bad = 0
        else:
            bad += 1
            if bad >= 12: break
    if best[1]: model.load_state_dict(best[1])
    model.eval()
    with torch.no_grad():
        return torch.sigmoid(model(Xte_t).squeeze(-1)).cpu().numpy()


def make_gru(Fd):
    class G(nn.Module):
        def __init__(s):
            super().__init__(); s.g = nn.GRU(Fd, 64, batch_first=True)
            s.h = nn.Sequential(nn.Linear(64, 32), nn.ReLU(), nn.Dropout(0.3), nn.Linear(32, 1))
        def forward(s, x): o, _ = s.g(x); return s.h(o[:, -1, :])
    return G().to(DEV)


def make_tcn(Fd):
    class Tn(nn.Module):
        def __init__(s):
            super().__init__()
            s.c = nn.Sequential(nn.Conv1d(Fd, 64, 3, padding=1), nn.BatchNorm1d(64), nn.ReLU(),
                                nn.Conv1d(64, 64, 3, padding=1), nn.BatchNorm1d(64), nn.ReLU(),
                                nn.AdaptiveAvgPool1d(1))
            s.h = nn.Sequential(nn.Linear(64, 32), nn.ReLU(), nn.Dropout(0.3), nn.Linear(32, 1))
        def forward(s, x): return s.h(s.c(x.transpose(1, 2)).squeeze(-1))
    return Tn().to(DEV)


def make_trans(Fd, T):
    class Tr(nn.Module):
        def __init__(s):
            super().__init__(); s.proj = nn.Linear(Fd, 64); s.pos = nn.Parameter(torch.zeros(1, T, 64))
            s.enc = nn.TransformerEncoder(nn.TransformerEncoderLayer(64, 4, 128, dropout=0.2, batch_first=True), 1)
            s.h = nn.Sequential(nn.Linear(64, 32), nn.ReLU(), nn.Dropout(0.3), nn.Linear(32, 1))
        def forward(s, x): return s.h(s.enc(s.proj(x) + s.pos).mean(1))
    return Tr().to(DEV)


# ----------------------------- metrics -----------------------------
def mrow(split, model, family, label, yte, sc, fit_ms, ntr_g, nte_g):
    m = op_metrics(yte, sc, youden(sc, yte))
    return dict(split=split, model=model, family=family, label=label, n=len(yte),
                base_valid=round(float(yte.mean()), 4), fit_ms=round(fit_ms, 1),
                ntr_groups=ntr_g, nte_groups=nte_g,
                **{k: (round(v, 4) if v == v else v) for k, v in m.items()})


def boot_aurc_diff(y, sA, sB, gk, n=300, seed=11):
    rs = np.random.RandomState(seed); g = np.asarray(gk); uniq = np.unique(g); diffs = []
    for _ in range(n):
        samp = rs.choice(uniq, size=len(uniq), replace=True)
        mask = np.concatenate([np.where(g == s)[0] for s in samp])
        diffs.append(aurc(y[mask], sA[mask]) - aurc(y[mask], sB[mask]))
    d = np.array(diffs)
    return float(d.mean()), float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))


# ----------------------------- per-split feature bundle -----------------------------
class Bundle:
    """Holds row-aligned per-frame + window features + labels + group keys for one df at window T."""
    def __init__(self, df, group, T, ds_name):
        self.df, self.SEQ = sorted_windows(df, group, T)
        self.group = group; self.ds = ds_name; self.T = T
        self.pf = F.prep(self.df, TCSV)            # 14 summary feats (aligned)
        self.gk = self.df["split_key"].to_numpy()
        self.range = pd.to_numeric(self.df["range_m"], errors="coerce").to_numpy(float)
        self.cv = pd.to_numeric(self.df["cv_residual"], errors="coerce").to_numpy(float)
        self.depth = pd.to_numeric(self.df["depth_m"], errors="coerce").to_numpy(float)
        self.bbox = pd.to_numeric(self.df["bbox_area"], errors="coerce").to_numpy(float)
        self.conf = pd.to_numeric(self.df["det_conf"], errors="coerce").to_numpy(float)
    def y(self, label): return self.df[label].to_numpy(int)


def main():
    t0 = time.time()
    rows, sweep_rows, boot_rows, multi_rows = [], [], [], []
    car = F.load_carla(W=5); kit = F.load_kitti(W=5)
    DAT = {"carla": car, "kitti": kit}
    print(f"[load] CARLA n={len(car)} towns={sorted(car.town.unique())} runs={car.split_key.nunique()} "
          f"vv={car.velocity_valid.mean():.3f} pv={car.position_valid.mean():.3f}")
    print(f"[load] KITTI n={len(kit)} seqs={kit.split_key.nunique()} "
          f"vv={kit.velocity_valid.mean():.3f} pv={kit.position_valid.mean():.3f}")

    # ===== B. SEQUENCE T x POOLING sweep (in-domain) to choose deployable (T, pool) =====
    POOLS = ["mean", "max", "std", "last", "quantile", "mean_std_last", "full"]
    TS = [3, 5, 7, 10, 15]
    bund = {}  # (ds,T)->Bundle
    def B(ds, T):
        if (ds, T) not in bund: bund[(ds, T)] = Bundle(DAT[ds], GROUP[ds], T, ds)
        return bund[(ds, T)]
    te_mask = {}  # (ds,T)->mask aligned to that bundle's df
    def TE(ds, T):
        if (ds, T) not in te_mask: te_mask[(ds, T)] = split_by_key(B(ds, T).df, seed=7, frac=0.25)
        return te_mask[(ds, T)]

    for ds in ["carla", "kitti"]:
        for T in TS:
            b = B(ds, T); tem = TE(ds, T)
            ytr, yte = b.y("velocity_valid")[~tem], b.y("velocity_valid")[tem]
            for pk in POOLS:
                Ptr, Pte = pool(b.SEQ[~tem], pk), pool(b.SEQ[tem], pk)
                Ptr, Pte = impute(Ptr, Ptr), impute(Ptr, Pte)
                t = time.time(); sc = hgbm(Ptr, ytr, Pte); ms = (time.time() - t) * 1e3
                au = op_metrics(yte, sc, youden(sc, yte))
                sweep_rows.append(dict(dataset=ds, T=T, pool=pk, aurc=round(aurc(yte, sc), 4),
                                       auroc=round(au["auroc"], 4), oc_ret90=round(au["overconf_at_ret90"], 4),
                                       fit_ms=round(ms, 1)))
    sw = pd.DataFrame(sweep_rows)
    rc = sw[sw.dataset == "carla"].set_index(["T", "pool"]).aurc.rank()
    rk = sw[sw.dataset == "kitti"].set_index(["T", "pool"]).aurc.rank()
    comb = (rc + rk).sort_values()
    SEQ_T, SEQ_POOL = int(comb.index[0][0]), comb.index[0][1]
    print(f"[seq] chosen deployable seq config: T={SEQ_T} pool={SEQ_POOL}")

    # ===== A+C. PER-FRAME + SEQUENCE on ALL SPLITS (aligned within split) =====
    def perframe_scores(btr, bte, label):
        ytr = btr.y(label)
        S, FT = {}, {}
        def timed(n, fn): t = time.time(); S[n] = fn(); FT[n] = (time.time() - t) * 1e3
        # gates (score: higher=more valid); nan->min
        def gate(name, arr):
            a = arr.copy(); a = np.nan_to_num(a, nan=(np.nanmin(a[np.isfinite(a)]) if np.isfinite(a).any() else 0.0))
            S[name] = a; FT[name] = 0.0
        gate("distance_gate", -bte.range); gate("cv_smoothing_gate", -bte.cv)
        gate("depth_gate", -bte.depth); gate("bbox_gate", bte.bbox); gate("conf_gate", bte.conf)
        geo = ["range_m", "bearing_deg", "depth_m"]
        timed("qiu_proxy(logit-geo)", lambda: logit(F.prep(btr.df, geo), ytr, F.prep(bte.df, geo)))
        timed("logistic", lambda: logit(btr.pf, ytr, bte.pf))
        timed("logistic_balanced", lambda: logit(btr.pf, ytr, bte.pf, balanced=True))
        timed("TCSV-HistGBM", lambda: hgbm(btr.pf, ytr, bte.pf))
        timed("TCSV-M(mono)", lambda: hgbm(btr.pf, ytr, bte.pf, mono=MONO))
        timed("TCSV-HistGBM-bal", lambda: hgbm(btr.pf, ytr, bte.pf, balanced=True))
        timed("MLP(128,64)", lambda: mlp(btr.pf, ytr, bte.pf))
        return S, FT

    def sequence_scores(btr, bte, label, deep=False):
        ytr = btr.y(label)
        Ptr = impute(pool(btr.SEQ, SEQ_POOL), pool(btr.SEQ, SEQ_POOL))
        Pte = impute(pool(btr.SEQ, SEQ_POOL), pool(bte.SEQ, SEQ_POOL))
        S, FT = {}, {}
        t = time.time(); S["seq_pool_hgbm"] = hgbm(Ptr, ytr, Pte); FT["seq_pool_hgbm"] = (time.time() - t) * 1e3
        t = time.time(); S["seq_pool_mlp"] = mlp(Ptr, ytr, Pte); FT["seq_pool_mlp"] = (time.time() - t) * 1e3
        if deep and HAS_TORCH:
            Fd = btr.SEQ.shape[2]
            trX = impute(btr.SEQ.reshape(len(btr.SEQ), -1), btr.SEQ.reshape(len(btr.SEQ), -1)).reshape(btr.SEQ.shape)
            teX = impute(btr.SEQ.reshape(len(btr.SEQ), -1), bte.SEQ.reshape(len(bte.SEQ), -1)).reshape(bte.SEQ.shape)
            for dn, mk in [("seq_GRU", lambda: make_gru(Fd)), ("seq_TCN", lambda: make_tcn(Fd)),
                           ("seq_Transformer", lambda: make_trans(Fd, btr.T))]:
                try:
                    t = time.time(); S[dn] = torch_train(mk(), trX, ytr, teX); FT[dn] = (time.time() - t) * 1e3
                except Exception as e:
                    print(f"[deep] {dn} FAILED: {e}")
        return S, FT

    # build the six splits using bundles at chosen T (so per-frame & seq aligned within each)
    cT, kT = B("carla", SEQ_T), B("kitti", SEQ_T)
    cte, kte = TE("carla", SEQ_T), TE("kitti", SEQ_T)
    # in-domain train/test sub-bundles share the same df; we slice arrays by mask.
    class Sub:  # lightweight view that mimics Bundle's attributes via a mask
        def __init__(s, b, mask):
            s.df = b.df[mask]; s.SEQ = b.SEQ[mask]; s.pf = b.pf[mask]; s.gk = b.gk[mask]; s.T = b.T
            s.range = b.range[mask]; s.cv = b.cv[mask]; s.depth = b.depth[mask]; s.bbox = b.bbox[mask]; s.conf = b.conf[mask]
        def y(s, label): return s.df[label].to_numpy(int)

    def concat_bundles(parts):
        class Cat:
            def __init__(c):
                c.df = pd.concat([p.df for p in parts], ignore_index=True)
                c.SEQ = np.concatenate([p.SEQ for p in parts], 0); c.pf = np.concatenate([p.pf for p in parts], 0)
                c.T = parts[0].T
            def y(c, label): return c.df[label].to_numpy(int)
        return Cat()

    splits = []
    splits.append(("CARLA->CARLA", Sub(cT, ~cte), Sub(cT, cte), True))
    splits.append(("KITTI->KITTI", Sub(kT, ~kte), Sub(kT, kte), True))
    splits.append(("CARLA->KITTI", cT, kT, False))
    splits.append(("KITTI->CARLA", kT, cT, False))
    splits.append(("C+Ktr->Khold", concat_bundles([cT, Sub(kT, ~kte)]), Sub(kT, kte), True))
    splits.append(("K+Ctr->Chold", concat_bundles([kT, Sub(cT, ~cte)]), Sub(cT, cte), True))

    store = {}
    for name, btr, bte, do_boot in splits:
        Spf, Fpf = perframe_scores(btr, bte, "velocity_valid")
        deep = name in ("CARLA->CARLA", "KITTI->KITTI", "C+Ktr->Khold", "K+Ctr->Chold")
        Sseq, Fseq = sequence_scores(btr, bte, "velocity_valid", deep=deep)
        yte = bte.y("velocity_valid")
        ntr_g = pd.Series(getattr(btr, "gk", btr.df["split_key"])).nunique() if hasattr(btr, "df") else 0
        nte_g = bte.df["split_key"].nunique()
        for nm, sc in Spf.items():
            rows.append(mrow(name, nm, "per_frame", "velocity_valid", yte, sc, Fpf[nm], ntr_g, nte_g))
        for nm, sc in Sseq.items():
            rows.append(mrow(name, nm, "sequence", "velocity_valid", yte, sc, Fseq[nm], ntr_g, nte_g))
        store[name] = dict(Spf=Spf, Sseq=Sseq, yte=yte, gk=bte.df["split_key"].to_numpy(), do_boot=do_boot)

    # ===== D. choose BEST per-frame & best sequence by mean in-domain AURC; paired bootstrap =====
    M = pd.DataFrame(rows)
    ind = M[M.split.isin(["CARLA->CARLA", "KITTI->KITTI"])]
    pf_rank = ind[ind.family == "per_frame"].groupby("model").aurc.mean().sort_values()
    seq_rank = ind[ind.family == "sequence"].groupby("model").aurc.mean().sort_values()
    BEST_PF, BEST_SEQ = pf_rank.index[0], seq_rank.index[0]
    print(f"[best] per_frame={BEST_PF} ({pf_rank.iloc[0]:.4f}) sequence={BEST_SEQ} ({seq_rank.iloc[0]:.4f})")

    for name in ["CARLA->CARLA", "KITTI->KITTI", "C+Ktr->Khold", "K+Ctr->Chold"]:
        st = store[name]; y, gk = st["yte"], st["gk"]
        sc_pf, sc_seq, sc_cv = st["Spf"][BEST_PF], st["Sseq"][BEST_SEQ], st["Spf"]["cv_smoothing_gate"]
        for cand, ref, lbl in [(sc_seq, sc_pf, f"{BEST_SEQ} vs {BEST_PF}"),
                               (sc_seq, sc_cv, f"{BEST_SEQ} vs cv_gate"),
                               (sc_pf, sc_cv, f"{BEST_PF} vs cv_gate")]:
            md, lo, hi = boot_aurc_diff(y, cand, ref, gk)
            boot_rows.append(dict(split=name, comparison=lbl, dAURC_mean=round(md, 4),
                                  ci_lo=round(lo, 4), ci_hi=round(hi, 4),
                                  verdict=("cand_better" if hi < 0 else "cand_worse" if lo > 0 else "tie")))

    # ===== E. multi-label feasibility (position_valid, full_state_valid) in-domain =====
    car["full_state_valid"] = ((car.position_valid == 1) & (car.velocity_valid == 1)).astype(int)
    kit["full_state_valid"] = ((kit.position_valid == 1) & (kit.velocity_valid == 1)).astype(int)
    for lbl in ["position_valid", "full_state_valid"]:
        for ds, b, tem in [("carla", cT, cte), ("kitti", kT, kte)]:
            # rebuild label col on the bundle df (full_state needs compute)
            df = b.df.copy()
            if lbl == "full_state_valid":
                df[lbl] = ((df.position_valid == 1) & (df.velocity_valid == 1)).astype(int)
            y = df[lbl].to_numpy(int)
            if len(np.unique(y)) < 2:
                multi_rows.append(dict(label=lbl, dataset=ds, model="(skip)", note="single-class")); continue
            ytr, yte = y[~tem], y[tem]
            sc_pf = hgbm(b.pf[~tem], ytr, b.pf[tem])  # per-frame TCSV-HistGBM
            Ptr = impute(pool(b.SEQ[~tem], SEQ_POOL), pool(b.SEQ[~tem], SEQ_POOL))
            Pte = impute(pool(b.SEQ[~tem], SEQ_POOL), pool(b.SEQ[tem], SEQ_POOL))
            sc_seq = hgbm(Ptr, ytr, Pte)
            for nm, sc in [("perframe_TCSV-HistGBM", sc_pf), (f"seq_pool_hgbm(T{SEQ_T},{SEQ_POOL})", sc_seq)]:
                m = op_metrics(yte, sc, youden(sc, yte))
                multi_rows.append(dict(label=lbl, dataset=ds, model=nm, n=len(yte), base=round(float(yte.mean()), 4),
                                       **{k: round(v, 4) for k, v in m.items() if v == v}))

    # ---- save ----
    M.to_csv(OUT / "paper2_frame_vs_sequence_metrics.csv", index=False)
    sw.to_csv(OUT / "paper2_frame_vs_sequence_seqsweep.csv", index=False)
    pd.DataFrame(boot_rows).to_csv(OUT / "paper2_frame_vs_sequence_bootstrap.csv", index=False)
    pd.DataFrame(multi_rows).to_csv(OUT / "paper2_frame_vs_sequence_multilabel.csv", index=False)
    meta = dict(BEST_PF=BEST_PF, BEST_SEQ=BEST_SEQ, SEQ_T=SEQ_T, SEQ_POOL=SEQ_POOL,
                pf_rank=pf_rank.round(4).to_dict(), seq_rank=seq_rank.round(4).to_dict(),
                seq_best_per_ds={ds: [int(comb.index[0][0]), comb.index[0][1]] for ds in ["carla", "kitti"]},
                has_torch=HAS_TORCH, n_carla=int(len(car)), n_kitti=int(len(kit)),
                runtime_s=round(time.time() - t0, 1))
    (OUT / "paper2_frame_vs_sequence_meta.json").write_text(json.dumps(meta, indent=2))
    print("[done]", json.dumps(meta, indent=2))
    return M, pd.DataFrame(boot_rows), pd.DataFrame(multi_rows), meta, sw


if __name__ == "__main__":
    main()
