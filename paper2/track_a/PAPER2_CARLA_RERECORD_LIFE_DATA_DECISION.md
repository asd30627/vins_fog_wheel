# PAPER2 — CARLA RE-RECORD / LIFE-DATA DECISION (Phase R, honest interim)

> Answers the 9 questions after R0 (stop) + R1 (recorder patch) + preview iteration. CARLA = Docker
> `carla_dyn` restarted on :3000. New runs named `dynamic_v3fix` (old `dynamic_v3` untouched). Date 2026-07-01.
> **STOP point: a scenario-design conclusion reached that changes the plan — reporting before the
> multi-hour 4-town campaign.**

## 1. Why is the old data not enough?
Partly — but **less than assumed**. The far-object / det=0 failures are concentrated in **Town06
(highway: NPCs outrun the FOV), Town07 dense_b1 (spawn-collision, full-frame bbox), and the rotated/
sparse runs**. The already-PASS_CORE runs (Town01/Town10HD dense & medium) were NOT far-object-limited.

## 2. Which towns' old data has far-object / collision problems?
- **Town06**: highway, global spawn → NPCs drive off; most objects >150 m (dense_r30/r60/r90, medium_r*
  INVALID). 
- **Town07**: dense_b1 = spawn-collision (56% dets fill >50% frame); several sparse/rotated far.
- Town01/Town10HD sparse & rotated: some far/thin.
- **Town01 dense_b1 (old) was fine**: 1180 matched, **777 objects <50 m**, 31 tracks — PASS_CORE. It did
  NOT need re-recording. Same for Town10HD dense/medium.

## 3. What did the new recording script fix (validated)?
`collect_carla_v2.py` (patched, compiles, preflight OK): ego-relative NPC spawn from the dense road
network; **autopilot delay** (NPCs braked through settle/static/ramp, released at drive start — verified);
collision guard (`--npc-min-dist`); spawn retry/jitter; slow-traffic (`--npc-target-speed-frac`, for
Town06); forward-cone + lane-align; **on-route placement** (`--npc-on-route`, NPCs on the ego's forward
driven lane); `--run-kind` (preview/core/long_inertial); full meta logging. All mechanisms work.

## 4. Per-town preview results
Only **Town01** previewed (validation). Result: the near-route/on-route placement **fixes the GT
distribution** (median range 44 m, ~26 near-ahead objects/frame, only 2% >150 m) BUT the **camera sees an
empty road facing a wall** → YOLO det = 1–2 over 260 frames in all three variants (near-band, cone,
on-route). Root cause: **ego spawn_index 0 on Town01 faces a wall/road-end**, so geometrically-"ahead"
NPCs are occluded or off the actual driven view. Straight-line/on-lane near placement ≠ camera-visible
when the spawn viewpoint is bad.

## 5. Which new runs can enter core experiments?
**None yet** — no core re-record was made (correctly gated on cracking visibility).

## 6. Is the VINS baseline smoke normal?
Not run — gated on a PASS_PREVIEW, which none reached.

## 7. Do we have the data conditions to find TCSV/VINS life?
**Not from the re-record path yet — but we may not need it for the good towns.** Key correction:

- The near-route rework **hurts already-good Town01** (empty view) because it concentrates NPCs on a
  wall-facing geometry, whereas the **old GLOBAL spawn populated the whole map's real roads → 1180
  detections** on the ego's actual route. For coverage-over-a-drive, global/dense spawn beats a
  straight-line near cone.
- So the honest data plan is: **(a) KEEP the old PASS_CORE runs** (Town01/Town10HD dense & medium — they
  already have hundreds of near objects); **(b) apply the near-route + slow-traffic + collision-guard
  fixes ONLY to the towns that actually failed** (Town06 highway, Town07 collision), and validate the
  preview THERE, not on Town01; **(c) for placement, prefer a HYBRID — keep global/dense NPC density for
  route coverage AND add near-band NPCs — or pick an ego spawn_index that faces a long open road**, since
  a good viewpoint matters more than geometric near-placement.

## 8. If not ready, where is it stuck?
Stuck at **camera-visibility of near objects on a bad ego viewpoint**. The recorder mechanism is done;
the blocker is scenario design: (i) ego spawn_index selection (avoid wall-facing starts), (ii) global vs
near spawn trade-off (global gives coverage, near guarantees proximity), (iii) validating on the towns
that need it (Town06/07). Iterating this on Town01 (which didn't need fixing) was the wrong target.

## 9. Recommendation (needs裁示)
1. **Do NOT re-record Town01/Town10HD dense & medium** — old data is PASS_CORE with 500–2000 near objects.
2. Re-record **Town06 (slow-traffic near-route) + Town07 (collision-guard near-route)** with the patched
   recorder, and **preview-gate on THOSE towns**. Choose ego spawn_index by a quick 3–4 index scan for a
   long-open-road viewpoint (avoid wall-facing spawn 0 where it fails).
3. For placement use **hybrid global+near** (coverage + guaranteed proximity), not a pure forward cone.
4. Add the long_inertial run only after a core preview passes.
5. Then VINS baseline smoke (DET2, repeat×2) on the new PASS_CORE + the retained old PASS_CORE.

**No TCSV / soft-weighting / dynamic-factor / FOG-grid this round (per instruction).** The life-gate
signal (degraded-gyro object-mask −14%, object-specific) is preserved for after the data is confirmed.
