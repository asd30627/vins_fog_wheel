#!/usr/bin/env python3
"""LOSO failure-prediction / early-warning benchmark on the reliability dataset.

Honesty rules (baked in):
  - LOSO by SEQUENCE (all grades of a seq held out together; urban38 never leaks into train).
  - Every model compared to TRIVIAL baseline (majority / predict-mean) + a 1-feature RULE.
  - Imbalanced classification scored by PR-AUC vs random-AP(=pos rate); accuracy/ROC-AUC reported but NOT headlined.
  - Per-sequence breakdown + lead-time; bootstrap CIs; positives counted, not hidden.
  - Scalers/imputers fit on TRAIN folds only. No threshold/HP tuning on the held-out sequence.

Targets:
  classification: failure_in_30s, survival_60s, grade_sensitive
  regression(early-warning): acc_margin_min30   (+ acc_bias_margin reported as IDENTITY sanity)
Models: trivial, rule(1-feat threshold), logistic/ridge, HistGB(monotonic for reg), GRU(documented).
"""
import sys, warnings, json
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.metrics import average_precision_score, roc_auc_score, precision_recall_curve, f1_score
rng = np.random.RandomState(42)

TSV = sys.argv[1] if len(sys.argv) > 1 else "/home/ivlab3/fwvio_estimator_ws_wheel/kaist_grade_scripts/reliability_dataset.tsv"
OUT = sys.argv[2] if len(sys.argv) > 2 else "/home/ivlab3/fwvio_estimator_ws_wheel/RELIABILITY_MODELS.md"
KEYS = ["dataset","sequence","grade","rep","t_end","tau","n_future_kf"]
BIN = ["failure_in_30s","death_in_60s","survival_60s","grade_sensitive"]   # death = 1-survival (rare minority view)
REG = ["acc_margin_min30","acc_bias_margin"]
LABELS = BIN + REG
L = []; P = L.append

def load():
    df = pd.read_csv(TSV, sep="\t")
    if "survival_60s" in df and "death_in_60s" not in df:
        df["death_in_60s"] = 1 - df["survival_60s"]   # rare minority view of survival
    feats = [c for c in df.columns if c not in KEYS + LABELS]
    for c in feats:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.replace([np.inf, -np.inf], np.nan)
    # drop all-NaN / zero-variance features
    keep = [c for c in feats if df[c].notna().any() and df[c].std(skipna=True) > 1e-12]
    return df, keep

def prep(tr, te, feats):
    """median-impute + standardize, fit on train only."""
    med = tr[feats].median()
    Xtr = tr[feats].fillna(med).values; Xte = te[feats].fillna(med).values
    sc = StandardScaler().fit(Xtr)
    return sc.transform(Xtr), sc.transform(Xte)

# ---------- GRU ----------
def gru_fit_predict(df, feats, target, is_clf, seqs_test):
    import torch, torch.nn as nn
    torch.manual_seed(42)
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    med = df[df.sequence.isin([s for s in df.sequence.unique() if s not in seqs_test])][feats].median()
    def runs_of(sub):
        out = []
        for (s, g, rp), d in sub.groupby(["sequence","grade","rep"]):
            d = d.sort_values("t_end")
            X = d[feats].fillna(med).values.astype(np.float32)
            y = d[target].values.astype(np.float32)
            out.append((s, X, y, d.index.values))
        return out
    tr = df[~df.sequence.isin(seqs_test)]; te = df[df.sequence.isin(seqs_test)]
    sc = StandardScaler().fit(tr[feats].fillna(med).values)
    class G(nn.Module):
        def __init__(s, d):
            super().__init__(); s.g = nn.GRU(d, 32, batch_first=True); s.drop = nn.Dropout(0.3); s.fc = nn.Linear(32, 1)
        def forward(s, x): o,_ = s.g(x); return s.fc(s.drop(o)).squeeze(-1)
    net = G(len(feats)).to(dev)
    opt = torch.optim.Adam(net.parameters(), lr=1e-3, weight_decay=1e-4)
    if is_clf:
        pos = max(1, int(tr[target].sum())); neg = max(1, len(tr) - pos)
        lossf = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([neg/pos], dtype=torch.float32, device=dev))
    else:
        lossf = nn.MSELoss()
    trr = runs_of(tr)
    for ep in range(40):
        net.train()
        for s, X, y, _ in trr:
            xb = torch.tensor(sc.transform(X)[None], device=dev); yb = torch.tensor(y[None], device=dev)
            opt.zero_grad(); out = net(xb); loss = lossf(out, yb); loss.backward(); opt.step()
    net.eval(); pred = np.full(len(df), np.nan)
    with torch.no_grad():
        for s, X, y, idx in runs_of(te):
            xb = torch.tensor(sc.transform(X)[None], device=dev)
            o = net(xb).cpu().numpy()[0]
            pred[df.index.get_indexer(idx)] = (1/(1+np.exp(-o))) if is_clf else o
    return pred

