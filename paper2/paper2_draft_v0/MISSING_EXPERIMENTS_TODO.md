# MISSING EXPERIMENTS TODO — Paper-2 Draft v0

> Everything required before this draft becomes submission-ready. Status is honest: nothing here is "done".
> Priority: **P0** = blocks main claims, **P1** = strengthens, **P2** = nice-to-have.
> Owner/effort are rough estimates for planning, not commitments.

| # | item | priority | why needed | depends on | rough effort |
|---|---|---|---|---|---|
| 1 | **stereo KITTI redo** | P0 | monocular bbox-height depth confounds velocity & `bbox_depth_consistency`; reviewers will ask; apples-to-apples with CARLA stereo | image_03 re-download (~95% done), `unzip -t` clean | M (rebuild KITTI dataset + rerun TCSV) |
| 2 | **leakage audit** | P0 | must prove all 14 features are runtime-observable & only the label uses GT | feature list frozen | S (audit script + table; per-feature provenance) |
| 3 | **public/proxy baseline implementation** | P0 | current baselines insufficient: Qiu-style observability gate, SelectiveNet, KF/CV smoothing, YOLO-conf gate, bbox-depth gate | RELATED_WORK_BASELINE_PLAN items 3–7 | L (multiple baselines) |
| 4 | **planner-facing TTC/risk minimal evaluation** | P1 | substantiates C3 / §VIII; shows refusal reduces dangerous downstream errors | emitted/refused states from TCSV | M (TTC estimate + risk-at-coverage; minimal, not a planner) |
| 5 | **failure gallery** | P1 | qualitative credibility: car-following / lateral-crossing / occlusion regimes | per-regime tagging | M (figure assembly) |
| 6 | **feature-importance (SHAP) plot** | P1 | make "temporal-consistency dominates (via raw_speed)" crisp; permutation done, SHAP more intuitive | `pip install shap` (not installed) | S (once shap available) |
| 7 | **risk-coverage figure cleanup** | P1 | `figs/fig_tcsv_riskcov.png` exists but draft-quality; need publication styling + baselines #3–7 overlaid | baselines run (#3) | S |
| 8 | **threshold-robustness update after TCSV grouping fix** | P0 | the 27/27 threshold-robust claim predates the `(town,run,track_id)` regroup; must regenerate | grouping fix (done in features) | S (rerun `paper2_v5_threshold_robustness.py` w/ new grouping) |
| 9 | **CARLA grouping-fix update in OLD reports** | P0 | `PAPER2_SELECTIVE_VALIDITY_RESULTS.md` reports CARLA +0.117 (AUROC 0.873) under buggy grouping; correct to ~+0.045 (0.800) | — | S (edit old report + note) |
| 10 | **Qiu 2018 claim-boundary table** | P1 | precisely scope our novelty vs Qiu; avoid "first observability gate" overclaim | read Qiu 2018 carefully | S (table + verified cells) |

## P0 critical path (do these first, in order)
1. **#9 + #8** — fix the record (grouping correction + threshold-robustness regen). Cheap, removes inconsistency.
2. **#2 leakage audit** — protects the whole no-leakage claim.
3. **#3 baselines** (start with Qiu-style #3 and SelectiveNet #7) — without these the "beats baselines" claim is thin.
4. **#1 stereo KITTI redo** — biggest data-quality lever; affects almost every number.

## Honest notes
- Until #3 is done, §VII-A's baseline column is incomplete; the draft says so via `[TODO]`.
- #1 may shift KITTI numbers (currently monocular); do not freeze abstract numbers before it.
- Do not add experiments outside this list (scope guard); frontier/trajectory planning → Paper-3.
- Do not re-tune thresholds or re-pick sequences to improve numbers; gated-execution discipline.
