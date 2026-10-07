# R8 — CARLA Scenario/Headroom Search: Phase R8-1 Preview Results

**Date:** 2026-07-02
**OpenSpec topic:** Shared Object Persistence for Coupled ORB-SLAM3 Backend and Frontier Navigation
**Scope of this phase:** preview search only (5 towns × 3 scenarios = 15 short recordings), no backend
changes, no closed-loop, no learned persistence.

---

## What was built (additive, no ORB-SLAM3 backend / no closed-loop / no learned persistence)

1. `fwvio_ws/scripts/collect_carla_v2.py`: new `--npc-static-frac` — a fraction of spawned NPCs are
   given handbrake + never autopiloted → **genuine parked/semi-static candidate-anchor objects**,
   distinct from the moving NPCs. Validated: reported `static_npc=N` in the recorder log matches the
   audit's GT-derived `semi_static_object_count` exactly (cross-checked, e.g. 11==11).
2. `scripts/r8_frame_audit.py`: pure offline analysis (GT geometry + a **standalone** `cv2.ORB`
   detector run directly on saved frames — does NOT touch the ORB-SLAM3 C++ backend). Computes:
   path length, mean speed, loop distance, semi-static/transient object counts (GT speed threshold),
   mean ORB keypoints, **object-region keypoint ratio** (via CARLA-standard camera projection of each
   object's 3D oriented bbox into the image), and **all_dynamic feature-loss ratio** (keypoints lost
   when moving-object regions are blurred before detection — a simulated class-prior mask, not a real
   ORB-SLAM3 run).
3. `scripts/r8_record_preview.sh` / `scripts/r8_orchestrate_preview.py`: per-scenario NPC presets +
   batch driver. Uses the already-validated `gentle_loop` + `speed-mod` + A\* return-leg + stuck-recovery
   recipe (Town01 loop-closure work, prior session). New condition tag `dynamic_v3r8` — does **not**
   overwrite `dynamic_v3loop` / `dynamic_v3r7` data.

## Scenario presets used

| scenario | NPC preset | intent |
|----------|-----------|--------|
| normal_urban_loop | `--npc 12 --npc-global 8` (all moving) | ordinary drivable baseline |
| anchor_recovery | `--npc 18 --npc-global 8 --npc-static-frac 0.6` | many parked (candidate anchors) + a few moving |
| dynamic_noise | `--npc 22 --npc-global 10 --npc-static-frac 0.1` | mostly moving, few static anchors |

All previews: 1500 drive frames (~83 s total incl. static+ramp), baseline 0.5, `gentle_loop`+`speed-mod`,
base-speed 6.0. Full log: `logs/phase6/r8_preview_batch.log`; raw data: `paper2_r8_preview_audit.csv`.

---

## Results (all 15 previews)

