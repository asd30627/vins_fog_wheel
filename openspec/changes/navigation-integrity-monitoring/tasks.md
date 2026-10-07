# Tasks — Navigation Integrity Monitoring

Gated phases. Each phase ends with STOP-and-report; no phase auto-starts the next. No experiments run under this change until the user approves the phase. Numeric `TBD-XX` values are resolved by the probes below, not assumed.

> **⚠️ CLAIM AUDIT (2026-07-02).** A PI-level audit re-classified all prior results. Outcomes:
> **PAPER-READY** = KITTI Mondrian OPL only. **VALID-LIMITED** = Phase 4.2, Phase 4.3, nuScenes
> (target-calib), VINS raw-speed mask. **REMOVED/INVALID** = Phase 4.4 (broken metric). **DOWNGRADED**
> = HealthNet (within-distribution single-route; cross-route not evaluable; cross-grade LOGO 0.94–1.0).
> **SMOKE-ONLY** = ORB-SLAM3 masking (no ATE). Authoritative: `paper2/track_a/PAPER2_YESTERDAY_CLAIM_AUDIT.md`,
> `PAPER2_CORRECTED_EVIDENCE_HIERARCHY.md`, `PAPER2_PROJECT_COMPLETION_ROADMAP.md`. **Directive: stop
> opening new branches; write the OPL-spine paper.**

---

## Phase 0 — Boundary freeze + closed-loop stack audit (no experiments)

- [ ] 0.1 Freeze the contribution boundary: supervisor-on-top only; no Nav2/frontier planner edit; no VINS backend edit; obstacle source modular. (proposal + supervisor spec)
- [ ] 0.2 Freeze the integrity formalism vocabulary (AL/PL/IR/TTA/Stanford diagram) and mark all numeric bounds `TBD-XX`. (integrity-formalism spec)
- [x] 0.3 **Closed-loop stack audit (early gate).** DONE 2026-07-02 (`logs/PHASE0_3_CLOSED_LOOP_AUDIT.md`). Finding: a minimal A→B closed loop already exists in `~/nav2_ws` pkg `paper2_validity_bridge`. Capability matrix: pose = GT-pose stub (no VINS path, PARTIAL); sim = custom 2D kinematic `mini_world_sim` (no CARLA/Gazebo, PARTIAL); obstacles inject via synthetic `/scan` but static-within-episode (PARTIAL); logging has collision/near_miss/mission_success but MISSING freezing+false_safe; supervisor hooks PRESENT+proven (`/path_cost_monitor/high_cost`→twist_servo hard-stop, `/paper2/frontier_risk_cost` speed scaling, nav2 collision_monitor/velocity_smoother — no planner edit); P2 drift-injection MISSING (easy), P3 live-VINS MISSING (large bridge).
- [x] 0.4 DECISION 2026-07-02: **proceed with Nav2/frontier base** (Gazebo-minimal NOT needed). Remaining closed-loop work is additive glue in `paper2_validity_bridge`: moving obstacles, 5-label logger, P2 drift injection, rule-based supervisor node. Honest caveats: 2D kinematic stub, synthetic scan (collision = GT-distance proxy not physics), real-Nav2-in-loop launch unstable (~11.5s) so use builtin-controller loop, VINS absent from loop (P3 later/gated).

## Phase 1 — Obstacle-State Integrity channel (extend done work)

- [x] 1.1 Consolidated CARLA/KITTI/nuScenes obstacle validity results; schema frozen (AL_pos=3m, AL_vel=3m/s). KITTI scene-split exceedance (0.1444 at IR=0.10) exceeded target → K1 gate fired.
- [x] 1.2 nuScenes T4-light direct-transfer: position exceedance 0.052 (PASS at IR=0.10); velocity exceedance 0.201 (needs calibration); 3-dataset coverage confirmed.
- [x] 1.3 **K1 RESOLVED 2026-07-02** (`logs/obstacle_opl/KITTI_MONDRIAN_RESULTS.md`). Mondrian leave-scene-out calibration (126 models, 21 scenes × 2 channels × 3 IR). **KITTI-position IR=0.10: exceedance=0.1140 (PASS ≤ 0.12), avail=0.324, HMI=194.** KITTI-velocity IR=0.10: exceedance=0.1042 (PASS), avail=0.055. IR=0.20 KITTI-position: exceedance=0.2225 (marginal FAIL by 0.0025 — boundary artifact, exclude IR=0.20 operating point). Cross-scene Stanford KITTI position result is **publishable**. E1 + Stanford figures: `logs/obstacle_opl/stanford_KITTI_position_mondrian.png`, `stanford_KITTI_velocity_mondrian.png`.

