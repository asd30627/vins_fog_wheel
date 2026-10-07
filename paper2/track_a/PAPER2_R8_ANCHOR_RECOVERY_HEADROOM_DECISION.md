# R8-3 — Anchor Recovery Headroom Decision

**Date:** 2026-07-02
**OpenSpec topic:** Shared Object Persistence for Coupled ORB-SLAM3 Backend and Frontier Navigation
**Boundary respected:** no ORB-SLAM3 backend/core changes; no closed-loop frontier; no learned
persistence; no dynamic-object BA factor. All 3 conditions are **input-level masking** through the
existing wrapper (`run_orbslam_carla_logged.sh` + `--stereo-mask-json`), exactly as used in the prior
CARLA PV-mask work.

---

## Method

Two core recordings (Town02, 3600 drive frames / 180 s each, from R8-2):
- `anchor_recovery_core` — many parked/semi-static objects (16 static NPCs), few moving (10).
- `dynamic_noise_core` — mostly moving objects (29 moving NPCs), few static (3).

Three GT-based masks per recording (`scripts/r8_gt_mask_builder.py`, stereo-consistent via
depth-derived disparity, no detector/backend dependency):
- **baseline** — no mask.
- **class_prior** — mask ALL GT object 3D-bbox projections (static + moving). Proxy for a naive
  "vehicle-class" detector that can't distinguish semi-static from transient.
- **oracle_cull** — mask ONLY objects with GT speed ≥ 0.5 m/s (transient). Semi-static/parked regions
  are left **unmasked** — this operationalizes "oracle candidate-anchor recovery" as: does keeping the
  static regions (instead of discarding them like class_prior does) help?

ATE computed vs GT (SE(3) Umeyama = raw metric error; Sim(3) = scale-free, isolates shape/heading
accuracy from a global scale error).

## Results (6 ORB-SLAM3 runs, single seed each)

| recording | condition | poses | init-resets | loop detected/accepted | ATE SE(3) RMSE (m) | ATE Sim(3) RMSE (m) |
|-----------|-----------|-------|-------------|------------------------|---------------------|----------------------|
| anchor_recovery | **baseline** | 3740/3760 | 14 | 10 / NO | 76.5 | 66.8 |
| anchor_recovery | **class_prior** (mask all) | 3740/3760 | 14 | 0 / — | **85.5 (worse)** | **74.3 (worse)** |
| anchor_recovery | **oracle_cull** (mask moving only) | 3740/3760 | 14 | 0 / — | **906.4 (catastrophic)** | **54.1 (best)** |
| dynamic_noise | **baseline** | 3740/3760 | 14 | 0 / — | 104.4 | 80.3 |
| dynamic_noise | **class_prior** (mask all) | 3740/3760 | 14 | 0 / — | **78.9 (better)** | **71.1 (better)** |
| dynamic_noise | **oracle_cull** (mask moving only) | 3740/3760 | 14 | 0 / — | **70.6 (best)** | **65.9 (best)** |

Full raw CSV: `logs/phase6/r8_diagnostics_results.csv`. All init-resets (14) are early-phase
("not enough motion"), same pattern as every prior run — harmless, not mid-drive tracking loss.

**Loop closure note:** baseline detected the loop 10 times but rejected every one (`BAD LOOP!!!`,
same pattern as the earlier Town01 loop-recording finding — online tracking had already drifted too
far by return time). No masked condition even detected a loop candidate (path/drift differs enough
under masking that the return-area keyframe match never triggered).

## Required diagnostics — what was/wasn't measured (honest)

| diagnostic | status |
|-----------|--------|
| ATE / RPE / reset / lost count | ✅ measured (RPE not computed — evo RPE needs a delta config; ATE + reset + pose-count are the load-bearing signals here) |
| loop detected / accepted / rejected | ✅ measured (log grep) |
| dynamic feature ratio, object-region feature ratio | ✅ measured in R8-1 (standalone cv2 ORB analysis) on the preview clips of the same scenarios; not re-run at core length (same scenario design, no reason to expect a different distribution) |
| MapPoint contamination ratio, object-region residual distribution, transient/candidate-anchor MapPoint survival time, object descriptors entering BoW | **NOT measured** — these require live MapPoint/KeyFrame instrumentation inside ORB-SLAM3, which is a backend change. Explicitly out of scope this round (per the stated boundary). This is the concrete gap a future backend-instrumentation phase would need to close. |

