# PAPER2 — CLEAN BENCHMARK MANIFEST V2 (after dynamic_v3fix re-record)

> Which runs may enter core VINS/TCSV experiments, after the Phase-R re-record of the broken towns.
> New runs = `dynamic_v3fix` (hybrid spawn recipe); old `dynamic_v3` untouched. Quality gate = YOLO
> **matched<50 m** near-detection yield (NOT pct>150 m, which is inflated by intentional far
> global-coverage NPCs). Date 2026-07-01.

## Recipe used for the new runs
`--npc-global 55` (map coverage) + ~16–20 near-band (`--npc-near-band 8,70 --npc-on-route`) +
`--ego-spawn-scan` (open-road viewpoint) + `--npc-autopilot-delay` + `--npc-min-dist 8` (collision guard);
Town06 `--npc-target-speed-frac 55` (slow highway). 640×480. `--run-kind` preview(100)/core(720).

## New runs (dynamic_v3fix) — quality
| run | kind | drive_f | spawned | det/f | matched | **matched<50m** | glued-face | class |
|---|---|---|---|---|---|---|---|---|
| Town06 dense_near_core | core | 720 | 74 | 5.42 | 4336 | **3681** | 0 | **PASS_CORE_NEW** |
| Town06 medium_near | preview | 100 | 42 | 8.17 | 1952 | 1582 | 0 | PASS_PREVIEW |
| Town06 dense_slow | preview | 100 | 75 | 7.70 | 1995 | 1747 | 0 | PASS_PREVIEW |
| Town07 dense_near_core | core | 720 | 72 | 1.14 | 158 | **149** | 0 | **PASS_CORE_NEW** |
| Town07 medium_near | preview | 100 | 42 | 1.00 | 4 | 4 | 0 | INVALID_NEW (rural: too sparse) |
| Town07 dense_slow | preview | 100 | 73 | 1.00 | 38 | 35 | 0 | LOW_YIELD_NEW |

## Verdict per town
- **Town06 (was INVALID: highway far-spawn) → RECOVERED.** dense_near / medium_near / dense_slow all pass;
  dense_near_core = **PASS_CORE_NEW** with 3681 near matched detections over 720 drive frames, no
  glued-face. Slow-traffic + spawn-scan + hybrid coverage fixed it. **Usable for object-validity + VINS
  routing + TTC.**
- **Town07 (was INVALID: spawn-collision) → PARTIALLY RECOVERED.** dense_near_core = **PASS_CORE_NEW**
  (149 near, no glued-face — collision guard fixed the face-fill). But it is a **rural town with sparse
  roads**: medium density = INVALID (matched<50m=4), dense_slow = LOW_YIELD. Only the dense_near setting
  yields enough near objects. Usable at dense_near only.

## Combined usable set for core experiments
- **Retain old PASS_CORE (unchanged, already good):** Town01 dense_b1 & medium_b1 (777 / 865 near),
  Town10HD dense/medium (+ others from the v1 manifest).
- **Add new PASS_CORE_NEW:** Town06 dense_near_core, Town07 dense_near_core.
- **Appendix (LOW_YIELD_NEW):** Town07 dense_slow.
- **Excluded (INVALID_NEW):** Town07 medium_near (rural sparse).

## Improvement vs old dynamic_v3
- Town06: old dense_r30/r60/r90 & medium_r* were >150 m / matched≈0 INVALID → new dense_near_core has
  3681 near matched detections. **matched<50 m: 0 → 3681.**
- Town07: old dense_b1 spawn-collision (56% full-frame) → new dense_near_core glued-face 0.0, 149 near.
  **collision eliminated.**
- >150 m no longer a limiter for the DETECTED set; spawn collision eliminated (min-dist guard).

## R6 PASS_CORE_R6 — VINS-ready (2026-07-01)

Three-root-cause fix applied (`--npc-skip-ego-lane + --imu-at-vehicle-center --baseline 0.2 + --drive-mode gentle_turn`).
New recording names: `Town0X__dynamic_v3fix__rundense_near_r6_core`.

| run | near-band candidates | ego path | rep1 n/early/late/ATE | rep2 ATE | verdict |
|---|---|---|---|---|---|
| **Town06 R6 core** | 11 adj-lane (0 oncoming; one-way highway) + 55 global | 147.3 m | 840/**0.995**/2.233/29.42 m | 29.42 m (0%) | **PASS_DET** |
| **Town07 R6 core** | 8 oncoming + 55 global | 150.2 m | 840/**0.997**/2.208/27.57 m | 28.20 m (2.3%) | **PASS_DET** |

**Scale drift (late≈2.2)** is consistent and deterministic — acceptable for relative life-gate comparisons (masked vs baseline ATE difference). SNR ≈ 6× (4m expected signal / 0.6m variance). Absolute ATE higher than Town01 stock config because (a) DET2 single-thread, (b) Town06 highway + Town07 rural have less yaw excitation than urban Town01. See `PAPER2_RERECORDED_VINS_BASELINE_SMOKE.md` for full analysis.

## Next (gated — STOP here, await decision)
Life gate experiments (Phase 2–3): run `ideal_imu` vs `industrial_fog` with/without object masking on Town06 R6 + Town07 R6 cores. Expected signal: ~14% ATE reduction with masking under industrial_fog (from Town01 evidence). Use DET2 ×3 reps (median), NOT single run.

OLD PASS_CORE (Town01/Town10HD) → keep unchanged, still the reference baselines.
