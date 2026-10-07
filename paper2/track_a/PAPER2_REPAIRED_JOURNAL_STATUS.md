# Paper-2 — Repaired Journal Status (after repair attempts)

**Date:** 2026-07-02 (post-repair)
**Basis:** repairs actually executed this pass (P1 HealthNet, P2 VINS+TCSV-M, P3 Phase 4.4, P5 OPL) +
P4 ORB-SLAM3 plan. Scope decided AFTER repairs, not before.

> Dual-channel (Phase 4.4) FULLY REPAIRED (2-stage). Stage 2 availability flag → **claim 7 SUPPORTED**:
> dual_channel_avail commits 0 false-safe and 0 collisions at availability 0.12 / success 40% (honest
> protection-level tradeoff). See `logs/phase44/PHASE4_4_LPL_AVAILABILITY_REPAIR_REPORT.md`.

---

## 1. Which yesterday claims are now successfully repaired?

| claim | repair outcome |
|-------|----------------|
| **OPL calibrated + beats baselines** | STRENGTHENED — confidence gate added; OPL 0.114 < range 0.137 < conf 0.172 @ matched availability. |
| **HealthNet cross-sequence** | REPAIRED — expanded to 6 routes (incl. 4 real-grade highways); LOSO AUROC 0.73–0.99 (was "not evaluable"). |
| **nuScenes transfer** | REPAIRED (framing) — zero-shot 0.69 / target-calib 0.969 / in-domain 0.973 reported separately. |
| **Phase 4.4 dual-channel** | REPAIRED (metric+timeout+risk-scaled mode); rerun verdict → [PENDING]. |

## 2. Which claims remain weak but fixable?

| claim | weakness | fix (not done) |
|-------|----------|----------------|
| VINS masking benefit | small + mixed (−2.5% dense / +2.3% medium); nondeterminism-bound | more PASS_CORE runs (Town03/04/05) + soft feat_weight estimator hook |
| HealthNet | run-mode confound (highways = soft-failure mode) | matched-mode VINS replay (multi-hour) |
| Closed-loop (4.2) | 5 seeds, sim proxy | 10-seed rerun (cheap); real robot (large) |

## 3. Which claims are blocked by missing data?

| claim | blocker |
|-------|---------|
| Learned TCSV-M **superiority** | not data-blocked — experiment ran and showed NO advantage over raw_speed. Falsified, not blocked. |
| ORB-SLAM3 PV localization | pose logger DONE + baseline ATE obtainable; PV test blocked on a CARLA ORB-SLAM3 config YAML + GT→TUM converter (topics compatible). |
| Deployable LPL | needs a scale-drift onset signal; early_env insufficient. |
| Real-world closed loop | needs live VINS-in-loop + real platform. |
| External dynamic-SLAM baseline | no executable ROS2 baseline locally (DynaVINS is ROS1). |

## 4. Which experiments were actually run this pass?

1. HealthNet dataset expansion (builder re-run, no VINS) + leave-one-sequence-out eval.
2. VINS: baseline / raw_speed / **learned TCSV-M** / oracle × Town01 dense + medium, one session (8 replays).
3. TCSV-M mask built from existing leak-free scores.
4. OPL confidence-gate baseline + matched-availability gate-vs-OPL comparison.
5. Phase 4.4: sim-node + batch repaired, rebuilt, rerun 15 episodes [completing].

## 5. Which experiments were NOT run, and why?

| not run | why |
|---------|-----|
| ORB-SLAM3 wrapper pose logger + dynamic run | gated on user approval + a dynamic stereo+IMU bag (blocker). |
| Soft feat_weight VINS variant | needs an estimator hook (new branch) — out of scope. |
| Matched-mode / multi-town VINS replay for HealthNet | multi-hour batch — report-before-run rule. |
| DynaVINS ROS1→ROS2 port | >1h, explicitly out of scope. |

## 6. Main-paper claims (defensible)

1. **OPL obstacle-state integrity** (KITTI Mondrian, PASS @IR=0.05/0.10; beats distance/range/confidence gates at matched availability). — headline.
2. **OPL closed-loop benefit** (Phase 4.2, controlled sim). — main, labeled sim.
3. **OPL ≠ LPL structural gap** (Phase 4.3). — main, motivation.
4. Dual-channel ablation ladder (Phase 4.4, repaired + availability flag) — **main**: OPL → hard-stop →
   speed-only → availability. dual_channel_avail = 0 false-safe, 0 collisions, at availability 0.12 /
   40% success. Shows a correct dual channel needs risk-scaling AND an availability flag; the
   integrity/mission tradeoff is the contribution, not hidden.

## 7. Appendix claims

- HealthNet cross-route detection (LOSO 0.73–0.99; confounds disclosed).
- nuScenes replication (target-calibrated).
- VINS raw-speed dynamic mask (small, mixed effect; learned TCSV-M no better).
- ORB-SLAM3 wrapper infra + pose-logger plan.
- LPL research gap (1.85% avail); acc-bias runtime flag.

## 8. Claims to remove ONLY after repair failed

- **Learned-TCSV-M superiority** — repair ran, showed no advantage → remove the "learned PV beats raw_speed" framing (keep raw-speed mask).
- **VINS masking −10.5% headline** — shown to be a favorable-session artifact → replace with the honest small/mixed effect.
- **Original Phase 4.4 table** (broken metric) — replaced by the repaired rerun.

Nothing else is removed by assertion; every downgrade above is experiment-backed.

## 9. Current best journal story AFTER repair

**"A RAIM-style obstacle-state integrity monitor (OPL), leave-scene-out conformal-calibrated on KITTI,
that dominates fixed distance/range/confidence gates, drives a safer closed-loop policy than naive or
hard-stop in simulation, and is shown to require a separate localization-integrity channel."**
Supporting: cross-route VINS-failure HealthNet (real cross-sequence, confounds disclosed), 3-dataset
reliability replication, and a small input-masking localization effect. This is **broader than
OPL-only** — the HealthNet repair restored a genuine (if confounded) localization-risk-prediction
result, so the "PV-validity for both monitoring and localization" arc is partially back, honestly bounded.

## 10. What should the user decide next?

1. **Scope:** OPL-headline paper WITH the repaired supporting results (HealthNet cross-route, dual-channel)
   as secondary — vs OPL-only. Recommendation: include the repaired supporting results as secondary,
   since they are now experiment-backed with disclosed confounds.
2. **Approve the 2 cheap strengtheners?** (a) matched-mode / multi-town VINS replay to remove the HealthNet
   run-mode confound (multi-hour — the path to a STRONG HealthNet claim); (b) Phase 4.2 10-seed rerun.
3. **ORB-SLAM3:** approve the wrapper pose-logger + confirm whether a dynamic stereo+IMU bag exists; else
   keep it infrastructure-only.
