# PAPER2 Phase 3 — FEATURE-TRACKER ROUTING DESIGN (not image blur)

> Move dynamic-object suppression from the player's image-blur side effect to the VINS **feature tracker**,
> where features are actually born and tracked. Design + minimal patch, grounded in the real source. Date 2026-07-01.

## Why (from Phase 1)
Image-blur suppression is indirect: boundary corners survive, blurred regions still yield weak corners, and
VINS already rejects ~most object features in the backend (baseline outlier ratio ~0.5–0.9). We need to
(a) never CREATE features on dynamic objects and (b) DROP existing tracked features that drift onto them.

## Where to hook (verified source)
`src/VINS-Fusion-ROS2-jazzy/vins/src/featureTracker/feature_tracker.cpp`:
- `FeatureTracker::setMask()` (line 55): builds `mask` (CV_8UC1, 255=allow); already draws MIN_DIST circles
  for spacing. `cv::goodFeaturesToTrack(cur_img, ..., mask)` (line 289/307) only extracts where mask==255.
  **Hook A** — subtract dynamic-object bboxes from `mask` (set to 0) → zero NEW features on objects.
- `FeatureTracker::trackImage()` (line 104): KLT-tracks `prev_pts→cur_pts`. **Hook B** — after tracking,
  cull `cur_pts/ids/track_cnt` whose points fall inside a dynamic bbox → drop features that drifted onto objects.
- Note `rejectWithF()` is **disabled** (line 271) — so the frontend currently does NO geometric rejection;
  routing here is additive, not redundant.

## Minimal patch
1. **Input path**: add per-frame dynamic-region info to the tracker. Two options:
   - (pref) a new ROS topic `/carla/dynamic_mask` (mono8, 255=dynamic) published by the player alongside the
     image; `trackImage(cur_time, img0, img1, mask_dyn)` gains an optional arg. Player already has the bboxes.
   - (simpler, offline) a per-run JSON `{frame:[bboxes]}` loaded by the tracker via env `REL_DYN_MASK_JSON`,
     keyed by image sequence index. No new topic/message.
2. **feature_tracker.h**: add `cv::Mat dyn_mask;` + `void setDynamicMask(const cv::Mat&);`.
3. **setMask()**: after building `mask`, `if(!dyn_mask.empty()) mask.setTo(0, dyn_mask);` (Hook A).
4. **trackImage()**: after KLT + `reduceVector`, add a pass removing points where `dyn_mask.at<uchar>(pt)>0`
   (Hook B), using the same `reduceVector` idiom already in the file.
5. **Env gate**: `REL_FEATURE_ROUTING=1` (default off) → byte-identical to baseline when off.

## Metrics to log (per keyframe → reliability CSV)
- baseline feature count (raw + mgr), object-region feature count (points inside dyn bbox before culling),
  rejected feature count (Hook A skipped + Hook B culled), surviving feature count,
- backend outlier count / ratio (already logged: admission-debug), reprojection residual (opt-cost),
- final ATE/RPE via `paper2_vins_metrics.py`.

## Risks
- Time-sync: the JSON/topic must align to the exact image frame (use the player's frame index / ts).
- Over-culling on degraded baselines (same Town07-style risk as blur) → pair with a stability gate (Phase 4).
- KLT features that are *partly* on an object: use bbox-center test + small erosion to avoid over-culling edges.
- Recompile required (`colcon build --packages-select vins`); ~minutes.

## Expected value
Cleaner, measurable suppression + exact object-region feature counts (which blur cannot give). But note the
Phase-1 ceiling: the backend already rejects most object features, so the net ATE gain is likely still modest
on stable baselines. Worth doing mainly to (a) measure the effect precisely and (b) enable soft weighting (Phase 4).
