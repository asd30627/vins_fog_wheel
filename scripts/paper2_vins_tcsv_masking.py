#!/usr/bin/env python3
"""Paper-2 Phase 2 — deploy the REAL TCSV-M(mono) as a per-detection VINS routing signal.

This replaces the prior 'validity_aware' = raw_speed_gate. It emits, for every GT-matched object
detection in the target CLEAN runs, the learned validity probabilities + a routing policy + a soft
feature weight, WITHOUT using any GT feature at inference (GT is used only to build training labels
and, separately, the oracle). Leak-free: the model scoring a run is trained on all OTHER runs
(leave-target-run-out at the (town,run) level).

Model: TCSV-M(mono) = HistGradientBoostingClassifier(max_iter=300, max_depth=4, lr=0.05, l2=1.0)
with the monotone constraints from paper2_frame_vs_sequence_search (aligned to F.TCSV_FEATS order).
Three heads: position_valid, velocity_valid, full_state_valid(=pos&vel).

Output (all under paper2/track_a/):
  paper2_tcsv_vins_scores.csv   : run,frame,track_id,bbox_u,bbox_v,bbox_w,bbox_h,
                                  P_position_valid,P_velocity_valid,P_full_state_valid,
                                  uncertainty,policy,feat_weight,model_version
This CSV is the input to the mask/weight builder that turns bboxes -> per-frame VINS feature routing.
NO VINS run here; this is the deployment scoring stage only.
"""
from __future__ import annotations
import sys, json
from pathlib import Path
import numpy as np, pandas as pd

WS = Path("/home/ivlab3/fwvio_estimator_ws_wheel")
sys.path.insert(0, str(WS / "scripts"))
import paper2_tcsv_features as F  # noqa: E402
from sklearn.ensemble import HistGradientBoostingClassifier  # noqa: E402

OUT = WS / "paper2" / "track_a"
MODEL_VERSION = "TCSV-M(mono)_hgbm_v1_leaveRunOut"

# monotone constraints aligned to F.TCSV_FEATS =
# [range_m,bearing_deg,bbox_area,depth_m,det_conf, track_age,raw_speed,
#  cv_residual,acceleration_score,jerk_score,velocity_direction_flip_count,
#  bbox_depth_consistency,short_window_position_jitter,short_window_velocity_jitter]
MONO = [-1, 0, +1, -1, +1, +1, 0, -1, -1, -1, -1, +1, -1, -1]
assert len(MONO) == len(F.TCSV_FEATS), (len(MONO), len(F.TCSV_FEATS))

# target clean+stable runs (PAPER2_CLEAN_BENCHMARK_MANIFEST.md); (town, run)
TARGETS = [("Town01", "dense_b1"), ("Town01", "medium_b1")]

# routing thresholds (documented in PAPER2_TCSV_MODEL_DEPLOYMENT_AUDIT.md)
TAU_HI = 0.60      # "high validity"
TAU_LO = 0.40      # "low validity"
UNC_HI = 0.20      # |P-0.5| < UNC_HI/... -> uncertain band (uncertainty>0.30 below)
W_KEEP = 1.00
W_LOWER = 0.60     # position ok / velocity bad -> keep as landmark, lower weight
W_SOFT = 0.40      # uncertain
W_SUPPRESS = 0.15  # full_state low
W_REJECT = 0.0     # high dynamic unreliable


def fit_head(train_X, train_y):
    m = HistGradientBoostingClassifier(max_iter=300, max_depth=4, learning_rate=0.05,
                                       l2_regularization=1.0, random_state=7, monotonic_cst=MONO)
    m.fit(train_X, train_y)
    return m