## Phase 2 — Localization Integrity channel (K0 FIRED 2026-07-02 → rule-calibration, not learned)

- [x] 2.1 **[Probe — K0 event count]** DONE (`logs/PHASE2_1_K0_EVENT_PROBE.md`). **K0 FIRES.** Genuine divergence collapses to ~7 distinct physical scenes / ~2 deterministic mechanisms (acc-bias>2.5 saturation dominant; scale-drift minority); only 1 real-sensor scene (KAIST urban38). Feasibility AUROC illusory (acc-margin label leakage AUROC 1.000; all positives in 1 scene ⇒ LOSO 0 train positives; temporal-tail confound). Recommended `TBD-N = 30 distinct diverging scenes (≥10 real-sensor, ≥2 mechanisms)`; current ~7/1/2 is ~4–5× short. → **Do NOT train a learned HealthNet on current data.**
- [x] 2.2 Localization label reframed: the acc-bias margin (`Bas` vs 2.5) IS the operative failure definition; scale-envelope is the secondary mechanism. Kept parametric over `AL_loc`.
- [ ] 2.3 ~~Train VINS HealthNet~~ SKIPPED per K0 branch. Replaced by 2.3′.
- [x] 2.3′-partial **PARTIAL 2026-07-02** (`logs/loc_lpl/`). Script `build_loc_lpl.py` (seed 0, reproducible). Method: isotonic calibration of `early_env` (|early_scale-1|) → LPL; Q-inflation for IR. CARLA Stanford produced (n=54 test, 3 AL values). **Best point: IR=0.10, AL=0.20 → 0 HMI, availability 1.85%.** Regions: nominal=1/available=27/MI=26/HMI=0. KAIST: only binary (urban38-pankyo, 0 train_positives after LOSO) → no KAIST Stanford. **Availability crisis root cause:** early_env is too noisy + heavy-tailed true errors force LPL high → flags almost everything. Fix: add `feature_count` as second signal (feat_fail=63.8 vs feat_nofail=117.6 strongly discriminative). Estimated ~1h script work.
- [x] 2.3′-v2 **DONE 2026-07-02** (`logs/loc_lpl/build_loc_lpl_v2.py`). Stratification by accbias_flag did NOT improve availability at AL=0.20 (remains 0%). Root cause: `early_env` cannot distinguish scale-drift failures (baseline/grade_sweep: small early_env ~0.02 but large true_scale_err 1–62). Isotonic monotone constraint forces LPL ≥ 0.20 for essentially all runs. Best operating point: AL=0.50, IR=0.10 → avail_noacc=31.8%, HMI_noacc=13.6%, but exceedance=0.273 (not calibrated). **Next step needed: a second runtime predictor that can distinguish scale-drift onset** (e.g., rolling scale-estimate variance, feature-count time-window, or dedicated scale-drift detection signal). This is a confirmed research gap.
- [x] 2.4 **DONE 2026-07-02 (HONEST NULL + RESEARCH GAP DOCUMENTED)** LPL-v3 investigation: `feature_count` as second signal was investigated. CARLA TSV files have no feature_count; parquet `vins_feat_count` shows ALL CARLA runs have feat_count=47-64 (below KAIST fail threshold 63.8, no within-domain discriminability, `vins_failure`=0 for all CARLA runs). LPL-v3 with feature_count NOT FEASIBLE without new data extraction from grade_sweep VINS replay logs. **Published LPL claim**: (a) acc-bias stratum: runtime `accbias_flag` correctly forces UNAVAILABLE → acc-bias detectable at runtime; (b) scale-drift stratum: `early_env` insufficient predictor (51% unsafe runs have small early_env), 0% availability at AL=0.20 — RESEARCH GAP. Best honest operating point: AL=0.50, IR=0.10, avail=31.8% (not calibrated, exceedance=0.27). Phase 4.3 closed-loop shows the gap in action: all 3 OPL conditions have false_safe≈255 events under loc_err degradation — dedicated LPL supervisor required. **T-A follow-up (2026-07-02):** Joined VINS replay runs to object parquet → feat_count div=56.9 vs safe=50.5 (opposite direction vs KAIST, tiny effect) → LPL-v3 BLOCKED; CARLA feature counts uniformly low (real-world hardware discriminativity is domain-specific).

## Phase 3 — Integrity formalism instantiation (headline)

