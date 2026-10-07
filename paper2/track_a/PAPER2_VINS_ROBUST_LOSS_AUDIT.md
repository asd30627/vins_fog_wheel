# PAPER2 — VINS ROBUST-LOSS / HUBER AUDIT (source-of-truth)

> Where every robust / outlier mechanism lives in this VINS-Fusion tree, so that TCSV soft
> weighting is NEVER claimed as a TCSV effect when it is really the pre-existing Huber /
> backend outlier rejection doing the work. All line numbers are from
> `src/VINS-Fusion-ROS2-jazzy/vins/`. Date 2026-07-01. Read-only audit — no code changed here.

---

## 0. TL;DR (the honest one-liner)

This VINS has **three** robust mechanisms on the visual channel, not one:

1. **Huber(δ=1.0)** on the visual reprojection residual (M-estimator, in the Ceres cost).
2. **Backend reprojection outlier rejection** — a HARD post-optimization cull at **mean reproj > 3 px** (`outliersRejection`). This is the dominant one; it is what `outlier_ratio_last` counts.
3. **A per-feature weight hook `feat_weight_` / `sqrt_info_inst_`** already wired into every projection factor (default 1.0 = bit-identical). **This is exactly the slot TCSV soft weighting plugs into — and it is applied BEFORE Huber.**

The **frontend** F-matrix RANSAC (`rejectWithF()`) is **commented out** — it does NOT run during tracking. So the earlier claim (masking-limitation audit §3.2) that "the frontend already rejects ~0.9 of features via RANSAC/F-threshold" is **inaccurate on two counts**: the rejection is *backend reprojection-based*, not frontend RANSAC, and the measured ratio is ~0.33–0.52, not 0.9.

TCSV soft weighting will **overlap most with mechanism #2** (both remove/down-weight the same high-reproj dynamic-object features) and will **interact multiplicatively with mechanism #1** (see the interaction doc). It does NOT touch IMU / marginalization / wheel / FOG factors.

---

## 1. Does the visual reprojection factor use Huber / Cauchy / a LossFunction?

**Yes — Huber, δ=1.0 by default.** `estimator.cpp:2416-2427`:

```cpp
ceres::LossFunction *loss_function;
// REL_HUBER_DELTA (env, default 1.0): >0 -> HuberLoss(delta); <=0 -> NULL (no robust loss).
static const double REL_HUBER_DELTA = [](){ const char* e=std::getenv("REL_HUBER_DELTA"); return e?std::atof(e):1.0; }();
loss_function = (REL_HUBER_DELTA > 0.0) ? new ceres::HuberLoss(REL_HUBER_DELTA) : (ceres::LossFunction*)NULL;
//loss_function = new ceres::CauchyLoss(1.0 / FOCAL_LENGTH);   // available but disabled
```

- Cauchy exists as a commented alternative; **Huber is the live one**.
- A visual-only knob **already exists**: `REL_HUBER_DELTA` (env). `>0` → Huber(δ); `<=0` → NULL. Default 1.0 is bit-identical to the gate binary. (§ Q-implement below builds a clearer `REL_VISUAL_ROBUST_LOSS` alias on top of this.)

## 2. Which file / function adds Huber to the Ceres problem?

`Estimator::optimization()` in `estimator.cpp`. The visual residual blocks:

| factor | line | loss arg | δ |
|---|---|---|---|
| mono `ProjectionTwoFrameOneCamFactor` (f_td) | `estimator.cpp:2668` | `loss_function` | Huber 1.0 |
| stereo `ProjectionTwoFrameTwoCamFactor` | `estimator.cpp:2680` | `stereo_loss` | Huber 1.0* |
| stereo `ProjectionOneFrameTwoCamFactor` | `estimator.cpp:2688` | `stereo_loss` | Huber 1.0* |

`*stereo_loss = stereo_robust_off ? NULL : loss_function` (`estimator.cpp:2476`). `stereo_robust_off` is only set by diagnostic envs (`VINS_STEREO_NO_ROBUST_FIRST_N`, `DEBUG_DISABLE_STEREO_ROBUST_LOSS`); default = same Huber as mono.

The visual reprojection Huber is **also re-added into the marginalization** at `estimator.cpp:2943` (`f_td` with `loss_function`), so the loss survives into the prior. Turning Huber off (below) affects the current-window residual; the marginalized prior of already-dropped frames keeps whatever loss was active when they were marginalized.

