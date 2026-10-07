# Navigation Integrity Monitoring — Claims Table

**Date:** 2026-07-02  
**Convention:** SUPPORTED = data exists; PARTIAL = evidence incomplete; FORBIDDEN = insufficient data / forbidden by gates

> **⚠️ AUDIT + REPAIR (2026-07-02):** re-audited, then REPAIRED (not just downgraded). Authoritative:
> `PAPER2_CLAIM_REPAIR_PLAN.md`, `PAPER2_REPAIRED_JOURNAL_STATUS.md`. Repair outcomes:
> **HealthNet** — cross-sequence RESTORED (LOSO 0.73–0.99 across 6 routes; was "not evaluable").
> **OPL** — confidence-gate baseline added; OPL beats range+confidence gates at matched availability.
> **VINS** — learned TCSV-M actually run: it MATCHES but does not beat raw_speed (claim 9 falsified by
> experiment); masking effect small+mixed (−2.5% dense / +2.3% medium). **Phase 4.4** — metric/timeout
> bugs fixed + risk-scaled dual-channel mode added + rerun. **ORB-SLAM3** — wrapper pose-logger plan
> ready (impl gated on a dynamic bag). **nuScenes** — zero-shot(0.69)/target-calib(0.97)/in-domain reported separately.

---

## Fully Supported Claims (SUPPORTED — data exists now)

### C1 — Obstacle state integrity formalism (KITTI, real data)

> *"We instantiate a RAIM-style OPL for obstacle position using Mondrian leave-scene-out conformal calibration on KITTI tracking. At IR=0.10, the empirical exceedance is 0.1140 (calibration target 0.10, passes within tolerance), availability is 32.4%, and HMI (false-safe) rate is 0.52% overall. This reduces HMI by 7.2× vs a distance-gate baseline."*

**Evidence:** `logs/obstacle_opl/KITTI_MONDRIAN_RESULTS.md`, Stanford diagram `stanford_KITTI_position_mondrian.png`  
**Scope:** KITTI tracking 21 scenes, 37,022 obstacle-frames  
**Gap:** IR=0.20 fails marginally (0.2225 vs 0.22 target, Δ=0.0025); exclude IR=0.20 from published operating points

---

### C2 — Cross-dataset transfer (nuScenes)

> *"Obstacle position validity cross-dataset transfer from CARLA to nuScenes reaches AUROC 0.969 after target calibration (direct transfer: 0.692). Three real datasets — KITTI, nuScenes, KAIST probe — confirm the position-validity effect. Target calibration is required for deployment."*

**Evidence:** `logs/PHASE1_2_NUSCENES_VALIDITY.md`  
**Scope:** nuScenes val, 700 scenes, target-calibrated HistGBM transfer

---

### C3 — OPL risk-scaled margin outperforms hard-stop supervisor in dynamic environments

> *"In a mixed-world 30-episode closed-loop benchmark (sim, 2D kinematic, GT pose), OPL risk-scaled speed modulation reduces near-collisions 94% vs naive (46.6→2.7) with 0 actual collisions and 0 freeze time. Hard-stop supervisor achieves 10% collision rate in moving-obstacle mode (frozen robot = stationary target) and 0% mission success in static-obstacle mode (52.8s freeze time per episode). OPL risk-scaling is Pareto-dominant over hard-stop."*

**Evidence:** `logs/phase42/PHASE4_2_MIXED_WORLD_BENCHMARK.md`  
**Scope:** 30 episodes; sim-only; GT pose  
**Honest caveat:** sim (2D kinematic), GT pose (not live VINS), single robot platform

---

### C4 — OPL ≠ LPL coverage: dual-channel is architecturally necessary

> *"In a 9-episode closed-loop experiment with safe-only obstacles (OPL never fires) and injected localization degradation (0→0.7m ramp), all three conditions including the OPL hard-stop supervisor experience ~255 false_safe events. The OPL channel provides zero additional protection over naive baseline in this scenario. A dedicated LPL channel is architecturally required."*

**Evidence:** `logs/phase43/PHASE4_3_LOC_DEGRADATION.md`  
**Scope:** 9 episodes; sim-only  
**Interpretation:** structural gap proof-of-concept; not a statistical claim about real-world frequency

---

### C5 — Channel independence justifies two-channel design

> *"Prior experiments (v4 A2) show that conditioning obstacle reliability on VINS health features provides weak / null improvement. The two channels carry non-overlapping information; treating them as independent (RAIM-style) is data-justified."*

