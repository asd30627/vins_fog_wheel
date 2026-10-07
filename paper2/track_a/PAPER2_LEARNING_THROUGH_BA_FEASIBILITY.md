# PAPER2 Phase 5b — LEARNING-THROUGH-BA FEASIBILITY (assessment, not implemented)

> Should the Part-1 validity model's parameters be trained by backpropagating the VIO localization loss
> through bundle adjustment? Assessment only. Date 2026-07-01.

## What it would require
- **Differentiable BA**: gradients of the VIO estimate (poses) w.r.t. per-feature validity weights, through
  the optimizer. VINS-Fusion uses **Ceres** (C++, non-differentiable w.r.t. hyper-weights) → not available.
  Would need a re-implementation in a differentiable backend (e.g. theseus/PyPose/g2o-torch) or implicit-
  function-theorem gradients through the KKT conditions of BA. Both are large research efforts.
- **A differentiable data path**: images → features → validity net → weights → BA → pose → loss(GT pose).
  Feature extraction/tracking (KLT, non-diff) sits in the middle; typically frozen or replaced.
- **Training data**: many sequences with GT ego trajectory. Currently ~2 clean stable CARLA runs → far too few;
  KITTI is VO-only; nuScenes pending.

## Cheaper equivalents that capture most of the benefit
1. **Frozen validity → soft weighting** (Phase 4): no BA gradients; the validity net (Part-1 TCSV-M) is trained
   on its own selective-validity objective, then used to set factor weights. This is the recommended path.
2. **Outer-loop / black-box search** of the weight-mapping hyperparameters (e.g. w_min, thresholds) against ATE
   on a validation set — derivative-free (CMA-ES / grid), no differentiable BA. Cheap and safe.
3. **Unrolled BA (few iterations)** only if a differentiable backend is adopted later.

## Verdict
**Not warranted now — do NOT implement.** (a) Ceres VINS is not differentiable; (b) frozen validity + soft
weighting (Phase 4) already realizes the available signal without BA gradients; (c) the Phase-1 evidence
(backend already rejects most object features; scale-drift dominates) means the expected payoff of end-to-end
learning is low relative to its very high cost; (d) insufficient clean training sequences. If a localization
result ever justifies it (Paper-3, after fixing data + proving soft weighting ≈ oracle), start with outer-loop
weight search (#2), not full differentiable BA.