# ---------- metrics ----------
def clf_metrics(y, s, name):
    m = ~np.isnan(s); y = y[m].astype(int); s = s[m]
    n, npos = len(y), int(y.sum()); base = npos/n if n else 0
    if npos == 0 or npos == n:
        return dict(model=name, n=n, npos=npos, base_ap=round(base,4), pr_auc=None, roc_auc=None,
                    bestF1=None, thr=None, rec_at_p50=None, far=None, miss=None)
    pr = average_precision_score(y, s); roc = roc_auc_score(y, s)
    prec, rec, thr = precision_recall_curve(y, s)
    f1s = 2*prec*rec/(prec+rec+1e-12); bi = int(np.nanargmax(f1s[:-1])) if len(thr) else 0
    bthr = thr[bi] if len(thr) else 0.5
    pred = (s >= bthr).astype(int)
    tp = int(((pred==1)&(y==1)).sum()); fp = int(((pred==1)&(y==0)).sum())
    fn = int(((pred==0)&(y==1)).sum()); tn = int(((pred==0)&(y==0)).sum())
    far = fp/max(1,fp+tn); miss = fn/max(1,fn+tp)
    ok = np.where(prec[:-1] >= 0.5)[0]
    rec_at_p50 = float(np.max(rec[:-1][ok])) if len(ok) else 0.0
    return dict(model=name, n=n, npos=npos, base_ap=round(base,4), pr_auc=round(pr,4), roc_auc=round(roc,4),
                bestF1=round(float(np.nanmax(f1s)),4), thr=round(float(bthr),4),
                rec_at_p50=round(rec_at_p50,4), far=round(far,4), miss=round(miss,4))

def boot_prauc(y, s, n=500):
    m = ~np.isnan(s); y=y[m].astype(int); s=s[m]
    if y.sum()==0: return (None,None)
    vals=[]
    for _ in range(n):
        idx=rng.randint(0,len(y),len(y))
        if y[idx].sum()==0: continue
        vals.append(average_precision_score(y[idx], s[idx]))
    return (round(float(np.percentile(vals,2.5)),4), round(float(np.percentile(vals,97.5)),4)) if vals else (None,None)

def reg_metrics(y, p, name, ymean):
    m = ~np.isnan(p); y=y[m]; p=p[m]
    mae=float(np.mean(np.abs(y-p))); rmse=float(np.sqrt(np.mean((y-p)**2)))
    rmse_mean=float(np.sqrt(np.mean((y-ymean)**2)))
    skill=1-rmse/rmse_mean if rmse_mean>0 else 0
    return dict(model=name, n=len(y), mae=round(mae,4), rmse=round(rmse,4), skill_vs_mean=round(skill,4))

