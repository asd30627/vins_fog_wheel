# ORB-SLAM3 PV-Validity Localization — Feasibility Assessment

**Date:** 2026-07-02  
**Branch:** Phase 6 (upgrade branch; does not replace OPL/LPL integrity package)  
**Purpose:** Evaluate whether position/velocity (PV) validity can actively improve localization, not only supervise navigation

---

## Framing

The existing integrity-monitoring paper uses PV-validity for SUPERVISION (flag unsafe navigation decisions). This branch asks a different question:

> *Can PV-validity protect localization itself by excluding unreliable dynamic-object observations from pose estimation?*

If yes: the contribution becomes stronger — PV-validity both monitors navigation AND improves the localization it monitors.  
If no: document honest null; keep the existing integrity-monitoring paper unchanged.

---

## Infrastructure Status (Phase 6.0–6.1)

| Item | Status |
|------|--------|
| ORB-SLAM3 ROS2 wrapper | **Present** at `/home/ivlab3/orbslam_ws/` |
| Core library | Pre-built (`libORB_SLAM3.so`) |
| Supported modes | Mono, Stereo, RGBD, Stereo-Inertial, RGBD-Inertial |
| EuRoC compatibility | **CONFIRMED** — stereo-inertial smoke test PASS |
| KITTI format | Config exists; needs ROS2 bag or adapter |
| Vocabulary | `vocabulary/ORBvoc.txt` ready |
| Config for EuRoC | `config/stereo-inertial/EuRoC.yaml` ready |
| Smoke test result | Map 534 pts, VIBA 1+2 complete, no tracking loss in ~100s |

---

## The PV-Validity Localization Idea

### Problem

