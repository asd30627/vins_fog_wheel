# Paper-2 — Claim Repair Plan (targets, not downgrades)

**Date:** 2026-07-02 (repair pass)
**Rule:** yesterday's claims are TARGETS. For each: notify weakness → name the exact missing
experiment/baseline/split/artifact → try to fix with existing data/scripts/allowed code → mark BLOCKED
only if unfixable, with the exact blocker. Do NOT permanently downgrade before repair attempts complete.

Legend for `can_fix_now`: YES (fixed or fixable with existing artifacts) / PARTIAL / NO (blocked).

---

## Repair table

### 1. OPL obstacle integrity is calibrated and improves navigation safety
- **current_evidence:** KITTI Mondrian leave-scene-out, exceedance 0.1140@IR=0.10 PASS; Phase 4.2 sim closed loop.
- **current_problem / not-ready:** missing a **confidence-gate** baseline; closed loop is 2D sim.
- **exact repair:** add confidence-gate baseline (on `det_conf`); keep closed loop labeled sim.
- **available data/scripts:** `paper2/paper2_kitti_validity_dataset.csv` (`det_conf` 0.30–0.966, 100% non-null); `scripts/paper2_obstacle_opl_stanford.py` (`baseline_distance_gate` to fork).
- **can_fix_now:** YES — DONE. Confidence gate added (`scripts/paper2_opl_confidence_gate.py`).
  **Result: OPL WINS.** At matched 32.4% availability, exceedance: OPL 0.114 < range-gate 0.137 <
  confidence-gate 0.172. Report: `logs/PHASE_OBSTACLE_OPL_REPAIR_REPORT.md`.
- **success criterion:** OPL beats both gates at matched availability → **MET.**
- **user_decision_required:** NO.

### 2. nuScenes supports cross-dataset obstacle reliability
- **current_evidence:** in-domain 0.973; zero-shot 0.692; target-calib 0.969.
- **problem:** "transfer" implied zero-shot; zero-shot is weak.
- **exact repair:** report all three separately (already computed in `logs/nuscenes_analysis/model_auroc_summary.csv`).
- **can_fix_now:** YES (reporting) — done in OPL repair report.
- **success criterion:** three numbers reported separately with honest "needs target calibration" framing.
- **user_decision_required:** NO.

### 3. LPL / localization integrity is necessary
- **current_evidence:** Phase 4.3 structural gap (false_safe≈255 all conditions, sim).
- **problem:** LPL formalism itself only 1.85% avail (isotonic v1); necessity shown, solution not.
- **exact repair:** none needed for the *necessity* claim (Phase 4.3 valid as structural proof); the
  *deployable-LPL* claim stays a research gap (scale-drift predictor missing).
- **can_fix_now:** PARTIAL — necessity=YES (valid), deployability=NO (needs scale-drift signal).
- **success criterion:** necessity framed as structural; deployability marked BLOCKED with blocker.
- **user_decision_required:** NO.

### 4/5. HealthNet predicts VINS failure + gives useful detection
- **current_evidence (repaired):** expanded dataset 43,654 windows / 598 failures / **6 routes**
  (incl. 4 real-sensor-grade highways). LOSO AUROC 0.73–0.99 (mean reliable ≈0.84); hardest
  cross-route+grade transfer 0.726. TTA=0s (state detector).
- **problem repaired:** cross-sequence went from "not evaluable" → genuine LOSO.
- **repair run:** `extract_reliability_dataset.py --out reliability_dataset_expanded.tsv` (folds in
  on-disk diverged routes; NO VINS rerun) + LOSO eval.
- **can_fix_now:** YES (done). Report: `logs/phase5/PHASE5_HEALTHNET_REPAIR_REPORT.md`.
- **remaining weakness:** run-mode confound (highways=soft-failure mode); grade↔route confound.
- **success criterion:** non-leaky cross-sequence AUROC > 0.5 established → **MET** (0.73–0.99).
- **fallback if confound fatal:** matched-mode VINS replay (multi-hour; report before running).
- **user_decision_required:** YES (approve matched-mode replay to remove confound → strong claim).

### 6. Closed-loop supervisor improves safety
- **current_evidence:** Phase 4.2 (near_coll −94%, 0 collisions, 30 eps sim).
- **problem:** 5 seeds; sim proxy.
- **exact repair:** optional 10-seed rerun (S3); label sim.
- **can_fix_now:** PARTIAL (10 seeds cheap, ~10 min); real-world = future work.
- **success criterion:** collision-reduction holds at 10 seeds.
- **user_decision_required:** YES (run S3?).

### 7. Dual-channel OPL+LPL is better than single-channel
- **current_evidence:** Phase 4.4 — INVALID (broken collision% metric, no risk-scaled LPL mode, stale ep07).
- **exact repair:** fix metric (per-episode boolean), enforce episode timeout, ADD risk-scaled LPL
  mode (continuous speed scaling, not hard-stop), purge stale CSVs, rebuild, rerun 15 eps.
- **available:** `scripts/phase44_batch.py` (metric line 267), `mini_world_sim_node.py` (freeze lines
  344–346, boolean `collision` line 501, unused `timeout_s`), `colcon build --packages-select paper2_validity_bridge`.
- **can_fix_now:** YES — DONE in two stages. Stage 2 (availability flag) **SUPPORTS claim 7**: 20-ep
  ablation → dual_channel_avail false_safe% **0** (vs OPL 60, speed-only 80), collision **0%** (= OPL),
  at availability **0.12** / success 40% (honest tradeoff). Reports:
  `logs/phase44/PHASE4_4_LPL_AVAILABILITY_REPAIR_REPORT.md` (+ `PHASE4_4_DUAL_CHANNEL_REPAIR_REPORT.md`).
