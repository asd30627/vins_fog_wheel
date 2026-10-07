# PAPER2 — TCSV × ROBUST-LOSS ABLATION PLAN

> The matrix that separates "TCSV helps VINS" from "Huber / the 3-px backend cull already did it".
> Built on the mechanisms in `PAPER2_VINS_ROBUST_LOSS_AUDIT.md`. Core runs = clean + stable only:
> **Town01 dense_b1, Town01 medium_b1** (per `PAPER2_CLEAN_BENCHMARK_MANIFEST.md`). No invalid runs.
> Date 2026-07-01.

---

## The confounder we are removing

Any masking/weighting acts on the *same* high-reprojection dynamic-object features that the backend
**3-px cull** (`outliersRejection`) already deletes and that **Huber(1.0)** already down-weights.
So a raw before/after ATE delta is a *combined* effect. This matrix isolates each contributor.

Two robust knobs, one method knob:
- **Huber**: on (δ=1.0, stock) | off (`REL_VISUAL_ROBUST_LOSS=0`).
- **3-px backend cull**: on (stock) — kept ON for the 8 core variants; noted as the dominant confounder, optionally probed in an appendix (`outliersRejection` `//return;`).
- **Feature routing**: none | all_dynamic removal | raw_speed_gate | TCSV-M hard | TCSV-M soft | oracle.

---

## The 8 required variants (per run)

| # | variant | routing | Huber | isolates |
|---|---|---|---|---|
| V1 | baseline + robust | none | **on** | stock reference |
| V2 | baseline + robust OFF | none | **off** | **Huber's standalone strength** (V1−V2) |
| V3 | all_dynamic + robust | remove every dynamic-class detection region | on | crude removal ceiling-of-simplicity |
| V4 | raw_speed_gate + robust | mask det with own raw speed > 1 m/s | on | the *observability gate* (what the prior run mislabeled "validity_aware") |
| V5 | TCSV-M hard + robust | mask det with P_full_state_valid < τ | on | learned hard mask vs V3/V4 |
| V6 | **TCSV-M soft + robust** | feat_weight_ = f(P_valid) ∈ (0,1] | on | **the headline method** |
| V7 | TCSV-M soft + robust OFF | same weights, Huber off | **off** | can TCSV *replace* Huber? |
| V8 | oracle + robust | mask by GT (pos_err/vel_err) | on | perfect-knowledge upper bound |

Additional 2×2 read directly from the above (the de-confounding core):

|          | Huber ON | Huber OFF |
|----------|----------|-----------|
| TCSV off | **V1**   | **V2**    |
| TCSV soft| **V6**   | **V7**    |

- V1→V6 = TCSV benefit **with** Huber (is there headroom left after Huber?).
- V2→V7 = TCSV benefit **without** Huber (does TCSV stand alone?).
- V1→V2 = Huber alone. V6−V1 vs V7−V2 = **interaction sign** (complementary / redundant / interfering).

---

## Smoke-test gate (Huber-off may diverge)

Huber-off (V2, V7) can destabilize VINS (large dynamic residuals no longer down-weighted, only the
3-px cull remains). **Do NOT run the full sweep blind.** Order:

1. **V1** (stock) on both runs → confirm reproduces the manifest baseline (Town01 dense early≈1.01 ATE≈3.9; medium early≈0.99 ATE≈3.5).
2. **V2 smoke** (Huber off, no routing) on Town01 dense_b1 **only**. Record: does it finish? early/late scale, ATE, `vins_failure`. 
   - If V2 **diverges / fails** → mark Huber-off as "VINS depends on Huber"; run V7 as smoke only, do **not** claim a clean Huber-off sweep. Report the failure as the result.
   - If V2 **survives** → proceed to full 8×2.
3. Full matrix V3–V8 on both runs only after V1/V2 behave.

---

## Metrics logged per (run × variant)

Trajectory: `ATE_rmse, ATE_mean, RPE_trans, early_scale, late_scale, vins_failure_count`.
VINS internals (from `reliability_features_vins.csv` / `[admission-debug]`):
`tracked_feature_count_raw, tracked_feature_count_mgr, object_region_feat_count (if derivable),
rejected_feature_count (outlier_count_last), outlier_ratio_last, reproj_cost/opt_cost (if instrumented),
huber_saturation_ratio (if instrumented)`.
Deltas: `Δ vs baseline (V1), Δ vs all_dynamic (V3), Δ vs raw_speed_gate (V4), Δ vs oracle (V8)`.

Output → `paper2/track_a/paper2_tcsv_huber_ablation_metrics.csv` + `PAPER2_TCSV_HUBER_ABLATION_RESULTS.md`.

---

## Questions each cell answers

- **How strong is Huber alone?** V1−V2.
- **Does TCSV add anything once Huber is on?** V6 vs V1 (and vs V3/V4).
- **Is TCSV-M > raw_speed_gate?** V6/V5 vs V4.
- **Is TCSV-M ≥ all_dynamic?** V6/V5 vs V3.
- **Soft vs hard stability?** V6 vs V5 (failures, scale).
- **Can TCSV replace Huber?** V7 vs V2 (and V7 vs V6).
- **Complement / overlap / interfere?** sign of (V6−V1) − (V7−V2).
- **Distance to oracle?** V6 vs V8.

---

## Hard constraints (carried from the manifest + memory)

- Core = **Town01 dense_b1 + medium_b1 ONLY**. Town06 dense_b1 = failure-analysis (unstable baseline, ATE 41 m). Town07 dense_b1 = **EXCLUDED** (invalid spawn-collision). No sparse/invalid runs in core.
- Replay discipline: **CARLA must be stopped during replay** (single-thread VINS lags under CARLA CPU → nondeterministic scale). Use the b05 + rate 0.5 + skip-imu-head 150 recipe.
- raw_speed_gate is **NOT** TCSV-M. Keep V4 and V5/V6 strictly separate and labeled.
- n=2 clean runs is **too few to claim** a localization contribution regardless of outcome (per `PAPER2_VINS_LOCALIZATION_CONTRIBUTION_DECISION.md`). This matrix answers the *mechanism* question (is any TCSV effect real and non-Huber), not the *headline-claim* question.
