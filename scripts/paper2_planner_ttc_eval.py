#!/usr/bin/env python3
"""Paper-2 — PLANNER-FACING MINIMAL EVALUATION (TTC / collision-risk). NOT a planner method.

For front objects, a planner consumes object velocity to compute time-to-contact (TTC) and act on it.
We measure how much TCSV's refusal protects this downstream decision, WITHOUT building a planner:
  - TTC_gt   from GT range-rate; TTC_raw from RAW range-rate (closing only).
  - risk event = TTC < TAU (e.g. 3 s).
  - false_alarm  = raw says risk, GT says safe.
  - missed_risk  = raw says safe, GT says risk (the dangerous one).
  - overconfident_velocity_accepted = emitted (not refused) samples whose RAW velocity is invalid AND that
    flip the TTC risk decision vs GT.
Compare ALWAYS-EMIT vs TCSV-refusal at MATCHED coverage. CARLA has GT range (gt_range_m) → primary.
KITTI lacks a clean per-frame GT range here → reported as [TODO].
Output: PAPER2_PLANNER_TTC_RESULTS.md + paper2_planner_ttc_metrics.csv
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
import paper2_tcsv_features as F
from paper2_tcsv_train_eval import split_by_key
from sklearn.ensemble import HistGradientBoostingClassifier

WS = Path("/home/ivlab3/fwvio_estimator_ws_wheel")
TAU_TTC = 3.0   # s
DT = 0.05       # CARLA


def range_rate(df, col, group=("town", "run", "track_id"), dt=DT):
    d = df.sort_values(list(group) + ["frame"])
    rr = np.full(len(d), np.nan)
    R = d[col].to_numpy(float); FR = d["frame"].to_numpy()
    for _, rows in d.groupby(list(group), sort=False).indices.items():
        rows = list(rows)
        for i in range(1, len(rows)):
            if FR[rows[i]] - FR[rows[i-1]] == 1:
                rr[rows[i]] = -(R[rows[i]] - R[rows[i-1]]) / dt   # closing>0
    d["_rr"] = rr
    return d


def ttc(rng, rr):
    out = np.full(len(rng), np.inf)
    closing = rr > 0.1
    out[closing] = rng[closing] / rr[closing]
    return out


def main():
    car = F.load_carla()
    front = car[(car["body_fwd"] > 0) & (car["body_lat"].abs() < 2.5)].copy()
    fr = range_rate(front, "range_m")          # raw range-rate
    fg = range_rate(front, "gt_range_m")        # gt range-rate (same ordering)
    fr["_rr_gt"] = fg["_rr"].values
    d = fr[fr["_rr"].notna() & fr["_rr_gt"].notna() & fr["gt_range_m"].notna()].copy()
    ttc_raw = ttc(d["range_m"].values, d["_rr"].values)
    ttc_gt = ttc(d["gt_range_m"].values, d["_rr_gt"].values)
    risk_raw = ttc_raw < TAU_TTC; risk_gt = ttc_gt < TAU_TTC
    inv_vel = d["velocity_valid"].values == 0

    # TCSV score on this subset (train on non-front to avoid trivial overlap; in-domain by run split)
    te = split_by_key(car)
    Xall = F.prep(car, F.TCSV_FEATS); yall = car["velocity_valid"].values.astype(int)
    m = HistGradientBoostingClassifier(max_iter=300, max_depth=4, learning_rate=0.05,
                                       l2_regularization=1.0, random_state=7).fit(Xall[~te], yall[~te])
    score = m.predict_proba(F.prep(d, F.TCSV_FEATS))[:, 1]

    n = len(d)
    base_fa = float((risk_raw & ~risk_gt).mean())
    base_miss = float((~risk_raw & risk_gt).mean())
    base_oc = float((inv_vel & (risk_raw != risk_gt)).mean())   # invalid vel that flips decision (accepted by planner)

    rows = [dict(policy="always_emit", coverage=1.0, false_alarm=round(base_fa, 4),
                 missed_risk=round(base_miss, 4), overconf_vel_accepted=round(base_oc, 4), n=n)]
    for cov in [0.9, 0.8, 0.7]:
        thr = np.quantile(score, 1 - cov)
        emit = score >= thr
        fa = float((risk_raw & ~risk_gt & emit).sum() / max(emit.sum(), 1))
        miss = float((~risk_raw & risk_gt & emit).sum() / max(emit.sum(), 1))
        oc = float((inv_vel & (risk_raw != risk_gt) & emit).sum() / max(emit.sum(), 1))
        rows.append(dict(policy=f"TCSV_emit@cov{cov}", coverage=round(float(emit.mean()), 3),
                         false_alarm=round(fa, 4), missed_risk=round(miss, 4),
                         overconf_vel_accepted=round(oc, 4), n=int(emit.sum())))
    M = pd.DataFrame(rows); M.to_csv(WS / "paper2_planner_ttc_metrics.csv", index=False)

    L = ["# PAPER2_PLANNER_TTC_RESULTS", "",
         f"> Minimal planner-facing eval (NOT a planner). CARLA front objects (body_fwd>0, |lat|<2.5 m), "
         f"n={n}. TTC=range/closing-rate; risk if TTC<{TAU_TTC}s. GT range-rate from gt_range_m. "
         "Compares always-emit vs TCSV refusal at matched coverage (rates among EMITTED).", "",
         "| policy | coverage | false_alarm | missed_risk | overconf_vel_accepted | n_emit |",
         "|---|---|---|---|---|---|"]
    for _, r in M.iterrows():
        L.append(f"| {r.policy} | {r.coverage} | {r.false_alarm:.3f} | {r.missed_risk:.3f} | "
                 f"{r.overconf_vel_accepted:.3f} | {int(r.n)} |")
    base = M.iloc[0]; best = M.iloc[-1]
    L += ["", "## Reading (supports C3?)",
          f"- always-emit: overconfident invalid velocities that FLIP the TTC decision = **{base.overconf_vel_accepted:.3f}**.",
          f"- TCSV refusal at coverage≈{best.coverage}: drops to **{best.overconf_vel_accepted:.3f}** "
          f"({'reduces' if best.overconf_vel_accepted < base.overconf_vel_accepted else 'does NOT reduce'} planner-accepted bad velocity).",
          "- missed_risk is the safety-critical error; report whether refusal trades false_alarm/coverage for fewer "
          "planner-accepted bad velocities. Honest: refusal removes velocity, so missed_risk via velocity can only be "
          "addressed by falling back to position-only TTC `[TODO: position-only TTC variant]`.",
          "- KITTI TTC: `[TODO: needs clean per-frame GT range; not computed here]`.",
          "", "## Caveats",
          "- This is a *minimal* decision-level probe, NOT a planning method (red line: no trajectory planning).",
          "- TTC uses range-rate, not full relative-velocity vectors; a richer TTC is future work."]
    (WS / "PAPER2_PLANNER_TTC_RESULTS.md").write_text("\n".join(L) + "\n")
    print("[ttc] done. base oc", round(base_oc, 3))


if __name__ == "__main__":
    main()