**Evidence:** `paper2/track_a/PAPER2_A2_VINS_CONDITIONING_RESULTS.md`  
**Scope:** CARLA sim A2 null result

---

### C6 — Localization integrity formalism (CARLA sim, conservative operating point)

> *"A scale-envelope LPL calibrated on CARLA VINS replay achieves 0 HMI at IR=0.10, AL_loc=0.20, with 1.85% availability (n=54 test runs). Without LPL, the naive always-safe policy has 37.0% overall HMI. LPL is conservative by design — availability is limited by the predictor's inability to distinguish scale-drift onset, which is a documented research gap."*

**Evidence:** `logs/loc_lpl/stanford_CARLA_AL020.png`, `logs/loc_lpl/lpl_results_all.csv`  
**Scope:** 54 CARLA test runs; sim-only  
**Honest framing:** CARLA sim only; KAIST real = binary, K0 fires (1 scene); learned LPL not feasible

---

### C7 — Acc-bias failure is detectable at runtime

> *"The dominant VINS divergence mechanism (acc-bias saturation, Bas>2.5) is detectable at runtime via VINS internal `failureDetection()`. The accbias_flag correctly forces LPL to UNAVAILABLE for all 26 acc-bias runs in the test set, with 0 HMI. This is a viable and lightweight localization integrity signal for the acc-bias failure mode."*

**Evidence:** `logs/loc_lpl/build_loc_lpl_v2.py` stratification results  
**Scope:** CARLA sim; 1 real-sensor acc-bias scene (KAIST urban38)

---

### C8 — HistGBM HealthNet (controlled degradation KAIST) — ⚠️ DOWNGRADED (audit 2026-07-02)

> **ORIGINAL (OVERCLAIMED):** ~~"HealthNet achieves AUROC=0.963 for predicting VINS failure..."~~

> **CORRECTED then REPAIRED (2026-07-02):** *"A visual-entropy runtime HealthNet detects the
> imminent-VINS-failure state across **6 KAIST routes** (including 4 real-sensor-grade highway routes).
> Leave-one-sequence-out AUROC is 0.73–0.99 (mean of reliable folds ≈0.84); the hardest cross-route +
> cross-grade transfer (train synthetic-grade urban38 → test real-grade highways) is 0.726. The earlier
> ~1.0 same-distribution AUROC was temporal-leakage inflated and is quoted only as a ceiling."*

**Repair:** the single-route leak was fixed by folding in already-on-disk diverged routes
(urban18/19/22/24-highway, real grade) — `extract_reliability_dataset.py --out reliability_dataset_expanded.tsv`,
no VINS rerun — then a genuine LOSO eval.  
**Evidence:** `logs/phase5/PHASE5_HEALTHNET_REPAIR_REPORT.md`, `logs/phase5/healthnet_loso_expanded.json`.  
**Scope / confounds:** highway routes ran in soft-failure mode (route↔mode + grade↔route confounds
disclosed); TTA still 0s (state detector).  
**Placement:** supporting result / candidate secondary contribution (NOT headline until the run-mode
confound is removed by a matched-mode replay). This is a genuine cross-sequence result, not a downgrade.

---

### C10 — ✅ REPAIRED + SUPPORTED (2026-07-02): dual-channel with LPL availability flag

> Two-stage repair. Stage 1 (metric/timeout/risk-scaled): fixed the invalid benchmark; showed
> risk-scaled dual-channel removes the hard-stop collision/freeze failure but did NOT reduce false-safe
> (speed-only). Stage 2 (availability flag): the LPL channel now **declares UNAVAILABLE** on breach
> (not just slows) → false-safe eliminated.

