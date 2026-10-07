# PAPER2 — LOCALIZATION DATA-QUALITY DECISION (final)

> Synthesis of Phases -1..-4 + Phase 1. Honest answers to the data-quality questions. Date 2026-07-01.
> Evidence: PAPER2_RECORDING_QUALITY_AUDIT.md, PAPER2_CARLA_SPAWN_BUG_AUDIT.md,
> PAPER2_CLEAN_BENCHMARK_MANIFEST.md, PAPER2_CARLA_RERECORD_{PLAN,PREVIEW_RESULTS}.md, PAPER2_VINS_MASKING_LIMITATION_AUDIT.md.

## 1. Does the raw CARLA recording have spawn / visibility problems?
**Yes, two distinct bugs.**
(a) **Global-spawn-point placement** — NPCs are spawned at the map's fixed global `spawn_points[(i+1)%N]`, never
relative to the ego route, so on most maps they are hundreds of metres away (rng_median 80–620 m; even PASS_CORE
runs are 50–84% >150 m). (b) **Spawn collision** — an NPC can spawn on top of the ego (Town07 dense_b1: 56% of
detections are near-full-frame bboxes at 1.26 m). Root cause + fix in PAPER2_CARLA_SPAWN_BUG_AUDIT.md.

## 2. Which runs are excluded? Which re-recorded?
Of 48 runs: **25 PASS_CORE, 6 LOW_YIELD (appendix), 17 INVALID (excluded / re-record).** INVALID list &
per-run stats in the manifest. The 17 INVALID are queued for re-record (priority: Town06 rotated, Town01 sparse,
Town07 dense_b1 collision, Town10HD/Town07 sparse-rotated).

## 3. Did re-recording pass the quality gate?
**No — re-record is NOT yet done.** The spawn-placement fix (`--npc-near-band`) was implemented and preview-
tested; it correctly selects near candidate points but the **preview FAILED the gate** (objects still ~578 m
away on Town06 — NPCs disperse on the highway during the ego's static/ramp phase; CARLA also crashed on a
map switch). A second fix (delay NPC autopilot / spawn-retry / non-highway towns / longer drive) is required
before re-record. Per the gate, **no bulk re-record was performed** (avoids reproducing bad data).

## 4. Was the earlier VINS masking corrupted by data quality?
**Partially, yes.** Of the 4 runs used in the prior Phase-C masking: Town01 dense_b1 & medium_b1 = clean
PASS_CORE + stable baseline (valid); Town06 dense_b1 = clean data but UNSTABLE baseline (ATE 41 m, 84% far);
Town07 dense_b1 = **INVALID (spawn collision)** — the +29% "masking hurts" was a data artifact, not a method
failure. The "mixed/erratic" conclusion was driven by the 2 bad runs. On the 2 clean runs, masking gave a
consistent small improvement (−10.5% / −2.8% ATE, 0 failures).

## 5. Also: `validity_aware` ≠ TCSV-M
The prior `validity_aware` variant was a **raw-speed gate**, not the Part-1 learned TCSV-M. Acknowledged and
corrected in the plan (Phase 2 tooling). Any future validity-aware claim must use the actual model.

## 6. Usable clean set (now)
- **VINS-masking core (clean + stable baseline verified):** Town01 dense_b1, Town01 medium_b1.
- **Object-validity / TTC core:** the 25 PASS_CORE runs (baseline VINS stability not required for those).
- Excluded from all core results: the 17 INVALID runs.

## 7. What re-record needs before it can proceed
1. Delay NPC autopilot until ego drive phase (highest leverage).
2. Spawn-retry with positional jitter so all requested NPCs actually spawn near.
3. Prefer compact towns / route-constrained NPCs; longer recorded drive phase.
4. Fresh CARLA container per town (the `-maps` image is unstable on in-process map switching).
Then: re-probe → re-audit → confirm PASS_CORE → re-aggregate → re-run experiments.

## Verdict
The dataset had real spawn/visibility defects; they are now **diagnosed, classified, and partially fixed**. The
clean core (25 PASS_CORE; 2 with verified stable VINS baselines) is usable and honest; the 17 INVALID runs are
excluded and queued for a **properly-fixed** re-record (not done tonight, gated by the preview failure). No
placeholder/invalid data enters core results.
