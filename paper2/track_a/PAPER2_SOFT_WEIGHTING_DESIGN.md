# PAPER2 Phase 4 — SOFT WEIGHTING / COVARIANCE SCALING DESIGN

> Instead of binary removal (which hurt on degraded baselines, e.g. Town07), downweight visual factors on
> low-validity objects: weight = f(P_valid). Design grounded in the real estimator. Date 2026-07-01.

## The existing hook (verified — repo already has a GLOBAL visual weight)
`estimator/estimator.cpp`:
- `visual_alpha = selectVisualAlpha()` (line 480) — a scalar visual weight (REL_* learned-reliability net /
  admission-weight machinery; logged as `[admission-weight] alpha=…`).
- `ProjectionTwoFrameOneCamFactor::sqrt_info = weighted_sqrt_info` (lines 627/686/846) where
  `weighted_sqrt_info = visual_alpha * sqrt_info`. So the visual factor's information matrix is ALREADY
  scaled — but **globally** (one α for all features this update), via a STATIC class member.

## What Phase 4 changes: global α → per-object (per-feature) weight
The limitation: `sqrt_info` is a static class member, so all projection residuals in an update share one α.
To weight by object validity we need a **per-observation** weight w_f = g(P_valid(object(f))):
- **Option A (minimal, per-update multiplicative field):** keep the global α but multiply it by the median
  validity of features in the current frame — crude, cheap, no per-feature change. Low fidelity.
- **Option B (proper, per-feature):** give each `ProjectionTwoFrameOneCamFactor` instance its own weight.
  Add a `double w` member set at construction from the feature's object validity, and scale the residual/
  jacobian by `w` inside `Evaluate()` (multiply the mapped `sqrt_info` by `w`). Requires threading a
  per-feature validity value from `f_manager` (FeatureManager) into the factor at
  `problem.AddResidualBlock(...)` time. Feature→object association via the dynamic mask / track id.

## Weight mapping (choices, ablatable)
- w = 1.0 for validity high (reliable static);
- w = clamp(P_valid, w_min, 1.0), w_min≈0.1, for uncertain → lower confidence, NOT full reject;
- w = 0 (or w_min) for confidently-dynamic (P_valid low AND observably moving).
- Covariance interpretation: information ∝ w² (since sqrt_info scales the residual). So w=0.3 ⇒ 9× larger cov.

## Files to touch
- `factor/projectionTwoFrameOneCamFactor.{h,cpp}` (+ TwoFrameTwoCam, OneFrameTwoCam): add `w`, apply in Evaluate.
- `estimator/estimator.cpp` optimization(): at each `AddResidualBlock` for a feature, pass its validity-derived w
  (look up from a `map<feature_id,double>` built from the dynamic mask / TCSV-M score).
- `estimator/feature_manager.*`: carry per-feature object id / validity if not already present.
- Env gate `REL_SOFT_VALIDITY_WEIGHT=1` (default off).

## Comparison plan (once implemented, on CLEAN core runs only)
baseline · binary all_dynamic · binary validity · **soft weighting (this)** · oracle. Metrics: ATE_rmse,
RPE, early/late scale, VINS failures, feature/object-feature/rejected counts, outlier ratio, reproj cost.

## Hypothesis
Soft weighting should **avoid the Town07-style regression** (never fully starves VINS — worst case just
downweights), i.e. strictly safer than binary removal, at the cost of a smaller best-case gain. If it does
NOT beat baseline on stable runs, report honestly that per-feature validity weighting adds nothing beyond the
backend's existing outlier rejection.

## Note
This is the natural next mechanism AFTER Phase 3 (which supplies the per-feature object association). Given
the Phase-1 finding that the backend already rejects most object features, expected gains are modest; the main
value is ROBUSTNESS (no catastrophic starvation) rather than raw ATE.