## Reading the results

1. **`anchor_recovery_core` (static-object-dominated scene):** `class_prior` (mask everything) is
   **worse** than baseline on both metrics — discarding the many static/parked regions removes useful
   tracking features without removing much harmful content (few moving objects here to begin with).
   `oracle_cull` (keep static, mask only the few movers) gives the **best scale-free shape** (Sim3 54.1,
   beats both baseline and class_prior) — but its raw SE(3) error is catastrophic (906 m), meaning the
   run hit a severe scale-divergence event somewhere in the 180 s drive. This is a genuinely unstable,
   **single-run** result: the shape evidence points toward anchor-recovery headroom, but the raw-metric
   evidence is dominated by an unexplained divergence that a single seed cannot disambiguate from noise.
2. **`dynamic_noise_core` (moving-object-dominated scene):** BOTH `class_prior` and `oracle_cull` beat
   baseline on both metrics, with `oracle_cull` the best of the three (SE3 70.6, Sim3 65.9). But
   `class_prior` (mask everything, no anchor preservation) is only slightly behind `oracle_cull` — there
   is a clean **culling** benefit, but only a small extra margin from **specifically preserving** the
   static regions. This is a `CULLING_ONLY` pattern, not a strong differential anchor-recovery signal.

## Decision

Per the prescribed decision rule:

- **NOT `NO_HEADROOM`.** Masking changes the result substantially in both scenarios (up to ±25% ATE
  swings) — there is real headroom to be found, input masking is not neutral here.
- **`dynamic_noise_core` → `CULLING_ONLY`.** Transient culling helps (best of the three), but
  class_prior (no anchor preservation) is nearly as good — do not overclaim a distinct anchor-recovery
  benefit from this scenario alone.
- **`anchor_recovery_core` → suggestive of `ANCHOR_HEADROOM` but UNCONFIRMED.** class_prior hurts (as
  the ANCHOR_HEADROOM pattern predicts) and oracle_cull's scale-free shape is the best of the three —
  but the catastrophic raw SE(3) result (906 m, a single-run divergence event) means this cannot be
  reported as a confirmed ANCHOR_HEADROOM result. **n=1 per condition; needs ≥3-seed repetition before
  any backend-prototype commitment.**

### Overall verdict: **MIXED / SCENARIO-CONDITIONAL, NOT YET A CLEAN ANCHOR_HEADROOM CALL**

The evidence rules out NO_HEADROOM (masking clearly matters) and gives a clean CULLING_ONLY result in
the moving-object-dominated scenario. The static-object-dominated scenario gives a suggestive but
statistically unconfirmed ANCHOR_HEADROOM signal (real shape-accuracy benefit, but one run also showed
a large raw-metric divergence that must be understood before trusting the signal).

## UPDATE (2026-07-02, same day) — 3-seed replication of `anchor_recovery_core`

Per the plan above, `anchor_recovery_core` was repeated on **2 additional seeds** (s2, s3; same
scenario preset, independently randomized NPC placement/route), giving **n=3 per condition**. This
**changes the conclusion** — the single-run "suggestive ANCHOR_HEADROOM" signal does **not** replicate.

| condition | SE3 RMSE (m) | | | Sim3 RMSE (m) | | | SE3 divergence (>200 m) |
|-----------|------|------|------|------|------|------|--------------------------|
| | s1 | s2 | s3 | s1 | s2 | s3 | |
| baseline | 76.5 | **8082.9** | 183.6 | 66.8 | 54.3 | 72.0 | **1/3** |
| class_prior (mask all) | 85.5 | 78.7 | 82.1 | 74.3 | 71.5 | 71.7 | **0/3** |
| oracle_cull (mask moving only) | 906.4 | 2274.4 | 173.4 | 54.1 | 65.5 | 73.1 | **2/3** |

