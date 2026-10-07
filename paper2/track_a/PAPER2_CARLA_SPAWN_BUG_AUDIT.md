# PAPER2 Phase -2 — CARLA SPAWN / RECORDING ROOT-CAUSE AUDIT

> Why so many dynamic_v3 recordings have objects hundreds of metres away (YOLO det≈0) or an object glued
> to the camera. Source read: `/home/ivlab3/fwvio_ws/scripts/collect_carla_v2.py`. Date 2026-07-01.

---

## 1. How dynamic objects are generated (the bug)

`collect_carla_v2.py`, lines 170–174:
```python
n_npc = args.npc if args.npc >= 0 else (60 if "dynamic" in args.condition else 0)
for i in range(n_npc):
    bp = rng.choice(bl.filter("vehicle.*"))
    sp = spawn_points[(i + 1) % len(spawn_points)]     # <-- ROOT CAUSE
    npc = world.try_spawn_actor(bp, sp)
    if npc: npc.set_autopilot(True, tm.get_port())
```

**NPCs are placed at the map's fixed global `spawn_points`, indexed sequentially (`spawn_points[1], [2], …`)
— NOT relative to the ego's position or route.** The ego then drives a small loop from its own spawn point;
whether any NPC is ever visible is pure luck of map geometry.

## 2. Answers to the audit questions
1. **How generated?** `world.try_spawn_actor` at global map spawn points, autopilot on. No ego-relative logic.
2. **Ego-relative or world-absolute?** **World-absolute** (global `spawn_points`). This is the bug.
3. **Same world coords across towns?** No — each town's `get_spawn_points()` is its own map layout. Big maps
   (Town06 highway) have spawn points spread over km; compact maps (Town10HD) pack them → Town10HD is the only
   town that passes well, Town06 is worst. (Confirmed by Phase -1: Town10HD 9–10 PASS_CORE, Town06 mostly INVALID.)
4. **How are r30/r60/r90 rotated?** They are **NOT NPC rotations.** The jobfile's last column is `--spawn-index`
   (line 80) = the EGO's spawn-point index (route variation: b1→0, r30→30, r60→60, r90→90). NPCs stay at
   `spawn_points[1..n]` regardless, so moving the ego to index 30/60/90 often puts it **further** from the fixed
   NPC cluster → rotated runs are frequently worse (Town06 r-runs: object rng_median 400–620 m).
5. **Ego start/heading aligned with NPC spawn zone?** No alignment at all — independent indices.
6. **Why Town06 sparse_r30 → 26 GT objects all >160 m?** Town06 is a large highway map; ego at
   `spawn_points[30]`, only 25 NPCs at `spawn_points[1..25]` scattered across the map → none near the ego route.
7. **Is the ego in per_instance?** **Yes** — confirmed: a self-actor at range≈0 (e.g. id 424, range 0.0,
   speed>0). The audit now excludes it (range<2 m). (Prior stats were not corrupted by it, but it must be excluded.)
8. **Camera FOV / projection correct?** Yes — validated: matched detections are all flagged in-FOV by the
   independent ego-yaw+fov check; projection is fine. The problem is object placement, not the camera.
9. **YOLO det=0 cause?** Objects **not in frame / too small** (beyond ~150 m a car is 1–3 px at 640×480), NOT a
   detector fault. Where objects are near, YOLO detects them normally.

## 3. Second defect — spawn collision (object glued to camera)
Town07 dense_b1: **61% of detections are near-full-frame bboxes** (~304,751 px² of 307,200; centred at image
centre; range **1.26 m**). An NPC spawned on top of / immediately in front of the ego and stayed there. This
starves VINS of background features and is the true cause of the Phase-C "masking makes Town07 WORSE (+29%)"
anomaly. Cause: `try_spawn_actor` at a spawn point coincident with (or adjacent to) the ego's, with no
min-distance-from-ego guard. Detector added to the audit (`frac_fullframe ≥ 0.30 → INVALID`).

## 4. Affected towns/runs (from Phase -1 audit)
- **Systematic far-object**: all sparse runs (few NPCs), all Town06 (big map), most rotated (r30/r60/r90) runs.
- **Spawn collision**: Town07 dense_b1 (and any other run flagged `frac_fullframe≥0.3` in the re-run audit).
- Town10HD (compact) is the healthiest town; Town01 dense/medium are usable; Town06/Town07 sparse/rotated are not.

## 5. Fix (spawn NPCs on/near the ego route, with a min-distance guard)
Replace the global-spawn-point loop with **ego-relative spawning**:
```python
ego_loc = ego.get_transform().location
# rank map spawn points by distance to ego; keep a near band [MIN_D, MAX_D]
cand = sorted(spawn_points, key=lambda sp: sp.location.distance(ego_loc))
cand = [sp for sp in cand if MIN_D <= sp.location.distance(ego_loc) <= MAX_D]   # e.g. MIN_D=8, MAX_D=60
for i in range(n_npc):
    sp = cand[i % len(cand)]
    npc = world.try_spawn_actor(bp, sp)
    ...
```
- `MIN_D≈8 m` prevents the glued-to-camera collision; `MAX_D≈60 m` keeps NPCs in detectable range.
- Optionally bias toward spawn points **ahead** of the ego (dot(sp−ego, ego_forward) > 0) so they enter the
  camera FOV as the ego drives.
- Alternatively, spawn along the ego's planned route waypoints (the script already computes a `route`).
- Keep the min-distance guard so "dense" really means many NEAR vehicles, not many far ones.

This is a **spawn-script fix only** — it does not touch VINS, the estimator, or GT logging.

## 6. Recommendation
- Patch `collect_carla_v2.py` NPC spawn as above (new flag e.g. `--npc-near-band 8,60`, default off to preserve
  reproducibility of old runs).
- Preview-gate (Phase -3) before any full re-record.
- Re-record ONLY the runs Phase -1 marked INVALID/LOW_YIELD that are needed for core experiments; keep the
  PASS_CORE runs as-is (see `PAPER2_CLEAN_BENCHMARK_MANIFEST.md`).
