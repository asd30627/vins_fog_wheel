# Design — Component-wise Dynamic Object Validity for VINS-Aided Navigation

**Change ID:** dynamic-object-validity-routing  
**Date:** 2026-07-01

---

## Context

This change investigates whether a component-wise dynamic-object validity module can improve visual-inertial navigation (VINS) in scenes with moving objects, and whether validity scores are useful for downstream planning. The key prior finding (Town01 dense_b1, industrial_fog): object-masking reduced ATE by −14.3%, while random_control ≈ baseline, confirming the effect is object-specific, not a feature-count artifact. Phase 2 (Town06/07 R6 cores) showed VISION_INERT — confirming the effect is town-specific (requires urban density + near objects). This design extends the search to urban candidates (Town01–Town05, Town10HD).

---

## Architecture

```
object detector / tracker (YOLO + ByteTrack)
    ↓
raw object state
  position (stereo depth + bearing)
  velocity (optical flow + tracker + ego-motion comp)
  bbox, class, track_id, age
    ↓
component-wise validity estimator
  P_position_valid
  P_velocity_valid
  P_full_state_valid
  routing_policy: REJECT | DOWNWEIGHT | ACCEPT
    ↓ (two consumers)
    ├── A. VINS routing
    │     hard reject → mask bbox in LEFT image (suppress features)
    │     soft weight → (future) lower visual-factor weight
    │     accept → no change
    │
    └── B. Planner interface
          full-state object  (P_full_state_valid > τ_hi)
          position-only object  (P_pos > τ_hi, P_vel < τ_lo)
          velocity-invalid object  (P_pos > τ_hi, P_vel ∈ [τ_lo, τ_hi])
          invalid object  (P_pos < τ_lo)
```

---

## VINS Routing Variants

The following is the **complete, fixed variant list** for evaluation. No variant may be added without a change proposal update.

| variant | description | role |
|---|---|---|
| `baseline` | no masking, no routing change | formal baseline |
| `all_object` | mask ALL detected bbox in LEFT image | naive upper-bound ablation |
| `oracle` | mask only GT-confirmed moving objects | oracle upper bound (GT; eval only) |
| `random_control` | same count + size boxes, random position | artifact control (must not match all_object) |
| `raw_speed_gate` | mask if raw_speed_ms > 1.0 | baseline signal; NOT formal method |
| `cv_smoothing_gate` | mask if smoothed velocity > threshold | baseline signal; NOT formal method |
| `tcsv_m_hard` | TCSV-M classifier → hard reject (REJECT policy) | **formal method — hard routing** |
| `tcsv_m_soft` | TCSV-M classifier → soft weight | **formal method — soft routing** |
| `backend_cull_off` | disable 3-px backend outlier culling | **ablation only** |
| `huber_off` | disable Huber robust loss | **ablation only** |

**Formal method keeps:** stock Huber + stock backend 3-px cull.  
**Ablation only:** `huber_off`, `backend_cull_off` — these are analysis tools, not proposed improvements.  
**Baseline-only signals:** `raw_speed_gate`, `cv_smoothing_gate` — characterize raw signal strength; TCSV-M must beat them.

---

## IMU Grade Grid

| grade | ARW (°/√h) | bias (°/hr) | biasRW (°/hr/√h) | role |
|---|---|---|---|---|
| `ideal_imu` | 0 | 0 | 0 | control (vision always needed) |
| `industrial_fog` | 0.03 | 0.3 | 0.005 | **primary positive signal grade** |
| `precision_mems` | 0.15 | 5.0 | 0.05 | diverges in most towns; excluded |

`ideal_imu` expected VISION_INERT (sensor dominates). `industrial_fog` expected VISION_ACTIVE in high-density urban. `precision_mems` excluded — diverges (documented).

---

## Dataset Roles (locked)

### CARLA (primary controlled evaluation)

**Purpose:** controlled VINS routing ablation with GT, deterministic replay, known dynamic ground truth.

**Positive urban candidates (Phase 1–5):**
- Town01 — reference urban; confirmed VISION_ACTIVE signal under industrial_fog (Town01 dense_b1)
- Town02 — urban mixed traffic; TBD
- Town04 — suburb/urban mix; TBD
- Town05 — town center + roundabout; TBD
- Town10HD — high-fidelity urban; TBD (needs Town01 replication)

**Boundary / negative controls (Phase 2 confirmed):**
- Town06 — highway, VISION_INERT (both grades); scale drift late≈2.2; used as negative control
- Town07 — rural, VISION_INERT (both grades); sparse objects; used as negative control

**Do not re-test Town06/07 as positive candidates. Do not use old Town06/07 masks for R7.**

**Recording condition:** `dynamic_v3r7` (all new R7 runs). **Do not overwrite `dynamic_v3` or `dynamic_v3fix` data.**

### KITTI Tracking (real object validity)

**Purpose:** validate component-wise validity estimates on real-world data with LiDAR GT.  
**Role:** object validity generalization; NOT used for first-stage VINS life gate.  
**Not a stereo-VINS benchmark** (different camera rig, monocular primary for KITTI).

### nuScenes (object validity + planner interface)

**Purpose:** validate planner-facing validity interface with real urban multi-camera data.  
**Role:** object validity / planner-facing risk; NOT a stereo-VINS benchmark.  
**Limitation known:** nuScenes uses a fisheye-adjacent ring camera; stereo depth is not standard.

### KAIST / real car (optional)

**Purpose:** feasibility demonstration on real FOG data.  
**Role:** optional; depends on Phase 5 positive outcome.

### EuRoC (static sanity)

**Purpose:** static-scene VINS sanity check; confirm baseline estimator is not broken.  
**Role:** control only; NOT a dynamic-object evaluation dataset.

---

## Evaluation Protocol

### ATE computation
- SE(3) alignment (Umeyama, no scale), full trajectory.
- RMSE over all VIO poses.
- All results: median over ≥2 DET2 reps.
- DET2 variance gate: if rep1 vs rep2 ATE difference > 3%, run rep3 and take median.

### Vision sensitivity gate
- VISION_ACTIVE: `all_object` or `oracle` reduces ATE ≥5% vs baseline, AND `random_control` does NOT reduce ATE by ≥3% (rules out feature-count artifact).
- VISION_INERT: all variants change ATE by < 3%.
- AMBIGUOUS: `all_object` signal ≥5% but `random_control` also improves ≥3%.
- UNSTABLE: n_vio incomplete, divergence, or rep variance > ATE signal.

### TCSV life gate (Phase 6 — gated)
- Only proceeds if Phase 5 produces at least one VISION_ACTIVE town with a written gate decision.
- TCSV-M must beat `raw_speed_gate` and `cv_smoothing_gate` by ≥3% ATE.
- `random_control` must not match TCSV-M (controls for drop-count artifact).
- Oracle sets the upper bound; TCSV-M must reach ≥50% of oracle gain.

---

## Architectural Constraints (non-negotiable)

1. **No BA factor for dynamic objects.** Object state does not enter the factor graph.
2. **No learning-through-BA.** No gradient signal through the VINS solver.
3. **Stock Huber + stock 3-px cull remain for all formal results.**
4. **TCSV-M classifier is the trained model; raw_speed is the baseline.**
5. **GT used only for oracle (eval) and training labels (offline); never at runtime.**
6. **Planner interface is output-only; no planner feedback to VINS.**
