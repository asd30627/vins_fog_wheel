
## Why

In the FOG-aided VINS program (**Framework 2**: learned per-feature covariance *adds on top of* FOG, never replaces it), the currently deployed `reliability_cov.onnx` is **geometry-only** (10 inputs, no motion signal) and deploys **shape-only** anisotropy. An offline diagnostic on CARLA `dynamic_dense` (run01+run02, 1332 dynamic features) established that, after ego-flow subtraction, the per-feature object-motion residual flow is a **strong, directional, stable, deployable** signal:

- magnitude separation dynamic vs static **4.2×** (corr with `obj_speed` r=0.57),
- within-object directional coherence **R=0.997** vs random null 0.47 (excess +0.53),
- cross-frame direction stability **10.3°** vs static **122.5°**.

Dynamic features are corrupted **along a specific image direction (the object's motion)**, not isotropically. The geometry-only net has **no motion input**, so it architecturally cannot orient its anisotropy to that direction. **Route C** adds a motion input so the net can express motion-aligned anisotropy — closing the gap between the physics that exists in the data and what the deployed net can represent.

## What Changes

- **NEW per-feature motion inputs to the covariance net (A+)**: raw optical flow (`vx_j,vy_j` = `FeaturePerFrame.velocity`, normalized coords) + wheel SE(2) motion parts (`w_dx,w_dy,w_dtheta`), on top of existing depth/position. The net **learns the ego-flow subtraction internally** from these cov-independent parts (NOT fed a precomputed `velocity − predict()`, which would be circular = NLL target ÷ dt). All inputs are cov-independent observables → no train/deploy skew. Known limitation: wheel gives yaw only (pitch/roll ego unmodeled; small on KAIST, full angular rate would need FOG).
- **Explicitly NOT using vg/fog cross-modal signals as the motion input** (narrative separation — see design.md): FOG = rotation precision inside IMU preintegration (the moat); cov's motion signal must come from an independent source (visual flow vs ego-motion inconsistency).
- **NLL training target UNCHANGED**: supervision stays the wheel-reference reprojection residual (`ex_norm`, `ey_norm`) already produced by `build_perfeat_window_dataset.py`. No new label design.
- **Net input vector grows 10 → 15 dims** (+5: `vx_j,vy_j,w_dx,w_dy,w_dtheta`) at both train and deploy; `cov_norm.npz` normalization auto-handles new dims; golden-vector parity extended by 5 dims. (PRE-TASK 1 logger only added `vx_j,vy_j`; `w_dx,w_dy,w_dtheta` were already in the perfeat CSV.)
- **Deploy stays env-gated / default-OFF** for bit-invariance; shape-only anisotropy deploy path is retained.
- **PRE-TASK 0 (required, runs FIRST, before any training)**: measure FOG-base run-to-run variance on the corruption trio (urban35/31/36, 5 isolated reps) and use it to fix the concrete corruption-win % threshold. Depends on nothing in Route C; the FOG-base variance is itself a required paper number.
- **PRE-TASK 1 (required)**: regenerate KAIST perfeat training data with a per-feature `velocity` column (currently not logged).
- **PRE-TASK 2 (deferred, not a prerequisite)**: regenerate CARLA dynamic data via the wheel-WS perfeat logger for **mechanism validation only** — done **only after** Route C beats the FOG baseline on KAIST.

## Capabilities

### New Capabilities
- `motion-conditioned-aniso-cov`: per-feature anisotropic covariance prediction conditioned on a deployable, FOG-independent ego-residual-flow motion input, trained with the existing wheel-reference residual NLL target, with hard do-no-harm and corruption-win acceptance gates.

### Modified Capabilities
<!-- None: there is no existing spec in openspec/specs/ whose requirements change. The current geometry-only deploy is an implementation detail, not a previously-specified capability. -->

## Impact

- **C++ estimator** (`vins/src/estimator/estimator.cpp` `computeFeatureReliabilityAnisoLearned` ~3577; the R1 per-feature logger): add motion input to the deploy feats vector and add `velocity`/residual-flow columns to the perfeat CSV. `FeaturePerFrame.velocity` (`feature_manager.h:65`) and the `predict()` lambda (`estimator.cpp:3602-3611`) already exist.
- **Training pipeline** (`dl_reliability_ws/`): `build_perfeat_window_dataset.py` (BASE_COLS + INPUTS), `train_cov_nll.py` + `export_cov_onnx.py` (input dim; follows the existing `--vg/--fog` precedent), `M1_covariance_parity_spec.md` (parity vectors +5 dims).
- **Data**: regenerate KAIST perfeat (8 sequences) with velocity; later regenerate CARLA dynamic via wheel-WS logger (requires wiring `carla_stereo_player` → wheel-WS `vins_node` + a CARLA runner). The OLD CARLA parquets are unusable (`sigma_uv=0`, wrong schema).
- **Evaluation**: FOG-base vs FOG+Route-C on clean (do-no-harm gate) and dynamic-heavy corruption sequences (decisive win). Aligns with `FRAMEWORK2_PLAN.md`.
- **No new sensors**; no change to the FOG/IMU/wheel backbone.
