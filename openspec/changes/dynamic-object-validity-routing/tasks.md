# Tasks — Component-wise Dynamic Object Validity for VINS-Aided Navigation

**Change ID:** dynamic-object-validity-routing  
**Date:** 2026-07-01

---

## Phase 0 — OpenSpec and Boundary Definition ✅ DONE

- [x] Create OpenSpec change: `openspec/changes/dynamic-object-validity-routing/`
- [x] Write proposal.md — problem, proposed change, non-goals, evidence status, success/failure gates
- [x] Write design.md — architecture, variant list, dataset roles, evaluation protocol
- [x] Write tasks.md (this file)
- [x] Write specs: object-state-validity, vins-dynamic-routing, planner-validity-interface, dataset-evaluation-boundary
- [x] Write `PAPER2_OPENSPEC_SUMMARY.md`
- [x] Freeze non-goals list in proposal.md
- [x] Lock dataset roles in design.md
- [x] Confirm Town06/07 as boundary/negative controls (Phase 2 VISION_INERT confirmed)
- [x] Define success/failure gates

**Gate:** OpenSpec written and internally consistent. Non-goals frozen.

---

## Phase 1 — R7 Urban-Candidate Scenario Search 🔄 IN PROGRESS

**Goal:** Find which CARLA urban towns support life-gate experiments (VINS-ready + VISION_ACTIVE under industrial_fog).

### Task 1.1 — Map availability audit

- [ ] Connect to CARLA (:3000) and enumerate available towns
- [ ] Try loading: Town01, Town02, Town04, Town05, Town10HD
- [ ] Record MAP_AVAILABLE / MAP_UNAVAILABLE per town
- [ ] Write `paper2/track_a/PAPER2_R7_MAP_AVAILABILITY.md`
- [ ] Write `paper2/track_a/paper2_r7_map_availability.csv`

**Gate:** Town list confirmed. Skip MAP_UNAVAILABLE towns in all subsequent steps.

### Task 1.2 — R7 preview recording

For each MAP_AVAILABLE candidate town, record 3–4 preview variants (100 drive frames each):

| scenario | --npc | --npc-global | notes |
|---|---|---|---|
| `medium_near_r7_preview` | 12 | 30 | lighter density |
| `dense_near_r7_preview` | 20 | 55 | reference R6 density |
| `dense_slow_r7_preview` | 20 | 55 | add `--npc-target-speed-frac 55` if helpful |
| `cross_traffic_r7_preview` | 20 | 55 | mark NOT_IMPLEMENTED if flag unavailable |

R7 base recipe (all previews):
```
--imu-at-vehicle-center --baseline 0.2
--drive-mode gentle_turn --base-speed 6.0
--ego-spawn-scan
--npc-near-band 8,70 --npc-on-route --npc-skip-ego-lane
--npc-autopilot-delay --npc-min-dist 8
--skip-aux --image-width 640 --image-height 480
--frames 100 --run-kind preview
--condition dynamic_v3r7
```

- [ ] Record preview variants for Town01 (if map available)
- [ ] Record preview variants for Town02 (if map available)
- [ ] Record preview variants for Town04 (if map available)
- [ ] Record preview variants for Town05 (if map available)
- [ ] Record preview variants for Town10HD (if map available)

### Task 1.3 — Preview quality audit

For each recorded preview:

- [ ] Run YOLO per-det probe (conda gf)
- [ ] Compute quality metrics:
  - ego GT path length (must be > 20 m for 100 drive frames)
  - ego average speed
  - YOLO detection count
  - matched detection count
  - matched<50m (primary quality signal)
  - det/frame
  - bbox area median
  - full-frame ratio (must be low — no glued face)
  - near-object density
- [ ] Classify: PASS_PREVIEW / LOW_YIELD_PREVIEW / FAIL_PREVIEW

PASS_PREVIEW criteria:
- ego path length > 20 m
- matched<50m > 30 per 100 frames (≥0.3/frame)
- det/frame > 0.5
- full-frame ratio < 0.10 (no glued face)
- no collision / no ego blocking observed

- [ ] Write `paper2/track_a/PAPER2_R7_PREVIEW_AUDIT.md`
- [ ] Write `paper2/track_a/paper2_r7_preview_audit.csv`

**Gate:** At least one scenario per town passes PASS_PREVIEW before recording core.

### Task 1.4 — R7 core recording

For each town, select the best 1–2 PASS_PREVIEW scenarios (highest matched<50m, good motion, no blocking):

- [ ] Record selected core variants (720 drive frames, `--run-kind core`)
- [ ] Same R7 recipe as preview (same flags, same seed handling)
- [ ] Naming: `TownXX__dynamic_v3r7__run<scenario_name>_r7_core`

Core quality gate:
- ego path length > 100 m
- matched<50m high (> 200 per 720 frames recommended)
- no collision / no blocking
- no glued face
- full-frame ratio < 0.10

- [ ] Classify: PASS_CORE_R7 / LOW_YIELD_R7 / INVALID_R7
- [ ] Write `paper2/track_a/PAPER2_R7_CORE_MANIFEST.md`
- [ ] Write `paper2/track_a/paper2_r7_core_manifest.csv`

