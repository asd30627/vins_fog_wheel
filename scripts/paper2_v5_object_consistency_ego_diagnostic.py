#!/usr/bin/env python3
"""Paper-2 v5 (C4, optional) — object-consistency ego-degradation diagnostic. OFFLINE correlation only.

Change: paper2-observability-aware-object-validity-v5.

Idea: when ego pose/yaw drifts, many distant objects show COHERENT fake apparent motion. We test
whether a per-frame object-motion-inconsistency signal correlates with VINS degradation (per-frame
outlier_ratio / feat_count, and per-recording VINS scale divergence). NO VINS feedback, NO object
factor, NO localization-improvement claim. If correlation is unclear -> mark weak/null.

Output: PAPER2_V5_OBJECT_CONSISTENCY_EGO_DIAGNOSTIC.md
"""
from __future__ import annotations
from pathlib import Path
import numpy as np, pandas as pd

WS = Path("/home/ivlab3/fwvio_estimator_ws_wheel")


def main():
    df = pd.read_csv(WS / "paper2_raw_object_benchmark_all_with_vins.csv", low_memory=False)
    df = df[(df["matched"] == 1) & (df["vins_match_ok"] == 1)].copy()
    for c in ["speed_err_ms", "raw_speed_ms", "dir_err_deg", "vins_outlier_ratio", "vins_feat_count", "gt_range_m"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df[df["speed_err_ms"].notna()].copy()

    # per-frame object-motion signals + VINS quality (vins quality is per-frame, same for all objs in a frame)
    g = df.groupby(["town", "run", "frame"])
    pf = g.agg(obj_n=("speed_err_ms", "size"),
               obj_speed_err_mean=("speed_err_ms", "mean"),
               obj_raw_speed_mean=("raw_speed_ms", "mean"),
               obj_raw_speed_std=("raw_speed_ms", "std"),
               vins_outlier=("vins_outlier_ratio", "mean"),
               vins_feat=("vins_feat_count", "mean")).reset_index()
    pf = pf[pf["obj_n"] >= 2].copy()   # need >=2 objects for "consistency"

    from scipy.stats import spearmanr
    def sp(a, b):
        m = a.notna() & b.notna()
        if m.sum() < 30: return (float("nan"), float("nan"), int(m.sum()))
        r, p = spearmanr(a[m], b[m]); return (float(r), float(p), int(m.sum()))

    c1 = sp(pf["obj_speed_err_mean"], pf["vins_outlier"])
    c2 = sp(pf["obj_speed_err_mean"], -pf["vins_feat"])   # low feat = degraded -> expect positive
    c3 = sp(pf["obj_raw_speed_std"], pf["vins_outlier"])

    # per-recording: mean object speed error vs VINS scale divergence
    rep = WS / "paper2_vins_replay_status.tsv"
    rec_corr = (float("nan"), float("nan"), 0)
    scale_tbl = ""
    if rep.exists():
        rs = pd.read_csv(rep, sep="\t")
        rs["scale"] = pd.to_numeric(rs["scale"], errors="coerce")
        rs["key"] = rs["rec"].str.replace("__dynamic_v3__run", "@", regex=False)  # Town@run... approx
        # map recording -> mean obj speed err
        recagg = df.groupby(["town", "run"])["speed_err_ms"].mean().reset_index()
        recagg["recname"] = recagg["town"] + "__dynamic_v3__run" + recagg["run"].astype(str)
        m = recagg.merge(rs[["rec", "scale"]], left_on="recname", right_on="rec", how="inner")
        rec_corr = sp(m["speed_err_ms"], m["scale"])
        scale_tbl = m[["recname", "speed_err_ms", "scale"]].round(2).to_string(index=False)

    def verdict(rp):
        r, p, n = rp
        if r != r or n < 30: return "null (insufficient)"
        if abs(r) >= 0.3 and p < 0.05: return f"promising (rho={r:.2f}, p={p:.1e})"
        if abs(r) >= 0.15 and p < 0.05: return f"weak (rho={r:.2f}, p={p:.1e})"
        return f"null (rho={r:.2f}, p={p:.2g})"

    L = ["# PAPER2_V5_OBJECT_CONSISTENCY_EGO_DIAGNOSTIC (C4, optional)", "",
         "> OFFLINE correlation: does per-frame object-motion inconsistency track VINS degradation? "
         "NO VINS feedback, NO object factor, NO localization claim.", "",
         f"- frames analyzed (>=2 objects): {len(pf)}", "",
         "## Frame-level Spearman correlations",
         f"- obj_speed_err_mean vs vins_outlier_ratio: rho={c1[0]:.3f} p={c1[1]:.2g} n={c1[2]} -> **{verdict(c1)}**",
         f"- obj_speed_err_mean vs (-vins_feat_count): rho={c2[0]:.3f} p={c2[1]:.2g} n={c2[2]} -> **{verdict(c2)}**",
         f"- obj_raw_speed_std vs vins_outlier_ratio: rho={c3[0]:.3f} p={c3[1]:.2g} n={c3[2]} -> **{verdict(c3)}**", "",
         "## Recording-level: mean object speed error vs VINS scale divergence",
         f"- rho={rec_corr[0]:.3f} p={rec_corr[1]:.2g} n={rec_corr[2]} -> **{verdict(rec_corr)}**", ""]
    if scale_tbl:
        L += ["```", scale_tbl, "```", ""]
    overall = max([abs(c1[0]) if c1[0] == c1[0] else 0, abs(c2[0]) if c2[0] == c2[0] else 0,
                   abs(rec_corr[0]) if rec_corr[0] == rec_corr[0] else 0])
    concl = "promising" if overall >= 0.3 else ("weak" if overall >= 0.15 else "null/weak")
    L += ["## Conclusion (honest)",
          f"- strongest signal |rho| ≈ {overall:.2f} -> diagnostic = **{concl}**.",
          "- object-motion inconsistency as an INDEPENDENT ego-degradation alert: "
          + ("shows a usable correlation (worth a secondary contribution)." if concl == "promising"
             else "is weak/inconclusive here — report as a minor/negative finding, do not package."),
          "- caveat: VINS scale divergence here is partly artifact of aggressive 640 recordings; "
          "object speed error also driven by range/observability, confounding the ego-degradation link."]
    (WS / "PAPER2_V5_OBJECT_CONSISTENCY_EGO_DIAGNOSTIC.md").write_text("\n".join(L) + "\n")
    print(f"[v5-diag] frame corr outlier rho={c1[0]:.2f} feat rho={c2[0]:.2f} rec-scale rho={rec_corr[0]:.2f} -> {concl}")


if __name__ == "__main__":
    main()
