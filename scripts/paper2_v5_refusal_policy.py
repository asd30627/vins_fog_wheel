#!/usr/bin/env python3
"""Paper-2 v5 (C3) — refusal-aware dynamic object state policy. STANDALONE; no backend.

Change: paper2-observability-aware-object-validity-v5.

Levels: full_state / position_only / conservative_warning / unobservable (velocity emitted only in full_state).
Driven by OVI_velocity (C2) + a small OVI_position (logistic on log_range+depth_noise). Compared vs
no-policy (always emit velocity) and a naive distance-threshold policy. Reports overconfident-wrong-velocity,
invalid-velocity recall, valid-velocity retention / false-refusal, planner-usable ratio, per distance bin.
"""
from __future__ import annotations
from pathlib import Path
import numpy as np, pandas as pd

WS = Path("/home/ivlab3/fwvio_estimator_ws_wheel")
BINS = ["0-15m", "15-30m", "30m+"]


def main():
    d = pd.read_parquet(WS / "paper2_v5_validity_with_ovi.parquet")
    tr = (d["split"] == "train").values; te = (d["split"] == "test").values
    # position-validity predictor (interpretable logistic on geometry)
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_curve
    Zp = np.column_stack([d["log_range"].values, d["depth_noise"].fillna(0).values])
    Zp = (Zp - Zp[tr].mean(0)) / (Zp[tr].std(0) + 1e-9)
    lp = LogisticRegression(max_iter=500).fit(Zp[tr], d["position_valid"].values[tr])
    ovi_pos = lp.predict_proba(Zp)[:, 1]

    def youden(score, label):
        fpr, tpr, th = roc_curve(label[tr], score[tr]); return th[np.argmax(tpr - fpr)]
    thr_v = youden(d["OVI_velocity_cal"].values, d["velocity_valid"].values)
    thr_p = youden(ovi_pos, d["position_valid"].values)
    vel_ok = d["OVI_velocity_cal"].values >= thr_v
    pos_ok = ovi_pos >= thr_p
    near = d["range_m"].values < 15.0

    # OVI policy levels
    level = np.full(len(d), "unobservable", dtype=object)
    level[pos_ok & vel_ok] = "full_state"
    level[pos_ok & ~vel_ok] = "position_only"
    level[~vel_ok & near] = "conservative_warning"      # near + velocity unreliable = high risk
    level[~pos_ok & ~near] = "unobservable"
    d["level"] = level

    true_inv = d["invalid_velocity"].values.astype(int)
    true_valid = d["velocity_valid"].values.astype(int)

    def policy_metrics(emit, name):
        e = emit & te
        emit_n = e.sum()
        oc = float(true_inv[e].mean()) if emit_n else float("nan")              # overconfident-wrong-velocity
        withheld = (~emit) & te
        rec = float(withheld[(true_inv == 1) & te].sum() / max((true_inv[te] == 1).sum(), 1))  # invalid recall
        ret = float(emit[(true_valid == 1) & te].sum() / max((true_valid[te] == 1).sum(), 1))  # valid retention
        return dict(model=name, emit_frac=float(e.sum() / te.sum()), overconf_wrong=oc,
                    invalid_recall=rec, valid_retention=ret, false_refusal=1 - ret)

    emit_nopolicy = np.ones(len(d), bool)
    emit_distance = d["range_m"].values < 15.0
    emit_ovi = (level == "full_state")
    M = [policy_metrics(emit_nopolicy, "no_policy"),
         policy_metrics(emit_distance, "distance_policy(range<15)"),
         policy_metrics(emit_ovi, "v5_OVI_policy")]
    usable = np.isin(level, ["full_state", "position_only"])
    usable_ratio = float(usable[te].mean())
    from collections import Counter
    lvl_counts = Counter(level[te])

    L = ["# PAPER2_V5_REFUSAL_POLICY_RESULTS (C3)", "",
         f"> Refusal-aware object state policy on test n={int(te.sum())}. Velocity emitted ONLY in full_state.",
         f"> OVI thresholds (train-Youden): vel {thr_v:.3f}, pos {thr_p:.3f}.", "",
         "## Policy comparison",
         "| policy | emit_velocity_frac | overconfident_wrong_velocity | invalid_recall | valid_retention | false_refusal |",
         "|---|---|---|---|---|---|"]
    for m in M:
        L.append(f"| {m['model']} | {m['emit_frac']:.3f} | {m['overconf_wrong']:.3f} | {m['invalid_recall']:.3f} | "
                 f"{m['valid_retention']:.3f} | {m['false_refusal']:.3f} |")
    L += ["", "## v5 OVI policy level distribution (test)", "| level | count | frac |", "|---|---|---|"]
    for lv in ["full_state", "position_only", "conservative_warning", "unobservable"]:
        c = lvl_counts.get(lv, 0); L.append(f"| {lv} | {c} | {c/te.sum():.3f} |")
    L += ["", f"- planner-usable (full_state OR position_only) ratio = {usable_ratio:.3f}", ""]
    # per-bin overconfident-wrong for no-policy vs OVI
    L += ["## Overconfident-wrong-velocity by distance bin (no-policy → OVI policy)", "| bin | no_policy | v5_OVI |", "|---|---|---|"]
    for b in BINS:
        mb = (d["dist_bin"] == b).values & te
        if mb.sum() >= 8:
            ocn = float(true_inv[mb].mean())
            em = emit_ovi & mb
            oco = float(true_inv[em].mean()) if em.sum() else float("nan")
            L.append(f"| {b} | {ocn:.3f} | {oco:.3f} |")
    M_ovi = M[2]; M_no = M[0]
    L += ["", "## Reading",
          f"- v5 OVI policy cuts overconfident-wrong-velocity {M_no['overconf_wrong']:.3f} → {M_ovi['overconf_wrong']:.3f} "
          f"among emitted, at false-refusal {M_ovi['false_refusal']:.3f} (invalid-velocity recall {M_ovi['invalid_recall']:.3f}).",
          f"- vs naive distance<15 policy (overconf {M[1]['overconf_wrong']:.3f}, false-refusal {M[1]['false_refusal']:.3f}).",
          "- reference: v4 NOUE policy reported overconfident 0.586→0.387 on its own split (PAPER2_OUTPUT_POLICY_RESULTS.md; different split, not directly comparable).",
          "- thresholds/operating point ablatable; position_only is a real regime (position usable, velocity withheld)."]
    (WS / "PAPER2_V5_REFUSAL_POLICY_RESULTS.md").write_text("\n".join(L) + "\n")
    print(f"[v5-policy] overconf no_policy {M_no['overconf_wrong']:.3f} -> OVI {M_ovi['overconf_wrong']:.3f} "
          f"; false_refusal {M_ovi['false_refusal']:.3f} ; usable {usable_ratio:.3f}")


if __name__ == "__main__":
    main()