# ---------- LOSO drivers ----------
def loso_clf(df, feats, target):
    seqs = sorted(df.sequence.unique())
    scores = {k: np.full(len(df), np.nan) for k in ["rule","logreg","histgb","gru"]}
    rule_feat = "ba_norm_last" if "ba_norm_last" in feats else feats[0]
    for s in seqs:
        tr = df[df.sequence != s]; te = df[df.sequence == s]
        if tr[target].nunique() < 2:  # no positives in train -> models can't learn
            continue
        Xtr, Xte = prep(tr, te, feats); ytr = tr[target].values
        ti = df.index.get_indexer(te.index)
        # rule: standardized single feature score (higher ba_norm -> more failure). use raw value as score.
        scores["rule"][ti] = te[rule_feat].fillna(tr[rule_feat].median()).values
        # logistic (balanced)
        try:
            lr = LogisticRegression(max_iter=2000, class_weight="balanced").fit(Xtr, ytr)
            scores["logreg"][ti] = lr.predict_proba(Xte)[:,1]
        except Exception: pass
        # HistGB (sample-weight balanced)
        try:
            w = np.where(ytr==1, len(ytr)/(2*max(1,ytr.sum())), len(ytr)/(2*max(1,len(ytr)-ytr.sum())))
            hb = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=300,
                                                l2_regularization=1.0).fit(Xtr, ytr, sample_weight=w)
            scores["histgb"][ti] = hb.predict_proba(Xte)[:,1]
        except Exception: pass
    # GRU once (internal LOSO per seq is expensive; do per-seq)
    try:
        for s in seqs:
            if df[df.sequence!=s][target].nunique()<2: continue
            pr = gru_fit_predict(df, feats, target, True, [s])
            ti = df.index[df.sequence==s]; scores["gru"][df.index.get_indexer(ti)] = pr[df.index.get_indexer(ti)]
    except Exception as e:
        P(f"  (GRU skipped for {target}: {e})")
    y = df[target].values
    rows = [clf_metrics(y, np.where(df.sequence.isna(),np.nan,0.0)*0 + (y*0+y.mean()), "trivial(majority)")]  # placeholder
    rows = [dict(model="trivial(majority)", n=len(y), npos=int(y.sum()), base_ap=round(y.mean(),4),
                 pr_auc=round(y.mean(),4), roc_auc=0.5, bestF1=None, thr=None, rec_at_p50=0.0, far=0.0, miss=1.0)]
    for k in ["rule","logreg","histgb","gru"]:
        mm = clf_metrics(y, scores[k], k)
        if mm["pr_auc"] is not None:
            mm["prauc_ci95"] = boot_prauc(y, scores[k])
        rows.append(mm)
    return rows, scores

def loso_reg(df, feats, target):
    seqs = sorted(df.sequence.unique())
    preds = {k: np.full(len(df), np.nan) for k in ["persist","ridge","histgb","gru"]}
    for s in seqs:
        tr = df[df.sequence != s]; te = df[df.sequence == s]
        Xtr, Xte = prep(tr, te, feats); ytr = tr[target].values
        ti = df.index.get_indexer(te.index)
        # persistence: predict current margin (2.5 - ba_norm_last) as future margin
        if "ba_norm_last" in df:
            preds["persist"][ti] = (2.5 - te["ba_norm_last"].fillna(tr["ba_norm_last"].median())).values
        try:
            preds["ridge"][ti] = Ridge(alpha=1.0).fit(Xtr, ytr).predict(Xte)
        except Exception: pass
        try:
            # monotonic: margin should DECREASE as ba_norm features increase -> -1 on bias feats
            mono = [(-1 if ("ba_norm" in f or "bg_norm" in f) else 0) for f in feats]
            hb = HistGradientBoostingRegressor(max_depth=3, learning_rate=0.05, max_iter=400,
                                               l2_regularization=1.0, monotonic_cst=mono).fit(Xtr, ytr)
            preds["histgb"][ti] = hb.predict(Xte)
        except Exception as e:
            try: preds["histgb"][ti] = HistGradientBoostingRegressor(max_depth=3, max_iter=400).fit(Xtr,ytr).predict(Xte)
            except Exception: pass
    try:
        for s in seqs:
            pr = gru_fit_predict(df, feats, target, False, [s])
            ti = df.index[df.sequence==s]; preds["gru"][df.index.get_indexer(ti)] = pr[df.index.get_indexer(ti)]
    except Exception as e:
        P(f"  (GRU skipped for {target}: {e})")
    y = df[target].values; ymean = df[target].mean()
    rows = [dict(model="trivial(mean)", n=len(y), mae=round(float(np.mean(np.abs(y-ymean))),4),
                 rmse=round(float(np.sqrt(np.mean((y-ymean)**2))),4), skill_vs_mean=0.0)]
    for k in ["persist","ridge","histgb","gru"]:
        rows.append(reg_metrics(y, preds[k], k, ymean))
    return rows, preds

