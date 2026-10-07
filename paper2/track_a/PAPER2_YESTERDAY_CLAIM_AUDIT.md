# Paper-2 — Yesterday's Claim Audit (PI-level review)

**Date:** 2026-07-02 (audit pass)
**Reviewer stance:** strict / corrective. No optimism-by-default.
**Rule:** verify every number from source files; do not call smoke tests "results"; do not
call raw-speed masking "learned PV"; do not call random-split HealthNet "generalization"; do
not claim ORB-SLAM3 localization improvement without a direct baseline-vs-masked trajectory.

**Verdict legend:** PAPER-READY / VALID-LIMITED / SMOKE-ONLY / OVERCLAIMED / INCOMPLETE / INVALID / BLOCKED

---

## Master audit table

| id | claim (as stated yesterday) | source | evidence | dataset / seqs | method | baseline | metric | number | problem | verdict | corrected claim |
|----|------|--------|----------|------|--------|----------|--------|--------|---------|---------|-----------------|
| **A** | OPL reduces obstacle near-collisions | PHASE4_2 | phase42/…BENCHMARK.md | mini_world sim, 30 eps (3×2×5 seeds) | risk-scaled speed margin | naive, hard-stop | near_coll/ep | 46.6→2.7 (−94%), 0 collisions | 2D kinematic sim, GT pose, synthetic `/scan`, 5 seeds | **VALID-LIMITED** | "In a controlled 2D sim, risk-scaled OPL margins reduce near-collisions 94% vs naive and avoid the frozen-robot failure of hard-stop." NOT real-robot. |
| **B** | KITTI Mondrian OPL is calibrated | KITTI_MONDRIAN | obstacle_opl/KITTI_MONDRIAN_RESULTS.md | KITTI tracking, 21 scenes, 37,022 obj-frames | leave-scene-out conformal (quantile GBR) | scene-split, random-split, distance-gate | exceedance @IR=0.10 | 0.1140 (PASS ≤0.12); avail 32.4%; HMI 194 | IR=0.20 FAILS (0.2225); avail only 32% | **PAPER-READY** | Keep as-is at IR=0.05/0.10. Exclude IR=0.20. This is the strongest result. |
| **C** | nuScenes supports cross-dataset transfer | PHASE1_2 | PHASE1_2_NUSCENES_VALIDITY.md | nuScenes CAM_FRONT, 85 scenes (1/10 subset), YOLO+LiDAR-median-depth proxy | HGBM train CARLA+KITTI → test nuScenes | distance gate | AUROC | zero-shot 0.691; target-calib 0.969; in-domain 0.973 | zero-shot transfer WEAK; "transfer" needs target calibration; proxy detector pipeline | **VALID-LIMITED** | "Reliability structure replicates across 3 real datasets, but zero-shot cross-dataset transfer is weak (0.69); a small target-calibration slice recovers 0.97." Do NOT claim zero-shot transfer. |
| **D** | LPL is necessary (OPL can't cover localization) | PHASE4_3 | phase43/…LOC_DEGRADATION.md | mini_world sim, 9 eps (3×3) | safe-only obstacles + loc_err ramp | naive, OPL, OPL-hardstop | false_safe/ep | ≈255 in ALL 3 conditions | sim proxy; structural demo not statistical | **VALID-LIMITED** | "Structural proof (sim): OPL is blind to localization degradation → a dedicated LPL channel is architecturally required." Valid as motivation. |
| **D′** | LPL formalism delivers usable coverage | PHASE3 | loc_lpl/, phase3 | CARLA sim, 54 runs | isotonic on early_env | naive | avail @IR=0.10 | 1.85% (0 HMI) | 1.85% avail = essentially always UNAVAILABLE; scale-drift gap unresolved | **INCOMPLETE** | "LPL calibration achieves 0 HMI but only 1.85% availability — a documented research gap, not a deployable channel." |
| **E** | HealthNet works (AUROC 0.963) | PHASE5 | phase5/…BASELINE.md, healthnet_results.json | KAIST reliability_dataset.tsv, 22,028 win | HGBM, stratified RANDOM split | acc_bias_margin rule | AUROC | 0.963 (rule 0.297) | ALL 90 failures in urban38-pankyo ONLY; random split ⇒ adjacent 5s windows of the SAME failure event in train+test (temporal leakage); single feature entropy8=0.62, all others ≈0 | **OVERCLAIMED** | "A single-feature (visual-entropy) detector separates the urban38-pankyo failure STATE within-distribution (AUROC 0.96). Cross-sequence generalization is NOT evaluable — only one sequence contains failures. Adjacent-window leakage likely inflates AUROC." |
| **F** | HealthNet gives time-to-alert | PHASE5 | healthnet_tta_results.json | same | temporal holdout | — | TTA | 0s (all 3 seqs) | 0s lead = no early warning | **OVERCLAIMED** (if called early-warning) | "HealthNet is a failure-STATE detector, not an early-warning predictor: measured lead time is 0s. Failure onset is abrupt." |
| **G** | Closed-loop supervisor improves safety | PHASE4_2 | phase42 | mini_world sim | rule supervisor | naive | collision%, freeze | 0 coll / 0 freeze (ours) | sim only | **VALID-LIMITED** | Same as A: controlled-sim evidence, not real-world validation. |
| **H** | Hard-stop is bad | PHASE4_2 (+4.4) | phase42, phase44 | mini_world sim | hard-stop cond | risk-scale | collision% | 10% (moving world) | 4.4 corroboration is anomalous (see I) | **VALID-LIMITED** | "In dynamic sim, hard-stop freezes the robot into a collision target (10% collision, 0% success in static). Use risk-scaled modulation." Cite Phase 4.2 only. |
| **I** | Phase 4.4 dual-channel result | PHASE4_4 | phase44/…BENCHMARK.md | mini_world sim, 9 eps (3×3) | OPL+LPL | single-channel | collision%, near_coll | collision% = 800% & **6100%** (impossible); dual near_coll=116 | broken metric (collisions/ep ×100 mislabeled); dual_channel is WORST on near_coll — CONTRADICTS the report's own "reduces both" text; n=3 | **INVALID / ANOMALOUS** | REMOVE from main. Only surviving qualitative point ("LPL hard-stop dangerous in moving world") is already shown cleanly in Phase 4.2. |
| **J** | VINS PV masking improves localization | PHASE6_VINS / Phase C | PHASE6_VINS_PV_FILTER_SMOKE.md, VINS_MASKING_LIMITATION_AUDIT.md | CARLA Town01 dense/medium (2 PASS_CORE) | image BLUR relay, raw_speed>1m/s gate | baseline, all_dynamic, oracle | ATE | −10.5% (dense), −2.8% (medium), 0 fail | NOT learned TCSV-M (raw_speed gate); image blur not feature routing; only 2 clean runs; frontend already rejects ~90% (outlier ratio 0.9) | **VALID-LIMITED** | "A raw-speed dynamic-object mask reduces VINS ATE by 2.8–10.5% on 2 clean CARLA runs. This is an observability gate, NOT the learned TCSV-M model, and headroom is limited because RANSAC already rejects most dynamic features." |
| **K** | ORB-SLAM3 PV masking improves localization | PHASE6 | phase6/…PV_FILTER_SMOKE.md | EuRoC MH_01_easy | synthetic bbox blur relay | baseline | ATE | **NONE** (not saved) | no trajectory in either run (global BA hangs); node publishes nothing live; synthetic mask ≠ real dynamic bbox | **SMOKE-ONLY** | "The masking relay runs on ORB-SLAM3 without crashing it (infrastructure ready). NO ATE comparison exists. No localization claim." |
| **L** | ORB-SLAM3 baseline runs | PHASE6 | phase6/…BASELINE_SMOKE.md | EuRoC MH_01_easy | stereo-inertial | — | map pts, VIBA | 534 pts, VIBA 1+2, 0 resets | trajectory not saved (BA hang) | **VALID (smoke/infra)** | "ORB-SLAM3 stereo-inertial initializes and tracks on EuRoC (infrastructure verified)." Not a localization result. |
| **M** | Dyna* / RTABMap external baselines | PHASE6D | PHASE6_DYNAMIC_SLAM_BASELINE_AUDIT.md | — | audit | — | — | DynaVINS=ROS1 not built; DynaSLAM/DS-SLAM=not found; RTABMap=present, non-specialist | no executable external dynamic-SLAM baseline exists locally | **BLOCKED (literature-only)** | "No executable third-party dynamic-SLAM baseline is available; comparisons are literature-only." Honest as-is. |
| **N** | Full paper-ready package complete | FINAL_EVIDENCE §10, NIGHT S4 | package docs | — | — | — | — | "paper-ready", "branch upgrades paper" | only B is truly paper-ready; E/F/I/K overclaimed; J mislabeled | **OVERCLAIMED** | "One result (KITTI Mondrian OPL) is paper-ready. The rest is supporting/exploratory. The package is NOT submission-complete." |

---

## Count by verdict

| verdict | claims | note |
|---------|--------|------|
| PAPER-READY | B | KITTI Mondrian OPL only |
| VALID-LIMITED | A, C, D, G, H, J, L | usable with honest, narrowed framing |
| SMOKE-ONLY | K | ORB-SLAM3 masking = infra, no ATE |
| OVERCLAIMED | E, F, N | HealthNet AUROC, TTA, "package complete" |
| INCOMPLETE | D′ | LPL availability crisis |
| INVALID / ANOMALOUS | I | Phase 4.4 broken metric + self-contradiction |
| BLOCKED | M | no executable external baseline |

---

## The three overclaims to remove/downgrade first

1. **HealthNet "AUROC 0.963" as a capability claim (E).** It is a within-distribution,
   single-sequence, single-feature detector with probable adjacent-window leakage. Reframe as a
   within-distribution failure-state detector; state plainly that cross-sequence generalization is
   not evaluable on this data (only urban38 has failures). *(Being verified now: leave-sequence-out
   + leave-grade-out diagnostic → `logs/phase5/healthnet_generalization_audit.json`.)*

2. **Phase 4.4 dual-channel (I).** Metric is broken (collision% up to 6100%) and the table
   contradicts its own conclusion. Remove from the evidence package; do not cite as a benchmark.

3. **"validity_aware" VINS masking implying a learned PV model (J).** It is a raw-speed gate on
   blurred images. Rename to "raw-speed dynamic mask" everywhere. TCSV-M was never run in this loop.

Plus: **ORB-SLAM3 (K/L)** stays as "infrastructure / smoke", never a localization result, until a
direct baseline-vs-masked trajectory exists (which needs a small wrapper change — see missing-experiments doc).