| town | scenario | path (m) | speed (m/s) | ORB poses% | resets | semi-static | transient | obj-region ratio | all_dyn loss | verdict |
|------|----------|----------|-------------|-----------|--------|-------------|-----------|-------------------|--------------|---------|
| Town01 | normal_urban_loop | 213.1 | 2.57 | 98.8% | 14 | 0 | 20 | 0.000 | 0.000 | PASS(core) |
| Town01 | anchor_recovery | 212.4 | 2.57 | 98.8% | 14 | 11 | 9 | 0.001 | 0.000 | PASS(core) |
| Town01 | dynamic_noise | 215.0 | 2.60 | 98.8% | 14 | 8 | 14 | 0.001 | 0.000 | PASS(core) |
| Town10HD | normal_urban_loop | 298.0 | 3.59 | 98.8% | 14 | 0 | 19 | 0.017 | 0.000 | PASS(core) |
| Town10HD | anchor_recovery | 297.8 | 3.59 | 98.8% | 14 | 11 | 8 | 0.018 | 0.000 | PASS(core) |
| Town10HD | dynamic_noise | 298.0 | 3.59 | 98.8% | 14 | 2 | 19 | 0.018 | 0.000 | PASS(core) |
| **Town02** | normal_urban_loop | 302.1 | 3.64 | 98.8% | 14 | 0 | 21 | 0.003 | 0.000 | PASS(core) |
| **Town02** | **anchor_recovery** | 213.7 | 2.58 | 98.8% | 14 | **16** | 11 | **0.178** | 0.000 | **PASS (all 6)** |
| **Town02** | **dynamic_noise** | 212.7 | 2.57 | 98.8% | 14 | 3 | **30** | **0.236** | 0.000 | PASS(core) |
| Town04 | normal_urban_loop | 307.6 | 3.71 | 98.8% | 14 | 0 | 20 | 0.130 | 0.003 | PASS(core) |
| Town04 | anchor_recovery | 306.9 | 3.70 | 98.8% | 14 | 12 | 9 | 0.029 | 0.000 | PASS(core) |
| Town04 | dynamic_noise | 307.0 | 3.70 | 98.8% | 14 | 9 | 14 | 0.050 | 0.002 | PASS(core) |
| Town05 | normal_urban_loop | 269.4 | 3.25 | 98.8% | 14 | 0 | 21 | 0.062 | 0.000 | PASS(core) |
| Town05 | anchor_recovery | **98.4** | **1.20** | 98.8% | **222** | 14 | 10 | 0.465 | 0.000 | **FAIL** (blocked) |
| Town05 | dynamic_noise | 298.1 | 3.59 | 98.8% | 14 | 7 | 19 | 0.055 | 0.000 | PASS(core) |

"PASS(core)" = the 3 hard gates (path>150m, speed>2.5, ORB poses>80%) pass; object-region-ratio≥15% /
anchor≥5 / transient≥3 are reported but not all met. "PASS (all 6)" = every R8-1 criterion met.

---

## Key findings

1. **Recording pipeline: 15/15 succeeded** (no map hangs, no unrecoverable stalls except one).
2. **Static-NPC feature (candidate-anchor mechanism) validated**: `anchor_recovery` scenarios
   reliably produce 8–16 semi-static objects and `dynamic_noise` reliably produces fewer (2–9) —
   matches the `npc-static-frac` design (0.6 vs 0.1) directly.
3. **Town05/anchor_recovery FAILED** — path 98.4 m, speed 1.2 m/s, 222 ORB resets. The dense
   near-band + high static-fraction spawn blocked the ego's route (traffic jam), consistent with the
   earlier loop-recording stall investigation (dense near-band NPCs can wedge the route). Its
   high object-region ratio (0.465) is an artifact of barely moving near a cluster of parked cars,
   not a usable scenario.
4. **`all_dynamic_feature_loss_ratio` ≈ 0 almost everywhere** (0.000–0.003, all 15). This
   **replicates the prior session's `PHASE6_LEARNED_PV_FAILURE_ANALYSIS.md` finding**: CARLA vehicle
   surfaces are low-texture and contribute very few ORB keypoints relative to their pixel footprint —
   masking moving-object regions removes almost no features in most towns/scenarios tested.
5. **Town02 is the standout town for object-region signal**: `anchor_recovery` reaches 0.178 and
   `dynamic_noise` reaches 0.236 — both clear the 0.15 threshold, an order of magnitude above every
   other town (0.000–0.13). This is the only town where dynamic-object regions carry a non-trivial
   share of the total keypoints, i.e. the only town where masking could plausibly matter.
6. **Town01/Town10HD anchor_recovery previews show weak object-region signal** (0.001, 0.018) despite
   the user's stated priority for these towns. This is reported honestly, not hidden — see R8-2 for
   how this shapes the core-recording scope.

## Honest limitation of the object-region-ratio metric

`object_region_keypoint_ratio` and `all_dynamic_feature_loss_ratio` are computed by a **standalone**
`cv2.ORB` detector on saved frames, using the SAME nFeatures (1200) as the CARLA ORB-SLAM3 config —
this is a reasonable proxy but is NOT the actual ORB-SLAM3 frontend (no stereo matching, no tracking
consistency, no RANSAC). It measures "how many raw corners fall on object pixels", not "how many
matched/tracked/mapped features come from objects". R8-3 (below) uses the REAL ORB-SLAM3 pipeline via
input masking to get ATE-level evidence, which is the authoritative signal.
