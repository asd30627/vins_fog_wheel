# PAPER2 Phase -3 — TARGETED RE-RECORD PLAN (preview-gated)

> Fix the spawn design first, verify by preview, then re-record ONLY invalid runs. Never re-record
> PASS_CORE runs. Date 2026-07-01.

## 1. The fix (implemented)
`collect_carla_v2.py` now has `--npc-near-band MIN,MAX` (+ `--npc-ahead-only`): spawn NPCs at map
spawn points **within MIN–MAX metres of the ego** (default band `8,60`), instead of the legacy global
`spawn_points[(i+1)%N]`. MIN=8 m stops the glued-to-camera collision (Town07 dense_b1); MAX=60 m keeps
NPCs detectable. `--npc-ahead-only` further keeps only spawn points ahead of ego heading. Flag defaults
OFF → old runs reproduce exactly.

## 2. Preview gate (before any full re-record)
For each candidate run: record **60–80 frames** with the fix, run `paper2_raw_object_probe.py`, and require:
- matched detections > 0 and det/frame ≥ 0.5
- some objects <50 m (matched_lt50m ≥ a few)
- no spawn-collision (frac of full-frame bboxes < 0.30)
- objects in-FOV near > 0
Only a run that PASSES preview is recorded to full 720 frames. Preview results → `PAPER2_CARLA_RERECORD_PREVIEW_RESULTS.md`.

## 3. Re-record priority (17 INVALID runs)
1. **Town06** rotated + medium/sparse (7) — worst town, biggest beneficiary of ego-relative spawn.
2. **Town01** sparse b1/r30/r90 (3) — sparse spawned too far.
3. **Town07** dense_b1 (spawn collision) + sparse r30/r60 (3).
4. **Town10HD** medium_r60, sparse r30/r60 (3), Town06 remaining.
Keep NPC counts (sparse 25 / medium 50 / dense 70) but now NEAR the ego.

## 4. After re-record
- Re-run `paper2_raw_object_probe.py` → per-det CSVs (overwrite invalid ones).
- Re-run `paper2_recording_quality_audit.py` → confirm re-recorded runs now PASS_CORE.
- Re-aggregate benchmark + join → refreshed `paper2_raw_object_benchmark_all*.csv`.
- Update `PAPER2_CLEAN_BENCHMARK_MANIFEST.md`.
- Only then re-run Part-1 frame-vs-sequence and Part-2 VINS masking on the enlarged clean core set.

## 5. Scope note (honest)
Full re-record of all 17 invalid runs + re-running every downstream experiment is multi-hour. This session
verifies the FIX by preview (Town06, the worst case) and records a small confirmation set; the remaining
re-records are queued here for the user to approve/run. PASS_CORE runs (25) are already usable and untouched.
