# PAPER2 — TCSV-M MODEL DEPLOYMENT AUDIT (Phase 2 scoring stage)

> Proves the routing signal used for the VINS ablation is the **real learned TCSV-M(mono)**, per
> detection per frame, leak-free — NOT the raw_speed_gate the prior 'validity_aware' run used.
> Producer: `scripts/paper2_vins_tcsv_masking.py`. Date 2026-07-01.
> Output files live under `paper2/track_a/` (subfolder rule), not repo root.

---

## 1. Model
- **TCSV-M(mono)** = `HistGradientBoostingClassifier(max_iter=300, max_depth=4, lr=0.05, l2=1.0,
  monotonic_cst=MONO)` — the deployment model recommended in `PAPER2_FRAME_VS_SEQUENCE_DECISION.md`
  (per-frame, per-detection, zero track-history latency; statistically tied with TCSV-HistGBM, adds
  interpretable monotone physical priors).
- `MODEL_VERSION = TCSV-M(mono)_hgbm_v1_leaveRunOut`.
- **14 runtime-observable features** (`F.TCSV_FEATS`): 5 geometry (range, bearing, bbox_area, depth,
  det_conf) + 2 temporal-base (track_age, raw_speed) + 7 TCSV temporal-residuals (cv_residual,
  acceleration, jerk, heading-flip count, bbox-depth consistency, position/velocity jitter).
- **Monotone constraints** `MONO = [-1,0,+1,-1,+1,+1,0,-1,-1,-1,-1,+1,-1,-1]`, aligned 1:1 to
  `F.TCSV_FEATS` (asserted in code): farther/deeper/jerkier/flippier ⇒ less valid; bigger bbox /
  higher conf / older track / better bbox-depth agreement ⇒ more valid.
- **Three heads**: `position_valid`, `velocity_valid`, `full_state_valid` (= pos ∧ vel). Base rates
  on training split: 0.379 / 0.108 / 0.065.

## 2. No-GT-at-inference / leakage control
- **Inference features contain NO GT.** `compute_tcsv_features` uses only raw detection columns
  (bbox, depth, raw position/velocity derived from raw detections). GT (`pos_err_m`, `gt_speed_ms`,
  `dir_err_deg`) is used **only** to construct the training LABELS (position_valid/velocity_valid) and,
  separately, the oracle variant — never as a model input.
- **Leave-target-run-out.** The model scoring Town01/dense_b1 + medium_b1 is trained on **all other
  (town,run) rows** (n_train = 21,381), scoring only the 2 targets (n_score = 2,186). The scored runs
  are absent from training → no per-run leakage. (Cross-town generalization caveat from the
  frame-vs-seq doc still applies; in-domain CARLA is the operating regime here.)

## 3. Per-detection output (`paper2_tcsv_vins_scores.csv`)
Columns: `town, run, frame, track_id, bbox_u, bbox_v, bbox_w, bbox_h, P_position_valid,
P_velocity_valid, P_full_state_valid, uncertainty, policy, feat_weight, model_version`.
- `uncertainty = 1 − 2·|P_full_state − 0.5|` (0 = confident, 1 = on the fence).
- `feat_weight ∈ [0,1]` = the soft weight to apply to VINS features inside the bbox (feeds
  `feat_weight_` in the projection factor).

## 4. Routing policy (component-wise, from the multi-label heads)
| condition | policy | feat_weight |
|---|---|---|
| P_full ≥ 0.60 and P_pos ≥ 0.60 | `keep_static_reliable` | 1.00 |
| P_pos ≥ 0.60 and P_vel < 0.40 | `keep_position_lower_weight` (landmark, distrust motion) | 0.60 |
| P_full < 0.40 and P_vel < 0.40 | `reject_high_dynamic` | 0.00 |
| P_full < 0.40 (other) | `suppress_full_state_low` | 0.15 |
| else | `soft_uncertain` | 0.40 |

This realizes the position-vs-velocity **component-wise routing** from the frame-vs-seq decision
(position-valid object usable as a positional landmark even when its velocity is untrustworthy).

## 5. Result on the 2 clean runs (scored, not yet run through VINS)
| run | keep_static | keep_pos_lower | soft | suppress | reject | mean feat_weight |
|---|---|---|---|---|---|---|
| dense_b1 (n=1180) | 7 | 198 | 51 | 59 | 865 | 0.131 |
| medium_b1 (n=1006) | 1 | 337 | 30 | 53 | 585 | 0.222 |

- Reject dominates because most matched detections are distant/dynamic (full_state base rate 6.5%);
  this is a **policy-threshold** choice (TAU_LO=0.40), tunable, documented here so it is not silently
  baked in. For the ablation, `feat_weight` gives the **soft** variant; `policy∈{reject,suppress}`
  gives the **hard-mask** variant.

## 6. What this stage does NOT do (honest scope)
- **No bbox→feature mapping yet.** These are per-object scores. The actual VINS routing needs a
  builder that, per frame, maps each VINS feature pixel to the bbox it falls in and sets its
  `feat_weight_` (soft) or drops it (hard). That builder + the estimator hook is the next step; it is
  where "TCSV-M soft weighting + robust loss" (variant V6) is actually realized. Re-using
  `paper2_carla_stereo_player_masked.py` / `paper2_make_vins_masks.py` for the bbox regions.
- **No VINS run, no ATE here.** Numbers above are label-space, not localization.
- **track_id = −1** rows exist (GT-matched detections without a persistent track id): fine for
  frame-local masking (bbox is present), but they get no temporal-residual history → their TCSV score
  leans on geometry. Flagged, not a blocker.

## 7. Verdict
The routing signal for the VINS ablation is now the **genuine learned TCSV-M(mono)**, per detection,
leak-free, with component-wise position/velocity policy and a soft `feat_weight` — cleanly distinct
from the raw_speed_gate. Ready to feed the mask/weight builder for variants V5 (hard) and V6 (soft)
in `PAPER2_TCSV_HUBER_ABLATION_PLAN.md`. The bbox→feature builder + estimator injection is the
remaining gated step before any ATE can be claimed.