**Per-condition summary (n=3):**

| condition | SE3 median | Sim3 mean | divergence rate |
|-----------|-----------|-----------|------------------|
| baseline | 183.6 | 64.4 | 1/3 |
| **class_prior** | **82.1** | 72.5 | **0/3 (most stable)** |
| **oracle_cull** | **906.4** | 64.2 | **2/3 (least stable)** |

### Corrected reading

1. **The SE(3) "catastrophic divergence" is NOT specific to any masking condition** — it occurred in
   baseline (1/3) and oracle_cull (2/3), and even the SAME scenario/route can diverge unpredictably run
   to run (seed2 baseline hit SE3=8083 m). This is evidence of a general ORB-SLAM3 online-trajectory
   scale-instability on this route, not a masking artifact.
2. **`oracle_cull`'s earlier "best Sim3 shape" result does NOT replicate.** Mean Sim3 across 3 seeds
   (64.2) is statistically indistinguishable from baseline (64.4). Its raw-metric stability is actually
   the **worst** of the three (2/3 seeds diverged). **There is no reliable evidence that keeping
   static/candidate-anchor regions unmasked (while culling only moving objects) improves localization
   over doing nothing.**
3. **`class_prior` (mask everything, no anchor preservation) is the most STABLE condition** (0/3
   divergence, tight SE3 band 78.7–85.5) but its Sim3 shape (72.5) is not better than baseline (64.4) —
   it trades shape accuracy for raw-metric predictability. This is a genuinely new finding, but it does
   **not** support a candidate-anchor-recovery mechanism; if anything it mildly favors indiscriminate
   masking for tracking *stability*, which is the opposite of what a "preserve useful static anchors"
   mechanism would predict.

### Revised decision: **`anchor_recovery_core` → `NO_HEADROOM`** (not `ANCHOR_HEADROOM`)

The single-run signal that motivated a tentative `ANCHOR_HEADROOM` reading was **noise**. With proper
3-seed replication, oracle-based candidate-anchor preservation shows **no measurable benefit** over
baseline on this scenario (Sim3 tied, SE3 worse). Per the prescribed decision rule ("if all_dynamic
does not hurt [much] and candidate anchor oracle does not help, mark NO_HEADROOM and redesign
scenario") — this scenario does not support building a rule-based anchor-recovery backend prototype.

### Combined R8 verdict

- `dynamic_noise_core` (n=1, **not** re-verified this round): suggested `CULLING_ONLY` — masking
  moving objects (with or without anchor preservation) beat baseline. This finding is **still
  unreplicated** and should not be trusted more than the anchor_recovery single-run result was.
- `anchor_recovery_core` (n=3, verified): **`NO_HEADROOM`** for candidate-anchor recovery specifically.
- **Net recommendation: do NOT proceed to a rule-based anchor-recovery backend prototype based on this
  evidence.** If the `dynamic_noise` culling-only signal is to be trusted, it would need the same
  3-seed replication treatment first — anchor_recovery's single-run result already showed how
  unreliable n=1 CARLA/ORB-SLAM3 conclusions are.

## What this means for the next phase

1. ~~Repeat `anchor_recovery_core` with ≥3 seeds~~ — **DONE, executed this round.**
2. The `ANCHOR_HEADROOM` path (rule-based backend prototype) is **not supported** by the replicated
   evidence — do not start it.
3. If a `CULLING_ONLY` mechanism is still of interest, `dynamic_noise_core` needs the same 3-seed
   replication before it can be trusted (not done this round — would be the next concrete step, NOT
   executed here).
4. **STOP here per the user's explicit boundary** — no learned persistence, no closed-loop frontier, no
   dynamic-object BA factor, no backend changes were made or are recommended from this evidence.

## Process hygiene

`pgrep -af "stereo-inertial|paper2_carla_stereo_player|r8_run_diagnostics|collect_carla_v2"` →
**ALL CLEAR** after the batch. `carla_dyn` docker container left running (unharmed).
