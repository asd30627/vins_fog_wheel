# PAPER2 OpenSpec Summary — Component-wise Dynamic Object Validity for VINS-Aided Navigation

> OpenSpec change: `openspec/changes/dynamic-object-validity-routing/`  
> Branch: grade-fusion-v1  
> Date: 2026-07-01  
> Status: ACTIVE — Phase 1–3 COMPLETE; VISION_INERT (all towns); awaiting Option A/B/C decision

---

## Title

**Component-wise Dynamic Object Validity for VINS-Aided Navigation**

(Alt: *Validity-Conditioned Dynamic Object Routing for Visual-Inertial Navigation and Planning*)

---

## Core Thesis

TCSV-M is not the whole paper. TCSV-M is one implementation of a component-wise object-state validity estimator. The paper's three contributions are:

1. **Component-wise object-state validity** — decomposing object validity into position validity, velocity validity, and full-state validity, with independent failure modes.

2. **Validity-conditioned VINS dynamic feature routing / soft weighting** — using the validity scores to selectively suppress corrupting visual features from dynamic objects in the VINS pipeline.

3. **Planner-facing dynamic object validity interface** — passing per-object validity classes to downstream planning for risk-aware TTC, occupancy, and conservative decision-making.

---

## Non-Goals (frozen)

These are out of scope for this change. Violating any requires a new change proposal:

| non-goal | reason |
|---|---|
| Closed-loop navigation | not a navigation system change |
| Dynamic object BA factor | no object state in factor graph |
| Learning-through-BA | no gradient through VINS solver |
| FOG full grade grid | grade is a confound here, not a primary variable |
| raw_speed as TCSV-M | raw_speed is a baseline signal only |
| Single-run ATE conclusion | always median ≥2 DET2 reps |
| Huber-off / cull-off as formal method | ablation only |
| nuScenes as stereo-VINS benchmark | wrong rig; planner eval only |
| Invalid CARLA runs | must pass quality gate |
| Placeholder CSV | all numbers from real runs |

---

## Dataset Roles (locked)

| dataset | role |
|---|---|
| CARLA `dynamic_v3r7` — urban candidates | controlled VINS routing ablation |
| CARLA Town06/07 R6 | boundary / negative control (VISION_INERT confirmed) |
| KITTI Tracking | real object validity evaluation |
| nuScenes | planner-facing object validity |
| KAIST real car | optional FOG feasibility |
| EuRoC | static VINS sanity only |

---

## Evidence Status (2026-07-02)

| claim | status |
|---|---|
| industrial_fog → VISION_ACTIVE (Town01 dense_b1, −14.3%) | ONE town/recipe only; R7 does NOT replicate (confound: gentle_turn drift) |
| ideal_imu → VISION_INERT | confirmed (all R7 towns + Town06/07) |
| Town06/07 → VISION_INERT (both grades) | confirmed — Phase 2 |
| Town10HD replication | ❌ VISION_INERT (confound: drift) |
| Town02 / Town04 / Town05 signal | ❌ VISION_INERT (Town04 failed preview) |
| TCSV-M vs raw_speed | ⛔ GATED — blocked (no VISION_ACTIVE) |

---

## Phase Map

| phase | task | status |
|---|---|---|
| 0 | OpenSpec + boundary freeze | ✅ DONE |
| 1 | R7 map availability + preview + core | ✅ DONE — Town04 FAIL; Town01/02/05/10HD PASS |
| 2 | R7 VINS baseline smoke | ✅ DONE — all 4 VINS_READY_R7 |
| 3 | R7 vision sensitivity gate | ✅ DONE — all 8 (town,grade) VISION_INERT |
| 4 | TCSV life gate | ⛔ BLOCKED — no VISION_ACTIVE; awaiting Option A/B/C |

---

## Success Gate

At end of Phase 3:
- ≥2 distinct urban towns show VISION_ACTIVE under industrial_fog
- Signal is object-specific (random_control ruled out)
- Signal is repeatable (DET2 variance < ATE signal)
- Written gate decision issued before Phase 4

## Failure Gate

At end of Phase 3:
- No town is VISION_ACTIVE → paper claim downgraded to planner/perception-facing validity only

---

## Files

| file | content |
|---|---|
| `openspec/changes/dynamic-object-validity-routing/proposal.md` | problem, proposed change, non-goals, evidence, success/failure gates |
| `openspec/changes/dynamic-object-validity-routing/design.md` | architecture, variant list, IMU grade grid, dataset roles, evaluation protocol |
| `openspec/changes/dynamic-object-validity-routing/tasks.md` | phase-by-phase task list with gates |
| `specs/object-state-validity/spec.md` | requirements for component-wise validity decomposition |
| `specs/vins-dynamic-routing/spec.md` | requirements for VINS feature routing, DET2 gate, variant nomenclature |
| `specs/planner-validity-interface/spec.md` | requirements for planner-facing object classes |
| `specs/dataset-evaluation-boundary/spec.md` | requirements for dataset roles, town classification, recording versioning |
| `paper2/track_a/PAPER2_LIFE_GATE_PHASE2_RESULTS.md` | Phase 2 results — Town06/07 VISION_INERT confirmed |
| `paper2/track_a/PAPER2_R7_MAP_AVAILABILITY.md` | ✅ R7 town availability — all 5 MAP_AVAILABLE |
| `paper2/track_a/PAPER2_R7_PREVIEW_AUDIT.md` | ✅ R7 preview quality — Town04 FAIL, 4 PASS |
| `paper2/track_a/PAPER2_R7_CORE_MANIFEST.md` | ✅ R7 core recordings — 4 PASS_CORE |
| `paper2/track_a/PAPER2_R7_VINS_BASELINE_SMOKE.md` | ✅ R7 VINS baselines — 4 VINS_READY_R7 |
| `paper2/track_a/PAPER2_R7_VISION_SENSITIVITY_RESULTS.md` | ✅ Phase 3 results — all VISION_INERT |
| `paper2/track_a/PAPER2_R7_URBAN_CANDIDATE_DECISION.md` | ✅ final decision — BLOCKED; awaiting Option A/B/C |