## 3. Does every residual block use the same loss?

**No.** Loss per factor type:

| factor | file / line | loss |
|---|---|---|
| visual mono | `estimator.cpp:2668` | **Huber(1.0)** |
| visual stereo | `estimator.cpp:2680,2688` | **Huber(1.0)** (stereo_loss) |
| IMU pre-integration | `estimator.cpp:2538` | **NULL** (no robust loss) |
| marginalization prior | `estimator.cpp:2516` | **NULL** |
| wheel SE2 | `estimator.cpp:2587,2901` | `HuberLoss(wheel_huber_)` (separate δ) |
| wheel forward | `estimator.cpp:2611` | NULL |
| FOG yaw | `estimator.cpp:2625` | NULL |
| NHC | `estimator.cpp:2636` | NULL |

→ **A visual-Huber switch is clean**: it cannot touch IMU (NULL), marginalization (NULL), wheel (own Huber), FOG/NHC (NULL). This is what makes REL_VISUAL_ROBUST_LOSS safe.

## 4. Is there a global visual_alpha / weighted sqrt_info?

**Yes, two layers, both live but default-neutral on these CARLA runs:**

- **Global visual admission weight** `visual_alpha` / `visual_w_pred`: `applyVisualResidualWeight()` (`estimator.cpp:1775`) scales the whole visual channel by a predicted admission weight. On the CARLA runs α=1 (neutral) per the stereo-diag comments (`estimator.cpp:2433`).
- **Per-feature weight** `feat_weight_` and per-feature anisotropic whitener `sqrt_info_inst_`: filled by `computeFeatureReliability()` into `feat_weight_cur_[fid]` (`estimator.cpp:2412-2413`, `estimator.h:327`), applied inside each projection factor's `Evaluate()`. Default `feat_weight_ = 1.0` → bit-identical. **This is the R3 / Route-C reliability slot and is exactly where TCSV per-object weights would be injected.**

The default whitening is `sqrt_info = FOCAL_LENGTH / 1.5` (isotropic). `feat_weight_` multiplies that whitened residual (see Q5 / interaction doc).

## 5. Is there outlier rejection?

**Yes — backend, hard, reprojection-based.** `outliersRejection()` (`estimator.cpp:3281-3339`), called every keyframe at `estimator.cpp:1789`:

```cpp
double ave_err = err / errCnt;               // mean reproj over all observations of the feature
if (ave_err * FOCAL_LENGTH > 3)              // > 3 px  -> outlier
    removeIndex.insert(it_per_id.feature_id);
```

Then `f_manager.removeOutlier(removeIndex)` (`estimator.cpp:1790`) and, single-thread only, `featureTracker.removeOutliers` (`estimator.cpp:1793`). Threshold is a fixed **3 px** mean reprojection error; features with ≥4 observations only.

`outlier_ratio_last = |removeIndex| / tracked_feature_count_mgr` (`estimator.cpp:874-884`). This is what the CSV logs — **it is the fraction culled by the 3-px rule, NOT a RANSAC ratio.**

## 6. Frontend or backend?

**Backend.** The only outlier rejection that runs online is `outliersRejection` in the estimator (backend), after `optimization()`. There is **no** frontend rejection during tracking (see Q7). `findFundamentalMat` appears only in **initialization** (`solve_5pts.cpp:215`, `initial_ex_rotation.cpp:90`) — not in the steady-state feature pipeline.

## 7. Is FeatureTracker::rejectWithF() enabled?

**No — it is commented out.** `feature_tracker.cpp:269-271`:

```cpp
if (1)
{
    //rejectWithF();          // <-- DISABLED
    ROS_DEBUG("set mask begins");
    setMask();
```

`rejectWithF()` is defined (`feature_tracker.cpp:501`, uses `cv::findFundamentalMat(..., FM_RANSAC, F_THRESHOLD, 0.99, status)`) and `F_THRESHOLD` is loaded from config (`parameters.cpp:198`), but the call site is disabled. **Frontend F-RANSAC does not run.** Correction to prior docs: the "frontend already rejects most features" story is wrong; the culling is the backend 3-px rule.

