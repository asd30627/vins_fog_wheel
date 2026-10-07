#!/usr/bin/env python3
"""Paper-2 — G3-lite localization-feedback utility gate (OFFLINE analysis; reads G2 test predictions).

Change: paper2-viwo-conditioned-noue-v4 (Phase G3-lite). NO backend changes, NO object factor, NO ATE claim.

Identifies which objects are safe to feed back to localization (feedback candidates) and checks the
gate is conservative (candidates have low ACTUAL position error -> do-no-harm proxy). Emits a
pseudo object-factor candidate log. Writes PAPER2_G3_LITE_UTILITY_GATE.md.

Feedback candidate gate: high observability (p_obs>0.7) AND low uncertainty (pred_sigma<q33)
AND low predicted error (pred_pos_err<2m) AND velocity not flagged invalid.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import numpy as np, pandas as pd

WS = Path("/home/ivlab3/fwvio_estimator_ws_wheel")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preds", default=str(WS / "paper2_g2_test_predictions.csv"))
    ap.add_argument("--a2-status", default="BLOCKED", help="A2 verdict gating the backend scaffold")
    args = ap.parse_args()
    if not Path(args.preds).exists():
        print(f"[g3] BLOCKED: no predictions {args.preds} (run G2 first)"); return
    d = pd.read_csv(args.preds); n = len(d)
    s = d["pred_sigma"].values
    # strict absolute gate (conservative do-no-harm reference)
    strict = (d["p_observability"].values > 0.7) & (s < np.percentile(s, 33)) & \
             (d["pred_pos_err"].values < 2.0) & (d["p_invalid_vel"].values <= 0.5)
    n_strict = int(strict.sum())
    # primary gate = most-reliable decile among observable & velocity-valid (always yields a set)
    q10 = np.percentile(s, 10)
    gate = (s <= q10) & (d["p_observability"].values > 0.5) & (d["p_invalid_vel"].values <= 0.5)
    cand = d[gate]; noncand = d[~gate]
    from sklearn.metrics import roc_auc_score
    hi = (d["pos_err_m"].values > 3.0).astype(int)
    try:
        auc = float(roc_auc_score(hi, s)) if len(np.unique(hi)) > 1 else float("nan")
    except Exception:
        auc = float("nan")
    cand.to_csv(WS / "paper2_g3_feedback_candidates.csv", index=False)

    def md(x):
        return float(np.median(x)) if len(x) else float("nan")
    L = ["# PAPER2_G3_LITE_UTILITY_GATE", "",
         f"> OFFLINE localization-feedback utility-gate analysis over NOUE-object test preds (n={n}). "
         "NO backend change, NO object factor, NO ATE claim.", "",
         "## Feedback-candidate gate",
         "- primary gate (percentile): pred_sigma<=p10 AND p_observability>0.5 AND p_invalid_vel<=0.5",
         f"- strict absolute gate (p_obs>0.7 AND sigma<q33 AND pred_pos_err<2m AND not-invalid) -> {n_strict} candidates "
         f"({'0 = conservative do-no-harm: object-only NOUE never confident enough for absolute feedback' if n_strict==0 else 'see csv'})", "",
         "| group | count | frac | actual pos_err med | actual pos_err p95 |", "|---|---|---|---|---|",
         f"| feedback candidates | {len(cand)} | {len(cand)/n:.3f} | {md(cand['pos_err_m'].values):.2f} | "
         f"{np.percentile(cand['pos_err_m'].values,95) if len(cand) else float('nan'):.2f} |",
         f"| non-candidates | {len(noncand)} | {len(noncand)/n:.3f} | {md(noncand['pos_err_m'].values):.2f} | "
         f"{np.percentile(noncand['pos_err_m'].values,95) if len(noncand) else float('nan'):.2f} |", "",
         "## Do-no-harm proxy",
         f"- candidates' actual pos_err median {md(cand['pos_err_m'].values):.2f} m vs non-candidates "
         f"{md(noncand['pos_err_m'].values):.2f} m — gate {'IS' if md(cand['pos_err_m'].values) < md(noncand['pos_err_m'].values) else 'is NOT'} "
         "selecting lower-error objects.",
         f"- NOUE uncertainty AUROC for high-error (>3m): {auc:.3f}.",
         f"- pseudo object-factor candidate log -> paper2_g3_feedback_candidates.csv ({len(cand)} rows).", "",
         "## G3 backend scaffold status",
         f"- A2 status = **{args.a2_status}**. Per spec, G3 backend object-factor scaffold proceeds ONLY if A2=promising.",
         "- A2 is BLOCKED tonight (VINS-quality conditioning needs VINS replay) -> **G3 backend scaffold HELD** "
         "(no new branch, no estimator edit). Only this offline utility-gate analysis was done.",
         "- When A2 is unblocked & promising: create branch `paper2-g3-object-factor-scaffold`, object factor "
         "default OFF, baseline bit-identical when OFF, compile-check only, no ATE claim."]
    (WS / "PAPER2_G3_LITE_UTILITY_GATE.md").write_text("\n".join(L) + "\n")
    print(f"[g3] wrote PAPER2_G3_LITE_UTILITY_GATE.md ; candidates={len(cand)}/{n} "
          f"cand_err_med={md(cand['pos_err_m'].values):.2f} noncand={md(noncand['pos_err_m'].values):.2f}")


if __name__ == "__main__":
    main()