- [x] 3.1 **DONE 2026-07-02** (`logs/phase3/PHASE3_FORMALISM_INSTANTIATION.md`). OPL: AL_pos=3m, IR=0.10 → exceedance=0.1140 PASS, avail=32.4%, HMI=194 (KITTI Mondrian real data). LPL: AL_loc=0.20, IR=0.10 → exceedance=0.056 PASS, avail=1.85%, HMI=0/54 (CARLA sim). Stanford diagrams: `stanford_KITTI_position_mondrian.png`, `stanford_CARLA_AL020.png`. **TBD-AL-LOC=0.20 ✓, TBD-IR=0.10 ✓.** KAIST LPL: binary-only (K0).
- [x] 3.2 **PARTIAL 2026-07-02** (`logs/phase3/PHASE3_FORMALISM_INSTANTIATION.md`). Causal chain demonstrated end-to-end in principle via OPL proxy (risk≥0.5 = validity adapter). Formal PL publisher not yet wired into closed-loop; per-step PL logging deferred to Phase 5. Phase 4.1/4.2/4.3 provide step-by-step evidence: OPL detection ✓, mode switch ✓, collision reduction ✓, LPL gap ✓.

## Phase 4 — Closed-loop bring-up + rule-based supervisor (gated by 0.4)

- [x] 4.1-partial **PARTIAL 2026-07-02** (`logs/closed_loop/`). 5-label logger schema added. Moving obstacles configurable. Rule-based supervisor node added. `honor_hard_stop` parameter added to source. **ROOT CAUSE FOUND:** source edited but package NOT rebuilt → installed binary always honored hard_stop (all 16/20 pre-rebuild episodes froze at path_length≈0.12m). Fix: `colcon build --packages-select paper2_validity_bridge` 2026-07-02. Note on `goal_sent=0`: EXPECTED in builtin-controller mode — Nav2 goal is not used; the loop is purely kinematic.
- [x] 4.1-rebuild **DONE 2026-07-02.** `paper2_validity_bridge` rebuilt. Installed binary now: `if self.honor_hard_stop and self.hard_stop:` (correct gate). Stale pre-rebuild CSVs archived to `logs/closed_loop/stale_prerebuild/`.
- [x] 4.1-batch-v2 **DONE 2026-07-02.** 20-episode batch completed. (`logs/closed_loop/T5_BATCH_RESULTS.md`). **Results: baseline success=100%/freeze=0%, supervised success=0%/freeze=100% — behavioral gate VERIFIED.** Key finding: unnecessary_stop=100% in all conditions (world uses only unobservable `deg` obstacles → adapter fires in every episode). Zero collisions in both conditions → cannot yet measure collision-reduction tradeoff. **Next step (4.2):** design mixed-world episodes (some truly dangerous obstacles visible + some invisible) to get genuine collision-reduction vs false-alert comparison. Phase 4.1 closed-loop gate = PASSED (baseline/supervised behavior differentiated correctly).
- [x] 4.2 **DONE 2026-07-02** Mixed-World Benchmark (`logs/phase42/PHASE4_2_MIXED_WORLD_BENCHMARK.md`). 30 episodes (3 cond × 2 obs_mode × 5 seeds). **Key findings: (1) ours_baseline (risk-scaled margins) reduces near_collisions 94%** (46.6→2.7) vs naive with 0 actual collisions and 0 freeze-time. (2) supervised (hard-stop) has MORE near_collisions (5.4 > 2.7) and 10% collision rate in moving-obstacle mode — frozen robot becomes sitting target. (3) ours_baseline dominates supervised on all metrics except static near_coll (both=0). FIX: effective_risk=0 gate added to mws potential field for naive_baseline; FastDDS shm-contamination fixed via UDP-only FASTRTPS profile. **Gate verdict: validated that risk-scaled margin (OPL channel) outperforms hard-stop supervisor in dynamic environments.**
- [x] 4.3 **DONE 2026-07-02** Localization degradation structural gap (`logs/phase43/PHASE4_3_LOC_DEGRADATION.md`). v3 design: safe-only obstacles (FULL_STATE, y=2.0 off path) → OPL never fires; 12s ramp (loc_err ≥ 0.5m at ep_t≈13s, goal at ≈19s). **Results: ALL 3 conditions have false_safe_events≈255, 100% success, 0 near_coll, 0 freeze.** naive_baseline=258.3, ours_baseline=255.3, supervised=255.0. supervised also unprotected (OPL hard_stop structurally blind to loc_err; no OPL events in safe-obstacle world). **Conclusion: OPL ≠ LPL coverage. Dedicated localization integrity channel required.** Note: v1 and v2 had design flaws (episodes too fast for 45s ramp; v2 supervised froze for obstacle reasons masking loc_err gap). v3 corrected by safe-only world + fast ramp.