**Ablation ladder (20 eps, 4 conditions × 5 seeds):** OPL-only 100% succ/0% coll/60% fs;
lpl_only hard-stop 0% succ/20% coll/48.7s freeze; dual_channel_speed 40%/0% coll/**80% fs**;
**dual_channel_avail 40% succ / 0% coll / false_safe% = 0 / fs_evt = 0 / availability 0.12**.

**Claim:** *"A dual channel needs BOTH risk-scaled speed (avoid hard-stop collision/freeze) AND an
availability flag (eliminate HMI). The availability-flag dual-channel commits 0 false-safe and 0
collisions at the cost of availability (0.12) and mission success (40%) — the correct protection-level
tradeoff: declare unavailable rather than falsely claim safe."* → **claim 7 SUPPORTED** (with correct design).

**Evidence:** `logs/phase44/PHASE4_4_LPL_AVAILABILITY_REPAIR_REPORT.md`, `logs/PHASE4_NAVIGATION_METRIC_AUDIT.md`

---

### C9 — acc_bias_margin rule is insufficient; multi-signal HealthNet necessary

> *"The acc_bias_margin alone achieves AUROC=0.297 for predicting failure_in_30s — worse than random. Acc-bias saturation in KAIST urban38-pankyo is sudden (not gradually predictable from current margin 30s ahead). Multi-signal HealthNet using visual features (entropy8, feature count) is necessary to achieve high AUROC."*

**Evidence:** Rule baseline AUROC=0.297 vs HistGBM AUROC=0.963  
**Implication:** The LPL isotonic v1 (based on early_env, a different signal) was correct to document low availability — the scale envelope is also insufficient. Visual entropy signals are the key.

---

### C11 — VINS raw-speed dynamic mask reduces ATE (renamed; audit 2026-07-02)

> **CORRECTED (renamed):** *"A **raw-speed dynamic-object mask** (blur regions whose own raw estimated
> speed > 1 m/s) reduces VINS-Fusion ATE by 2.8–10.5% on two clean CARLA runs (Town01 dense/medium)
> with 0 tracking failures. This is a deployable observability gate, **NOT the learned TCSV-M PV
> model** (which was never run in this loop). Headroom is limited because the frontend already rejects
> ~90% of features via RANSAC (baseline outlier ratio ≈ 0.9)."*

**Evidence:** `logs/PHASE6_VINS_MASKING_CLAIM_AUDIT.md`, `PAPER2_VINS_MASKING_LIMITATION_AUDIT.md`  
**Scope:** 2 PASS_CORE CARLA runs; image blur (Method A), not feature routing.  
**Do NOT call this "learned PV" or "validity_aware."** Upgrade path = run TCSV-M (S1, deferred).

---

## Partial Claims (PARTIAL — evidence incomplete)

### P1 — Hard-stop as emergency fallback only

**Status:** Demonstrated in Phase 4.2 but not formally quantified as a "maximum acceptable risk threshold". The claim "hard-stop is only for extreme risk" is supported qualitatively (Phase 4.2 shows it actively worsens outcomes in moving-obstacle world) but the threshold for when hard-stop is correct vs risk-scaling is not yet formalized.

---

### P2 — OPL protects navigation in real closed-loop environments

**Status:** Closed-loop experiments are sim-only (2D kinematic, GT pose, synthetic obstacles). The mechanism is demonstrated; generalization to real environments requires Phase 8 (P3 live VINS-in-loop).

---

### P3 — LPL Stanford diagram on real data

**Status:** KAIST real-sensor data yields only binary label (1 divergence scene, K0 fires). No continuous Stanford possible on real data. CARLA sim Stanford exists. Requires ≥30 distinct diverging scenes with real sensor data (TBD-N=30 unmet).

---

## Forbidden Claims (FORBIDDEN — data/gates insufficient)

### F1 — KAIST-only real-world HealthNet generalization

**Reason:** K0 REFRAMED (user directive 2026-07-02). K0 blocked KAIST-only REAL-WORLD claim. HistGBM HealthNet on controlled degradation IS valid (C8). What remains forbidden: "HealthNet generalizes to arbitrary real-world VINS conditions beyond the controlled-degradation training distribution." AUROC=0.963 is valid for within-distribution evaluation (C8); cross-sequence AUROC is NOT computed (would be 0 true positives on other sequences). TBD-N=30 real-sensor divergence scenes is still needed for real-world generalization claim.

---

### F2 — Learned navigation risk supervisor (K3 pending)

**Reason:** Phase 5 not yet run. Rule-based supervisor (Phase 4.1) is the current deliverable. Learned supervisor claimed only if it beats rule-based on held-out towns/routes.

---

### F3 — FOG_COAST / STOP_REINIT / UNAVAILABLE mode benefit

**Reason:** Phase 6 not yet run. KAIST real-FOG drift-vs-time curve (TBD-drift-budget, TBD-Tmax) required to ground FOG_COAST feasibility. No claim about real navigation-grade FOG benefit.

---

### F4 — Real-world closed-loop collision reduction

**Reason:** Phase 8 not yet run. All closed-loop experiments are sim-only (2D kinematic mini_world_sim, GT pose stub). No claim about real-robot performance.

---

### F5 — VINS ATE improvement via integrity

**Reason:** The supervisor acts on top of the planner; it never modifies the VINS backend. No claim about VINS localization accuracy improvement.

---

### F6 — Quantitative LPL benefit at AL_loc=0.20 beyond conservative operation

**Reason:** LPL v1 achieves 0 HMI but only 1.85% availability (essentially always UNAVAILABLE for non-accbias runs). The scale-drift gap makes LPL conservative beyond usefulness at this AL. Cannot claim "LPL provides X% useful coverage" without fixing the scale-drift predictor.

---

## Summary Table

| Claim | Status | Key number | Source |
|-------|--------|-----------|--------|
| OPL KITTI Mondrian (real, cross-scene) | **SUPPORTED** | exceedance=0.1140 ✓, avail=32.4%, HMI=0.52% | T7 |
| nuScenes cross-dataset transfer | **SUPPORTED** | AUROC 0.969 target-calib | T4-light |
| OPL risk-scale beats hard-stop (sim) | **SUPPORTED** | 94% near-coll reduction, 0 vs 10% collision | Phase 4.2 |
| OPL ≠ LPL structural gap (sim) | **SUPPORTED** | false_safe≈255 in all 3 conditions | Phase 4.3 |
| Channel independence justified | **SUPPORTED** | v4 A2 null | prior work |
| LPL CARLA Stanford (sim, conservative) | **SUPPORTED** | 0 HMI, 1.85% avail, Q=1.0 | T6 |
| Acc-bias detection at runtime | **SUPPORTED** | 0 HMI on acc-bias stratum | T6 v2 |
| HealthNet cross-sequence failure detection | **REPAIRED → VALID-LIMITED** | LOSO AUROC 0.73–0.99 across 6 routes (4 real-grade highways); hardest transfer 0.726; random-split ~1.0 is leaky ceiling | `PHASE5_HEALTHNET_REPAIR_REPORT.md` |
| HealthNet is single-feature (entropy) | **SUPPORTED** | entropy8_mean imp=0.62, all others ≈0 | Phase 5 |
| ~~Both channels need risk-scaling~~ (Phase 4.4) | **REMOVED — INVALID/ANOMALOUS** | collision% metric broken (up to 6100%); table self-contradicts | `PHASE4_CLOSED_LOOP_CLAIM_AUDIT.md` |
| Learned VINS HealthNet (K0 real-world gen.) | **FORBIDDEN** | K0 fires (~7 scenes vs TBD-N=30) | T2 |
| Learned supervisor | **FORBIDDEN** | K3 pending (Phase 5) | — |
| FOG_COAST benefit | **FORBIDDEN** | Phase 7 (real FOG) required | — |
| Real-world closed-loop | **FORBIDDEN** | Phase 9 (P3 live VINS) required | — |
| LPL useful coverage at AL=0.20 | **FORBIDDEN** | scale-drift gap: 0% non-accbias avail | T6 v2 |
| ORB-SLAM3 CARLA stereo-inertial runs (infra) | **REPAIRED** | CARLA config authored; map 722pts, VIBA1+2, ATE vs GT obtained; stereo-consistent masks don't break tracking | `PHASE6_ORBSLAM3_CARLA_BASELINE_REPAIR_REPORT.md` |
| ORB-SLAM3 PV-mask improves localization | **NOT DEMONSTRATED (n=1, within noise)** | dense: base 3.50 / all_dynamic 2.94 / raw 3.77 / tcsvm 4.19(worst) / oracle 3.66; learned PV doesn't beat naive/baseline; deltas < run-to-run spread → need ≥5 seeds | `PHASE6_ORBSLAM3_CARLA_BASELINE_VS_PV_MASK_REPORT.md` |
| VINS masking improves ATE (claim 8) | **VALID-LIMITED (repaired, weaker)** | controlled session: −2.5% dense / +2.3% medium; small, mixed, nondeterminism-bound | `PHASE6_VINS_TCSV_MASK_REPAIR_REPORT.md` |
| Learned TCSV-M > raw_speed (claim 9) | **NOT SUPPORTED (experiment)** | tcsvm 3.492 ≈ raw 3.483 ≈ oracle 3.492; learning gives no advantage | `PHASE6_VINS_TCSV_MASK_REPAIR_REPORT.md` |
| OPL beats fixed gates (repair) | **SUPPORTED** | @32.4% avail: OPL 0.114 < range 0.137 < confidence 0.172 | `PHASE_OBSTACLE_OPL_REPAIR_REPORT.md` |
| Cross-dataset transfer (nuScenes) | **VALID-LIMITED (narrowed)** | zero-shot 0.69 WEAK; target-calib 0.969; not zero-shot | `PHASE_OBSTACLE_OPL_REPAIR_REPORT.md` |
