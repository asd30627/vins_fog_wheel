# Navigation Integrity Monitoring — Next 24h Action Plan

**Date:** 2026-07-02  
**Current state:** Offline formalism + closed-loop proxy complete. Paper package assembled. Tasks ordered by impact/feasibility.

> **⚠️ SUPERSEDED BY AUDIT (2026-07-02).** The next 24h is NOT new experiments — it is **writing the
> OPL-spine paper**. See `PAPER2_PROJECT_COMPLETION_ROADMAP.md` (authoritative) and
> `PAPER2_MISSING_EXPERIMENTS_TO_FIX.md`. Must-fix reporting items are done. Only S1 (learned TCSV-M
> VINS mask) and S3 (Phase 4.2 10 seeds) are optional low-cost strengtheners; do them only on explicit
> go-ahead. Do NOT open new branches.

---

## Tier 1 — Within current scope, no new data required (≤ 3h each)

### T-A: LPL-v3 feature_count signal — **DONE (HONEST NULL) 2026-07-02**

**What was investigated:** Joined 19 VINS replay runs (from `paper2_object_dataset_v2_with_vins.parquet`, per-detection rows) to `vins_loc_table.csv` (24 VINS replay runs with scale divergence labels). Computed mean `vins_feat_count` per run.

**Result:** feature_count does NOT discriminate divergence in CARLA VINS replay:
- div_tight=True (17 divergent runs): feat_mean = **56.89**
- div_tight=False (7 safe runs): feat_mean = **50.52**
- Direction is OPPOSITE to KAIST (KAIST: feat_fail=63.8 < feat_nofail=117.6)
- Effect size is tiny (< 7 features, large within-group variance)

**Root cause:** CARLA feature counts are uniformly low (47-64 range) regardless of divergence. The discriminativity seen in KAIST (63.8 vs 117.6) requires real hardware with genuine visual degradation — not available in CARLA sim.

**Conclusion: LPL-v3 BLOCKED.** feature_count is NOT a useful second signal in CARLA sim. The autonomous_results TSV files (town_scan, grade_sweep, etc.) also have no feature_count column. New VINS replay with feature logging would require re-running 135 CARLA bags — new data collection (~4h), not in current scope.

**Honest remaining claim:** LPL v1 (scale-envelope only, 1.85% avail) is the published result. Acc-bias stratum correctly forced UNAVAILABLE via runtime flag (useful partial coverage).

---

### T-B: OPL publisher wiring into closed-loop (MEDIUM IMPACT, ~3h)

**What:** Add a Mondrian-calibrated OPL publisher node to `paper2_validity_bridge` that emits `opl_position_m` per obstacle per step. Log these values to episode CSV. Add a check: does the mode switch (risk≥0.5) correlate with OPL≥3.0m crossings?

**Why:** Closes L6 (formal causal chain). The offline KITTI Mondrian OPL is already computed; the publisher needs to evaluate the same quantile GBR model at runtime. This makes the causal chain formally traceable.

**Files to edit:**  
- `~/nav2_ws/src/paper2_validity_bridge/` — add OPL publisher node
- Episode CSV schema — add `opl_position_m_min`, `opl_threshold_crosses`

**Forbidden:** Do NOT modify mini_world_sim core, Nav2 planner, VINS backend.

**Gate:** Re-run Phase 4.2 batch (30 episodes) with OPL publisher → check that mode switches co-occur with OPL≥3.0m crossings → satisfy spec requirement 3.2.

---

### T-C: CARLA sim OPL velocity channel — **DONE 2026-07-02 (existing data, updated docs)**

**CARLA velocity OPL at IR=0.10:** exceedance=0.0548 (calibrated ✓), HMI=11 (0.44%), avail=0.52%  
- CARLA velocity OPL IS useful (unlike position which has 0% avail due to depth blow-ups)
- Velocity estimates are more robust to depth noise → OPL velocity can provide meaningful bounds in CARLA sim
- Stanford diagram: `logs/obstacle_opl/stanford_CARLA_velocity.png` ✓

**CARLA position OPL at IR=0.10:** exceedance=0.0715 (calibrated ✓), HMI=0, avail=0% — always flags everything (depth blow-ups force OPL > 3m for all frames)