**Gate:** At least one PASS_CORE_R7 before running VINS smoke.

---

## Phase 2 (= Task 1.5) — R7 VINS Baseline Smoke

For every PASS_CORE_R7:

- [ ] Generate ideal_imu grade yref (`gen_carla_grade_imu.py`)
- [ ] Run baseline VINS ×2 reps (DET2 config, rate=0.5, no mask, ideal_imu)
- [ ] Compute: n_vio, ATE_rmse, ATE_mean, RPE_trans, early_scale, late_scale, full_scale, vins_failures, feature_raw, feature_mgr, outlier_ratio
- [ ] Classify: VINS_READY_R7 / VINS_UNSTABLE_R7 / NONDETERMINISTIC_R7

VINS_READY_R7 criteria:
- n_vio complete (≥ 95% of expected frames)
- no vins_failures
- rep1 vs rep2 ATE difference < 3%
- early_scale ≈ 1.0 (0.85–1.15)
- late_scale repeatable (same rep1 and rep2 direction)
- no divergence (ATE < 500 m)

- [ ] Write `paper2/track_a/PAPER2_R7_VINS_BASELINE_SMOKE.md`
- [ ] Write `paper2/track_a/paper2_r7_vins_baseline_smoke.csv`

**Gate:** VINS_READY_R7 required before vision sensitivity gate.

---

## Phase 3 (= Task 1.6) — R7 Vision Sensitivity Gate

For every VINS_READY_R7:

- [ ] Generate per-det CSV for R7 core (YOLO probe, conda gf)
- [ ] Build masks from R7 per-det (do NOT reuse old masks):
  - `all_dynamic`
  - `oracle`
  - `random_control`
- [ ] Run vision sensitivity experiments:

| grade | variants |
|---|---|
| ideal_imu | baseline, all_object, oracle, random_control, backend_cull_off |
| industrial_fog | baseline, all_object, oracle, random_control, backend_cull_off |

- [ ] Each variant: ×2 reps minimum; if DET2 variance > 3% use ×3 reps
- [ ] Compute per-variant median ATE, RPE, n_vio
- [ ] Classify per (town, grade): VISION_ACTIVE / VISION_INERT / AMBIGUOUS / UNSTABLE

VISION_ACTIVE criteria:
- `all_object` or `oracle` reduces ATE ≥5% vs baseline
- `random_control` does NOT reduce ATE by ≥3%
- At least 2/3 reps agree in direction

- [ ] Write `paper2/track_a/PAPER2_R7_VISION_SENSITIVITY_RESULTS.md`
- [ ] Write `paper2/track_a/paper2_r7_vision_sensitivity_metrics.csv`

**⛔ STOP after Phase 3.** Do not run Phase 4 (TCSV life gate) automatically.

---

## Phase 4 (= Task 1.7) — TCSV Life Gate [GATED — requires explicit approval]

**Prerequisite:** Phase 3 must produce at least one VISION_ACTIVE (town, grade) pair with a written gate decision.

- [ ] **GATE DECISION REQUIRED** — write gate decision before starting
- [ ] For each VISION_ACTIVE (town, grade): run full TCSV variant grid
- [ ] See design.md for full variant list (tcsv_m_hard, tcsv_m_soft, raw_speed_gate, cv_smoothing_gate, oracle, random_control)
- [ ] Report TCSV-M vs baselines vs oracle
- [ ] Write `paper2/track_a/PAPER2_TCSV_LIFE_GATE_RESULTS.md`

---

## Final Decision Document

- [ ] Write `paper2/track_a/PAPER2_R7_URBAN_CANDIDATE_DECISION.md`

Must answer (at minimum):
1. Which candidate towns were MAP_AVAILABLE?
2. Which previews passed (PASS_PREVIEW)?
3. Which core recordings are VINS_READY_R7?
4. Which towns are VISION_ACTIVE?
5. Which towns are VISION_INERT?
6. Did Town10HD replicate Town01?
7. Did Town02 / Town04 / Town05 show stronger signals?
8. Are Town06 / Town07 confirmed as boundary / negative controls?
9. Is there enough evidence to run TCSV life gate (Phase 4)?
10. Which exact runs should enter Phase 4?
11. Which runs should be excluded?
12. What is the current paper claim status?
    - main localization contribution
    - secondary VINS result
    - planner/perception-facing validity only

---

## Hard Constraints (apply to all phases)

- No closed-loop navigation
- No dynamic object BA factor
- No learning-through-BA
- No FOG full grade grid
- Do not use old Town06/07 masks
- Do not use old masks for R7 (rebuild from R7 per-det)
- No invalid CARLA runs (quality gate required)
- No placeholder CSV
- No raw_speed as TCSV-M
- No single-run ATE conclusion (always median ≥2 reps)
- No Huber-off / cull-off as formal method
- No localization improvement claim without repeatable signal + random_control ruled out
- Do not hide negative towns
- Do not overwrite `dynamic_v3` / `dynamic_v3fix` data
- Use `dynamic_v3r7` for all new R7 recordings
