#!/usr/bin/env python3
"""Paper-2 — uncertainty-driven output policy (STANDALONE; reads G2 test predictions).

Change: paper2-viwo-conditioned-noue-v4. NO training, NO backend.

Policy levels from NOUE outputs (pred_sigma, p_invalid_vel):
  conservative_warning : pred_sigma > q90  (position itself unreliable)
  position_only        : p_invalid_vel > 0.5  (velocity unreliable, position usable)
  high_covariance      : q66 < pred_sigma <= q90
  full_state           : else
Evaluates: overconfident-wrong-speed (vs no-policy), planner-usable ratio, invalid-velocity
recall/precision, risk-coverage error@80%. Writes PAPER2_OUTPUT_POLICY_RESULTS.md.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import numpy as np, pandas as pd

WS = Path("/home/ivlab3/fwvio_estimator_ws_wheel")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preds", default=str(WS / "paper2_g2_test_predictions.csv"))
    args = ap.parse_args()
    if not Path(args.preds).exists():
        print(f"[policy] BLOCKED: no predictions at {args.preds} (run G2 first)"); return
    d = pd.read_csv(args.preds)
    n = len(d)
    if n < 20:
        print(f"[policy] WARN small test set n={n}")
    s = d["pred_sigma"].values; pinv = d["p_invalid_vel"].values
    q66, q90 = np.percentile(s, 66), np.percentile(s, 90)

    level = np.where(s > q90, "conservative_warning",
            np.where(pinv > 0.5, "position_only",
            np.where(s > q66, "high_covariance", "full_state")))
    d["level"] = level
    emits_vel = np.isin(level, ["full_state", "high_covariance"])
    usable = np.isin(level, ["full_state", "high_covariance", "position_only"])
    true_invalid = d["invalid_velocity"].values.astype(int)

    # overconfident wrong speed: among objects that EMIT velocity, fraction actually invalid
    oc_policy = float(true_invalid[emits_vel].mean()) if emits_vel.any() else float("nan")
    oc_nopolicy = float(true_invalid.mean())  # baseline: everyone emits velocity
    # invalid-velocity withholding (recall/precision): withhold = not emits_vel
    withhold = ~emits_vel
    rec = float(withhold[true_invalid == 1].mean()) if (true_invalid == 1).any() else float("nan")
    prec = float(true_invalid[withhold].mean()) if withhold.any() else float("nan")
    usable_ratio = float(usable.mean())
    # risk-coverage by pred_sigma (retain low-sigma 80%) -> mean pos_err
    order = np.argsort(s); err = d["pos_err_m"].values[order]
    n80 = max(1, int(0.8 * n)); rc80 = float(np.mean(err[:n80])); rc_all = float(np.mean(err))

    L = ["# PAPER2_OUTPUT_POLICY_RESULTS", "",
         f"> Uncertainty-driven output policy over NOUE-object test predictions (n={n}).", "",
         "## Level distribution", "| level | count | frac |", "|---|---|---|"]
    vc = pd.Series(level).value_counts()
    for lv in ["full_state", "high_covariance", "position_only", "conservative_warning"]:
        c = int(vc.get(lv, 0)); L.append(f"| {lv} | {c} | {c/n:.3f} |")
    L += ["", "## Effect", "| metric | value |", "|---|---|",
          f"| overconfident-wrong-speed (policy: among vel-emitters that are truly invalid) | {oc_policy:.3f} |",
          f"| overconfident-wrong-speed (no policy: all emit velocity) | {oc_nopolicy:.3f} |",
          f"| invalid-velocity recall (withheld / true-invalid) | {rec:.3f} |",
          f"| invalid-velocity precision (true-invalid / withheld) | {prec:.3f} |",
          f"| planner-usable object ratio | {usable_ratio:.3f} |",
          f"| risk-coverage mean pos_err @80% (low-sigma) | {rc80:.2f} |",
          f"| mean pos_err @100% (all) | {rc_all:.2f} |", "",
          "## Reading",
          f"- policy {'REDUCES' if oc_policy < oc_nopolicy else 'does NOT reduce'} overconfident wrong-velocity "
          f"({oc_nopolicy:.3f} -> {oc_policy:.3f} among emitters).",
          f"- risk-coverage: keeping the 80% lowest-uncertainty cuts mean pos_err {rc_all:.2f} -> {rc80:.2f} m.",
          "- thresholds = sigma q66/q90 + p_invalid_vel>0.5 (documented; not tuned).",
          "- NOTE: NOUE here is object-only (VINS-quality conditioning blocked); policy quality bounded accordingly."]
    (WS / "PAPER2_OUTPUT_POLICY_RESULTS.md").write_text("\n".join(L) + "\n")
    print(f"[policy] wrote PAPER2_OUTPUT_POLICY_RESULTS.md ; overconf {oc_nopolicy:.3f}->{oc_policy:.3f}, "
          f"risk-cov {rc_all:.2f}->{rc80:.2f}, usable {usable_ratio:.3f}")


if __name__ == "__main__":
    main()