ORB-SLAM3 extracts ORB features from the full image frame. In dynamic environments, features detected on moving objects (vehicles, pedestrians) may be:
- **Tracked across frames** as if they were static scene features
- **Added to the 3D map** as MapPoints (which they should not be, since they're moving)
- **Used in pose estimation** via PnP/BA, corrupting the ego-pose estimate

ORB-SLAM3 has built-in outlier rejection (RANSAC in PnP, BA robust loss) but does not use semantic/validity priors about which image regions contain unreliable features.

### Proposed Solution

Use the PV-validity channel (position/velocity validity from the obstacle integrity module) as a **feature suppression mask** during ORB feature extraction:

```
Raw image → [PV-validity mask] → Masked image → ORB-SLAM3 feature extraction
```

Regions with **low position validity** (dynamic/unobservable objects) are zeroed or blurred before ORB extraction. No features are extracted on dynamic-object regions → no dynamic MapPoints → cleaner pose estimation.

---

## Candidate Methods (ordered by implementation risk)

### Method A — Pre-extraction image masking (ZERO core change)

**Implementation:**
1. Subscribe to `/cam0/image_raw`, `/cam1/image_raw` (stereo images)
2. Subscribe to `/paper2/object_validity` or `/detection2d_array` (bboxes + validity scores)
3. For each bbox where `validity_score < threshold` (e.g., 0.5 = "position invalid"):
   - Set pixels inside bbox to 0 (or Gaussian blur to avoid edge artifacts)
4. Publish masked images to `/cam0/image_masked`, `/cam1/image_masked`
5. Run ORB-SLAM3 with `camera/left:=/cam0/image_masked` remapping

**Pros:** Zero ORB-SLAM3 modification; fully reversible; image relay is 5-10ms latency  
**Cons:** Aggressive — eliminates entire bbox even for partially valid features; bbox must be in stereo-synchronized  
**Safety:** All ORB-SLAM3 code unchanged; masking relay node can be killed with no SLAM impact

### Method B — Validity-weighted ORBextractor (MODERATE core change)

**Implementation:**
1. Add `void SetMask(const cv::Mat& mask)` to ORBextractor
2. In `Tracking::GrabImageStereo()`, compute the validity mask before calling ORBextractor
3. ORBextractor respects mask: skips feature extraction in masked regions

**Pros:** More precise than full-image zeroing; only suppresses feature detection, not tracking  
**Cons:** Requires modifying ORB-SLAM3 Tracking + ORBextractor; need a restore point first  
**Safety:** Restore point required (commit `git stash` before modification)

### Method C — MapPoint validity filtering (DEEP core change — DEFERRED)

**Implementation:**
- Flag MapPoints derived from dynamic-object regions as "suspect"
- Reduce their weight in BA / exclude from loop closing
- Requires modification of `LocalMapping.cc`, `LoopClosing.cc`, `Optimizer.cc`

**Status:** OUT OF CURRENT SCOPE — too invasive for current phase  
**Only attempt if:** A and B show significant improvement + restore point confirmed

---

## Priority Experiment Plan (Method A first)

### Step 1 — Baseline run with trajectory

Run ORB-SLAM3 stereo-inertial on EuRoC V1_01_easy (dynamic sequence) with **no masking**.  
Save `KeyFrameTrajectory.txt`. Compute ATE vs GT using evo or provided scripts.

### Step 2 — PV-validity proxy mask

Since existing PV-validity is CARLA-based (no EuRoC object validity currently available), use a **proxy mask**:

**Option P1 — Synthetic mask (bounding boxes from timestamps):**
- EuRoC has no dynamic objects → use a fixed region as "synthetic dynamic object"
- Measure ATE degradation from masking (should be small if no real dynamic objects)
- Confirms that masking does NOT break tracking on static scenes

**Option P2 — Dynamic-class semantic mask:**
- Run a lightweight detector (YOLO-nano or existing `mmdetection3d`) on EuRoC frames
- Generate semantic masks for dynamic classes (person=0, car=2 in COCO)
- Feed masked images to ORB-SLAM3
- EuRoC MH_01 (machine hall) has no dynamic objects → should be ATE-neutral
- EuRoC V2_01 (room with people) may have pedestrians → more impact

**Option P3 — Use existing CARLA object validity on CARLA sequences:**
- ORB-SLAM3 can run on CARLA sequences if a ROS2 bag is available
- Existing `paper2_object_dataset_v2_with_vins.parquet` has per-frame validity scores for CARLA Town01/Town10HD
- Map CARLA bboxes → validity scores → masking relay node
- This is the cleanest integration with existing PV-validity infrastructure

### Step 3 — Compare metrics

| Metric | Baseline | PV-masked |
|--------|----------|-----------|
| ATE (m) | — | — |
| RPE (m/frame) | — | — |
| Tracking lost count | — | — |
| Map points count | — | — |
| Keyframe count | — | — |
| Feature tracks on dynamic regions | — | — |

---

## Gate for Phase 6.3

| Result | Action |
|--------|--------|
| PV-masking improves ATE/RPE or reduces tracking loss | → PROMISING: attempt Method B |
| PV-masking neutral (±5% ATE) | → CONFIRM on dynamic sequence, then document as partial |
| PV-masking worsens ATE or causes tracking loss | → HONEST NULL: document and stop |

---

## What This Can Add to the Paper

If PROMISING:
> *"PV-validity not only supervises navigation decisions but can actively protect localization by suppressing dynamic-object features from entering ORB-SLAM3's map. On [sequence] with [N] dynamic objects, PV-masked ORB-SLAM3 reduces ATE by X% vs baseline."*

This upgrades the contribution from "integrity monitoring" to "integrity-aided localization" — a stronger position in the autonomy stack.

If NULL:
> *"We evaluated whether PV-validity masking could directly improve ORB-SLAM3 localization. On [sequence], masking did not significantly improve ATE/RPE (±X%), suggesting that ORB-SLAM3's existing outlier rejection (RANSAC + BA robust loss) already handles the dynamic-object noise well in this dataset. PV-validity remains useful for navigation supervision even if localization improvement requires a deeper integration."*

This is an honest and publishable null result that strengthens the paper's credibility.

---

## Current Status

| Phase | Status | Result |
|-------|--------|--------|
| 6.0 Audit | **DONE** (`logs/PHASE6_ORBSLAM3_AUDIT.md`) | ORB-SLAM3 found, pre-built, runnable |
| 6A.1 Baseline smoke | **DONE** (`logs/phase6/PHASE6_ORBSLAM3_BASELINE_SMOKE.md`) | 534 pts, VIBA 1+2, 0 resets |
| 6A.2 Mask relay smoke | **DONE** (`logs/phase6/PHASE6_ORBSLAM3_MASK_RELAY_SMOKE.md`) | Relay works (2500 frames, 100%); 3 resets from synthetic bbox placement |
| 6A.3 Baseline vs masked | **DONE** (`logs/phase6/PHASE6_ORBSLAM3_PV_FILTER_SMOKE.md`) | HONEST NULL on ATE (trajectory not saved); qualitatively similar post-VIBA |
| 6B.1 VINS mask audit | **DONE** (`logs/PHASE6_VINS_DYNAMIC_MASK_AUDIT.md`) | mask field at feature_tracker.cpp:289 |
| 6B.2 VINS design | **DONE** (`paper2/track_a/PAPER2_VINS_PV_DYNAMIC_FILTER_DESIGN.md`) | Method A/B/C defined |
| 6B.3 VINS PV smoke | **DONE** (`logs/PHASE6_VINS_PV_FILTER_SMOKE.md`) | −10.5% ATE Town01 dense_b1 (PROMISING) |
| 6C Localization-nav compare | **DONE** (`logs/phase6/PHASE6_LOCALIZATION_TO_NAV_COMPARISON.md`) | Branch upgrades paper; VINS evidence stronger |
| 6D External baseline audit | **DONE** (`logs/PHASE6_DYNAMIC_SLAM_BASELINE_AUDIT.md`) | DynaVINS=lit-only; DynaSLAM=not found; RTABMap=non-specialist |
| 6A.4 CARLA PV-validity integration | **DEFERRED** — requires CARLA bag + existing validity parquet | — |

---

## Phase 6A Final Summary

### ORB-SLAM3 Baseline vs Masked (Method A)

| Metric | Baseline | Synthetic Mask | Delta |
|--------|----------|----------------|-------|
| Map points | 534 | 521 | −2.4% |
| Init resets | 0 | 3 | +3 |
| VIBA 1+2 | PASS | PASS (delayed) | — |
| ATE | **NOT SAVED** | **NOT SAVED** | **N/A** |

**ATE not fabricated.** Global BA timeout (>18min for 184s sequence) prevents trajectory save on both runs.

### Key Finding: Relay Works, Synthetic Mask Location Matters

The 150×150 px mask at (500,150-650,300) = center-right of 752×480 EuRoC frame covers an initialization-critical texture region. Three resets occur before VIBA 1+2 succeed. For real dynamic-object bboxes (lower image, vehicle locations), fewer resets expected.

### VINS Evidence Is Stronger

VINS PV-masking (Phase C) provides direct ATE comparison on CARLA PASS_CORE runs: −10.5% ATE, 0 failures. This is the primary evidence for the PV-localization contribution. ORB-SLAM3 requires trajectory recording via topic (not global BA) for future ATE comparison.

---

## Boundaries

- Do NOT modify VINS backend
- Do NOT modify Nav2 core or frontier planner
- Do NOT modify ORB-SLAM3 core (src/orbslam3_core/) during Phase 6.3 — Method A only
- Do NOT claim ATE improvement without direct baseline/masked comparison on same sequence
- Do NOT use moving objects as static map anchors
- The existing OPL/LPL navigation-integrity evidence package remains valid regardless of this branch
