# Paper-2 — Project Completion Roadmap

**Date:** 2026-07-02 (audit pass)
**Purpose:** practical route to a submit-ready paper from the honestly-audited evidence. No new branches.

---

## 1. Current strongest honest journal topic

**"A RAIM-style obstacle-state integrity monitor for GPS-denied navigation, calibrated by
leave-scene-out conformal regression, with a controlled-simulation closed loop."**

The spine is the **OPL** (obstacle protection level) on KITTI — real data, proper protocol,
formal integrity bound, baselines. Everything else is supporting or motivation.

## 2. Exact main contribution

> A per-object **protection level** for obstacle position, calibrated with **leave-scene-out
> (Mondrian) conformal regression** so the finite-sample integrity guarantee survives cross-scene
> shift; achieving exceedance 0.114 ≤ IR 0.10 (+tol) on KITTI with 32% availability, reducing
> false-safe events 7× vs a distance gate; and a controlled-simulation closed loop showing the bound
> yields a safer policy than naive or hard-stop, plus a structural argument that a **separate
> localization-integrity channel** is required (OPL is blind to pose drift).

## 3. Results ready for the main paper

- KITTI Mondrian OPL (headline, Tier 1).
- Phase 4.2 closed-loop OPL benefit (Tier 2, labeled controlled sim).
- Phase 4.3 OPL≠LPL structural gap (Tier 2, motivation).

## 4. Results for appendix only

- nuScenes replication (with target calibration; zero-shot weak).
- VINS raw-speed dynamic mask (2 clean CARLA runs).
- HealthNet cross-grade transfer (single route).
- LPL isotonic v1 research gap; acc-bias runtime flag; ORB-SLAM3 wrapper infra note.

## 5. Results that MUST be removed / relabeled

- **Remove:** Phase 4.4 dual-channel benchmark (broken metric, self-contradiction).
- **Remove:** HealthNet "AUROC 0.963 works" capability claim + "time-to-alert" early-warning framing.
- **Remove:** ORB-SLAM3 "localization improvement / promising".
- **Relabel:** VINS "validity_aware/PV mask" → "raw-speed dynamic mask".
- **Remove:** "full paper-ready package complete."

## 6. Experiments that must be completed before submission

**None are strictly required** to submit the OPL-spine paper as an integrity-monitoring contribution.
The must-fix items (M1–M6) were reporting/analysis fixes and are DONE. What remains before submission
is **writing**, not experiments:
- final OPL tables with per-scene spread + availability, IR=0.20 excluded;
- honest limitations section (this audit).

## 7. Optional experiments (strengthen, not required)

- S1 learned TCSV-M VINS mask (upgrades the localization-mask appendix).
- S3 Phase 4.2 with 10 seeds (tightens closed-loop CI).
- S2 feature-level routing; S4 Phase 4.4 metric-fix rerun.

## 8. Shortest route to submit-ready

1. Lock scope to **OPL integrity monitor** (KITTI headline + sim closed loop + LPL-gap motivation).
2. Apply the package corrections (done this pass): remove Tier-4 items, relabel raw-speed mask.
3. Write results §: OPL tables (per-scene, exclude IR=0.20), Phase 4.2, Phase 4.3.
4. Write limitations § straight from `PAPER2_NAV_INTEGRITY_LIMITATIONS.md` (sim proxy, LPL gap,
   single-route HealthNet, no external executable baseline).
5. Appendix: nuScenes, raw-speed mask, HealthNet cross-grade, ORB-SLAM3 infra.
6. Target a venue matched to "real-data OPL + sim closed loop" (see §9).

## 9. What the user should do today

- **Decide the scope lock:** OPL-integrity-monitor paper (recommended) vs waiting to add a learned
  localization channel (blocked by data). Recommendation: **lock OPL scope now.**
- **Pick the venue tier** matching current evidence (real-data OPL + controlled sim): a robotics/
  sensors venue where controlled-sim closed loop is acceptable with honest framing — NOT a venue that
  demands real-robot collision statistics.
- **Approve or decline S1/S3** (the only two low-cost strengtheners).

## 10. What to avoid

- Do NOT open new branches (ORB-SLAM3 core, new datasets, temporal fusion) before the OPL paper is written.
- Do NOT re-inflate HealthNet or Phase 4.4.
- Do NOT claim zero-shot cross-dataset transfer, real-world closed loop, learned PV mask, or ORB-SLAM3
  localization improvement.
- Do NOT leave heavy SLAM/replay processes running.
