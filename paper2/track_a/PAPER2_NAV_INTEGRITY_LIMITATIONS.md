# Navigation Integrity Monitoring — Limitations & Honest Assessment

**Date:** 2026-07-02  
**Purpose:** Explicit limitations for paper writing — what cannot be claimed, why, and what would be needed to fix each.

---

## L0 — Audit-added limitations (2026-07-02 PI review)

These were surfaced by the yesterday-claim audit and take precedence over any earlier optimistic text.

| # | limitation | consequence |
|---|-----------|-------------|
| L0a | **HealthNet failures are on ONE route** (urban38-pankyo, 90/90); real-sensor grade has 0 failures. Leave-one-sequence-out is undefined. | No cross-route / real-world HealthNet generalization can be claimed or even measured. Random-split AUROC (~1.0) is temporal-leakage inflated. Only cross-grade transfer (0.94–1.0, one route) is defensible → appendix. |
| L0b | **VINS mask is a raw-speed gate on blurred images**, not the learned TCSV-M and not feature-level routing; 2 clean CARLA runs; frontend already rejects ~90% of features. | Must be called "raw-speed dynamic mask". ATE gain (2.8–10.5%) is real but small and limited-headroom. No "learned PV" claim. |
| L0c | **Phase 4.4 is invalid** (broken `collision%` metric up to 6100%; table contradicts its own conclusion; n=3). | Removed from the package. Dual-channel-risk-scaling insight rests on Phase 4.2 only. |
| L0d | **ORB-SLAM3 masking has no ATE** (wrapper publishes nothing; trajectory only via a global BA that hangs). | Smoke/infra only. No localization claim. A wrapper pose-logging change is required to ever produce ATE. |
| L0e | **nuScenes zero-shot transfer is weak (0.69)**; only target-calibrated reaches 0.969. | Claim is "replicates with target calibration", not zero-shot cross-dataset transfer. |
| L0f | **KITTI OPL availability is 32.4%** and per-scene exceedance varies widely (several scenes fail individually); IR=0.20 fails. | Report availability + per-scene spread honestly; publish IR=0.05/0.10 only. |

See `PAPER2_YESTERDAY_CLAIM_AUDIT.md` and `PAPER2_CORRECTED_EVIDENCE_HIERARCHY.md`.

---

## L1 — Closed-loop experiments are simulation-only (sim-to-real gap)

**What was done:** All closed-loop experiments (Phase 4.1/4.2/4.3) use `mini_world_sim` — a 2D kinematic simulator with GT pose, synthetic lidar scan, and simplified obstacle dynamics. No physics engine, no real sensor noise, no actual VINS, no real robot.

**Impact:** Cannot claim real-world collision reduction. Cannot claim the OPL supervisor generalizes to real environments. The mechanism is demonstrated; its real-world benefit is not.

**Honest framing:** "Simulated closed-loop experiments (2D kinematic, GT pose, synthetic obstacles) demonstrate the causal mechanism; real-world validation is future work (P3 live VINS-in-loop)."

**What would fix it:** Phase 8.1 — P3 live VINS-in-loop small-scale validation on the user platform.

---

## L2 — GT pose stub (no live VINS in closed-loop)

**What was done:** The closed-loop uses a GT pose stub. The robot "knows" where it is perfectly. The LPL channel cannot be tested in the loop under real VINS uncertainty.

**Impact:** Phase 4.3 proves OPL ≠ LPL structurally (by injecting artificial loc_err = proxy), but the test is synthetic. Real VINS divergence in the loop would require live VINS (P3).

**Honest framing:** "Localization degradation is injected synthetically in the closed-loop. The structural gap between OPL and LPL is demonstrated architecturally; real VINS divergence in the navigation loop is deferred to future work."

**What would fix it:** P2 VINS-noise replay injection → P3 live VINS-in-loop (Phase 5/8).

---

## L3 — LPL availability crisis: scale-drift gap

**What was done:** LPL v1 achieves 0 HMI at IR=0.10, AL_loc=0.20, but only 1.85% availability. The early_env predictor (`|scale_early−1|`) cannot distinguish scale-drift failures from safe runs: 48.6% of non-accbias unsafe CARLA runs have small early_env (~0.02) but large true_scale_err (1–62×). The isotonic monotone constraint forces LPL ≥ AL for essentially all runs.

**Impact:** LPL is conservative to the point of uselessness for the scale-drift stratum. The only useful LPL result is the acc-bias stratum (correctly UNAVAILABLE via runtime Bas>2.5 flag).

**Honest framing:** "The scale-envelope LPL achieves 0 HMI but 1.85% availability — it is conservative by design. The dominant failure mechanism (acc-bias saturation) is covered by a runtime detector; scale-drift onset prediction requires a richer runtime signal (feature count temporal variance, scale consistency) which is left as future work."

**What would fix it:** Feature_count as second signal (feat_fail=63.8 vs feat_nofail=117.6 strongly discriminative on KAIST, but needs extraction from grade_sweep VINS logs). Estimated ~1h script work + data extraction.

---

## L4 — LPL validated on CARLA sim only (K0 blocks real data)

**What was done:** CARLA provides the only source of continuous diverging-VINS ground truth. KAIST has 1 real-sensor divergence scene (urban38-pankyo) — K0 fires (TBD-N = 30 distinct scenes unmet).

**Impact:** The LPL Stanford diagram is CARLA simulation only. Cannot claim the scale-error LPL generalizes to real driving without more real-sensor divergence data.