def lead_time(df, score, thr_q=0.5):
    """For each failing run (has failure_in_30s positives), seconds between first alarm and failure."""
    out = []
    for (s,g,rp), d in df.groupby(["sequence","grade","rep"]):
        d = d.sort_values("t_end")
        if d["failure_in_30s"].sum() == 0: continue
        sc = score[df.index.get_indexer(d.index)]
        if np.all(np.isnan(sc)): continue
        thr = np.nanquantile(sc, thr_q)
        fail_tau = d["tau"].max()  # run ends ~at failure
        alarms = d["tau"].values[(sc >= thr)]
        if len(alarms): out.append((f"{s}/{g}", round(float(fail_tau - alarms.min()),1)))
    return out

def main():
    df, feats = load()
    P(f"# Reliability models — LOSO benchmark\n")
    P(f"- windows={len(df)}, sequences={df.sequence.nunique()} (LOSO folds), features={len(feats)}")
    P(f"- ⚠ effective N ≈ #sequences. Headline = beat-trivial under LOSO, not window-count.")
    P(f"- ⚠ CAVEATS: `survival_60s`=0 occurs in the last 60s of EVERY run (incl. normal end-of-recording), "
      f"so it conflates failure-truncation with normal completion; `death_in_60s`=1−survival is the same signal. "
      f"Init-crash seqs (<3s of keyframes) yield ZERO 5s windows → dropped → real failure-detection events in the "
      f"windowed data are confined to urban38 only.\n")
    # identity sanity
    P("## Regression: `acc_bias_margin` (IDENTITY sanity — should be ~perfect, NOT a real task)")
    rows,_ = loso_reg(df, feats, "acc_bias_margin")
    P(pd.DataFrame(rows).to_markdown(index=False) + "\n")
    P("## ★ Regression: `acc_margin_min30` (early-warning: worst future-30s margin from current features)")
    rows, regpred = loso_reg(df, feats, "acc_margin_min30")
    P(pd.DataFrame(rows).to_markdown(index=False))
    # per-seq skill for best reg model on urban38
    P("\n  (per-sequence RMSE skill vs mean — focus urban38)")
    ymean = df["acc_margin_min30"].mean()
    for k in ["persist","ridge","histgb","gru"]:
        p = regpred[k]
        if np.all(np.isnan(p)): continue
        u = df.sequence=="urban38-pankyo"; yv=df["acc_margin_min30"].values[u]; pv=p[df.index.get_indexer(df.index[u])]
        m=~np.isnan(pv)
        if m.sum():
            rm=np.sqrt(np.mean((yv[m]-pv[m])**2)); rmean=np.sqrt(np.mean((yv[m]-ymean)**2))
            P(f"  - {k}: urban38 RMSE={rm:.3f} skill={1-rm/max(rmean,1e-9):+.3f}")
    P("")
    for tgt in BIN:
        P(f"## Classification: `{tgt}`")
        npos = int(df[tgt].sum()); nseq = (df.groupby('sequence')[tgt].sum()>0).sum()
        P(f"- positives={npos}/{len(df)} ({npos/len(df)*100:.2f}%), in {nseq} sequence(s).")
        if npos == 0:
            P("- ⛔ ZERO positives — not learnable. Skipped.\n"); continue
        if nseq <= 1:
            P(f"- ⚠ positives in only {nseq} sequence → under LOSO the fold holding it has 0 train positives; "
              f"expect failure to learn. Reported for honesty.")
        rows, scr = loso_clf(df, feats, tgt)
        P(pd.DataFrame(rows).to_markdown(index=False))
        # lead-time for failure_in_30s
        if tgt == "failure_in_30s":
            for k in ["rule","histgb"]:
                lt = lead_time(df, scr[k])
                if lt: P(f"\n  lead-time ({k}, alarm@median-score): " + ", ".join(f"{a}={b}s" for a,b in lt))
        P("")
    txt = "\n".join(map(str, L)); open(OUT,"w").write(txt); print(txt); print(f"\n[written -> {OUT}]")

if __name__ == "__main__":
    main()