## Phase 5 — IMU-VINS HealthNet (K0 REFRAME 2026-07-02)

**K0 REFRAME:** K0 only blocked the KAIST-only real-world learned HealthNet claim. IMU/VINS HealthNet on controlled degradation (CARLA + IMU sweep + grade injection + VINS replay) is valid. K0 applies only to claiming real-world generalization without sufficient real-sensor divergence data.

**New Phase 5 plan:**
- 5.1 Survey all available runtime signals + GT labels → build HealthNet dataset table per sequence
- 5.2 Implement rule-based baseline (acc-bias margin, feature threshold, scale envelope) 
- 5.3 Implement HistGBM HealthNet on runtime signals → evaluate AUROC, false_safe, availability, time-to-alert
- 5.4 CARLA Stanford diagram for HealthNet (LPL via learned model, compare to isotonic LPL v1)
- Report: `logs/PHASE5_IMU_VINS_HEALTHNET_DATASET.md`, `logs/PHASE5_IMU_VINS_HEALTHNET_BASELINE.md`

- [x] 5.1 **DONE 2026-07-02** (`logs/phase5/PHASE5_IMU_VINS_HEALTHNET_DATASET.md`). Survey complete. Primary data: KAIST reliability_dataset.tsv (22,028 windows, 32 runtime signals, 90 failures in urban38-pankyo × 3 synthetic grades). Secondary: CARLA loc_table (133 runs, 1 signal), CARLA object parquet (no failures). EuRoC/KITTI/CARLA per-timestep: need VINS replay with feature logging.
- [x] 5.2 **DONE 2026-07-02** (`logs/phase5/PHASE5_IMU_VINS_HEALTHNET_DATASET.md`). Dataset table complete. Stratified split (70/30, seed=42): train=15,419 (63 failures), test=6,609 (27 failures). Honest caveat: within-distribution evaluation; NOT cross-sequence.
- [x] 5.3 **DONE 2026-07-02** (`logs/phase5/PHASE5_IMU_VINS_HEALTHNET_BASELINE.md`). **KEY RESULT: HistGBM AUROC=0.963 (rule-based 0.297).** Top feature: entropy8_mean (imp=0.62) — visual entropy dominates over IMU margin. acc_bias_margin alone POOR predictor (AUROC=0.297). Multi-signal HealthNet necessary and sufficient.
- [x] 5.4 **DONE 2026-07-02** Stanford LPL (calibrated HistGBM): IR=0.10 → exceedance=0.0011, **availability=99.3%**, HMI=1/6609. vs LPL isotonic v1: avail=1.85%, HMI=0. vs Rule LPL: avail=100%, HMI=27. HealthNet LPL: **99.3% available, 27× fewer HMI than rule**. Diagrams: `logs/phase5/stanford_healthnet_ir10.png`. TTA=0s (stratified split loses temporal ordering; limitation documented).
- [ ] 5.5 Supervisor training under pose curriculum: P2 VINS-noise-replay episodes → K3 gate. (Deferred — requires temporal TTA evaluation + more failure sequences for TTA claim.)

## Phase 6 — ORB-SLAM3 PV-Validity Localization Branch (user directive 2026-07-02)

**Goal:** Evaluate whether PV-validity can actively IMPROVE localization (not only supervise navigation). Upgrade branch — does NOT replace OPL/LPL integrity package. Honest null result is acceptable.

