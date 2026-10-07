#!/usr/bin/env python3
"""EDA for the reliability dataset. Reports per-label class balance (global + per-sequence),
feature distributions, and correlation with the early-warning targets. Writes a markdown summary.
Honest-by-design: prints positive COUNTS and per-sequence breakdown, flags <5% positive labels."""
import sys
import numpy as np, pandas as pd

TSV = sys.argv[1] if len(sys.argv) > 1 else "/home/ivlab3/fwvio_estimator_ws_wheel/kaist_grade_scripts/reliability_dataset.tsv"
OUT = sys.argv[2] if len(sys.argv) > 2 else "/home/ivlab3/fwvio_estimator_ws_wheel/RELIABILITY_EDA.md"
KEYS = ["dataset","sequence","grade","rep","t_end","tau","n_future_kf"]
BIN_LABELS = ["failure_in_30s","survival_60s","grade_sensitive"]
REG_LABELS = ["acc_bias_margin","acc_margin_min30"]
LABELS = BIN_LABELS + REG_LABELS

def main():
    df = pd.read_csv(TSV, sep="\t")
    feats = [c for c in df.columns if c not in KEYS + LABELS]
    L = []
    P = L.append
    P(f"# Reliability dataset — EDA\n")
    P(f"- rows (windows): **{len(df)}**  |  sequences: **{df.sequence.nunique()}**  |  grades: {sorted(df.grade.unique())}")
    P(f"- features: {len(feats)}  |  window=5s stride=1s")
    P(f"- ⚠ effective N ≈ #sequences = **{df.sequence.nunique()}** (windows are autocorrelated; stride<window).\n")

    P("## Per-sequence window counts (x grade)")
    ct = df.pivot_table(index="sequence", columns="grade", values="t_end", aggfunc="count", fill_value=0)
    P(ct.to_markdown() + "\n")

    P("## Label class balance (binary) — global")
    P("| label | n_pos | n | pos_rate | flag |")
    P("|---|---|---|---|---|")
    for lb in BIN_LABELS:
        npos = int(df[lb].sum()); n = len(df); rate = npos/n
        flag = "⚠ <5%" if rate < 0.05 else ""
        if npos == 0: flag = "⛔ ZERO positives"
        P(f"| {lb} | {npos} | {n} | {rate:.4f} | {flag} |")
    P("")

    P("## Binary-label positives — per sequence (LOSO honesty: where do positives live?)")
    for lb in BIN_LABELS:
        g = df.groupby("sequence")[lb].sum()
        nz = g[g > 0]
        P(f"- **{lb}**: total {int(g.sum())} positives; sequences with positives: "
          + (", ".join(f"{s}({int(v)})" for s, v in nz.items()) if len(nz) else "NONE"))
    P("")

    P("## Regression targets — distribution")
    P("| target | mean | std | min | p25 | p50 | p75 | max |")
    P("|---|---|---|---|---|---|---|---|")
    for lb in REG_LABELS:
        s = df[lb].astype(float)
        P(f"| {lb} | {s.mean():.3f} | {s.std():.3f} | {s.min():.3f} | {s.quantile(.25):.3f} | "
          f"{s.median():.3f} | {s.quantile(.75):.3f} | {s.max():.3f} |")
    P("")
    # identity check: acc_bias_margin vs (2.5 - ba_norm_last)
    if "ba_norm_last" in df:
        ident = (df["acc_bias_margin"] - (2.5 - df["ba_norm_last"])).abs().max()
        P(f"- ⚠ `acc_bias_margin` is identity of feature `ba_norm_last` (max|diff|={ident:.2e}) → trivial; "
          f"use **`acc_margin_min30`** (future) as the real early-warning regression target.\n")

    P("## Feature summary (describe)")
    desc = df[feats].astype(float).describe().T[["mean","std","min","50%","max"]]
    P(desc.to_markdown() + "\n")

    P("## Top feature correlations with `acc_margin_min30` (early-warning target)")
    cc = df[feats + ["acc_margin_min30"]].astype(float).corr()["acc_margin_min30"].drop("acc_margin_min30")
    cc = cc.reindex(cc.abs().sort_values(ascending=False).index)
    P("| feature | corr |")
    P("|---|---|")
    for k, v in cc.head(15).items():
        P(f"| {k} | {v:+.3f} |")
    P("")

    P("## Correlation with `failure_in_30s`")
    cc2 = df[feats + ["failure_in_30s"]].astype(float).corr()["failure_in_30s"].drop("failure_in_30s")
    cc2 = cc2.reindex(cc2.abs().sort_values(ascending=False).index)
    P("| feature | corr |")
    P("|---|---|")
    for k, v in cc2.head(12).items():
        P(f"| {k} | {v:+.3f} |")
    P("")

    txt = "\n".join(map(str, L))
    open(OUT, "w").write(txt)
    print(txt)
    print(f"\n[EDA written -> {OUT}]")

if __name__ == "__main__":
    main()
