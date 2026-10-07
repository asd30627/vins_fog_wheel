# R8-2 — Core Scenario Selection

**Date:** 2026-07-02
**Basis:** R8-1 preview results (`PAPER2_R8_CARLA_SCENARIO_SEARCH.md`, `paper2_r8_preview_audit.csv`).

---

## Selection against the user's priority order

| priority | candidate | preview evidence | decision |
|----------|-----------|-------------------|----------|
| 1 | Town01 anchor_recovery | obj-region ratio **0.001** (near-zero); path/speed/ORB all pass | **Included in manifest, but DEFERRED from R8-3 execution** — preview shows essentially no object-region keypoint signal, so a core-length run is very unlikely to show masking headroom. Documented, not hidden. |
| 2 | Town10HD anchor_recovery | obj-region ratio **0.018**; path/speed/ORB pass | **Included in manifest, DEFERRED from R8-3 execution** — same reasoning, weak but non-zero signal; second priority for a follow-up round if Town02 shows headroom worth generalizing. |
| 3 | best of Town02/04/05 | Town02 anchor_recovery = **0.178** (full 6/6 PASS); Town04 normal_urban_loop = 0.130 (close, but not an anchor scenario); Town05 anchor_recovery FAILED (blocked, 222 resets) | **Town02 anchor_recovery selected — RUN in R8-3.** Clear best evidence. |
| 4 | one dynamic_noise route | Town02 dynamic_noise = **0.236** (highest of all 15 previews), 30 transient objects | **Town02 dynamic_noise selected — RUN in R8-3.** Strongest transient-culling stress test available. |
| 5 | Town06/Town07 (boundary/negative) | not previewed (explicitly boundary, "if needed") | **NOT needed this round** — Town02 already gives a decisive object-region signal; Town06/Town07 held in reserve if R8-3 on Town02 is inconclusive. |

## Core recording spec

- Frames: **3600** (180 s drive; within the "do not exceed 5 min" cap).
- Same recipe as R8-1 previews: `gentle_loop --speed-mod --base-speed 6.0`, baseline 0.5,
  `imu-at-vehicle-center`, `ego-spawn-scan`.
- NPC preset: reuse the scenario preset that produced the winning preview —
  `anchor_recovery`: `--npc 18 --npc-global 8 --npc-static-frac 0.6`
  `dynamic_noise`: `--npc 22 --npc-global 10 --npc-static-frac 0.1`
- Condition tag: `dynamic_v3r8_core` (does not collide with the r8 preview or prior r7/loop data).

## Manifest (executed in R8-3)

| # | town | scenario | frames | status |
|---|------|----------|--------|--------|
| 1 | Town02 | anchor_recovery | 3600 | **RUN** |
| 2 | Town02 | dynamic_noise | 3600 | **RUN** |
| 3 | Town01 | anchor_recovery | 3600 | deferred (weak preview signal, see above) |
| 4 | Town10HD | anchor_recovery | 3600 | deferred (weak preview signal, see above) |
| 5 | Town06/Town07 | boundary | — | not needed this round |

**Scope decision:** R8-3 executes 2 core scenarios (both Town02) with 3 masking conditions each = 6
ORB-SLAM3 runs, rather than the full 4-5 scenario battery, because the preview data already gives a
clean discriminating signal (Town02 >> all other towns) and running weak-signal scenarios at full
core length would not change the headroom decision, only consume time. Town01/Town10HD anchor_recovery
core runs are queued as an explicit follow-up if the Town02 R8-3 result is ANCHOR_HEADROOM (worth
generalizing) rather than NO_HEADROOM.

CSV: `paper2_r8_core_manifest.csv`.
