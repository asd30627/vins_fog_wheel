# PAPER2 Phase R2 — CARLA RE-RECORD PREVIEW RESULTS V2 (honest, in-progress)

> Preview validation of the patched `collect_carla_v2.py` dynamic_near_route mode. CARLA = Docker
> `carla_dyn` (carlasim/carla:0.9.16-maps), restarted on :3000. All new runs named `dynamic_v3fix` (old
> `dynamic_v3` untouched). Date 2026-07-01. **Status: recorder mechanism validated; a camera-VISIBILITY
> blocker found — reporting before the full 4-town campaign.**

## What the R1 patch added (validated mechanically)
- Ego-relative NPC spawn from the DENSE drivable road-network (`generate_waypoints(4m)`) in a near band
  (default 8–70 m) — fixes the "only 11 sparse map spawn_points" problem (→ 32–58 candidates).
- Collision guard (`--npc-min-dist 8`), spawn retry/jitter, **autopilot delay** (NPCs held braked through
  settle/static/ramp, released at drive start — verified "released N/N NPC autopilot at drive frame 160").
- Slow-traffic knob (`--npc-target-speed-frac`, for Town06 highway), forward-cone + lane-align filter,
  `--run-kind`, and full meta logging (requested/spawned/retries/collisions/release_frame/run_kind).
- Verified: `spawned/requested` 0.63 (near-band, 44/70) and the GT object distribution is now NEAR:
  **median range 44 m, ~26 forward objects <50 m per drive frame, only 100/4500 >150 m** — the old
  "objects all >150 m" problem is fixed AT THE GT LEVEL.

## The blocker: GT-near ≠ camera-visible
Despite GT showing ~20–26 near-ahead objects per frame, **the YOLO probe detects only 1–2 over 260
frames**, and the drive-phase images show an **empty road facing a wall**. Root cause:
- Ego spawn_index 0 on Town01 faces a wall/open plaza; the near-band/forward-cone places NPCs on road
  waypoints that are **occluded (behind the wall) or off the actual driven lane**. Straight-line geometry
  ("ahead within 70 m") does not equal "in the camera view down the road the ego drives".
- **The forward-cone made Town01 WORSE, not better**: preview2 (wide ahead) det=1, preview3 (±40° cone)
  det=2. Over-constraining to a geometric cone concentrated NPCs onto an occluded/wall direction.

## Re-examination of the premise (important)
The old `dynamic_v3` **Town01 dense_b1 was already PASS_CORE**: 1180 matched, **777 objects <50 m**, 31
tracks — it did NOT have the far-object problem. Old GLOBAL spawn scattered NPCs across the map's real
roads, so many landed on the ego's actual driven road → lots of visible detections. The ">150 m / det=0"
failures were specific to **Town06 (highway, NPCs outrun FOV), Town07 dense_b1 (spawn-collision), and the
rotated/sparse runs** — not Town01/Town10HD dense/medium.

→ Implication: the fix should **target the bad towns/conditions** (Town06 highway slow-traffic, Town07
collision-guard), and for NPC placement should spawn on the **ego's forward DRIVEN LANE/route** (follow
`waypoint.next()` down the ego's road), NOT a straight-line cone that can face a wall. The near-band by
straight-line distance is necessary but not sufficient; on-lane placement is what guarantees visibility.

## Preview runs so far (Town01, 100 drive frames each)
| run | mode | cand | spawned/req | GT<50m/frame | YOLO det | camera |
|---|---|---|---|---|---|---|
| dense_near_preview | spawn_points near-band | 11 | 11/70=0.16 | — | — | (sparse spawn_points) |
| dense_near_preview2 | dense-wp near-band (ahead hemi) | 58 | 44/70=0.63 | ~26 | 1 | empty/wall |
| dense_near_preview3 | dense-wp forward-cone ±40° | 32 | 30/70=0.43 | ~20 | 2 | empty/wall |

All FAIL_PREVIEW on detections (det≪50). The mechanism works; the placement-visibility does not yet.

## Recommendation (needs裁示 before the multi-hour campaign)
1. **Spawn NPCs on the ego's forward route/lane** (build the ego route first via `waypoint.next()`, place
   NPCs at 6–15 m intervals on that lane + adjacent lanes) so they are provably on the visible driven
   road. This is a bounded additional patch to `collect_carla_v2.py`.
2. **Keep the good old runs** (Town01/Town10HD dense/medium) — they already pass; re-record only to add
   near-object density / longer runs, and PRIORITIZE the broken towns (Town06 slow-traffic, Town07 guard).
3. Then run the 4-town preview gate (medium_near/dense_near/dense_near_slow), audit, and only re-record
   PASS_PREVIEW settings.

**No core re-record run yet** — gated on cracking the on-lane visibility placement (step 1).

---

## UPDATE — HYBRID spawn cracks the broken towns (Town06, Town07)

Fix that worked = **hybrid global+near + ego-spawn-scan** (not pure near-route):
- `--ego-spawn-scan`: pick the ego spawn whose forward road stays straight+open longest (Town06 idx0 =150m, Town07 idx53 =150m) → camera looks down an open road, not a wall.
- `--npc-global 55`: global map spawn (route coverage, like the old working runs) ON TOP of ~16–18 near-band NPCs, all collision-guarded + autopilot-delayed.
- Town06: `--npc-target-speed-frac 55` (slow highway traffic so NPCs stay in FOV).

| town | mode | spawned | YOLO det | matched | matched<50m | det/frame | glued-face | class |
|---|---|---|---|---|---|---|---|---|
| Town06 dense_near | hybrid+scan+slow | 73 (18 near+55 glob) | 1497 | 1497 | **1358** | 5.76 | 0.0 | **PASS_PREVIEW** |
| Town07 dense_near | hybrid+scan+guard | 71 (16 near+55 glob) | 198 | 194 | 44 | 1.02 | 0.0 | **PASS_PREVIEW** |
| Town01 near-only (ref) | on-route (no global) | 22 | 1 | 0 | 0 | 0.0 | — | FAIL (spawn faced wall) |

Confirmed by eye: Town06 image = multiple near cars/van/rider on the driven road; Town07 = rural road
with vehicles ahead, no glued-face. **Town06 (was highway-far INVALID) and Town07 (was spawn-collision
INVALID) are now usable.** The collision guard removed the Town07 glued-face; slow-traffic kept Town06
NPCs near; spawn-scan removed the wall-facing viewpoint; global coverage restored the detections that pure
near-route lost. `matched<50m` is the real quality signal (pct>150m is inflated by intentional far
global-coverage NPCs — do not gate on it).

Next (gated): extend the same hybrid recipe to **medium_near / dense_near_slow** per town, add the
core (720+) and long_inertial (2400+) lengths, per-town preview-gate, then VINS baseline smoke (DET2 ×2).
Keep the already-PASS_CORE old Town01/Town10HD dense/medium.