## 8. What columns in vins.log / reliability_features_vins.csv are usable?

From `reliability_logger.h` header (`~L490-540`) + the `[admission-debug]` ROS log line (`estimator.cpp:1821-1831`):

| need | column / log token | source |
|---|---|---|
| feature count (raw) | `tracked_feature_count_raw` / log `raw=` | `image.size()` |
| feature count (manager) | `tracked_feature_count_mgr` / log `mgr=` | `f_manager.getFeatureCount()` |
| **outlier ratio** | `outlier_ratio_last` / log `ratio=` | 3-px cull / mgr |
| outlier count | `outlier_count_last` / log `outlier=` | `|removeIndex|` |
| inlier count | `inlier_count_last` / log `inlier=` | mgr − outlier |
| reprojection cost | — (not logged directly) | derivable: rebuild per-feature `reprojectionError`, or read Ceres `final_cost` |
| solver cost | `solver_time_ms_last` / log `solver costs: X [ms]` | `TicToc` |
| visual alpha | `visual_alpha` / log `alpha=` | admission weight |
| visual weight | `visual_w_pred` / log `w=` | admission weight |
| failure count | `failure_detected_last` / `vins_failure` / log `fail=` | `failureDetection()` |
| coverage / entropy | `coverage_8x8`, `feature_entropy_8x8` | spatial spread |
| est pose / vel / bias | `est_p_*`, `est_q_*`, `vel_norm`, `ba_norm`, `bg_norm` | state |

**Not currently logged, needed for the interaction study (see interaction doc):**
- **Huber saturation ratio** (fraction of visual residuals with whitened ‖r‖ > δ, i.e. in the linear/robust arm). Requires a new per-residual probe or reading `ρ'` from the loss. → instrument or derive from residual dump.
- **Ceres reprojection / final cost** per optimization (`summary.final_cost`) — one line to add if needed.

---

## Conclusions

**Robust mechanisms VINS already has (visual channel):**
1. Huber(δ=1.0) M-estimator on mono+stereo reprojection (soft, down-weights large residuals).
2. Backend hard cull at mean reproj > 3 px (`outliersRejection`) — the dominant, discrete one.
3. Per-feature `feat_weight_` / `sqrt_info_inst_` slot (currently 1.0) + global `visual_alpha` (currently 1.0).

**Where TCSV soft weighting overlaps:**
- **Strongest overlap = mechanism #2 (3-px cull).** Dynamic-object features are exactly the ones with high reproj that the 3-px rule already deletes. This is why prior input-masking gave only a small net ATE change: the estimator was culling most of those features anyway. TCSV down-weighting acts on the *same population*.
- **Multiplicative interaction with mechanism #1 (Huber).** TCSV weight enters as `feat_weight_` **before** Huber (`residual *= feat_weight_` inside `Evaluate`), so a small TCSV weight shrinks the residual and pushes a feature *out* of Huber's robust arm — TCSV and Huber are not additive. Full analysis in `PAPER2_TCSV_SOFT_WEIGHTING_HUBER_INTERACTION.md`.
- **No overlap** with IMU / marginalization / wheel / FOG (different or NULL loss).

**Where ablation is required (to de-confound):**
1. **Huber on vs off** (`REL_VISUAL_ROBUST_LOSS` / `REL_HUBER_DELTA<=0`) with TCSV off — measures Huber's standalone strength.
2. **3-px backend cull on vs off** would be the cleaner de-confounder, but the user's matrix does not request it; note it as the dominant confounder. (`outliersRejection` has a `//return;` at `estimator.cpp:3283` that could disable it — flagged, not used.)
3. **TCSV weighting × Huber**: 2×2 (TCSV {off, soft} × Huber {on, off}) is the minimum to separate "TCSV helps" from "Huber already did it".
4. **TCSV vs raw_speed_gate vs all_dynamic vs oracle** at fixed Huber-on — separates the learned signal from crude dynamic removal.

**Bottom line:** any ATE improvement measured with Huber-on AND the 3-px cull active is a *combined* effect. To claim "TCSV improves VINS localization" we must show TCSV adds ATE benefit **beyond** what Huber + the 3-px cull already deliver on the same features. The ablation plan (`PAPER2_TCSV_HUBER_ABLATION_PLAN.md`) is built to answer exactly that.
