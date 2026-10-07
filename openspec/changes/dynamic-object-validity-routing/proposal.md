# Proposal — Component-wise Dynamic Object Validity for VINS-Aided Navigation

**Change ID:** dynamic-object-validity-routing  
**Branch:** grade-fusion-v1  
**Date:** 2026-07-01  
**Status:** ACTIVE — Phase 1 (CARLA urban-candidate scenario search)

---

## Problem

Dynamic objects corrupt visual-inertial localization and also create uncertainty for downstream planning. Traditional dynamic-object masking treats dynamic objects as uniformly bad — every detected moving object is either fully removed or fully kept, with no distinction between what is valid to use and what is not.

For navigation, this binary treatment is insufficient. The same vehicle that is a dangerous occluder in the visual channel may also be a trackable, well-estimated object useful for planner-facing risk prediction. What is needed is **component-wise validity**:

- **Position validity** — is the estimated position of this object trustworthy?
- **Velocity validity** — is the estimated velocity of this object trustworthy?
- **Full-state validity** — is the joint (position, velocity, orientation) trustworthy?

These three components have different failure modes. An object at the edge of stereo-depth range may have low position validity but detectable, valid velocity from optical flow. An object with occluded view may have good short-term velocity from a tracker but poor position validity. A fresh detection with no tracking history has neither.

## Proposed Change

Introduce an **object-state validity module** that takes raw object detections + tracked states as input and emits per-object, per-component validity scores:

- `P_position_valid ∈ [0,1]`
- `P_velocity_valid ∈ [0,1]`
- `P_full_state_valid ∈ [0,1]`
- `routing_policy ∈ {REJECT, DOWNWEIGHT, ACCEPT}`

The same output goes to **two consumers**:

**A. VINS feature routing / visual factor weighting**  
Objects flagged REJECT are masked in the visual factor; objects flagged DOWNWEIGHT receive soft Huber-compatible feature weighting; objects flagged ACCEPT are treated normally. The goal: remove corrupting visual features from dynamic objects when and only when they are genuinely corrupting.

**B. Planner-facing dynamic object validity interface**  
Per-object validity scores are passed downstream for use in risk assessment, time-to-collision (TTC) estimation, and occupancy prediction. The planner receives: full-state objects, position-only objects, velocity-invalid objects, and invalid objects — each class triggering a different conservative-planning response.

## Title Candidates

1. **Component-wise Dynamic Object Validity for VINS-Aided Navigation**
2. **Validity-Conditioned Dynamic Object Routing for Visual-Inertial Navigation and Planning**

Title 2 is preferred if the planner interface is a first-class contribution; Title 1 if VINS routing is primary.

## Non-Goals (locked)

The following are **explicitly out of scope for this change**. They must not appear in implementation or evaluation without a new change proposal:

- No closed-loop navigation. No planner in the loop. The planner interface is output-only (one-way).
- No dynamic object BA factor. The object state does not enter the bundle adjustment graph.
- No learning-through-BA. No gradient through the VINS solver.
- No FOG full grade grid in this change. Grade is not a primary variable here (it is a confound we must test around).
- No raw_speed masquerading as TCSV-M. `raw_speed` is a baseline-only signal; TCSV-M is the trained classifier.
- No single-run ATE conclusion. Every claim requires median over ≥2 deterministic reps; any result with DET2 variance >3% requires ≥3 reps.
- No Huber-off / cull-off as formal method. These are ablation controls only.
- No nuScenes-as-stereo-VINS-benchmark. nuScenes serves object-validity evaluation only (monocular, different optics).
- No invalid CARLA runs. Runs must pass quality gate (n_vio complete, no divergence, det/frame sufficient, no glued-face).
- No placeholder CSV. All reported numbers must come from real VINS runs on real/simulated data.

## Evidence Status (as of 2026-07-01)

| claim | status | source |
|---|---|---|
| industrial_fog → VISION_ACTIVE (object masking −14%) | **possible signal, one town** | Town01 dense_b1, paper2_repeated_lifegate_dense.csv |
| ideal_imu → VISION_INERT | **confirmed** | Town01, Town06 R6, Town07 R6 |
| Town06 / Town07 R6 → VISION_INERT (both grades) | **confirmed, Phase 2** | PAPER2_LIFE_GATE_PHASE2_RESULTS.md |
| Town06 / Town07 R6 → VINS_READY (late≈2.2, deterministic) | **confirmed** | PAPER2_RERECORDED_VINS_BASELINE_SMOKE.md |
| Town10HD positive replication | **not yet tested** | pending R7 |
| Town02 / Town04 / Town05 life gate signal | **not yet tested** | pending R7 |
| KITTI tracking object validity | **not yet tested** | pending Phase 6+ |
| nuScenes object validity | **not yet tested** | pending Phase 6+ |

## Success Gate

This change is considered successful if, at the end of Phase 5 (vision sensitivity gate):

1. At least **two distinct urban candidate towns** show VISION_ACTIVE under industrial_fog.
2. The masking signal is **object-specific** (all_object/oracle reduces ATE ≥5%; random_control does not).
3. The signal is **repeatable** across ≥2 DET2 runs (Δ between reps < 3%).
4. At least one scenario advances to Phase 6 (TCSV life gate) with explicit gate decision written.

## Failure Gate

This change stops (and paper claim is downgraded to planner/perception-facing validity only) if:

1. No urban candidate town shows VISION_ACTIVE under industrial_fog in Phase 5.
2. Random_control always matches all_object_mask (feature-count artifact, not object-specific).
3. The signal is nondeterministic across reps (variance > ATE change).
