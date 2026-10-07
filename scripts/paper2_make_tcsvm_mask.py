#!/usr/bin/env python3
"""Build the LEARNED TCSV-M mask JSON from the leave-run-out TCSV-M scores.

Repair for claim J: the prior 'validity_aware' mask was a raw_speed gate. This builder consumes the
already-produced, leak-free learned scores (paper2/track_a/paper2_tcsv_vins_scores.csv, leave-run-out
HGBM, model_version TCSV-M(mono)_hgbm_v1_leaveRunOut) and emits a hard-reject mask in the SAME
{frame:[[x0,y0,x1,y1],...]} format as scripts/paper2_make_vins_masks.py, so it plugs into the existing
VINS replay runner (paper2_vins_run_one.sh via MASK_JSON) with zero other changes.

Hard-reject = policies the learned model assigns to unreliable detections:
  reject_high_dynamic, suppress_full_state_low
(the two 'remove this detection' policies; keep_position_lower_weight / soft_uncertain /
keep_static_reliable are NOT hard-masked — soft weighting needs an estimator hook that does not exist).

Usage:
  python3 scripts/paper2_make_tcsvm_mask.py \
      --scores paper2/track_a/paper2_tcsv_vins_scores.csv \
      --run Town01__dynamic_v3__rundense_b1 --town Town01 --runtag dense_b1 \
      --out-dir /mnt/sata4t/ivlab3_data/fwvio/results/paper2_vinsaware/_masks
"""
import argparse, json, os
import pandas as pd

HARD_REJECT = {"reject_high_dynamic", "suppress_full_state_low"}


def boxes_from(df):
    out = {}
    for _, r in df.iterrows():
        u, v, w, h = r["bbox_u"], r["bbox_v"], r["bbox_w"], r["bbox_h"]
        x0, y0, x1, y1 = u - w / 2, v - h / 2, u + w / 2, v + h / 2
        out.setdefault(int(r["frame"]), []).append(
            [round(float(x0), 1), round(float(y0), 1), round(float(x1), 1), round(float(y1), 1)])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scores", default="paper2/track_a/paper2_tcsv_vins_scores.csv")
    ap.add_argument("--run", required=True, help="full run name for output file, e.g. Town01__dynamic_v3__rundense_b1")
    ap.add_argument("--town", required=True)
    ap.add_argument("--runtag", required=True, help="matches 'run' column in scores CSV, e.g. dense_b1")
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args()

    df = pd.read_csv(a.scores)
    sub = df[(df["town"] == a.town) & (df["run"] == a.runtag)].copy()
    if len(sub) == 0:
        raise SystemExit(f"no rows for town={a.town} run={a.runtag} in {a.scores}")

    hard = sub[sub["policy"].isin(HARD_REJECT)].copy()
    bx = boxes_from(hard)

    os.makedirs(a.out_dir, exist_ok=True)
    outp = os.path.join(a.out_dir, f"mask_{a.run}__tcsvm.json")
    with open(outp, "w") as f:
        json.dump(bx, f)

    nb = sum(len(v) for v in bx.values())
    policy_counts = sub["policy"].value_counts().to_dict()
    print(f"[tcsvm-mask] run={a.run}")
    print(f"  total scored dets={len(sub)}  hard-reject dets={len(hard)}  frames masked={len(bx)}  boxes={nb}")
    print(f"  policy counts: {policy_counts}")
    print(f"  -> {outp}")


if __name__ == "__main__":
    main()
