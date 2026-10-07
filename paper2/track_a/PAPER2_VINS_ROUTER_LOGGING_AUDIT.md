# PAPER2 Phase B — VINS ROUTER LOGGING AUDIT (logging only, VINS output unchanged)

> Does VINS already remove dynamic-object features, and is there operable feature mass for TCSV-M to
> route? Correlates per-keyframe VINS feature pixels (perfeat log, DET2, same 640x480 space) with
> detected object bboxes + TCSV-M validity. NO VINS result changed. Producer:
> `scripts/paper2_vins_router_logging.py` → `paper2_vins_router_logging.csv`. Run: Town01 dense_b1.
> Date 2026-07-01.

---

## 1. Setup
- Feature pixels: `perfeat` CSV (`u_j,v_j`, one row per tracked feature per keyframe), written AFTER
  the 3-px cull → the ON run = survivors; a second run with `REL_BACKEND_OUTLIER_CULL=0` = pre-cull.
- Object bboxes: `paper2_raw_object_benchmark_all_with_vins.csv` (u,v CENTER + bbox_w/h), matched dets.
- TCSV-M validity + policy: `paper2_tcsv_vins_scores.csv` (real TCSV-M(mono), per matched track).
- All in the shared 640x480 image frame (verified: rec + VINS cam0 both 640x480; bbox max_u=630).
- Deterministic DET2 replay; 519 keyframes; ~171 surviving feats/keyframe (median), 38 in-object.

## 2. Results (dense_b1, 519 keyframes, 92,476 surviving feats)

| quantity | count | % of surviving feats |
|---|---|---|
| surviving VINS features (cull ON) | 92,476 | 100% |
| **in ANY detected object bbox** | **34,027** | **36.8%** |
| in TCSV-low-validity bbox (P_full<0.4 or reject/suppress) | 3,774 | 4.1% |
| TCSV would DROP (reject+suppress bbox feats, scored) | 2,378 | 2.6% |
| 3-px cull removed from object bboxes (in-bbox_off − in-bbox_on) | 6,578 | 16.2% of pre-cull in-bbox |

TCSV feature-action distribution (features falling in a TCSV-SCORED bbox):
| action | feats | % |
|---|---|---|
| keep_static_reliable | 67 | 0.1% |
| keep_position_lower_weight | 918 | 1.0% |
| soft_uncertain | 277 | 0.3% |
| suppress_full_state_low | 257 | 0.3% |
| reject_high_dynamic | 2,121 | 2.3% |
| (background — not in any bbox) | 58,449 | 63.2% |

## 3. The three questions Phase B was built to answer

### Q. Does VINS already remove dynamic-object features?
**No — only partially.** The 3-px backend cull removes just **16.2%** of the features that sit inside
object bboxes; **~84% of object-region features survive** into the optimization. So the earlier claim
"the frontend already rejects the vast majority of dynamic features" is **false** — a large majority of
object-region features are retained. There IS object-feature mass in the estimator.

### Q. Is there operable feature mass for TCSV-M?
**Yes in raw count, but small as a fraction, and with a coverage gap.**
- 36.8% of surviving features are on objects — plenty in absolute terms.
- BUT TCSV would actually DROP only **2.6%** of all features (reject+suppress), and act (any non-keep) on
  ~3.9%. So TCSV's deployable footprint is a **small slice** of the feature set.
- **Coverage gap (honest):** of the 34,027 in-object features, only ~3,640 (≈11%) fall in a
  TCSV-*scored* bbox; the remaining ~30k fall in bboxes whose detection had **no persistent track_id
  (track_id = −1) or was otherwise unscored**, so TCSV cannot route them. Per-track TCSV scoring does
  not cover all detections at deploy → real coverage is partial. This must be stated: TCSV-M can only
  route the subset of object-region features attached to a scored track.

### Q. If TCSV routed, how much would it change?
**Very little is even eligible.** Even a hard TCSV mask removes ~2.6% of features; a soft weight touches
~3.9%. Combined with Phase A (removing ~2/3 of ALL features via cull-off changed ATE only chaotically by
≤0.33 m), routing 2–4% of features cannot be expected to move ATE beyond the noise/chaos floor on these
ideal-IMU runs.

## 4. Verdict (Phase B)
There is real object-region feature mass (36.8% of features on objects; the cull leaves ~84% of them),
so the "frontend already cleans dynamics" story is wrong. **But** TCSV-M's deployable action covers only
~2.6–3.9% of features (and only ~11% of in-object features are even TCSV-scored, due to the track_id
coverage gap). Given Phase A (visual channel is ATE-inert under ideal IMU; cull of 2/3 of features barely
moved ATE), routing this small, partially-covered slice is **not expected to produce a measurable,
consistent VINS ATE change** on these runs. The signal remains **object-state validity**, not localization.
