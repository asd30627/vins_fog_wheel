# PAPER2 Phase -3 — RE-RECORD PREVIEW RESULTS (spawn fix verification)

> Preview-gate the spawn fix BEFORE any bulk re-record. Honest outcome: **fix necessary but NOT sufficient;
> preview FAILED the gate → do NOT bulk re-record.** Date 2026-07-01.

## Previews run (80 recorded frames each, with the `--npc-near-band` fix)
| preview | config | spawn fix log | det | GT nearest obj @ frame 0 | gate |
|---|---|---|---|---|---|
| Town06 sparse_r30 | npc=25, band 8–60 m, ahead-only | "13 candidate spawn points near ego (of 436)" | 2 | 578 m | **FAIL** |
| Town06 dense_b1 | npc=70, band 6–45 m, surround | "11 candidate spawn points near ego (of 436)" | 4 | 578 m | **FAIL** |
| Town10HD sparse_r30 | npc=25, band 6–45 m | — | — | — | **CARLA CRASH on map load** |

## What the fix DID achieve
The near-band spawn selection works as designed: instead of 436 global spawn points, the loop now selects
11–13 points within 6–60 m of the ego (verified in the collect log). The spawn-placement bug is fixed.

## Why the preview still FAILS (honest root cause)
Per-instance GT logs ALL world vehicles (`collect_carla_v2.py:341`). In both Town06 previews only ~11 vehicles
exist and **all are ~578 m away even at frame 0** (constant across the 240 frames). So the near-spawned NPCs are
not near by the time recording starts. Diagnosis:
1. **NPCs get autopilot at spawn** and, on Town06's **highway**, accelerate away during the ego's un-recorded
   settle + recorded static/ramp phases (≈10 s of ego-stationary time) → they are far before the drive phase.
2. The near band yields only ~11–13 candidate points; cycling 25–70 NPCs over them means most `try_spawn_actor`
   calls collide (same points) and fail → few NPCs actually spawn, and those that do leave immediately.
3. Preview horizon (80 drive frames) is short; the original PASS_CORE dense runs got yield by brute force
   (70 NPCs × 560 drive frames × global scatter → some near by luck), which the near-band + short preview lack.

So the spawn-placement fix is **necessary but not sufficient**. A second fix is required.

## Additional required fixes (for a real re-record — NOT done tonight)
1. **Delay NPC autopilot** until the ego's drive phase begins (keep them parked/near during settle/static/ramp),
   or set NPC target speed low, so they remain in view.
2. **Spawn-retry / jitter**: if a near point is occupied, offset a few metres instead of reusing the same point,
   so all N NPCs actually spawn.
3. **Prefer compact/urban towns** (Town10HD) over highway (Town06) for object-dense recordings; or constrain NPC
   routes to the ego's route.
4. **Longer drive phase** (recorded), shorter static/ramp, for object-yield runs.
5. **CARLA `-maps` image is unstable on map switching** (crashed on Town06→Town10HD). Re-records should launch a
   fresh container per town (as the original campaign did) rather than switching maps in-process.

## Decision (preview gate)
- **Do NOT bulk re-record** with the current fix — it would reproduce the low-yield failure.
- The spawn-placement fix (`--npc-near-band`) is committed and correct as far as it goes; it is a prerequisite,
  not a complete solution.
- Re-record is deferred pending the additional fixes above (autopilot-delay is the highest-leverage one).
- Meanwhile, the **25 PASS_CORE runs** (esp. Town01 dense/medium with verified stable VINS baselines) remain
  the usable clean set for all downstream experiments; the 17 INVALID runs stay excluded.

## Artifacts
Preview recordings kept for reference: `/mnt/sata4t/datasets/carla_fwvio/Town0{6}__dynamic_v3__runpreviewfix_*`
(their per-det CSVs were removed from `outputs/paper2_perdet/` so they do not pollute the core set).
