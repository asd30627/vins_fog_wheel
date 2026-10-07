# PAPER2 Phase 5a — DYNAMIC-OBJECT FACTOR FEASIBILITY (assessment, not implemented)

> Should a reliable dynamic object be modeled as a moving landmark with its own motion factor, rather than
> removed? Assessment only, per instruction. Date 2026-07-01.

## Concept
A confidently-tracked dynamic object should NOT be a static landmark (that biases ego motion). Instead add a
constant-velocity object factor: `object_pos_{t+1} ≈ object_pos_t + v_t·dt`, with the object's observations
constraining a per-object state, and `position_valid`/`velocity_valid` (Part-1) choosing the factor type/weight.

## What the current VINS provides / lacks
- Factors present: `imu_factor`, `projectionTwoFrame*`, `marginalization`, `nhc_factor`, `fog_*` — all
  STATIC-world. No object state, no moving-landmark factor.
- FeatureManager keys features by feature-id, not object-id; no per-object grouping or track association.
- Estimator state = camera/IMU poses + inverse-depth of static features. No object position/velocity states.

## Required changes (large)
1. **Object association**: map detections (track_id, per-frame) to VINS observations; needs a feature↔object
   assignment (via the dynamic mask / bbox membership from Phase 3).
2. **New state**: per-object position (+velocity) in the sliding window; sizeable estimator/marginalization changes.
3. **New factors**: (a) object observation factor (reprojection of object point given object state + ego pose),
   (b) constant-velocity object-motion factor with cov from `velocity_valid`. Both must join the ceres problem
   and the marginalization prior.
4. **Routing (Part-1)**: position_valid & velocity_valid high → full motion factor; position_valid only →
   positional/occupancy constraint but NOT a velocity factor; neither → reject.

## Data sufficiency
- CARLA: GT object pos+vel present (per_instance) → can supervise/eval, and (once recordings are fixed —
  Phase -1/-2/-3) object tracks are available. Current recordings: only ~2 clean stable runs → insufficient.
- KITTI: object tracks (label_02) present but VIO is only stereo-VO (oxts 10 Hz) → weak for object-motion VI.
- nuScenes (downloading): GT object velocity + 6-cam → best future source once ingested.

## Cheaper proxies before full BA change
1. **Pre-BA feature compensation**: shift object features by predicted object motion before treating as static
   (approximate; error-prone).
2. **Pseudo-measurement / post-BA correction**: estimate ego correction from object-consistency residuals after
   BA, outside the optimizer.
3. **Covariance scaling** (Phase 4): the pragmatic middle ground — downweight rather than model.

## Verdict
**Feasible but a major backend program (weeks), not warranted yet.** Gating evidence: (a) recordings must be
fixed and expanded first (Phase -1..-3 show most dynamic runs are currently invalid/low-yield); (b) Phase-1
showed the backend already rejects most object features, so the marginal value of *modeling* objects over
*downweighting* them is unproven; (c) the dominant error is IMU scale-drift, not object pollution. Recommend
proxy #3 (soft weighting, Phase 4) first; pursue a true object factor only if soft weighting proves it matters
AND clean multi-object data (fixed CARLA / nuScenes) is available.