These numbers are now reflected in Phase 3 and paper evidence files.

### T-E: Phase 4.4 Dual-Channel OPL+LPL — **RUNNING 2026-07-02**

**What:** 9-episode experiment (3 conditions × 3 seeds). World: mixed obstacles (2 DANGEROUS) + loc_err ramp (0→0.7m over 12s, AL_loc=0.20m).  
Conditions: `ours_baseline` (OPL only), `lpl_only` (LPL only via honor_lpl), `dual_channel` (OPL+LPL).

**Changes:** Added `honor_lpl` and `al_loc_m` parameters to mini_world_sim_node.py (additive, 3 lines). Rebuilt paper2_validity_bridge. Script: `scripts/phase44_batch.py`.

**Expected result:**
- ours_baseline: near_coll reduced (OPL), false_safe≈high (loc_err blind)
- lpl_only: near_coll≈high (no obstacle margin), false_safe reduced (LPL fires at loc_err≥0.20m)
- dual_channel: BOTH near_coll reduced AND false_safe reduced

**Status:** RUNNING in background. Results → `logs/phase44/PHASE4_4_DUAL_CHANNEL_BENCHMARK.md`

---

## Tier 2 — Requires minor new runs (< 1h compute, within allowed files)

### T-D: More closed-loop seeds for supervised collision rate (MEDIUM IMPACT, ~45min)

**What:** Phase 4.2 supervised moving: 2/5 seeds had collisions (40% collision rate). Re-run with 10 seeds (same batch script, just increase n_seeds=10) to get tighter confidence interval.

**Why:** L9 (seed-dependence) — 5 seeds is thin for a collision rate. 10 seeds gives n=10 per condition.

**Files:** `scripts/phase42_batch.py` — already written; just increase N_SEEDS and re-run

**Gate:** If collision rate persists across 10 seeds → strengthens C3. If it drops → update evidence honestly.

---

### T-E: OPL+LPL combined experiment (NEW, ~2h design + run)

**What:** Design a Phase 4.4 experiment combining: (a) DANGEROUS obstacles (OPL fires) + (b) loc_err ramp (LPL needed). Show that OPL alone misses the loc_err degradation AND LPL alone misses the obstacle collision. Combined dual-channel protection covers both.

**Why:** Directly demonstrates the "why dual-channel" argument in closed-loop. Currently Phase 4.2 shows OPL benefit and Phase 4.3 shows LPL gap separately — Phase 4.4 would show them jointly.

**Design:** Mix Phase 4.2 world (DANGEROUS obstacles) + Phase 4.3 loc_err ramp. Add LPL publisher (accbias_flag only → force UNAVAILABLE). Show: OPL prevents collision (Phase 4.2 result replicates) AND LPL fires on loc_err (Phase 4.3 result replicates) in the same episode.

**Feasibility:** High (additive in mini_world_sim; no new data). ~2h scripting + ~1h run.

---

## Tier 3 — Blocked by missing data or forbidden operations

### T-F: LPL-v3 from grade_sweep VINS replay logs — BLOCKED IF no feature_count

**Blocker:** If grade_sweep VINS replay logs don't include feature_count (only scale metrics), LPL-v3 is blocked. The CARLA parquet already shows all feat_count=47-64 (no variation). New VINS replay run with feature logging would take ~4h and requires new data collection.

**Status:** CHECK T-A first. If T-A confirms no feature_count variation in logs → mark LPL-v3 BLOCKED with this exact reason.

---

### T-G: KAIST real-sensor LPL Stanford — BLOCKED (K0)

**Blocker:** K0 fires. Only 1 real-sensor divergence scene (KAIST urban38-pankyo). Need ≥30 distinct diverging scenes (≥10 real-sensor, ≥2 mechanisms). This requires new real-sensor data collection.

**Status:** BLOCKED. Document as: "KAIST LPL requires ≥30 distinct diverging scenes; currently ~7/1/2 (total/real-sensor/mechanisms). Data collection is the next concrete step."

---

### T-H: Learned VINS HealthNet — BLOCKED (K0)

**Blocker:** Same as T-G. K0 fires; any AUROC is illusory (label leakage from acc-bias margin, LOSO gives 0 train positives).