def policy_and_weight(pp, pv, pf):
    """Map (P_position, P_velocity, P_full_state) -> (policy_label, feat_weight)."""
    unc = 1.0 - 2.0 * abs(pf - 0.5)   # 0=confident, 1=on the fence
    if pf >= TAU_HI and pp >= TAU_HI:
        return "keep_static_reliable", W_KEEP, unc
    if pp >= TAU_HI and pv < TAU_LO:
        return "keep_position_lower_weight", W_LOWER, unc
    if pf < TAU_LO and pv < TAU_LO:
        return "reject_high_dynamic", W_REJECT, unc
    if pf < TAU_LO:
        return "suppress_full_state_low", W_SUPPRESS, unc
    return "soft_uncertain", W_SOFT, unc


def main():
    car = F.load_carla(W=5)
    car = car[car["velocity_valid"].notna()].copy()
    car["full_state_valid"] = (car["position_valid"].astype(int) & car["velocity_valid"].astype(int)).astype(int)

    Xall = F.prep(car, F.TCSV_FEATS)
    is_target = np.zeros(len(car), dtype=bool)
    for (t, r) in TARGETS:
        is_target |= (car["town"].astype(str).values == t) & (car["run"].astype(str).values == r)
    tr = ~is_target
    n_tr, n_te = int(tr.sum()), int(is_target.sum())
    print(f"train rows (leave-target-run-out)={n_tr}  score rows (targets)={n_te}")
    if n_te == 0:
        print("ERROR: no target rows found; check town/run values.", file=sys.stderr); sys.exit(2)

    heads = {}
    for lab in ["position_valid", "velocity_valid", "full_state_valid"]:
        y = car[lab].astype(int).values
        heads[lab] = fit_head(Xall[tr], y[tr])
        print(f"  head {lab}: base_rate={y[tr].mean():.3f}")

    te = car[is_target].copy().reset_index(drop=True)
    Xte = Xall[is_target]
    pp = heads["position_valid"].predict_proba(Xte)[:, 1]
    pv = heads["velocity_valid"].predict_proba(Xte)[:, 1]
    pf = heads["full_state_valid"].predict_proba(Xte)[:, 1]

    rows = []
    for i in range(len(te)):
        pol, w, unc = policy_and_weight(float(pp[i]), float(pv[i]), float(pf[i]))
        # bbox: benchmark stores center u,v + bbox_w,bbox_h
        rows.append(dict(
            town=te["town"].iloc[i], run=te["run"].iloc[i],
            frame=int(te["frame"].iloc[i]), track_id=int(te["track_id"].iloc[i]),
            bbox_u=float(te["u"].iloc[i]) if "u" in te else np.nan,
            bbox_v=float(te["v"].iloc[i]) if "v" in te else np.nan,
            bbox_w=float(te["bbox_w"].iloc[i]) if "bbox_w" in te else np.nan,
            bbox_h=float(te["bbox_h"].iloc[i]) if "bbox_h" in te else np.nan,
            P_position_valid=round(float(pp[i]), 4),
            P_velocity_valid=round(float(pv[i]), 4),
            P_full_state_valid=round(float(pf[i]), 4),
            uncertainty=round(float(unc), 4),
            policy=pol, feat_weight=round(float(w), 3),
            model_version=MODEL_VERSION,
        ))
    out = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / "paper2_tcsv_vins_scores.csv"
    out.to_csv(p, index=False)

    # summary
    summ = out.groupby(["run", "policy"]).size().unstack(fill_value=0)
    meta = dict(model_version=MODEL_VERSION, n_train=n_tr, n_score=n_te,
                targets=[f"{t}/{r}" for t, r in TARGETS],
                policy_counts={r: out[out.run == r]["policy"].value_counts().to_dict()
                               for r in out["run"].unique()},
                weight_mean_by_run={r: float(out[out.run == r]["feat_weight"].mean())
                                    for r in out["run"].unique()})
    (OUT / "paper2_tcsv_vins_scores_meta.json").write_text(json.dumps(meta, indent=2))
    print("wrote", p)
    print(summ)
    print("mean feat_weight by run:", meta["weight_mean_by_run"])


if __name__ == "__main__":
    main()