**Honest framing:** "LPL calibration and the Stanford diagram are CARLA-simulation results. Real-world validation is limited to binary evidence (KAIST urban38 = acc-bias divergence) due to data scarcity (K0: ~7 distinct diverging scenes vs required ≥30)."

**What would fix it:** Collect ≥30 distinct VINS diverging scenes on real sensors (≥10 real-sensor, ≥2 mechanisms). This is the `TBD-N` threshold.

---

## L5 — OPL CARLA result is dominated by depth blow-ups (sim artifact)

**What was done:** CARLA depth noise causes p95 depth error ~110m for the nearest 10% of objects. OPL at AL=3m is essentially forced to flag everything → 0% availability on CARLA. The CARLA OPL result is not informative.

**Impact:** CARLA cannot be used as the OPL calibration evidence. KITTI is the primary real-data result.

**Honest framing:** "CARLA obstacle depth noise is unrealistically large; OPL results on CARLA are uninformative. KITTI tracking is the primary evidence for OPL."

---

## L6 — Formal causal chain not yet bit-for-bit traceable in closed-loop

**What was done:** Phase 4.2/4.3 closed-loop uses `risk_score ≥ 0.5` (validity adapter output) as OPL proxy. The calibrated Mondrian OPL publisher is NOT yet wired into the closed-loop. Mode switches cannot be attributed to formal `OPL ≥ AL_pos` crossings at the frame level.

**Impact:** The spec requirement "a mode switch SHALL be attributable to a `PL ≥ AL` crossing" is not yet satisfied in the closed-loop.

**Honest framing:** "Closed-loop mode switches are triggered by a rule-based OPL proxy (validity score threshold); the calibrated PL publisher from the offline integrity formalism is not yet integrated into the closed-loop. Full causal traceability requires Phase 5 integration."

**What would fix it:** Wire Mondrian-calibrated OPL publisher into paper2_validity_bridge; log per-obstacle PL values; attribute mode switches to OPL≥AL crossings. ~2-3h engineering.

---

## L7 — nuScenes: cross-dataset transfer requires target calibration

**What was done:** Direct-transfer CARLA→nuScenes AUROC = 0.692. Target-calibrated: 0.969. Without target calibration, cross-dataset performance is weak.

**Impact:** Target calibration (fitting a final-layer calibrator on a small target-domain sample) is required for deployment. This is not a zero-shot transfer.

**Honest framing:** "Cross-dataset transfer of the obstacle validity model requires target calibration; direct transfer achieves only 0.692 AUROC. Target calibration recovers to 0.969, requiring a small labeled target-domain sample."

---

## L8 — Velocity OPL availability is low (5.5% at IR=0.10)

**What was done:** KITTI velocity OPL at IR=0.10, Mondrian LSO: exceedance=0.1042 (PASS), but availability=5.5% (only 5.5% of frames have OPL_vel < AL_vel). Most frames are flagged as high-uncertainty.

**Impact:** The velocity channel is useful for reducing HMI (0.45% vs uncalibrated baseline) but has limited operational utility (5.5% availability).

**Honest framing:** "Velocity OPL achieves calibrated exceedance at IR=0.10 but 5.5% availability — velocity estimates are frequently flagged as uncertain, which limits the operational benefit."

---

## L9 — Hard-stop collision in moving world: seed-dependent

**What was done:** Supervised (hard-stop) shows 40% collision rate in moving-obstacle mode across 5 seeds (2/5 seeds have collision). The result is from 5 seeds only.

**Impact:** Statistical uncertainty on this collision rate is high (n=5). The direction (frozen robot = vulnerability) is robust, but the exact rate may vary.

**Honest framing:** "Supervised hard-stop achieves 40% collision rate in moving-obstacle mode across 5 seeds — directionally robust but statistically limited (n=5)."

---

## L10 — Obstacle AL is frozen, not grounded by planner safety margin

**What was done:** AL_pos = 3.0 m, AL_vel = 3.0 m/s are adopted from the prior obstacle validity work labels (fixed before evaluation). These are not derived from planner safety margins or actual stopping distance.

**Impact:** The alert limit is a reasonable heuristic but not formally grounded. A reviewer may ask why 3m specifically.

**Honest framing:** "Obstacle alert limits (AL_pos=3m, AL_vel=3m/s) are adopted from prior work labels, selected to match typical obstacle avoidance margins. Formal grounding from planner stopping distance is deferred to future work."

---

## Summary of Limitation Severity

| # | Limitation | Severity | Fixable within scope? |
|---|-----------|---------|----------------------|
| L1 | Sim-only closed-loop | HIGH (main claim caveat) | No (Phase 8, real robot) |
| L2 | GT pose in loop | HIGH (no real VINS) | No (Phase 5/8) |
| L3 | LPL scale-drift gap | HIGH (1.85% avail) | Partial (feature_count ~1h) |
| L4 | LPL CARLA-only | MEDIUM (K0 fires) | No (need real data) |
| L5 | OPL CARLA null | LOW (known artifact) | No (KITTI is primary) |
| L6 | Causal chain proxy | MEDIUM (spec gap) | Yes (~3h wiring) |
| L7 | nuScenes transfer | LOW (expected) | No (deployment issue) |
| L8 | Velocity avail 5.5% | LOW (secondary) | No (fundamental) |
| L9 | Collision seed-dependence | LOW (directional) | Partial (more seeds) |
| L10 | AL not grounded | LOW (heuristic) | No (design choice) |