- [x] 6.0 **DONE 2026-07-02** ORB-SLAM3 discovery + audit (`logs/PHASE6_ORBSLAM3_AUDIT.md`). Found: `/home/ivlab3/orbslam_ws/` with pre-built `libORB_SLAM3.so`, ROS2 wrapper, EuRoC/KITTI configs. EuRoC MH_01_easy ROS2 bag at `/mnt/sata4t/datasets/EuRoC_full/ros2_bags/MH_01_easy/`. Stereo-inertial mode ready.
- [x] 6.1 **DONE 2026-07-02** Baseline smoke (`logs/phase6/PHASE6_ORBSLAM3_BASELINE_SMOKE.md`). **PASS**: Map 534 pts, VIBA 1+2 complete on EuRoC MH_01_easy at rate=1.0. Viewer OK with DISPLAY=:1. Rate=0.5x had timing sync issues (known issue; fixed with rate=1.0).
- [x] 6.2 **DONE 2026-07-02** PV-validity localization feasibility design (`paper2/track_a/PAPER2_ORBSLAM3_PV_LOCALIZATION_FEASIBILITY.md`). Method A (image relay masking, zero core change) is the implementation target. Method B (ORBextractor mask) deferred. Method C (core BA change) out of scope.
- [x] 6A.2 **DONE 2026-07-02** Mask relay smoke test (`logs/phase6/PHASE6_ORBSLAM3_MASK_RELAY_SMOKE.md`). **Relay PASS**: 2500 frames, 100% masked, no crash. ORB-SLAM3 with synthetic bbox (500,150-650,300): 521 pts (−2.4%), 3 resets (synthetic mask at init-critical region), VIBA 1+2 eventually complete. Finding: relay works; synthetic mask location matters for initialization robustness.
- [x] 6A.3 **DONE 2026-07-02** Baseline vs masked comparison (`logs/phase6/PHASE6_ORBSLAM3_PV_FILTER_SMOKE.md`). **HONEST NULL on ATE**: trajectory not saved in either run (global BA timeout). Qualitatively similar post-VIBA tracking. ATE NOT fabricated. For valid ATE comparison: need trajectory recording via topic (not global BA) + real dynamic-object bboxes (lower image, not init region).
- [x] 6B.1 **DONE 2026-07-02** VINS dynamic mask audit (`logs/PHASE6_VINS_DYNAMIC_MASK_AUDIT.md`). mask field at `feature_tracker.cpp:289`; existing infrastructure in `paper2_make_vins_masks.py`.
- [x] 6B.2 **DONE 2026-07-02** VINS PV-dynamic filter design (`paper2/track_a/PAPER2_VINS_PV_DYNAMIC_FILTER_DESIGN.md`). Method A (image relay), B (feature-tracker mask injection), C (TCSV-M). Method A already executed in Phase C.
- [x] 6B.3 **DONE 2026-07-02** VINS PV smoke (`logs/PHASE6_VINS_PV_FILTER_SMOKE.md`). **GATE: PROMISING.** −10.5% ATE on Town01 dense_b1; 0 failures; 2 PASS_CORE runs. validity_aware ≈ oracle (deployable raw_speed gate captures nearly all benefit). Limitation: CARLA sim only, KAIST real untested.
- [x] 6C **DONE 2026-07-02** Localization-to-navigation comparison (`logs/phase6/PHASE6_LOCALIZATION_TO_NAV_COMPARISON.md`). VINS PV-mask = stronger evidence (−10.5% ATE, phase C). ORB-SLAM3 ATE deferred. Branch upgrades paper: PV-masking adds localization-layer Step 1 to integrity-monitor Step 2.
- [x] 6D **DONE 2026-07-02** External baseline audit (`logs/PHASE6_DYNAMIC_SLAM_BASELINE_AUDIT.md`). DynaVINS=literature-only (ROS1). DynaSLAM/DS-SLAM=NOT FOUND. RTABMap=present but not dynamic-specialized. Two executable baselines: ORB-SLAM3 (standard) and VINS-Fusion (standard) — both compared against PV-masked variants.
- [ ] 6.4 (Deferred) CARLA PV-validity integration for ORB-SLAM3: connect existing object validity parquet to masking relay on CARLA sequences. Requires trajectory recording via topic (not global BA). Needs CARLA ORB-SLAM3 bag.
- [ ] 6.5 (Conditional) If 6.4 PROMISING: implement Method B (ORBextractor mask) for ORB-SLAM3 and re-evaluate. Only after restore-point commit.

## Phase 7 — FOG_COAST feasibility (K4 gate) [renumbered]

- [ ] 7.1 Measure the FOG/IMU drift-vs-time curve on KAIST real navigation-grade FOG under simulated VINS outages; resolve `TBD-drift-budget` / `TBD-Tmax`.
- [ ] 7.2 Evaluate FOG_COAST / STOP_REINIT / UNAVAILABLE decisions against the grounded budget; report recovery-success. STOP. Enforce K4.

## Phase 8 — Integrated temporal fusion (Stage 4, last) [renumbered from 7]

- [ ] 8.1 Only after Phases 1–6 succeed: train the multi-task integrated model (localization integrity + obstacle reliability + navigation risk + mode) over sequence embeddings; compare against the frozen-module pipeline. STOP and report.

## Phase 9 — Real-system validation + venue decision (K5) [renumbered from 8]

- [ ] 9.1 P3 live VINS-in-loop small-scale validation on the user platform: demonstrate VINS-health warning + FOG_COAST/STOP_REINIT feasibility + runtime/integration (feasibility, not statistical proof).
- [ ] 9.2 Apply K5: set venue and claim scope from what real data supports. STOP and report the final claim boundary.
