# Paper-2 — Missing Experiments To Fix

**Date:** 2026-07-02 (audit pass)
**Rule:** classify every gap; execute only feasible must-fix with existing files/data; do NOT open
new branches; do NOT fabricate ATE/RPE.

**Classes:** must_fix_before_journal / should_fix_if_time / appendix_only / future_work

---

## must_fix_before_journal

| # | gap | class | status | action |
|---|-----|-------|--------|--------|
| M1 | HealthNet generalization boundary must be shown, not asserted | must_fix | **DONE this pass** | Ran `phase5_healthnet_generalization_audit.py` → LOSO undefined (only urban38 has failures), cross-grade 0.94–1.0. See `logs/phase5/PHASE5_HEALTHNET_CLAIM_AUDIT.md`. |
| M2 | Rename "validity_aware / PV mask" → "raw-speed dynamic mask" everywhere | must_fix | **DONE this pass** | Package files updated; TCSV-M explicitly marked NOT run. |
| M3 | Remove Phase 4.4 broken benchmark from package | must_fix | **DONE this pass** | Downgraded to Tier-4; qualitative point folded into 4.2. |
| M4 | Label all Phase-4 results "controlled 2D sim (GT pose, synthetic scan)" | must_fix | **DONE this pass** | Package updated. |
| M5 | Report KITTI OPL per-scene spread + availability + exclude IR=0.20 | must_fix | mostly present | Ensure final tables show avail 32.4% and drop IR=0.20 — already in results file; reflect in FINAL_EVIDENCE. |
| M6 | State nuScenes zero-shot number (0.69) openly, not just target-calib 0.969 | must_fix | **DONE this pass** | CLAIMS/EVIDENCE corrected. |

## should_fix_if_time (real experiments; upgrade a Tier, but need a run — deferred, not a new branch)

| # | gap | class | what it buys | cost / blocker |
|---|-----|-------|--------------|----------------|
| S1 | Run **learned TCSV-M** VINS mask on Town01 dense/medium | should_fix | Upgrades J from "raw-speed gate" → "learned PV mask" IF it holds | Needs `paper2_vins_tcsv_masking.py` + TCSV-M model + VINS replay loop (CARLA stopped). ~2–4h. |
| S2 | Add **feature-level routing** (Method B, `feature_tracker.cpp:289` mask) vs blur | should_fix | Cleaner mechanism than blur; small ATE gain expected | Frontend rebuild (NOT backend). Restore point first. |
| S3 | Re-run **Phase 4.2 with 10 seeds** | should_fix | Tightens the 10% hard-stop collision CI | `phase42_batch.py`, ~15 min. Low risk. |
| S4 | Fix Phase 4.4 metric + timeout, re-run ≥5 seeds | should_fix | Could resurrect a dual-channel result | `phase44_batch.py` metric bug fix + rerun. Only if dual-channel story is wanted. |

## appendix_only (document; do not chase)

| # | item |
|---|------|
| A1 | LPL isotonic v1 (1.85% avail) as a research-gap appendix |
| A2 | HealthNet cross-grade transfer (single route) as an appendix micro-result |
| A3 | ORB-SLAM3 wrapper-portability note (infra) |
| A4 | acc-bias runtime detection as a lightweight partial LPL signal |

## future_work (blocked by data/hardware; state as future work)

| # | item | blocker |
|---|------|---------|
| F1 | Cross-route / real-sensor HealthNet generalization | needs ≥10 diverging routes + ≥1 real-sensor grade (K0 / TBD-N=30) |
| F2 | Deployable LPL (fix scale-drift predictor) | needs a scale-drift onset signal; current early_env insufficient |
| F3 | ORB-SLAM3 baseline-vs-masked ATE | needs wrapper pose-logging change + dynamic-object bag |
| F4 | Real-robot / physics closed-loop | needs live VINS-in-loop + real platform (P3) |
| F5 | Executable external dynamic-SLAM baseline | DynaVINS ROS1→ROS2 port (>1h, not attempted) |

---

## What was executed this pass (feasible must-fix only)

1. **M1** — HealthNet leave-sequence-out + leave-grade-out diagnostic (new data-free script) →
   empirically confirmed cross-sequence is not evaluable; cross-grade transfers.
2. **M2–M4, M6** — corrective re-labeling/removals across the package (reporting fixes, not new runs).

No new experimental branch was opened. S1–S4 are real runs left for an explicit go-ahead.
