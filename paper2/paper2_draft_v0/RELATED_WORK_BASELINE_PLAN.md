# RELATED WORK & BASELINE PLAN — Paper-2 Draft v0

> Current baselines are insufficient for a journal. This plan classifies each required baseline as
> **RUN (must actually run)** / **PROXY (approximate, can't fully reproduce)** / **TAXONOMY (related-work table only)**,
> with the metric each must report. Honest status as of draft v0.
> Metric vocabulary: AUROC, AURC↓ (area under risk-coverage), overconf@ret.8/.9 (overconfident-wrong velocity at
> fixed valid-retention), retention, false_refusal, F1_invalid. Selective-risk metrics (AURC, overconf@ret) are the
> headline; AUROC is secondary.

## Baseline matrix

| # | baseline | category | status now | metric(s) to report | notes |
|---|---|---|---|---|---|
| 1 | **no policy / always full-state** | RUN | ✅ done | overconf (=base invalid), retention=1, AURC | lower bound; already in `paper2_tcsv_metrics.csv` |
| 2 | **distance gate** | RUN | ✅ done | AUROC, AURC, overconf@ret.8/.9 | primary geometric baseline (−range) |
| 3 | **Qiu-style geometric excitation / observability gate** | RUN | ❌ TODO | AUROC, AURC, overconf@ret + binary accept/reject rate | implement excitation/observability score from raw motion; head-to-head vs TCSV. **Do NOT claim first observability gate.** |
| 4 | **YOLO confidence gate** | RUN | ⚠️ partial | AURC, overconf@ret | `det_conf` exists as a feature; need it as a *standalone gate* baseline |
| 5 | **bbox-depth uncertainty gate** | RUN | ⚠️ partial | AURC, overconf@ret | use `bbox_depth_consistency` + depth as standalone gate; tests appearance-uncertainty-only |
| 6 | **Kalman / constant-velocity smoothing baseline** | RUN | ❌ TODO | velocity error after smoothing → validity; AURC, overconf@ret | CV/KF smoother on raw track; gate by innovation magnitude. Tests "just smooth it" rebuttal |
| 7 | **SelectiveNet-style MLP selector** | RUN | ❌ TODO | AURC, overconf@ret, coverage at target risk | joint predictor+selector head with coverage constraint; the proper selective-prediction baseline vs our threshold-on-classifier |
| 8 | **OVI geometry** (logistic on geometry) | RUN | ✅ done | AUROC, AURC, overconf@ret | already in metrics; marginal over distance — keep as "geometry-only" point, do NOT oversell |
| 9 | **TCSV-rule / TCSV-HistGBM / TCSV-MLP** | RUN | ✅ done | full metric set + risk-coverage curve | our models; HistGBM = main |
| 10 | **Dynamic-SLAM reference table (Qiu 2018 / VDO-SLAM / DynaSLAM II)** | TAXONOMY | ❌ TODO | qualitative axes table (no rerun) | positioning only: estimation-vs-refusal, geometry-vs-learned, decision-level eval y/n, real-data y/n |

## What must actually RUN (priority order)
1. **#3 Qiu-style observability gate** — needed for the central "geometry is not the strongest signal" claim and the
   Qiu boundary in §II-E. Highest priority.
2. **#7 SelectiveNet** — needed so reviewers see we compared against a *proper* selective-prediction method, not
   only threshold-on-classifier.
3. **#6 KF/CV smoothing** — pre-empts the "why not just smooth" reviewer.
4. **#4 YOLO-conf gate, #5 bbox-depth gate** — cheap; promote existing features to standalone gates.

## PROXY (approximate, cannot fully reproduce)
- Qiu 2018 exact pipeline (no public code assumed) → implement a *faithful proxy* of its observability/excitation
  criterion, label it clearly as "Qiu-style (our reimplementation)". `[TODO: confirm whether any reference impl exists]`

## TAXONOMY only (no rerun, related-work table)
- VDO-SLAM, DynaSLAM II, ClusterVO — full-system dynamic SLAM; compared qualitatively (they estimate, we refuse).
- SelectiveNet / learning-to-defer / risk-coverage (Geifman & El-Yaniv) — method lineage for our framing.
- Introspective perception / failure prediction for AV — planner-facing reliability lineage.

## Reference table to build (item 10)
| system | estimates object motion? | refusal/abstain? | signal | learned? | decision-level eval? | real data? |
|---|---|---|---|---|---|---|
| Qiu 2018 | yes | binary | geometric observability | no | no | `[TODO verify]` |
| VDO-SLAM | yes | no | — | partial | no | yes |
| DynaSLAM II | yes | no | — | yes(detection) | no | yes |
| **TCSV (ours)** | uses raw | **multi-level selective** | **temporal-consistency** | yes | **yes (risk-coverage)** | yes (KITTI) |
`[TODO: fill/verify each cell against the actual papers before submission]`

## Honest caveats
- Do not claim head-to-head superiority over #3/#7 until they are actually run (currently TODO).
- OVI (#8) is a weak/marginal baseline — present as evidence that geometry-only is insufficient, not as a strawman win.
