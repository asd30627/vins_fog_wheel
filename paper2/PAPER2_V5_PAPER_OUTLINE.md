# PAPER2 v5 — PAPER OUTLINE

> Observability-Aware Dynamic Object State Validity for GPS-Denied Navigation. Outline for a mid-tier
> measurement+methodology paper. Honest contribution spine = C1 (phenomenon+regime map) + C3 (validity/refusal layer).

## Title (candidates)
- "When Not to Trust a Moving Object: Observability-Aware State Validity for GPS-Denied Navigation"
- "Position-or-Velocity? An Observability-Aware Validity Layer for Dynamic Object State in GPS-Denied Navigation"

## Abstract (core message)
Dynamic-object perception usually estimates a full object state (position + velocity) regardless of geometry.
We show that under common GPS-denied road geometries, object **velocity** (and sometimes full state) is
frequently weakly observable — robustly across thresholds. We separate **position** and **velocity** validity,
map the road-geometry regimes where each holds, and propose an **observability-aware validity layer** that
emits full-state / position-only / invalid-velocity / unobservable / conservative-warning. We evaluate at the
**decision level** (overconfident-wrong-velocity, invalid-velocity recall, false-refusal, planner-usable),
showing the layer sharply cuts overconfident wrong-velocity vs always-estimating. We position against
observability-gated VI object estimation (Qiu et al. 2018), dynamic SLAM, and selective prediction.

## 1. Introduction
- Problem: GPS-denied dynamic-object state; perception "estimates-and-hopes".
- Observation: velocity unobservable in common geometries (static/following/far) → wrong velocity is dangerous.
- Contributions (honest): (C1) road-regime **validity phase map** + the velocity-unobservability phenomenon
  (robust); (C3) a **multi-class refusal/validity layer** + **decision-level evaluation**; (C2, minor)
  an interpretable observability index (OVI) — marginal over distance, reported honestly.
- Explicit non-claims: not first to notice object unobservability (Qiu 2018); not dynamic SLAM / object factor;
  not VINS-quality conditioning (a tested negative); not conformal risk tube.

## 2. Related Work & Claim Boundary  (see PAPER2_V5_LITERATURE_POSITIONING.md)
- Observability-gated object VI estimation: **Qiu et al., IROS 2018** (closest) — single-object scalar
  observability threshold, binary keep/keep-up-to-scale. **We differ**: regime phase map, position/velocity
  separation, 5-way refusal, decision-level evaluation.
- Bearings-only TMA (Nardone & Aidala 1981): theoretical root of velocity unobservability (cite as foundation).
- Dynamic SLAM (VDO-SLAM, DynaSLAM II, ClusterVO, DOT-SLAM): always output object velocity, never gate.
- Selective prediction (SelectiveNet, ICML 2019; risk-coverage): borrow the abstain frame, not the novelty.
- Task-aware risk (Antonante, RSS 2023): task-relevance of failures, complementary.
- Conformal risk tube (Fu & Chen, ICRA 2026); 3D-MOT uncertainty (Gaussian-YOLO, BayesOD, MonoRUn):
  uncertainty/risk scoring, not geometric state-validity decisions.

## 3. Problem Formulation
- object state = (position, velocity) in ego/body frame; observability of each under road geometry.
- validity definitions (position_valid / velocity_valid / full / position_only / invalid / unobservable);
  thresholds stated + ablatable.

## 4. Observability/Validity Phase Map (C1)
- raw object estimation pipeline (YOLO + stereo SGBM depth + ByteTrack + ego-comp); GT-matched errors.
- validity vs distance/density/bearing-change/depth-quality; **velocity collapses, position degrades slower**.
- **threshold robustness (27/27)** → the phenomenon is not threshold-tuned.
- Fig: validity-by-distance; phase-map heatmaps.

## 5. Observability Validity Index (C2, interpretable, minor)
- geometric terms (range, yaw_lever=range·sin(yaw_sigma), bearing_change_rate, depth_noise, vel_obs_proxy).
- HONEST result: marginal gain over distance overall (+0.008 AUROC); helps only in mid-range (15-30m);
  presented as an interpretable auxiliary, with the ablation shown (not hidden).
- Fig: OVI vs distance within-bin AUROC.

## 6. Refusal-Aware Validity Layer (C3)
- policy levels + decision-level metrics.
- LAYER cuts overconfident-wrong-velocity 0.84 → ~0.6 while retaining velocity; position_only is ~38%.
- trade-off curve: observability-aware refusal ≫ no-policy; a simple distance/geometry gate already
  realizes most of the gain (honest — you don't need a heavy model).
- Fig: refusal trade-off curve.

## 7. Experiments
- dataset: CARLA dynamic_v3 (24 runs, 2 towns × 3 densities × 4 routes; 15.8k GT-matched detections).
- [NEEDED] real-data validation: KITTI tracking (now downloaded) — show the velocity-unobservability
  phenomenon + validity layer generalize to real data.
- ablations: validity thresholds; OVI terms; refusal operating points.

## 8. Limitations & Honest Negatives
- raw velocity = centroid-diff (noisy); a cleaner estimator (flow) ablation is future work.
- VINS-quality conditioning (v4 A2): tested, did NOT help (reported, not hidden).
- object-consistency ego diagnostic (C4): NULL in this data (reported, not packaged).
- 2 towns; CARLA domain; VINS scale-divergence artifact in yaw_sigma proxy.

## 9. Conclusion
- decide-then-estimate, not estimate-and-hope; separate position/velocity validity; refuse when unobservable.

## Figures (have / need)
- HAVE: fig_v5_validity_by_distance, fig_v5_phase_map, fig_v5_ovi_within_bin, fig_v5_refusal_tradeoff.
- NEED: KITTI-vs-CARLA validity comparison; per-scenario (car-following/lateral-crossing/occlusion) validity;
  qualitative failure gallery (far object fake velocity); missed-danger curve.

## Tables (have / need)
- HAVE: validity by bin/density/town; threshold-robustness; OVI ablation; refusal policy + trade-off; claim-boundary.
- NEED: per-regime validity; real-data (KITTI) validity; cleaner-velocity-estimator ablation.