**Status:** BLOCKED. Document: "Learned HealthNet requires K0 threshold (TBD-N=30 diverging scenes). Current ~7 distinct scenes — do not train."

---

### T-I: FOG_COAST/STOP_REINIT/UNAVAILABLE — BLOCKED (K4, real FOG required)

**Blocker:** Phase 6. KAIST real navigation-grade FOG (0.05°/hr) drift-vs-time curve required to ground TBD-drift-budget and TBD-Tmax. Hardware experiment required.

**Status:** BLOCKED. Document: "FOG_COAST feasibility requires KAIST real-FOG drift curve (Phase 6). TBD-drift-budget and TBD-Tmax cannot be resolved without hardware data."

---

### T-J: Learned navigation risk supervisor — BLOCKED (K3, Phase 5)

**Blocker:** Phase 5 requires: P2 VINS-noise replay injection (not done) + closed-loop with live VINS (not done) + held-out town/route evaluation. K3 gate: learned supervisor must beat rule-based on new routes.

**Status:** BLOCKED. Rule-based supervisor (Phase 4.1 result) is the current deliverable; learned supervisor is K3-gated.

---

## Decision Points (user action required)

### D1 — Confirm AL_loc = 0.20

LPL v1 achieves 0 HMI at IR=0.10, AL_loc=0.20. This is the recommended operating point. **Confirm or adjust.**

### D2 — Run T-A (feature_count extraction) or defer?

If yes: estimate 2h scripting. The potential payoff is LPL v3 availability improvement from 1.85% to ≥20%. If no/defer: publish LPL with honest conservative framing.

### D3 — Run T-D (more seeds) before paper draft?

Phase 4.2 supervised collision rate (40%) is from n=5 seeds. More seeds tighten the CI. Suggest n=10 (5 more episodes = ~15min compute).

### D4 — Venue target

Current evidence supports:
- **T-IM / Sensors:** Offline OPL formalism (KITTI Mondrian real data, cross-scene, 3 datasets) + LPL formalism (sim conservative) + closed-loop proof-of-concept (sim). Strong enough with honest framing.
- **T-ITS / T-IV:** Requires real closed-loop collision reduction (Phase 8) + real-sensor LPL (K0 fix). Not achievable without new data.

**Recommendation: T-IM or IEEE Sensors as primary target.** T-ITS/T-IV as follow-up after Phase 8.

---

## Execution Priority (if autonomous continuation)

1. **T-A** (feature_count check) — check if VINS replay logs have feature_count; if yes → run LPL-v3 
2. **T-C** (CARLA velocity OPL) — update docs with existing numbers (30min)
3. **T-D** (more seeds Phase 4.2) — run if compute available (15min)
4. **T-E** (combined OPL+LPL Phase 4.4) — design + run if T-A done (2h)
5. **T-B** (OPL publisher wiring) — only if Phase 5 scope is approved by user (3h)

---

## Phase 6 Status (2026-07-02 update)

All Phase 6A–6D tasks DONE. See `logs/NIGHT_2026-07-02_RESULTS.md` Session 4 for complete summary.

### Phase 6 open items (deferred, need user decision):

1. **ORB-SLAM3 ATE comparison** — Deferred. Requires trajectory recording via `/tf` topic (not global BA) + real dynamic-object bboxes at vehicle locations (lower image). EuRoC is not ideal (indoor, no real dynamic vehicles). CARLA ORB-SLAM3 bag would be better.
2. **Feature-tracker mask injection (Method B)** — Deferred. Requires frontend rebuild. `feature_tracker.cpp:289` is the injection site. Only attempt if Method A CARLA test shows insufficient improvement.
3. **KAIST real-driving VINS PV-mask** — Deferred. Needs per-frame bbox annotations on KAIST sequences. Strong claim would require KAIST pedestrian/vehicle GT or detection.

### Paper contribution framing (updated):

The branch upgrades the paper from "navigation integrity monitoring" to "**PV-validity-aware localization and navigation integrity**":
- Step 1 (localization): PV-mask dynamic objects → −10.5% ATE VINS (CARLA); ORB-SLAM3 relay proven (ATE deferred)
- Step 2 (monitoring): OPL/LPL/HealthNet → formal integrity bounds
- Step 3 (action): risk-scaled speed modulation
- One consistent PV-validity signal flows through all three steps
