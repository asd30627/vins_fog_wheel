# FIGURE & TABLE PLAN — Paper-2 Draft v0

> Planned figures/tables for the journal. Status: **ready** (asset exists), **draft** (exists, needs cleanup),
> **TODO** (not made). Source artifact noted. Honest: most are draft/TODO.

## Figures

| id | title | status | source / `[TODO]` | section |
|---|---|---|---|---|
| F1 | Concept: emit full-state vs refuse-to-position-only (system diagram) | TODO | hand-drawn | I / V |
| F2 | Velocity- vs position-validity by range, CARLA vs KITTI | draft | `figs/fig_v5_validity_by_distance.png`, `fig_v5_kitti_vs_carla_validity.png` | VI-A |
| F3 | **Risk-coverage curves** (TCSV vs gates), CARLA & KITTI | draft | `figs/fig_tcsv_riskcov.png` — needs baselines #3–7 overlaid + styling | VII-A |
| F4 | Permutation importance by group (GEO/TEMP-base/TEMP-resid) + top features | TODO | from `paper2_tcsv_importance.csv` (barh) | VII-C |
| F5 | SHAP summary (temporal-consistency story) | TODO | needs `shap` install — MISSING_EXP item 6 | VII-C |
| F6 | Temporal-window ablation (AURC vs W) | TODO | from `paper2_tcsv_window_ablation.csv` | VII-D |
| F7 | Failure gallery (car-following / lateral-crossing / occlusion) | TODO | per-regime frames — MISSING_EXP item 5 | VIII |
| F8 | Planner-facing TTC/risk reduction at fixed coverage | TODO | MISSING_EXP item 4 | VIII |
| F9 | TCSV-rule (depth-3 tree) box | draft | rule listing in `PAPER2_TCSV_RESULTS.md` §5 | VII-F |

## Tables

| id | title | status | source / `[TODO]` | section |
|---|---|---|---|---|
| T1 | Related-work taxonomy (estimate vs refuse; geometry vs learned; decision-level; real-data) | TODO | RELATED_WORK item 10 | II |
| T2 | Validity by distance bin (CARLA/KITTI, pos & vel) | ready | `PAPER2_KITTI_TRACKING_VALIDITY_RESULTS.md` | VI-A |
| T3 | Near-contact / collision audit summary (24 runs, 3.8%) | ready | `PAPER2_CARLA_COLLISION_AUDIT.md` | VI-B |
| T4 | **Main results: selective-risk per scenario** (AUROC/AURC/overconf@ret + all baselines) | draft | `paper2_tcsv_metrics.csv` — baselines #3–7 still TODO | VII-A |
| T5 | New-residual vs OLD10 ablation (honest: net neutral) | ready | `PAPER2_TCSV_RESULTS.md` §2 | VII-B |
| T6 | Permutation-importance table | ready | `paper2_tcsv_importance.csv` | VII-C |
| T7 | Temporal-window ablation table | ready | `paper2_tcsv_window_ablation.csv` | VII-D |
| T8 | Cross-dataset transfer (CARLA→KITTI weak; +calibration strong) | ready | `paper2_tcsv_metrics.csv` | VII-A / IX |

## Headline asset
- **F3 (risk-coverage) + T4 (selective-risk table)** carry the paper's method claim. Both are **draft** because
  baselines #3–7 (RELATED_WORK_BASELINE_PLAN) are not yet run. Do not finalize until those land.

## Notes / honesty
- F2/T2/T3 are the most solid (phenomenon + audit, already validated).
- T5 must stay framed as a *neutral/negative* result (new residuals don't net-improve) — do not redraw to imply a gain.
- All "ready" tables still need the **stereo-KITTI redo** (MISSING_EXP item 1) before numbers are frozen.