- **success criterion:** false_safe↓ vs OPL-only AND speed-only, without collision↑ vs OPL → **MET.**
- **user_decision_required:** NO.

### 8. VINS PV/dynamic masking improves localization
- **current_evidence:** raw_speed mask −2.8%…−10.5% ATE, 2 clean CARLA runs.
- **repair:** re-run baseline/raw_speed/**tcsvm**/oracle in ONE session (controls nondeterminism).
- **can_fix_now:** YES — DONE. **Result: MIXED.** Controlled session: dense −2.5% (3.582→3.492), medium
  +2.3% (3.418→3.495, worse). Effect small, variant-insensitive, within nondeterminism band; the prior
  −10.5% was a favorable-session artifact. Report: `logs/PHASE6_VINS_TCSV_MASK_REPAIR_REPORT.md`.
- **success criterion:** masking reduces ATE vs baseline → PARTIAL (dense yes, medium no).
- **user_decision_required:** NO.

### 9. Learned TCSV-M / PV mask improves VINS, not just raw_speed
- **current_evidence:** learned leak-free scores existed (`paper2_tcsv_vins_scores.csv`) but were never
  turned into a mask or run through VINS.
- **exact repair:** built `scripts/paper2_make_tcsvm_mask.py` → `mask_*__tcsvm.json` (dense 924 boxes/497
  frames; medium 638/341), then VINS replay tcsvm variant (P2).
- **can_fix_now:** YES — DONE. **Result: NOT SUPPORTED.** Controlled session: dense tcsvm 3.492 vs
  raw_speed 3.483 vs oracle 3.492; medium all identical 3.495. Learned TCSV-M matches but does NOT beat
  raw_speed or oracle (frontend already rejects the features). Report: `logs/PHASE6_VINS_TCSV_MASK_REPAIR_REPORT.md`.
- **success criterion:** tcsvm ATE < raw_speed → **NOT MET** (tcsvm ≈ raw_speed).
- **outcome:** keep "raw-speed dynamic mask"; the learned mask is validated as no better.
- **user_decision_required:** NO.

### 10. ORB-SLAM3 PV masking can improve localization
- **current_evidence:** smoke only; no ATE (wrapper discards pose; save only after hanging global BA).
- **exact repair:** wrapper-only pose logger (capture `Sophus::SE3f` at `stereo-inertial-node.cpp:219`,
  write TUM CSV) → online trajectory → evo ATE. Does NOT touch core.
- **can_fix_now:** DONE (infra). Wrapper pose logger implemented + rebuilt; **baseline ATE now
  obtainable** (EuRoC online RMSE 1.276 m); baseline-vs-masked pipeline works (masked_synth 5.268 m —
  HURTS, expected sanity on a static scene, NOT a PV result). Reports:
  `logs/phase6/PHASE6_ORBSLAM3_POSE_LOGGER_REPAIR_REPORT.md`, `PHASE6_ORBSLAM3_BASELINE_VS_MASKED_REPAIR_REPORT.md`.
- **success criterion (PV improvement):** needs a DYNAMIC scene → **BLOCKED** on 2 adapters:
  (1) a CARLA ORB-SLAM3 stereo-inertial config YAML (intrinsics/extrinsics/IMU), (2) CARLA-GT→TUM
  converter. CARLA player topics ARE compatible (remap works; masks exist). Not run (config-authoring
  + tuning; report-before-run).
- **user_decision_required:** YES (author the CARLA config + GT converter to run the real PV test?).

### 11. External dynamic-SLAM baselines are handled properly
- **current_evidence:** DynaVINS (ROS1, not built), DynaSLAM/DS-SLAM (not found), RTABMap (non-specialist).
- **exact repair:** none feasible in <1h (ROS1→ROS2 port explicitly out of scope).
- **can_fix_now:** NO (BLOCKED). Blocker: no executable third-party dynamic-SLAM on this machine.
- **success criterion:** honest "literature-only comparison" framing.
- **user_decision_required:** NO.

### 12. Full journal package can be completed
- **current_evidence:** OPL solid; other channels repairing.
- **can_fix_now:** decide AFTER repairs (P1/P2/P3/P5 this pass). See `PAPER2_REPAIRED_JOURNAL_STATUS.md`.
- **user_decision_required:** YES (final scope after repair results).

---

## Repairs executed this pass

| priority | repair | status |
|----------|--------|--------|
| P1 HealthNet | expand dataset (6 routes) + LOSO 0.73–0.99 | **DONE — REPAIRED** (cross-seq now real) |
| P2 VINS masking | baseline/raw/tcsvm/oracle, 1 session | **DONE** — masking mixed (−2.5%/+2.3%) |
| P2b learned TCSV-M | build mask + run through VINS | **DONE — claim 9 NOT SUPPORTED** (TCSV-M ≈ raw) |
| P3 Phase 4.4 (stage 1) | metric+timeout fix + risk-scaled mode + rerun | **DONE** — valid; speed-only fixes safety not HMI |
| P3 Phase 4.4 (stage 2) | LPL availability flag + 20-ep rerun | **DONE — claim 7 SUPPORTED** (false-safe→0, coll 0%, avail 0.12) |
| P4 ORB-SLAM3 | wrapper pose logger + baseline + masked ATE | **DONE (infra)** — ATE obtainable; PV test BLOCKED on CARLA config+GT converter |
| Nav metric audit | classify 18 metrics; compute CSV-derivable | **DONE** — 13 computed, 4 need logging, 1 N/A |
| P5 OPL | confidence-gate baseline + nuScenes split framing | **DONE — OPL beats both gates** |

Nothing was permanently downgraded by assertion. Where a repair falsified a claim (learned TCSV-M),
that is an experimental result, not a downgrade. Final scope decision → `PAPER2_REPAIRED_JOURNAL_STATUS.md`.
